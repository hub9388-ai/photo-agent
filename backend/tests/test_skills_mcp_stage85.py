from __future__ import annotations

import asyncio
from typing import Any

from app.agents.coach_agent import CoachAgentService
from app.agents.plan_agent import PlanAgentService
from app.agents.post_agent import PostAgentService
from app.main import app
from app.orchestration.event_bus import AgentEventSink, EventBus
from app.schemas.agent import CoachAgentRequest, PlanAgentRequest, PostAgentRequest
from app.schemas.media import MediaAsset
from app.storage.database import SQLiteDatabase
from app.storage.event_store import EventStore
from app.storage.media_store import MediaStore


def prepare_media_record(media_store: MediaStore) -> None:
    media_store.records_dir.mkdir(parents=True, exist_ok=True)
    media_store.previews_dir.mkdir(parents=True, exist_ok=True)
    media_store.originals_dir.mkdir(parents=True, exist_ok=True)

    preview_path = media_store.previews_dir / "media_001.jpg"
    original_path = media_store.originals_dir / "media_001.jpg"
    preview_path.write_bytes(b"preview")
    original_path.write_bytes(b"original")

    asset = MediaAsset(
        id="media_001",
        kind="photo",
        filename="sample.jpg",
        content_type="image/jpeg",
        size_bytes=8,
        storage_uri=str(original_path),
        preview_url="/media/previews/media_001.jpg",
        status="ready",
    )
    (media_store.records_dir / "media_001.json").write_text(
        asset.model_dump_json(),
        encoding="utf-8",
    )


def run_service(service, request, event_store: EventStore):
    async def _run():
        sink = AgentEventSink(
            job_id=request.job_id,
            agent=request.agent,
            event_store=event_store,
            event_bus=EventBus(),
            loop=asyncio.get_running_loop(),
        )
        return await service.run(request, sink)

    return asyncio.run(_run())


def test_post_agent_degrades_when_legacy_skills_loader_fails(tmp_path, monkeypatch) -> None:
    import photo_v1

    media_store = MediaStore(root=tmp_path / "media")
    prepare_media_record(media_store)
    event_store = EventStore(SQLiteDatabase(tmp_path / "app.sqlite3"))
    captured: dict[str, Any] = {}

    monkeypatch.setattr(photo_v1, "load_profile", lambda: {})
    monkeypatch.setattr(photo_v1, "load_skills_knowledge", lambda: (_ for _ in ()).throw(OSError("missing")))
    monkeypatch.setattr(photo_v1, "build_system_prompt", lambda profile, skills: captured.setdefault("skills", skills) or "system")
    monkeypatch.setattr(
        photo_v1,
        "prepare_media_items",
        lambda paths, sink=None: (
            [{"path": paths[0], "label": "preview", "source_label": "preview", "data": "x", "media_type": "image/jpeg"}],
            paths,
            False,
        ),
    )
    monkeypatch.setattr(
        photo_v1,
        "analyze_photo_streaming",
        lambda **kwargs: ("visible", {"summary": "summary"}),
    )

    result = run_service(
        PostAgentService(media_store=media_store, model_client=object()),
        PostAgentRequest(job_id="job_001", media_ids=["media_001"]),
        event_store,
    )

    assert result.status == "succeeded"
    assert captured["skills"] == ""
    assert result.payload["legacy_skills_status"] == "failed"
    assert result.payload["warnings"]
    assert "skills_unavailable" in [event.payload.get("step") for event in event_store.list_by_job("job_001")]


def test_coach_agent_degrades_when_legacy_skills_missing(tmp_path, monkeypatch) -> None:
    import photo_v2

    media_store = MediaStore(root=tmp_path / "media")
    prepare_media_record(media_store)
    event_store = EventStore(SQLiteDatabase(tmp_path / "app.sqlite3"))
    captured: dict[str, Any] = {}

    monkeypatch.setattr(photo_v2, "load_profile", lambda: {})
    monkeypatch.setattr(photo_v2, "load_skills_knowledge", lambda: "")
    monkeypatch.setattr(
        photo_v2,
        "build_learning_system_prompt",
        lambda profile, skills, handoff_issues=None: captured.setdefault("skills", skills) or "system",
    )
    monkeypatch.setattr(
        photo_v2,
        "prepare_media_items",
        lambda paths, sink=None: (
            [{"path": paths[0], "label": "preview", "source_label": "preview", "data": "x", "media_type": "image/jpeg"}],
            paths,
            False,
        ),
    )
    monkeypatch.setattr(photo_v2, "run_learning_coach_turn", lambda **kwargs: ("visible", {"summary": "summary"}))

    result = run_service(
        CoachAgentService(media_store=media_store, model_client=object()),
        CoachAgentRequest(job_id="job_001", media_ids=["media_001"]),
        event_store,
    )

    assert result.status == "succeeded"
    assert captured["skills"] == ""
    assert result.payload["legacy_skills_status"] == "missing"
    assert result.payload["warnings"]


def test_plan_agent_degrades_when_planning_skills_missing(tmp_path, monkeypatch) -> None:
    import photo_v3

    event_store = EventStore(SQLiteDatabase(tmp_path / "app.sqlite3"))
    captured: dict[str, Any] = {}

    monkeypatch.setattr(photo_v3, "load_profile", lambda: {})
    monkeypatch.setattr(photo_v3, "load_planning_skills_knowledge", lambda: "")

    def fake_run_planning_turn(**kwargs):
        captured["skills"] = kwargs["skills_knowledge"]
        return (
            "plan visible",
            {"summary": "plan summary", "plans": [{"style_handoff": "warm"}]},
            {"city": "杭州"},
        )

    monkeypatch.setattr(photo_v3, "run_planning_turn", fake_run_planning_turn)
    monkeypatch.setattr(
        photo_v3,
        "update_planning_session_state",
        lambda session_state, user_text, brief, payload, media_request=None: session_state,
    )

    result = run_service(
        PlanAgentService(model_client=object()),
        PlanAgentRequest(job_id="job_001", user_text="去杭州拍人像", city="杭州"),
        event_store,
    )

    assert result.status == "succeeded"
    assert captured["skills"] == ""
    assert result.payload["legacy_skills_status"] == "missing"
    assert result.payload["warnings"]


def test_openapi_does_not_expose_skills_or_mcp_endpoints() -> None:
    paths = app.openapi()["paths"]
    assert not any("/skills" in path.lower() for path in paths)
    assert not any("/mcp" in path.lower() for path in paths)
