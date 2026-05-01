from __future__ import annotations

import importlib
from dataclasses import dataclass
from types import ModuleType
from typing import Protocol

from app.core.legacy_path import ensure_agent_code_on_path
from app.orchestration.event_bus import AgentEventSink
from app.schemas.agent import AgentRequest
from app.schemas.result import AgentResult


class BaseAgent(Protocol):
    async def run(self, request: AgentRequest, sink: AgentEventSink) -> AgentResult:
        ...


@dataclass(frozen=True)
class LegacyAgentService:
    agent_name: str
    module_name: str
    required_callables: tuple[str, ...] = ()

    def load_legacy_module(self) -> ModuleType:
        ensure_agent_code_on_path()
        module = importlib.import_module(self.module_name)
        missing = [name for name in self.required_callables if not callable(getattr(module, name, None))]
        if missing:
            joined = ", ".join(missing)
            raise RuntimeError(f"Legacy module {self.module_name} missing callable(s): {joined}")
        return module
