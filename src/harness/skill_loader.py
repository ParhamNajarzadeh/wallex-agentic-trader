"""Progressive Disclosure Skill Loader (`skills/*/SKILL.md`) with YAML frontmatter and allowed-tools parsing."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from src.config import SKILLS_DIR


class SkillLoader:
    """Loads one-line skill summaries into the base prompt and discloses full SKILL.md on demand."""

    def __init__(self, skills_dir: Path | None = None) -> None:
        self.skills_dir = skills_dir or SKILLS_DIR

    def list_skill_summaries(self) -> list[dict[str, Any]]:
        """Return only name, description, and allowed-tools for progressive disclosure."""
        summaries: list[dict[str, Any]] = []
        for skill_file in sorted(self.skills_dir.glob("*/SKILL.md")):
            meta, _ = self._parse_frontmatter(skill_file.read_text(encoding="utf-8"))
            summaries.append(
                {
                    "name": meta.get("name", skill_file.parent.name),
                    "description": meta.get("description", ""),
                    "allowed_tools": meta.get("allowed-tools", []),
                    "path": str(skill_file.relative_to(self.skills_dir.parent)),
                }
            )
        return summaries

    def load_skill_markdown(self, skill_name: str) -> dict[str, Any]:
        """Load the full SKILL.md instructions for a specific skill when requested by System-1 or System-2."""
        clean_name = Path(skill_name).name.replace(".md", "")
        candidate = self.skills_dir / clean_name / "SKILL.md"
        if not candidate.exists():
            raise FileNotFoundError(f"Skill '{skill_name}' not found under {self.skills_dir}")

        raw_text = candidate.read_text(encoding="utf-8")
        meta, body = self._parse_frontmatter(raw_text)
        return {
            "name": meta.get("name", clean_name),
            "description": meta.get("description", ""),
            "allowed_tools": meta.get("allowed-tools", []),
            "body_markdown": body.strip(),
        }

    @staticmethod
    def _parse_frontmatter(text: str) -> tuple[dict[str, Any], str]:
        if not text.startswith("---"):
            return {}, text
        parts = text.split("---", 2)
        if len(parts) < 3:
            return {}, text
        fm_raw, body = parts[1], parts[2]
        meta: dict[str, Any] = {}
        current_list_key: str | None = None
        for line in fm_raw.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith("- ") and current_list_key:
                meta.setdefault(current_list_key, []).append(stripped[2:].strip())
            elif ":" in stripped:
                k, v = stripped.split(":", 1)
                k = k.strip()
                v = v.strip()
                if not v:
                    current_list_key = k
                    meta[k] = []
                else:
                    current_list_key = None
                    meta[k] = v
        return meta, body
