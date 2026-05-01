from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from app.core.legacy_path import ensure_agent_code_on_path, find_repo_root

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - optional dependency
    load_dotenv = None


_ENV_FILE_NAMES = (".env", ".env.local", "model.env")
_ENV_FILES_LOADED = False


def _to_bool(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _to_int(value: str, *, default: int) -> int:
    try:
        parsed = int(value.strip())
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default


def _to_csv(value: str, *, default: tuple[str, ...]) -> tuple[str, ...]:
    items = tuple(item.strip() for item in value.split(",") if item.strip())
    return items or default


def _resolve_repo_path(value: str, *, default: str) -> Path:
    raw_path = Path(value.strip() or default)
    if raw_path.is_absolute():
        return raw_path
    return find_repo_root() / raw_path


def candidate_env_file_paths(
    *,
    repo_root: Path | None = None,
    cwd: Path | None = None,
) -> tuple[Path, ...]:
    root = (repo_root or find_repo_root()).resolve()
    current_dir = (cwd or Path.cwd()).resolve()
    candidate_dirs = (root, root / "backend", current_dir)

    paths: list[Path] = []
    seen: set[str] = set()
    for directory in candidate_dirs:
        for file_name in _ENV_FILE_NAMES:
            path = directory / file_name
            resolved = str(path.resolve(strict=False))
            if resolved in seen:
                continue
            seen.add(resolved)
            if path.exists():
                paths.append(path)

    return tuple(paths)


def load_backend_env_files() -> None:
    global _ENV_FILES_LOADED
    if _ENV_FILES_LOADED:
        return

    _ENV_FILES_LOADED = True
    if load_dotenv is None:
        return

    for path in candidate_env_file_paths():
        load_dotenv(path, override=False)


@dataclass(frozen=True)
class Settings:
    app_name: str
    version: str
    environment: str
    debug: bool
    anthropic_auth_mode: str
    anthropic_base_url_configured: bool
    anthropic_credentials_configured: bool
    media_root: Path
    max_upload_bytes: int
    database_path: Path
    cors_origins: tuple[str, ...]
    cors_allow_all: bool


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    ensure_agent_code_on_path()
    load_backend_env_files()

    from photo_runtime import resolve_anthropic_client_settings, resolve_env_value

    anthropic_settings = resolve_anthropic_client_settings()

    app_name = resolve_env_value("PHOTO_APP_NAME") or "Photography Agent API"
    version = resolve_env_value("PHOTO_APP_VERSION") or "0.1.0"
    environment = resolve_env_value("PHOTO_ENV") or "development"
    debug = _to_bool(resolve_env_value("PHOTO_DEBUG"))
    media_root = _resolve_repo_path(resolve_env_value("PHOTO_MEDIA_ROOT"), default="media")
    max_upload_bytes = _to_int(
        resolve_env_value("PHOTO_MAX_UPLOAD_BYTES"),
        default=25 * 1024 * 1024,
    )
    database_path = _resolve_repo_path(
        resolve_env_value("PHOTO_DATABASE_PATH"),
        default="data/app.sqlite3",
    )
    cors_origins = _to_csv(
        resolve_env_value("PHOTO_CORS_ORIGINS"),
        default=(
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "http://localhost:3001",
            "http://127.0.0.1:3001",
        ),
    )
    cors_allow_all = _to_bool(resolve_env_value("PHOTO_CORS_ALLOW_ALL")) or environment == "development"

    return Settings(
        app_name=app_name,
        version=version,
        environment=environment,
        debug=debug,
        anthropic_auth_mode=anthropic_settings["active_auth_mode"],
        anthropic_base_url_configured=bool(anthropic_settings["base_url"]),
        anthropic_credentials_configured=bool(
            anthropic_settings["api_key"] or anthropic_settings["auth_token"]
        ),
        media_root=media_root,
        max_upload_bytes=max_upload_bytes,
        database_path=database_path,
        cors_origins=cors_origins,
        cors_allow_all=cors_allow_all,
    )
