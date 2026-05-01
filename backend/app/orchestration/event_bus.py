from __future__ import annotations

import asyncio
import re
import uuid
from collections import defaultdict
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import AsyncIterator

from app.schemas.common import AgentName
from app.schemas.event import AgentEvent
from app.storage.event_store import EventStore


@dataclass
class EventBus:
    max_queue_size: int = 100
    _subscribers: dict[str, set[asyncio.Queue[AgentEvent]]] = field(
        default_factory=lambda: defaultdict(set)
    )

    async def publish(self, event: AgentEvent) -> None:
        self._publish_nowait(event)

    def publish_threadsafe(self, event: AgentEvent, loop: asyncio.AbstractEventLoop) -> None:
        loop.call_soon_threadsafe(self._publish_nowait, event)

    def _publish_nowait(self, event: AgentEvent) -> None:
        subscribers = list(self._subscribers.get(event.job_id, set()))
        for queue in subscribers:
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                continue

    @asynccontextmanager
    async def subscribe(self, job_id: str) -> AsyncIterator[asyncio.Queue[AgentEvent]]:
        queue: asyncio.Queue[AgentEvent] = asyncio.Queue(maxsize=self.max_queue_size)
        self._subscribers[job_id].add(queue)
        try:
            yield queue
        finally:
            subscribers = self._subscribers.get(job_id)
            if subscribers is not None:
                subscribers.discard(queue)
                if not subscribers:
                    self._subscribers.pop(job_id, None)


_EVENT_BUS = EventBus()


def get_event_bus() -> EventBus:
    return _EVENT_BUS


@dataclass
class AgentEventSink:
    job_id: str
    agent: AgentName
    event_store: EventStore
    event_bus: EventBus
    loop: asyncio.AbstractEventLoop

    async def emit_async(
        self,
        type: str,
        *,
        message: str | None = None,
        payload: dict | None = None,
        persist: bool = True,
    ) -> AgentEvent:
        event = self._build_event(
            type=type,
            message=message,
            payload=payload,
            persist=persist,
        )
        self.event_store.append_if_persisted(event)
        await self.event_bus.publish(event)
        return event

    def emit_sync(
        self,
        type: str,
        *,
        message: str | None = None,
        payload: dict | None = None,
        persist: bool = True,
    ) -> AgentEvent:
        event = self._build_event(
            type=type,
            message=message,
            payload=payload,
            persist=persist,
        )
        self.event_store.append_if_persisted(event)
        self.event_bus.publish_threadsafe(event, self.loop)
        return event

    def progress_step(self, step: str, message: str, *, progress: float | None = None) -> None:
        payload: dict = {"step": step}
        if progress is not None:
            payload["progress"] = progress
        self.emit_sync("agent.progress", message=message, payload=payload)

    def write(self, text: str, *, end: str = "", flush: bool = False) -> None:
        del flush
        chunk = f"{text}{end}"
        if not chunk:
            return
        self.emit_sync(
            "agent.delta",
            payload={"text": chunk},
            persist=False,
        )

    def line(self, text: str = "") -> None:
        self.write(text, end="\n")

    def progress(self, message: str) -> None:
        self.progress_step(
            _step_from_message(message),
            message,
        )

    def _build_event(
        self,
        *,
        type: str,
        message: str | None,
        payload: dict | None,
        persist: bool,
    ) -> AgentEvent:
        return AgentEvent(
            id=f"evt_{uuid.uuid4().hex}",
            job_id=self.job_id,
            seq=self.event_store.next_seq(self.job_id),
            agent=self.agent,
            type=type,
            message=message,
            payload=payload or {},
            persist=persist,
        )


def _step_from_message(message: str) -> str:
    normalized = re.sub(r"[^0-9A-Za-z]+", "_", message.strip()).strip("_").lower()
    return normalized[:64] or "legacy_progress"
