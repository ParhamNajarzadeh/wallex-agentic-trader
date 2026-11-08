"use client";

import React, { useState } from "react";

export interface DecisionLogRecord {
  timestamp: string;
  cycle_id: string;
  execution_mode: "BACKTEST" | "SHADOW" | "LIVE";
  symbol: string;
  action: "BUY" | "SELL" | "HOLD" | "CANCEL" | "LIQUIDATE_ALL_TO_TOMAN";
  side: "BUY" | "SELL" | "NONE";
  order_type: "LIMIT" | "MARKET";
  quantity: number;
  price: number;
  stop_loss: number;
  take_profit: number;
  idempotency_key: string;
  observed_signals: {
    orderbook_imbalance: number;
    spread_pct: number;
    rsi_14: number;
    alpha_microstructure: number;
    kronos_expected_return_pct: number;
    kronos_upside_prob: number;
    system1_regime: string;
    system1_confidence: number;
  };
  ai_reasoning_fa: string;
  risk_gate_audit: {
    approved: boolean;
    rejection_reasons: string[];
    risk_metrics: Record<string, number>;
    portfolio_total_equity_tmn: number;
    portfolio_free_tmn: number;
    portfolio_realized_return_pct: number;
  };
}

export const TradeDecisionCard: React.FC<{ decision: DecisionLogRecord }> = ({ decision }) => {
  const [accordionOpen, setAccordionOpen] = useState<boolean>(true);

  const badgeColors: Record<string, string> = {
    BUY: "bg-emerald-500/20 text-emerald-300 border-emerald-500/40",
    SELL: "bg-amber-500/20 text-amber-300 border-amber-500/40",
    HOLD: "bg-slate-500/20 text-slate-300 border-slate-500/40",
    LIQUIDATE_ALL_TO_TOMAN: "bg-rose-500/20 text-rose-300 border-rose-500/40",
  };

  const notionalTmn = Math.round(decision.quantity * decision.price);
  const sig = decision.observed_signals;

  return (
    <div
      dir="rtl"
      className="rounded-xl border border-slate-800 bg-slate-900/90 p-4 shadow-lg backdrop-blur-md transition-all hover:border-slate-700"
    >
      {/* Header Row: Action Badge, Symbol, Mode, Timestamp */}
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-800 pb-3">
        <div className="flex items-center gap-2">
          <span
            className={`rounded-md border px-2.5 py-0.5 text-xs font-bold ${
              badgeColors[decision.action] || badgeColors.HOLD
            }`}
          >
            {decision.action}
          </span>
          <span className="text-base font-extrabold tracking-tight text-white">
            {decision.symbol}
          </span>
          <span className="rounded bg-indigo-500/20 px-2 py-0.5 text-[11px] font-medium text-indigo-300">
            {decision.execution_mode}
          </span>
        </div>
        <div className="text-xs text-slate-400">
          <span>سیکل: {decision.cycle_id}</span>
          <span className="mx-1.5">|</span>
          <span dir="ltr">{decision.timestamp.slice(11, 19)} UTC</span>
        </div>
      </div>

      {/* Quantitative Grid: Entry Price, Toman Notional, Stop-Loss, Take-Profit, Kronos Forecast */}
      <div className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-4">
        <div className="rounded-lg bg-slate-950/70 p-2.5 border border-slate-800/80">
          <div className="text-[11px] text-slate-400">قیمت ورود / مرجع (تومان)</div>
          <div className="mt-0.5 text-sm font-bold text-slate-100">
            {decision.price.toLocaleString("fa-IR")}
          </div>
          <div className="text-[10px] text-slate-500">حجم: {notionalTmn.toLocaleString("fa-IR")} تومان</div>
        </div>

        <div className="rounded-lg bg-slate-950/70 p-2.5 border border-slate-800/80">
          <div className="text-[11px] text-slate-400">حد ضرر پویا / حد سود</div>
          <div className="mt-0.5 text-xs font-semibold text-rose-400">
            SL: {decision.stop_loss > 0 ? decision.stop_loss.toLocaleString("fa-IR") : "—"}
          </div>
          <div className="text-xs font-semibold text-emerald-400">
            TP: {decision.take_profit > 0 ? decision.take_profit.toLocaleString("fa-IR") : "—"}
          </div>
        </div>

        <div className="rounded-lg bg-slate-950/70 p-2.5 border border-slate-800/80">
          <div className="text-[11px] text-slate-400">پیش‌بینی ۱۲ کندل Kronos</div>
          <div className="mt-0.5 text-sm font-bold text-cyan-400" dir="ltr">
            {sig.kronos_expected_return_pct >= 0 ? "+" : ""}
            {sig.kronos_expected_return_pct.toFixed(2)}%
          </div>
          <div className="text-[10px] text-slate-400">
            احتمال صعود خالص: {(sig.kronos_upside_prob * 100).toFixed(0)}%
          </div>
        </div>

        <div className="rounded-lg bg-slate-950/70 p-2.5 border border-slate-800/80">
          <div className="text-[11px] text-slate-400">ریزساختار اردربوک & System-1</div>
          <div className="mt-0.5 text-xs font-semibold text-amber-300" dir="ltr">
            OBI: {sig.orderbook_imbalance.toFixed(2)} | α: {sig.alpha_microstructure.toFixed(2)}
          </div>
          <div className="text-[10px] text-slate-400">
            رژیم: {sig.system1_regime} ({(sig.system1_confidence * 100).toFixed(0)}%)
          </div>
        </div>
      </div>

      {/* shadcn/ui Accordion for Full Persian AI Reasoning & Risk Audit */}
      <div className="mt-3 border-t border-slate-800/80 pt-2">
        <button
          type="button"
          onClick={() => setAccordionOpen(!accordionOpen)}
          className="flex w-full items-center justify-between py-1 text-right text-xs font-semibold text-indigo-300 hover:text-indigo-200"
        >
          <span>مشاهده استدلال کامل ایجنت (ai_reasoning_fa) و ممیزی گیت ریسک</span>
          <span>{accordionOpen ? "▲" : "▼"}</span>
        </button>

        {accordionOpen && (
          <div className="mt-2 space-y-2 rounded-lg bg-slate-950/90 p-3 text-xs leading-relaxed text-slate-200 border border-slate-800">
            <p className="text-slate-100">{decision.ai_reasoning_fa}</p>
            <div className="flex flex-wrap items-center gap-3 border-t border-slate-800 pt-2 text-[11px] text-slate-400">
              <span className="text-emerald-400 font-semibold">
                وضعیت گیت ریسک: {decision.risk_gate_audit.approved ? "تایید شده (Approved)" : "مسدود شده"}
              </span>
              <span>
                ارزش کل پرتفوی:{" "}
                {decision.risk_gate_audit.portfolio_total_equity_tmn.toLocaleString("fa-IR")} تومان
              </span>
              <span>
                بازدهی محقق‌شده: {decision.risk_gate_audit.portfolio_realized_return_pct.toFixed(2)}%
              </span>
              <span dir="ltr" className="text-slate-500">
                idempotency_key: {decision.idempotency_key}
              </span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
