"""Shadow Testing Engine (`MockOrderBookMatcher`) matching virtual orders against live Wallex OrderBooks."""

from __future__ import annotations

from typing import Any, Literal

from src.config import ALLOWED_CREDIT_MARKETS, settings
from src.wallex.microstructure import estimate_vwap_slippage_pct


class MockOrderBookMatcher:
    """Matches virtual SHADOW orders against real-time Wallex OrderBook depth with realistic slippage & fees."""

    def __init__(self, initial_capital_tmn: float | None = None) -> None:
        self.initial_capital_tmn = initial_capital_tmn or settings.initial_capital_tmn
        self.shadow_fills: list[dict[str, Any]] = []

    def match_order(
        self,
        symbol: str,
        side: Literal["BUY", "SELL"],
        order_type: Literal["LIMIT", "MARKET"],
        quantity: float,
        limit_price: float,
        orderbook: dict[str, Any],
        client_order_id: str,
    ) -> dict[str, Any]:
        """Match order against live bids/asks depth and compute exact VWAP fill price and Wallex fee."""
        meta = ALLOWED_CREDIT_MARKETS.get(symbol, {"base": "USDT", "quote": "TMN"})
        bids = orderbook.get("bids", [])
        asks = orderbook.get("asks", [])
        best_bid = float(orderbook.get("best_bid", limit_price))
        best_ask = float(orderbook.get("best_ask", limit_price))

        levels = asks if side == "BUY" else bids
        target_notional = quantity * limit_price
        slippage_pct = (
            estimate_vwap_slippage_pct(levels, target_notional)
            if order_type == "MARKET"
            else 0.02
        )

        if side == "BUY":
            base_px = best_ask if order_type == "MARKET" else min(limit_price, best_ask)
            exec_price = base_px * (1.0 + slippage_pct / 100.0)
        else:
            base_px = best_bid if order_type == "MARKET" else max(limit_price, best_bid)
            exec_price = base_px * (1.0 - slippage_pct / 100.0)

        fee_rate = settings.maker_fee if order_type == "LIMIT" else settings.taker_fee
        notional_quote = quantity * exec_price
        fee_quote = notional_quote * fee_rate

        receipt = {
            "status": "FILLED_SHADOW",
            "symbol": symbol,
            "base_asset": meta["base"],
            "quote_asset": meta["quote"],
            "side": side,
            "type": order_type,
            "requested_price": round(limit_price, 4),
            "executed_price": round(exec_price, 4),
            "executed_quantity": round(quantity, 6),
            "notional_quote": round(notional_quote, 2),
            "fee_paid_quote": round(fee_quote, 2),
            "slippage_pct": round(slippage_pct, 4),
            "clientOrderId": client_order_id,
            "timestamp": settings.now_iso(),
        }
        self.shadow_fills.append(receipt)
        return receipt
