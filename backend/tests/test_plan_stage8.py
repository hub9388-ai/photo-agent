from __future__ import annotations

import asyncio

from fastapi.testclient import TestClient

from app.agents.plan_agent import PlanAgentService
from app.main import app
from app.orchestration.event_bus import AgentEventSink, EventBus, get_event_bus
from app.schemas.agent import PlanAgentRequest
from app.storage.database import SQLiteDatabase
from app.storage.event_store import EventStore, get_event_store
from app.storage.job_store import get_job_store
from app.storage.media_store import get_media_store
from app.storage.result_store import get_result_store
from backend.tests.test_job_system import (
    FakeAgentService,
    FakeMediaStore,
    install_overrides,
    wait_for_job_status,
)


def run_plan_service(service: PlanAgentService, request: PlanAgentRequest, event_store: EventStore):
    async def _run():
        event_bus = EventBus()
        sink = AgentEventSink(
            job_id=request.job_id,
            agent="plan",
            event_store=event_store,
            event_bus=event_bus,
            loop=asyncio.get_running_loop(),
        )
        return await service.run(request, sink)

    return asyncio.run(_run())


def test_plan_service_returns_clarification_without_model_call(tmp_path) -> None:
    event_store = EventStore(SQLiteDatabase(tmp_path / "app.sqlite3"))
    service = PlanAgentService(model_client=object())

    result = run_plan_service(
        service,
        PlanAgentRequest(job_id="job_001", user_text=""),
        event_store,
    )

    assert result.status == "succeeded"
    assert result.agent == "plan"
    assert result.payload["needs_clarification"] is True
    assert "去哪里拍" in result.content
    events = event_store.list_by_job("job_001")
    assert events[-1].type == "agent.progress"
    assert events[-1].payload["step"] == "clarification_required"


def test_plan_service_forwards_raw_requirements_and_hard_constraints(tmp_path, monkeypatch) -> None:
    import photo_v3

    event_store = EventStore(SQLiteDatabase(tmp_path / "app.sqlite3"))
    captured: dict[str, str] = {}

    monkeypatch.setattr(photo_v3, "load_profile", lambda: {})
    monkeypatch.setattr(photo_v3, "load_planning_skills_knowledge", lambda: "")

    def fake_run_planning_turn(**kwargs):
        captured["user_text"] = kwargs["user_text"]
        return (
            "visible",
            {"summary": "summary", "plans": [{"id": "A", "style_handoff": "warm"}]},
            {"city": "威海"},
        )

    monkeypatch.setattr(photo_v3, "run_planning_turn", fake_run_planning_turn)
    monkeypatch.setattr(
        photo_v3,
        "update_planning_session_state",
        lambda session_state, user_text, brief, payload, media_request=None: session_state,
    )

    result = run_plan_service(
        PlanAgentService(model_client=object()),
        PlanAgentRequest(
            job_id="job_001",
            user_text="从上午十点到晚上8点游玩威海，并中午晚上品尝当地美食和海鲜，并且拍摄海边的落日",
            city="威海",
            shoot_date="2026-05-01",
            subject="风光人像",
            context={
                "requirements": "从上午十点到晚上8点游玩威海，并中午晚上品尝当地美食和海鲜，并且拍摄海边的落日",
                "hard_constraints": {
                    "user_requirements_first": True,
                    "start_time": "10:00",
                    "end_time": "20:00",
                    "shooting_goals": ["落日/黄金时刻"],
                    "required_meals": {
                        "lunch": True,
                        "lunch_time": "12:00",
                        "dinner": True,
                        "dinner_time": "18:30",
                    },
                },
                "output_requirements": {
                    "include_transfer_nodes": True,
                    "include_local_food_area_dish_budget": True,
                },
            },
            constraints=["其他要求优先：从上午十点到晚上8点游玩威海"],
        ),
        event_store,
    )

    assert result.status == "succeeded"
    user_text = captured["user_text"]
    assert "用户原始诉求" in user_text
    assert "硬约束 JSON" in user_text
    assert '"start_time": "10:00"' in user_text
    assert '"end_time": "20:00"' in user_text
    assert "输出要求 JSON" in user_text
    assert "落日、日出、蓝调、夜景、黄金时刻、剪影是拍摄目标，不是地点名称" in user_text


