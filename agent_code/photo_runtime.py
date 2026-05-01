from __future__ import annotations

import os
import sys
from collections.abc import Sequence
from pathlib import Path

import anthropic

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - optional dependency
    load_dotenv = None


_DOTENV_LOADED = False
_DOTENV_FILE_NAMES = (".env", ".env.local", "model.env")


def load_local_env_files() -> None:
    global _DOTENV_LOADED
    if _DOTENV_LOADED:
        return

    _DOTENV_LOADED = True
    if load_dotenv is None:
        return

    candidate_dirs = [
        Path.cwd(),
        Path(__file__).resolve().parent,
    ]
    seen_paths: set[str] = set()

    for directory in candidate_dirs:
        for file_name in _DOTENV_FILE_NAMES:
            path = directory / file_name
            resolved = str(path.resolve(strict=False))
            if resolved in seen_paths or not path.exists():
                continue
            seen_paths.add(resolved)
            load_dotenv(path, override=False)


def read_windows_persistent_env(name: str) -> str:
    if os.name != "nt":
        return ""

    try:
        import winreg
    except ImportError:
        return ""

    registry_paths = (
        (winreg.HKEY_CURRENT_USER, "Environment"),
        (
            winreg.HKEY_LOCAL_MACHINE,
            r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment",
        ),
    )

    for hive, path in registry_paths:
        try:
            with winreg.OpenKey(hive, path) as key:
                value, _ = winreg.QueryValueEx(key, name)
        except OSError:
            continue

        text = str(value).strip()
        if text:
            return text

    return ""


def resolve_env_value(name: str) -> str:
    load_local_env_files()

    value = os.getenv(name, "").strip()
    if value:
        return value

    persistent_value = read_windows_persistent_env(name)
    if persistent_value:
        os.environ[name] = persistent_value
        return persistent_value

    return ""


def resolve_anthropic_client_settings() -> dict[str, str]:
    api_key = resolve_env_value("ANTHROPIC_API_KEY")
    auth_token = resolve_env_value("ANTHROPIC_AUTH_TOKEN")
    base_url = resolve_env_value("ANTHROPIC_BASE_URL")

    active_auth_mode = ""
    if auth_token:
        active_auth_mode = "auth_token"
    elif api_key:
        active_auth_mode = "api_key"

    return {
        "api_key": api_key,
        "auth_token": auth_token,
        "base_url": base_url,
        "active_auth_mode": active_auth_mode,
    }


def ensure_anthropic_credentials(*, source_cli: str) -> dict[str, str]:
    settings = resolve_anthropic_client_settings()
    if settings["auth_token"] or settings["api_key"]:
        return settings

    print(
        "\nStartup failed: missing Anthropic credential.\n"
        "Please configure ANTHROPIC_API_KEY or ANTHROPIC_AUTH_TOKEN"
        f" before launching {source_cli} again.\n"
    )
    sys.exit(1)


def create_anthropic_client(*, source_cli: str) -> anthropic.Anthropic:
    settings = ensure_anthropic_credentials(source_cli=source_cli)
    client_kwargs: dict[str, str] = {}

    if settings["active_auth_mode"] == "auth_token":
        client_kwargs["auth_token"] = settings["auth_token"]
    elif settings["api_key"]:
        client_kwargs["api_key"] = settings["api_key"]

    if settings["base_url"]:
        client_kwargs["base_url"] = settings["base_url"]

    return anthropic.Anthropic(**client_kwargs)


def ensure_required_env(required_names: Sequence[str], *, source_cli: str) -> None:
    missing = [
        name
        for name in required_names
        if not resolve_env_value(str(name).strip())
    ]
    if not missing:
        return

    joined_names = ", ".join(missing)
    print(
        "\nStartup failed: missing required environment variable(s): "
        f"{joined_names}\n"
        f"Please configure them before launching {source_cli} again.\n"
    )
    sys.exit(1)


def handle_api_error(exc: Exception) -> bool:
    try:
        from photo_trace import trace_event
    except ImportError:  # pragma: no cover - defensive fallback
        trace_event = None

    if isinstance(exc, anthropic.BadRequestError):
        if trace_event is not None:
            trace_event("api.error", error_type="BadRequestError", message=str(exc))
        print(f"\nRequest error: {exc}\n")
        return True

    if isinstance(exc, anthropic.AuthenticationError):
        if trace_event is not None:
            trace_event("api.error", error_type="AuthenticationError", message=str(exc))
        print(
            "\nAuthentication failed: please check ANTHROPIC_API_KEY / "
            "ANTHROPIC_AUTH_TOKEN and ANTHROPIC_BASE_URL.\n"
        )
        sys.exit(1)

    if isinstance(exc, anthropic.RateLimitError):
        if trace_event is not None:
            trace_event("api.error", error_type="RateLimitError", message=str(exc))
        print("\nRate limit reached. Please wait a moment and try again.\n")
        return True

    if isinstance(exc, anthropic.APIConnectionError):
        if trace_event is not None:
            trace_event("api.error", error_type="APIConnectionError", message=str(exc))
        print("\nNetwork connection failed. Please check connectivity and retry.\n")
        return True

    if isinstance(exc, anthropic.APIStatusError):
        if trace_event is not None:
            trace_event(
                "api.error",
                error_type="APIStatusError",
                status_code=getattr(exc, "status_code", ""),
                message=getattr(exc, "message", str(exc)),
            )
        if exc.status_code >= 500:
            print(f"\nServer error {exc.status_code}. Please retry shortly.\n")
        else:
            print(f"\nAPI error {exc.status_code}: {exc.message}\n")
        return True

    return False
