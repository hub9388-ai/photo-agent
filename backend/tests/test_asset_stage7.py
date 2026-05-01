from __future__ import annotations

import json
import time
from pathlib import Path

from fastapi.testclient import TestClient

from app.agents.asset_agent import AssetAgentService
from app.main import app
from app.orchestration.event_bus import AgentEventSink, EventBus, get_event_bus
from app.orchestration.job_runner import JobRunner, get_job_runner
from app.schemas.agent import AssetAgentRequest
from app.storage.database import SQLiteDatabase
from app.storage.event_store import EventStore, get_event_store
from app.storage.job_store import JobStore, get_job_store
from app.storage.media_store import MediaStore, get_media_store
from app.storage.result_store import ResultStore, get_result_store
from backend.tests.test_job_system import FakeAgentService


def build_asset_index(project_root: Path, asset_path: Path) -> dict:
    return {
        "project_root": str(project_root),
        "project_name": "stage7",
        "assets": [
            {
                "id": "asset_00001",
                "relative_path": asset_path.name,
                "absolute_path": str(asset_path),
                "delivery_grade": "A",
                "quality_score": 91.0,
                "scene_id": "scene_001",
                "burst_id": "burst_0001",
                "duplicate_group": "",
                "duplicate_of": "",
                "reject_reasons": [],
                "tags": ["精选"],
            },
            {
                "id": "asset_00002",
                "relative_path": "reject.jpg",
                "absolute_path": str(project_root / "reject.jpg"),
                "delivery_grade": "Reject",
                "quality_score": 20.0,
                "scene_id": "scene_001",
                "burst_id": "burst_0001",
                "duplicate_group": "dup_001",
                "duplicate_of": "asset_00001",
                "reject_reasons": ["近似重复"],
                "tags": ["清理候选"],
            },
        ],
        "stats": {
            "total_assets": 2,
            "grade_counts": {"A": 1, "B": 0, "C": 0, "Reject": 1},
            "duplicate_count": 1,
        },
        "suggestions": {"project_name_suggestions": ["202604_stage7"]},
        "duplicate_groups": [{"id": "dup_001", "confidence": 0.92}],
        "highlight_ids": ["asset_00001"],
        "reject_ids": ["asset_00002"],
    }


def install_stage7_overrides(
    db_path: Path,
    media_root: Path,
    *,
    asset_service: FakeAgentService,
    post_service: FakeAgentService | None = None,
    coach_service: FakeAgentService | None = None,
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
        post_agent_service=post_service or FakeAgentService("post"),
        coach_agent_service=coach_service or FakeAgentService("coach"),
        asset_agent_service=asset_service,
    )
    media_store = MediaStore(root=media_root)
    app.dependency_overrides[get_job_store] = lambda: job_store
    app.dependency_overrides[get_event_store] = lambda: event_store
    app.dependency_overrides[get_result_store] = lambda: result_store
    app.dependency_overrides[get_event_bus] = lambda: event_bus
    app.dependency_overrides[get_job_runner] = lambda: job_runner
    app.dependency_overrides[get_media_store] = lambda: media_store
    return job_store, result_store, media_store


def wait_for_status(client: TestClient, job_id: str, status: str) -> dict:
    deadline = time.time() + 3
    payload = {}
    while time.time() < deadline:
        response = client.get(f"/api/jobs/{job_id}")
        response.raise_for_status()
        payload = response.json()
        if payload["status"] == status:
            return payload
        time.sleep(0.05)
    raise AssertionError(f"job {job_id} did not reach {status}: {payload}")


def test_asset_agent_service_maps_import_request_to_legacy_index(tmp_path, monkeypatch) -> None:
    import asyncio

    import photo_v4

    project_root = tmp_path / "project"
    project_root.mkdir()
    asset_path = project_root / "pick.jpg"
    asset_path.write_bytes(b"image")
    captured = {}
    asset_index = build_asset_index(project_root, asset_path)

    monkeypatch.setattr(photo_v4, "load_profile", lambda: {"culling_preference": "balanced"})
    monkeypatch.setattr(photo_v4, "ensure_asset_profile_fields", lambda profile: profile)

    def fake_index_project_assets(paths, intent, profile, sink=None):
        captured["paths"] = paths
        captured["intent"] = intent
        captured["profile"] = profile
        sink.progress("legacy asset progress")
        return asset_index

    monkeypatch.setattr(photo_v4, "index_project_assets", fake_index_project_assets)
    monkeypatch.setattr(photo_v4, "save_project_index", lambda index: tmp_path / "cache.json")
    monkeypatch.setattr(photo_v4, "render_index_response", lambda index, cache_path: "asset visible")

    async def run_service():
        event_store = EventStore(SQLiteDatabase(tmp_path / "app.sqlite3"))
        sink = AgentEventSink(
            job_id="job_001",
            agent="asset",
            event_store=event_store,
            event_bus=EventBus(),
            loop=asyncio.get_running_loop(),
        )
        result = await AssetAgentService().run(
            AssetAgentRequest(
                job_id="job_001",
                project_id="project_001",
                project_root=str(project_root),
                task_mode="import_project",
                context={"project_name": "stage7", "culling_preference": "strict"},
            ),
            sink,
        )
        return result, event_store

    result, event_store = asyncio.run(run_service())

    assert result.agent == "asset"
    assert result.status == "succeeded"
    assert result.content == "asset visible"
    assert result.payload["index"]["stats"]["total_assets"] == 2
    assert captured["paths"] == [project_root]
    assert captured["intent"]["project_name"] == "stage7"
    assert captured["intent"]["culling_preference"] == "strict"
    assert "agent.delta" not in [event.type for event in event_store.list_by_job("job_001")]


