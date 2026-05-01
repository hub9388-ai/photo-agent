from __future__ import annotations

import sys
from pathlib import Path


def find_repo_root(start: Path | None = None) -> Path:
    current = (start or Path(__file__)).resolve()
    search_from = current if current.is_dir() else current.parent

    for candidate in (search_from, *search_from.parents):
        if (candidate / "agent_code").is_dir():
            return candidate

    raise RuntimeError("Could not locate repository root containing agent_code/.")


def ensure_agent_code_on_path() -> Path:
    repo_root = find_repo_root()
    agent_code_path = repo_root / "agent_code"
    agent_code_text = str(agent_code_path)

    if agent_code_text not in sys.path:
        sys.path.insert(0, agent_code_text)

    return agent_code_path
