"use client";

import React, { useState } from "react";

export interface HITLApprovalModalProps {
  isOpen: boolean;
  reason: string;
  shadowValidatedCount: number;
  virtualReturnPct: number;
  onApprove: (note: string) => void;
  onReject: () => void;
}

export const HITLApprovalModal: React.FC<HITLApprovalModalProps> = ({
  isOpen,
  reason,
  shadowValidatedCount,
  virtualReturnPct,
  onApprove,
  onReject,
}) => {
  const [note, setNote] = useState<string>(
    "تایید نتایج ۱۰ سیکل Shadow Testing و مجوز ورود خودکار به بازار اسپات والکس با سقف ریسک ۱۸٪"
  );

  if (!isOpen) return null;

  return (
    <div
      dir="rtl"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 p-4 backdrop-blur-sm"
    >
      <div className="w-full max-w-lg rounded-2xl border border-amber-500/40 bg-slate-900 p-6 shadow-2xl">
        <div className="flex items-center justify-between border-b border-slate-800 pb-3">
          <span className="rounded bg-amber-500/20 px-2.5 py-1 text-xs font-bold text-amber-300">
            گیت حاکمیت کلان (LangGraph Macro-HITL Interrupt)
          </span>
          <span className="text-xs text-slate-400">حساب اختصاصی ۵ میلیون تومانی والکس</span>
        </div>

        <h3 className="mt-4 text-base font-extrabold text-white">
          تایید ارتقای وضعیت از تست سایه (SHADOW) به معاملات واقعی (LIVE)
        </h3>
        <p className="mt-2 text-xs leading-relaxed text-slate-300">{reason}</p>

        <div className="mt-4 grid grid-cols-2 gap-3 rounded-xl bg-slate-950 p-3 border border-slate-800">
          <div>
            <div className="text-[11px] text-slate-400">سیکل‌های موفق تست سایه</div>
            <div className="text-sm font-bold text-emerald-400">
              {shadowValidatedCount} تصمیم ممیزی‌شده
            </div>
          </div>
          <div>
            <div className="text-[11px] text-slate-400">بازده مجازی محقق‌شده</div>
            <div className="text-sm font-bold text-cyan-400" dir="ltr">
              +{virtualReturnPct.toFixed(2)}%
            </div>
          </div>
        </div>

        <div className="mt-4">
          <label className="block text-xs font-semibold text-slate-300">
            یادداشت ممیزی ناظر (ثبت در لاگ حاکمیت):
          </label>
          <input
            type="text"
            value={note}
            onChange={(e) => setNote(e.target.value)}
            className="mt-1.5 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-xs text-white focus:border-indigo-500 focus:outline-none"
          />
        </div>

        <div className="mt-5 flex items-center justify-end gap-3">
          <button
            type="button"
            onClick={onReject}
            className="rounded-lg border border-slate-700 bg-slate-800 px-4 py-2 text-xs font-semibold text-slate-300 hover:bg-slate-700"
          >
            ادامه در وضعیت SHADOW
          </button>
          <button
            type="button"
            onClick={() => onApprove(note)}
            className="rounded-lg bg-emerald-600 px-4 py-2 text-xs font-bold text-white shadow-lg hover:bg-emerald-500"
          >
            تایید و فعال‌سازی اجرای ۱۰۰٪ خودکار LIVE
          </button>
        </div>
      </div>
    </div>
  );
};
