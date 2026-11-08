"""Three-Tier Memory Manager: Working Memory (`active_positions_plan.json`) & Episodic (`learned_trading_rules.md`)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.config import LOGS_DIR, MEMORY_DIR, settings


class MemoryManager:
    """Manages file-based Working Memory, Self-Learning Episodic Memory, and immutable JSONL decision logs."""

    def __init__(self, memory_dir: Path | None = None, logs_dir: Path | None = None) -> None:
        self.memory_dir = memory_dir or MEMORY_DIR
        self.logs_dir = logs_dir or LOGS_DIR
        self.working_memory_path = self.memory_dir / "active_positions_plan.json"
        self.learned_rules_path = self.memory_dir / "learned_trading_rules.md"
        self.decision_logs_path = self.logs_dir / "decision_logs.jsonl"
        self._ensure_files()

    def _ensure_files(self) -> None:
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        if not self.working_memory_path.exists():
            self.working_memory_path.write_text(
                json.dumps(
                    {
                        "schema_version": "1.0",
                        "updated_at": settings.now_iso(),
                        "high_water_mark_tmn": settings.initial_capital_tmn,
                        "shadow_validated_decisions": 0,
                        "circuit_breaker_active": False,
                        "open_positions": {},
                    },
                    indent=2,
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
        if not self.learned_rules_path.exists():
            self.learned_rules_path.write_text(
                "# ژورنال خودآموز قوانین معاملاتی ایجنت والکس\n", encoding="utf-8"
            )

    def read_working_memory(self) -> dict[str, Any]:
        """Read current active positions plan and high-water mark from JSON working memory."""
        try:
            return json.loads(self.working_memory_path.read_text(encoding="utf-8"))
        except Exception:
            return {
                "schema_version": "1.0",
                "updated_at": settings.now_iso(),
                "high_water_mark_tmn": settings.initial_capital_tmn,
                "shadow_validated_decisions": 0,
                "circuit_breaker_active": False,
                "open_positions": {},
            }

    def write_working_memory(self, data: dict[str, Any]) -> dict[str, Any]:
        """Atomically persist updated working memory plan to disk."""
        data["updated_at"] = settings.now_iso()
        self.working_memory_path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        return data

    def update_position_plan(
        self,
        symbol: str,
        side: str,
        quantity: float,
        entry_price: float,
        stop_loss: float,
        take_profit: float,
        reasoning_fa: str,
    ) -> dict[str, Any]:
        """Record or close an active position plan in `memory/active_positions_plan.json`."""
        mem = self.read_working_memory()
        positions = mem.setdefault("open_positions", {})
        if side == "BUY" and quantity > 0:
            positions[symbol] = {
                "symbol": symbol,
                "quantity": round(quantity, 6),
                "entry_price": round(entry_price, 4),
                "stop_loss": round(stop_loss, 4),
                "take_profit": round(take_profit, 4),
                "opened_at": settings.now_iso(),
                "entry_reasoning_fa": reasoning_fa,
            }
        elif side in ("SELL", "LIQUIDATE_ALL_TO_TOMAN"):
            positions.pop(symbol, None)
        return self.write_working_memory(mem)

    def read_learned_rules(self) -> str:
        """Read episodic self-learning trading rules markdown."""
        return self.learned_rules_path.read_text(encoding="utf-8")

    def append_learned_rule(self, rule_id: str, lesson_text_fa: str) -> str:
        """Append a post-trade reflection lesson to `memory/learned_trading_rules.md`."""
        current = self.read_learned_rules()
        entry = f"\n- **[{rule_id}] ({settings.now_iso()[:19]}Z):** {lesson_text_fa.strip()}\n"
        if rule_id not in current:
            updated = current.rstrip() + entry
            self.learned_rules_path.write_text(updated, encoding="utf-8")
            return updated
        return current

    def append_decision_log(self, record: dict[str, Any]) -> None:
        """Append an immutable JSONL audit record to `logs/decision_logs.jsonl`."""
        with self.decision_logs_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    def read_recent_decision_logs(self, limit: int = 50) -> list[dict[str, Any]]:
        """Read the latest `limit` trade decision records from `logs/decision_logs.jsonl`."""
        if not self.decision_logs_path.exists():
            return []
        lines = self.decision_logs_path.read_text(encoding="utf-8").splitlines()
        records = []
        for line in lines[-limit:]:
            if line.strip():
                try:
                    records.append(json.loads(line))
                except Exception:
                    continue
        return records
