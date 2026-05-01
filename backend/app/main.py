from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.core.legacy_path import ensure_agent_code_on_path

ensure_agent_code_on_path()

from app.api import agents, handoff, health, jobs, learning, media, projects
from app.core.errors import install_error_handlers
from app.core.settings import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version=settings.version,
        debug=settings.debug,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if settings.cors_allow_all else list(settings.cors_origins),
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(health.router)
    app.include_router(media.router)
    app.include_router(jobs.router)
    app.include_router(learning.router)
    app.include_router(agents.router)
    app.include_router(projects.router)
    app.include_router(handoff.router)
    install_error_handlers(app)
    app.mount(
        "/media",
        StaticFiles(directory=str(settings.media_root), check_dir=False),
        name="media",
    )
    return app


app = create_app()
