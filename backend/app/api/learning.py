from __future__ import annotations

import re
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import Field

from app.schemas.common import ApiSchema, utc_now
from app.storage.job_store import JobStore, get_job_store
from app.storage.result_store import ResultStore, get_result_store


router = APIRouter(prefix="/api/learning", tags=["learning"])


class LearningProfileResponse(ApiSchema):
    streak_days: int = Field(alias="streakDays", ge=0)
    completed_practice_tasks: int = Field(alias="completedPracticeTasks", ge=0)
    current_level: str = Field(alias="currentLevel")
    coach_feedback_count: int = Field(alias="coachFeedbackCount", ge=0)
    source: Literal["job_result_profile"] = "job_result_profile"
    generated_at: datetime = Field(default_factory=utc_now, alias="generatedAt")


@router.get(
    "/profile",
    response_model=LearningProfileResponse,
    summary="Get the lightweight learning profile derived from persisted jobs and results",
)
def get_learning_profile(
    job_store: JobStore = Depends(get_job_store),
    result_store: ResultStore = Depends(get_result_store),
) -> LearningProfileResponse:
    jobs = job_store.list(limit=100)
    practice_task_ids: set[str] = set()
    learning_dates: list[str] = []
    coach_feedback_count = 0

    for job in jobs:
        results = result_store.list_latest_by_job(job.id)
        coach_result = next((result for result in results if result.agent == "coach"), None)
        if coach_result is None or coach_result.status != "succeeded":
            continue

        if job.type in {"photo_review", "coach_feedback"}:
            coach_feedback_count += 1
            learning_dates.append(job.updated_at.isoformat())

        if job.type != "coach_feedback":
            continue

        practice_task_id = str(job.context.get("practice_task_id") or "")
        if practice_task_id and _is_completed_practice_result(coach_result.summary, coach_result.content):
            practice_task_ids.add(practice_task_id)

    completed_count = len(practice_task_ids)
    return LearningProfileResponse(
        streak_days=_count_streak(learning_dates),
        completed_practice_tasks=completed_count,
        current_level=_level_from_completed_practices(completed_count),
        coach_feedback_count=coach_feedback_count,
    )


def _is_completed_practice_result(summary: str, content: str) -> bool:
    text = f"{summary} {content}"
    if re.search(r"未完成|需复练|还需要|不足|失败|没有完成", text):
        return False
    return True


def _date_key(value: str) -> str | None:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).date().isoformat()
    except ValueError:
        return None


def _count_streak(values: list[str]) -> int:
    keys = sorted({key for value in values if (key := _date_key(value))}, reverse=True)
    if not keys:
        return 0

    streak = 1
    cursor = datetime.fromisoformat(keys[0]).date()
    for key in keys[1:]:
        next_day = datetime.fromisoformat(key).date()
        if (cursor - next_day).days != 1:
            break
        streak += 1
        cursor = next_day
    return streak


def _level_from_completed_practices(count: int) -> str:
    if count >= 20:
        return "Lv.5"
    if count >= 10:
        return "Lv.4"
    if count >= 4:
        return "Lv.3"
    if count >= 1:
        return "Lv.2"
    return "Lv.1"
