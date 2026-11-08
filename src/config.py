"""Central configuration, allowed Wallex credit markets, and risk parameters."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

BASE_DIR = Path(__file__).resolve().parent.parent
SKILLS_DIR = BASE_DIR / "skills"
MEMORY_DIR = BASE_DIR / "memory"
LOGS_DIR = BASE_DIR / "logs"
EVAL_DIR = BASE_DIR / "evaluation_results"
DATA_DIR = BASE_DIR / "data" / "historical_candles"

for _d in (SKILLS_DIR, MEMORY_DIR, LOGS_DIR, EVAL_DIR, DATA_DIR):
    _d.mkdir(parents=True, exist_ok=True)


# Official Wallex Credit Trading Whitelist (Spot Only — Toman & USDT pairs)
ALLOWED_CREDIT_MARKETS: dict[str, dict[str, float | int | str]] = {
    "USDTTMN": {
        "base": "USDT",
        "quote": "TMN",
        "tick_size": 10.0,
        "step_size": 0.01,
        "min_notional_tmn": 150_000.0,
        "tier": "CORE_LIQUID",
    },
    "BTCTMN": {
        "base": "BTC",
        "quote": "TMN",
        "tick_size": 1000.0,
        "step_size": 0.00001,
        "min_notional_tmn": 150_000.0,
        "tier": "CORE_LIQUID",
    },
    "ETHTMN": {
        "base": "ETH",
        "quote": "TMN",
        "tick_size": 500.0,
        "step_size": 0.0001,
        "min_notional_tmn": 150_000.0,
        "tier": "CORE_LIQUID",
    },
    "SOLTMN": {
        "base": "SOL",
        "quote": "TMN",
        "tick_size": 100.0,
        "step_size": 0.001,
        "min_notional_tmn": 150_000.0,
        "tier": "HIGH_BETA",
    },
    "TONTMN": {
        "base": "TON",
        "quote": "TMN",
        "tick_size": 10.0,
        "step_size": 0.01,
        "min_notional_tmn": 150_000.0,
        "tier": "HIGH_BETA",
    },
    "XRPTMN": {
        "base": "XRP",
        "quote": "TMN",
        "tick_size": 10.0,
        "step_size": 0.1,
        "min_notional_tmn": 150_000.0,
        "tier": "HIGH_BETA",
    },
    "BTCUSDT": {
        "base": "BTC",
        "quote": "USDT",
        "tick_size": 0.01,
        "step_size": 0.00001,
        "min_notional_tmn": 150_000.0,
        "tier": "TWO_LEG_USDT",
    },
    "ETHUSDT": {
        "base": "ETH",
        "quote": "USDT",
        "tick_size": 0.01,
        "step_size": 0.0001,
        "min_notional_tmn": 150_000.0,
        "tier": "TWO_LEG_USDT",
    },
}


@dataclass(frozen=True)
class EngineConfig:
    """Immutable runtime and risk configuration for the Wallex Agentic Engine."""

    execution_mode: Literal["BACKTEST", "SHADOW", "LIVE"] = field(
        default_factory=lambda: os.getenv("EXECUTION_MODE", "SHADOW").upper()  # type: ignore[return-value]
    )
    initial_capital_tmn: float = field(
        default_factory=lambda: float(os.getenv("CHALLENGE_INITIAL_CAPITAL_TMN", "5000000"))
    )
    challenge_duration_hours: float = field(
        default_factory=lambda: float(os.getenv("CHALLENGE_DURATION_HOURS", "72.0"))
    )
    agent_virtual_user: str = field(
        default_factory=lambda: os.getenv("AGENT_VIRTUAL_USER", "hackathon-wallex-agent")
    )
    agent_key_expires_at: str = field(
        default_factory=lambda: os.getenv(
            "AGENT_KEY_EXPIRES_AT", "2026-10-25T12:00:00+03:30"
        )
    )

    # Wallex Endpoints & Fees
    wallex_base_url: str = field(
        default_factory=lambda: os.getenv("WALLEX_BASE_URL", "https://api.wallex.ir")
    )
    wallex_ws_url: str = field(
        default_factory=lambda: os.getenv("WALLEX_WS_URL", "wss://api.wallex.ir/ws")
    )
    wallex_mcp_url: str = field(
        default_factory=lambda: os.getenv("WALLEX_MCP_SERVER_URL", "http://localhost:8090/mcp")
    )
    maker_fee: float = field(
        default_factory=lambda: float(os.getenv("WALLEX_MAKER_FEE", "0.0020"))
    )
    taker_fee: float = field(
        default_factory=lambda: float(os.getenv("WALLEX_TAKER_FEE", "0.0025"))
    )
    max_price_drift_pct: float = field(
        default_factory=lambda: float(os.getenv("MAX_PRICE_DRIFT_PCT", "0.40"))
    )

    # Kronos Foundation Model Settings
    kronos_model_id: str = field(
        default_factory=lambda: os.getenv("KRONOS_MODEL_ID", "NeoQuasar/Kronos-small")
    )
    kronos_tokenizer_id: str = field(
        default_factory=lambda: os.getenv(
            "KRONOS_TOKENIZER_ID", "NeoQuasar/Kronos-Tokenizer-base"
        )
    )
    kronos_device: str = field(
        default_factory=lambda: os.getenv("KRONOS_DEVICE", "cpu")
    )
    kronos_pred_len: int = field(
        default_factory=lambda: int(os.getenv("KRONOS_PRED_LEN", "12"))
    )
    kronos_sample_count: int = field(
        default_factory=lambda: int(os.getenv("KRONOS_SAMPLE_COUNT", "5"))
    )
    kronos_temperature: float = field(
        default_factory=lambda: float(os.getenv("KRONOS_TEMPERATURE", "1.0"))
    )
    kronos_top_p: float = field(
        default_factory=lambda: float(os.getenv("KRONOS_TOP_P", "0.90"))
    )

    # Unified System-1 Decision Engine
    system1_provider: str = field(
        default_factory=lambda: os.getenv("SYSTEM1_PROVIDER", "jev").lower()
    )
    jev_metis_url: str = field(
        default_factory=lambda: os.getenv(
            "JEV_METIS_URL",
            "https://api.metisai.ir/api/v1/wrapper/typesafe/v1/systemone",
        )
    )
    mizan_local_url: str = field(
        default_factory=lambda: os.getenv(
            "MIZAN_LOCAL_URL", "http://localhost:8007/v1/systemone"
        )
    )
    laya_local_url: str = field(
        default_factory=lambda: os.getenv(
            "LAYA_LOCAL_URL", "http://localhost:8008/v1/systemone"
        )
    )
    kev_local_url: str = field(
        default_factory=lambda: os.getenv(
            "KEV_LOCAL_URL", "http://localhost:8009/v1/systemone"
        )
    )

    # System-2 LLM Settings
    llm_base_url: str = field(
        default_factory=lambda: os.getenv(
            "LLM_BASE_URL", "https://api.metisai.ir/openai/v1"
        )
    )
    llm_model_name: str = field(
        default_factory=lambda: os.getenv("LLM_MODEL_NAME", "deepseek-v4.1-flash")
    )
    max_context_tokens: int = field(
        default_factory=lambda: int(os.getenv("MAX_CONTEXT_TOKENS", "12000"))
    )

    # Hard Risk Gate Guardrails (5,000,000 TMN Capital)
    max_single_order_pct: float = field(
        default_factory=lambda: float(os.getenv("MAX_SINGLE_ORDER_PCT", "0.18"))
    )
    max_single_order_tmn_cap: float = 900_000.0  # 18% of 5,000,000 TMN
    min_cash_reserve_pct: float = field(
        default_factory=lambda: float(os.getenv("MIN_CASH_RESERVE_PCT", "0.40"))
    )
    stop_loss_min_pct: float = field(
        default_factory=lambda: float(os.getenv("STOP_LOSS_MIN_PCT", "0.015"))
    )
    stop_loss_max_pct: float = field(
        default_factory=lambda: float(os.getenv("STOP_LOSS_MAX_PCT", "0.020"))
    )
    min_expected_net_rr: float = field(
        default_factory=lambda: float(os.getenv("MIN_EXPECTED_NET_RR", "2.0"))
    )
    max_daily_drawdown_pct: float = field(
        default_factory=lambda: float(os.getenv("MAX_DAILY_DRAWDOWN_PCT", "0.030"))
    )
    night_spread_threshold_pct: float = 0.35
    end_of_cycle_liquidation_hours: float = field(
        default_factory=lambda: float(os.getenv("END_OF_CYCLE_LIQUIDATION_HOURS", "4.0"))
    )

    def get_wallex_api_key(self) -> str:
        """Retrieve Wallex API key strictly inside Python runtime (never exposed to LLM)."""
        return os.getenv("WALLEX_API_KEY", "")

    def get_metis_api_key(self) -> str:
        """Retrieve MetisAI API key strictly inside Python runtime."""
        return os.getenv("METIS_API_KEY", "")

    def get_llm_api_key(self) -> str:
        """Retrieve System-2 LLM API key strictly inside Python runtime."""
        return os.getenv("LLM_API_KEY", "")

    @staticmethod
    def now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()


settings = EngineConfig()
