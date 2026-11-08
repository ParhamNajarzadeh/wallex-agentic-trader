"""Three Categorized Mega-Tools (`src/harness/mega_tools.py`) to eliminate Context Bloat.

Instead of exposing dozens of raw REST/MCP endpoints to the System-2 LLM, all capabilities are
consolidated into 3 strongly-typed Mega-Tools:
1. `wallex_market_intelligence`
2. `wallex_trade_executor`
3. `agent_memory_and_skills`
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from src.config import ALLOWED_CREDIT_MARKETS
from src.governance.security_guard import SecurityGuard
from src.harness.memory_manager import MemoryManager
from src.harness.skill_loader import SkillLoader
from src.models.kronos_forecaster import KronosForecastService
from src.wallex.mcp_client import WallexMCPClient
from src.wallex.microstructure import (
    compute_orderbook_microstructure,
    compute_technical_indicators,
)
from src.wallex.rest_client import WallexRestClient


class MarketIntelligenceInput(BaseModel):
    action: Literal[
        "get_orderbook_microstructure",
        "get_kronos_kline_forecast",
        "get_technical_alphas",
        "get_allowed_markets_status",
    ] = Field(..., description="Market intelligence action to execute.")
    symbol: str = Field(default="USDTTMN", description="Wallex market symbol (e.g., BTCTMN, USDTTMN).")
    timeframe: str = Field(default="15m", description="K-line timeframe: 5m, 15m, or 60m.")
    limit: int = Field(default=15, description="OrderBook depth levels or trade lookback count.")


class TradeExecutorInput(BaseModel):
    action: Literal[
        "propose_order",
        "cancel_open_order",
        "check_open_orders_and_balance",
        "liquidate_all_to_toman",
    ] = Field(..., description="Order execution or account query action.")
    symbol: str = Field(default="USDTTMN", description="Target Wallex market symbol.")
    side: Literal["BUY", "SELL", "NONE"] = Field(default="NONE", description="Order direction.")
    order_type: Literal["LIMIT", "MARKET"] = Field(default="LIMIT", description="LIMIT or MARKET.")
    quantity: float = Field(default=0.0, description="Base asset order quantity.")
    price: float = Field(default=0.0, description="Limit or reference entry price.")
    stop_loss: float = Field(default=0.0, description="Dynamic stop-loss price (1.5%-2.0% below entry).")
    take_profit: float = Field(default=0.0, description="Target take-profit price (Net R/R >= 2.0).")
    idempotency_key: str = Field(default="", description="Unique clientOrderId for idempotent execution.")
    reasoning_summary: str = Field(default="", description="Detailed Persian justification for the decision.")


class MemoryAndSkillsInput(BaseModel):
    action: Literal[
        "load_skill_markdown",
        "read_working_memory",
        "update_position_plan",
        "append_learned_rule",
    ] = Field(..., description="Memory or progressive skill disclosure action.")
    skill_name: str = Field(
        default="orderbook_scalp",
        description="Name of skill to load: orderbook_scalp | risk_management | toman_settlement",
    )
    position_data: dict[str, Any] = Field(
        default_factory=dict, description="Position plan metadata to store in working memory."
    )
    lesson_text: str = Field(
        default="", description="Post-trade reflection rule to append to learned_trading_rules.md."
    )


class MegaToolsHarness:
    """Provides the 3 categorized Mega-Tools with strict security and schema validation."""

    def __init__(
        self,
        rest_client: WallexRestClient | None = None,
        mcp_client: WallexMCPClient | None = None,
        kronos_service: KronosForecastService | None = None,
        skill_loader: SkillLoader | None = None,
        memory_manager: MemoryManager | None = None,
        security_guard: SecurityGuard | None = None,
    ) -> None:
        self.rest_client = rest_client or WallexRestClient()
        self.mcp_client = mcp_client or WallexMCPClient(self.rest_client)
        self.kronos_service = kronos_service or KronosForecastService()
        self.skill_loader = skill_loader or SkillLoader()
        self.memory_manager = memory_manager or MemoryManager()
        self.security_guard = security_guard or SecurityGuard()

    async def wallex_market_intelligence(
        self,
        action: Literal[
            "get_orderbook_microstructure",
            "get_kronos_kline_forecast",
            "get_technical_alphas",
            "get_allowed_markets_status",
        ],
        symbol: str = "USDTTMN",
        timeframe: str = "15m",
        limit: int = 15,
    ) -> dict[str, Any]:
        """Mega-Tool 1: Unified read-only Wallex market intelligence, OrderBook microstructure, and Kronos forecast."""
        if action == "get_allowed_markets_status":
            markets = await self.rest_client.get_markets()
            return {"allowed_markets": markets, "count": len(markets)}

        if symbol not in ALLOWED_CREDIT_MARKETS:
            return {"error": f"Symbol {symbol} is not in ALLOWED_CREDIT_MARKETS."}

        if action == "get_orderbook_microstructure":
            ob = await self.rest_client.get_orderbook_depth(symbol, limit=limit)
            trades = await self.rest_client.get_recent_trades(symbol, limit=limit * 2)
            micro = compute_orderbook_microstructure(ob, trades)
            return {"symbol": symbol, "microstructure": micro}

        if action == "get_kronos_kline_forecast":
            res = timeframe.replace("m", "")
            df = await self.rest_client.get_udf_history(symbol, resolution=res, lookback_bars=120)
            signal = self.kronos_service.predict_single(symbol=symbol, df=df, timeframe=timeframe)
            return {"symbol": symbol, "kronos_forecast": signal}

        if action == "get_technical_alphas":
            res = timeframe.replace("m", "")
            df = await self.rest_client.get_udf_history(symbol, resolution=res, lookback_bars=120)
            tech = compute_technical_indicators(df)
            return {"symbol": symbol, "technical_indicators": tech}

        return {"error": f"Unknown action: {action}"}

    async def wallex_trade_executor(
        self,
        action: Literal[
            "propose_order",
            "cancel_open_order",
            "check_open_orders_and_balance",
            "liquidate_all_to_toman",
        ],
        symbol: str = "USDTTMN",
        side: Literal["BUY", "SELL", "NONE"] = "NONE",
        order_type: Literal["LIMIT", "MARKET"] = "LIMIT",
        quantity: float = 0.0,
        price: float = 0.0,
        stop_loss: float = 0.0,
        take_profit: float = 0.0,
        idempotency_key: str = "",
        reasoning_summary: str = "",
    ) -> dict[str, Any]:
        """Mega-Tool 2: Unified account balance, open-order inspection, order proposal, and Toman settlement."""
        if action == "check_open_orders_and_balance":
            balances = await self.mcp_client.get_balances()
            open_orders = await self.mcp_client.get_open_orders(
                symbol if symbol in ALLOWED_CREDIT_MARKETS else None
            )
            fees = await self.mcp_client.get_account_fees()
            return {"balances": balances, "open_orders": open_orders, "fees": fees}

        if action == "cancel_open_order":
            return await self.mcp_client.cancel_order(idempotency_key)

        if action == "liquidate_all_to_toman":
            settlements = await self.mcp_client.liquidate_all_to_toman(
                reason=reasoning_summary or "AGENT_REQUESTED_TOMAN_LIQUIDATION"
            )
            return {"status": "LIQUIDATED_TO_TOMAN", "settlements": settlements}

        if action == "propose_order":
            return {
                "status": "PROPOSAL_STAGED_FOR_RISK_GATE",
                "symbol": symbol,
                "side": side,
                "order_type": order_type,
                "quantity": quantity,
                "entry_price": price,
                "stop_loss": stop_loss,
                "take_profit": take_profit,
                "idempotency_key": idempotency_key,
                "reasoning_summary": reasoning_summary,
            }

        return {"error": f"Unknown action: {action}"}

    def agent_memory_and_skills(
        self,
        action: Literal[
            "load_skill_markdown",
            "read_working_memory",
            "update_position_plan",
            "append_learned_rule",
        ],
        skill_name: str = "orderbook_scalp",
        position_data: dict[str, Any] | None = None,
        lesson_text: str = "",
    ) -> dict[str, Any]:
        """Mega-Tool 3: Progressive disclosure skill reader and 3-tier file memory manager."""
        self.security_guard.assert_safe_file_access(skill_name)

        if action == "load_skill_markdown":
            return self.skill_loader.load_skill_markdown(skill_name)

        if action == "read_working_memory":
            return {
                "working_memory": self.memory_manager.read_working_memory(),
                "learned_rules_markdown": self.memory_manager.read_learned_rules(),
            }

        if action == "update_position_plan":
            pdata = position_data or {}
            updated = self.memory_manager.update_position_plan(
                symbol=str(pdata.get("symbol", "USDTTMN")),
                side=str(pdata.get("side", "BUY")),
                quantity=float(pdata.get("quantity", 0.0)),
                entry_price=float(pdata.get("entry_price", 0.0)),
                stop_loss=float(pdata.get("stop_loss", 0.0)),
                take_profit=float(pdata.get("take_profit", 0.0)),
                reasoning_fa=str(pdata.get("reasoning_fa", "")),
            )
            return {"status": "WORKING_MEMORY_UPDATED", "working_memory": updated}

        if action == "append_learned_rule":
            rule_id = (position_data or {}).get("rule_id", "RULE-AUTO")
            text = self.memory_manager.append_learned_rule(str(rule_id), lesson_text)
            return {"status": "LEARNED_RULE_APPENDED", "learned_rules_markdown": text}

        return {"error": f"Unknown action: {action}"}
