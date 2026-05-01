from __future__ import annotations

import asyncio
from typing import Any

from app.agents.coach_agent import CoachAgentService
from app.agents.post_agent import PostAgentService
from app.orchestration.event_bus import AgentEventSink, EventBus
from app.schemas.agent import CoachAgentRequest, PostAgentRequest
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
    async def run():
        sink = AgentEventSink(
            job_id=request.job_id,
            agent=request.agent,
            event_store=event_store,
            event_bus=EventBus(),
            loop=asyncio.get_running_loop(),
        )
        return await service.run(request, sink)

    return asyncio.run(run())


def test_post_agent_service_maps_request_to_legacy_call(tmp_path, monkeypatch) -> None:
    import photo_v1

    media_store = MediaStore(root=tmp_path / "media")
    prepare_media_record(media_store)
    event_store = EventStore(SQLiteDatabase(tmp_path / "app.sqlite3"))
    fake_client = object()
    captured: dict[str, Any] = {}

    monkeypatch.setattr(photo_v1, "load_profile", lambda: {"style_preference": "warm"})
    monkeypatch.setattr(photo_v1, "load_skills_knowledge", lambda: "skills")
    monkeypatch.setattr(photo_v1, "build_system_prompt", lambda profile, skills: "post system")

    def fake_prepare_media_items(paths, sink=None):
        captured["paths"] = paths
        sink.write("post delta", end="")
        return (
            [
                {
                    "path": paths[0],
                    "label": "preview.jpg",
                    "source_label": "preview.jpg",
                    "data": "base64",
                    "media_type": "image/jpeg",
                    "preview_note": "",
                }
            ],
            paths,
            False,
        )

    def fake_analyze_photo_streaming(**kwargs):
        captured["analyze_kwargs"] = kwargs
        return "post visible", {"summary": "post summary", "warnings": ["w1"]}

    monkeypatch.setattr(photo_v1, "prepare_media_items", fake_prepare_media_items)
    monkeypatch.setattr(photo_v1, "analyze_photo_streaming", fake_analyze_photo_streaming)

    service = PostAgentService(media_store=media_store, model_client=fake_client)
    request = PostAgentRequest(
        job_id="job_001",
        media_ids=["media_001"],
        user_text="帮我看看后期",
    )

    result = run_service(service, request, event_store)

    assert result.agent == "post"
    assert result.status == "succeeded"
    assert result.content == "post visible"
    assert result.summary == "post summary"
    assert captured["paths"] == [media_store.previews_dir / "media_001.jpg"]
    analyze_kwargs = captured["analyze_kwargs"]
    assert analyze_kwargs["client"] is fake_client
    assert analyze_kwargs["system"] == "post system"
    assert analyze_kwargs["messages"] == []
    assert analyze_kwargs["user_text"] == "帮我看看后期"
    assert analyze_kwargs["media_items"][0]["media_id"] == "media_001"
    assert "agent.delta" not in [event.type for event in event_store.list_by_job("job_001")]


def test_coach_agent_service_maps_request_to_legacy_call(tmp_path, monkeypatch) -> None:
    import photo_v2

    media_store = MediaStore(root=tmp_path / "media")
    prepare_media_record(media_store)
    event_store = EventStore(SQLiteDatabase(tmp_path / "app.sqlite3"))
    fake_client = object()
    captured: dict[str, Any] = {}

    monkeypatch.setattr(photo_v2, "load_profile", lambda: {"skill_level": "beginner"})
    monkeypatch.setattr(photo_v2, "load_skills_knowledge", lambda: "skills")
    monkeypatch.setattr(
        photo_v2,
        "build_learning_system_prompt",
        lambda profile, skills, handoff_issues=None: "coach system",
    )

    def fake_prepare_media_items(paths, sink=None):
        captured["paths"] = paths
        sink.write("coach delta", end="")
        return (
            [
                {
                    "path": paths[0],
                    "label": "preview.jpg",
                    "source_label": "preview.jpg",
                    "data": "base64",
                    "media_type": "image/jpeg",
                    "preview_note": "",
                }
            ],
            paths,
            False,
        )

    def fake_run_learning_coach_turn(**kwargs):
        captured["coach_kwargs"] = kwargs
        return "coach visible", {"summary": "coach summary", "warnings": ["w1"]}

    monkeypatch.setattr(photo_v2, "prepare_media_items", fake_prepare_media_items)
    monkeypatch.setattr(photo_v2, "run_learning_coach_turn", fake_run_learning_coach_turn)

    service = CoachAgentService(media_store=media_store, model_client=fake_client)
    request = CoachAgentRequest(
        job_id="job_001",
        media_ids=["media_001"],
        user_text="帮我复盘拍摄",
        handoff_issues=["背景干扰强"],
    )

    result = run_service(service, request, event_store)

    assert result.agent == "coach"
    assert result.status == "succeeded"
    assert result.content == "coach visible"
    assert result.summary == "coach summary"
    assert captured["paths"] == [media_store.previews_dir / "media_001.jpg"]
    coach_kwargs = captured["coach_kwargs"]
    assert coach_kwargs["client"] is fake_client
    assert coach_kwargs["system"] == "coach system"
    assert coach_kwargs["messages"] == []
    assert coach_kwargs["user_text"] == "帮我复盘拍摄"
    assert coach_kwargs["handoff_issues"] == ["背景干扰强"]
    assert coach_kwargs["media_items"][0]["media_id"] == "media_001"
    assert "agent.delta" not in [event.type for event in event_store.list_by_job("job_001")]
