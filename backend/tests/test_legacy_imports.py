from __future__ import annotations

from app.agents.asset_agent import AssetAgentService
from app.agents.coach_agent import CoachAgentService
from app.agents.plan_agent import PlanAgentService
from app.agents.post_agent import PostAgentService


def test_agent_services_import_legacy_modules() -> None:
    services = (
        PostAgentService(),
        CoachAgentService(),
        PlanAgentService(),
        AssetAgentService(),
    )

    loaded = [service.load_legacy_module().__name__ for service in services]

    assert loaded == ["photo_v1", "photo_v2", "photo_v3", "photo_v4"]
