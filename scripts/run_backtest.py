#!/usr/bin/env python3
"""CLI script to execute reproducible historical Backtest for Wallex Hackathon judges."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

os.environ["EXECUTION_MODE"] = "BACKTEST"

from src.testing.backtester import WallexBacktester  # noqa: E402


def main() -> None:
    print("=" * 78)
    print("WALLEX AGENTIC AI TRADER — REPRODUCIBLE HISTORICAL BACKTEST (5,000,000 TMN)")
    print("=" * 78)
    backtester = WallexBacktester()
    report = backtester.run_backtest(num_cycles=18)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    print("-" * 78)
    print("Backtest report saved to: evaluation_results/backtest_report.json")
    print("Audit decision logs appended to: logs/decision_logs.jsonl")


if __name__ == "__main__":
    main()
