from __future__ import annotations

import sys

from fastapi import APIRouter

from app.core.legacy_path import ensure_agent_code_on_path
from app.core.settings import get_settings

router = APIRouter(tags=["health"])


@router.get("/api/health")
def health_check() -> dict:
    settings = get_settings()
    agent_code_path = ensure_agent_code_on_path()

    return {
        "status": "ok",
        "service": {
            "name": settings.app_name,
            "version": settings.version,
            "environment": settings.environment,
        },
        "legacy": {
            "agentCodePath": str(agent_code_path),
            "agentCodeOnPath": str(agent_code_path) in sys.path,
        },
        "model": {
            "anthropicConfigured": settings.anthropic_credentials_configured,
            "authMode": settings.anthropic_auth_mode or "none",
            "baseUrlConfigured": settings.anthropic_base_url_configured,
        },
    }
