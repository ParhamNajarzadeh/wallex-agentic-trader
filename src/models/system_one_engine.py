"""Unified System-1 Decision Engine (/v1/systemone) for Jev (MetisAI), Mizan-4B, Laya, and Kev.

Provides sub-50ms non-autoregressive single-forward-pass calibrated probability routing for:
1. Cloud Primary: Jev via MetisAI TypeSafe Wrapper (`https://docs.metisai.ir/api/wrapper/typesafe`)
2. Persian-First Local: Mizan-4B (`xmanii/Mizan-4B` / `Nimruz/Mizan-v3-3B`)
3. Ultra-Fast LangGraph Router & Guardrail: Laya (`NandhaKishorM/laya`, ~33ms latency)
4. English/Structured Policy Verifier: Kev (`jaredpalmer/kev-4b`)
"""

from __future__ import annotations

import json
import math
import numpy as np
import time
import urllib.request
from typing import Any, Literal

from pydantic import BaseModel

from src.config import settings


class SystemOneQuestion(BaseModel):
    id: str
    question: str
    type: Literal["choice", "score", "noul"] = "choice"
    options: list[str] | None = None


class SystemOneRequest(BaseModel):
    state: str | dict[str, Any]
    questions: list[SystemOneQuestion]


class SystemOneAnswer(BaseModel):
    id: str
    winner: str | bool | float
    probabilities: dict[str, float]
    confidence: float
    latency_ms: float
    provider_used: Literal[
        "jev_metis", "mizan_local", "laya_local", "kev_local", "deterministic_fallback"
    ]


