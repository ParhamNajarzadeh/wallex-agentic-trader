"""OpenCode-inspired Context Compaction Engine (`src/harness/compaction.py`).

Prevents Context Poisoning, Confusion, Conflict, and Distraction during continuous 72-hour runs
by compacting message history whenever estimated token count exceeds `MAX_CONTEXT_TOKENS` (12,000).
"""

from __future__ import annotations

import json
from typing import Any

from src.config import settings


class ContextCompactor:
    """Monitors session message token usage and compacts old tool traces into a structured state summary."""

    def __init__(self, max_tokens: int | None = None) -> None:
        self.max_tokens = max_tokens or settings.max_context_tokens

    @staticmethod
    def estimate_tokens(messages: list[Any]) -> int:
        """Estimate token count (~3.8 characters per token across Persian/English/JSON)."""
        total_chars = sum(len(json.dumps(m, default=str, ensure_ascii=False)) for m in messages)
        return max(1, int(total_chars / 3.8))

    def should_compact(self, messages: list[Any]) -> bool:
        return self.estimate_tokens(messages) > self.max_tokens or len(messages) > 24

    def compact_messages(
        self,
        messages: list[Any],
        portfolio_status: dict[str, Any],
        open_positions: dict[str, Any],
        learned_rules_snippet: str,
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        """Compact historical messages into a structured checkpoint preserving critical trading state."""
        tokens_before = self.estimate_tokens(messages)
        if not self.should_compact(messages):
            return messages, {
                "compacted": False,
                "tokens_before": tokens_before,
                "tokens_after": tokens_before,
            }

        summary_payload = {
            "compaction_event": "OPENCODE_STRUCTURED_COMPACTION",
            "timestamp": settings.now_iso(),
            "preserved_portfolio_status": {
                "total_equity_tmn": portfolio_status.get("total_equity_tmn"),
                "free_tmn": portfolio_status.get("free_tmn"),
                "daily_drawdown_pct": portfolio_status.get("daily_drawdown_pct"),
                "realized_return_pct": portfolio_status.get("realized_return_pct"),
            },
            "preserved_open_positions": open_positions,
            "active_learned_rules_tail": learned_rules_snippet[-600:],
            "pruned_messages_count": max(0, len(messages) - 4),
        }

        compacted_msg = {
            "role": "system",
            "name": "context_compactor",
            "content": (
                "خلاصه فشرده‌سازی کانتکست سشن (OpenCode Compaction): تاریخچه پیام‌های قدیمی پاک‌سازی شد. "
                f"وضعیت فعلی پرتفوی و پوزیشن‌های باز: {json.dumps(summary_payload, ensure_ascii=False)}"
            ),
        }
        recent_tail = list(messages[-3:]) if len(messages) >= 3 else list(messages)
        new_messages = [compacted_msg] + recent_tail
        tokens_after = self.estimate_tokens(new_messages)

        return new_messages, {
            "compacted": True,
            "tokens_before": tokens_before,
            "tokens_after": tokens_after,
            "messages_removed": max(0, len(messages) - len(new_messages)),
        }
