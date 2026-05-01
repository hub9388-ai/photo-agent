"""
摄影全栈 Agent - 统一入口路由器
===========================
负责：
  1. 理解用户意图并路由到对应模块
  2. 读取用户档案与最近任务摘要
  3. 调用后期辅助 / 学习教练 / 拍摄规划 / 素材管理中的对应能力

当前已接入模块：
  - V1 后期辅助（photo_v1.py）
  - V2 学习教练（photo_v2.py）
  - V3 拍摄规划（photo_v3.py）
  - V4 素材管理（photo_v4.py）
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import anthropic

from photo_cli import CLIOutput, render_main_banner, render_main_help
from photo_events import EventSink
from photo_handoff import (
    PendingHandoffRequest,
    build_handoff_followup_prompt as shared_build_handoff_followup_prompt,
    build_handoff_selection_response as shared_build_handoff_selection_response,
    consume_pending_handoff_input,
    create_pending_handoff_request,
    normalize_media_path_key as shared_normalize_media_path_key,
    resolve_handoff_selection as shared_resolve_handoff_selection,
    split_selection_prompt as shared_split_selection_prompt,
)
from photo_runtime import create_anthropic_client, handle_api_error
from photo_trace import trace_event
import photo_v1 as post_module
import photo_v2 as coach_module
import photo_v3 as plan_module
import photo_v4 as asset_module


ROUTE_LABELS = {
    "post": "后期辅助",
    "coach": "学习教练",
    "plan": "拍摄规划",
    "asset": "素材管理",
}


ROUTE_RULES = {
    "post": {
        "strong": [
            "后期", "调色", "修图", "参数", "lightroom", "xmp", "预设",
            "高光", "阴影", "色温", "饱和", "对比度", "清晰度", "电影感",
            "统一色调", "肤色别那么黄", "再冷一点",
        ],
        "weak": ["风格", "调一调", "色调", "导出预设", "怎么后期"],
        "counter": ["练习", "提高", "课题", "作业", "点评成长", "怎么进步"],
    },
    "coach": {
        "strong": [
            "学习", "教练", "点评", "反馈", "评估", "提高", "怎么进步", "练习", "训练",
            "课题", "作业", "技能水平", "我现在算什么水平", "成长",
            "景深", "白平衡", "区域曝光", "iso", "快门", "光圈",
        ],
        "weak": ["导师", "怎么拍得更好", "怎么拍更好", "复盘", "讲解", "验收标准"],
        "counter": ["xmp", "预设", "调色", "后期参数", "lightroom"],
    },
    "plan": {
        "strong": [
            "拍摄规划", "拍摄计划", "去哪里拍", "什么时候拍", "光线最好",
            "机位", "踩点", "布光怎么布", "怎么构图", "拍摄清单", "旅拍方案",
        ],
        "weak": ["选景", "时间段", "黄金时段", "场景搭配", "拍摄路线"],
        "counter": ["调色", "练习课题", "归档", "筛片"],
    },
    "asset": {
        "strong": [
            "素材管理", "归档", "筛片", "整理照片", "标签", "命名", "元数据",
            "批量整理", "素材库", "淘汰废片", "文件夹结构",
        ],
        "weak": ["整理", "归类", "检索", "批量命名"],
        "counter": ["调色", "练习", "拍摄计划", "布光"],
    },
}


ROUTER_MODEL_THRESHOLD = 0.7
ASSET_DIRECT_TASKS = {
    "show_grade_a",
    "show_grade_b",
    "show_grade_c",
    "show_highlights",
    "show_rejects",
    "show_duplicates",
    "show_suggestions",
    "prepare_handoff",
}
ASSET_FOLLOWUP_HINTS = (
    "精选",
    "典藏",
    "佳片",
    "留存",
    "清理",
    "候选",
    "废片",
    "重复",
    "相似",
    "命名",
    "标签",
    "归档",
    "送去",
    "拿去",
    "流转",
    "后期辅助",
    "学习教练",
    "复盘",
)


def build_router_prompt(profile: dict, task_history: list[dict], active_module: str) -> str:
    profile_text = post_module.profile_summary(profile)
    history_lines = []
    for item in task_history[-4:]:
        history_lines.append(
            f"- module: {ROUTE_LABELS.get(item.get('module', ''), item.get('module', ''))}"
            f"; summary: {item.get('summary', '')}"
        )
    history_text = "\n".join(history_lines) if history_lines else "- none"

    return f"""You are the router for the photography full-stack agent. Choose exactly one module.
User profile summary:
{profile_text}

Recent task history:
{history_text}

Current active module: {ROUTE_LABELS.get(active_module, 'none')}

Module boundaries:
1. post
- Use for post-processing, color grading, Lightroom, XMP, highlight/shadow tuning, preset export.
2. coach
- Use for learning, critique, exercises, improvement advice, exposure concepts, ISO, shutter, aperture.
3. plan
- Use for location choice, timing, lighting plan, composition plan, shooting checklist, route planning.
4. asset
- Use for culling, archive, tagging, naming, folder organization, duplicate detection, search.

Rules:
- Return JSON only.
- If confidence is below 0.7, ask one natural-language clarification question.

