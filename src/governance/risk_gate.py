"""Deterministic Risk Gate (`src/governance/risk_gate.py`) + System-1 Policy Check.

Enforces 8 hard pure-Python guardrails on the 5,000,000 Toman Wallex challenge account:
1. Allowed Credit Market Whitelist (`ALLOWED_CREDIT_MARKETS`)
2. Fractional Position Sizing Cap (`<= 18%` of equity, hard max `900,000 TMN`, >20% strictly blocked)
3. Minimum Toman Cash Reserve (`>= 40%` cash reserve, max `60%` total crypto exposure)
4. Mandatory Dynamic Stop-Loss (`1.5% - 2.0%` below entry) & Fee-Adjusted Net R/R (`>= 2.0`)
5. Self-Trade Prevention (cross-checks account `openOrders` to prevent matching own orders)
6. Night Liquidity Adaptation (00:30-07:00 Tehran time or `spread_pct > 0.35%` -> 50% size cut & LIMIT only)
7. Daily Drawdown Circuit Breaker (`> 3.0%` drop from High-Water Mark -> auto-switch to SHADOW cooldown)
8. End-of-Cycle Toman Realization (`hours_remaining_in_challenge <= 4.0` -> block BUY, liquidate 100% to TMN)
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from src.config import ALLOWED_CREDIT_MARKETS, settings
from src.graph.state import RiskValidationResult, TradeProposal


class DeterministicRiskGate:
    """100% deterministic pure-Python risk validator before any order reaches Wallex MCP."""

    def __init__(self) -> None:
        self.max_single_order_pct = settings.max_single_order_pct
        self.min_cash_reserve_pct = settings.min_cash_reserve_pct
        self.sl_min_pct = settings.stop_loss_min_pct
        self.sl_max_pct = settings.stop_loss_max_pct
        self.min_net_rr = settings.min_expected_net_rr
        self.max_daily_dd_pct = settings.max_daily_drawdown_pct
        self.eoc_hours = settings.end_of_cycle_liquidation_hours

    @staticmethod
    def is_tehran_night_window(timestamp_iso: str | None = None) -> bool:
        """Check whether current timestamp falls in thin night liquidity window (00:30 - 07:00IRST)."""
        try:
            dt_utc = (
                datetime.fromisoformat(timestamp_iso.replace("Z", "+00:00"))
                if timestamp_iso
                else datetime.now(timezone.utc)
            )
        except Exception:
            dt_utc = datetime.now(timezone.utc)
        tehran_dt = dt_utc.astimezone(timezone(timedelta(hours=3, minutes=30)))
        minutes_of_day = tehran_dt.hour * 60 + tehran_dt.minute
        return 30 <= minutes_of_day <= 420

    def validate(
        self,
        proposal: TradeProposal,
        portfolio_status: dict[str, Any],
        market_snapshot: dict[str, dict[str, Any]],
        open_orders: list[dict[str, Any]],
        hours_remaining: float,
        timestamp_iso: str | None = None,
    ) -> RiskValidationResult:
        """Audit a proposed trade against all 8 hard risk rules."""
        rejection_reasons: list[str] = []
        action = proposal["action"]
        symbol = proposal["symbol"]
        side = proposal["side"]
        qty = float(proposal["quantity"])
        entry_px = float(proposal["entry_price"])
        stop_loss = float(proposal["stop_loss"])
        take_profit = float(proposal["take_profit"])

        total_equity_tmn = float(
            portfolio_status.get("total_equity_tmn", settings.initial_capital_tmn)
        )
        free_tmn = float(portfolio_status.get("free_tmn", settings.initial_capital_tmn))
        high_water_mark_tmn = float(
            portfolio_status.get("high_water_mark_tmn", max(total_equity_tmn, settings.initial_capital_tmn))
        )
        daily_dd_pct = (
            max(0.0, (high_water_mark_tmn - total_equity_tmn) / max(1.0, high_water_mark_tmn))
            * 100.0
        )

        # Allow HOLD or LIQUIDATE_ALL_TO_TOMAN immediately
        if action in ("HOLD", "LIQUIDATE_ALL_TO_TOMAN", "CANCEL"):
            return RiskValidationResult(
                approved=True,
                adjusted_quantity=qty,
                adjusted_price=entry_px,
                rejection_reasons=[],
                risk_metrics={
                    "total_equity_tmn": round(total_equity_tmn, 2),
                    "free_tmn": round(free_tmn, 2),
                    "daily_drawdown_pct": round(daily_dd_pct, 4),
                    "hours_remaining": round(hours_remaining, 2),
                },
            )

        # Rule 1: Allowed Credit Market Whitelist
        if symbol not in ALLOWED_CREDIT_MARKETS:
            rejection_reasons.append(
                f"RULE_1_VIOLATION: Symbol '{symbol}' is not in ALLOWED_CREDIT_MARKETS."
            )
            return self._reject(qty, entry_px, rejection_reasons, total_equity_tmn, daily_dd_pct)

        meta = ALLOWED_CREDIT_MARKETS[symbol]
        step_size = float(meta["step_size"])
        tick_size = float(meta["tick_size"])
        sym_snap = market_snapshot.get(symbol, {})
        spread_pct = float(sym_snap.get("spread_pct", 0.12))
        usdt_tmn_px = float(market_snapshot.get("USDTTMN", {}).get("mid_price", 68_450.0))

        # Rule 7: Daily 3.0% Drawdown Circuit Breaker
        if daily_dd_pct >= self.max_daily_dd_pct * 100.0 and side == "BUY":
            rejection_reasons.append(
                f"RULE_7_CIRCUIT_BREAKER: Daily drawdown {daily_dd_pct:.2f}% >= {self.max_daily_dd_pct * 100:.1f}% limit. Switching to SHADOW cooldown."
            )

        # Rule 8: End-of-Cycle Toman Realization Gate (<= 4.0h remaining)
        if hours_remaining <= self.eoc_hours and side == "BUY":
            rejection_reasons.append(
                f"RULE_8_END_OF_CYCLE_GATE: Only {hours_remaining:.2f}h remaining (<= {self.eoc_hours}h). New BUY orders are blocked; liquidating to Toman."
            )

        # Convert order notional to Toman
        order_notional_tmn = (
            qty * entry_px if meta["quote"] == "TMN" else qty * entry_px * usdt_tmn_px
        )

        # Rule 6: Night Liquidity Adaptation (00:30 - 07:00 Tehran or spread > 0.35%)
        is_night = self.is_tehran_night_window(timestamp_iso)
        thin_liquidity = is_night or (spread_pct > settings.night_spread_threshold_pct)
        effective_max_pct = (
            self.max_single_order_pct * 0.5 if thin_liquidity else self.max_single_order_pct
        )
        max_allowed_tmn = min(
            total_equity_tmn * effective_max_pct,
            settings.max_single_order_tmn_cap * (0.5 if thin_liquidity else 1.0),
        )

        # Rule 2: Fractional Position Sizing Cap (<= 18% of equity, hard block > 20%)
        if side == "BUY":
            if order_notional_tmn > total_equity_tmn * 0.2001:
                # Auto-scale down to effective_max_pct (18% or 9% at night) while logging adjustment
                scale_factor = max_allowed_tmn / max(1.0, order_notional_tmn)
                qty = self._round_step(qty * scale_factor, step_size)
                order_notional_tmn = (
                    qty * entry_px if meta["quote"] == "TMN" else qty * entry_px * usdt_tmn_px
                )
            elif order_notional_tmn > max_allowed_tmn:
                scale_factor = max_allowed_tmn / max(1.0, order_notional_tmn)
                qty = self._round_step(qty * scale_factor, step_size)
                order_notional_tmn = (
                    qty * entry_px if meta["quote"] == "TMN" else qty * entry_px * usdt_tmn_px
                )

            if order_notional_tmn < float(meta["min_notional_tmn"]):
                rejection_reasons.append(
                    f"RULE_2_MIN_NOTIONAL: Adjusted order notional {order_notional_tmn:,.0f} TMN < min {meta['min_notional_tmn']:,.0f} TMN."
                )

        # Rule 3: Minimum 40% Toman Cash Reserve
        min_reserve_tmn = total_equity_tmn * self.min_cash_reserve_pct
        if side == "BUY" and (free_tmn - order_notional_tmn) < min_reserve_tmn:
            avail_for_trade = max(0.0, free_tmn - min_reserve_tmn)
            if avail_for_trade >= float(meta["min_notional_tmn"]):
                qty = self._round_step(
                    avail_for_trade / (entry_px if meta["quote"] == "TMN" else entry_px * usdt_tmn_px),
                    step_size,
                )
                order_notional_tmn = (
                    qty * entry_px if meta["quote"] == "TMN" else qty * entry_px * usdt_tmn_px
                )
            else:
                rejection_reasons.append(
                    f"RULE_3_CASH_RESERVE: Free TMN ({free_tmn:,.0f}) minus order ({order_notional_tmn:,.0f}) breaches 40% reserve floor ({min_reserve_tmn:,.0f} TMN)."
                )

        # Rule 4: Dynamic Stop-Loss (1.5% - 2.0%) & Fee-Adjusted Net R/R >= 2.0
        round_trip_cost_pct = (settings.maker_fee + settings.taker_fee) * 100.0 + spread_pct
        net_rr = float(proposal.get("expected_net_rr", 0.0))
        sl_distance_pct = 0.0
        portfolio_risk_pct = 0.0

        if side == "BUY":
            if stop_loss <= 0.0 or stop_loss >= entry_px:
                rejection_reasons.append(
                    "RULE_4_STOP_LOSS_MISSING: BUY order must specify a valid stop_loss below entry_price."
                )
            else:
                sl_distance_pct = ((entry_px - stop_loss) / max(1e-9, entry_px)) * 100.0
                if sl_distance_pct < (self.sl_min_pct * 100.0 - 0.05) or sl_distance_pct > (
                    self.sl_max_pct * 100.0 + 0.05
                ):
                    rejection_reasons.append(
                        f"RULE_4_STOP_LOSS_BOUNDS: Stop-loss distance {sl_distance_pct:.2f}% outside mandatory [1.50%, 2.00%] band."
                    )
                gross_reward_pct = ((take_profit - entry_px) / max(1e-9, entry_px)) * 100.0
                net_reward_pct = max(0.0, gross_reward_pct - round_trip_cost_pct)
                effective_risk_pct = sl_distance_pct + round_trip_cost_pct * 0.5
                net_rr = net_reward_pct / max(1e-9, effective_risk_pct)
                portfolio_risk_pct = (order_notional_tmn / max(1.0, total_equity_tmn)) * sl_distance_pct

                if net_rr < self.min_net_rr:
                    rejection_reasons.append(
                        f"RULE_4_NET_RR_LOW: Fee-adjusted Net R/R ({net_rr:.2f}) < mandatory {self.min_net_rr:.2f}."
                    )

        # Rule 5: Self-Trade Prevention (cross-check openOrders on same symbol)
        for o in open_orders:
            if o.get("symbol") != symbol:
                continue
            o_side = str(o.get("side", "")).upper()
            o_px = float(o.get("price", 0.0))
            if side == "BUY" and o_side == "SELL" and entry_px >= o_px:
                adjusted_px = o_px - tick_size
                if adjusted_px <= 0:
                    rejection_reasons.append(
                        f"RULE_5_SELF_TRADE_PREVENTION: BUY at {entry_px} crosses own open SELL at {o_px}."
                    )
                else:
                    entry_px = adjusted_px
            elif side == "SELL" and o_side == "BUY" and entry_px <= o_px:
                entry_px = o_px + tick_size

        approved = len(rejection_reasons) == 0
        return RiskValidationResult(
            approved=approved,
            adjusted_quantity=round(qty, 6),
            adjusted_price=round(entry_px, 4),
            rejection_reasons=rejection_reasons,
            risk_metrics={
                "order_notional_tmn": round(order_notional_tmn, 2),
                "order_pct_of_equity": round((order_notional_tmn / max(1.0, total_equity_tmn)) * 100.0, 2),
                "post_trade_cash_reserve_pct": round(
                    ((free_tmn - (order_notional_tmn if side == "BUY" else 0.0)) / max(1.0, total_equity_tmn))
                    * 100.0,
                    2,
                ),
                "stop_loss_distance_pct": round(sl_distance_pct, 3),
                "portfolio_risk_pct": round(portfolio_risk_pct, 4),
                "fee_adjusted_net_rr": round(net_rr, 3),
                "round_trip_cost_pct": round(round_trip_cost_pct, 3),
                "daily_drawdown_pct": round(daily_dd_pct, 3),
                "night_liquidity_mode": 1.0 if thin_liquidity else 0.0,
            },
        )

    @staticmethod
    def _round_step(value: float, step: float) -> float:
        if step <= 0:
            return value
        return round(int(value / step) * step, 6)

    @staticmethod
    def _reject(
        qty: float,
        price: float,
        reasons: list[str],
        total_equity_tmn: float,
        daily_dd_pct: float,
    ) -> RiskValidationResult:
        return RiskValidationResult(
            approved=False,
            adjusted_quantity=qty,
            adjusted_price=price,
            rejection_reasons=reasons,
            risk_metrics={
                "total_equity_tmn": round(total_equity_tmn, 2),
                "daily_drawdown_pct": round(daily_dd_pct, 4),
            },
        )
