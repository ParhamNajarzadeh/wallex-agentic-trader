#!/usr/bin/env python3
"""CLI script to execute autonomous Live Trading on the dedicated Wallex Challenge Account."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

os.environ["EXECUTION_MODE"] = "LIVE"

from src.config import settings  # noqa: E402
from src.governance.security_guard import SecurityGuard  # noqa: E402
from src.graph.nodes import TradingGraphNodes  # noqa: E402
from src.graph.state import TradingState  # noqa: E402
from src.graph.workflow import build_trading_graph  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Wallex Agentic AI Live Trading Loop")
    parser.add_argument("--cycles", type=int, default=1, help="Number of trading cycles to run")
    parser.add_argument("--interval-sec", type=int, default=60, help="Seconds between cycles")
    args = parser.parse_args()

    guard = SecurityGuard()
    ttl_status = guard.check_key_ttl_valid()
    if not ttl_status["ttl_valid"]:
        print(f"[SECURITY BLOCK] Agent key expired at {ttl_status['expires_at']}. Aborting live loop.")
        sys.exit(1)

    nodes = TradingGraphNodes()
    graph = build_trading_graph(nodes)

    for c in range(args.cycles):
        ttl_now = guard.check_key_ttl_valid()
        state: TradingState = {
            "cycle_id": f"live-cycle-{int(time.time())}-{c + 1:03d}",
            "timestamp_iso": settings.now_iso(),
            "execution_mode": "LIVE",
            "hours_remaining_in_challenge": float(ttl_now["remaining_hours"]),
            "market_snapshot": {},
            "kronos_forecasts": {},
            "sentiment_guard_report": {},
            "portfolio_status": {},
            "market_regime": "BULL_TREND",
            "system1_routing_metadata": {},
            "active_skills_loaded": [],
            "proposed_signal": None,
            "risk_validation": None,
            "macro_hitl_required": False,
            "macro_hitl_reason": None,
            "execution_result": None,
            "messages": [],
        }
        result = graph.invoke(state, config={"configurable": {"thread_id": "wallex-live-challenge"}})
        print(
            json.dumps(
                {
                    "cycle_id": result["cycle_id"],
                    "regime": result["market_regime"],
                    "proposed_action": (result.get("proposed_signal") or {}).get("action"),
                    "symbol": (result.get("proposed_signal") or {}).get("symbol"),
                    "execution_status": (result.get("execution_result") or {}).get("status"),
                    "portfolio_equity_tmn": result["portfolio_status"].get("total_equity_tmn"),
                },
                indent=2,
                ensure_ascii=False,
            )
        )
        if c + 1 < args.cycles:
            time.sleep(args.interval_sec)


if __name__ == "__main__":
    main()
