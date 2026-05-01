from __future__ import annotations

import importlib
import uuid
from dataclasses import dataclass
from pathlib import Path

from app.core.errors import ApiError
from app.core.legacy_path import ensure_agent_code_on_path
from app.orchestration.event_bus import EventBus
from app.orchestration.job_runner import JobRunner
from app.schemas.event import AgentEvent
from app.schemas.handoff import HandoffRequest
from app.schemas.job import CreateJobRequest
from app.schemas.response import HandoffResponse
from app.storage.event_store import EventStore
from app.storage.job_store import JobStore
from app.storage.media_store import MediaStore
from app.storage.result_store import ResultStore


@dataclass
class HandoffService:
    job_store: JobStore
    result_store: ResultStore
    event_store: EventStore
    event_bus: EventBus
    job_runner: JobRunner
    media_store: MediaStore

    async def create_handoff(self, request: HandoffRequest) -> HandoffResponse:
        if request.source_agent != "asset":
            raise ApiError(
                "HANDOFF_REJECTED",
                status_code=400,
                detail={"reason": "only_asset_source_supported_in_stage_7"},
            )
        if request.target_agent not in {"post", "coach"}:
            raise ApiError(
                "HANDOFF_REJECTED",
                status_code=400,
                detail={"reason": "only_post_or_coach_targets_supported_in_stage_7"},
            )

        source_job = self.job_store.get(request.source_job_id)
        if source_job is None:
            raise ApiError("JOB_NOT_FOUND", status_code=404)

        index = self._load_asset_index(request.source_job_id)
        selected_assets = self._select_assets(index, request)
        if not selected_assets and not request.media_ids:
            raise ApiError(
                "HANDOFF_REJECTED",
                status_code=400,
                detail={"reason": "no_assets_available_for_handoff"},
            )

        media_ids = list(request.media_ids)
        for asset in selected_assets:
            media = self.media_store.register_existing_file(
                Path(str(asset.get("absolute_path", ""))),
                metadata={
                    "sourceJobId": request.source_job_id,
                    "sourceAgent": "asset",
                    "assetId": asset.get("id", ""),
                    "relativePath": asset.get("relative_path", ""),
                    "deliveryGrade": asset.get("delivery_grade", ""),
                },
            )
            media_ids.append(media.id)

        target_job = self.job_store.create_from_request(
            CreateJobRequest(
                type="post_process_advice" if request.target_agent == "post" else "coach_feedback",
                trigger="handoff",
                media_ids=media_ids,
                agents=[request.target_agent],
                user_goal=request.user_goal or self._default_user_goal(request.target_agent),
                context={
                    **request.context,
                    "source_job_id": request.source_job_id,
                    "source_agent": request.source_agent,
                    "handoff_asset_ids": [asset.get("id", "") for asset in selected_assets],
                    "handoff_note": self._handoff_note(index, request.target_agent),
                },
            )
        )
        await self._publish_created_event(target_job.id, request.target_agent, media_ids)
        self.job_runner.start(target_job.id)

        return HandoffResponse(
            handoff_id=f"handoff_{uuid.uuid4().hex}",
            source_agent=request.source_agent,
            target_agent=request.target_agent,
            target_job_id=target_job.id,
            status="accepted",
        )

    def _load_asset_index(self, job_id: str) -> dict:
        for result in self.result_store.list_latest_by_job(job_id):
            if result.agent == "asset" and isinstance(result.payload.get("index"), dict):
                return result.payload["index"]
        raise ApiError(
            "HANDOFF_REJECTED",
            status_code=400,
            detail={"reason": "source_job_has_no_asset_index_result"},
        )

    def _select_assets(self, index: dict, request: HandoffRequest) -> list[dict]:
        asset_ids = (
            request.context.get("asset_ids")
            or request.context.get("assetIds")
            or request.context.get("selected_asset_ids")
            or request.context.get("selectedAssetIds")
            or []
        )
        if asset_ids:
            wanted = {str(asset_id) for asset_id in asset_ids}
            return [asset for asset in index.get("assets", []) if str(asset.get("id", "")) in wanted]

        legacy = self._legacy_asset_module()
        assets, _note = legacy.prepare_handoff_assets(index, request.target_agent)
        return list(assets)

    def _handoff_note(self, index: dict, target_agent: str) -> str:
        legacy = self._legacy_asset_module()
        _assets, note = legacy.prepare_handoff_assets(index, target_agent)
        return str(note)

    async def _publish_created_event(
        self,
        job_id: str,
        target_agent: str,
        media_ids: list[str],
    ) -> None:
        event = AgentEvent(
            id=f"evt_{job_id}_created",
            job_id=job_id,
            seq=self.event_store.next_seq(job_id),
            agent=None,
            type="job.created",
            message="Handoff 任务已创建",
            payload={"agents": [target_agent], "mediaIds": media_ids},
        )
        self.event_store.append_if_persisted(event)
        await self.event_bus.publish(event)

    def _legacy_asset_module(self):
        ensure_agent_code_on_path()
        return importlib.import_module("photo_v4")

    def _default_user_goal(self, target_agent: str) -> str:
        if target_agent == "coach":
            return "请复盘这些素材的问题，并给出下次拍摄训练建议。"
        return "请基于这些精选素材给出统一后期方向和参数建议。"
