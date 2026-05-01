from __future__ import annotations

import asyncio
import json
import time
import uuid
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app
from app.orchestration.event_bus import AgentEventSink, EventBus, get_event_bus
from app.orchestration.job_runner import JobRunner, get_job_runner
from app.schemas.agent import AgentRequest
from app.schemas.common import AgentName
from app.schemas.event import AgentEvent
from app.schemas.result import AgentResult
from app.storage.database import SQLiteDatabase
from app.storage.event_store import EventStore, get_event_store
from app.storage.job_store import JobStore, get_job_store
from app.storage.media_store import get_media_store
from app.storage.result_store import ResultStore, get_result_store


class FakeMediaStore:
    def __init__(self, existing_media_ids: set[str] | None = None) -> None:
        self.existing_media_ids = existing_media_ids

    def get(self, media_id: str):
        if self.existing_media_ids is not None and media_id not in self.existing_media_ids:
            from app.storage.media_store import MediaNotFoundError

            raise MediaNotFoundError(f"Media not found: {media_id}")
        return object()


class FakeAgentService:
    def __init__(
        self,
        agent: AgentName,
        *,
        should_fail: bool = False,
        delay_seconds: float = 0,
        payload: dict | None = None,
    ) -> None:
        self.agent = agent
        self.should_fail = should_fail
        self.delay_seconds = delay_seconds
        self.payload = payload or {"agent": agent}
        self.requests: list[AgentRequest] = []

    async def run(self, request: AgentRequest, sink: AgentEventSink) -> AgentResult:
        self.requests.append(request)
        await sink.emit_async(
            "agent.progress",
            message=f"{self.agent} mock progress",
            payload={"step": f"{self.agent}_mock", "progress": 0.5},
        )
        sink.write(f"{self.agent} delta", end="")
        if self.delay_seconds:
            await asyncio.sleep(self.delay_seconds)
        if self.should_fail:
            raise RuntimeError(f"{self.agent} failed")
        return AgentResult(
            id=f"result_{uuid.uuid4().hex}",
            job_id=request.job_id,
            agent=self.agent,
            status="succeeded",
            summary=f"{self.agent} summary",
            content=f"{self.agent} visible text",
            payload=self.payload,
        )


def build_test_services(
    db_path: Path,
    *,
    post_agent_service: FakeAgentService | None = None,
    coach_agent_service: FakeAgentService | None = None,
    plan_agent_service: FakeAgentService | None = None,
    asset_agent_service: FakeAgentService | None = None,
):
    database = SQLiteDatabase(db_path)
    job_store = JobStore(database)
    event_store = EventStore(database)
    result_store = ResultStore(database)
    event_bus = EventBus()
    job_runner = JobRunner(
        job_store=job_store,
        event_store=event_store,
        result_store=result_store,
        event_bus=event_bus,
        post_agent_service=post_agent_service or FakeAgentService("post"),
        coach_agent_service=coach_agent_service or FakeAgentService("coach"),
        plan_agent_service=plan_agent_service or FakeAgentService("plan"),
        asset_agent_service=asset_agent_service or FakeAgentService("asset"),
    )
    return job_store, event_store, result_store, event_bus, job_runner


def install_overrides(
    db_path: Path,
    *,
    post_agent_service: FakeAgentService | None = None,
    coach_agent_service: FakeAgentService | None = None,
    plan_agent_service: FakeAgentService | None = None,
    asset_agent_service: FakeAgentService | None = None,
):
    job_store, event_store, result_store, event_bus, job_runner = build_test_services(
        db_path,
        post_agent_service=post_agent_service,
        coach_agent_service=coach_agent_service,
        plan_agent_service=plan_agent_service,
        asset_agent_service=asset_agent_service,
    )
    app.dependency_overrides[get_job_store] = lambda: job_store
    app.dependency_overrides[get_event_store] = lambda: event_store
    app.dependency_overrides[get_result_store] = lambda: result_store
    app.dependency_overrides[get_event_bus] = lambda: event_bus
    app.dependency_overrides[get_job_runner] = lambda: job_runner
    app.dependency_overrides[get_media_store] = lambda: FakeMediaStore()
    return job_store, event_store, result_store, event_bus, job_runner


def wait_for_job_status(client: TestClient, job_id: str, status: str) -> dict:
    deadline = time.time() + 3
    payload: dict = {}
    while time.time() < deadline:
        response = client.get(f"/api/jobs/{job_id}")
        response.raise_for_status()
        payload = response.json()
        if payload["status"] == status:
            return payload
        time.sleep(0.05)
    raise AssertionError(f"job {job_id} did not reach {status}: {payload}")


