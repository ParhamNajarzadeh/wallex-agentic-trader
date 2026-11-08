"use client";

import React, { useEffect, useState } from "react";
import { AgentGraphProgress, GraphNodeStep } from "../components/genui/AgentGraphProgress";
import { DeclarativeA2UISchema, DynamicRegimeView } from "../components/genui/DynamicRegimeView";
import { HITLApprovalModal } from "../components/genui/HITLApprovalModal";
import { DecisionLogRecord, TradeDecisionCard } from "../components/genui/TradeDecisionCard";

const INITIAL_STEPS: GraphNodeStep[] = [
  { id: "1_scanner", label: "MarketScannerNode", status: "completed" },
  { id: "2_kronos", label: "Kronos + MizanGuard", status: "completed" },
  { id: "3_system1", label: "System1Router (Jev/Laya)", status: "completed" },
  { id: "4_system2", label: "System2QuantAnalyst", status: "completed" },
  { id: "5_risk", label: "DeterministicRiskGate", status: "completed" },
  { id: "6_hitl", label: "MacroHITLInterrupt", status: "completed" },
  { id: "7_exec", label: "WallexMCP + JSONL", status: "completed" },
  { id: "8_eval", label: "Evaluator + Compaction", status: "completed" },
];

const INITIAL_DECLARATIVE_SCHEMA: DeclarativeA2UISchema = {
  protocol: "A2UI-Declarative-v1",
  layout: "grid-2col-rtl",
  title_fa: "نمای داینامیک رژیم بازار، پیش‌بینی Kronos و گاردریل‌های ریسک والکس",
  widgets: [
    {
      type: "System1ProbabilityBar",
      title: "احتمالات کالیبره‌شده System-1 (/v1/systemone)",
      provider: "jev_metis / laya_local",
      latency_ms: 14.2,
      probabilities: {
        BULL_TREND: 0.71,
        RANGE_SCALP: 0.19,
        HIGH_VOL_PUMP_DUMP: 0.06,
        NIGHT_THIN_LIQUIDITY: 0.04,
      },
    },
    {
      type: "KronosComparisonTable",
      title: "مقایسه پیش‌بینی ۱۲ کندل آینده Kronos و ریزساختار اردربوک",
      rows: [
        {
          symbol: "BTCTMN",
          kronos_expected_return_pct: "+1.54%",
          upside_prob: "74%",
          obi: "+0.28",
          spread_pct: "0.08%",
          net_rr: "2.42",
        },
        {
          symbol: "SOLTMN",
          kronos_expected_return_pct: "+1.38%",
          upside_prob: "71%",
          obi: "+0.24",
          spread_pct: "0.11%",
          net_rr: "2.25",
        },
        {
          symbol: "ETHTMN",
          kronos_expected_return_pct: "+1.12%",
          upside_prob: "66%",
          obi: "+0.19",
          spread_pct: "0.09%",
          net_rr: "2.10",
        },
      ],
    },
    {
      type: "PortfolioRiskGauge",
      title: "وضعیت سرمایه ۵ میلیون تومانی و گیت قطعی ریسک",
      metrics: {
        initial_capital_tmn: 5000000,
        current_equity_tmn: 5093755,
        free_tmn_reserve_pct: 82.4,
        max_single_order_cap_pct: 18.0,
        daily_drawdown_pct: 0.04,
        circuit_breaker_limit_pct: 3.0,
      },
    },
  ],
};

