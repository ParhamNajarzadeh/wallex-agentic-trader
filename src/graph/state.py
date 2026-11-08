"""State schema (`TradingState`, `KronosSignal`, `TradeProposal`, `RiskValidationResult`) for LangGraph."""

from __future__ import annotations

from typing import Annotated, Any, Literal, TypedDict

try:
    from langgraph.graph.message import add_messages  # type: ignore[import-not-found]
except Exception:
    def add_messages(left: list[Any], right: list[Any]) -> list[Any]:
        return (left or []) + (right or [])


class KronosSignal(TypedDict):
    symbol: str
    timeframe: str
    current_price: float
    predicted_close_mean: float
    expected_return_pct: float
    upside_probability: float
    predicted_low_min: float
    predicted_volatility_pct: float


class TradeProposal(TypedDict):
    action: Literal["BUY", "SELL", "HOLD", "CANCEL", "LIQUIDATE_ALL_TO_TOMAN"]
    symbol: str
    side: Literal["BUY", "SELL", "NONE"]
    order_type: Literal["LIMIT", "MARKET"]
    quantity: float
    entry_price: float
    stop_loss: float
    take_profit: float
    expected_net_rr: float
    confidence: float
    idempotency_key: str
    observed_signals: dict[str, Any]
    reasoning_log_fa: str
    reasoning_log_en: str


class RiskValidationResult(TypedDict):
    approved: bool
    adjusted_quantity: float
    adjusted_price: float
    rejection_reasons: list[str]
    risk_metrics: dict[str, float]


class TradingState(TypedDict):
    cycle_id: str
    timestamp_iso: str
    execution_mode: Literal["BACKTEST", "SHADOW", "LIVE"]
    hours_remaining_in_challenge: float
    market_snapshot: dict[str, dict[str, Any]]
    kronos_forecasts: dict[str, KronosSignal]
    sentiment_guard_report: dict[str, Any]
    portfolio_status: dict[str, Any]
    market_regime: Literal[
        "BULL_TREND", "RANGE_SCALP", "HIGH_VOL_PUMP_DUMP", "NIGHT_THIN_LIQUIDITY"
    ]
    system1_routing_metadata: dict[str, Any]
    active_skills_loaded: list[str]
    proposed_signal: TradeProposal | None
    risk_validation: RiskValidationResult | None
    macro_hitl_required: bool
    macro_hitl_reason: str | None
    execution_result: dict[str, Any] | None
    messages: Annotated[list[Any], add_messages]
