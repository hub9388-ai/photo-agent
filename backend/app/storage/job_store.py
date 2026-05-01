from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from threading import RLock

from app.schemas.common import utc_now
from app.schemas.job import AgentJob, CreateJobRequest
from app.storage.database import SQLiteDatabase, get_database


@dataclass
class JobStore:
    database: SQLiteDatabase

    def __post_init__(self) -> None:
        self._lock = RLock()

    def create_from_request(self, request: CreateJobRequest) -> AgentJob:
        now = utc_now()
        job = AgentJob(
            id=f"job_{uuid.uuid4().hex}",
            type=request.type,
            trigger=request.trigger,
            media_ids=request.media_ids,
            agents=request.agents,
            status="queued",
            user_goal=request.user_goal,
            context=request.context,
            created_at=now,
            updated_at=now,
        )
        self.save(job)
        return job

    def save(self, job: AgentJob) -> AgentJob:
        payload = job.model_dump_json()
        with self._lock, self.database.connect() as connection:
            connection.execute(
                """
                INSERT INTO jobs (id, type, status, created_at, updated_at, payload_json)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    type = excluded.type,
                    status = excluded.status,
                    updated_at = excluded.updated_at,
                    payload_json = excluded.payload_json
                """,
                (
                    job.id,
                    job.type,
                    job.status,
                    job.created_at.isoformat(),
                    job.updated_at.isoformat(),
                    payload,
                ),
            )
        return job

    def get(self, job_id: str) -> AgentJob | None:
        with self.database.connect() as connection:
            row = connection.execute(
                "SELECT payload_json FROM jobs WHERE id = ?",
                (job_id,),
            ).fetchone()
        if row is None:
            return None
        return AgentJob.model_validate(json.loads(row["payload_json"]))

    def list(self, *, media_id: str | None = None, limit: int = 50) -> list[AgentJob]:
        with self.database.connect() as connection:
            rows = connection.execute(
                """
                SELECT payload_json FROM jobs
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        jobs = [AgentJob.model_validate(json.loads(row["payload_json"])) for row in rows]
        if media_id is None:
            return jobs
        return [job for job in jobs if media_id in job.media_ids]

    def update_status(self, job_id: str, status: str) -> AgentJob | None:
        job = self.get(job_id)
        if job is None:
            return None
        updated = job.model_copy(update={"status": status, "updated_at": utc_now()})
        return self.save(updated)


_JOB_STORE: JobStore | None = None
_JOB_STORE_LOCK = RLock()


def get_job_store() -> JobStore:
    global _JOB_STORE
    with _JOB_STORE_LOCK:
        if _JOB_STORE is None:
            _JOB_STORE = JobStore(get_database())
        return _JOB_STORE
