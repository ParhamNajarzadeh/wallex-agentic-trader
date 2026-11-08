---
name: toman_settlement
description: Two-legged cycle settlement (TMN -> USDT -> Coin -> TMN), Self-Trade Prevention, and mandatory 4-hour End-of-Cycle Toman realization.
allowed-tools:
  - wallex_market_intelligence
  - wallex_trade_executor
  - agent_memory_and_skills
---
# Toman Settlement, Self-Trade Prevention & End-of-Cycle Liquidation (`toman_settlement`)

## 1. 100% Realized PnL in Toman (`TMN`)
The Wallex Hackathon rubric evaluates net return strictly on **Realized Toman Net Worth**:
$$\text{Return (\%)} = \frac{\text{Final Realized TMN} - 5,000,000}{5,000,000} \times 100$$
- Single-leg cycles (`TMN -> Coin -> TMN`) and two-leg cycles (`TMN -> USDT -> Coin -> USDT -> TMN`) must always close back into `TMN`.
- Holding unliquidated coins at the end of the 72-hour window is strictly forbidden.

## 2. Self-Trade Prevention (STP)
Before submitting any `BUY` or `SELL` order on `symbol`, inspect all open orders on the account (`check_open_orders_and_balance`):
- A new `BUY` order at price $P_{\text{buy}}$ is blocked or repriced if the account has an open `SELL` order on the same symbol with $P_{\text{sell,open}} \le P_{\text{buy}}$.
- A new `SELL` order at price $P_{\text{sell}}$ is blocked or repriced if the account has an open `BUY` order on the same symbol with $P_{\text{buy,open}} \ge P_{\text{sell}}$.

## 3. Mandatory 4-Hour End-of-Cycle Liquidation Gate
When `hours_remaining_in_challenge <= 4.0`:
1. Block all new `BUY` orders across all markets immediately.
2. Cancel all open `BUY` orders.
3. Execute stepped TWAP/Limit `SELL` orders (`liquidate_all_to_toman`) to convert 100% of crypto and USDT balances into realized `TMN`.
