from __future__ import annotations

import json
from dataclasses import dataclass
from threading import RLock

from app.schemas.result import AgentResult
from app.storage.database import SQLiteDatabase, get_database


@dataclass
class ResultStore:
    database: SQLiteDatabase

    def __post_init__(self) -> None:
        self._lock = RLock()

    def save(self, result: AgentResult) -> AgentResult:
        with self._lock, self.database.connect() as connection:
            connection.execute(
                """
                INSERT INTO results (id, job_id, agent, status, created_at, payload_json)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    status = excluded.status,
                    payload_json = excluded.payload_json
                """,
                (
                    result.id,
                    result.job_id,
                    result.agent,
                    result.status,
                    result.created_at.isoformat(),
                    result.model_dump_json(),
                ),
            )
        return result

    def list_by_job(self, job_id: str) -> list[AgentResult]:
        with self.database.connect() as connection:
            rows = connection.execute(
                """
                SELECT payload_json FROM results
                WHERE job_id = ?
                ORDER BY created_at ASC, id ASC
                """,
                (job_id,),
            ).fetchall()
        return [AgentResult.model_validate(json.loads(row["payload_json"])) for row in rows]

    def list_latest_by_job(self, job_id: str) -> list[AgentResult]:
        latest_by_agent: dict[str, AgentResult] = {}
        for result in self.list_by_job(job_id):
            latest_by_agent[result.agent] = result
        return list(latest_by_agent.values())


_RESULT_STORE: ResultStore | None = None
_RESULT_STORE_LOCK = RLock()


def get_result_store() -> ResultStore:
    global _RESULT_STORE
    with _RESULT_STORE_LOCK:
        if _RESULT_STORE is None:
            _RESULT_STORE = ResultStore(get_database())
        return _RESULT_STORE
