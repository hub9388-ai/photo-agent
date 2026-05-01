from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field

from app.agents.base import BaseAgent
from app.agents.asset_agent import get_asset_agent_service
from app.agents.coach_agent import get_coach_agent_service
from app.agents.plan_agent import get_plan_agent_service
from app.agents.post_agent import get_post_agent_service
from app.orchestration.event_bus import AgentEventSink, EventBus, get_event_bus
from app.schemas.agent import AssetAgentRequest, CoachAgentRequest, PlanAgentRequest, PostAgentRequest
from app.schemas.common import AgentName
from app.schemas.event import AgentEvent
from app.schemas.job import AgentJob
from app.schemas.result import AgentResult
from app.storage.event_store import EventStore, get_event_store
from app.storage.job_store import JobStore, get_job_store
from app.storage.result_store import ResultStore, get_result_store


@dataclass
class JobRunner:
    job_store: JobStore
    event_store: EventStore
    result_store: ResultStore
    event_bus: EventBus
    post_agent_service: BaseAgent | None = None
    coach_agent_service: BaseAgent | None = None
    plan_agent_service: BaseAgent | None = None
    asset_agent_service: BaseAgent | None = None
    _tasks: dict[str, asyncio.Task[None]] = field(default_factory=dict)

    def start(self, job_id: str) -> None:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            asyncio.run(self.run_job(job_id))
            return

        task = loop.create_task(self.run_job(job_id))
        self._tasks[job_id] = task
        task.add_done_callback(lambda _task: self._tasks.pop(job_id, None))

    def start_agent_retry(self, job_id: str, agent: AgentName) -> None:
        task_id = f"{job_id}:{agent}:retry"
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            asyncio.run(self.run_agent_retry(job_id, agent))
            return

        task = loop.create_task(self.run_agent_retry(job_id, agent))
        self._tasks[task_id] = task
        task.add_done_callback(lambda _task: self._tasks.pop(task_id, None))

    async def run_job(self, job_id: str) -> None:
        job = self.job_store.get(job_id)
        if job is None:
            return

        try:
            self.job_store.update_status(job_id, "running")
            await self.emit(job_id=job_id, agent=None, type="job.started", message="任务开始")

            loop = asyncio.get_running_loop()
            tasks = [
                asyncio.create_task(self._run_agent(job, agent, loop))
                for agent in job.agents
            ]
            gathered = await asyncio.gather(*tasks, return_exceptions=True)

            results = [item for item in gathered if isinstance(item, AgentResult)]
            unexpected_errors = [item for item in gathered if isinstance(item, Exception)]
            succeeded = sum(1 for result in results if result.status == "succeeded")
            failed = sum(1 for result in results if result.status != "succeeded")
            failed += len(unexpected_errors)

            if failed and succeeded == 0:
                final_status = "failed"
                final_event_type = "job.failed"
                final_message = "任务失败"
            elif failed:
                final_status = "partial_completed"
                final_event_type = "job.partial_completed"
                final_message = "任务部分完成"
            else:
                final_status = "completed"
                final_event_type = "job.completed"
                final_message = "任务完成"

            self.job_store.update_status(job_id, final_status)
            await self.emit(
                job_id=job_id,
                agent=None,
                type=final_event_type,
                message=final_message,
                payload={
                    "succeeded": succeeded,
                    "failed": failed,
                    "total": len(job.agents),
                },
            )
        except Exception as exc:  # pragma: no cover - defensive runner guard
            self.job_store.update_status(job_id, "failed")
            await self.emit(
                job_id=job_id,
                agent=None,
                type="job.failed",
                message="任务失败",
                payload={"error": str(exc)},
            )

    async def run_agent_retry(self, job_id: str, agent: AgentName) -> None:
        job = self.job_store.get(job_id)
        if job is None or agent not in job.agents:
            return

        try:
            self.job_store.update_status(job_id, "running")
            await self.emit(
                job_id=job_id,
                agent=None,
                type="job.started",
                message="任务重试开始",
                payload={"retryAgent": agent},
            )
            loop = asyncio.get_running_loop()
            await self._run_agent(job, agent, loop)
            await self._finalize_job_from_latest_results(job)
        except Exception as exc:  # pragma: no cover - defensive runner guard
            self.job_store.update_status(job_id, "failed")
            await self.emit(
                job_id=job_id,
                agent=None,
                type="job.failed",
                message="任务重试失败",
                payload={"retryAgent": agent, "error": str(exc)},
            )

    async def _run_agent(
        self,
        job: AgentJob,
        agent: AgentName,
        loop: asyncio.AbstractEventLoop,
    ) -> AgentResult:
        if agent == "post":
            return await self._run_service_agent(
                job,
                agent,
                self.post_agent_service or get_post_agent_service(),
                loop,
            )
        if agent == "coach":
            return await self._run_service_agent(
                job,
                agent,
                self.coach_agent_service or get_coach_agent_service(),
                loop,
            )
        if agent == "asset":
            return await self._run_service_agent(
                job,
                agent,
                self.asset_agent_service or get_asset_agent_service(),
                loop,
            )
        if agent == "plan":
            return await self._run_service_agent(
                job,
                agent,
                self.plan_agent_service or get_plan_agent_service(),
                loop,
            )
        return await self._run_placeholder_agent(job.id, agent, loop)

    async def _run_service_agent(
        self,
        job: AgentJob,
        agent: AgentName,
        service: BaseAgent,
        loop: asyncio.AbstractEventLoop,
    ) -> AgentResult:
        sink = self._agent_sink(job.id, agent, loop)
        await sink.emit_async(
            "agent.started",
            message=f"{agent} Agent 已开始",
            payload={"agent": agent},
        )
        try:
            request = self._build_agent_request(job, agent)
            result = await service.run(request, sink)
            self.result_store.save(result)
            await sink.emit_async(
                "agent.result",
                message=f"{agent} Agent 已完成",
                payload={"resultId": result.id, "status": result.status},
            )
            return result
        except Exception as exc:
            result = AgentResult(
                id=f"result_{uuid.uuid4().hex}",
                job_id=job.id,
                agent=agent,
                status="failed",
                summary=f"{agent} Agent failed.",
                content="",
                payload={"errorType": exc.__class__.__name__},
                error=str(exc),
            )
            self.result_store.save(result)
            await sink.emit_async(
                "agent.error",
                message=f"{agent} Agent 运行失败",
                payload={"error": str(exc), "errorType": exc.__class__.__name__},
            )
            await sink.emit_async(
                "agent.result",
                message=f"{agent} Agent 失败结果已保存",
                payload={"resultId": result.id, "status": result.status},
            )
            return result

    def _build_agent_request(
        self,
        job: AgentJob,
        agent: AgentName,
    ) -> PostAgentRequest | CoachAgentRequest | PlanAgentRequest | AssetAgentRequest:
        common = {
            "job_id": job.id,
            "user_text": job.user_goal,
            "trigger": job.trigger,
            "context": job.context,
        }
        if agent == "post":
            return PostAgentRequest(
                **common,
                media_ids=job.media_ids,
                is_batch=len(job.media_ids) > 1,
            )
        if agent == "coach":
            handoff_issues = job.context.get("handoff_issues", [])
            return CoachAgentRequest(
                **common,
                media_ids=job.media_ids,
                handoff_issues=[
                    str(item)
                    for item in handoff_issues
                    if str(item).strip()
                ],
            )
        if agent == "asset":
            return AssetAgentRequest(
                **common,
                project_id=str(job.context.get("project_id") or job.context.get("projectId") or ""),
                project_root=str(job.context.get("project_root") or job.context.get("projectRoot") or ""),
                media_ids=job.media_ids,
                task_mode=str(job.context.get("asset_task_mode") or "import_project"),
                search_query=str(job.context.get("search_query") or job.context.get("searchQuery") or ""),
            )
        if agent == "plan":
            return PlanAgentRequest(
                **common,
                project_id=str(job.context.get("project_id") or job.context.get("projectId") or "") or None,
                city=_optional_str(job.context.get("city")),
                target_location=_optional_str(job.context.get("target_location") or job.context.get("targetLocation")),
                shoot_date=_optional_str(job.context.get("shoot_date") or job.context.get("shootDate")),
                time_window=_optional_str(job.context.get("time_window") or job.context.get("timeWindow")),
                subject=_optional_str(job.context.get("subject")),
                budget=_optional_str(job.context.get("budget")),
                constraints=_string_list(job.context.get("constraints")),
                style_keywords=_string_list(job.context.get("style_keywords") or job.context.get("styleKeywords")),
                gear=_string_list(job.context.get("gear")),
                reference_media_ids=_string_list(
                    job.context.get("reference_media_ids") or job.context.get("referenceMediaIds")
                ),
            )
        raise ValueError(f"Unsupported service agent: {agent}")

    async def _run_placeholder_agent(
        self,
        job_id: str,
        agent: AgentName,
        loop: asyncio.AbstractEventLoop,
    ) -> AgentResult:
        sink = self._agent_sink(job_id, agent, loop)
        await sink.emit_async(
            "agent.started",
            message=f"{agent} Agent 已进入队列",
        )
        await sink.emit_async(
            "agent.progress",
            message="等待后续阶段接入真实 Agent",
            payload={"step": "contract_placeholder", "progress": 1.0},
        )

        result = AgentResult(
            id=f"result_{uuid.uuid4().hex}",
            job_id=job_id,
            agent=agent,
            status="skipped",
            summary="Agent execution is not implemented in stage 5.",
            content="阶段 5 只接入 post + coach，其他 Agent 的真实执行将在后续阶段接入。",
            payload={"stage": 5, "reason": "agent_service_not_connected"},
        )
        self.result_store.save(result)
        await sink.emit_async(
            "agent.result",
            message="Agent 占位结果已保存",
            payload={"resultId": result.id, "status": result.status},
        )
        return result

    async def _finalize_job_from_latest_results(self, job: AgentJob) -> None:
        latest_results = self.result_store.list_latest_by_job(job.id)
        result_by_agent = {result.agent: result for result in latest_results}
        succeeded = sum(
            1
            for agent in job.agents
            if result_by_agent.get(agent) and result_by_agent[agent].status == "succeeded"
        )
        failed = sum(
            1
            for agent in job.agents
            if result_by_agent.get(agent) and result_by_agent[agent].status != "succeeded"
        )
        pending = len([agent for agent in job.agents if agent not in result_by_agent])

        if failed and succeeded == 0:
            final_status = "failed"
            final_event_type = "job.failed"
            final_message = "任务失败"
        elif failed or pending:
            final_status = "partial_completed"
            final_event_type = "job.partial_completed"
            final_message = "任务部分完成"
        else:
            final_status = "completed"
            final_event_type = "job.completed"
            final_message = "任务完成"

        self.job_store.update_status(job.id, final_status)
        await self.emit(
            job_id=job.id,
            agent=None,
            type=final_event_type,
            message=final_message,
            payload={
                "succeeded": succeeded,
                "failed": failed,
                "pending": pending,
                "total": len(job.agents),
            },
        )

    async def emit(
        self,
        *,
        job_id: str,
        agent: AgentName | None,
        type: str,
        message: str | None = None,
        payload: dict | None = None,
        persist: bool = True,
    ) -> AgentEvent:
        event = AgentEvent(
            id=f"evt_{uuid.uuid4().hex}",
            job_id=job_id,
            seq=self.event_store.next_seq(job_id),
            agent=agent,
            type=type,
            message=message,
            payload=payload or {},
            persist=persist,
        )
        self.event_store.append_if_persisted(event)
        await self.event_bus.publish(event)
        return event

    def _agent_sink(
        self,
        job_id: str,
        agent: AgentName,
        loop: asyncio.AbstractEventLoop,
    ) -> AgentEventSink:
        return AgentEventSink(
            job_id=job_id,
            agent=agent,
            event_store=self.event_store,
            event_bus=self.event_bus,
            loop=loop,
        )


_JOB_RUNNER: JobRunner | None = None


def get_job_runner() -> JobRunner:
    global _JOB_RUNNER
    if _JOB_RUNNER is None:
        _JOB_RUNNER = JobRunner(
            job_store=get_job_store(),
            event_store=get_event_store(),
            result_store=get_result_store(),
            event_bus=get_event_bus(),
            post_agent_service=get_post_agent_service(),
            coach_agent_service=get_coach_agent_service(),
            plan_agent_service=get_plan_agent_service(),
            asset_agent_service=get_asset_agent_service(),
        )
    return _JOB_RUNNER


def _optional_str(value: object) -> str | None:
    text = str(value or "").strip()
    return text or None


def _string_list(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value or "").strip()
    return [text] if text else []
