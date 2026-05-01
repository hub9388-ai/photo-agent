from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from photo_v4 import format_delivery_grade, sort_assets_for_display

DEFAULT_ROUTE_LABELS = {
    "post": "后期辅助",
    "coach": "学习教练",
    "plan": "拍摄规划",
    "asset": "素材管理",
}


@dataclass
class PendingHandoffRequest:
    destination: str
    assets: list[dict]
    note: str


def normalize_media_path_key(path_text: str) -> str:
    return str(path_text).strip().replace("/", "\\").lower()


def split_selection_prompt(user_input: str) -> tuple[str, str]:
    stripped = user_input.strip()
    for separator in ("::", "->", "|"):
        if separator in stripped:
            left, right = stripped.split(separator, 1)
            return left.strip(), right.strip()
    return stripped, ""


def build_handoff_followup_prompt(destination: str, assets: list[dict], custom_prompt: str = "") -> str:
    custom_prompt = custom_prompt.strip()

    if destination == "coach":
        base = (
            "These photos were handed off from asset management. "
            "Please critique them from the learning-coach perspective and suggest the next exercise."
        )
    elif len(assets) > 1:
        base = (
            "These photos were selected in asset management. "
            "Please provide a batch post-processing analysis with a unified grading strategy."
        )
    else:
        asset_name = Path(assets[0].get("absolute_path", "")).name if assets else "this image"
        base = (
            f"This image came from asset management ({asset_name}). "
            "Please provide post-processing analysis and actionable settings."
        )

    if custom_prompt:
        return f"{base} User request: {custom_prompt}"
    return base


def build_handoff_selection_response(
    destination: str,
    assets: list[dict],
    note: str,
    route_labels: dict[str, str] | None = None,
) -> str:
    labels = route_labels or DEFAULT_ROUTE_LABELS
    if not assets:
        if destination == "coach":
            return "当前还没有明确适合送去学习教练的清理样片，先看看清理列表。"
        return "当前还没有明确适合送去后期辅助的典藏或佳片，先看看典藏 / 佳片列表。"

    destination_label = labels.get(destination, destination)
    lines = [
        f"已准备进入{destination_label}。告诉我你想继续处理哪几张：",
        "",
    ]

    display_assets = sort_assets_for_display(assets)
    for idx, asset in enumerate(display_assets, 1):
        lines.append(
            f"{idx}. [{format_delivery_grade(asset.get('delivery_grade', ''))}] {asset.get('relative_path', '')}"
            f"；场景 {asset.get('scene_id', '')}"
            f"；得分 {asset.get('quality_score', 0)}"
        )

    lines.extend(
        [
            "",
            note,
            "",
            "回复序号，例如：1 3",
            "回复 all 表示全选。",
            "也可以直接回复文件名，例如：CAT_19.jpg",
            "也可以补充要求，例如：1 3 :: 保留暖灰夜景氛围",
            "回复 cancel 取消这次流转。",
        ]
    )
    return "\n".join(lines).strip()


def resolve_handoff_selection(
    user_input: str,
    destination: str,
    assets: list[dict],
    *,
    media_request_parser: Callable[[str], dict | None] | None = None,
) -> dict:
    assets = sort_assets_for_display(assets)
    lowered = user_input.strip().lower()
    if lowered in {"cancel", "取消", "算了", "不用了", "停止"}:
        return {"status": "cancel"}

    if media_request_parser is not None:
        direct_media_request = media_request_parser(user_input)
        if direct_media_request:
            requested = {
                normalize_media_path_key(str(path))
                for path in direct_media_request["paths"]
            }
            selected_assets = [
                asset for asset in assets
                if normalize_media_path_key(asset.get("absolute_path", "")) in requested
            ]
            if selected_assets:
                return {
                    "status": "ok",
                    "media_request": {
                        "paths": [Path(asset["absolute_path"]) for asset in selected_assets],
                        "prompt": build_handoff_followup_prompt(
                            destination,
                            selected_assets,
                            direct_media_request.get("prompt", ""),
                        ),
                    },
                    "selected_assets": selected_assets,
                }

    selection_text, custom_prompt = split_selection_prompt(user_input)
    lowered_selection = selection_text.lower()
    if any(keyword in lowered_selection for keyword in ("all", "全部", "都要", "全都", "所有")):
        selected_assets = list(assets)
    else:
        selected_indexes: set[int] = set()
        for match in re.findall(r"\d+", selection_text):
            idx = int(match)
            if 1 <= idx <= len(assets):
                selected_indexes.add(idx - 1)

        selection_tokens = [
            token.strip().strip("\"'")
            for token in re.split(r"[\s,，、]+", selection_text)
            if token.strip().strip("\"'")
        ]
        for idx, asset in enumerate(assets):
            absolute_path = asset.get("absolute_path", "")
            relative_path = asset.get("relative_path", "")
            path_name = Path(absolute_path).name if absolute_path else Path(relative_path).name
            candidate_keys = {
                normalize_media_path_key(absolute_path),
                normalize_media_path_key(relative_path),
                path_name.lower(),
            }
            if any(token.lower() in candidate_keys for token in selection_tokens):
                selected_indexes.add(idx)

        selected_assets = [assets[idx] for idx in sorted(selected_indexes)]

    if not selected_assets:
        return {"status": "invalid"}

    return {
        "status": "ok",
        "media_request": {
            "paths": [Path(asset["absolute_path"]) for asset in selected_assets],
            "prompt": build_handoff_followup_prompt(destination, selected_assets, custom_prompt),
        },
        "selected_assets": selected_assets,
    }


def create_pending_handoff_request(destination: str, assets: list[dict], note: str) -> PendingHandoffRequest:
    return PendingHandoffRequest(
        destination=destination,
        assets=list(assets),
        note=note,
    )


def consume_pending_handoff_input(
    user_input: str,
    pending_request: PendingHandoffRequest,
    *,
    route_labels: dict[str, str] | None = None,
    media_request_parser: Callable[[str], dict | None] | None = None,
) -> dict:
    result = resolve_handoff_selection(
        user_input,
        pending_request.destination,
        pending_request.assets,
        media_request_parser=media_request_parser,
    )

    labels = route_labels or DEFAULT_ROUTE_LABELS
    destination_label = labels.get(pending_request.destination, pending_request.destination)

    if result["status"] == "cancel":
        return {
            "status": "cancel",
            "message": f"已取消流转到{destination_label}。",
        }

    if result["status"] == "invalid":
        response_text = build_handoff_selection_response(
            pending_request.destination,
            pending_request.assets,
            pending_request.note,
            route_labels=labels,
        )
        return {
            "status": "invalid",
            "message": f"没有识别出你的选择，请再选一次。\n\n{response_text}",
        }

    selected_assets = result.get("selected_assets", [])
    selected_names = [Path(asset.get("absolute_path", "")).name for asset in selected_assets[:3]]
    if len(selected_assets) > 3:
        selected_names.append("...")

    return {
        "status": "accepted",
        "destination": pending_request.destination,
        "selected_assets": selected_assets,
        "media_request": result["media_request"],
        "message": (
            f"[流转] 已选择 {len(selected_assets)} 张：{', '.join(selected_names)}。\n"
            f"接下来进入{destination_label}。"
        ),
    }