def test_create_job_runs_post_and_coach_services_in_parallel(tmp_path) -> None:
    post_service = FakeAgentService("post")
    coach_service = FakeAgentService("coach")
    _, event_store, _, _, _ = install_overrides(
        tmp_path / "app.sqlite3",
        post_agent_service=post_service,
        coach_agent_service=coach_service,
    )

    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/jobs",
                json={
                    "type": "photo_review",
                    "media_ids": ["media_001"],
                    "agents": ["post", "coach"],
                    "user_goal": "看看这张照片",
                },
            )
            assert response.status_code == 202
            create_payload = response.json()
            job_id = create_payload["jobId"]
            assert create_payload["eventsUrl"] == f"/api/jobs/{job_id}/events"
            assert create_payload["resultsUrl"] == f"/api/jobs/{job_id}/results"

            job = wait_for_job_status(client, job_id, "completed")
            results = client.get(f"/api/jobs/{job_id}/results").json()
    finally:
        app.dependency_overrides.clear()

    assert job["status"] == "completed"
    assert job["jobId"] == job_id
    assert results["jobId"] == job_id
    assert results["status"] == "completed"
    assert [result["agent"] for result in results["results"]] == ["post", "coach"]
    assert all(result["status"] == "succeeded" for result in results["results"])
    assert all("visibleText" in result for result in results["results"])
    assert all("structuredPayload" in result for result in results["results"])
    assert [request.agent for request in post_service.requests + coach_service.requests] == [
        "post",
        "coach",
    ]
    assert post_service.requests[0].media_ids == ["media_001"]
    assert coach_service.requests[0].media_ids == ["media_001"]

    events = event_store.list_by_job(job_id)
    assert [event.seq for event in events] == sorted(event.seq for event in events)
    assert events[-1].type == "job.completed"
    assert {"post", "coach"} <= {event.agent for event in events if event.agent}
    assert "agent.delta" not in [event.type for event in events]


def test_job_becomes_partial_completed_when_one_agent_fails(tmp_path) -> None:
    install_overrides(
        tmp_path / "app.sqlite3",
        post_agent_service=FakeAgentService("post"),
        coach_agent_service=FakeAgentService("coach", should_fail=True),
    )

    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/jobs",
                json={
                    "type": "photo_review",
                    "media_ids": ["media_001"],
                    "agents": ["post", "coach"],
                },
            )
            job_id = response.json()["jobId"]
            job = wait_for_job_status(client, job_id, "partial_completed")
            results = client.get(f"/api/jobs/{job_id}/results").json()
    finally:
        app.dependency_overrides.clear()

    assert job["status"] == "partial_completed"
    assert results["status"] == "partial_completed"
    assert {result["agent"]: result["status"] for result in results["results"]} == {
        "post": "succeeded",
        "coach": "failed",
    }
    assert results["completedAgents"] == ["post"]
    assert results["failedAgents"] == ["coach"]
    assert results["pendingAgents"] == []
    assert next(result for result in results["results"] if result["agent"] == "coach")["error"]


def test_retry_agent_updates_latest_result_and_job_status(tmp_path) -> None:
    coach_service = FakeAgentService("coach", should_fail=True)
    install_overrides(
        tmp_path / "app.sqlite3",
        post_agent_service=FakeAgentService("post"),
        coach_agent_service=coach_service,
    )

    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/jobs",
                json={
                    "type": "photo_review",
                    "media_ids": ["media_001"],
                    "agents": ["post", "coach"],
                },
            )
            job_id = response.json()["jobId"]
            wait_for_job_status(client, job_id, "partial_completed")

            coach_service.should_fail = False
            retry_response = client.post(f"/api/jobs/{job_id}/agents/coach/retry")
            assert retry_response.status_code == 202
            assert retry_response.json()["agent"] == "coach"

            wait_for_job_status(client, job_id, "completed")
            results = client.get(f"/api/jobs/{job_id}/results").json()
    finally:
        app.dependency_overrides.clear()

    assert len(results["results"]) == 2
    assert {result["agent"]: result["status"] for result in results["results"]} == {
        "post": "succeeded",
        "coach": "succeeded",
    }
    assert results["completedAgents"] == ["post", "coach"]
    assert results["failedAgents"] == []
    assert len(coach_service.requests) == 2


def test_list_jobs_can_filter_by_media_id(tmp_path) -> None:
    install_overrides(tmp_path / "app.sqlite3")

    try:
        with TestClient(app) as client:
            first = client.post(
                "/api/jobs",
                json={"type": "photo_review", "media_ids": ["media_001"], "agents": ["post"]},
            )
            second = client.post(
                "/api/jobs",
                json={"type": "photo_review", "media_ids": ["media_002"], "agents": ["coach"]},
            )
            wait_for_job_status(client, first.json()["jobId"], "completed")
            wait_for_job_status(client, second.json()["jobId"], "completed")

            response = client.get("/api/jobs?media_id=media_002")
    finally:
        app.dependency_overrides.clear()

    payload = response.json()
    assert payload["count"] == 1
    assert payload["jobs"][0]["mediaIds"] == ["media_002"]


