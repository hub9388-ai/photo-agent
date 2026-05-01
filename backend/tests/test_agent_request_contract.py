from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.agent import (
    AgentRequestAdapter,
    AssetAgentRequest,
    CoachAgentRequest,
    PlanAgentRequest,
    PostAgentRequest,
    RUNTIME_ONLY_FIELDS,
)


def test_agent_request_union_uses_agent_discriminator() -> None:
    request = AgentRequestAdapter.validate_python(
        {
            "job_id": "job_001",
            "agent": "plan",
            "user_text": "明天去杭州拍日出",
            "city": "杭州",
        }
    )

    assert isinstance(request, PlanAgentRequest)
    assert request.agent == "plan"


def test_agent_requests_do_not_expose_legacy_runtime_fields() -> None:
    models = (PostAgentRequest, CoachAgentRequest, PlanAgentRequest, AssetAgentRequest)

    for model in models:
        assert RUNTIME_ONLY_FIELDS.isdisjoint(model.model_fields)


def test_post_agent_request_requires_media_ids() -> None:
    with pytest.raises(ValidationError):
        PostAgentRequest(job_id="job_001", agent="post", media_ids=[])


def test_coach_photo_feedback_requires_media_ids_but_text_qa_does_not() -> None:
    with pytest.raises(ValidationError):
        CoachAgentRequest(job_id="job_001", agent="coach")

    request = CoachAgentRequest(
        job_id="job_002",
        agent="coach",
        task_mode="text_qa",
        user_text="怎么练习构图？",
    )

    assert request.media_ids == []


def test_asset_non_chat_modes_require_project_or_media_input() -> None:
    with pytest.raises(ValidationError):
        AssetAgentRequest(job_id="job_001", agent="asset", task_mode="search_assets")

    request = AssetAgentRequest(
        job_id="job_002",
        agent="asset",
        task_mode="search_assets",
        project_root="D:/Photos/set01",
    )

    assert request.project_root == "D:/Photos/set01"
