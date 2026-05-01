from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from app.orchestration.event_bus import AgentEventSink
from app.schemas.common import AgentName


@dataclass(frozen=True)
class LegacySkillsKnowledge:
    text: str = ""
    status: str = "loaded"
    warnings: list[str] = field(default_factory=list)


def load_optional_legacy_skills(
    *,
    agent: AgentName,
    loader: Callable[[], str],
    sink: AgentEventSink,
) -> LegacySkillsKnowledge:
    try:
        text = str(loader() or "")
    except Exception:
        warning = "本地 Skills 知识加载失败，已按无额外 Skills 知识降级运行。"
        sink.progress_step("skills_unavailable", warning, progress=0.12)
        return LegacySkillsKnowledge(
            text="",
            status="failed",
            warnings=[warning],
        )

    if not text.strip():
        warning = "未检测到本地 Skills 知识，已按无额外 Skills 知识降级运行。"
        sink.progress_step("skills_unavailable", warning, progress=0.12)
        return LegacySkillsKnowledge(
            text="",
            status="missing",
            warnings=[warning],
        )

    return LegacySkillsKnowledge(text=text, status="loaded")


def attach_legacy_skills_metadata(
    payload: dict,
    skills: LegacySkillsKnowledge,
) -> dict:
    enriched = dict(payload)
    enriched["legacy_skills_status"] = skills.status
    if skills.warnings:
        warnings = enriched.get("warnings", [])
        if not isinstance(warnings, list):
            warnings = [str(warnings)]
        enriched["warnings"] = [str(item) for item in warnings] + skills.warnings
    return enriched