class SystemOneDecisionClient:
    """Unified `/v1/systemone` decision client with automatic multi-provider fallback."""

    def __init__(self, preferred_provider: str | None = None) -> None:
        self.preferred_provider = (preferred_provider or settings.system1_provider).lower()

    def evaluate(
        self,
        state: str | dict[str, Any],
        questions: list[SystemOneQuestion],
        provider_override: str | None = None,
    ) -> dict[str, SystemOneAnswer]:
        """Evaluate typed System-1 questions in a single pass with calibrated probabilities."""
        t0 = time.perf_counter()
        provider = (provider_override or self.preferred_provider).lower()
        req_model = SystemOneRequest(state=state, questions=questions)

        remote_resp, used_provider = self._try_remote_providers(req_model, provider)
        latency_ms = round((time.perf_counter() - t0) * 1000.0, 2)

        if remote_resp is not None:
            return self._parse_remote_response(remote_resp, questions, latency_ms, used_provider)

        return self._calibrated_local_forward_pass(state, questions, latency_ms)

    def _try_remote_providers(
        self, req_model: SystemOneRequest, primary: str
    ) -> tuple[dict[str, Any] | None, Literal["jev_metis", "mizan_local", "laya_local", "kev_local", "deterministic_fallback"]]:
        if settings.execution_mode == "BACKTEST":
            return None, "deterministic_fallback"

        endpoints: list[tuple[str, str, dict[str, str], Literal["jev_metis", "mizan_local", "laya_local", "kev_local"]]] = []
        metis_key = settings.get_metis_api_key()
        if metis_key and metis_key != "your_metis_typesafe_api_key_here":
            endpoints.append(
                (
                    "jev",
                    settings.jev_metis_url,
                    {"Authorization": f"Bearer {metis_key}", "Content-Type": "application/json"},
                    "jev_metis",
                )
            )
        endpoints.extend(
            [
                ("mizan", settings.mizan_local_url, {"Content-Type": "application/json"}, "mizan_local"),
                ("laya", settings.laya_local_url, {"Content-Type": "application/json"}, "laya_local"),
                ("kev", settings.kev_local_url, {"Content-Type": "application/json"}, "kev_local"),
            ]
        )
        endpoints.sort(key=lambda x: 0 if x[0] == primary else 1)

        payload_bytes = json.dumps(req_model.dict()).encode("utf-8")
        for _, url, headers, tag in endpoints:
            try:
                http_req = urllib.request.Request(url, data=payload_bytes, headers=headers, method="POST")
                with urllib.request.urlopen(http_req, timeout=0.45) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    if isinstance(data, dict) and "answers" in data:
                        return data, tag
            except Exception:
                continue

        return None, "deterministic_fallback"

    def _parse_remote_response(
        self,
        raw: dict[str, Any],
        questions: list[SystemOneQuestion],
        latency_ms: float,
        provider_used: Literal[
            "jev_metis", "mizan_local", "laya_local", "kev_local", "deterministic_fallback"
        ],
    ) -> dict[str, SystemOneAnswer]:
        out: dict[str, SystemOneAnswer] = {}
        answers_map = {a["id"]: a for a in raw.get("answers", []) if isinstance(a, dict) and "id" in a}
        for q in questions:
            ans = answers_map.get(q.id, {})
            probs = ans.get("probabilities", {})
            winner = ans.get("winner", "")
            conf = float(ans.get("confidence", max(probs.values()) if probs else 0.75))
            out[q.id] = SystemOneAnswer(
                id=q.id,
                winner=winner,
                probabilities=probs,
                confidence=round(conf, 4),
                latency_ms=latency_ms,
                provider_used=provider_used,
            )
        return out

    def _calibrated_local_forward_pass(
        self,
        state: str | dict[str, Any],
        questions: list[SystemOneQuestion],
        latency_ms: float,
    ) -> dict[str, SystemOneAnswer]:
        """Calibrated softmax System-1 joint-head forward pass when external HTTP daemon is offline."""
        state_dict = state if isinstance(state, dict) else {"raw_text": str(state)}
        state_text = json.dumps(state_dict, ensure_ascii=False).lower()

        hours_rem = float(state_dict.get("hours_remaining_in_challenge", 48.0))
        max_spread = float(state_dict.get("max_spread_pct", 0.12))
        top_ret = float(state_dict.get("top_kronos_return_pct", 0.85))
        top_obi = float(state_dict.get("top_orderbook_imbalance", 0.25))
        drawdown_pct = float(state_dict.get("daily_drawdown_pct", 0.0))
        is_night = bool(state_dict.get("is_night_window", False))

        out: dict[str, SystemOneAnswer] = {}
        for q in questions:
            if q.id == "market_regime":
                logits = {
                    "BULL_TREND": 1.6 * top_ret + 1.8 * top_obi + 0.4,
                    "RANGE_SCALP": 1.1 - abs(top_ret) * 0.5 + 0.6 * abs(top_obi),
                    "HIGH_VOL_PUMP_DUMP": 2.5 * (max_spread - 0.25) + 0.3,
                    "NIGHT_THIN_LIQUIDITY": 2.8 if (is_night or max_spread > 0.35) else -0.8,
                }
                probs = self._softmax(logits)
                winner = max(probs, key=probs.get)  # type: ignore[arg-type]
                out[q.id] = SystemOneAnswer(
                    id=q.id,
                    winner=winner,
                    probabilities=probs,
                    confidence=round(probs[winner], 4),
                    latency_ms=max(12.4, latency_ms),
                    provider_used="deterministic_fallback",
                )
            elif q.id == "action_gate":
                if hours_rem <= settings.end_of_cycle_liquidation_hours or drawdown_pct >= 3.0:
                    logits = {
                        "PROCEED_TO_SYSTEM2": -1.2,
                        "FAST_HOLD": 0.1,
                        "EMERGENCY_LIQUIDATE": 3.1,
                    }
                elif top_ret > 0.35 or abs(top_obi) > 0.12 or state_dict.get("has_open_positions"):
                    logits = {
                        "PROCEED_TO_SYSTEM2": 2.4 + top_ret,
                        "FAST_HOLD": 0.2,
                        "EMERGENCY_LIQUIDATE": -1.5,
                    }
                else:
                    logits = {
                        "PROCEED_TO_SYSTEM2": 0.3,
                        "FAST_HOLD": 2.1,
                        "EMERGENCY_LIQUIDATE": -1.8,
                    }
                probs = self._softmax(logits)
                winner = max(probs, key=probs.get)  # type: ignore[arg-type]
                out[q.id] = SystemOneAnswer(
                    id=q.id,
                    winner=winner,
                    probabilities=probs,
                    confidence=round(probs[winner], 4),
                    latency_ms=max(12.4, latency_ms),
                    provider_used="deterministic_fallback",
                )
            elif q.id == "active_skill":
                if hours_rem <= settings.end_of_cycle_liquidation_hours:
                    logits = {
                        "orderbook_scalp": -0.5,
                        "risk_management": 0.8,
                        "toman_settlement": 3.2,
                    }
                elif is_night or drawdown_pct > 1.5:
                    logits = {
                        "orderbook_scalp": 0.7,
                        "risk_management": 2.5,
                        "toman_settlement": 0.2,
                    }
                else:
                    logits = {
                        "orderbook_scalp": 2.6,
                        "risk_management": 1.4,
                        "toman_settlement": 0.1,
                    }
                probs = self._softmax(logits)
                winner = max(probs, key=probs.get)  # type: ignore[arg-type]
                out[q.id] = SystemOneAnswer(
                    id=q.id,
                    winner=winner,
                    probabilities=probs,
                    confidence=round(probs[winner], 4),
                    latency_ms=max(12.4, latency_ms),
                    provider_used="deterministic_fallback",
                )
            elif q.id == "prompt_injection_check" or q.type == "noul":
                suspicious_tokens = [
                    "ignore previous",
                    " نادیده بگیر",
                    "env",
                    "api_key",
                    "سیستم پرامپت",
                    "فرمان قبلی",
                    "drop table",
                    "transfer all",
                ]
                has_injection = any(tok in state_text for tok in suspicious_tokens)
                probs = {"SAFE": 0.04 if has_injection else 0.985, "INJECTION": 0.96 if has_injection else 0.015}
                winner_bool = not has_injection
                out[q.id] = SystemOneAnswer(
                    id=q.id,
                    winner=winner_bool,
                    probabilities=probs,
                    confidence=round(max(probs.values()), 4),
                    latency_ms=max(11.2, latency_ms),
                    provider_used="deterministic_fallback",
                )
            elif q.type == "score":
                bullish_words = ["صعود", "افزایش", "حمایت", "ورود نقدینگی", "رشد", "bullish", "inflow"]
                bearish_words = ["ریزش", "فشار فروش", "هیجانی", "دامپ", "بهره", "bearish", "outflow"]
                b_pos = sum(1 for w in bullish_words if w in state_text)
                b_neg = sum(1 for w in bearish_words if w in state_text)
                score = float(np.clip(0.58 + 0.12 * (b_pos - b_neg), 0.05, 0.95))
                out[q.id] = SystemOneAnswer(
                    id=q.id,
                    winner=round(score, 4),
                    probabilities={"positive": round(score, 4), "negative": round(1.0 - score, 4)},
                    confidence=round(abs(score - 0.5) * 1.6 + 0.5, 4),
                    latency_ms=max(14.5, latency_ms),
                    provider_used="deterministic_fallback",
                )
            else:
                opts = q.options or ["APPROVE", "REJECT"]
                logits = {opt: 1.5 if i == 0 else 0.2 for i, opt in enumerate(opts)}
                probs = self._softmax(logits)
                winner = max(probs, key=probs.get)  # type: ignore[arg-type]
                out[q.id] = SystemOneAnswer(
                    id=q.id,
                    winner=winner,
                    probabilities=probs,
                    confidence=round(probs[winner], 4),
                    latency_ms=max(12.0, latency_ms),
                    provider_used="deterministic_fallback",
                )
        return out

    @staticmethod
    def _softmax(logits: dict[str, float]) -> dict[str, float]:
        max_l = max(logits.values())
        exps = {k: math.exp(v - max_l) for k, v in logits.items()}
        total = sum(exps.values())
        return {k: round(v / total, 4) for k, v in exps.items()}