def test_plan_run_api_creates_explicit_trip_planning_job(tmp_path) -> None:
    plan_service = FakeAgentService("plan", payload={"style_handoff": "暖色夕阳人像"})
    job_store, _, _, _, _ = install_overrides(
        tmp_path / "app.sqlite3",
        plan_agent_service=plan_service,
    )
    app.dependency_overrides[get_media_store] = lambda: FakeMediaStore({"media_ref_001"})

    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/agents/plan/run",
                json={
                    "user_goal": "下周去杭州拍人像，帮我规划路线和机位。",
                    "city": "杭州",
                    "shoot_date": "2026-05-02",
                    "subject": "人像",
                    "style_keywords": ["暖色", "湖边"],
                    "gear": ["85mm"],
                    "reference_media_ids": ["media_ref_001"],
                },
            )
            assert response.status_code == 202
            payload = response.json()
            assert payload["status"] == "queued"
            assert payload["agent"] == "plan"

            job_id = payload["jobId"]
            job = wait_for_job_status(client, job_id, "completed")
            assert job["type"] == "trip_planning"
            assert job["agents"] == ["plan"]
            assert job["mediaIds"] == ["media_ref_001"]

            results = client.get(f"/api/jobs/{job_id}/results").json()
            assert results["completedAgents"] == ["plan"]
            assert results["results"][0]["structuredPayload"]["style_handoff"] == "暖色夕阳人像"

        assert len(plan_service.requests) == 1
        plan_request = plan_service.requests[0]
        assert plan_request.agent == "plan"
        assert plan_request.city == "杭州"
        assert plan_request.shoot_date == "2026-05-02"
        assert plan_request.reference_media_ids == ["media_ref_001"]
        assert job_store.get(payload["jobId"]).type == "trip_planning"
    finally:
        app.dependency_overrides.clear()


def test_plan_run_api_is_friendly_wrapper_over_job_system(tmp_path) -> None:
    plan_service = FakeAgentService("plan")
    install_overrides(
        tmp_path / "app.sqlite3",
        plan_agent_service=plan_service,
    )

    try:
        with TestClient(app) as client:
            wrapper_response = client.post(
                "/api/agents/plan/run",
                json={
                    "user_goal": "明天去苏州拍园林，帮我安排路线。",
                    "city": "苏州",
                    "shoot_date": "2026-04-27",
                    "subject": "园林",
                },
            )
            assert wrapper_response.status_code == 202
            wrapper_payload = wrapper_response.json()
            wrapper_job_id = wrapper_payload["jobId"]
            assert wrapper_payload["eventsUrl"] == f"/api/jobs/{wrapper_job_id}/events"
            assert wrapper_payload["resultsUrl"] == f"/api/jobs/{wrapper_job_id}/results"

            wrapper_job = wait_for_job_status(client, wrapper_job_id, "completed")
            assert wrapper_job["type"] == "trip_planning"
            assert wrapper_job["agents"] == ["plan"]

            generic_response = client.post(
                "/api/jobs",
                json={
                    "type": "trip_planning",
                    "agents": ["plan"],
                    "user_goal": "明天去苏州拍园林，帮我安排路线。",
                    "context": {
                        "city": "苏州",
                        "shoot_date": "2026-04-27",
                        "subject": "园林",
                    },
                },
            )
            assert generic_response.status_code == 202
            generic_job_id = generic_response.json()["jobId"]
            generic_job = wait_for_job_status(client, generic_job_id, "completed")
            assert generic_job["type"] == "trip_planning"
            assert generic_job["agents"] == ["plan"]

        assert len(plan_service.requests) == 2
    finally:
        app.dependency_overrides.clear()


def test_plan_run_rejects_missing_reference_media_id(tmp_path) -> None:
    install_overrides(
        tmp_path / "app.sqlite3",
        plan_agent_service=FakeAgentService("plan"),
    )
    app.dependency_overrides[get_media_store] = lambda: FakeMediaStore({"existing_media"})

    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/agents/plan/run",
                json={
                    "user_goal": "基于参考图规划下一次拍摄。",
                    "reference_media_ids": ["missing_media"],
                },
            )

        assert response.status_code == 400
        assert response.json()["errorCode"] == "VALIDATION_ERROR"
        assert response.json()["detail"]["field"] == "reference_media_ids"
    finally:
        app.dependency_overrides.clear()


def test_photo_review_job_does_not_trigger_plan_by_default(tmp_path) -> None:
    plan_service = FakeAgentService("plan")
    install_overrides(
        tmp_path / "app.sqlite3",
        post_agent_service=FakeAgentService("post"),
        coach_agent_service=FakeAgentService("coach"),
        plan_agent_service=plan_service,
    )
    app.dependency_overrides[get_media_store] = lambda: FakeMediaStore({"media_001"})

    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/jobs",
                json={
                    "type": "photo_review",
                    "media_ids": ["media_001"],
                    "agents": ["post", "coach"],
                    "user_goal": "帮我看看这张照片。",
                },
            )
            assert response.status_code == 202
            wait_for_job_status(client, response.json()["jobId"], "completed")

        assert plan_service.requests == []
    finally:
        app.dependency_overrides.clear()
