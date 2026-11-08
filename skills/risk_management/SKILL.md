---
name: risk_management
description: Fractional position sizing (max 18%), ATR/Kronos dynamic stop-loss, fee-adjusted Net R/R >= 2.0, and night-thin liquidity rules.
allowed-tools:
  - wallex_market_intelligence
  - wallex_trade_executor
  - agent_memory_and_skills
---
# Quantitative Risk Management & Capital Preservation (`risk_management`)

## 1. Fractional Position Sizing on 5,000,000 TMN Capital
- **Single Order Cap**: Never allocate more than `18%` of total equity (`<= 900,000 TMN`) to a single buy order. Any order above 20% is hard-blocked by `DeterministicRiskGateNode`.
- **Cash Reserve Floor**: Maintain at least `40%` of total portfolio equity (`>= 2,000,000 TMN`) in liquid Toman (`TMN`) at all times. Total concurrent crypto exposure must not exceed `60%`.

## 2. Dynamic Stop-Loss & Fee-Adjusted Net Risk/Reward
- **Stop-Loss Placement**: Set `stop_loss` using the tighter bound of `1.5% to 2.0%` below `entry_price` and `kronos_predicted_low_min`:
  $$P_{\text{SL}} = \text{clip}\!\left(\min(P_{\text{entry}} - 1.5\times\text{ATR}_{14},\; P_{\text{Kronos,low}}),\; 0.980\,P_{\text{entry}},\; 0.985\,P_{\text{entry}}\right)$$
- **Maximum Portfolio Risk per Trade**: With an 18% position size and 2.0% stop-loss, maximum portfolio loss on any single trade is strictly bounded to `0.36%` (`~18,000 TMN`).
- **Net Risk/Reward Gate**:
  $$\text{Net R/R} = \frac{\text{Gross Target Return (\%)} - (2 \times \text{Fee (\%)} + \text{Spread (\%)})}{\text{Stop-Loss Distance (\%)} + (2 \times \text{Fee (\%)} + \text{Spread (\%)})} \ge 2.0$$

## 3. Night Liquidity Adaptation & Drawdown Circuit Breaker
- Between `00:30` and `07:00` Asia/Tehran time (or whenever `spread_pct > 0.35%`), cut maximum order size in half (`<= 9%` equity / `450,000 TMN`) and force `order_type = "LIMIT"`.
- If daily drawdown from the High-Water Mark exceeds `3.0%` (`150,000 TMN`), trigger the **Circuit Breaker** and switch to `SHADOW` cooldown mode for 4 hours.
