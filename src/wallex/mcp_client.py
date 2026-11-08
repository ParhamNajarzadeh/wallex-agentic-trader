"""Wallex MCP Server client + Authenticated REST Fallback with Stale Price Refresh."""

from __future__ import annotations

import asyncio
import json
import time
import urllib.request
from typing import Any, Literal

from src.config import ALLOWED_CREDIT_MARKETS, settings
from src.wallex.rest_client import WallexRestClient


class WallexMCPClient:
    """Dual-layer account & order execution client via Wallex MCP + x-api-key REST fallback.

    Enforces:
    - Secret isolation: WALLEX_API_KEY is injected strictly inside HTTP headers, never in LLM context.
    - Stale Price Refresh: Refreshes live orderbook best_bid/best_ask right before order dispatch and
      aborts or reprices if price drifted beyond MAX_PRICE_DRIFT_PCT (0.40%).
    """

    def __init__(self, rest_client: WallexRestClient | None = None) -> None:
        self.rest_client = rest_client or WallexRestClient()
        self.base_url = settings.wallex_base_url.rstrip("/")
        self.mcp_url = settings.wallex_mcp_url

        # Virtual account state for SHADOW / BACKTEST and fallback tracking
        self._balances: dict[str, dict[str, float]] = {
            "TMN": {"free": settings.initial_capital_tmn, "locked": 0.0},
            "USDT": {"free": 0.0, "locked": 0.0},
            "BTC": {"free": 0.0, "locked": 0.0},
            "ETH": {"free": 0.0, "locked": 0.0},
            "SOL": {"free": 0.0, "locked": 0.0},
            "TON": {"free": 0.0, "locked": 0.0},
            "XRP": {"free": 0.0, "locked": 0.0},
        }
        self._open_orders: dict[str, dict[str, Any]] = {}
        self._executed_idempotency_keys: dict[str, dict[str, Any]] = {}

    def _auth_request(
        self, method: str, path: str, payload: dict[str, Any] | None = None
    ) -> dict[str, Any] | None:
        """Execute authenticated request with x-api-key header strictly in Python layer."""
        api_key = settings.get_wallex_api_key()
        if not api_key or api_key == "your_wallex_challenge_account_api_key_here":
            return None
        if settings.execution_mode != "LIVE":
            return None

        url = f"{self.base_url}{path}"
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        req = urllib.request.Request(
            url,
            data=data,
            method=method,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
                "x-api-key": api_key,
                "X-Agent-Identity": settings.agent_virtual_user,
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=4.0) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception:
            return None

    async def get_balances(self) -> dict[str, dict[str, float]]:
        """Query GET /v1/account/balances via MCP/REST or return synchronized shadow ledger."""
        raw = await asyncio.to_thread(self._auth_request, "GET", "/v1/account/balances")
        if raw and "result" in raw and "balances" in raw["result"]:
            parsed: dict[str, dict[str, float]] = {}
            for asset, info in raw["result"]["balances"].items():
                val = float(info.get("value", 0.0) or 0.0)
                locked = float(info.get("locked", 0.0) or 0.0)
                parsed[asset] = {"free": max(0.0, val - locked), "locked": locked}
            return parsed
        return {k: dict(v) for k, v in self._balances.items()}

    async def get_account_fees(self) -> dict[str, float]:
        """Query GET /v1/account/fee for exact Maker/Taker fee tiers."""
        raw = await asyncio.to_thread(self._auth_request, "GET", "/v1/account/fee")
        if raw and "result" in raw:
            return {
                "maker_fee": float(raw["result"].get("makerFeeRate", settings.maker_fee)),
                "taker_fee": float(raw["result"].get("takerFeeRate", settings.taker_fee)),
            }
        return {"maker_fee": settings.maker_fee, "taker_fee": settings.taker_fee}

    async def get_open_orders(self, symbol: str | None = None) -> list[dict[str, Any]]:
        """Query GET /v1/account/openOrders (mandatory for Self-Trade Prevention)."""
        path = f"/v1/account/openOrders?symbol={symbol}" if symbol else "/v1/account/openOrders"
        raw = await asyncio.to_thread(self._auth_request, "GET", path)
        if raw and "result" in raw and "orders" in raw["result"]:
            return list(raw["result"]["orders"])
        orders = list(self._open_orders.values())
        if symbol:
            orders = [o for o in orders if o.get("symbol") == symbol]
        return orders

    async def refresh_and_verify_price(
        self, symbol: str, side: Literal["BUY", "SELL"], proposed_price: float
    ) -> dict[str, Any]:
        """Stale Price Refresh: re-fetch live OrderBook best_bid/best_ask before order submission."""
        ob = await self.rest_client.get_orderbook_depth(symbol, limit=5)
        best_bid = float(ob["best_bid"])
        best_ask = float(ob["best_ask"])
        ref_price = best_ask if side == "BUY" else best_bid
        drift_pct = abs(ref_price - proposed_price) / max(1e-9, proposed_price) * 100.0
        is_stale = drift_pct > settings.max_price_drift_pct
        return {
            "symbol": symbol,
            "best_bid": best_bid,
            "best_ask": best_ask,
            "reference_price": ref_price,
            "proposed_price": proposed_price,
            "drift_pct": round(drift_pct, 4),
            "is_stale": is_stale,
            "refreshed_price": ref_price if not is_stale else proposed_price,
        }

    async def place_order(
        self,
        symbol: str,
        side: Literal["BUY", "SELL"],
        order_type: Literal["LIMIT", "MARKET"],
        quantity: float,
        price: float,
        client_order_id: str,
    ) -> dict[str, Any]:
        """Submit order via POST /v1/account/orders with idempotency and Stale Price Refresh."""
        if client_order_id in self._executed_idempotency_keys:
            cached = dict(self._executed_idempotency_keys[client_order_id])
            cached["idempotent_replay"] = True
            return cached

        if symbol not in ALLOWED_CREDIT_MARKETS:
            return {
                "status": "REJECTED",
                "reason": f"Symbol {symbol} is outside ALLOWED_CREDIT_MARKETS.",
                "clientOrderId": client_order_id,
            }

        refresh_check = await self.refresh_and_verify_price(symbol, side, price)
        if refresh_check["is_stale"]:
            return {
                "status": "ABORTED_STALE_PRICE",
                "reason": (
                    f"Stale price detected: drift {refresh_check['drift_pct']:.3f}% "
                    f"> MAX_PRICE_DRIFT_PCT ({settings.max_price_drift_pct}%)"
                ),
                "refresh_audit": refresh_check,
                "clientOrderId": client_order_id,
            }

        exec_price = (
            refresh_check["reference_price"]
            if order_type == "MARKET"
            else refresh_check["refreshed_price"]
        )
        payload = {
            "symbol": symbol,
            "type": order_type,
            "side": side,
            "price": str(exec_price),
            "quantity": str(quantity),
            "clientOrderId": client_order_id,
        }

        if settings.execution_mode == "LIVE":
            raw = await asyncio.to_thread(self._auth_request, "POST", "/v1/account/orders", payload)
            if raw and raw.get("success"):
                res = {
                    "status": "FILLED_LIVE",
                    "exchange_response": raw.get("result", {}),
                    "symbol": symbol,
                    "side": side,
                    "type": order_type,
                    "executed_price": exec_price,
                    "executed_quantity": quantity,
                    "clientOrderId": client_order_id,
                    "refresh_audit": refresh_check,
                    "timestamp": settings.now_iso(),
                }
                self._executed_idempotency_keys[client_order_id] = res
                return res

        # Deterministic ledger update for SHADOW / BACKTEST or dry-run LIVE without external connectivity
        res = self._apply_local_fill(
            symbol=symbol,
            side=side,
            order_type=order_type,
            quantity=quantity,
            exec_price=exec_price,
            client_order_id=client_order_id,
            refresh_audit=refresh_check,
        )
        self._executed_idempotency_keys[client_order_id] = res
        return res

    def _apply_local_fill(
        self,
        symbol: str,
        side: Literal["BUY", "SELL"],
        order_type: Literal["LIMIT", "MARKET"],
        quantity: float,
        exec_price: float,
        client_order_id: str,
        refresh_audit: dict[str, Any],
    ) -> dict[str, Any]:
        meta = ALLOWED_CREDIT_MARKETS[symbol]
        base_asset = str(meta["base"])
        quote_asset = str(meta["quote"])
        fee_rate = settings.maker_fee if order_type == "LIMIT" else settings.taker_fee
        notional = quantity * exec_price
        fee_quote = notional * fee_rate

        if side == "BUY":
            total_cost = notional + fee_quote
            avail_quote = self._balances.get(quote_asset, {}).get("free", 0.0)
            if total_cost > avail_quote:
                quantity = max(0.0, (avail_quote * 0.995) / (exec_price * (1.0 + fee_rate)))
                notional = quantity * exec_price
                fee_quote = notional * fee_rate
                total_cost = notional + fee_quote
            self._balances[quote_asset]["free"] = max(0.0, avail_quote - total_cost)
            self._balances.setdefault(base_asset, {"free": 0.0, "locked": 0.0})
            self._balances[base_asset]["free"] += quantity
        else:
            avail_base = self._balances.get(base_asset, {}).get("free", 0.0)
            quantity = min(quantity, avail_base)
            notional = quantity * exec_price
            fee_quote = notional * fee_rate
            net_proceeds = max(0.0, notional - fee_quote)
            self._balances[base_asset]["free"] = max(0.0, avail_base - quantity)
            self._balances.setdefault(quote_asset, {"free": 0.0, "locked": 0.0})
            self._balances[quote_asset]["free"] += net_proceeds

        return {
            "status": f"FILLED_{settings.execution_mode}",
            "symbol": symbol,
            "side": side,
            "type": order_type,
            "executed_price": round(exec_price, 4),
            "executed_quantity": round(quantity, 6),
            "notional_quote": round(notional, 2),
            "fee_paid_quote": round(fee_quote, 2),
            "fee_rate": fee_rate,
            "clientOrderId": client_order_id,
            "refresh_audit": refresh_audit,
            "timestamp": settings.now_iso(),
        }

    async def cancel_order(self, client_order_id: str) -> dict[str, Any]:
        """Cancel open order via DELETE /v1/account/orders?clientOrderId={ID}."""
        if settings.execution_mode == "LIVE":
            await asyncio.to_thread(
                self._auth_request,
                "DELETE",
                f"/v1/account/orders?clientOrderId={client_order_id}",
            )
        removed = self._open_orders.pop(client_order_id, None)
        return {
            "status": "CANCELLED",
            "clientOrderId": client_order_id,
            "removed_order": removed,
            "timestamp": settings.now_iso(),
        }

    async def cancel_all_open_orders(self) -> list[dict[str, Any]]:
        """Cancel all open orders on the challenge account."""
        open_list = await self.get_open_orders()
        results = []
        for o in open_list:
            cid = str(o.get("clientOrderId", ""))
            if cid:
                results.append(await self.cancel_order(cid))
        self._open_orders.clear()
        return results

    async def liquidate_all_to_toman(self, reason: str = "END_OF_CYCLE_SETTLEMENT") -> list[dict[str, Any]]:
        """Liquidate 100% of non-Toman holdings back into realized Toman (TMN)."""
        await self.cancel_all_open_orders()
        balances = await self.get_balances()
        settlements: list[dict[str, Any]] = []

        for asset, bal in balances.items():
            if asset == "TMN":
                continue
            free_qty = float(bal.get("free", 0.0))
            if free_qty <= 1e-8:
                continue
            tmn_symbol = f"{asset}TMN"
            if tmn_symbol in ALLOWED_CREDIT_MARKETS:
                ob = await self.rest_client.get_orderbook_depth(tmn_symbol, limit=5)
                cid = f"liq-{asset.lower()}-{int(time.time() * 1000)}"
                fill = await self.place_order(
                    symbol=tmn_symbol,
                    side="SELL",
                    order_type="LIMIT",
                    quantity=free_qty,
                    price=float(ob["best_bid"]),
                    client_order_id=cid,
                )
                fill["liquidation_reason"] = reason
                settlements.append(fill)
        return settlements