def test_import_project_assets_creates_asset_job_and_lists_filtered_assets(tmp_path, monkeypatch) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    asset_path = project_root / "pick.jpg"
    asset_path.write_bytes(b"image")
    (project_root / "reject.jpg").write_bytes(b"image")
    monkeypatch.setenv("PHOTO_ASSET_IMPORT_ROOTS", str(tmp_path))

    asset_index = build_asset_index(project_root, asset_path)
    asset_service = FakeAgentService("asset", payload={"index": asset_index})
    install_stage7_overrides(
        tmp_path / "app.sqlite3",
        tmp_path / "media",
        asset_service=asset_service,
    )

    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/projects/project_001/assets/import",
                json={
                    "project_root": str(project_root),
                    "project_name": "stage7",
                    "culling_preference": "balanced",
                },
            )
            assert response.status_code == 202
            job_id = response.json()["jobId"]
            wait_for_status(client, job_id, "completed")

            assets = client.get("/api/projects/project_001/assets?grade=A").json()
            with client.stream(
                "GET",
                f"/api/jobs/{job_id}/events?replay_only=true",
            ) as stream:
                event_lines = [line for line in stream.iter_lines() if line.startswith("event: ")]
                if "event: job.completed" in event_lines:
                    pass
    finally:
        app.dependency_overrides.clear()

    assert asset_service.requests
    assert asset_service.requests[0].agent == "asset"
    assert asset_service.requests[0].project_root == str(project_root.resolve())
    assert assets["projectId"] == "project_001"
    assert assets["stats"]["total_assets"] == 2
    assert [asset["assetId"] for asset in assets["assets"]] == ["asset_00001"]


def test_asset_handoff_to_post_creates_target_job_with_registered_media(tmp_path, monkeypatch) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    asset_path = project_root / "pick.jpg"
    asset_path.write_bytes(b"image")
    monkeypatch.setenv("PHOTO_ASSET_IMPORT_ROOTS", str(tmp_path))

    asset_index = build_asset_index(project_root, asset_path)
    asset_service = FakeAgentService("asset", payload={"index": asset_index})
    post_service = FakeAgentService("post")
    _job_store, result_store, media_store = install_stage7_overrides(
        tmp_path / "app.sqlite3",
        tmp_path / "media",
        asset_service=asset_service,
        post_service=post_service,
    )

    try:
        with TestClient(app) as client:
            import_response = client.post(
                "/api/projects/project_001/assets/import",
                json={"project_root": str(project_root)},
            )
            source_job_id = import_response.json()["jobId"]
            wait_for_status(client, source_job_id, "completed")

            handoff_response = client.post(
                "/api/handoff",
                json={
                    "source_job_id": source_job_id,
                    "source_agent": "asset",
                    "target_agent": "post",
                    "context": {"asset_ids": ["asset_00001"]},
                },
            )
            assert handoff_response.status_code == 202
            target_job_id = handoff_response.json()["targetJobId"]
            wait_for_status(client, target_job_id, "completed")
            target_results = client.get(f"/api/jobs/{target_job_id}/results").json()
    finally:
        app.dependency_overrides.clear()

    assert post_service.requests
    assert post_service.requests[0].media_ids
    registered_media = media_store.get(post_service.requests[0].media_ids[0])
    assert registered_media.storage_uri == str(asset_path.resolve(strict=False))
    assert target_results["completedAgents"] == ["post"]
    assert len(result_store.list_latest_by_job(target_job_id)) == 1


def test_project_import_rejects_directory_outside_allowed_roots(tmp_path, monkeypatch) -> None:
    allowed_root = tmp_path / "allowed"
    outside_root = tmp_path / "outside"
    allowed_root.mkdir()
    outside_root.mkdir()
    monkeypatch.setenv("PHOTO_ASSET_IMPORT_ROOTS", str(allowed_root))
    asset_service = FakeAgentService("asset", payload={"index": {"assets": []}})
    install_stage7_overrides(
        tmp_path / "app.sqlite3",
        tmp_path / "media",
        asset_service=asset_service,
    )

    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/projects/project_001/assets/import",
                json={"project_root": str(outside_root)},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 400
    assert response.json()["errorCode"] == "VALIDATION_ERROR"


def test_sse_replay_contains_asset_events(tmp_path, monkeypatch) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    asset_path = project_root / "pick.jpg"
    asset_path.write_bytes(b"image")
    monkeypatch.setenv("PHOTO_ASSET_IMPORT_ROOTS", str(tmp_path))
    asset_service = FakeAgentService(
        "asset",
        payload={"index": build_asset_index(project_root, asset_path)},
    )
    install_stage7_overrides(
        tmp_path / "app.sqlite3",
        tmp_path / "media",
        asset_service=asset_service,
    )

    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/projects/project_001/assets/import",
                json={"project_root": str(project_root)},
            )
            job_id = response.json()["jobId"]
            wait_for_status(client, job_id, "completed")
            with client.stream("GET", f"/api/jobs/{job_id}/events?replay_only=true") as stream:
                lines = [line for line in stream.iter_lines() if line]
    finally:
        app.dependency_overrides.clear()

    assert "event: agent.started" in lines
    assert "event: agent.result" in lines
    assert "event: job.completed" in lines
    data_lines = [line for line in lines if line.startswith("data: ")]
    assert any(json.loads(line.removeprefix("data: "))["agent"] == "asset" for line in data_lines)
