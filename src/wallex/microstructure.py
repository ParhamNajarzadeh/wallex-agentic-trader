"""Market Microstructure Engine: Alpha, Beta, Gamma, OrderBook Imbalance, Spread, ATR, and Slippage."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd


def compute_orderbook_microstructure(
    orderbook: dict[str, Any], recent_trades: list[dict[str, Any]] | None = None
) -> dict[str, float]:
    """Compute OrderBook Imbalance (OBI), Spread, Depth-Weighted Pressure, and Microstructure Alpha/Beta/Gamma.

    Formulas:
    - OBI (Level-5): (V_bid - V_ask) / (V_bid + V_ask) in [-1, +1]
    - Alpha (Micro-price lead): (MicroPrice - MidPrice) / Spread
    - Beta (Order-flow toxicity / aggressive buy ratio): (V_buy_trades - V_sell_trades) / V_total_trades
    - Gamma (Convexity / Depth decay slope): ratio of top-3 liquidity to top-10 liquidity
    """
    bids = orderbook.get("bids", [])[:10]
    asks = orderbook.get("asks", [])[:10]
    if not bids or not asks:
        return {
            "best_bid": 0.0,
            "best_ask": 0.0,
            "mid_price": 0.0,
            "micro_price": 0.0,
            "spread_pct": 0.0,
            "orderbook_imbalance": 0.0,
            "alpha_microstructure": 0.0,
            "beta_orderflow": 0.0,
            "gamma_convexity": 0.0,
            "estimated_slippage_pct": 0.0,
            "bid_depth_top5_quote": 0.0,
            "ask_depth_top5_quote": 0.0,
        }

    best_bid = float(bids[0]["price"])
    best_ask = float(asks[0]["price"])
    best_bid_qty = float(bids[0]["quantity"])
    best_ask_qty = float(asks[0]["quantity"])

    mid_price = 0.5 * (best_bid + best_ask)
    spread = max(1e-9, best_ask - best_bid)
    spread_pct = (spread / max(1e-9, mid_price)) * 100.0

    # Micro-price weighted by top-of-book opposite queue sizes
    micro_price = (best_bid * best_ask_qty + best_ask * best_bid_qty) / max(
        1e-9, best_bid_qty + best_ask_qty
    )

    # Top-5 decayed volume imbalance
    weights = [np.exp(-0.25 * i) for i in range(min(5, len(bids), len(asks)))]
    v_bid = sum(w * float(bids[i]["quantity"]) for i, w in enumerate(weights))
    v_ask = sum(w * float(asks[i]["quantity"]) for i, w in enumerate(weights))
    obi = (v_bid - v_ask) / max(1e-9, v_bid + v_ask)

    # Alpha: Microprice displacement normalized by spread + OBI contribution
    alpha = ((micro_price - mid_price) / spread) + 0.65 * obi

    # Beta: Tape order-flow imbalance
    beta = 0.0
    if recent_trades:
        buy_vol = sum(float(t["quantity"]) for t in recent_trades if t.get("is_buy_order"))
        sell_vol = sum(float(t["quantity"]) for t in recent_trades if not t.get("is_buy_order"))
        beta = (buy_vol - sell_vol) / max(1e-9, buy_vol + sell_vol)

    # Gamma: Orderbook depth concentration (top 3 vs top 10)
    top3_depth = sum(float(b["quantity"]) for b in bids[:3]) + sum(
        float(a["quantity"]) for a in asks[:3]
    )
    top10_depth = sum(float(b["quantity"]) for b in bids[:10]) + sum(
        float(a["quantity"]) for a in asks[:10]
    )
    gamma = top3_depth / max(1e-9, top10_depth)

    bid_depth_quote = sum(float(b["price"]) * float(b["quantity"]) for b in bids[:5])
    ask_depth_quote = sum(float(a["price"]) * float(a["quantity"]) for a in asks[:5])

    # Estimate slippage for a typical 850,000 TMN order
    est_slippage_pct = estimate_vwap_slippage_pct(asks, target_notional=850_000.0)

    return {
        "best_bid": round(best_bid, 4),
        "best_ask": round(best_ask, 4),
        "mid_price": round(mid_price, 4),
        "micro_price": round(micro_price, 4),
        "spread_pct": round(float(spread_pct), 4),
        "orderbook_imbalance": round(float(obi), 4),
        "alpha_microstructure": round(float(alpha), 4),
        "beta_orderflow": round(float(beta), 4),
        "gamma_convexity": round(float(gamma), 4),
        "estimated_slippage_pct": round(float(est_slippage_pct), 4),
        "bid_depth_top5_quote": round(float(bid_depth_quote), 2),
        "ask_depth_top5_quote": round(float(ask_depth_quote), 2),
    }


def estimate_vwap_slippage_pct(levels: list[dict[str, Any]], target_notional: float) -> float:
    """Calculate expected VWAP slippage percentage against best quote for a given order notional."""
    if not levels or target_notional <= 0:
        return 0.0
    top_px = float(levels[0]["price"])
    rem_notional = target_notional
    accum_qty = 0.0
    accum_cost = 0.0
    for lvl in levels:
        px = float(lvl["price"])
        qty = float(lvl["quantity"])
        lvl_notional = px * qty
        take_notional = min(rem_notional, lvl_notional)
        take_qty = take_notional / max(1e-9, px)
        accum_cost += take_notional
        accum_qty += take_qty
        rem_notional -= take_notional
        if rem_notional <= 1e-6:
            break
    if accum_qty <= 0:
        return 0.0
    vwap = accum_cost / accum_qty
    return abs(vwap - top_px) / max(1e-9, top_px) * 100.0


def compute_technical_indicators(df: pd.DataFrame) -> dict[str, float]:
    """Compute RSI-14, ATR-14, EMA-9/EMA-21 spread, and realized volatility from OHLCV K-lines."""
    if df.empty or len(df) < 15:
        return {
            "rsi_14": 50.0,
            "atr_14": 0.0,
            "atr_pct": 0.8,
            "ema_9": 0.0,
            "ema_21": 0.0,
            "ema_spread_pct": 0.0,
            "realized_vol_pct": 1.0,
        }

    close = df["close"].astype(float)
    high = df["high"].astype(float)
    low = df["low"].astype(float)

    # RSI-14
    delta = close.diff()
    gain = delta.clip(lower=0.0).rolling(window=14, min_periods=1).mean()
    loss = (-delta.clip(upper=0.0)).rolling(window=14, min_periods=1).mean()
    rs = gain / loss.replace(0.0, 1e-9)
    rsi_series = 100.0 - (100.0 / (1.0 + rs))
    rsi_14 = float(rsi_series.iloc[-1])

    # ATR-14
    prev_close = close.shift(1).bfill()
    tr = pd.concat(
        [
            (high - low).abs(),
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    atr_14 = float(tr.rolling(window=14, min_periods=1).mean().iloc[-1])
    last_close = float(close.iloc[-1])
    atr_pct = (atr_14 / max(1e-9, last_close)) * 100.0

    # EMA-9 & EMA-21
    ema_9 = float(close.ewm(span=9, adjust=False).mean().iloc[-1])
    ema_21 = float(close.ewm(span=21, adjust=False).mean().iloc[-1])
    ema_spread_pct = ((ema_9 - ema_21) / max(1e-9, ema_21)) * 100.0

    # Realized Volatility (%)
    returns = close.pct_change().dropna()
    realized_vol_pct = float(returns.tail(24).std() * np.sqrt(24) * 100.0) if len(returns) > 2 else 0.8

    return {
        "rsi_14": round(rsi_14, 2),
        "atr_14": round(atr_14, 4),
        "atr_pct": round(atr_pct, 4),
        "ema_9": round(ema_9, 4),
        "ema_21": round(ema_21, 4),
        "ema_spread_pct": round(ema_spread_pct, 4),
        "realized_vol_pct": round(realized_vol_pct, 4),
    }
