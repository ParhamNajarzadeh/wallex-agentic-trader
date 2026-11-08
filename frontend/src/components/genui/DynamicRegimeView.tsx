"use client";

import React from "react";

export interface DeclarativeA2UISchema {
  protocol: string;
  layout: string;
  title_fa: string;
  widgets: Array<{
    type: "System1ProbabilityBar" | "KronosComparisonTable" | "PortfolioRiskGauge";
    title: string;
    provider?: string;
    latency_ms?: number;
    probabilities?: Record<string, number>;
    rows?: Array<{
      symbol: string;
      kronos_expected_return_pct: string;
      upside_prob: string;
      obi: string;
      spread_pct: string;
      net_rr: string;
    }>;
    metrics?: {
      initial_capital_tmn: number;
      current_equity_tmn: number;
      free_tmn_reserve_pct: number;
      max_single_order_cap_pct: number;
      daily_drawdown_pct: number;
      circuit_breaker_limit_pct: number;
    };
  }>;
}

export const DynamicRegimeView: React.FC<{ schema: DeclarativeA2UISchema }> = ({ schema }) => {
  return (
    <div dir="rtl" className="rounded-xl border border-indigo-500/30 bg-slate-900/95 p-4 shadow-xl">
      <div className="mb-3 flex items-center justify-between border-b border-slate-800 pb-2.5">
        <div>
          <span className="rounded bg-indigo-500/20 px-2 py-0.5 text-[10px] font-bold text-indigo-300">
            Declarative GenUI ({schema.protocol})
          </span>
          <h3 className="mt-1 text-sm font-bold text-white">{schema.title_fa}</h3>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        {schema.widgets.map((w, idx) => {
          if (w.type === "System1ProbabilityBar" && w.probabilities) {
            return (
              <div key={idx} className="rounded-lg border border-slate-800 bg-slate-950/70 p-3">
                <div className="flex items-center justify-between text-xs font-bold text-slate-200">
                  <span>{w.title}</span>
                  <span className="text-[11px] text-cyan-400" dir="ltr">
                    {w.provider} ({w.latency_ms}ms)
                  </span>
                </div>
                <div className="mt-3 space-y-2">
                  {Object.entries(w.probabilities).map(([regime, prob]) => (
                    <div key={regime} className="text-xs">
                      <div className="flex justify-between text-[11px] text-slate-300" dir="ltr">
                        <span>{regime}</span>
                        <span>{(prob * 100).toFixed(1)}%</span>
                      </div>
                      <div className="mt-1 h-2 w-full overflow-hidden rounded-full bg-slate-800">
                        <div
                          className="h-full bg-gradient-to-r from-indigo-500 to-cyan-400"
                          style={{ width: `${Math.min(100, prob * 100)}%` }}
                        />
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            );
          }

          if (w.type === "KronosComparisonTable" && w.rows) {
            return (
              <div key={idx} className="rounded-lg border border-slate-800 bg-slate-950/70 p-3">
                <div className="text-xs font-bold text-slate-200">{w.title}</div>
                <div className="mt-2 overflow-x-auto">
                  <table className="w-full text-right text-[11px] text-slate-300">
                    <thead className="border-b border-slate-800 text-slate-400">
                      <tr>
                        <th className="py-1">نماد</th>
                        <th className="py-1">Kronos E[R]</th>
                        <th className="py-1">OBI</th>
                        <th className="py-1">اسپرد</th>
                        <th className="py-1">Net R/R</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-800/60">
                      {w.rows.map((r) => (
                        <tr key={r.symbol}>
                          <td className="py-1.5 font-bold text-white">{r.symbol}</td>
                          <td className="py-1.5 text-emerald-400 font-semibold" dir="ltr">
                            {r.kronos_expected_return_pct} ({r.upside_prob})
                          </td>
                          <td className="py-1.5" dir="ltr">{r.obi}</td>
                          <td className="py-1.5" dir="ltr">{r.spread_pct}</td>
                          <td className="py-1.5 font-bold text-cyan-300" dir="ltr">{r.net_rr}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            );
          }

          if (w.type === "PortfolioRiskGauge" && w.metrics) {
            const m = w.metrics;
            return (
              <div key={idx} className="rounded-lg border border-slate-800 bg-slate-950/70 p-3">
                <div className="text-xs font-bold text-slate-200">{w.title}</div>
                <div className="mt-2.5 space-y-2 text-xs text-slate-300">
                  <div className="flex justify-between">
                    <span>ارزش خالص فعلی (Realized TMN):</span>
                    <span className="font-bold text-emerald-400">
                      {m.current_equity_tmn.toLocaleString("fa-IR")} تومان
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span>ذخیره نقدی تومانی (کف ۴۰٪):</span>
                    <span className="font-semibold text-cyan-300">{m.free_tmn_reserve_pct}%</span>
                  </div>
                  <div className="flex justify-between">
                    <span>سقف کسری هر سفارش (قفل ۱۸٪):</span>
                    <span className="font-semibold text-indigo-300">{m.max_single_order_cap_pct}% (۹۰۰ هزار تومان)</span>
                  </div>
                  <div className="flex justify-between">
                    <span>افت سرمایه روزانه (Circuit Breaker 3%):</span>
                    <span className="font-semibold text-amber-300">{m.daily_drawdown_pct}%</span>
                  </div>
                </div>
              </div>
            );
          }

          return null;
        })}
      </div>
    </div>
  );
};