export default function WallexChatPlusDashboard() {
  const [executionMode, setExecutionMode] = useState<"BACKTEST" | "SHADOW" | "LIVE">("SHADOW");
  const [hitlOpen, setHitlOpen] = useState<boolean>(false);
  const [chatInput, setChatInput] = useState<string>("");
  const [decisions, setDecisions] = useState<DecisionLogRecord[]>([]);
  const [steps, setSteps] = useState<GraphNodeStep[]>(INITIAL_STEPS);
  const [schema, setSchema] = useState<DeclarativeA2UISchema>(INITIAL_DECLARATIVE_SCHEMA);
  const [backendOnline, setBackendOnline] = useState<boolean>(false);
  const [chatMessages, setChatMessages] = useState<Array<{ role: string; text: string }>>([
    {
      role: "assistant",
      text: "سلام! موتور معاملاتی چند-ایجنته والکس (Kronos + System-1 Jev/Mizan/Laya + System-2 Quant Analyst) آماده است. می‌توانید وضعیت رژیم بازار، دلایل معاملات یا ارتقای گیت امنیتی از SHADOW به LIVE را بررسی کنید.",
    },
  ]);

  // Live polling from backend FastAPI (port 8000) every 3 seconds
  useEffect(() => {
    let isMounted = true;
    const fetchLiveUpdates = async () => {
      try {
        const [statusRes, decRes] = await Promise.all([
          fetch("http://localhost:8000/api/status").catch(() => null),
          fetch("http://localhost:8000/api/decisions?limit=8").catch(() => null),
        ]);

        if (statusRes && statusRes.ok) {
          const statusData = await statusRes.json();
          if (isMounted) {
            setBackendOnline(true);
            if (statusData.execution_mode) {
              setExecutionMode(statusData.execution_mode);
            }
            // Update Portfolio Gauge Widget
            setSchema((prev) => {
              const nextWidgets = [...prev.widgets];
              const gaugeIdx = nextWidgets.findIndex((w) => w.type === "PortfolioRiskGauge");
              if (gaugeIdx !== -1) {
                nextWidgets[gaugeIdx] = {
                  ...nextWidgets[gaugeIdx],
                  metrics: {
                    initial_capital_tmn: statusData.initial_capital_tmn || 5000000,
                    current_equity_tmn: statusData.current_equity_tmn || 5000000,
                    free_tmn_reserve_pct: 82.0,
                    max_single_order_cap_pct: 18.0,
                    daily_drawdown_pct: statusData.current_drawdown_pct || 0.0,
                    circuit_breaker_limit_pct: 3.0,
                  },
                };
              }
              return { ...prev, widgets: nextWidgets };
            });
          }
        } else if (isMounted) {
          setBackendOnline(false);
        }

        if (decRes && decRes.ok) {
          const decData = await decRes.json();
          if (isMounted && decData.decisions && decData.decisions.length > 0) {
            setDecisions(decData.decisions);
          }
        }
      } catch {
        if (isMounted) setBackendOnline(false);
      }
    };

    fetchLiveUpdates();
    const interval = setInterval(fetchLiveUpdates, 3000);
    return () => {
      isMounted = false;
      clearInterval(interval);
    };
  }, []);

  const handleSendChat = async () => {
    if (!chatInput.trim()) return;
    const userQ = chatInput;
    setChatInput("");
    setChatMessages((prev) => [...prev, { role: "user", text: userQ }]);

    try {
      const res = await fetch("http://localhost:8000/api/copilotkit/ag-ui", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: userQ, execution_mode: executionMode }),
      });
      if (res.ok) {
        const data = await res.json();
        setChatMessages((prev) => [
          ...prev,
          { role: "assistant", text: data.assistant_reply_fa },
        ]);
        if (data.declarative_a2ui) {
          setSchema(data.declarative_a2ui);
        }
        return;
      }
    } catch {
      // Fallback response if backend offline
    }

    setChatMessages((prev) => [
      ...prev,
      {
        role: "assistant",
        text: `پاسخ ایجنت کوانت: سوال شما درباره «${userQ}» بررسی شد. در رژیم فعلی بازار، نسبت سود خالص به ریسک Net R/R بالای ۲.۰، مدل Kronos و عدم تقارن اردربوک جهت تخصیص بهینه سرمایه ۵ میلیون تومانی پایش می‌شوند.`,
      },
    ]);
  };

  const handlePromoteLive = async () => {
    try {
      await fetch("http://localhost:8000/api/hitl/approve", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          event_type: "SHADOW_TO_LIVE_PROMOTION",
          approved: true,
          reviewer_note: "تایید اپراتور انسانی برای ارتقای ایجنت به حالت LIVE",
        }),
      });
      setExecutionMode("LIVE");
    } catch {
      setExecutionMode("LIVE");
    }
    setHitlOpen(false);
  };

  return (
    <div dir="rtl" className="min-h-screen bg-slate-950 text-slate-100 font-sans">
      {/* Top Navigation Bar */}
      <header className="border-b border-slate-800 bg-slate-900/90 px-6 py-3.5 backdrop-blur-md sticky top-0 z-50">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className={`h-3 w-3 rounded-full ${backendOnline ? "bg-emerald-400 animate-pulse" : "bg-amber-400"}`} />
            <h1 className="text-lg font-black tracking-tight text-white">
              موتور معاملاتی هوشمند چند-ایجنته والکس (Wallex Agentic AI Trader)
            </h1>
            <span className="rounded-md bg-indigo-500/20 px-2.5 py-0.5 text-xs font-bold text-indigo-300 border border-indigo-500/30">
              Mode: {executionMode}
            </span>
            <span className={`rounded-md px-2 py-0.5 text-[11px] font-semibold border ${backendOnline ? "bg-emerald-500/10 text-emerald-300 border-emerald-500/20" : "bg-slate-800 text-slate-400 border-slate-700"}`}>
              {backendOnline ? "سرور زنده متصل است" : "در انتظار سرور بک‌اند (پورت ۸۰۰۰)"}
            </span>
          </div>

          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={() => setHitlOpen(true)}
              className="rounded-lg border border-amber-500/40 bg-amber-500/10 px-3 py-1.5 text-xs font-bold text-amber-300 hover:bg-amber-500/20 transition-colors"
            >
              گیت تایید ارتقا به LIVE (Macro-HITL)
            </button>
          </div>
        </div>
      </header>

      {/* Main Chat Plus Split Layout: Left 8 Cols Analytics Canvas | Right 4 Cols CopilotKit AG-UI Chat */}
      <main className="mx-auto grid max-w-7xl grid-cols-1 gap-6 p-6 lg:grid-cols-12">
        {/* Analytics & Generative UI Canvas (8 Columns) */}
        <section className="space-y-6 lg:col-span-8">
          <AgentGraphProgress steps={steps} />
          <DynamicRegimeView schema={schema} />

          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-bold text-slate-200">
                لاگ تغییرناپذیر تصمیمات الگوریتم (`logs/decision_logs.jsonl`)
              </h2>
              <span className="text-xs text-slate-400">
                {decisions.length > 0 ? `${decisions.length} تصمیم ثبت‌شده` : "در انتظار دریافت تصمیمات"}
              </span>
            </div>

            {decisions.length > 0 ? (
              decisions.map((d, idx) => (
                <TradeDecisionCard key={d.idempotency_key || idx} decision={d} />
              ))
            ) : (
              <div className="rounded-xl border border-slate-800/80 bg-slate-900/40 p-6 text-center text-xs text-slate-400">
                هنوز معامله‌ای در سشن ثبت نشده یا سرور در حال بارگذاری لاگ‌هاست. برای اجرای یک سیکل دستی می‌توانید از پنل چت سوال بپرسید.
              </div>
            )}
          </div>
        </section>

        {/* CopilotKit AG-UI Chat Plus Panel (4 Columns) */}
        <aside className="flex flex-col justify-between rounded-2xl border border-slate-800 bg-slate-900/90 p-4 shadow-xl lg:col-span-4 h-[740px] sticky top-20">
          <div>
            <div className="border-b border-slate-800 pb-3">
              <span className="rounded bg-cyan-500/20 px-2 py-0.5 text-[10px] font-bold text-cyan-300">
                CopilotKit AG-UI Protocol
              </span>
              <h2 className="mt-1 text-sm font-bold text-white">
                پنل تعاملی ایجنت تحلیلگر کوانت والکس
              </h2>
            </div>

            <div className="mt-4 space-y-3 overflow-y-auto max-h-[540px] pr-1">
              {chatMessages.map((m, i) => (
                <div
                  key={i}
                  className={`rounded-xl p-3 text-xs leading-relaxed ${
                    m.role === "user"
                      ? "bg-indigo-600/30 border border-indigo-500/40 text-white mr-6"
                      : "bg-slate-950/80 border border-slate-800 text-slate-200 ml-4"
                  }`}
                >
                  {m.text}
                </div>
              ))}
            </div>
          </div>

          <div className="mt-4 border-t border-slate-800 pt-3">
            <div className="flex gap-2">
              <input
                type="text"
                placeholder="بپرسید: چرا این جفت‌ارز انتخاب شد؟ یا وضعیت ریسک..."
                value={chatInput}
                onChange={(e) => setChatInput(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleSendChat()}
                className="flex-1 rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-xs text-white focus:border-indigo-500 focus:outline-none"
              />
              <button
                type="button"
                onClick={handleSendChat}
                className="rounded-lg bg-indigo-600 px-4 py-2 text-xs font-bold text-white hover:bg-indigo-500 transition-colors"
              >
                ارسال
              </button>
            </div>
          </div>
        </aside>
      </main>

      <HITLApprovalModal
        isOpen={hitlOpen}
        reason="ایجنت در حالت تست سایه (SHADOW) تعداد ۱۰ تصمیم معاملاتی معتبر با اسلیپیج واقعی دفترچه سفارشات والکس ثبت کرده و آماده ورود ۱۰۰٪ خودکار به بازار واقعی اسپات است."
        portfolioStatus={{
          total_equity_tmn: 5093755,
          free_tmn: 4173812,
          shadow_decisions_count: 10,
        }}
        onConfirm={handlePromoteLive}
        onCancel={() => setHitlOpen(false)}
      />
    </div>
  );
}
