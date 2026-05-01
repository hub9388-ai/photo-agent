from __future__ import annotations

import uuid
from typing import Any, Callable

from starlette.concurrency import run_in_threadpool

from app.agents.base import LegacyAgentService
from app.agents.legacy_skills import attach_legacy_skills_metadata, load_optional_legacy_skills
from app.orchestration.event_bus import AgentEventSink
from app.schemas.agent import CoachAgentRequest
from app.schemas.result import AgentResult
from app.storage.media_store import MediaStore, get_media_store


class CoachAgentService(LegacyAgentService):
    def __init__(
        self,
        *,
        media_store: MediaStore | None = None,
        model_client: Any | None = None,
        model_client_factory: Callable[[Any], Any] | None = None,
    ) -> None:
        super().__init__(
            agent_name="coach",
            module_name="photo_v2",
            required_callables=("run_learning_coach_turn",),
        )
        self.media_store = media_store or get_media_store()
        self.model_client = model_client
        self.model_client_factory = model_client_factory

    async def run(self, request: CoachAgentRequest, sink: AgentEventSink) -> AgentResult:
        return await run_in_threadpool(self._run_sync, request, sink)

    def _run_sync(self, request: CoachAgentRequest, sink: AgentEventSink) -> AgentResult:
        legacy = self.load_legacy_module()

        sink.progress_step("loading_profile", "正在读取学习反馈上下文", progress=0.1)
        profile = legacy.load_profile()
        skills = load_optional_legacy_skills(
            agent="coach",
            loader=legacy.load_skills_knowledge,
            sink=sink,
        )
        system = legacy.build_learning_system_prompt(
            profile,
            skills.text,
            handoff_issues=request.handoff_issues,
        )

        media_items: list[dict] = []
        total_files = 0
        if request.media_ids:
            sink.progress_step("preparing_media", "正在准备学习点评预览图", progress=0.25)
            media_items, total_files, _ = self.media_store.prepare_legacy_media_items(
                request.media_ids,
                legacy.prepare_media_items,
                sink=sink,
            )

        sink.progress_step("calling_model", "正在运行学习教练 Agent", progress=0.55)
        visible_text, payload = legacy.run_learning_coach_turn(
            client=self._create_model_client(legacy),
            system=system,
            messages=[],
            user_text=request.user_text,
            media_items=media_items,
            total_files=total_files,
            handoff_issues=request.handoff_issues,
            sink=sink,
        )

        sink.progress_step("finalizing_result", "正在整理学习反馈结果", progress=0.95)
        payload = attach_legacy_skills_metadata(payload if isinstance(payload, dict) else {}, skills)
        return AgentResult(
            id=f"result_{uuid.uuid4().hex}",
            job_id=request.job_id,
            agent="coach",
            status="succeeded",
            summary=str(payload.get("summary", "")),
            content=visible_text,
            payload=payload,
        )

    def _create_model_client(self, legacy: Any) -> Any:
        if self.model_client is not None:
            return self.model_client
        if self.model_client_factory is not None:
            return self.model_client_factory(legacy)
        try:
            return legacy.create_anthropic_client(source_cli="photo_v2.py")
        except SystemExit as exc:
            raise RuntimeError("Anthropic credentials are not configured for CoachAgentService.") from exc


_COACH_AGENT_SERVICE: CoachAgentService | None = None


def get_coach_agent_service() -> CoachAgentService:
    global _COACH_AGENT_SERVICE
    if _COACH_AGENT_SERVICE is None:
        _COACH_AGENT_SERVICE = CoachAgentService()
    return _COACH_AGENT_SERVICE
