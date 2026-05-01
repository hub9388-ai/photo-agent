from __future__ import annotations

import json
from dataclasses import dataclass
from threading import RLock

from app.schemas.event import AgentEvent, should_persist_event
from app.storage.database import SQLiteDatabase, get_database


@dataclass
class EventStore:
    database: SQLiteDatabase

    def __post_init__(self) -> None:
        self._lock = RLock()

    def next_seq(self, job_id: str) -> int:
        with self._lock, self.database.connect() as connection:
            connection.execute(
                """
                INSERT INTO event_sequences (job_id, next_seq)
                VALUES (?, 1)
                ON CONFLICT(job_id) DO NOTHING
                """,
                (job_id,),
            )
            row = connection.execute(
                "SELECT next_seq FROM event_sequences WHERE job_id = ?",
                (job_id,),
            ).fetchone()
            seq = int(row["next_seq"])
            connection.execute(
                "UPDATE event_sequences SET next_seq = ? WHERE job_id = ?",
                (seq + 1, job_id),
            )
            return seq

    def append_if_persisted(self, event: AgentEvent) -> bool:
        previous_step = None
        if event.type == "agent.progress":
            previous_step = self.latest_progress_step(event.job_id, event.agent)
        if not should_persist_event(event, previous_progress_step=previous_step):
            return False

        with self._lock, self.database.connect() as connection:
            connection.execute(
                """
                INSERT INTO events (id, job_id, seq, agent, type, created_at, payload_json)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event.id,
                    event.job_id,
                    event.seq,
                    event.agent,
                    event.type,
                    event.created_at.isoformat(),
                    event.model_dump_json(),
                ),
            )
        return True

    def list_by_job(self, job_id: str, *, after_seq: int = 0) -> list[AgentEvent]:
        with self.database.connect() as connection:
            rows = connection.execute(
                """
                SELECT payload_json FROM events
                WHERE job_id = ? AND seq > ?
                ORDER BY seq ASC
                """,
                (job_id, after_seq),
            ).fetchall()
        return [AgentEvent.model_validate(json.loads(row["payload_json"])) for row in rows]

    def latest_progress_step(self, job_id: str, agent: str | None) -> str | None:
        with self.database.connect() as connection:
            row = connection.execute(
                """
                SELECT payload_json FROM events
                WHERE job_id = ?
                    AND type = 'agent.progress'
                    AND ((agent IS NULL AND ? IS NULL) OR agent = ?)
                ORDER BY seq DESC
                LIMIT 1
                """,
                (job_id, agent, agent),
            ).fetchone()
        if row is None:
            return None
        event = AgentEvent.model_validate(json.loads(row["payload_json"]))
        step = event.payload.get("step")
        return step if isinstance(step, str) else None


_EVENT_STORE: EventStore | None = None
_EVENT_STORE_LOCK = RLock()


def get_event_store() -> EventStore:
    global _EVENT_STORE
    with _EVENT_STORE_LOCK:
        if _EVENT_STORE is None:
            _EVENT_STORE = EventStore(get_database())
        return _EVENT_STORE
