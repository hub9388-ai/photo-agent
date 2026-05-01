from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import Field, TypeAdapter, model_validator

from app.schemas.common import AgentName, ApiSchema, TriggerType


class BaseAgentRequest(ApiSchema):
    job_id: str
    user_id: str | None = None
    project_id: str | None = None
    agent: AgentName
    user_text: str = ""
    trigger: TriggerType = "user"
    context: dict[str, Any] = Field(default_factory=dict)


class PostAgentRequest(BaseAgentRequest):
    agent: Literal["post"] = "post"
    media_ids: list[str] = Field(min_length=1)
    is_batch: bool = False


class CoachAgentRequest(BaseAgentRequest):
    agent: Literal["coach"] = "coach"
    task_mode: Literal["photo_feedback", "text_qa", "exercise_plan"] = "photo_feedback"
    media_ids: list[str] = Field(default_factory=list)
    handoff_issues: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def require_media_for_photo_feedback(self) -> CoachAgentRequest:
        if self.task_mode == "photo_feedback" and not self.media_ids:
            raise ValueError("media_ids is required when task_mode is photo_feedback")
        return self


class PlanAgentRequest(BaseAgentRequest):
    agent: Literal["plan"] = "plan"
    city: str | None = None
    target_location: str | None = None
    shoot_date: str | None = None
    time_window: str | None = None
    subject: str | None = None
    budget: str | None = None
    constraints: list[str] = Field(default_factory=list)
    style_keywords: list[str] = Field(default_factory=list)
    gear: list[str] = Field(default_factory=list)
    reference_media_ids: list[str] = Field(default_factory=list)


class AssetAgentRequest(BaseAgentRequest):
    agent: Literal["asset"] = "asset"
    project_root: str | None = None
    media_ids: list[str] = Field(default_factory=list)
    task_mode: Literal[
        "import_project",
        "search_assets",
        "show_grade_a",
        "show_grade_b",
        "show_grade_c",
        "show_rejects",
        "show_duplicates",
        "show_suggestions",
        "prepare_handoff",
        "asset_chat",
    ] = "asset_chat"
    search_query: str = ""

    @model_validator(mode="after")
    def require_input_for_mvp_asset_modes(self) -> AssetAgentRequest:
        if self.task_mode == "asset_chat":
            return self
        if self.project_root or self.media_ids:
            return self
        raise ValueError("project_root or media_ids is required for asset task modes")


AgentRequest = Annotated[
    PostAgentRequest | CoachAgentRequest | PlanAgentRequest | AssetAgentRequest,
    Field(discriminator="agent"),
]
AgentRequestAdapter = TypeAdapter(AgentRequest)


RUNTIME_ONLY_FIELDS = frozenset({"client", "system", "messages", "media_items"})
