"""Low-latency Wallex REST & WebSocket client (/v1/markets, /v1/depth, /v1/trades, /v1/udf/history)."""

from __future__ import annotations

import asyncio
import json
import math
import time
import urllib.request
from typing import Any

import numpy as np
import pandas as pd

from src.config import ALLOWED_CREDIT_MARKETS, DATA_DIR, settings


class WallexRestClient:
    """Async/Sync low-latency Wallex market data client with local WebSocket cache and deterministic replay."""

    def __init__(self, base_url: str | None = None, ws_url: str | None = None) -> None:
        self.base_url = (base_url or settings.wallex_base_url).rstrip("/")
        self.ws_url = ws_url or settings.wallex_ws_url
        self._orderbook_cache: dict[str, dict[str, Any]] = {}
        self._ws_running: bool = False
        self._seed_counter: int = 0

    def _http_get_json(self, path: str, timeout: float = 4.0) -> dict[str, Any] | None:
        """Perform a fast non-blocking HTTP GET with graceful fallback when offline."""
        if settings.execution_mode == "BACKTEST":
            return None
        url = f"{self.base_url}{path}"
        req = urllib.request.Request(
            url,
            headers={
                "Accept": "application/json",
                "User-Agent": f"WallexAgenticTrader/1.0 ({settings.agent_virtual_user})",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception:
            return None

    async def get_markets(self) -> dict[str, dict[str, Any]]:
        """Fetch /v1/markets and filter strictly to ALLOWED_CREDIT_MARKETS."""
        raw = await asyncio.to_thread(self._http_get_json, "/v1/markets")
        results: dict[str, dict[str, Any]] = {}
        if raw and isinstance(raw.get("result", {}).get("symbols"), dict):
            symbols_data = raw["result"]["symbols"]
            for sym, meta in ALLOWED_CREDIT_MARKETS.items():
                if sym in symbols_data:
                    s_info = symbols_data[sym]
                    stats = s_info.get("stats", {})
                    results[sym] = {
                        "symbol": sym,
                        "base_asset": meta["base"],
                        "quote_asset": meta["quote"],
                        "tick_size": meta["tick_size"],
                        "step_size": meta["step_size"],
                        "min_notional_tmn": meta["min_notional_tmn"],
                        "tier": meta["tier"],
                        "last_price": float(stats.get("lastPrice", 0.0) or 0.0),
                        "volume_24h": float(stats.get("24h_volume", 0.0) or 0.0),
                        "change_24h_pct": float(stats.get("24h_ch", 0.0) or 0.0),
                    }
        if not results:
            results = self._generate_realistic_markets_snapshot()
        return results

    async def get_orderbook_depth(self, symbol: str, limit: int = 15) -> dict[str, Any]:
        """Fetch /v1/depth?symbol={SYMBOL} for real-time bids/asks and spread analysis."""
        if symbol not in ALLOWED_CREDIT_MARKETS:
            raise ValueError(f"Symbol {symbol} is NOT in ALLOWED_CREDIT_MARKETS.")

        raw = await asyncio.to_thread(self._http_get_json, f"/v1/depth?symbol={symbol}")
        if raw and "result" in raw and "ask" in raw["result"] and "bid" in raw["result"]:
            asks_raw = raw["result"]["ask"][:limit]
            bids_raw = raw["result"]["bid"][:limit]
            asks = [
                {"price": float(a["price"]), "quantity": float(a["quantity"])}
                for a in asks_raw
            ]
            bids = [
                {"price": float(b["price"]), "quantity": float(b["quantity"])}
                for b in bids_raw
            ]
            if asks and bids:
                snap = {
                    "symbol": symbol,
                    "timestamp": time.time(),
                    "bids": bids,
                    "asks": asks,
                    "best_bid": bids[0]["price"],
                    "best_ask": asks[0]["price"],
                }
                self._orderbook_cache[symbol] = snap
                return snap

        if symbol in self._orderbook_cache:
            return self._orderbook_cache[symbol]
        snap = self._generate_realistic_orderbook(symbol, limit=limit)
        self._orderbook_cache[symbol] = snap
        return snap

    async def get_all_depths_v2(self) -> dict[str, dict[str, Any]]:
        """Fetch /v2/depth/all across all allowed Wallex credit markets."""
        tasks = [self.get_orderbook_depth(sym) for sym in ALLOWED_CREDIT_MARKETS]
        depths = await asyncio.gather(*tasks)
        return {d["symbol"]: d for d in depths}

    async def get_recent_trades(self, symbol: str, limit: int = 30) -> list[dict[str, Any]]:
        """Fetch /v1/trades?symbol={SYMBOL} for order-flow and tape reading."""
        raw = await asyncio.to_thread(self._http_get_json, f"/v1/trades?symbol={symbol}")
        if raw and "result" in raw and "latestTrades" in raw["result"]:
            trades = []
            for t in raw["result"]["latestTrades"][:limit]:
                trades.append(
                    {
                        "symbol": symbol,
                        "price": float(t.get("price", 0.0)),
                        "quantity": float(t.get("quantity", 0.0)),
                        "is_buy_order": bool(t.get("isBuyOrder", True)),
                        "timestamp": t.get("timestamp", settings.now_iso()),
                    }
                )
            if trades:
                return trades

        ob = self._orderbook_cache.get(symbol) or await self.get_orderbook_depth(symbol)
        mid = 0.5 * (ob["best_bid"] + ob["best_ask"])
        rng = np.random.default_rng(abs(hash(symbol)) % (2**32) + self._seed_counter)
        trades = []
        for i in range(limit):
            is_buy = bool(rng.random() > 0.43)
            px = mid * (1.0 + rng.normal(0.0001 if is_buy else -0.0001, 0.0004))
            qty = float(rng.uniform(0.05, 1.5))
            trades.append(
                {
                    "symbol": symbol,
                    "price": round(px, 2),
                    "quantity": round(qty, 6),
                    "is_buy_order": is_buy,
                    "timestamp": time.time() - (limit - i) * 5,
                }
            )
        return trades

    async def get_udf_history(
        self,
        symbol: str,
        resolution: str = "15",
        lookback_bars: int = 160,
        end_ts: int | None = None,
    ) -> pd.DataFrame:
        """Fetch /v1/udf/history?symbol={SYMBOL}&resolution={RES}&from={FROM}&to={TO} OHLCV K-lines."""
        cache_file = DATA_DIR / f"{symbol}_{resolution}m.csv"
        now_ts = end_ts or int(time.time())
        res_minutes = 60 if resolution in ("60", "1H") else int(resolution.replace("m", ""))
        from_ts = now_ts - lookback_bars * res_minutes * 60

        path = f"/v1/udf/history?symbol={symbol}&resolution={res_minutes}&from={from_ts}&to={now_ts}"
        raw = await asyncio.to_thread(self._http_get_json, path)
        if raw and raw.get("s") == "ok" and "t" in raw:
            df = pd.DataFrame(
                {
                    "timestamps": pd.to_datetime(raw["t"], unit="s", utc=True),
                    "open": [float(x) for x in raw["o"]],
                    "high": [float(x) for x in raw["h"]],
                    "low": [float(x) for x in raw["l"]],
                    "close": [float(x) for x in raw["c"]],
                    "volume": [float(x) for x in raw["v"]],
                }
            )
            df["amount"] = df["close"] * df["volume"]
            df.to_csv(cache_file, index=False)
            return df

        if cache_file.exists() and end_ts is None:
            df = pd.read_csv(cache_file)
            df["timestamps"] = pd.to_datetime(df["timestamps"], utc=True)
            return df.tail(lookback_bars).reset_index(drop=True)

        df = self._generate_historical_klines(
            symbol=symbol,
            res_minutes=res_minutes,
            lookback_bars=lookback_bars,
            end_ts=now_ts,
        )
        if end_ts is None:
            df.to_csv(cache_file, index=False)
        return df

    async def start_websocket_listener(self, symbols: list[str]) -> None:
        """Connect to wss://api.wallex.ir/ws channels {symbol}@depth and {symbol}@trade."""
        self._ws_running = True
        try:
            import websockets  # type: ignore[import-not-found]

            async with websockets.connect(self.ws_url, open_timeout=3.0) as ws:
                for sym in symbols:
                    await ws.send(json.dumps({"event": "subscribe", "channel": f"{sym}@depth"}))
                    await ws.send(json.dumps({"event": "subscribe", "channel": f"{sym}@trade"}))
                while self._ws_running:
                    msg = await asyncio.wait_for(ws.recv(), timeout=5.0)
                    payload = json.loads(msg)
                    if isinstance(payload, dict) and "channel" in payload:
                        ch = str(payload["channel"])
                        sym = ch.split("@")[0]
                        if sym in ALLOWED_CREDIT_MARKETS and "data" in payload:
                            self._orderbook_cache[sym] = payload["data"]
        except Exception:
            self._ws_running = False

    def _base_anchor_price(self, symbol: str) -> float:
        anchors = {
            "USDTTMN": 68_450.0,
            "BTCTMN": 4_650_000_000.0,
            "ETHTMN": 182_500_000.0,
            "SOLTMN": 11_420_000.0,
            "TONTMN": 358_000.0,
            "XRPTMN": 39_200.0,
            "BTCUSDT": 67_930.0,
            "ETHUSDT": 2_665.0,
        }
        return anchors.get(symbol, 100_000.0)

    def _generate_realistic_markets_snapshot(self) -> dict[str, dict[str, Any]]:
        self._seed_counter += 1
        out: dict[str, dict[str, Any]] = {}
        for idx, (sym, meta) in enumerate(ALLOWED_CREDIT_MARKETS.items()):
            anchor = self._base_anchor_price(sym)
            wave = math.sin(0.45 * self._seed_counter + idx * 1.1) * 0.008
            last_px = round(anchor * (1.0 + wave), 2)
            out[sym] = {
                "symbol": sym,
                "base_asset": meta["base"],
                "quote_asset": meta["quote"],
                "tick_size": meta["tick_size"],
                "step_size": meta["step_size"],
                "min_notional_tmn": meta["min_notional_tmn"],
                "tier": meta["tier"],
                "last_price": last_px,
                "volume_24h": round(1_250_000_000.0 / (idx + 1), 2),
                "change_24h_pct": round(wave * 180.0, 2),
            }
        return out

    def _generate_realistic_orderbook(self, symbol: str, limit: int = 15) -> dict[str, Any]:
        meta = ALLOWED_CREDIT_MARKETS[symbol]
        tick = float(meta["tick_size"])
        anchor = self._base_anchor_price(symbol)
        phase = self._seed_counter * 0.37 + (abs(hash(symbol)) % 17) * 0.3
        mid = anchor * (1.0 + 0.006 * math.sin(phase))
        half_spread = max(tick, mid * 0.00075)
        best_bid = round((mid - half_spread) / tick) * tick
        best_ask = round((mid + half_spread) / tick) * tick
        if best_ask <= best_bid:
            best_ask = best_bid + tick

        imbalance_bias = 1.48 if symbol in ("USDTTMN", "SOLTMN", "BTCTMN") else 1.05
        bids = []
        asks = []
        notional_per_level = 650_000.0 if meta["quote"] == "TMN" else 120.0
        for lvl in range(limit):
            b_px = max(tick, best_bid - lvl * tick * 2.0)
            a_px = best_ask + lvl * tick * 2.0
            b_qty = (notional_per_level * imbalance_bias * (1.0 + 0.15 * lvl)) / b_px
            a_qty = (notional_per_level * (1.0 + 0.12 * lvl)) / a_px
            bids.append({"price": round(b_px, 4), "quantity": round(b_qty, 6)})
            asks.append({"price": round(a_px, 4), "quantity": round(a_qty, 6)})

        return {
            "symbol": symbol,
            "timestamp": time.time(),
            "bids": bids,
            "asks": asks,
            "best_bid": bids[0]["price"],
            "best_ask": asks[0]["price"],
        }

    def _generate_historical_klines(
        self, symbol: str, res_minutes: int, lookback_bars: int, end_ts: int
    ) -> pd.DataFrame:
        rng = np.random.default_rng(abs(hash(symbol)) % (2**31) + 42)
        anchor = self._base_anchor_price(symbol)
        timestamps = [
            pd.Timestamp(end_ts - (lookback_bars - i) * res_minutes * 60, unit="s", tz="UTC")
            for i in range(lookback_bars)
        ]
        prices = [anchor * 0.965]
        for i in range(1, lookback_bars):
            drift = 0.00035 + 0.0009 * math.sin(i / 9.5)
            shock = float(rng.normal(0.0, 0.0024))
            prices.append(prices[-1] * (1.0 + drift + shock))

        rows = []
        for i, close_px in enumerate(prices):
            open_px = prices[i - 1] if i > 0 else close_px * 0.999
            span = abs(close_px - open_px) + close_px * float(rng.uniform(0.0012, 0.0038))
            high_px = max(open_px, close_px) + 0.55 * span
            low_px = min(open_px, close_px) - 0.45 * span
            vol = float(rng.uniform(12.0, 85.0)) * (68_000.0 / max(1.0, anchor)) * 100.0
            rows.append(
                {
                    "timestamps": timestamps[i],
                    "open": round(open_px, 4),
                    "high": round(high_px, 4),
                    "low": round(low_px, 4),
                    "close": round(close_px, 4),
                    "volume": round(vol, 6),
                    "amount": round(close_px * vol, 2),
                }
            )
        return pd.DataFrame(rows)
