#!/usr/bin/env python3
"""Safe Agent Retirement & End-of-Challenge Toman Settlement Script (`scripts/retire_agent.py`).

Implements the AI Governance retirement protocol:
1. Cancels all open orders on the Wallex challenge account (`DELETE /v1/account/orders`).
2. Liquidates 100% of remaining non-Toman balances into realized Toman (`TMN`).
3. Generates the final realized PnL audit report (`evaluation_results/final_retirement_report.json`).
4. Permanently locks the agent loop in `memory/active_positions_plan.json`.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from src.config import EVAL_DIR, settings  # noqa: E402
from src.harness.memory_manager import MemoryManager  # noqa: E402
from src.wallex.mcp_client import WallexMCPClient  # noqa: E402
from src.wallex.rest_client import WallexRestClient  # noqa: E402


async def retire_agent_workflow() -> dict:
    rest = WallexRestClient()
    mcp = WallexMCPClient(rest)
    mem = MemoryManager()

    cancelled = await mcp.cancel_all_open_orders()
    settlements = await mcp.liquidate_all_to_toman(reason="OFFICIAL_HACKATHON_RETIREMENT")
    final_balances = await mcp.get_balances()

    final_tmn = round(float(final_balances.get("TMN", {}).get("free", settings.initial_capital_tmn)), 2)
    net_profit_tmn = round(final_tmn - settings.initial_capital_tmn, 2)
    return_pct = round((net_profit_tmn / settings.initial_capital_tmn) * 100.0, 4)

    w_mem = mem.read_working_memory()
    w_mem["agent_retired"] = True
    w_mem["retired_at"] = settings.now_iso()
    w_mem["open_positions"] = {}
    mem.write_working_memory(w_mem)

    retirement_report = {
        "agent_identity": settings.agent_virtual_user,
        "status": "RETIRED_AND_SETTLED_IN_TOMAN",
        "initial_capital_tmn": settings.initial_capital_tmn,
        "final_realized_tmn": final_tmn,
        "realized_net_profit_tmn": net_profit_tmn,
        "official_return_pct": return_pct,
        "open_orders_cancelled": len(cancelled),
        "liquidation_orders_executed": settlements,
        "retired_at": settings.now_iso(),
    }
    report_file = EVAL_DIR / "final_retirement_report.json"
    report_file.write_text(json.dumps(retirement_report, indent=2, ensure_ascii=False), encoding="utf-8")
    return retirement_report


def main() -> None:
    print("=" * 78)
    print("WALLEX AGENTIC AI TRADER — SAFE RETIREMENT & 100% TOMAN LIQUIDATION")
    print("=" * 78)
    report = asyncio.run(retire_agent_workflow())
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
