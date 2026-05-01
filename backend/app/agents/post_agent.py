from __future__ import annotations

import uuid
from typing import Any, Callable

from starlette.concurrency import run_in_threadpool

from app.agents.base import LegacyAgentService
from app.agents.legacy_skills import attach_legacy_skills_metadata, load_optional_legacy_skills
from app.orchestration.event_bus import AgentEventSink
from app.schemas.agent import PostAgentRequest
from app.schemas.result import AgentResult
from app.storage.media_store import MediaStore, get_media_store


class PostAgentService(LegacyAgentService):
    def __init__(
        self,
        *,
        media_store: MediaStore | None = None,
        model_client: Any | None = None,
        model_client_factory: Callable[[Any], Any] | None = None,
    ) -> None:
        super().__init__(
            agent_name="post",
            module_name="photo_v1",
            required_callables=("analyze_photo_streaming", "chat_streaming"),
        )
        self.media_store = media_store or get_media_store()
        self.model_client = model_client
        self.model_client_factory = model_client_factory

    async def run(self, request: PostAgentRequest, sink: AgentEventSink) -> AgentResult:
        return await run_in_threadpool(self._run_sync, request, sink)

    def _run_sync(self, request: PostAgentRequest, sink: AgentEventSink) -> AgentResult:
        legacy = self.load_legacy_module()

        sink.progress_step("loading_profile", "正在读取后期分析上下文", progress=0.1)
        profile = legacy.load_profile()
        skills = load_optional_legacy_skills(
            agent="post",
            loader=legacy.load_skills_knowledge,
            sink=sink,
        )
        system = legacy.build_system_prompt(profile, skills.text)

        sink.progress_step("preparing_media", "正在准备后期分析预览图", progress=0.25)
        media_items, total_files, detected_batch = self.media_store.prepare_legacy_media_items(
            request.media_ids,
            legacy.prepare_media_items,
            sink=sink,
        )

        sink.progress_step("calling_model", "正在运行后期辅助 Agent", progress=0.55)
        visible_text, payload = legacy.analyze_photo_streaming(
            client=self._create_model_client(legacy),
            system=system,
            messages=[],
            media_items=media_items,
            user_text=request.user_text,
            total_files=total_files,
            is_batch=request.is_batch or detected_batch,
            sink=sink,
        )

        sink.progress_step("finalizing_result", "正在整理后期建议结果", progress=0.95)
        payload = attach_legacy_skills_metadata(payload if isinstance(payload, dict) else {}, skills)
        return AgentResult(
            id=f"result_{uuid.uuid4().hex}",
            job_id=request.job_id,
            agent="post",
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
            return legacy.create_anthropic_client(source_cli="photo_v1.py")
        except SystemExit as exc:
            raise RuntimeError("Anthropic credentials are not configured for PostAgentService.") from exc


_POST_AGENT_SERVICE: PostAgentService | None = None


def get_post_agent_service() -> PostAgentService:
    global _POST_AGENT_SERVICE
    if _POST_AGENT_SERVICE is None:
        _POST_AGENT_SERVICE = PostAgentService()
    return _POST_AGENT_SERVICE
