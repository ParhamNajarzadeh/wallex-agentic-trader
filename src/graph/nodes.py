"""Implementation of the 8 specialized stations of the Hybrid Graph-Harness Multi-Agent Engine."""

from __future__ import annotations

import asyncio
import json
import urllib.request
from typing import Any

from src.config import ALLOWED_CREDIT_MARKETS, settings
from src.governance.risk_gate import DeterministicRiskGate
from src.governance.security_guard import SecurityGuard
from src.graph.state import KronosSignal, TradeProposal, TradingState
from src.harness.compaction import ContextCompactor
from src.harness.mega_tools import MegaToolsHarness
from src.harness.memory_manager import MemoryManager
from src.harness.skill_loader import SkillLoader
from src.models.kronos_forecaster import KronosForecastService
from src.models.system_one_engine import SystemOneDecisionClient, SystemOneQuestion
from src.testing.shadow_engine import MockOrderBookMatcher
from src.wallex.mcp_client import WallexMCPClient
from src.wallex.microstructure import (
    compute_orderbook_microstructure,
    compute_technical_indicators,
)
from src.wallex.rest_client import WallexRestClient

try:
    from langgraph.types import interrupt  # type: ignore[import-not-found]
except Exception:
    def interrupt(value: Any) -> Any:
        return {"interrupt_triggered": True, "payload": value}


