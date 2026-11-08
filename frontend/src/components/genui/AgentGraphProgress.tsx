"use client";

import React from "react";

export interface GraphNodeStep {
  id: string;
  label: string;
  status: "pending" | "running" | "completed" | "interrupted";
  latency_ms?: number;
}

export const AgentGraphProgress: React.FC<{ steps: GraphNodeStep[] }> = ({ steps }) => {
  return (
    <div dir="rtl" className="rounded-xl border border-slate-800 bg-slate-900/90 p-4 shadow-md">
      <div className="mb-3 flex items-center justify-between">
        <h3 className="text-sm font-bold text-white">
          وضعیت زنده ایستگاه‌های گراف تصمیم‌گیری (LangGraph 8-Node Hybrid Harness)
        </h3>
        <span className="rounded-full bg-emerald-500/20 px-2.5 py-0.5 text-[11px] font-semibold text-emerald-300">
          ۱۰۰٪ خودکار (۰ معامله دستی)
        </span>
      </div>

      <div className="grid grid-cols-2 gap-2 sm:grid-cols-4 lg:grid-cols-8">
        {steps.map((step, index) => {
          const isDone = step.status === "completed";
          const isRunning = step.status === "running";
          return (
            <div
              key={step.id}
              className={`flex flex-col justify-between rounded-lg border p-2.5 text-right transition-all ${
                isDone
                  ? "border-emerald-500/40 bg-emerald-950/25 text-emerald-200"
                  : isRunning
                  ? "border-indigo-500 bg-indigo-950/40 text-indigo-200 animate-pulse"
                  : "border-slate-800 bg-slate-950/50 text-slate-400"
              }`}
            >
              <div className="flex items-center justify-between text-[11px] font-bold">
                <span>ایستگاه {index + 1}</span>
                <span>{isDone ? "✓" : isRunning ? "●" : "○"}</span>
              </div>
              <div className="mt-1.5 text-[11px] font-medium leading-tight text-slate-100" dir="ltr">
                {step.label}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
