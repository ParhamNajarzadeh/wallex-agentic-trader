---
name: orderbook_scalp
description: Microstructure Alpha/Beta/Gamma, OrderBook Imbalance (OBI), and Kronos K-line confluence strategy for spot scalping on Wallex.
allowed-tools:
  - wallex_market_intelligence
  - wallex_trade_executor
  - agent_memory_and_skills
---
# OrderBook Microstructure & Kronos K-Line Scalping Protocol (`orderbook_scalp`)

## 1. Quantitative Signal Formulas
When analyzing candidate Wallex credit markets (`USDTTMN`, `BTCTMN`, `ETHTMN`, `SOLTMN`, `TONTMN`, `XRPTMN`), combine OrderBook Microstructure with the **Kronos** 12-step K-line trajectory forecast:

1. **OrderBook Imbalance ($\text{OBI}_5$)**:
   $$\text{OBI}_5 = \frac{\sum_{i=1}^5 w_i V_{\text{bid}, i} - \sum_{i=1}^5 w_i V_{\text{ask}, i}}{\sum_{i=1}^5 w_i V_{\text{bid}, i} + \sum_{i=1}^5 w_i V_{\text{ask}, i}}, \quad w_i = e^{-0.25(i-1)}$$
   - Bullish threshold: $\text{OBI}_5 \ge +0.18$.
   - Bearish/Exit threshold: $\text{OBI}_5 \le -0.20$.

2. **Microstructure $\alpha, \beta, \gamma$**:
   - $\alpha$ (Micro-price lead): $\frac{P_{\text{micro}} - P_{\text{mid}}}{\text{Spread}} + 0.65\,\text{OBI}_5$. Entry requires $\alpha \ge +0.15$.
   - $\beta$ (Tape Order-Flow): Aggressive buy volume minus sell volume normalized by total recent trade volume.
   - $\gamma$ (Depth Convexity): Top-3 level liquidity divided by Top-10 liquidity. High $\gamma > 0.45$ indicates concentrated support near the best bid/ask.

3. **Kronos K-Line Confluence (`shiyu-coder/Kronos`)**:
   - Require `kronos_expected_return_pct >= 0.95%` (exceeding 2x round-trip fee + spread).
   - Require `kronos_upside_prob >= 0.62` across sampled trajectories.

## 2. Execution & Stale Price Discipline
- Prefer `LIMIT` orders placed at `best_bid + tick_size` (Maker fee `0.20%`) when `spread_pct <= 0.25%`.
- Always verify live `best_bid` and `best_ask` via `wallex_trade_executor` to prevent stale price slippage (`MAX_PRICE_DRIFT_PCT = 0.40%`).