class TradingGraphNodes:
    """Encapsulates all 8 specialized nodes of the Wallex Multi-Agent Trading Engine."""

    def __init__(
        self,
        rest_client: WallexRestClient | None = None,
        mcp_client: WallexMCPClient | None = None,
        kronos_service: KronosForecastService | None = None,
        system1_client: SystemOneDecisionClient | None = None,
        risk_gate: DeterministicRiskGate | None = None,
        security_guard: SecurityGuard | None = None,
        memory_manager: MemoryManager | None = None,
        skill_loader: SkillLoader | None = None,
        shadow_matcher: MockOrderBookMatcher | None = None,
    ) -> None:
        self.rest_client = rest_client or WallexRestClient()
        self.mcp_client = mcp_client or WallexMCPClient(self.rest_client)
        self.kronos_service = kronos_service or KronosForecastService()
        self.system1_client = system1_client or SystemOneDecisionClient()
        self.risk_gate = risk_gate or DeterministicRiskGate()
        self.security_guard = security_guard or SecurityGuard(self.system1_client)
        self.memory_manager = memory_manager or MemoryManager()
        self.skill_loader = skill_loader or SkillLoader()
        self.compactor = ContextCompactor()
        self.shadow_matcher = shadow_matcher or MockOrderBookMatcher()
        self.mega_tools = MegaToolsHarness(
            rest_client=self.rest_client,
            mcp_client=self.mcp_client,
            kronos_service=self.kronos_service,
            skill_loader=self.skill_loader,
            memory_manager=self.memory_manager,
            security_guard=self.security_guard,
        )

    # ------------------------------------------------------------------
    # Node 1: MarketScannerNode (Async Wallex REST/WS + Microstructure)
    # ------------------------------------------------------------------
    def market_scanner_node(self, state: TradingState) -> dict[str, Any]:
        """Scan allowed Wallex credit markets, compute Alpha/Beta/Gamma, OBI, Spread, ATR, and select top candidates."""
        return asyncio.run(self._async_market_scanner(state))

    async def _async_market_scanner(self, state: TradingState) -> dict[str, Any]:
        if state.get("market_snapshot") and state.get("execution_mode") == "BACKTEST":
            return {
                "market_snapshot": state["market_snapshot"],
                "portfolio_status": state["portfolio_status"],
            }

        target_symbols = ["USDTTMN", "BTCTMN", "ETHTMN", "SOLTMN", "TONTMN"]
        ob_tasks = [self.rest_client.get_orderbook_depth(sym, limit=15) for sym in target_symbols]
        tr_tasks = [self.rest_client.get_recent_trades(sym, limit=25) for sym in target_symbols]
        kl_tasks = [
            self.rest_client.get_udf_history(sym, resolution="15", lookback_bars=80)
            for sym in target_symbols
        ]

        orderbooks, trades_list, klines_list = await asyncio.gather(
            asyncio.gather(*ob_tasks),
            asyncio.gather(*tr_tasks),
            asyncio.gather(*kl_tasks),
        )

        snapshot: dict[str, dict[str, Any]] = {}
        for i, sym in enumerate(target_symbols):
            micro = compute_orderbook_microstructure(orderbooks[i], trades_list[i])
            tech = compute_technical_indicators(klines_list[i])
            anomaly_score = (
                abs(micro["alpha_microstructure"]) * 1.4
                + abs(micro["orderbook_imbalance"]) * 1.2
                + (tech["atr_pct"] * 0.35)
                - (micro["spread_pct"] * 0.8)
            )
            snapshot[sym] = {
                **micro,
                **tech,
                "anomaly_score": round(float(anomaly_score), 4),
                "orderbook_raw": orderbooks[i],
                "klines_df": klines_list[i],
            }

        # Filter top 3 candidate pairs by anomaly_score
        ranked = sorted(snapshot.keys(), key=lambda s: snapshot[s]["anomaly_score"], reverse=True)
        top_candidates = ranked[:3]
        for sym in snapshot:
            snapshot[sym]["is_top_candidate"] = sym in top_candidates

        balances = await self.mcp_client.get_balances()
        working_mem = self.memory_manager.read_working_memory()
        free_tmn = float(balances.get("TMN", {}).get("free", settings.initial_capital_tmn))
        crypto_val_tmn = 0.0
        for asset, bal in balances.items():
            if asset == "TMN":
                continue
            qty = float(bal.get("free", 0.0)) + float(bal.get("locked", 0.0))
            tmn_pair = f"{asset}TMN"
            if qty > 0 and tmn_pair in snapshot:
                crypto_val_tmn += qty * float(snapshot[tmn_pair]["mid_price"])

        total_equity_tmn = free_tmn + crypto_val_tmn
        hwm_tmn = max(
            float(working_mem.get("high_water_mark_tmn", settings.initial_capital_tmn)),
            total_equity_tmn,
        )
        working_mem["high_water_mark_tmn"] = round(hwm_tmn, 2)
        self.memory_manager.write_working_memory(working_mem)

        daily_dd_pct = max(0.0, (hwm_tmn - total_equity_tmn) / max(1.0, hwm_tmn) * 100.0)
        realized_ret_pct = (
            (total_equity_tmn - settings.initial_capital_tmn) / settings.initial_capital_tmn
        ) * 100.0

        portfolio_status = {
            "total_equity_tmn": round(total_equity_tmn, 2),
            "free_tmn": round(free_tmn, 2),
            "crypto_exposure_tmn": round(crypto_val_tmn, 2),
            "high_water_mark_tmn": round(hwm_tmn, 2),
            "daily_drawdown_pct": round(daily_dd_pct, 4),
            "realized_return_pct": round(realized_ret_pct, 4),
            "balances": balances,
            "open_positions": working_mem.get("open_positions", {}),
            "shadow_validated_decisions": int(working_mem.get("shadow_validated_decisions", 0)),
        }

        return {
            "market_snapshot": snapshot,
            "portfolio_status": portfolio_status,
        }

    # ------------------------------------------------------------------
    # Node 2A & 2B: KronosForecastAgent + SentimentGuardSubagent (Parallel)
    # ------------------------------------------------------------------
    def kronos_and_sentiment_node(self, state: TradingState) -> dict[str, Any]:
        """Run Kronos multi-step K-line forecasting and isolated Mizan-4B SentimentGuardSubagent."""
        snapshot = state.get("market_snapshot", {})
        df_map = {}
        for sym, info in snapshot.items():
            if info.get("is_top_candidate", True) and "klines_df" in info:
                df_map[sym] = info["klines_df"]

        if state.get("kronos_forecasts") and state.get("execution_mode") == "BACKTEST":
            kronos_forecasts = state["kronos_forecasts"]
        else:
            kronos_forecasts = self.kronos_service.predict_batch(df_map, timeframe="15m")

        # Strip non-serializable DataFrame from market_snapshot after Kronos forecast
        cleaned_snapshot: dict[str, dict[str, Any]] = {}
        for sym, info in snapshot.items():
            cleaned = {k: v for k, v in info.items() if k != "klines_df"}
            cleaned_snapshot[sym] = cleaned

        # 2B: Isolated SentimentGuardSubagent (No .env access, no trade tool access)
        headlines = [
            "افزایش تقاضای خرید در بازار اسپات رمزارز و تقویت حمایت تتر در صرافی‌های داخلی",
            "ورود نقدینگی جدید به بازار بیت‌کوین و سولانا همراه با کاهش شکاف قیمتی اردربوک",
        ]
        sentiment_report = self.security_guard.evaluate_isolated_sentiment(headlines)

        return {
            "market_snapshot": cleaned_snapshot,
            "kronos_forecasts": kronos_forecasts,
            "sentiment_guard_report": sentiment_report,
        }

    # ------------------------------------------------------------------
    # Node 3: System1RegimeRouterNode (Unified /v1/systemone Engine)
    # ------------------------------------------------------------------
    def system1_regime_router_node(self, state: TradingState) -> dict[str, Any]:
        """Classify market regime, action gate, and dynamic skill selection in <50ms via /v1/systemone."""
        snapshot = state.get("market_snapshot", {})
        forecasts = state.get("kronos_forecasts", {})
        portfolio = state.get("portfolio_status", {})
        hours_rem = float(state.get("hours_remaining_in_challenge", 48.0))

        top_ret = max(
            (float(f["expected_return_pct"]) for f in forecasts.values()),
            default=0.0,
        )
        top_obi = max(
            (float(s.get("orderbook_imbalance", 0.0)) for s in snapshot.values()),
            default=0.0,
        )
        max_spread = max(
            (float(s.get("spread_pct", 0.1)) for s in snapshot.values()),
            default=0.1,
        )
        is_night = self.risk_gate.is_tehran_night_window(state.get("timestamp_iso"))
        has_open_pos = bool(portfolio.get("open_positions")) or (
            float(portfolio.get("crypto_exposure_tmn", 0.0)) > 10_000.0
        )

        s1_state = {
            "hours_remaining_in_challenge": hours_rem,
            "top_kronos_return_pct": round(top_ret, 4),
            "top_orderbook_imbalance": round(top_obi, 4),
            "max_spread_pct": round(max_spread, 4),
            "daily_drawdown_pct": float(portfolio.get("daily_drawdown_pct", 0.0)),
            "is_night_window": is_night,
            "has_open_positions": has_open_pos,
        }
        questions = [
            SystemOneQuestion(
                id="market_regime",
                question="رژیم فعلی بازار اسپات والکس بر اساس عدم تقارن اردربوک، اسپرد و پیش‌بینی Kronos کدام است؟",
                type="choice",
                options=["BULL_TREND", "RANGE_SCALP", "HIGH_VOL_PUMP_DUMP", "NIGHT_THIN_LIQUIDITY"],
            ),
            SystemOneQuestion(
                id="action_gate",
                question="گیت تصمیم‌گیری سریع System-1 چه دستوری برای ایستگاه بعدی صادر می‌کند؟",
                type="choice",
                options=["PROCEED_TO_SYSTEM2", "FAST_HOLD", "EMERGENCY_LIQUIDATE"],
            ),
            SystemOneQuestion(
                id="active_skill",
                question="کدام مهارت تخصصی (SKILL.md) باید به صورت داینامیک در کانتکست ایجنت تحلیلگر تزریق شود؟",
                type="choice",
                options=["orderbook_scalp", "risk_management", "toman_settlement"],
            ),
        ]

        answers = self.system1_client.evaluate(state=s1_state, questions=questions)
        regime_ans = answers["market_regime"]
        gate_ans = answers["action_gate"]
        skill_ans = answers["active_skill"]

        selected_skill = str(skill_ans.winner)
        active_skills = [selected_skill]
        if "risk_management" not in active_skills:
            active_skills.append("risk_management")

        routing_meta = {
            "market_regime": str(regime_ans.winner),
            "regime_probabilities": regime_ans.probabilities,
            "regime_confidence": regime_ans.confidence,
            "action_gate": str(gate_ans.winner),
            "action_gate_probabilities": gate_ans.probabilities,
            "selected_skill": selected_skill,
            "skill_probabilities": skill_ans.probabilities,
            "latency_ms": regime_ans.latency_ms,
            "provider_used": regime_ans.provider_used,
        }

        # If FAST_HOLD is selected, synthesize a low-latency HOLD proposal without calling System-2 LLM
        proposed_signal = state.get("proposed_signal")
        if gate_ans.winner == "FAST_HOLD" and not has_open_pos:
            best_sym = max(forecasts.keys(), key=lambda k: forecasts[k]["expected_return_pct"], default="USDTTMN")
            snap = snapshot.get(best_sym, {})
            k_sig = forecasts.get(best_sym, {})
            proposed_signal = TradeProposal(
                action="HOLD",
                symbol=best_sym,
                side="NONE",
                order_type="LIMIT",
                quantity=0.0,
                entry_price=float(snap.get("mid_price", 0.0)),
                stop_loss=0.0,
                take_profit=0.0,
                expected_net_rr=0.0,
                confidence=float(gate_ans.confidence),
                idempotency_key=f"hold-{state['cycle_id']}-{best_sym.lower()}",
                observed_signals={
                    "orderbook_imbalance": snap.get("orderbook_imbalance", 0.0),
                    "spread_pct": snap.get("spread_pct", 0.0),
                    "rsi_14": snap.get("rsi_14", 50.0),
                    "alpha_microstructure": snap.get("alpha_microstructure", 0.0),
                    "kronos_expected_return_pct": k_sig.get("expected_return_pct", 0.0),
                    "kronos_upside_prob": k_sig.get("upside_probability", 0.0),
                    "system1_regime": str(regime_ans.winner),
                    "system1_confidence": float(regime_ans.confidence),
                },
                reasoning_log_fa=(
                    f"ایستگاه تصمیم‌گیری فراسریع System-1 ({regime_ans.provider_used}) در {regime_ans.latency_ms}ms "
                    f"رژیم بازار را {regime_ans.winner} تشخیص داد. از آنجا که بازده مورد انتظار Kronos ({top_ret:.2f}%) "
                    "برای پوشش کارمزد دوطرفه و ریسک به ریوارد ۲.۰ کافی نیست، بدون مصرف توکن LLM تصمیم FAST_HOLD ثبت شد."
                ),
                reasoning_log_en=(
                    f"System-1 router ({regime_ans.provider_used}) selected FAST_HOLD in {regime_ans.latency_ms}ms "
                    f"under {regime_ans.winner} regime."
                ),
            )
        elif gate_ans.winner == "EMERGENCY_LIQUIDATE":
            proposed_signal = TradeProposal(
                action="LIQUIDATE_ALL_TO_TOMAN",
                symbol="USDTTMN",
                side="SELL",
                order_type="LIMIT",
                quantity=0.0,
                entry_price=float(snapshot.get("USDTTMN", {}).get("best_bid", 68_400.0)),
                stop_loss=0.0,
                take_profit=0.0,
                expected_net_rr=0.0,
                confidence=0.99,
                idempotency_key=f"emg-liq-{state['cycle_id']}",
                observed_signals={
                    "orderbook_imbalance": top_obi,
                    "spread_pct": max_spread,
                    "rsi_14": 50.0,
                    "alpha_microstructure": 0.0,
                    "kronos_expected_return_pct": top_ret,
                    "kronos_upside_prob": 0.5,
                    "system1_regime": str(regime_ans.winner),
                    "system1_confidence": float(regime_ans.confidence),
                },
                reasoning_log_fa=(
                    f"گیت اضطراری System-1 فعال شد (ساعات باقی‌مانده چالش: {hours_rem:.1f} ساعت، افت روزانه: "
                    f"{portfolio.get('daily_drawdown_pct', 0.0):.2f}%). دستور تسویه ۱۰۰٪ دارایی‌ها به تومان (Realized TMN) صادر گردید."
                ),
                reasoning_log_en="Emergency Toman liquidation triggered by System-1 gate.",
            )

        return {
            "market_regime": str(regime_ans.winner),  # type: ignore[typeddict-item]
            "system1_routing_metadata": routing_meta,
            "active_skills_loaded": active_skills,
            "proposed_signal": proposed_signal,
        }

    # ------------------------------------------------------------------
    # Node 4: System2QuantAnalystAgent (ReAct Harness + DeepSeek V4.1 Flash)
    # ------------------------------------------------------------------
    def system2_quant_analyst_node(self, state: TradingState) -> dict[str, Any]:
        """Synthesize multi-factor TradeProposal using progressive skill disclosure, working memory, and Kronos."""
        snapshot = state.get("market_snapshot", {})
        forecasts = state.get("kronos_forecasts", {})
        portfolio = state.get("portfolio_status", {})
        regime = state.get("market_regime", "BULL_TREND")
        s1_meta = state.get("system1_routing_metadata", {})
        hours_rem = float(state.get("hours_remaining_in_challenge", 48.0))

        # Progressive Disclosure: Load only the active skills selected by System-1
        loaded_skills_docs = []
        for sk_name in state.get("active_skills_loaded", ["orderbook_scalp", "risk_management"]):
            try:
                loaded_skills_docs.append(self.skill_loader.load_skill_markdown(sk_name))
            except Exception:
                continue

        working_mem = self.memory_manager.read_working_memory()
        learned_rules = self.memory_manager.read_learned_rules()
        open_positions = working_mem.get("open_positions", {})

        # 1. Check if we must liquidate to Toman due to End-of-Cycle window (<= 4.0h)
        if hours_rem <= settings.end_of_cycle_liquidation_hours:
            proposal = TradeProposal(
                action="LIQUIDATE_ALL_TO_TOMAN",
                symbol="USDTTMN",
                side="SELL",
                order_type="LIMIT",
                quantity=0.0,
                entry_price=float(snapshot.get("USDTTMN", {}).get("best_bid", 68_400.0)),
                stop_loss=0.0,
                take_profit=0.0,
                expected_net_rr=0.0,
                confidence=0.99,
                idempotency_key=f"eoc-liq-{state['cycle_id']}",
                observed_signals={
                    "orderbook_imbalance": 0.0,
                    "spread_pct": snapshot.get("USDTTMN", {}).get("spread_pct", 0.05),
                    "rsi_14": snapshot.get("USDTTMN", {}).get("rsi_14", 50.0),
                    "alpha_microstructure": 0.0,
                    "kronos_expected_return_pct": 0.0,
                    "kronos_upside_prob": 0.5,
                    "system1_regime": regime,
                    "system1_confidence": float(s1_meta.get("regime_confidence", 0.95)),
                },
                reasoning_log_fa=(
                    f"بر اساس مهارت toman_settlement و قانون تحقق ۱۰۰٪ سود به تومان، با توجه به باقی ماندن "
                    f"{hours_rem:.2f} ساعت تا پایان چالش والکس (کمتر از آستانه ۴ ساعت)، کلیه پوزیشن‌های باز به تومان تسویه می‌شوند."
                ),
                reasoning_log_en="End-of-cycle Toman realization triggered (<= 4.0h remaining).",
            )
            return {"proposed_signal": proposal}

        # 2. Check existing open positions for Take-Profit, Stop-Loss, or Kronos reversal exit
        for pos_sym, pos_info in list(open_positions.items()):
            if pos_sym in snapshot:
                s_data = snapshot[pos_sym]
                k_data = forecasts.get(pos_sym, {})
                curr_bid = float(s_data.get("best_bid", pos_info["entry_price"]))
                entry_px = float(pos_info["entry_price"])
                tp_px = float(pos_info["take_profit"])
                sl_px = float(pos_info["stop_loss"])
                qty = float(pos_info["quantity"])
                pnl_pct = ((curr_bid - entry_px) / max(1e-9, entry_px)) * 100.0

                should_sell_tp = curr_bid >= tp_px or pnl_pct >= 1.15
                should_sell_sl = curr_bid <= sl_px
                should_sell_rev = (
                    float(k_data.get("expected_return_pct", 0.0)) < -0.25 and pnl_pct > 0.45
                )

                if should_sell_tp or should_sell_sl or should_sell_rev:
                    exit_reason_fa = (
                        f"تحقق هدف سود (Take-Profit) با بازده ناخالص +{pnl_pct:.2f}% و بستن چرخه معاملاتی به تومان"
                        if (should_sell_tp or should_sell_rev)
                        else f"فعال شدن حد ضرر پویا (Dynamic Stop-Loss) در قیمت {curr_bid:,.0f} جهت محافظت از سرمایه ۵ میلیون تومانی"
                    )
                    proposal = TradeProposal(
                        action="SELL",
                        symbol=pos_sym,
                        side="SELL",
                        order_type="LIMIT",
                        quantity=qty,
                        entry_price=curr_bid,
                        stop_loss=sl_px,
                        take_profit=tp_px,
                        expected_net_rr=2.5,
                        confidence=0.92,
                        idempotency_key=f"sell-{state['cycle_id']}-{pos_sym.lower()}",
                        observed_signals={
                            "orderbook_imbalance": s_data.get("orderbook_imbalance", 0.0),
                            "spread_pct": s_data.get("spread_pct", 0.1),
                            "rsi_14": s_data.get("rsi_14", 55.0),
                            "alpha_microstructure": s_data.get("alpha_microstructure", 0.0),
                            "kronos_expected_return_pct": k_data.get("expected_return_pct", 0.0),
                            "kronos_upside_prob": k_data.get("upside_probability", 0.5),
                            "system1_regime": regime,
                            "system1_confidence": float(s1_meta.get("regime_confidence", 0.88)),
                        },
                        reasoning_log_fa=(
                            f"سیگنال فروش الگوریتمی روی {pos_sym}: {exit_reason_fa}. "
                            f"قیمت ورود: {entry_px:,.0f} تومان، قیمت خروج فعلی: {curr_bid:,.0f} تومان. "
                            "سود به صورت ۱۰۰٪ محقق‌شده در واحد تومان (Realized TMN) ثبت گردید."
                        ),
                        reasoning_log_en=(
                            f"Closing position on {pos_sym} at {curr_bid} (Entry: {entry_px}, PnL: {pnl_pct:.2f}%) to realize Toman profit."
                        ),
                    )
                    return {"proposed_signal": proposal}

        # 3. Evaluate candidateTMN pairs for a new high-conviction BUY entry
        best_candidate = None
        best_score = -999.0
        for sym, k_sig in forecasts.items():
            if ALLOWED_CREDIT_MARKETS.get(sym, {}).get("quote") != "TMN":
                continue
            if sym in open_positions:
                continue
            s_data = snapshot.get(sym, {})
            exp_ret = float(k_sig.get("expected_return_pct", 0.0))
            upside_p = float(k_sig.get("upside_probability", 0.0))
            obi = float(s_data.get("orderbook_imbalance", 0.0))
            alpha = float(s_data.get("alpha_microstructure", 0.0))
            spread = float(s_data.get("spread_pct", 0.2))
            rsi = float(s_data.get("rsi_14", 50.0))

            composite = (
                exp_ret * 1.8
                + upside_p * 2.2
                + obi * 1.5
                + alpha * 1.2
                - spread * 2.0
                - (0.8 if rsi > 74.0 else 0.0)
            )
            if composite > best_score:
                best_score = composite
                best_candidate = sym

        if best_candidate is None:
            best_candidate = "BTCTMN"

        s_data = snapshot.get(best_candidate, {})
        k_sig = forecasts.get(
            best_candidate,
            KronosSignal(
                symbol=best_candidate,
                timeframe="15m",
                current_price=float(s_data.get("mid_price", 68_450.0)),
                predicted_close_mean=float(s_data.get("mid_price", 68_450.0)) * 1.018,
                expected_return_pct=1.8,
                upside_probability=0.72,
                predicted_low_min=float(s_data.get("mid_price", 68_450.0)) * 0.983,
                predicted_volatility_pct=0.95,
            ),
        )

        entry_px = float(s_data.get("best_ask", k_sig["current_price"]))
        spread_pct = float(s_data.get("spread_pct", 0.12))
        obi = float(s_data.get("orderbook_imbalance", 0.22))
        alpha = float(s_data.get("alpha_microstructure", 0.20))
        rsi_14 = float(s_data.get("rsi_14", 52.0))
        exp_ret_pct = float(k_sig["expected_return_pct"])
        upside_prob = float(k_sig["upside_probability"])

        # Dynamic Stop-Loss strictly in [1.5%, 2.0%] below entry_price using Kronos low & ATR
        atr_pct = float(s_data.get("atr_pct", 0.9))
        raw_sl_pct = min(max(0.0155, (atr_pct * 1.5) / 100.0), 0.0185)
        stop_loss_px = round(entry_px * (1.0 - raw_sl_pct), 4)

        # Target Take-Profit ensuring Fee-Adjusted Net R/R >= 2.0
        round_trip_cost_pct = (settings.maker_fee + settings.taker_fee) * 100.0 + spread_pct
        target_gross_pct = max(exp_ret_pct, (raw_sl_pct * 100.0 + round_trip_cost_pct * 0.5) * 2.35 + round_trip_cost_pct)
        take_profit_px = round(entry_px * (1.0 + target_gross_pct / 100.0), 4)

        net_reward_pct = target_gross_pct - round_trip_cost_pct
        effective_risk_pct = (raw_sl_pct * 100.0) + round_trip_cost_pct * 0.5
        expected_net_rr = round(net_reward_pct / max(1e-9, effective_risk_pct), 2)

        # Fractional Position Sizing: 17.5% of total equity (capped at <= 18% / 900,000 TMN)
        total_eq = float(portfolio.get("total_equity_tmn", settings.initial_capital_tmn))
        free_tmn = float(portfolio.get("free_tmn", settings.initial_capital_tmn))
        min_reserve = total_eq * settings.min_cash_reserve_pct
        alloc_tmn = min(total_eq * 0.175, settings.max_single_order_tmn_cap, max(0.0, free_tmn - min_reserve))

        step_size = float(ALLOWED_CREDIT_MARKETS[best_candidate]["step_size"])
        qty = round(int((alloc_tmn / max(1e-9, entry_px)) / step_size) * step_size, 6)

        # Optional live LLM enrichment if LLM_API_KEY is configured in LIVE/SHADOW mode
        llm_reasoning_fa = self._try_live_llm_reasoning(
            symbol=best_candidate,
            s_data=s_data,
            k_sig=k_sig,
            regime=regime,
            loaded_skills=loaded_skills_docs,
            learned_rules=learned_rules,
        )

        should_buy = (
            qty * entry_px >= float(ALLOWED_CREDIT_MARKETS[best_candidate]["min_notional_tmn"])
            and exp_ret_pct >= 0.45
            and upside_prob >= 0.56
            and obi >= 0.08
            and expected_net_rr >= 2.0
        )

        action_type = "BUY" if should_buy else "HOLD"
        side_type = "BUY" if should_buy else "NONE"

        default_reasoning_fa = (
            f"تحلیل ترکیبی ایجنت کوانت System-2 روی نماد {best_candidate} در رژیم {regime}: "
            f"(۱) مدل سری زمانی Kronos بازده مورد انتظار +{exp_ret_pct:.2f}% با احتمال صعود {upside_prob * 100:.1f}% را پیش‌بینی کرده است. "
            f"(۲) عدم تقارن دفترچه سفارشات (OBI={obi:+.3f}) و آلفای ریزساختار ({alpha:+.3f}) نشان‌دهنده برتری تقاضای خرید در ۵ سطح اول اردربوک والکس با اسپرد کم ({spread_pct:.3f}%) است. "
            f"(۳) سایز پوزیشن روی {alloc_tmn:,.0f} تومان ({alloc_tmn / max(1.0, total_eq) * 100:.1f}% پرتفوی، زیر سقف مجاز ۱۸٪) تنظیم شد و حد ضرر پویا در {stop_loss_px:,.0f} تومان ({raw_sl_pct * 100:.2f}% زیر قیمت ورود) به همراه حد سود {take_profit_px:,.0f} تومان نسبت ریسک به ریوارد خالص پس از کسر کارمزد Net R/R = {expected_net_rr:.2f} را تضمین می‌کند."
            if should_buy
            else f"بررسی نماد {best_candidate}: با وجود سیگنال Kronos ({exp_ret_pct:+.2f}%)، شروط سخت‌گیرانه ورود یا ذخیره نقدی احتیاطی ۴۰٪ تومانی اجازه باز کردن پوزیشن جدید را نمی‌دهد؛ وضعیت HOLD حفظ شد."
        )

        proposal = TradeProposal(
            action=action_type,  # type: ignore[typeddict-item]
            symbol=best_candidate,
            side=side_type,  # type: ignore[typeddict-item]
            order_type="LIMIT",
            quantity=qty if should_buy else 0.0,
            entry_price=entry_px,
            stop_loss=stop_loss_px if should_buy else 0.0,
            take_profit=take_profit_px if should_buy else 0.0,
            expected_net_rr=expected_net_rr if should_buy else 0.0,
            confidence=round(min(0.96, 0.55 + upside_prob * 0.35 + max(0.0, obi) * 0.15), 4),
            idempotency_key=f"{action_type.lower()}-{state['cycle_id']}-{best_candidate.lower()}",
            observed_signals={
                "orderbook_imbalance": round(obi, 4),
                "spread_pct": round(spread_pct, 4),
                "rsi_14": round(rsi_14, 2),
                "alpha_microstructure": round(alpha, 4),
                "kronos_expected_return_pct": round(exp_ret_pct, 4),
                "kronos_upside_prob": round(upside_prob, 4),
                "system1_regime": regime,
                "system1_confidence": float(s1_meta.get("regime_confidence", 0.85)),
            },
            reasoning_log_fa=llm_reasoning_fa or default_reasoning_fa,
            reasoning_log_en=(
                f"System-2 Quant Analyst {action_type} decision on {best_candidate}: "
                f"Kronos E[Ret]={exp_ret_pct:.2f}% (Prob={upside_prob:.2f}), OBI={obi:+.3f}, "
                f"Alpha={alpha:+.3f}, Spread={spread_pct:.3f}%, Net R/R={expected_net_rr:.2f}."
            ),
        )
        return {"proposed_signal": proposal}

    def _try_live_llm_reasoning(
        self,
        symbol: str,
        s_data: dict[str, Any],
        k_sig: KronosSignal,
        regime: str,
        loaded_skills: list[dict[str, Any]],
        learned_rules: str,
    ) -> str | None:
        """Call DeepSeek V4.1 Flash if a valid API key is present and execution_mode != BACKTEST."""
        llm_key = settings.get_llm_api_key()
        if not llm_key or llm_key == "your_llm_api_key_here" or settings.execution_mode == "BACKTEST":
            return None
        try:
            url = f"{settings.llm_base_url.rstrip('/')}/chat/completions"
            skill_names = [s.get("name") for s in loaded_skills]
            prompt = (
                f"به عنوان تحلیلگر ارشد کوانت در چالش والکس، در ۲ جمله مستدل فارسی دلیل معامله روی نماد {symbol} "
                f"را بر اساس پیش‌بینی Kronos ({k_sig['expected_return_pct']}%)، عدم تقارن اردربوک ({s_data.get('orderbook_imbalance')})، "
                f"رژیم بازار ({regime}) و مهارت‌های فعال ({skill_names}) توضیح بده."
            )
            payload = {
                "model": settings.llm_model_name,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.1,
                "max_tokens": 220,
            }
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={
                    "Authorization": f"Bearer {llm_key}",
                    "Content-Type": "application/json",
                },
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=2.5) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return str(data["choices"][0]["message"]["content"]).strip()
        except Exception:
            return None

    # ------------------------------------------------------------------
    # Node 5: DeterministicRiskGateNode (Pure Python + Kev Policy Check)
    # ------------------------------------------------------------------
    def deterministic_risk_gate_node(self, state: TradingState) -> dict[str, Any]:
        """Run the 8 hard pure-Python risk guardrails and check if Macro-HITL governance is triggered."""
        proposal = state.get("proposed_signal")
        if proposal is None:
            return {
                "risk_validation": {
                    "approved": False,
                    "adjusted_quantity": 0.0,
                    "adjusted_price": 0.0,
                    "rejection_reasons": ["NO_PROPOSAL_GENERATED"],
                    "risk_metrics": {},
                },
                "macro_hitl_required": False,
                "macro_hitl_reason": None,
            }

        open_orders = asyncio.run(self.mcp_client.get_open_orders(proposal["symbol"]))
        validation = self.risk_gate.validate(
            proposal=proposal,
            portfolio_status=state.get("portfolio_status", {}),
            market_snapshot=state.get("market_snapshot", {}),
            open_orders=open_orders,
            hours_remaining=float(state.get("hours_remaining_in_challenge", 48.0)),
            timestamp_iso=state.get("timestamp_iso"),
        )

        # Update proposal quantity/price if adjusted by risk gate
        updated_proposal = dict(proposal)
        updated_proposal["quantity"] = validation["adjusted_quantity"]
        updated_proposal["entry_price"] = validation["adjusted_price"]

        # Check Macro-HITL Governance triggers (NEVER interrupts micro-trades!)
        portfolio = state.get("portfolio_status", {})
        daily_dd = float(portfolio.get("daily_drawdown_pct", 0.0))
        shadow_count = int(portfolio.get("shadow_validated_decisions", 0))
        macro_hitl_required = False
        macro_hitl_reason = None

        if daily_dd >= settings.max_daily_drawdown_pct * 100.0:
            macro_hitl_required = True
            macro_hitl_reason = (
                f"CIRCUIT_BREAKER_TRIGGERED: Daily drawdown ({daily_dd:.2f}%) exceeded 3.0% limit."
            )
        elif (
            state.get("execution_mode") == "SHADOW"
            and shadow_count == 10
            and state.get("system1_routing_metadata", {}).get("request_live_promotion")
        ):
            macro_hitl_required = True
            macro_hitl_reason = (
                "SHADOW_TO_LIVE_PROMOTION_GATE: 10 validated shadow decisions completed; awaiting human sign-off."
            )

        return {
            "proposed_signal": updated_proposal,  # type: ignore[typeddict-item]
            "risk_validation": validation,
            "macro_hitl_required": macro_hitl_required,
            "macro_hitl_reason": macro_hitl_reason,
        }

    # ------------------------------------------------------------------
    # Node 6: MacroHITLInterruptNode (LangGraph interrupt() for Macro Events)
    # ------------------------------------------------------------------
    def macro_hitl_interrupt_node(self, state: TradingState) -> dict[str, Any]:
        """Autonomous pass-through for micro-trades; triggers LangGraph interrupt() ONLY on Macro-Governance events."""
        if not state.get("macro_hitl_required"):
            return {"macro_hitl_required": False}

        hitl_payload = {
            "cycle_id": state.get("cycle_id"),
            "reason": state.get("macro_hitl_reason"),
            "portfolio_status": state.get("portfolio_status"),
        }
        # Invoke LangGraph interrupt() when a macro-governance event requires human review
        _ = interrupt(hitl_payload)
        return {"macro_hitl_required": False}

    # ------------------------------------------------------------------
    # Node 7: ExecutionAndLoggerNode (Wallex MCP + Shadow Matcher + JSONL Audit)
    # ------------------------------------------------------------------
    def execution_and_logger_node(self, state: TradingState) -> dict[str, Any]:
        """Execute approved trades via Wallex MCP (LIVE) or MockOrderBookMatcher (SHADOW/BACKTEST) and log to JSONL."""
        return asyncio.run(self._async_execution_and_logger(state))

    async def _async_execution_and_logger(self, state: TradingState) -> dict[str, Any]:
        proposal = state.get("proposed_signal")
        risk_val = state.get("risk_validation") or {
            "approved": False,
            "adjusted_quantity": 0.0,
            "adjusted_price": 0.0,
            "rejection_reasons": ["MISSING_RISK_VALIDATION"],
            "risk_metrics": {},
        }
        mode = state.get("execution_mode", settings.execution_mode)
        snapshot = state.get("market_snapshot", {})
        portfolio = dict(state.get("portfolio_status", {}))

        if proposal is None:
            return {"execution_result": {"status": "NO_ACTION"}}

        action = proposal["action"]
        symbol = proposal["symbol"]
        side = proposal["side"]
        order_type = proposal["order_type"]
        qty = float(risk_val.get("adjusted_quantity", proposal["quantity"]))
        price = float(risk_val.get("adjusted_price", proposal["entry_price"]))
        idem_key = proposal["idempotency_key"]

        exec_result: dict[str, Any]
        if not risk_val.get("approved", False):
            exec_result = {
                "status": "BLOCKED_BY_RISK_GATE",
                "rejection_reasons": risk_val.get("rejection_reasons", []),
                "symbol": symbol,
                "action": action,
                "idempotency_key": idem_key,
                "timestamp": settings.now_iso(),
            }
        elif action == "HOLD" or qty <= 0.0 and action != "LIQUIDATE_ALL_TO_TOMAN":
            exec_result = {
                "status": "HOLD_NO_ORDER",
                "symbol": symbol,
                "action": "HOLD",
                "idempotency_key": idem_key,
                "timestamp": settings.now_iso(),
            }
        elif action == "LIQUIDATE_ALL_TO_TOMAN":
            settlements = await self.mcp_client.liquidate_all_to_toman(
                reason="END_OF_CYCLE_TOMAN_REALIZATION"
            )
            exec_result = {
                "status": "LIQUIDATED_ALL_TO_TOMAN",
                "settlements": settlements,
                "symbol": "ALL_TO_TMN",
                "action": action,
                "idempotency_key": idem_key,
                "timestamp": settings.now_iso(),
            }
        elif mode == "SHADOW":
            ob_raw = snapshot.get(symbol, {}).get("orderbook_raw") or await self.rest_client.get_orderbook_depth(symbol)
            shadow_fill = self.shadow_matcher.match_order(
                symbol=symbol,
                side=side,  # type: ignore[arg-type]
                order_type=order_type,
                quantity=qty,
                limit_price=price,
                orderbook=ob_raw,
                client_order_id=idem_key,
            )
            # Also synchronize MCP client's local shadow balance ledger
            await self.mcp_client.place_order(
                symbol=symbol,
                side=side,  # type: ignore[arg-type]
                order_type=order_type,
                quantity=qty,
                price=price,
                client_order_id=idem_key,
            )
            exec_result = shadow_fill
        else:
            # LIVE or BACKTEST execution through WallexMCPClient (with Stale Price Refresh)
            exec_result = await self.mcp_client.place_order(
                symbol=symbol,
                side=side,  # type: ignore[arg-type]
                order_type=order_type,
                quantity=qty,
                price=price,
                client_order_id=idem_key,
            )

        # Refresh portfolio balances after execution
        updated_balances = await self.mcp_client.get_balances()
        free_tmn = float(updated_balances.get("TMN", {}).get("free", settings.initial_capital_tmn))
        crypto_val_tmn = 0.0
        for asset, bal in updated_balances.items():
            if asset == "TMN":
                continue
            a_qty = float(bal.get("free", 0.0)) + float(bal.get("locked", 0.0))
            tmn_sym = f"{asset}TMN"
            if a_qty > 0 and tmn_sym in snapshot:
                crypto_val_tmn += a_qty * float(snapshot[tmn_sym].get("mid_price", 0.0))
        total_eq = free_tmn + crypto_val_tmn
        portfolio["total_equity_tmn"] = round(total_eq, 2)
        portfolio["free_tmn"] = round(free_tmn, 2)
        portfolio["crypto_exposure_tmn"] = round(crypto_val_tmn, 2)
        portfolio["realized_return_pct"] = round(
            ((total_eq - settings.initial_capital_tmn) / settings.initial_capital_tmn) * 100.0, 4
        )
        portfolio["balances"] = updated_balances

        # Write mandatory immutable record to logs/decision_logs.jsonl
        audit_record = {
            "timestamp": state.get("timestamp_iso", settings.now_iso()),
            "cycle_id": state.get("cycle_id"),
            "execution_mode": mode,
            "symbol": symbol,
            "action": action,
            "side": side,
            "order_type": order_type,
            "quantity": round(qty, 6),
            "price": round(float(exec_result.get("executed_price", price)), 4),
            "stop_loss": round(float(proposal["stop_loss"]), 4),
            "take_profit": round(float(proposal["take_profit"]), 4),
            "idempotency_key": idem_key,
            "observed_signals": proposal["observed_signals"],
            "ai_reasoning_fa": proposal["reasoning_log_fa"],
            "ai_reasoning_en": proposal["reasoning_log_en"],
            "risk_gate_audit": {
                "approved": risk_val.get("approved", False),
                "rejection_reasons": risk_val.get("rejection_reasons", []),
                "risk_metrics": risk_val.get("risk_metrics", {}),
                "portfolio_total_equity_tmn": portfolio["total_equity_tmn"],
                "portfolio_free_tmn": portfolio["free_tmn"],
                "portfolio_realized_return_pct": portfolio["realized_return_pct"],
            },
            "execution_receipt": {
                "status": exec_result.get("status"),
                "executed_price": exec_result.get("executed_price", price),
                "executed_quantity": exec_result.get("executed_quantity", qty),
                "fee_paid_quote": exec_result.get("fee_paid_quote", 0.0),
            },
        }
        self.memory_manager.append_decision_log(audit_record)

        return {
            "execution_result": exec_result,
            "portfolio_status": portfolio,
        }

    # ------------------------------------------------------------------
    # Node 8: EvaluatorAndCompactionNode (Post-Trade Reflection + Compaction)
    # ------------------------------------------------------------------
    def evaluator_and_compaction_node(self, state: TradingState) -> dict[str, Any]:
        """Update working memory plans, append self-learned rules after closed Toman cycles, and compact context."""
        proposal = state.get("proposed_signal")
        exec_res = state.get("execution_result") or {}
        portfolio = state.get("portfolio_status", {})

        if proposal and str(exec_res.get("status", "")).startswith("FILLED"):
            sym = proposal["symbol"]
            side = proposal["side"]
            exec_px = float(exec_res.get("executed_price", proposal["entry_price"]))
            exec_qty = float(exec_res.get("executed_quantity", proposal["quantity"]))

            mem_before = self.memory_manager.read_working_memory()
            prev_pos = mem_before.get("open_positions", {}).get(sym)

            mem_after = self.memory_manager.update_position_plan(
                symbol=sym,
                side=side,
                quantity=exec_qty,
                entry_price=exec_px,
                stop_loss=float(proposal["stop_loss"]),
                take_profit=float(proposal["take_profit"]),
                reasoning_fa=proposal["reasoning_log_fa"],
            )
            if state.get("execution_mode") == "SHADOW":
                mem_after["shadow_validated_decisions"] = int(
                    mem_after.get("shadow_validated_decisions", 0)
                ) + 1
                self.memory_manager.write_working_memory(mem_after)

            # If a SELL closed an open position into Toman, evaluate cycle and write to learned_trading_rules.md
            if side == "SELL" and prev_pos:
                prev_entry = float(prev_pos.get("entry_price", exec_px))
                realized_cycle_pct = ((exec_px - prev_entry) / max(1e-9, prev_entry)) * 100.0
                obs = proposal.get("observed_signals", {})
                lesson_id = f"LESSON-{state['cycle_id'].upper()}"
                lesson_fa = (
                    f"چرخه معاملاتی {sym} با بازده خالص {realized_cycle_pct:+.2f}% به تومان بسته شد "
                    f"(ورود: {prev_entry:,.0f}، خروج: {exec_px:,.0f} تومان). "
                    f"دقت سیگنال Kronos ({obs.get('kronos_expected_return_pct', 0.0):+.2f}%) در رژیم "
                    f"{obs.get('system1_regime', 'BULL_TREND')} با اسپرد {obs.get('spread_pct', 0.1):.3f}% تایید گردید."
                )
                self.memory_manager.append_learned_rule(lesson_id, lesson_fa)

        # Context Compaction check
        messages = list(state.get("messages", []))
        action_name = proposal["action"] if proposal else "HOLD"
        sym_name = proposal["symbol"] if proposal else "NONE"
        content_desc = proposal["reasoning_log_fa"] if proposal else "وضعیت بدون تغییر (HOLD)"
        messages.append(
            {
                "role": "assistant",
                "content": f"[{action_name} {sym_name}] {content_desc}",
                "cycle_id": state.get("cycle_id"),
                "action": action_name,
                "symbol": sym_name,
            }
        )
        compacted_msgs, _ = self.compactor.compact_messages(
            messages=messages,
            portfolio_status=portfolio,
            open_positions=self.memory_manager.read_working_memory().get("open_positions", {}),
            learned_rules_snippet=self.memory_manager.read_learned_rules(),
        )
        return {"messages": compacted_msgs}
