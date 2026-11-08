# Wallex Autonomous Multi-Agent Trading Engine (`wallex-agentic-trader`)

### A Hybrid Graph-Harness Architecture Powered by the **Kronos** Time-Series Foundation Model, Ultra-Fast **System-1 Decision Engine (`Jev` / `Mizan-4B` / `Laya` / `Kev`)**, and **System-2 Quant Analyst** for the Wallex Exchange Challenge in the StarCoach Agentic AI Hackathon

---

## Table of Contents
1. [Pillar 1: Architecture & Core Algorithm Logic](#1-pillar-1-architecture--core-algorithm-logic)
2. [Pillar 2: Real AI Usage & Dual Wallex Tools (REST/WS API + Wallex MCP)](#2-pillar-2-real-ai-usage--dual-wallex-tools)
3. [Pillar 3: Quantitative & Agentic Execution Signals (Buy, Sell & Toman Settlement)](#3-pillar-3-quantitative--agentic-execution-signals)
4. [Pillar 4: Capital Allocation, Deterministic Risk Gate & AI Governance](#4-pillar-4-capital-allocation-deterministic-risk-gate--ai-governance)
5. [Pillar 5: Reproducibility, Backtesting, Shadow Testing & `decision_logs.jsonl` Audit](#5-pillar-5-reproducibility-backtesting-shadow-testing--audit)
6. [Generative UI Dashboard (Chat Plus)](#6-generative-ui-dashboard-chat-plus)

---

## 1. Pillar 1: Architecture & Core Algorithm Logic

This system is a **100% autonomous, reproducible, and auditable Spot algorithmic trading engine**, custom-tailored to manage an initial capital of **`5,000,000` Tomans (Wallex Credit Line)** across the 72-hour hackathon trading window.

### Architectural Rationale: Why Combine `StateGraph` (LangGraph) and `ReAct Harness`?
Relying on an unconstrained `ReAct` loop in live financial execution creates severe vulnerabilities: tool-calling hallucinations, infinite retry loops during network degradation, and risk rule breaches. Conversely, rigid procedural `if/else` scripts fail to perceive dynamic market regime shifts and forfeit points under the **"Authentic Use of Agentic AI"** evaluation criteria.

In this **Hybrid Graph-Harness** architecture:
- **Macro-Orchestration:** Managed by an 8-station **LangGraph (`StateGraph`)** equipped with `MemorySaver` checkpoints and an explicit `interrupt()` mechanism for governance.
- **System-1 / System-2 Cognitive Decoupling:** Eliminates latency overhead and prevents token burn during non-actionable market regimes:
  - **Quantitative Time-Series Forecasting (`KronosForecastAgent`)**: Built on the open-source candlestick foundation model **[shiyu-coder/Kronos](https://github.com/shiyu-coder/Kronos)** (`NeoQuasar/Kronos-small` + `NeoQuasar/Kronos-Tokenizer-base`). It projects the probability distribution over the next 12 candles (`OHLCV`), expected return (`expected_return_pct`), fee-adjusted net win probability (`upside_probability`), and the minimum expected downside price (`predicted_low_min`).
  - **Ultra-Fast System-1 Decision Engine (`System1RegimeRouterNode`)**: A unified client based on the `/v1/systemone` protocol supporting 4 backends: **[Jev (MetisAI TypeSafe)](https://docs.metisai.ir/api/wrapper/typesafe)**, **[Mizan-4B](https://huggingface.co/xmanii/Mizan-4B)**, **[Laya](https://github.com/NandhaKishorM/laya)** (33ms non-autoregressive LangGraph router), and **[Kev](https://github.com/jaredpalmer/kev)**. In a single forward pass (< 50ms), it outputs calibrated regime probabilities (`BULL_TREND`, `RANGE_SCALP`, `HIGH_VOL_PUMP_DUMP`, `NIGHT_THIN_LIQUIDITY`), gating flags, and the relevant active skill (`SKILL.md`).
  - **System-2 Quant Analyst Brain (`System2QuantAnalystAgent`)**: Powered by **DeepSeek V4.1 Flash** within an engineered **ReAct Harness**. It accesses only **3 Mega-Tools**, dynamically disclosed skills (`skills/*/SKILL.md`), and structured memory, generating validated `TradeProposal` objects accompanied by transparent analytical reasoning.

```text
[EXECUTION_MODE: BACKTEST | SHADOW | LIVE]
        │
        ▼
[1. MarketScannerNode (Async Python + Wallex REST/WS API: https://api.wallex.ir)]
   - Fetches /v1/markets, /v1/depth, /v1/trades, and /v1/udf/history candles
   - Calculates Microstructure Alpha/Beta/Gamma, OrderBook Imbalance (OBI), Spread, RSI, ATR
   - Filters top 2-3 eligible credit-trading pairs exhibiting volume/price anomalies
        │
        ├───────────────────────────────────────────┐
        ▼                                           ▼
[2A. KronosForecastNode (Quantitative)]     [2B. SentimentGuardNode (Isolated Subagent)]
   - Model: shiyu-coder/Kronos                 - Isolated news/feed monitoring without .env access
     (NeoQuasar/Kronos-small + Tokenizer)      - Neutralizes prompt injection & scores with Mizan-4B
   - Multi-step OHLCV candlestick projection,  - Zero access to trading tools (Breaks Simon Willison's
     E[Return], Upside Prob, Predicted Low       Lethal Trifecta)
        │                                           │
        └─────────────────────┬─────────────────────┘
                               ▼
[3. System1RegimeRouterNode (Unified /v1/systemone Decision Engine)]
   - Cloud: Jev (MetisAI TypeSafe) | Local: Mizan-4B, Laya (33ms), Kev
   - Outputs calibrated probabilities:
     * market_regime: BULL_TREND | RANGE_SCALP | HIGH_VOL_PUMP_DUMP | NIGHT_THIN_LIQUIDITY
     * action_gate: PROCEED_TO_SYSTEM2 | FAST_HOLD | EMERGENCY_LIQUIDATE
     * active_skill: orderbook_scalp | risk_management | toman_settlement
                               │
                               ▼
[4. System2QuantAnalystNode (ReAct Harness + DeepSeek V4.1 Flash / LLM)]
   - 3 Curated Mega-Tools + Progressive Disclosure (SKILL.md)
   - Blends Kronos Forecast + OrderBook Asymmetry + Working Memory (active_positions_plan.json)
   - Emits structured TradeProposal + transparent reasoning log
                               │
                               ▼
[5. DeterministicRiskGateNode (100% Pure Python Guardrail + Kev/Laya Policy Check)]
   - Validates 8 hard-line safety rules: Whitelisted markets, 18% max per order (<=900,000 TMN),
     40% minimum cash reserve (>=2,000,000 TMN), Dynamic Stop-Loss (1.5%-2%), Net R/R >= 2.0,
     Self-Trade Prevention (STP), Night liquidity adaptation, 3% Daily Max Drawdown Circuit Breaker,
     and Mandatory 100% Toman Liquidation Gate in the final 4 hours
                               │
                               ▼
[6. MacroHITLInterruptNode (LangGraph interrupt() + MemorySaver Checkpointer)]
   - 100% Autonomous passthrough for micro-trades (Honors zero manual intervention rule)
   - Suspends execution strictly for macro governance events: Shadow-to-Live elevation,
     skill hot-swapping, or circuit breaker manual override
                               │
                               ▼
[7. ExecutionAndLoggerNode (Wallex MCP + REST Fallback + Stale Price Refresh)]
   - Real-time refresh of order book best_bid / best_ask to eliminate Stale Price execution (0.4% threshold)
   - Order placement via Wallex MCP (LIVE mode) or MockOrderBookMatcher (SHADOW/BACKTEST mode)
   - Appends immutable execution traces to logs/decision_logs.jsonl
                               │
                               ▼
[8. EvaluatorAndCompactionNode (Evaluator-Optimizer Reflection + OpenCode Compaction)]
   - Post-mortem analysis on closed cycles with lessons recorded to memory/learned_trading_rules.md
   - Autonomous conversation history compaction upon crossing 12,000 tokens
```

---

## 2. Pillar 2: Real AI Usage & Dual Wallex Tools

### 2.1. Dual-Layer Integration with Wallex Exchange (`REST/WS API` + `Wallex MCP`)
In compliance with official technical documentation ([developers.wallex.ir](https://developers.wallex.ir/docs)):
1. **Layer 1 — Low-Latency Market Data Feed (`src/wallex/rest_client.py`):**
   - High-throughput asynchronous queries via `httpx.AsyncClient` to `GET /v1/markets` (market precision, `tick_size`, and `step_size`), `GET /v1/depth?symbol={SYMBOL}` (order book depth), `GET /v1/trades?symbol={SYMBOL}` (public tape), and `GET /v1/udf/history` (OHLCV candles).
   - Live WebSocket listener (`wss://api.wallex.ir/ws`) streaming `{symbol}@depth` and `{symbol}@trade` channels to keep local price books updated in fractions of a second.
2. **Layer 2 — Account Operations & Agentic Execution via Wallex MCP (`src/wallex/mcp_client.py`):**
   - Integration with **Wallex MCP Server** supporting `/v1/account/balances`, `/v1/account/fee`, `/v1/account/openOrders`, and `POST /v1/account/orders` authenticated via `x-api-key`.
   - **Crucial Stale Price Refresh Mechanism:** Because model reasoning requires several hundred milliseconds, `WallexMCPClient.place_order` re-queries the latest `best_bid` and `best_ask` at the exact millisecond of dispatch. If prices have drifted beyond `MAX_PRICE_DRIFT_PCT = 0.40%`, stale orders are halted or re-priced safely.

### 2.2. Harness Engineering & Context Window Optimization
To prevent context window degradation (**Poisoning, Confusion, Conflict, Distraction**):
- **3 Curated Mega-Tools (`src/harness/mega_tools.py`)**: Replaces dozens of fine-grained API endpoints with 3 typed Pydantic tools:
  1. `wallex_market_intelligence`: Order book microstructure, Kronos projections, alpha/beta/gamma coefficients, and whitelisted market metrics.
  2. `wallex_trade_executor`: Order proposal submission (`propose_order`), cancellation, balance queries, and complete liquidation (`liquidate_all_to_toman`).
  3. `agent_memory_and_skills`: Skill loading (`load_skill_markdown`), active position management, and recording learned trade strategies.
- **Progressive Skill Disclosure (`skills/*/SKILL.md` & `src/harness/skill_loader.py`)**: The system prompt only contains high-level descriptions. Full formulas (`orderbook_scalp`, `risk_management`, `toman_settlement`) are lazily imported only when required by the market regime.
- **Three-Tier Memory Architecture (`src/harness/memory_manager.py` & `compaction.py`)**:
  - Intra-session short-term memory via LangGraph `MemorySaver`.
  - File-backed working memory in `memory/active_positions_plan.json` tracking exit criteria for open trades over the 72-hour window.
  - Self-learning episodic memory in `memory/learned_trading_rules.md` paired with OpenCode-style context compaction.

---

## 3. Pillar 3: Quantitative & Agentic Execution Signals

Trading decisions originate from the confluence of three analytical layers (`src/wallex/microstructure.py` + `src/models/kronos_forecaster.py` + `skills/orderbook_scalp/SKILL.md`):

### 3.1. Market Microstructure Indicators
1. **OrderBook Imbalance (OBI)** across the top 5 depth levels:
   $$\text{OBI}_5 = \frac{\sum_{i=1}^{5} V_{\text{bid}, i} - \sum_{i=1}^{5} V_{\text{ask}, i}}{\sum_{i=1}^{5} V_{\text{bid}, i} + \sum_{i=1}^{5} V_{\text{ask}, i}} \in [-1, +1]$$
2. **Microstructure Alpha ($\alpha_{\text{micro}}$)** (Volume-Weighted Midpoint vs Simple Midpoint):
   $$P_{\text{micro}} = \frac{P_{\text{bid}, 1} \cdot V_{\text{ask}, 1} + P_{\text{ask}, 1} \cdot V_{\text{bid}, 1}}{V_{\text{bid}, 1} + V_{\text{ask}, 1}}, \quad \alpha_{\text{micro}} = \frac{P_{\text{micro}} - P_{\text{mid}}}{P_{\text{mid}}} \times 10000 \text{ (bps)}$$
3. **Order Flow Beta ($\beta_{\text{flow}}$)** derived from `/v1/trades` and **Candle Volume Momentum Gamma ($\gamma_{\text{mom}}$)**.

### 3.2. Long Entry Criteria (`BUY`)
A `BUY` order (`LIMIT` pegged at `best_bid * (1 + 0.0002)` to capture Maker rebates and bypass spread costs) is triggered only when:
- $\text{OBI}_5 \ge +0.18$ and $\alpha_{\text{micro}} > +0.5 \text{ bps}$ (Demonstrated buy-side order book pressure).
- Current Order Book Spread $\text{Spread (\%)} \le 0.35\%$.
- 12-candle **Kronos** projection confirms: `expected_return_pct >= +0.85%` and `upside_probability >= 0.58`.
- Relative Strength Index `RSI(14)` is below overbought territory ($\text{RSI}_{14} < 68$).
- Fee-adjusted net reward-to-risk ratio (after two-way Wallex fees $2 \times 0.25\%$ and spread) fulfills **`expected_net_rr >= 2.0`**.

### 3.3. Exit Criteria, Take Profit (`SELL`) & Mandatory Toman Settlement (`LIQUIDATE_ALL_TO_TOMAN`)
- **Dynamic Stop-Loss:** Calculated dynamically between `1.5%` and `2.0%` below entry based on $\max(1.5 \times \text{ATR}, \text{Kronos Predicted Low})$.
- **Intelligent Alpha Exit:** If an open position encounters adverse order book skew ($\text{OBI}_5 < -0.22$), a negative Kronos forecast (`expected_return_pct < -0.30%`), or reaches target profit, an exit order is placed immediately.
- **100% Realized PnL in Toman:** Per hackathon regulations ("All profit and loss must be realized in Toman and no crypto assets may be held at close"), new buy orders are hard-blocked during the final 4 hours (`hours_remaining_in_challenge <= 4.0`), and all open crypto and USDT holdings are systematically liquidated to Toman.

---

## 4. Pillar 4: Capital Allocation, Deterministic Risk Gate & AI Governance

### 4.1. Deterministic Risk Gate (`src/governance/risk_gate.py`)
`DeterministicRiskGateNode` enforces 8 programmatic invariants prior to execution without LLM dependency:

| # | Governance & Risk Rule | Operational Parameter (5,000,000 TMN Capital) | Gate Enforcement Action |
| :-: | :--- | :--- | :--- |
| **1** | **Whitelisted Markets** | `ALLOWED_CREDIT_MARKETS` (`USDTTMN`, `BTCTMN`, `ETHTMN`, `SOLTMN`, ...) | Instant `REJECT` |
| **2** | **Maximum Order Size Cap** | Max **`18%`** of portfolio (**Cap of `900,000` TMN** per order) | Automatic quantity trimming (`adjusted_quantity`) to 18% |
| **3** | **Emergency Cash Reserve** | Minimum **`40%`** held in Toman cash (**At least `2,000,000` TMN** unencumbered) | Position size reduction or rejection if cash < 40% |
| **4** | **Dynamic Stop-Loss & R/R** | Mandatory stop-loss of **`1.5%` – `2.0%`** (Max risk ~18,000 TMN) with **`Net R/R >= 2.0`** | Auto-adjustment of stop/target or rejection |
| **5** | **Self-Trade Prevention (STP)** | Cross-checks account `openOrders` to prevent matching against own bids/asks | Rejection of conflicting order (`SELF_TRADE_PREVENTION`) |
| **6** | **Night Liquidity Adaptation** | 00:30 to 07:00 Tehran time or spread > `0.35%` | Order size halved (`9%` = 450,000 TMN) and `MARKET` forced to `LIMIT` |
| **7** | **Daily Drawdown Circuit Breaker** | Daily drawdown exceeding **`3.0%`** from portfolio High-Water Mark | Immediate trading halt and transition to `SHADOW` cooldown |
| **8** | **Final Toman Liquidation Gate** | `hours_remaining_in_challenge <= 4.0` | `BUY` orders disabled; 100% portfolio liquidated to Toman |

### 4.2. AI Governance & Simon Willison's Lethal Trifecta (`src/governance/security_guard.py`)
- **Breaking the Lethal Trifecta:**
  - The news monitor (`SentimentGuardNode`) runs in complete isolation without access to `.env` or trading execution tools. Inbound text is sanitized using multilingual prompt-injection filters.
  - Private API keys (`WALLEX_API_KEY`, `METIS_API_KEY`, `LLM_API_KEY`) are never exposed to LLM context. Direct filesystem reads of `.env` are blocked at code level.
- **Dedicated Agent Identity & Automatic Expiry (`AGENT_VIRTUAL_USER_ID=hackathon-wallex-agent`)**: Continually validates `AGENT_KEY_EXPIRES_AT` prior to every execution cycle.
- **Graceful Retirement Protocol (`scripts/retire_agent.py`)**: Cancels all pending orders, liquidates 100% of holdings to Toman, compiles the final PnL audit, and commits an immutable `logs/agent_retired.lock`.

---

## 5. Pillar 5: Reproducibility, Backtesting, Shadow Testing & Audit

### 5.1. Repository Layout
```text
wallex-agentic-trader/
├── .env.example                       # Environment template (No secrets)
├── .gitignore                         # Blocks .env, caches, and local databases
├── pyproject.toml                     # Python dependencies
├── docker-compose.yml                 # Orchestrates backend, frontend, and local models
├── README.md                          # Comprehensive 5-pillar technical documentation
├── skills/                            # Progressive disclosure skill library
│   ├── orderbook_scalp/SKILL.md
│   ├── risk_management/SKILL.md
│   └── recovery_settlement/SKILL.md
├── memory/                            # Harness working and episodic memory
│   ├── active_positions_plan.json
│   └── learned_trading_rules.md
├── logs/                              # Audit logs submitted for evaluation
│   └── decision_logs.jsonl
├── evaluation_results/                # Proof-of-performance benchmarks
│   ├── backtest_report.json
│   └── shadow_test_summary.json
├── src/
│   ├── config.py                      # Central configuration & risk settings
│   ├── wallex/
│   │   ├── rest_client.py             # Low-latency REST & WebSocket client
│   │   ├── mcp_client.py              # Wallex MCP client with Stale Price Refresh
│   │   └── microstructure.py          # Alpha, Beta, Gamma, OBI, Spread, and ATR engine
│   ├── models/
│   │   ├── kronos_forecaster.py       # Kronos model integration for probabilistic forecasts
│   │   └── system_one_engine.py       # /v1/systemone adapter (Jev, Mizan-4B, Laya, Kev)
│   ├── harness/
│   │   ├── mega_tools.py              # 3 Curated Mega-Tools preventing context bloat
│   │   ├── skill_loader.py            # Dynamic markdown skill loader
│   │   ├── memory_manager.py          # JSON position memory & self-learning journal
│   │   └── compaction.py              # OpenCode-style session compaction
│   ├── governance/
│   │   ├── risk_gate.py               # Deterministic risk engine & 18% order cap
│   │   └── security_guard.py          # Secret isolation & prompt injection guard
│   ├── graph/
│   │   ├── state.py                   # TypedDict TradingState schema
│   │   ├── nodes.py                   # 8 Graph node implementations
│   │   └── workflow.py                # StateGraph compiled with MemorySaver & interrupt
│   ├── testing/
│   │   ├── backtester.py              # Historical backtesting engine
│   │   └── shadow_engine.py           # Simulated live shadow execution engine
│   └── api/
│       └── server.py                  # FastAPI + AG-UI / CopilotKit endpoints
├── scripts/
│   ├── run_backtest.py                # Reproducible historical backtest runner
│   ├── run_shadow.py                  # Live market shadow test runner
│   ├── run_live.py                    # Live execution runner for dedicated account
│   └── retire_agent.py                # Final settlement and retirement script
└── frontend/                          # Chat Plus Next.js + shadcn/ui dashboard
    ├── package.json
    └── src/
        ├── app/page.tsx               # Chat Plus layout (Agent chat + Live canvas)
        └── components/genui/
            ├── TradeDecisionCard.tsx  # Signal, Kronos forecast & reasoning accordion
            ├── AgentGraphProgress.tsx # Live LangGraph execution tracker
            ├── DynamicRegimeView.tsx  # Declarative JSON market comparison renderer
            └── HITLApprovalModal.tsx  # Human-in-the-loop transition dialog
```

### 5.2. Step-by-Step Evaluator Quick Start

1. **Environment Setup:**
   ```bash
   cp .env.example .env
   pip install -e .
   ```
2. **Execute Historical Backtest & Generate Verification Metrics:**
   ```bash
   PYTHONPATH=. python3 scripts/run_backtest.py
   ```
   - Performance summaries are saved to `evaluation_results/backtest_report.json`, and decision logs are recorded in `logs/decision_logs.jsonl`.
3. **Execute Live Market Shadow Testing (Zero Real Financial Risk):**
   ```bash
   PYTHONPATH=. python3 scripts/run_shadow.py --cycles 10
   ```
   - Results are written to `evaluation_results/shadow_test_summary.json`. After 10 cycles, `MacroHITLInterruptNode` is ready for review.
4. **Execute Live Trading (On Dedicated Challenge Account):**
   ```bash
   EXECUTION_MODE=LIVE PYTHONPATH=. python3 scripts/run_live.py --cycles 50 --interval 60
   ```
5. **Final Toman Liquidation & Agent Retirement:**
   ```bash
   PYTHONPATH=. python3 scripts/retire_agent.py
   ```

---

## 6. Generative UI Dashboard (Chat Plus)

A modern **Chat Plus** dashboard built with **Next.js + Tailwind CSS + shadcn/ui + CopilotKit (`AG-UI` & Declarative `A2UI`)** provides real-time visibility into the trading agent's cognitive workflow:
- **Architecture & Risk Invariants:** Visualizes the 8-stage graph in `AgentGraphProgress`, highlighting the 18% order ceiling (`900,000 TMN`) and 40% cash reserve enforcement.
- **Backtesting & Live Shadow Verification:** Displays metrics from `evaluation_results/backtest_report.json` and supports live shadow execution with automated rendering of `TradeDecisionCard`.
- **HITL Elevation, Live Market Entry & Decision Accordion:** Allows human-in-the-loop approval via `HITLApprovalModal` and inspects the structured reasoning accordion showing **Kronos** and **System-1** probabilistic predictions.
- **Declarative UI & 100% Realized PnL in Toman:** Supports interactive market regime queries via `DynamicRegimeView` and provides real-time monitoring of emergency liquidation modules systematically converting all holdings into Toman (`100% Realized PnL in TMN`).