def test_results_api_exposes_finished_agent_before_whole_job_completes(tmp_path) -> None:
    install_overrides(
        tmp_path / "app.sqlite3",
        post_agent_service=FakeAgentService("post"),
        coach_agent_service=FakeAgentService("coach", delay_seconds=0.4),
    )

    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/jobs",
                json={
                    "type": "photo_review",
                    "media_ids": ["media_001"],
                    "agents": ["post", "coach"],
                },
            )
            job_id = response.json()["jobId"]

            deadline = time.time() + 3
            partial_results: dict | None = None
            while time.time() < deadline:
                job = client.get(f"/api/jobs/{job_id}").json()
                results = client.get(f"/api/jobs/{job_id}/results").json()
                agents = [result["agent"] for result in results["results"]]
                if job["status"] == "running" and agents == ["post"]:
                    partial_results = results
                    break
                time.sleep(0.05)

            final_job = wait_for_job_status(client, job_id, "completed")
    finally:
        app.dependency_overrides.clear()

    assert partial_results is not None
    assert partial_results["status"] == "running"
    assert [result["agent"] for result in partial_results["results"]] == ["post"]
    assert final_job["status"] == "completed"


def test_job_becomes_failed_when_post_and_coach_both_fail(tmp_path) -> None:
    install_overrides(
        tmp_path / "app.sqlite3",
        post_agent_service=FakeAgentService("post", should_fail=True),
        coach_agent_service=FakeAgentService("coach", should_fail=True),
    )

    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/jobs",
                json={
                    "type": "photo_review",
                    "media_ids": ["media_001"],
                    "agents": ["post", "coach"],
                },
            )
            job_id = response.json()["jobId"]
            job = wait_for_job_status(client, job_id, "failed")
            results = client.get(f"/api/jobs/{job_id}/results").json()
    finally:
        app.dependency_overrides.clear()

    assert job["status"] == "failed"
    assert results["status"] == "failed"
    assert {result["agent"]: result["status"] for result in results["results"]} == {
        "post": "failed",
        "coach": "failed",
    }


def test_event_store_skips_delta_and_duplicate_progress(tmp_path) -> None:
    _, event_store, _, _, _ = build_test_services(tmp_path / "app.sqlite3")
    job_id = "job_001"

    created = AgentEvent(id="evt_001", job_id=job_id, seq=event_store.next_seq(job_id), agent=None, type="job.created")
    delta = AgentEvent(
        id="evt_002",
        job_id=job_id,
        seq=event_store.next_seq(job_id),
        agent="post",
        type="agent.delta",
        payload={"text": "chunk"},
    )
    progress = AgentEvent(
        id="evt_003",
        job_id=job_id,
        seq=event_store.next_seq(job_id),
        agent="post",
        type="agent.progress",
        payload={"step": "analyzing_color", "progress": 0.2},
    )
    duplicate_progress = AgentEvent(
        id="evt_004",
        job_id=job_id,
        seq=event_store.next_seq(job_id),
        agent="post",
        type="agent.progress",
        payload={"step": "analyzing_color", "progress": 0.7},
    )

    assert event_store.append_if_persisted(created) is True
    assert event_store.append_if_persisted(delta) is False
    assert event_store.append_if_persisted(progress) is True
    assert event_store.append_if_persisted(duplicate_progress) is False

    events = event_store.list_by_job(job_id)
    assert [event.type for event in events] == ["job.created", "agent.progress"]


def test_sse_replays_persisted_events(tmp_path) -> None:
    install_overrides(tmp_path / "app.sqlite3")

    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/jobs",
                json={"type": "photo_review", "media_ids": ["media_001"], "agents": ["post"]},
            )
            job_id = response.json()["jobId"]
            wait_for_job_status(client, job_id, "completed")

            seen_lines: list[str] = []
            data_payloads: list[dict] = []
            with client.stream("GET", f"/api/jobs/{job_id}/events?replay_only=true") as stream:
                for line in stream.iter_lines():
                    if line:
                        seen_lines.append(line)
                    if line.startswith("data: "):
                        data_payloads.append(json.loads(line.removeprefix("data: ")))
                    if line == "event: job.completed":
                        break
    finally:
        app.dependency_overrides.clear()

    assert "event: job.created" in seen_lines
    assert "event: agent.result" in seen_lines
    assert "event: job.completed" in seen_lines
    assert data_payloads
    assert all("eventId" in payload for payload in data_payloads)
    assert all("jobId" in payload for payload in data_payloads)
    assert all("id" not in payload for payload in data_payloads)