Return schema:
{{
  "module": "post | coach | plan | asset | clarify",
  "confidence": 0.0,
  "reason": "short reason",
  "clarification_question": "question or empty string"
}}
"""
def score_route_by_rules(user_input: str, has_media: bool, active_module: str) -> dict:
    text = user_input.lower()
    scores = {module: 0 for module in ROUTE_RULES}

    for module, config in ROUTE_RULES.items():
        for keyword in config["strong"]:
            if keyword.lower() in text:
                scores[module] += 3
        for keyword in config["weak"]:
            if keyword.lower() in text:
                scores[module] += 1
        for keyword in config["counter"]:
            if keyword.lower() in text:
                scores[module] -= 2

    if has_media:
        if any(keyword in text for keyword in ("点评", "反馈", "评估", "成长", "练习", "提高", "怎么拍更好")):
            scores["coach"] += 3
        elif active_module == "coach":
            scores["coach"] += 2
        else:
            scores["post"] += 2

    if active_module == "asset" and any(keyword in text for keyword in ASSET_FOLLOWUP_HINTS):
        fallback_asset_intent = asset_module.fallback_asset_intent(user_input, False, True)
        if fallback_asset_intent.get("task_mode") in ASSET_DIRECT_TASKS:
            if fallback_asset_intent.get("task_mode") == "prepare_handoff":
                scores["asset"] += 8
            else:
                scores["asset"] += 5

    if active_module in {"post", "coach"} and max(scores.values()) <= 1:
        scores[active_module] += 1

    ordered = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    top_module, top_score = ordered[0]
    second_score = ordered[1][1]
    margin = top_score - second_score

    confidence = 0.0
    if top_score >= 4 and margin >= 2:
        confidence = 0.9
    elif top_score >= 3 and margin >= 1:
        confidence = 0.75
    elif top_score >= 2:
        confidence = 0.55

    return {
        "module": top_module,
        "confidence": confidence,
        "scores": scores,
        "margin": margin,
    }


def should_force_asset_followup(
    user_input: str,
    has_media: bool,
    active_module: str,
    current_asset_index: dict | None,
) -> bool:
    # 只要有已加载的索引，不管当前在哪个模块，素材管理操作都应该优先响应
    if has_media or current_asset_index is None:
        return False

    text = user_input.strip().lower()
    if not any(keyword in text for keyword in ASSET_FOLLOWUP_HINTS):
        return False

    fallback_asset_intent = asset_module.fallback_asset_intent(user_input, False, True)
    return fallback_asset_intent.get("task_mode") in ASSET_DIRECT_TASKS


def route_with_model(
    client: anthropic.Anthropic,
    user_input: str,
    profile: dict,
    task_history: list[dict],
    has_media: bool,
    active_module: str,
) -> dict:
    response = client.messages.create(
        model=post_module.MODEL,
        max_tokens=500,
        system=build_router_prompt(profile, task_history, active_module),
        messages=[
            {
                "role": "user",
                "content": (
                    f"User input: {user_input}\n"
                    f"Has media attachment or local path: {'yes' if has_media else 'no'}"
                ),
            }
        ],
    )
    raw_text = "".join(
        block.text for block in response.content
        if getattr(block, "type", "") == "text"
    ).strip()
    payload = post_module.extract_json_object(raw_text)
    result = {
        "module": str(payload.get("module", "")).strip(),
        "confidence": float(payload.get("confidence", 0) or 0),
        "reason": str(payload.get("reason", "")).strip(),
        "clarification_question": str(payload.get("clarification_question", "")).strip(),
    }
    trace_event(
        "router.model_route",
        module=result["module"],
        confidence=result["confidence"],
        reason=result["reason"],
        active_module=active_module,
        has_media=has_media,
    )
    return result


def build_local_clarification(top_module: str, second_module: str) -> str:
    pair = {top_module, second_module}
    if pair == {"post", "coach"}:
        return "Do you want post-processing advice, or should I switch to learning-coach mode?"
    if pair == {"coach", "plan"}:
        return "Do you want learning guidance, or a concrete shooting plan?"
    if pair == {"post", "plan"}:
        return "Do you want post-processing help for this image, or a plan for how to shoot?"
    if pair == {"post", "asset"}:
        return "Do you want to keep editing this image, or organize the asset set?"
    return "Which do you want next: post, coach, plan, or asset?"


def resolve_route(
    client: anthropic.Anthropic,
    user_input: str,
    profile: dict,
    task_history: list[dict],
    has_media: bool,
    active_module: str,
) -> dict:
    rule_result = score_route_by_rules(user_input, has_media, active_module)
    if rule_result["confidence"] >= ROUTER_MODEL_THRESHOLD:
        result = {
            "module": rule_result["module"],
            "confidence": rule_result["confidence"],
            "reason": "rule_match",
            "clarify": False,
            "question": "",
        }
        trace_event(
            "router.rule_route",
            module=result["module"],
            confidence=result["confidence"],
            active_module=active_module,
            has_media=has_media,
        )
        return result

    try:
        model_result = route_with_model(client, user_input, profile, task_history, has_media, active_module)
    except Exception as e:
        print(f"\n[路由] 模型路由失败（{type(e).__name__}: {e}），回退到规则路由。\n")
        ordered = sorted(rule_result["scores"].items(), key=lambda item: item[1], reverse=True)
        result = {
            "module": "",
            "confidence": 0.0,
            "reason": "rule_ambiguous",
            "clarify": True,
            "question": build_local_clarification(ordered[0][0], ordered[1][0]),
        }
        trace_event(
            "router.clarify",
            reason=result["reason"],
            active_module=active_module,
            has_media=has_media,
            question=result["question"],
        )
        return result

    if model_result["module"] == "clarify" or model_result["confidence"] < ROUTER_MODEL_THRESHOLD:
        ordered = sorted(rule_result["scores"].items(), key=lambda item: item[1], reverse=True)
        result = {
            "module": "",
            "confidence": model_result["confidence"],
            "reason": model_result["reason"],
            "clarify": True,
            "question": model_result["clarification_question"] or build_local_clarification(ordered[0][0], ordered[1][0]),
        }
        trace_event(
            "router.clarify",
            reason=result["reason"],
            active_module=active_module,
            has_media=has_media,
            question=result["question"],
        )
        return result

    result = {
        "module": model_result["module"],
        "confidence": model_result["confidence"],
        "reason": model_result["reason"],
        "clarify": False,
        "question": "",
    }
    trace_event(
        "router.selected_module",
        module=result["module"],
        confidence=result["confidence"],
        reason=result["reason"],
        active_module=active_module,
        has_media=has_media,
    )
    return result


def summarize_text(text: str, limit: int = 80) -> str:
    compact = re.sub(r"\s+", " ", str(text).strip())
    return compact[:limit] + ("..." if len(compact) > limit else "")


def normalize_media_path_key(path_text: str) -> str:
    return shared_normalize_media_path_key(path_text)


def split_selection_prompt(user_input: str) -> tuple[str, str]:
    return shared_split_selection_prompt(user_input)


def build_handoff_followup_prompt(destination: str, assets: list[dict], custom_prompt: str = "") -> str:
    return shared_build_handoff_followup_prompt(destination, assets, custom_prompt)


def build_handoff_selection_response(destination: str, assets: list[dict], note: str) -> str:
    return shared_build_handoff_selection_response(
        destination,
        assets,
        note,
        route_labels=ROUTE_LABELS,
    )


def resolve_handoff_selection(
    user_input: str,
    destination: str,
    assets: list[dict],
) -> dict:
    return shared_resolve_handoff_selection(
        user_input,
        destination,
        assets,
        media_request_parser=post_module.parse_media_request,
    )


def append_task_history(task_history: list[dict], module: str, summary: str, issues: list[str] | None = None) -> list[dict]:
    task_history.append(
        {
            "module": module,
            "summary": summarize_text(summary),
            "issues": [str(item).strip() for item in issues or [] if str(item).strip()][:3],
        }
    )
    return task_history[-10:]


def build_unimplemented_message(module: str, user_input: str) -> str:
    if module == "plan":
        return "已路由到拍摄规划，但当前代码路径还没有执行实现。"
    if module == "asset":
        return "已路由到素材管理，但当前代码路径还没有执行实现。"
    return f"当前路径还没有实现这个模块：{ROUTE_LABELS.get(module, module)}"


def print_banner(output: CLIOutput | None = None) -> None:
    render_main_banner(output or CLIOutput())


def print_help(output: CLIOutput | None = None) -> None:
    ui = output or CLIOutput()
    render_main_help(ui)
    post_module.print_input_format_tips(sink=ui.sink)


def resolve_promptless_media_default_module(media_request: dict | None) -> str:
    if media_request is None:
        return ""

    request_prompt = str(media_request.get("prompt", "")).strip()
    if request_prompt:
        return ""

    raw_paths = media_request.get("paths", []) or []
    paths = [path for path in raw_paths if isinstance(path, Path)]
    if not paths:
        return ""

    if all(path.is_dir() for path in paths):
        return "asset"
    if all(path.is_file() for path in paths):
        return "post"
    if any(path.is_dir() for path in paths):
        return "asset"
    return ""


def resolve_entry_module_override(
    preferred_module: str,
    user_input: str,
    media_request: dict | None,
) -> str:
    if preferred_module not in ROUTE_LABELS or media_request is None:
        return ""

    request_prompt = str(media_request.get("prompt", "")).strip()
    if preferred_module == "asset":
        return "asset"

    if not request_prompt:
        return preferred_module

    return ""


def build_media_request_from_current_context(
    user_input: str,
    active_module: str,
    post_state: dict,
    coach_state: dict,
    asset_state: dict,
) -> dict | None:
    if not post_module.references_current_media(user_input):
        return None

    if active_module == "asset":
        asset_paths = asset_module.resolve_asset_context_paths(asset_state)
        if asset_paths:
            return {
                "paths": asset_paths,
                "prompt": user_input.strip(),
            }

    state_candidates: list[dict] = []
    if active_module == "coach":
        state_candidates.extend([coach_state, post_state])
    else:
        state_candidates.extend([post_state, coach_state])

    for state in state_candidates:
        raw_paths = state.get("current_media_paths", []) or []
        paths = [Path(path_text) for path_text in raw_paths if str(path_text).strip()]
        existing_paths = [path for path in paths if path.exists()]
        if existing_paths:
            return {
                "paths": existing_paths,
                "prompt": user_input.strip(),
            }
    return None


def main(
    preferred_module: str = "",
    source_cli: str = "photo.py",
    sink: EventSink | None = None,
) -> None:
    ui = CLIOutput(sink)
    event_sink = ui.sink

    def print(*args, sep: str = " ", end: str = "\n", flush: bool = False) -> None:
        ui.print(*args, sep=sep, end=end, flush=flush)

    client = create_anthropic_client(source_cli=source_cli)
    profile = asset_module.ensure_asset_profile_fields(post_module.load_profile())
    first_run = True
    skills_knowledge = post_module.load_skills_knowledge()
    plan_skills_knowledge = plan_module.load_planning_skills_knowledge()
    entry_module = preferred_module if preferred_module in ROUTE_LABELS else ""

    post_messages: list = []
    coach_messages: list = []
    plan_messages: list = []
    current_asset_index: dict | None = None
    post_state = dict(post_module.DEFAULT_SESSION_STATE)
    coach_state = dict(coach_module.DEFAULT_COACH_SESSION_STATE)
    plan_state = dict(plan_module.DEFAULT_PLANNING_SESSION_STATE)
    asset_state = dict(asset_module.DEFAULT_ASSET_SESSION_STATE)
    active_module = entry_module
    task_history: list[dict] = []

    last_post_analysis = ""
    last_post_payload: dict = {}
    last_post_image_name = ""
    handoff_issues: list[str] = []
    pending_route_request: dict | None = None
    pending_handoff_request: PendingHandoffRequest | None = None

    print_banner(ui)
    print(
        "\n我会先理解你的意图，再把请求路由到后期辅助、学习教练、拍摄规划或素材管理。\n"
        "如果置信度不够高，我会先追问一个简短澄清问题。\n"
    )
    if source_cli != "photo.py" and entry_module:
        print(
            f"[统一入口] {source_cli} 现在会通过 photo.py 进入。"
            f"当前默认焦点：{ROUTE_LABELS.get(entry_module, entry_module)}。\n"
        )
    post_module.print_input_format_tips(sink=event_sink)

    while True:
        try:
            user_input = input("You: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n\n已退出，下次见。")
            break

        if not user_input:
            continue

        cmd = user_input.lower()

        if cmd in {"quit", "exit", "q", "退出"}:
            print("已退出，下次见。")
            break
        if cmd in {"help", "帮助", "?"}:
            print_help(ui)
            continue
        if cmd in {"profile", "档案", "我的档案"}:
            print(f"\n当前档案：\n{post_module.profile_summary(profile)}\n")
            continue
        if cmd in {"reset", "重置", "重新开始"}:
            profile = asset_module.ensure_asset_profile_fields(dict(post_module.DEFAULT_PROFILE))
            post_messages = []
            coach_messages = []
            plan_messages = []
            current_asset_index = None
            post_state = dict(post_module.DEFAULT_SESSION_STATE)
            coach_state = dict(coach_module.DEFAULT_COACH_SESSION_STATE)
            plan_state = dict(plan_module.DEFAULT_PLANNING_SESSION_STATE)
            asset_state = dict(asset_module.DEFAULT_ASSET_SESSION_STATE)
            last_post_analysis = ""
            last_post_payload = {}
            last_post_image_name = ""
            handoff_issues = []
            print("档案和短期上下文已重置。\n")
            pending_route_request = None
            pending_handoff_request = None
            active_module = entry_module
            post_module.save_profile(profile)

            continue
        if post_module.is_export_command(user_input):
            xmp_params = last_post_payload.get("xmp_params") or post_state.get("last_xmp_params")
            if last_post_analysis or xmp_params:
                post_module.offer_xmp_export(
                    xmp_params,
                    last_post_image_name,
                    analysis_text=last_post_analysis,
                )
            else:
                print("当前还没有可导出的后期预设，先完成一次后期分析。\n")
            continue

        if first_run and not post_module.is_profile_initialized(profile):
            profile = post_module.init_profile_interactive(profile)
            first_run = False
        first_run = False

        forced_module = ""
        media_request = None
        has_media = False
        skip_entry_module_override = False
        suppress_media_reset_notice = False
        plan_followup_prompt = ""
        resumed_from_handoff = False

        if pending_handoff_request:
            handoff_result = consume_pending_handoff_input(
                user_input,
                pending_handoff_request,
                route_labels=ROUTE_LABELS,
                media_request_parser=post_module.parse_media_request,
            )
            trace_event(
                "handoff.selection",
                status=handoff_result.get("status", ""),
                destination=pending_handoff_request.destination,
                asset_count=len(pending_handoff_request.assets),
            )
            if handoff_result["status"] == "cancel":
                pending_handoff_request = None
                print(f"\n{handoff_result['message']}\n")
                continue
            if handoff_result["status"] == "invalid":
                print(f"\n{handoff_result['message']}\n")
                continue

            media_request = handoff_result["media_request"]
            has_media = True
            forced_module = handoff_result.get("destination", "post")
            suppress_media_reset_notice = True
            resumed_from_handoff = True
            selected_assets = handoff_result.get("selected_assets", [])
            pending_handoff_request = None
            asset_state = asset_module.update_asset_session_state(
                asset_state,
                current_asset_index,
                handoff_destination=forced_module,
                handoff_paths=[asset.get("absolute_path", "") for asset in selected_assets],
                focus_paths=[asset.get("absolute_path", "") for asset in selected_assets],
            )
            trace_event(
                "handoff.accepted",
                destination=forced_module,
                asset_count=len(selected_assets),
            )
            selected_names = [Path(asset.get("absolute_path", "")).name for asset in selected_assets[:3]]
            if len(selected_assets) > 3:
                selected_names.append("...")
            destination_label = ROUTE_LABELS.get(forced_module, forced_module)
            print(
                f"\n[流转] 已选择 {len(selected_assets)} 张：{', '.join(selected_names)}。"
                f"接下来进入{destination_label}。"
            )
            user_input = media_request.get("prompt", user_input)
        else:
            media_request = post_module.parse_media_request(user_input)
            if media_request is None:
                media_request = build_media_request_from_current_context(
                    user_input,
                    active_module,
                    post_state,
                    coach_state,
                    asset_state,
                )
                if media_request is not None:
                    selected_names = [path.name for path in media_request["paths"][:3]]
                    if len(media_request["paths"]) > 3:
                        selected_names.append("...")
                    skip_entry_module_override = True
                    print(f"\n[提示] 已沿用当前图片上下文：{', '.join(selected_names)}。\n")
            has_media = media_request is not None

        if not forced_module:
            forced_module = resolve_promptless_media_default_module(media_request)

        if not forced_module and not skip_entry_module_override:
            forced_module = resolve_entry_module_override(entry_module, user_input, media_request)

        if pending_route_request and media_request is None:
            pending_media_request = pending_route_request.get("media_request")
            pending_user_input = pending_route_request.get("user_input", "")
            if pending_media_request is not None:
                merged_prompt = " | ".join(
                    part.strip()
                    for part in [
                        pending_media_request.get("prompt", ""),
                        user_input,
                    ]
                    if part and part.strip()
                )
                media_request = {
                    "paths": pending_media_request["paths"],
                    "prompt": merged_prompt,
                }
                has_media = True
                user_input = f"{pending_user_input}\n用户补充说明：{user_input}"
                print("\n[提示] 已把上一轮图片路径和这次补充说明合并。\n")
            pending_route_request = None
        elif pending_route_request and media_request is not None:
            pending_route_request = None

        if not forced_module and should_force_asset_followup(
            user_input,
            has_media,
            active_module,
            current_asset_index,
        ):
            forced_module = "asset"

        if not forced_module and plan_module.should_resume_planning_followup(
            user_input,
            plan_state,
            has_media,
        ):
            forced_module = "plan"
            plan_followup_prompt = plan_module.build_pending_plan_followup_request(user_input, plan_state)
            trace_event(
                "plan.followup_resumed",
                selection_prompt=plan_state.get("pending_selection_prompt", ""),
                user_input=user_input,
            )
            print("\n[提示] 已按上一轮拍摄规划继续细化方案。\n")

        if forced_module:
            module = forced_module
        else:
            route_info = resolve_route(
                client,
                user_input,
                profile,
                task_history,
                has_media,
                active_module,
            )
            if route_info["clarify"]:
                pending_route_request = {
                    "user_input": user_input,
                    "media_request": media_request,
                    "has_media": has_media,
                    "question": route_info["question"],
                }
                print(f"\n{route_info['question']}\n")
                continue

            module = route_info["module"]

        if module != "plan" and plan_module.has_pending_plan_followup(plan_state):
            plan_state = plan_module.clear_pending_plan_followup(plan_state)

        if module == "asset":
            has_project_path = media_request is not None

            if not has_project_path and post_module.looks_like_local_media_reference(user_input):
                print(
                    "\n[提示] 这看起来像本地路径，但没有被解析成项目路径或素材输入。\n"
                )
                post_module.print_input_format_tips(sink=event_sink)
                continue

            intent = asset_module.resolve_asset_intent(
                client,
                user_input,
                profile,
                asset_state,
                has_project_path,
                current_asset_index is not None,
            )
            profile = asset_module.update_profile_from_asset_intent(profile, intent)

            if intent.get("needs_project_path") and current_asset_index is None and not has_project_path:
                print(f"\n{intent.get('clarification_question')}\n")
                continue

            if has_project_path:
                request_paths = media_request["paths"]
                request_prompt = media_request["prompt"] or user_input
                should_inherit = (
                    post_module.has_context_carryover_intent(user_input) or
                    post_module.has_context_carryover_intent(request_prompt)
                )

                incoming_root = asset_module.detect_project_root(request_paths)
                current_signature = post_module.build_media_signature([incoming_root])
                previous_signature = []
                if asset_state.get("current_project_root"):
                    previous_signature = post_module.build_media_signature([Path(asset_state["current_project_root"])])

                if previous_signature and current_signature != previous_signature and not should_inherit:
                    current_asset_index = None
                    asset_state = dict(asset_module.DEFAULT_ASSET_SESSION_STATE)
                    print(
                        "\n[提示] 检测到新的项目路径，正在为新项目重建素材索引。\n"
                        "如果你想沿用之前的筛片或命名偏好，请再说一遍。\n"
                    )

                print("\n⏳ 正在扫描项目并建立索引…")
                try:
                    current_asset_index = asset_module.index_project_assets(
                        request_paths,
                        intent,
                        profile,
                        sink=event_sink,
                    )
                except ValueError as e:
                    print(f"\n错误：{e}\n")
                    continue
                except OSError as e:
                    print(f"\n读取项目失败：{e}\n")
                    continue

                cache_path = asset_module.save_project_index(current_asset_index)
                asset_state = asset_module.update_asset_session_state(
                    asset_state,
                    current_asset_index,
                    cache_path=cache_path,
                )
                response_text = asset_module.render_index_response(current_asset_index, cache_path)
                print(f"\n{response_text}\n")
                task_history = append_task_history(
                    task_history,
                    "asset",
                    current_asset_index.get("stats", {}).get("date_range", "") or response_text,
                )
                active_module = "asset"
                continue

            if current_asset_index is None and asset_state.get("last_index_cache"):
                current_asset_index = asset_module.load_project_index(asset_state["last_index_cache"])

            task_mode = intent.get("task_mode", "")

            if intent.get("culling_preference") and current_asset_index is not None and task_mode in {
                "show_grade_a", "show_grade_b", "show_grade_c", "show_highlights",
                "show_rejects", "show_duplicates", "show_suggestions", "asset_chat", "search_assets"
            }:
                current_asset_index = asset_module.rebuild_curation(
                    current_asset_index,
                    profile,
                    intent["culling_preference"],
                )
                cache_path = asset_module.save_project_index(current_asset_index)
                asset_state = asset_module.update_asset_session_state(
                    asset_state,
                    current_asset_index,
                    cache_path=cache_path,
                )

            if task_mode == "show_grade_a":
                if current_asset_index is None:
                    print("\n先导入一个项目文件夹，我才能给你看典藏列表。\n")
                    continue
                assets = asset_module.select_assets_by_grade(current_asset_index, "A")
                response_text = asset_module.render_asset_subset("典藏：", assets, "当前还没有明确的典藏作品。")
                print(f"\n{response_text}\n")
                task_history = append_task_history(task_history, "asset", response_text)
                active_module = "asset"
                continue

            if task_mode in {"show_grade_b", "show_highlights"}:
                if current_asset_index is None:
                    print("\n先导入一个项目文件夹，我才能给你看佳片列表。\n")
                    continue
                assets = asset_module.select_assets_by_grade(current_asset_index, "B")
                response_text = asset_module.render_asset_subset("佳片：", assets, "当前还没有明确的佳片。")
                print(f"\n{response_text}\n")
                task_history = append_task_history(task_history, "asset", response_text)
                active_module = "asset"
                continue

            if task_mode == "show_grade_c":
                if current_asset_index is None:
                    print("\n先导入一个项目文件夹，我才能给你看留存列表。\n")
                    continue
                assets = asset_module.select_assets_by_grade(current_asset_index, "C")
                response_text = asset_module.render_asset_subset("留存：", assets, "当前还没有明确的留存照片。")
                print(f"\n{response_text}\n")
                task_history = append_task_history(task_history, "asset", response_text)
                active_module = "asset"
                continue

            if task_mode == "show_rejects":
                if current_asset_index is None:
                    print("\n先导入一个项目文件夹，我才能给你看清理列表。\n")
                    continue
                assets = asset_module.select_assets_by_ids(current_asset_index, current_asset_index.get("reject_ids", []))
                response_text = asset_module.render_asset_subset("清理：", assets, "当前还没有明确的清理照片。")
                print(f"\n{response_text}\n")
                task_history = append_task_history(task_history, "asset", response_text)
                active_module = "asset"
                continue

            if task_mode == "show_duplicates":
                if current_asset_index is None:
                    print("\n先导入一个项目文件夹，我才能给你看重复片和相似片。\n")
                    continue
                duplicate_ids = [asset["id"] for asset in current_asset_index["assets"] if asset.get("duplicate_of")]
                assets = asset_module.select_assets_by_ids(current_asset_index, duplicate_ids)
                response_text = asset_module.render_asset_subset("重复片 / 相似片：", assets, "当前还没有明显的重复片。")
                print(f"\n{response_text}\n")
                task_history = append_task_history(task_history, "asset", response_text)
                active_module = "asset"
                continue

            if task_mode == "show_suggestions":
                if current_asset_index is None:
                    print("\n先导入一个项目文件夹，我才能给你生成命名、标签和归档建议。\n")
                    continue
                cache_path = asset_module.save_project_index(current_asset_index)
                asset_state = asset_module.update_asset_session_state(
                    asset_state,
                    current_asset_index,
                    cache_path=cache_path,
                )
                response_text = asset_module.render_index_response(current_asset_index, cache_path)
                print(f"\n{response_text}\n")
                task_history = append_task_history(task_history, "asset", response_text)
                active_module = "asset"
                continue

            if task_mode == "prepare_handoff":
                if current_asset_index is None:
                    print("\n先导入并筛出一轮素材，我才能帮你准备跨 Agent 流转入口。\n")
                    continue
                destination = intent.get("destination") or "post"
                assets, note = asset_module.prepare_handoff_assets(current_asset_index, destination)
                handoff_paths = [asset["absolute_path"] for asset in assets]
                asset_state = asset_module.update_asset_session_state(
                    asset_state,
                    current_asset_index,
                    handoff_destination=destination,
                    handoff_paths=handoff_paths,
                    handoff_assets=assets,
                    handoff_note=note,
                )
                response_text = build_handoff_selection_response(destination, assets, note)
                pending_handoff_request = create_pending_handoff_request(destination, assets, note)
                trace_event(
                    "handoff.prepared",
                    destination=destination,
                    asset_count=len(assets),
                )
                print(f"\n{response_text}\n")
                task_history = append_task_history(task_history, "asset", response_text)
                active_module = "asset"
                continue

            indexes = [current_asset_index] if current_asset_index is not None else asset_module.load_all_cached_indexes()
            if not indexes:
                print("\n当前还没有可搜索的项目索引。先给我一个项目文件夹，我会先帮你建库。\n")
                continue


            query = intent.get("search_query") or user_input
            filters = asset_module.parse_search_filters(client, indexes, query)
            results = asset_module.search_index_records(indexes, filters)
            asset_state = asset_module.update_asset_session_state(
                asset_state,
                current_asset_index if current_asset_index is not None else None,
                search_query=query,
                search_filters=filters,
                search_results=results,
            )
            response_text = asset_module.render_search_response(query, filters, results)
            print(f"\n{response_text}\n")
            task_history = append_task_history(task_history, "asset", response_text)
            active_module = "asset"
            continue

        if module == "plan":
            is_media_request = media_request is not None
            prepared_items: list[dict] = []
            expanded_paths: list[Path] = []
            request_prompt = user_input

            if not is_media_request and post_module.looks_like_local_media_reference(user_input):
                print(
                    "\n[提示] 这看起来像本地图片路径，但没有被解析成可读取的参考图输入。\n"
                )
                post_module.print_input_format_tips(sink=event_sink)
                continue

            if is_media_request:
                request_prompt = media_request["prompt"] or "请根据这些参考图生成拍摄规划。"
                request_paths = media_request["paths"]
                current_signature = post_module.build_media_signature(request_paths)
                previous_signature = list(plan_state.get("current_media_signature", []))
                should_inherit = (
                    post_module.has_context_carryover_intent(user_input) or
                    post_module.has_context_carryover_intent(request_prompt)
                )

                if previous_signature and current_signature != previous_signature and not should_inherit:
                    plan_messages = []
                    plan_state = dict(plan_module.DEFAULT_PLANNING_SESSION_STATE)
                    print(
                        "\n[提示] 检测到新的参考图，正在为新任务重建拍摄规划。\n"
                        "如果你想沿用上一轮地点或风格，请明确说明。\n"
                    )

                print("\n⏳ 正在读取参考图片…")
                try:
                    prepared_items, expanded_paths, _ = post_module.prepare_media_items(
                        request_paths,
                        sink=event_sink,
                    )
                except ValueError as e:
                    print(f"\n错误：{e}\n")
                    continue
                except OSError as e:
                    print(f"\n读取素材失败：{e}\n")
                    continue

                print(f"已读取 {len(prepared_items)} 张参考图，正在生成拍摄规划…")


            plan_messages = post_module.trim_context(plan_messages, profile, plan_state)
            effective_plan_input = request_prompt if is_media_request else (plan_followup_prompt or user_input)

            try:
                response_text, payload, brief = plan_module.run_planning_turn(
                    client,
                    profile,
                    plan_state,
                    plan_skills_knowledge,
                    plan_messages,
                    effective_plan_input,
                    media_items=prepared_items if is_media_request else None,
                    total_files=len(expanded_paths),
                    sink=event_sink,
                )
            except Exception as exc:
                if handle_api_error(exc):
                    continue
                raise

            if payload.get("needs_clarification"):
                print(f"\n{response_text}\n")
                continue

            plan_state = plan_module.update_planning_session_state(
                plan_state,
                request_prompt if is_media_request else user_input,
                brief,
                payload,
                media_request,
            )

            if is_media_request:
                uploaded_names = [path.name for path in media_request["paths"][:3]]
                if len(media_request["paths"]) > 3:
                    uploaded_names.append("...")
                plan_messages.append(
                    {
                        "role": "user",
                        "content": f"[已上传参考图] {', '.join(uploaded_names)} | 诉求: {request_prompt}",
                    }
                )
            else:
                plan_messages.append({"role": "user", "content": user_input})
                post_module.maybe_print_media_input_hint(user_input, sink=event_sink)

            plan_messages.append({"role": "assistant", "content": response_text})
            task_history = append_task_history(
                task_history,
                "plan",
                payload.get("summary", "") or response_text,
            )
            active_module = "plan"
            print()
            continue

        if module == "post":
            system = post_module.build_system_prompt(profile, skills_knowledge)
            is_media_request = media_request is not None
            prepared_items: list[dict] = []
            expanded_paths: list[Path] = []
            is_batch = False
            request_prompt = user_input


            if not is_media_request and post_module.looks_like_local_media_reference(user_input):
                print(
                    "\n[提示] 这看起来像本地图片路径，但没有被解析成可读取的图片输入。\n"
                )
                post_module.print_input_format_tips(sink=event_sink)
                continue

            if is_media_request:
                request_prompt = media_request["prompt"]
                request_paths = media_request["paths"]
                current_signature = post_module.build_media_signature(request_paths)
                previous_signature = list(post_state.get("current_media_signature", []))
                should_inherit = (
                    post_module.has_context_carryover_intent(user_input) or
                    post_module.has_context_carryover_intent(request_prompt)
                )

                if previous_signature and current_signature != previous_signature and not should_inherit:
                    post_messages = []
                    post_state = dict(post_module.DEFAULT_SESSION_STATE)
                    last_post_analysis = ""
                    last_post_payload = {}
                    last_post_image_name = ""
                    if not suppress_media_reset_notice:
                        print(
                            "\n[提示] 检测到新的图片，正在为新任务重置后期分析上下文。\n"
                            "如果你想沿用上一轮风格，请明确说明。\n"
                        )

                print("\n⏳ 正在读取图片并准备后期分析…")
                try:
                    prepared_items, expanded_paths, is_batch = post_module.prepare_media_items(
                        request_paths,
                        sink=event_sink,
                    )
                except ValueError as e:
                    print(f"\n错误：{e}\n")
                    retry_handoff = asset_module.resolve_retryable_handoff(asset_state)
                    if resumed_from_handoff and retry_handoff is not None:
                        destination, assets, note = retry_handoff
                        pending_handoff_request = create_pending_handoff_request(destination, assets, note)
                        response_text = build_handoff_selection_response(destination, assets, note)
                        print(
                            "\n[提示] 刚才选中的素材暂时无法读入。"
                            "你可以重新选择其他序号，或回复 cancel 取消这次流转。\n"
                        )
                        print(f"{response_text}\n")
                    continue
                except OSError as e:
                    print(f"\n读取素材失败：{e}\n")
                    continue

                if is_batch:
                    print(
                        f"已读取 {len(prepared_items)} 张分析样片（来自 {len(expanded_paths)} 个源文件），"
                        "正在生成整组后期方案…"
                    )
                else:
                    print("已读取图片，正在开始后期分析…")



            post_messages = post_module.trim_context(post_messages, profile, post_state)

            try:
                if is_media_request:
                    response_text, analysis_payload = post_module.analyze_photo_streaming(
                        client,
                        system,
                        post_messages,
                        prepared_items,
                        request_prompt,
                        len(expanded_paths),
                        is_batch,
                        sink=event_sink,
                    )
                    last_post_analysis = response_text
                    last_post_payload = analysis_payload

                    first_path = media_request["paths"][0]
                    last_post_image_name = (
                        f"{first_path.name}_batch" if is_batch and first_path.is_dir()
                        else f"{first_path.stem}_batch" if is_batch
                        else first_path.stem
                    )

                    post_state = post_module.update_session_state_from_analysis(
                        post_state,
                        request_prompt,
                        media_request,
                        analysis_payload,
                        is_batch,
                    )
                    handoff_issues = analysis_payload.get("main_issues", [])[:3]

                    if analysis_payload.get("xmp_params"):
                        print("-" * 60)
                        xmp_label = "整组统一" if is_batch else "当前结果"
                        print(
                            f"[预设] {xmp_label} 的 Lightroom 参数已准备好导出。"
                            "如果你要导出，直接说 xmp 或 preset。\n"
                        )
                    else:
                        print("-" * 60)
                        print("这次结果里还没有足够稳定的结构化参数，我先不建议直接导出预设。\n")
                else:
                    response_text = post_module.chat_streaming(
                        client,
                        system,
                        post_messages,
                        user_input,
                        sink=event_sink,
                    )
                    post_state = post_module.update_session_state_from_chat(post_state, user_input)
                    text_xmp_params = post_module.normalize_xmp_params(
                        post_module.extract_xmp_params_from_text(response_text)
                    )
                    if text_xmp_params:
                        last_post_analysis = response_text
                        last_post_payload = {**last_post_payload, "xmp_params": text_xmp_params}
                        post_state["last_xmp_params"] = text_xmp_params
                    post_module.maybe_print_media_input_hint(user_input, sink=event_sink)
            except Exception as exc:
                if handle_api_error(exc):
                    continue
                raise

            if is_media_request:
                request_summary = request_prompt or ("批量统一色调" if is_batch else "默认后期诊断")
                uploaded_names = [path.name for path in media_request["paths"][:3]]
                if len(media_request["paths"]) > 3:
                    uploaded_names.append("...")
                post_messages.append(
                    {
                        "role": "user",
                        "content": f"[已上传图片] {', '.join(uploaded_names)} | 诉求: {request_summary}",
                    }
                )
            else:
                post_messages.append({"role": "user", "content": user_input})
            post_messages.append({"role": "assistant", "content": response_text})

            summary_text = (
                last_post_payload.get("summary", "") if is_media_request
                else response_text
            )
            task_history = append_task_history(task_history, "post", summary_text, handoff_issues)
            active_module = "post"
            print()
            continue

        if module == "coach":
            effective_handoff_issues = (
                handoff_issues if active_module == "post" and handoff_issues
                else coach_state.get("last_handoff_issues", [])
            )
            system = coach_module.build_learning_system_prompt(
                profile,
                skills_knowledge,
                effective_handoff_issues,
            )

            is_media_request = media_request is not None
            prepared_items: list[dict] = []
            expanded_paths: list[Path] = []
            request_prompt = user_input

            if not is_media_request and post_module.looks_like_local_media_reference(user_input):
                print(
                    "\n[提示] 这看起来像本地图片路径，但没有被解析成可读取的图片输入。\n"
                )
                post_module.print_input_format_tips(sink=event_sink)
                continue


            if is_media_request:
                request_prompt = media_request["prompt"] or "请从学习教练角度点评这张作品"
                request_paths = media_request["paths"]
                current_signature = post_module.build_media_signature(request_paths)
                previous_signature = list(coach_state.get("current_media_signature", []))
                should_inherit = (
                    post_module.has_context_carryover_intent(user_input) or
                    post_module.has_context_carryover_intent(request_prompt)
                )

                if previous_signature and current_signature != previous_signature and not should_inherit:
                    coach_messages = []
                    coach_state = dict(coach_module.DEFAULT_COACH_SESSION_STATE)
                    if not suppress_media_reset_notice:
                        print(
                            "\n[提示] 检测到新的图片，正在为新任务重置学习教练上下文。\n"
                            "如果你想继续上一轮练习方向，请明确说明。\n"
                        )

                print("\n⏳ 正在读取图片并准备学习教练点评…")
                try:
                    prepared_items, expanded_paths, _ = post_module.prepare_media_items(
                        request_paths,
                        sink=event_sink,
                    )
                except ValueError as e:
                    print(f"\n错误：{e}\n")
                    continue
                except OSError as e:
                    print(f"\n读取素材失败：{e}\n")
                    continue

                print("已读取图片，学习教练正在开始点评…")
            coach_messages = post_module.trim_context(coach_messages, profile, coach_state)

            try:
                response_text, payload = coach_module.run_learning_coach_turn(
                    client,
                    system,
                    coach_messages,
                    request_prompt if is_media_request else user_input,
                    media_items=prepared_items if is_media_request else None,
                    total_files=len(expanded_paths),
                    handoff_issues=effective_handoff_issues,
                    sink=event_sink,
                )
            except Exception as exc:
                if handle_api_error(exc):
                    continue
                raise

            profile = coach_module.update_profile_from_coach_payload(
                profile,
                payload,
                request_prompt if is_media_request else user_input,
                media_request,
            )
            coach_state = coach_module.update_coach_session_state(
                coach_state,
                request_prompt if is_media_request else user_input,
                media_request,
                payload,
                handoff_issues=effective_handoff_issues,
            )

            if is_media_request:
                uploaded_names = [path.name for path in media_request["paths"][:3]]
                coach_messages.append(
                    {
                        "role": "user",
                        "content": f"[已上传作品] {', '.join(uploaded_names)} | 诉求: {request_prompt}",
                    }
                )
            else:
                coach_messages.append({"role": "user", "content": user_input})
            coach_messages.append({"role": "assistant", "content": response_text})

            if not is_media_request:
                post_module.maybe_print_media_input_hint(user_input, sink=event_sink)

            task_history = append_task_history(
                task_history,
                "coach",
                payload.get("summary", "") or payload.get("answer", "") or response_text,
                payload.get("weak_points", []),
            )
            active_module = "coach"
            print()
            continue


if __name__ == "__main__":
    main()






