from __future__ import annotations

import importlib
import json
import uuid
from typing import Any, Callable

#from fastapi.concurrency import run_in_threadpool

from starlette.concurrency import run_in_threadpool

from app.agents.base import LegacyAgentService
from app.agents.legacy_skills import attach_legacy_skills_metadata, load_optional_legacy_skills
from app.orchestration.event_bus import AgentEventSink
from app.schemas.agent import PlanAgentRequest
from app.schemas.result import AgentResult
from app.storage.media_store import MediaStore, get_media_store


class PlanAgentService(LegacyAgentService):
    def __init__(
        self,
        *,
        media_store: MediaStore | None = None,
        model_client: Any | None = None,
        model_client_factory: Callable[[Any], Any] | None = None,
    ) -> None:
        super().__init__(
            agent_name="plan",
            module_name="photo_v3",
            required_callables=("run_planning_turn",),
        )
        self.media_store = media_store or get_media_store()
        self.model_client = model_client
        self.model_client_factory = model_client_factory

    async def run(self, request: PlanAgentRequest, sink: AgentEventSink) -> AgentResult:
        return await run_in_threadpool(self._run_sync, request, sink)

    def _run_sync(self, request: PlanAgentRequest, sink: AgentEventSink) -> AgentResult:
        if self._requires_clarification_before_model(request):
            return self._clarification_result(request, sink)

        legacy = self.load_legacy_module()

        sink.progress_step("loading_profile", "正在读取拍摄规划上下文", progress=0.1)
        profile = legacy.load_profile()
        skills = load_optional_legacy_skills(
            agent="plan",
            loader=legacy.load_planning_skills_knowledge,
            sink=sink,
        )
        session_state = {
            **getattr(legacy, "DEFAULT_PLANNING_SESSION_STATE", {}),
            **request.context.get("planning_session_state", {}),
        }

        sink.progress_step("preparing_reference_media", "正在准备拍摄规划参考图", progress=0.22)
        media_items: list[dict] = []
        total_files = 0
        if request.reference_media_ids:
            media_items, total_files, _ = self.media_store.prepare_legacy_media_items(
                request.reference_media_ids,
                legacy.prepare_media_items,
                sink=sink,
            )

        sink.progress_step("calling_model", "正在运行拍摄规划 Agent", progress=0.5)
        user_text = self._build_planning_user_text(request)
        visible_text, payload, brief = legacy.run_planning_turn(
            client=self._create_model_client(),
            profile=profile,
            session_state=session_state,
            skills_knowledge=skills.text,
            messages=[],
            user_text=user_text,
            media_items=media_items,
            total_files=total_files,
            sink=sink,
        )

        payload = payload if isinstance(payload, dict) else {}
        payload = self._with_planning_metadata(
            payload=payload,
            brief=brief if isinstance(brief, dict) else {},
            legacy=legacy,
            session_state=session_state,
            user_text=user_text,
            media_items=media_items,
        )
        payload = attach_legacy_skills_metadata(payload, skills)

        sink.progress_step("finalizing_result", "正在整理拍摄规划结果", progress=0.95)
        return AgentResult(
            id=f"result_{uuid.uuid4().hex}",
            job_id=request.job_id,
            agent="plan",
            status="succeeded",
            summary=str(payload.get("summary", "")),
            content=visible_text,
            payload=payload,
        )

    def _create_model_client(self) -> Any:
        if self.model_client is not None:
            return self.model_client
        if self.model_client_factory is not None:
            return self.model_client_factory(self)
        runtime = importlib.import_module("photo_runtime")
        try:
            return runtime.create_anthropic_client(source_cli="photo_v3.py")
        except SystemExit as exc:
            raise RuntimeError("Anthropic credentials are not configured for PlanAgentService.") from exc

    def _requires_clarification_before_model(self, request: PlanAgentRequest) -> bool:
        return not any(
            [
                request.user_text.strip(),
                request.city,
                request.target_location,
                request.shoot_date,
                request.time_window,
                request.subject,
                request.style_keywords,
                request.gear,
                request.reference_media_ids,
            ]
        )

    def _clarification_result(
        self,
        request: PlanAgentRequest,
        sink: AgentEventSink,
    ) -> AgentResult:
        question = "请补充这次想去哪里拍、什么时候拍，以及大致题材或风格。"
        sink.progress_step(
            "clarification_required",
            "需要补充拍摄规划信息",
            progress=1.0,
        )
        payload = {
            "task_mode": "clarify",
            "needs_clarification": True,
            "missing_fields": ["city_or_location", "shoot_date_or_time_window", "subject_or_style"],
            "selection_prompt": question,
            "visible_response": question,
            "style_handoff": "",
        }
        return AgentResult(
            id=f"result_{uuid.uuid4().hex}",
            job_id=request.job_id,
            agent="plan",
            status="succeeded",
            summary="需要补充拍摄规划信息",
            content=question,
            payload=payload,
        )

    def _build_planning_user_text(self, request: PlanAgentRequest) -> str:
        lines = []
        if request.user_text.strip():
            lines.extend(
                [
                    "【用户原始诉求】",
                    request.user_text.strip(),
                    "",
                    "【理解原则】",
                    "1. 用户原始诉求和“其他要求”优先级最高，不能被示例城市、默认景点、默认午饭/晚饭或上一次规划上下文覆盖。",
                    "2. 用户提到的时间范围、必须去/必须避开的地点、餐饮、美食、交通、预算、路线节奏都属于硬约束。",
                    "3. 落日、日出、蓝调、夜景、黄金时刻、剪影是拍摄目标，不是地点名称。",
                    "4. 信息不足时可以补全建议；信息明确时必须服从用户表达。",
                ]
            )
        field_lines = [
            ("城市", request.city),
            ("目标地点", request.target_location),
            ("拍摄日期", request.shoot_date),
            ("时间窗口", request.time_window),
            ("题材", request.subject),
            ("预算", request.budget),
        ]
        for label, value in field_lines:
            if value:
                lines.append(f"{label}：{value}")
        if request.style_keywords:
            lines.append(f"风格关键词：{'、'.join(request.style_keywords)}")
        if request.gear:
            lines.append(f"器材：{'、'.join(request.gear)}")
        if request.constraints:
            lines.append(f"限制条件：{'、'.join(request.constraints)}")
        hard_constraints = request.context.get("hard_constraints")
        if isinstance(hard_constraints, dict) and hard_constraints:
            lines.append("硬约束 JSON：")
            lines.append(json.dumps(hard_constraints, ensure_ascii=False, indent=2))
        output_requirements = request.context.get("output_requirements")
        if isinstance(output_requirements, dict) and output_requirements:
            lines.append("输出要求 JSON：")
            lines.append(json.dumps(output_requirements, ensure_ascii=False, indent=2))
        raw_requirements = request.context.get("requirements")
        if raw_requirements and str(raw_requirements).strip():
            lines.append(f"其他要求原文：{str(raw_requirements).strip()}")
        if request.reference_media_ids:
            lines.append("请结合参考图风格规划下一次拍摄。")
        return "\n".join(lines).strip()

    def _with_planning_metadata(
        self,
        *,
        payload: dict,
        brief: dict,
        legacy: Any,
        session_state: dict,
        user_text: str,
        media_items: list[dict],
    ) -> dict:
        enriched = dict(payload)
        plans = enriched.get("plans", [])
        if isinstance(plans, list) and plans:
            first_plan = plans[0] if isinstance(plans[0], dict) else {}
            enriched.setdefault("style_handoff", str(first_plan.get("style_handoff", "")).strip())
        else:
            enriched.setdefault("style_handoff", "")
        enriched["brief"] = brief
        try:
            enriched["planning_session_state"] = legacy.update_planning_session_state(
                session_state,
                user_text,
                brief,
                enriched,
                {"paths": [item.get("path", "") for item in media_items]} if media_items else None,
            )
        except Exception:
            enriched["planning_session_state"] = session_state
        return enriched


_PLAN_AGENT_SERVICE: PlanAgentService | None = None


def get_plan_agent_service() -> PlanAgentService:
    global _PLAN_AGENT_SERVICE
    if _PLAN_AGENT_SERVICE is None:
        _PLAN_AGENT_SERVICE = PlanAgentService()
    return _PLAN_AGENT_SERVICE
