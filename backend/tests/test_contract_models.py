from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.event import AgentEvent, should_persist_event
from app.schemas.job import AgentJob, CreateJobRequest


def test_agent_job_supports_partial_completed_status() -> None:
    job = AgentJob(
        id="job_001",
        type="photo_review",
        media_ids=["media_001"],
        agents=["post", "coach"],
        status="partial_completed",
    )

    assert job.status == "partial_completed"


def test_model_default_factories_are_not_shared() -> None:
    first = CreateJobRequest()
    second = CreateJobRequest()

    first.context["source"] = "test"
    first.agents.append("plan")

    assert second.context == {}
    assert second.agents == ["post", "coach"]


def test_event_seq_must_be_positive() -> None:
    with pytest.raises(ValidationError):
        AgentEvent(id="evt_001", job_id="job_001", seq=0, agent=None, type="job.created")


def test_event_persistence_rules_skip_delta_and_duplicate_progress_step() -> None:
    delta = AgentEvent(
        id="evt_001",
        job_id="job_001",
        seq=1,
        agent="post",
        type="agent.delta",
        payload={"text": "流式片段"},
    )
    first_progress = AgentEvent(
        id="evt_002",
        job_id="job_001",
        seq=2,
        agent="post",
        type="agent.progress",
        payload={"step": "analyzing_color", "progress": 0.2},
    )
    duplicate_progress = AgentEvent(
        id="evt_003",
        job_id="job_001",
        seq=3,
        agent="post",
        type="agent.progress",
        payload={"step": "analyzing_color", "progress": 0.5},
    )
    result = AgentEvent(
        id="evt_004",
        job_id="job_001",
        seq=4,
        agent="post",
        type="agent.result",
    )

    assert should_persist_event(delta) is False
    assert should_persist_event(first_progress) is True
    assert should_persist_event(duplicate_progress, previous_progress_step="analyzing_color") is False
    assert should_persist_event(result) is True
