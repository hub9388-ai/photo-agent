"""
摄影全栈 Agent — V2 学习教练模块（个性化反馈版）
================================================
功能：
  1. 作品点评（优点 2 条 + 改进点 2 条 + 下次练习建议 1 条）
  2. 技能水平识别（初学 / 进阶 / 专业）
  3. 个性化练习课题生成（场景 + 要求 + 验收标准）
  4. 摄影知识点问答（结合用户历史问题与作品上下文）
  5. 跨模块衔接（接收后期模块 issues 作为练习来源）
"""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime
from pathlib import Path

import anthropic

from photo_events import EventSink, ensure_event_sink
from photo_provider_adapter import search_reference_links as provider_search_reference_links
from photo_protocol import RESPONSE_DELIMITER, split_response_sections, stream_visible_response
from photo_runtime import create_anthropic_client
from photo_trace import trace_event
from photo_v1 import (
    MODEL,
    MAX_TOKENS_CHAT,
    DEFAULT_PROFILE,
    DEFAULT_SESSION_STATE,
    build_media_signature,
    collect_preview_notes,
    compact_note_text,
    extract_json_object,
    has_context_carryover_intent,
    init_profile_interactive,
    is_profile_initialized,
    load_profile,
    load_skills_knowledge,
    looks_like_local_media_reference,
    maybe_print_media_input_hint,
    parse_media_request,
    prepare_media_items,
    print_input_format_tips,
    profile_summary,
    save_profile,
    trim_context,
)


DEFAULT_COACH_SESSION_STATE = {
    **DEFAULT_SESSION_STATE,
    "last_skill_level": "",
    "last_weak_points": [],
    "last_exercise_title": "",
    "last_lesson_status": "",
    "last_active_lesson_title": "",
    "last_handoff_issues": [],
}

COACH_RESULT_HEADER = "学习教练结果："
COACH_FALLBACK_MESSAGE = "这轮我还没整理出稳定的学习建议，你可以换一种问法，我继续帮你拆。"
LESSON_STATUS_ORDER = {
    "assigned": 1,
    "in_progress": 2,
    "submitted": 3,
    "reviewed": 4,
    "completed": 5,
}
ACTIVE_LESSON_STATUSES = {"assigned", "in_progress", "submitted", "reviewed"}


def normalize_skill_level(text: str) -> str:
    normalized = str(text).strip()
    if not normalized:
        return ""

    mapping = {
        "初学": "初学",
        "入门": "初学",
        "新手": "初学",
        "beginner": "初学",
        "进阶": "进阶",
        "中级": "进阶",
        "intermediate": "进阶",
        "专业": "专业",
        "职业": "专业",
        "professional": "专业",
        "pro": "专业",
    }
    lowered = normalized.lower()
    for key, value in mapping.items():
        if key in lowered:
            return value
    return normalized


def normalize_weak_points(points: list[str] | None) -> list[str]:
    if not isinstance(points, list):
        return []

    normalized: list[str] = []
    seen: set[str] = set()
    for point in points:
        text = str(point).strip().lstrip("-").strip()
        if not text:
            continue
        key = re.sub(r"\s+", "", text.lower())
        if key in seen:
            continue
        seen.add(key)
        normalized.append(text)
    return normalized


def merge_weak_points(existing: list[str], incoming: list[str], limit: int = 8) -> list[str]:
    merged: list[str] = []
    seen: set[str] = set()

    for source in (incoming, existing):
        for item in source:
            text = str(item).strip()
            if not text:
                continue
            key = re.sub(r"\s+", "", text.lower())
            if key in seen:
                continue
            seen.add(key)
            merged.append(text)

    return merged[:limit]


def normalize_lesson_status(value: object) -> str:
    normalized = str(value or "").strip().lower()
    if not normalized:
        return ""

    mapping = {
        "assigned": "assigned",
        "assign": "assigned",
        "in_progress": "in_progress",
        "in progress": "in_progress",
        "started": "in_progress",
        "start": "in_progress",
        "submitted": "submitted",
        "submit": "submitted",
        "reviewed": "reviewed",
        "review": "reviewed",
        "completed": "completed",
        "complete": "completed",
        "done": "completed",
    }
    return mapping.get(normalized, "")


def lesson_title_key(title: object) -> str:
    return re.sub(r"\s+", "", str(title or "").strip().lower())


def build_lesson_history_summary(profile: dict, limit: int = 3) -> str:
    history = profile.get("lesson_history", [])
    if not isinstance(history, list) or not history:
        return "- No tracked lessons yet."

    lines: list[str] = []
    for item in history[:limit]:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title", "")).strip() or "Untitled lesson"
        status = normalize_lesson_status(item.get("status", "")) or "assigned"
        scene = str(item.get("scene", "")).strip()
        status_text = status.replace("_", " ")
        if scene:
            lines.append(f"- {title} | status: {status_text} | scene: {scene}")
        else:
            lines.append(f"- {title} | status: {status_text}")

    return "\n".join(lines) if lines else "- No tracked lessons yet."


def find_lesson_index(lesson_history: list[dict], target_title: object = "") -> int | None:
    normalized_target = lesson_title_key(target_title)
    if normalized_target:
        for index, lesson in enumerate(lesson_history):
            if lesson_title_key(lesson.get("title", "")) == normalized_target:
                return index

    for index, lesson in enumerate(lesson_history):
        if normalize_lesson_status(lesson.get("status", "")) in ACTIVE_LESSON_STATUSES:
            return index
    return 0 if lesson_history else None


def upsert_assigned_lesson(lesson_history: list[dict], next_exercise: dict) -> list[dict]:
    title = str(next_exercise.get("title", "")).strip()
    if not title:
        return lesson_history

    now_text = datetime.now().strftime("%Y-%m-%d")
    history = [dict(item) for item in lesson_history if isinstance(item, dict)]
    target_key = lesson_title_key(title)

    for index, lesson in enumerate(history):
        if lesson_title_key(lesson.get("title", "")) != target_key:
            continue
        if normalize_lesson_status(lesson.get("status", "")) == "completed":
            break

        lesson["title"] = title
        lesson["scene"] = str(next_exercise.get("scene", "")).strip()
        lesson["requirements"] = [
            str(item).strip()
            for item in next_exercise.get("requirements", [])
            if str(item).strip()
        ][:4]
        lesson["acceptance"] = [
            str(item).strip()
            for item in next_exercise.get("acceptance", [])
            if str(item).strip()
        ][:3]
        lesson["source"] = "learning_coach"
        lesson["assigned_at"] = lesson.get("assigned_at") or now_text
        lesson["date"] = lesson.get("date") or now_text
        history[index] = lesson
        return history[:12]

    history.insert(
        0,
        {
            "date": now_text,
            "title": title,
            "scene": str(next_exercise.get("scene", "")).strip(),
            "requirements": [
                str(item).strip()
                for item in next_exercise.get("requirements", [])
                if str(item).strip()
            ][:4],
            "acceptance": [
                str(item).strip()
                for item in next_exercise.get("acceptance", [])
                if str(item).strip()
            ][:3],
            "source": "learning_coach",
            "status": "assigned",
            "assigned_at": now_text,
        },
    )
    return history[:12]


def infer_lesson_status_update(
    user_text: str,
    media_request: dict | None,
    payload: dict,
    lesson_history: list[dict],
) -> str:
    explicit = normalize_lesson_status(payload.get("lesson_status_update", ""))
    if explicit:
        return explicit

    if not lesson_history:
        return ""

    text = str(user_text or "").strip().lower()
    if media_request and lesson_history:
        return "reviewed"

    start_keywords = (
        "开始",
        "练习",
        "执行",
        "去拍",
        "start",
        "practice",
        "working on",
        "current lesson",
    )
    if any(keyword in text for keyword in start_keywords):
        return "in_progress"

    return ""


def apply_lesson_status_update(
    lesson_history: list[dict],
    status_update: str,
    payload: dict,
    user_text: str,
    media_request: dict | None,
) -> list[dict]:
    normalized_status = normalize_lesson_status(status_update)
    if not normalized_status or not lesson_history:
        return lesson_history[:12]

    history = [dict(item) for item in lesson_history if isinstance(item, dict)]
    target_title = (
        str(payload.get("lesson_target_title", "")).strip()
        or str(payload.get("next_exercise", {}).get("title", "")).strip()
    )
    target_index = find_lesson_index(history, target_title)
    if target_index is None:
        return history[:12]

    lesson = history[target_index]
    current_status = normalize_lesson_status(lesson.get("status", "")) or "assigned"
    if LESSON_STATUS_ORDER.get(normalized_status, 0) < LESSON_STATUS_ORDER.get(current_status, 0):
        normalized_status = current_status

    now_text = datetime.now().strftime("%Y-%m-%d")
    review_note = (
        str(payload.get("lesson_review_note", "")).strip()
        or str(payload.get("summary", "")).strip()
        or str(payload.get("answer", "")).strip()
        or str(user_text or "").strip()
    )

    if normalized_status in {"submitted", "reviewed", "completed"}:
        lesson["submitted_at"] = lesson.get("submitted_at") or now_text

    if normalized_status == "in_progress":
        lesson["started_at"] = lesson.get("started_at") or now_text
    if normalized_status in {"reviewed", "completed"}:
        lesson["reviewed_at"] = now_text
        lesson["last_review_note"] = review_note[:240]
    if normalized_status == "completed":
        lesson["completed_at"] = now_text

    if media_request:
        lesson["latest_submission_count"] = len(media_request.get("paths", []))

    lesson["status"] = normalized_status
    history[target_index] = lesson
    return history[:12]


def build_learning_system_prompt(
    profile: dict,
    skills_knowledge: str = "",
    handoff_issues: list[str] | None = None,
) -> str:
    handoff_text = "；".join(str(item).strip() for item in handoff_issues or [] if str(item).strip()) or "无"
    summary = profile_summary(profile)
    lesson_summary = build_lesson_history_summary(profile)

    system = f"""# 用户档案摘要
{summary}

---

# 当前模块：学习教练

你是用户的摄影学习教练，也是同一个摄影助手的“成长反馈能力”。
你的目标不是只告诉用户“哪里有问题”，而是帮助用户知道“下一步该练什么、怎么进步”。

说话风格要求：
- 像真人导师，不输出评分表，不机械打分
- 语气温和、具体、有行动建议
- 点评时优先写清楚看到了什么，而不是堆术语
- 同一轮里只给最关键的成长建议，不要铺得太散

能力边界：
- 作品点评：输出优点 2 条、改进点 2 条、下次练习建议 1 条
- 技能水平识别：根据用户自述、历史表现和当前作品判断初学 / 进阶 / 专业
- 个性化练习课题：给出具体场景、拍摄要求、验收标准
- 知识点问答：讲清概念，并尽量结合用户刚才的照片或常见拍摄场景举例
- 跨模块衔接：如果收到后期模块交接问题，要自然生成交接语，让用户感知这是同一个助手在切换能力

重要规则：
- 禁止输出“构图 7 分 / 曝光 6 分”这类评分
- weak_points 必须写得具体，例如“地平线倾斜频繁（最近 3 次点评均出现）”，不要写“构图不好”
- 练习课题必须具体到场景、要求、验收标准，不能只说“多练习构图”
- 如果用户问知识点，优先用他当前照片、最近问题或常拍题材举例，不要只给抽象定义
- 如果收到后期模块交接问题，仅把 issues 当作成长线索，不要把完整后期对话复述给用户

当前可用的跨模块交接 issues：
{handoff_text}

---

# 摄影知识参考库

以下知识来自本地 Skills，仅作为专业参考，不要原样复读：
{skills_knowledge or "（当前无额外 skills 知识）"}
"""
    system += f"""

---

# Lesson Tracking
Tracked lessons:
{lesson_summary}

If this turn starts, submits, reviews, or completes an existing lesson, include:
- "lesson_status_update": "none | in_progress | submitted | reviewed | completed"
- "lesson_target_title": "optional lesson title"
- "lesson_review_note": "optional short note for lesson history"

When you assign a new exercise, keep using next_exercise as the source of truth.
Use "completed" only when the user's submission clearly meets the acceptance criteria.
"""
    return system


def build_learning_instruction(
    user_text: str,
    media_items: list[dict] | None = None,
    total_files: int = 0,
    handoff_issues: list[str] | None = None,
) -> str:
    media_items = media_items or []
    preview_notes = collect_preview_notes(media_items)
    preprocess_summary = "；".join(preview_notes) if preview_notes else "无"
    handoff_text = "；".join(str(item).strip() for item in handoff_issues or [] if str(item).strip()) or "无"

    if media_items:
        sample_lines = "\n".join(
            f"- 样本 {idx}: 原始文件 {item['label']}；实际分析来源 {item['source_label']}；预处理说明 {item.get('preview_note') or '无'}"
            for idx, item in enumerate(media_items, 1)
        )
    else:
        sample_lines = "- 本轮没有上传图片，请根据文字需求做学习指导"

    return f"""用户诉求：{user_text.strip() or "请给我学习上的建议"}
是否上传图片：{"是" if media_items else "否"}
样本数：{len(media_items)}（原始素材总数：{total_files}）
预处理提示：{preprocess_summary}
跨模块交接 issues：{handoff_text}
样本说明：
{sample_lines}

请严格按下面顺序输出，不要省略分隔符，也不要输出 Markdown 代码块：
第一部分：先直接写给用户看的自然中文正文，内容要和后面的结构化 JSON 保持一致，不要出现 JSON 字段名。
第二部分：单独一行原样输出 {RESPONSE_DELIMITER}
第三部分：再输出一个 JSON 对象，字段如下：
{{
  "task_mode": "critique | skill_assessment | exercise_plan | concept_qa | coaching_chat",
  "handoff_line": "可选，跨模块切换时的自然交接语",
  "summary": "可选，1~2 句整体判断",
  "strengths": ["优点1", "优点2"],
  "improvements": ["改进点1", "改进点2"],
  "next_exercise": {{
    "title": "本周课题标题",
    "scene": "场景说明",
    "requirements": ["要求1", "要求2", "要求3"],
    "acceptance": ["验收标准1", "验收标准2"]
  }},
  "skill_level": "初学 | 进阶 | 专业",
  "weak_points": ["具体薄弱项观察1", "具体薄弱项观察2"],
  "answer": "知识点问答或补充解释",
  "reference_query": "可选，仅在知识点问答时给一个适合搜索参考作品的关键词",
  "visible_response": "可选，仅当上方正文缺失或明显不完整时作为兜底文本"
}}

规则：
0. 分隔符必须单独占一行，并且完全等于 {RESPONSE_DELIMITER}。
1. 点评任务时，strengths 固定给 2 条，improvements 固定给 2 条，next_exercise 固定给 1 个。
2. 不输出分数，不输出“构图 7 分”这类评分表。
3. next_exercise 必须具体到场景、拍摄要求、验收标准。
4. skill_level 只允许使用“初学 / 进阶 / 专业”之一；不确定时可留空。
5. weak_points 必须具体可观察，不要写空泛结论。
6. 如果用户问知识点，answer 要先讲清概念，再尽量结合用户当前照片、最近问题或常拍题材举例。
7. 如果收到跨模块交接 issues，且当前任务和“练习 / 提高 / 成长”有关，handoff_line 要先自然承接，再进入建议。
8. 如果预处理提示里提到压缩预览或替代预览，不要对极细节做过度确定判断。
9. 每条 strengths / improvements 建议控制在 1~2 句话，先给结论，再解释原因或下一步做法。
10. JSON 字符串内部不要使用未转义的英文双引号；需要强调词语时使用中文引号「」或单引号。
"""


COACH_PAYLOAD_KEYS = [
    "task_mode",
    "handoff_line",
    "summary",
    "strengths",
    "improvements",
    "next_exercise",
    "skill_level",
    "weak_points",
    "answer",
    "reference_query",
    "reference_links",
    "lesson_status_update",
    "lesson_target_title",
    "lesson_review_note",
    "visible_response",
]


def strip_loose_string(segment: str) -> str:
    text = segment.strip().rstrip(",").strip()
    while text.endswith(("}", "]")):
        text = text[:-1].rstrip().rstrip(",").strip()
    if text.startswith('"'):
        text = text[1:]
    if text.endswith('"'):
        text = text[:-1]
    return text.replace('\\"', '"').strip()


def extract_loose_field(text: str, key: str, known_keys: list[str] | None = None) -> str:
    if known_keys is None:
        known_keys = COACH_PAYLOAD_KEYS
    match = re.search(rf'(?m)^\s*"{re.escape(key)}"\s*:', text)
    if not match:
        return ""

    start = match.end()
    end = len(text)
    for next_key in known_keys:
        if next_key == key:
            continue
        next_match = re.search(rf'(?m)^\s*"{re.escape(next_key)}"\s*:', text[start:])
        if next_match:
            end = min(end, start + next_match.start())

    return text[start:end].strip().rstrip(",").strip()


def parse_loose_string_array(segment: str) -> list[str]:
    text = segment.strip().rstrip(",").strip()
    if not text:
        return []

    try:
        parsed = json.loads(text)
        if isinstance(parsed, list):
            return [str(item).strip() for item in parsed if str(item).strip()]
    except json.JSONDecodeError:
        pass

    if text.startswith("["):
        text = text[1:]
    if text.endswith("]"):
        text = text[:-1]

    items: list[str] = []
    current_lines: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line in {"]", "],", "}", "},"}:
            continue
        current_lines.append(line)
        if line.endswith('",') or line.endswith('"'):
            item = " ".join(current_lines).strip().rstrip(",").strip()
            cleaned = strip_loose_string(item)
            if cleaned and cleaned not in {"]", "}", "],", "},"}:
                items.append(cleaned)
            current_lines = []

    if current_lines:
        cleaned = strip_loose_string(" ".join(current_lines))
        if cleaned and cleaned not in {"]", "}", "],", "},"}:
            items.append(cleaned)

    if len(items) <= 1 and '","' in text:
        items = [
            strip_loose_string(part)
            for part in re.split(r'"\s*,\s*"', text.strip().strip('"'))
            if strip_loose_string(part)
        ]

    return items


def parse_loose_coach_payload(raw_text: str) -> dict:
    start = raw_text.find("{")
    end = raw_text.rfind("}")
    if start != -1 and end != -1 and end > start:
        text = raw_text[start:end + 1]
    else:
        text = raw_text

    next_exercise_text = extract_loose_field(
        text,
        "next_exercise",
        [
            "skill_level",
            "weak_points",
            "answer",
            "reference_query",
            "reference_links",
            "lesson_status_update",
            "lesson_target_title",
            "lesson_review_note",
            "visible_response",
        ],
    )
    next_exercise = {
        "title": strip_loose_string(extract_loose_field(next_exercise_text, "title", ["scene", "requirements", "acceptance"])),
        "scene": strip_loose_string(extract_loose_field(next_exercise_text, "scene", ["requirements", "acceptance"])),
        "requirements": parse_loose_string_array(
            extract_loose_field(next_exercise_text, "requirements", ["acceptance"])
        ),
        "acceptance": parse_loose_string_array(
            extract_loose_field(next_exercise_text, "acceptance", [])
        ),
    }

    payload = {
        "task_mode": strip_loose_string(extract_loose_field(text, "task_mode")),
        "handoff_line": strip_loose_string(extract_loose_field(text, "handoff_line")),
        "summary": strip_loose_string(extract_loose_field(text, "summary")),
        "strengths": parse_loose_string_array(extract_loose_field(text, "strengths")),
        "improvements": parse_loose_string_array(extract_loose_field(text, "improvements")),
        "next_exercise": next_exercise,
        "skill_level": strip_loose_string(extract_loose_field(text, "skill_level")),
        "weak_points": parse_loose_string_array(extract_loose_field(text, "weak_points")),
        "answer": strip_loose_string(extract_loose_field(text, "answer")),
        "reference_query": strip_loose_string(extract_loose_field(text, "reference_query")),
        "reference_links": [],
        "lesson_status_update": strip_loose_string(extract_loose_field(text, "lesson_status_update")),
        "lesson_target_title": strip_loose_string(extract_loose_field(text, "lesson_target_title")),
        "lesson_review_note": strip_loose_string(extract_loose_field(text, "lesson_review_note")),
        "visible_response": strip_loose_string(extract_loose_field(text, "visible_response")),
    }

    has_content = any(
        payload.get(key)
        for key in ("summary", "strengths", "improvements", "answer", "visible_response")
    ) or any(next_exercise.values())
    if not has_content:
        raise ValueError("无法解析学习教练结构化结果")
    return payload


def parse_coach_payload(raw_text: str) -> dict:
    try:
        payload = extract_json_object(raw_text)
    except (ValueError, json.JSONDecodeError):
        trace_event("parser.coach_payload.fallback", parser="loose_json", reason="extract_json_object_failed")
        payload = parse_loose_coach_payload(raw_text)

    next_exercise = payload.get("next_exercise", {})
    if not isinstance(next_exercise, dict):
        next_exercise = {}

    reference_links = payload.get("reference_links", [])
    if not isinstance(reference_links, list):
        reference_links = []

    return {
        "task_mode": str(payload.get("task_mode", "")).strip(),
        "handoff_line": str(payload.get("handoff_line", "")).strip(),
        "summary": str(payload.get("summary", "")).strip(),
        "strengths": [str(item).strip() for item in payload.get("strengths", []) if str(item).strip()],
        "improvements": [str(item).strip() for item in payload.get("improvements", []) if str(item).strip()],
        "next_exercise": {
            "title": str(next_exercise.get("title", "")).strip(),
            "scene": str(next_exercise.get("scene", "")).strip(),
            "requirements": [
                str(item).strip() for item in next_exercise.get("requirements", []) if str(item).strip()
            ],
            "acceptance": [
                str(item).strip() for item in next_exercise.get("acceptance", []) if str(item).strip()
            ],
        },
        "skill_level": normalize_skill_level(payload.get("skill_level", "")),
        "weak_points": normalize_weak_points(payload.get("weak_points", [])),
        "answer": str(payload.get("answer", "")).strip(),
        "reference_query": str(payload.get("reference_query", "")).strip(),
        "reference_links": [
            {
                "title": str(item.get("title", "")).strip(),
                "url": str(item.get("url", "")).strip(),
            }
            for item in reference_links
            if isinstance(item, dict) and str(item.get("title", "")).strip() and str(item.get("url", "")).strip()
        ],
        "lesson_status_update": normalize_lesson_status(payload.get("lesson_status_update", "")),
        "lesson_target_title": str(payload.get("lesson_target_title", "")).strip(),
        "lesson_review_note": str(payload.get("lesson_review_note", "")).strip(),
        "visible_response": str(payload.get("visible_response", "")).strip(),
    }


def build_reference_links_block(reference_links: list[dict]) -> str:
    if not reference_links:
        return ""

    lines = ["参考作品："]
    for item in reference_links[:3]:
        lines.append(f"- {item['title']}：{item['url']}")
    return "\n".join(lines).strip()


def stream_learning_visible_response(
    client: anthropic.Anthropic,
    system: str,
    current_messages: list,
    sink: EventSink | None = None,
) -> tuple[str, str]:
    event_sink = ensure_event_sink(sink)
    event_sink.line()
    event_sink.line(COACH_RESULT_HEADER)
    event_sink.line()
    return stream_visible_response(
        client,
        model=MODEL,
        max_tokens=MAX_TOKENS_CHAT,
        system=system,
        messages=current_messages,
        anchor_keys=("task_mode", "summary", "strengths", "improvements", "next_exercise"),
        sink=event_sink,
    )


def search_reference_links(query: str, limit: int = 3) -> list[dict]:
    return provider_search_reference_links(query, limit=limit)


def render_coach_response(payload: dict) -> str:
    lines: list[str] = []

    handoff_line = payload.get("handoff_line", "").strip()
    if handoff_line:
        lines.append(handoff_line)

    summary = payload.get("summary", "").strip()
    if summary:
        if lines:
            lines.append("")
        lines.append("整体判断：")
        lines.append(summary)

    strengths = payload.get("strengths", [])
    if strengths:
        if lines:
            lines.append("")
        lines.append("做得好的地方：")
        lines.extend(f"{idx}. {item}" for idx, item in enumerate(strengths[:2], 1))

    improvements = payload.get("improvements", [])
    if improvements:
        if lines:
            lines.append("")
        lines.append("优先改进：")
        lines.extend(f"{idx}. {item}" for idx, item in enumerate(improvements[:2], 1))

    answer = payload.get("answer", "").strip()
    if answer:
        if lines:
            lines.append("")
        lines.append("讲解：")
        lines.append(answer)

    next_exercise = payload.get("next_exercise", {})
    if any(next_exercise.values()):
        if lines:
            lines.append("")
        lines.append("下次练习：")
        if next_exercise.get("title"):
            lines.append(f"课题：{next_exercise['title']}")
        if next_exercise.get("scene"):
            lines.append(f"场景：{next_exercise['scene']}")
        requirements = next_exercise.get("requirements", [])[:3]
        if requirements:
            lines.append("拍摄要求：")
            lines.extend(f"- {item}" for item in requirements)
        acceptance = next_exercise.get("acceptance", [])[:2]
        if acceptance:
            lines.append("验收标准：")
            lines.extend(f"- {item}" for item in acceptance)

    skill_level = payload.get("skill_level", "").strip()
    weak_points = payload.get("weak_points", [])
    if skill_level or weak_points:
        if lines:
            lines.append("")
        lines.append("成长档案：")
        if skill_level:
            lines.append(f"- 当前水平：{skill_level}")
        for item in weak_points[:3]:
            lines.append(f"- 需要持续关注：{item}")


    reference_links = payload.get("reference_links", [])
    if reference_links:
        if lines:
            lines.append("")
        lines.append("参考作品：")
        for item in reference_links[:3]:
            lines.append(f"- {item['title']}：{item['url']}")

    if not lines:
        return payload.get("visible_response", "").strip()
    return "\n".join(lines).strip()


def update_profile_from_coach_payload(
    profile: dict,
    payload: dict,
    user_text: str = "",
    media_request: dict | None = None,
) -> dict:
    updated = {**DEFAULT_PROFILE, **profile}

    skill_level = normalize_skill_level(payload.get("skill_level", ""))
    if skill_level:
        updated["skill_level"] = skill_level

    updated["weak_points"] = merge_weak_points(
        updated.get("weak_points", []),
        payload.get("weak_points", []),
    )

    lesson_history = list(updated.get("lesson_history", []))
    next_exercise = payload.get("next_exercise", {})
    if next_exercise.get("title"):
        lesson_history = upsert_assigned_lesson(lesson_history, next_exercise)

    status_update = infer_lesson_status_update(user_text, media_request, payload, lesson_history)
    if status_update:
        lesson_history = apply_lesson_status_update(
            lesson_history,
            status_update,
            payload,
            user_text,
            media_request,
        )

    updated["lesson_history"] = lesson_history[:12]
    trace_event(
        "coach.lesson_history.updated",
        active_title=(lesson_history[0].get("title", "") if lesson_history else ""),
        active_status=(lesson_history[0].get("status", "") if lesson_history else ""),
        total_lessons=len(lesson_history),
    )

    save_profile(updated)
    return updated


def update_coach_session_state(
    session_state: dict,
    user_text: str,
    media_request: dict | None,
    payload: dict,
    handoff_issues: list[str] | None = None,
) -> dict:
    updated = {**DEFAULT_COACH_SESSION_STATE, **session_state}
    updated["current_task_mode"] = payload.get("task_mode", "").strip() or "learning_coach"
    updated["current_goal"] = user_text.strip()
    updated["last_summary"] = payload.get("summary", "").strip() or payload.get("answer", "").strip()[:120]
    updated["confirmed_adjustments"] = payload.get("improvements", [])[:3]
    updated["last_source_note"] = compact_note_text("；".join(handoff_issues or []))
    updated["last_skill_level"] = normalize_skill_level(payload.get("skill_level", ""))
    updated["last_weak_points"] = payload.get("weak_points", [])[:4]
    updated["last_handoff_issues"] = list(handoff_issues or [])[:4]

    next_exercise = payload.get("next_exercise", {})
    updated["last_exercise_title"] = next_exercise.get("title", "").strip()
    updated["last_lesson_status"] = (
        payload.get("lesson_status_update", "").strip()
        or ("assigned" if next_exercise.get("title") else "")
    )
    updated["last_active_lesson_title"] = (
        payload.get("lesson_target_title", "").strip()
        or next_exercise.get("title", "").strip()
    )

    if media_request:
        subject_names = [path.name for path in media_request.get("paths", [])[:3]]
        if len(media_request.get("paths", [])) > 3:
            subject_names.append("...")
        updated["current_subject"] = ", ".join(subject_names)
        updated["current_media_paths"] = [str(path) for path in media_request.get("paths", [])]
        updated["current_media_signature"] = build_media_signature(media_request.get("paths", []))

    return updated


def run_learning_coach_turn(
    client: anthropic.Anthropic,
    system: str,
    messages: list,
    user_text: str,
    media_items: list[dict] | None = None,
    total_files: int = 0,
    handoff_issues: list[str] | None = None,
    sink: EventSink | None = None,
) -> tuple[str, dict]:
    event_sink = ensure_event_sink(sink)
    media_items = media_items or []

    content: list[dict] = []
    for idx, item in enumerate(media_items, 1):
        content.append(
            {
                "type": "text",
                "text": (
                    f"样本 {idx}：原始文件 {item['label']}；"
                    f"实际分析来源 {item['source_label']}；"
                    f"预处理说明 {item.get('preview_note') or '无'}"
                ),
            }
        )
        content.append(
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": item["media_type"],
                    "data": item["data"],
                },
            }
        )

    content.append(
        {
            "type": "text",
            "text": build_learning_instruction(user_text, media_items, total_files, handoff_issues),
        }
    )

    current_messages = messages + [{"role": "user", "content": content}]
    streamed_visible_response, raw_text = stream_learning_visible_response(
        client,
        system,
        current_messages,
        sink=event_sink,
    )

    _, payload_text, has_structured_tail = split_response_sections(
        raw_text,
        anchor_keys=("task_mode", "summary", "strengths", "improvements", "next_exercise"),
    )
    payload_source = payload_text if has_structured_tail else raw_text

    try:
        payload = parse_coach_payload(payload_source)
    except (ValueError, json.JSONDecodeError) as exc:
        trace_event("parser.coach_payload.failed", error=str(exc))
        payload = {
            "task_mode": "",
            "handoff_line": "",
            "summary": "",
            "strengths": [],
            "improvements": [],
            "next_exercise": {"title": "", "scene": "", "requirements": [], "acceptance": []},
            "skill_level": "",
            "weak_points": [],
            "answer": "",
            "reference_query": "",
            "reference_links": [],
            "lesson_status_update": "",
            "lesson_target_title": "",
            "lesson_review_note": "",
            "visible_response": streamed_visible_response or raw_text,
        }

    if payload.get("reference_query") and not payload.get("reference_links"):
        payload["reference_links"] = search_reference_links(payload["reference_query"])

    visible_response = streamed_visible_response or render_coach_response(payload) or (
        raw_text or COACH_FALLBACK_MESSAGE
    )

    reference_block = ""
    if payload.get("reference_links"):
        urls = [item["url"] for item in payload["reference_links"][:3]]
        if not streamed_visible_response or not any(url in visible_response for url in urls):
            reference_block = build_reference_links_block(payload["reference_links"])

    if not streamed_visible_response:
        event_sink.line(visible_response)
        event_sink.line()
    elif reference_block:
        event_sink.line(reference_block)
        event_sink.line()
        visible_response = f"{visible_response}\n\n{reference_block}"

    return visible_response, payload


def print_banner() -> None:
    print("=" * 60)
    print("  📚  摄影全栈 Agent — V2 学习教练模块")
    print("  支持作品点评、技能水平识别、练习课题生成与摄影知识讲解")
    print("  可上传图片做成长点评，也可直接问“怎么提高”“景深是什么”")
    print("=" * 60)


def print_help() -> None:
    print("""
可用命令：
  [图片路径]                      点评这张作品的成长价值
  "图片路径" 这张图我该练什么        基于作品给出练习建议
  我现在算什么水平？                识别当前技能水平
  给我一个本周练习课题              生成个性化训练任务
  白平衡 / 景深 / 区域曝光是什么？    结合你的作品语境解释摄影概念
  profile      查看当前用户档案
  reset        重置用户档案
  quit / exit  退出程序
""")
    print_input_format_tips()


def legacy_standalone_main() -> None:
    client = create_anthropic_client(source_cli="photo_v2.py")
    profile = load_profile()
    coach_messages: list = []
    coach_state = dict(DEFAULT_COACH_SESSION_STATE)
    first_run = True
    skills_knowledge = load_skills_knowledge()

    print_banner()
    print(
        "\n💬 你好！我现在除了能看作品问题，还能帮你拆成长重点、判断水平和布置练习课题。\n"
    )
    print_input_format_tips()

    while True:
        try:
            user_input = input("你：").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n\n再见！下次把新作品带来，我继续陪你练。")
            break

        if not user_input:
            continue

        cmd = user_input.lower()
        if cmd in {"quit", "exit", "q", "退出"}:
            print("再见！下次把新作品带来，我继续陪你练。")
            break
        if cmd in {"help", "帮助", "?"}:
            print_help()
            continue
        if cmd in {"profile", "档案", "我的档案"}:
            print(f"\n📋 当前用户档案：\n{profile_summary(profile)}\n")
            continue
        if cmd in {"reset", "重置", "重新填写"}:
            profile = dict(DEFAULT_PROFILE)
            coach_state = dict(DEFAULT_COACH_SESSION_STATE)
            coach_messages = []
            save_profile(profile)
            print("档案已重置，下次对话时重新填写。\n")
            continue

        if first_run and not is_profile_initialized(profile):
            profile = init_profile_interactive(profile)
            first_run = False
        first_run = False

        system = build_learning_system_prompt(
            profile,
            skills_knowledge,
            coach_state.get("last_handoff_issues", []),
        )

        media_request = parse_media_request(user_input)
        is_media_request = media_request is not None
        prepared_items: list[dict] = []
        expanded_paths: list[Path] = []
        request_prompt = user_input

        if not is_media_request and looks_like_local_media_reference(user_input):
            print(
                "\n[提示] 我识别到你输入的是本地图片路径，但这轮没有成功解析成可读取的图片内容。"
            )
            print_input_format_tips()
            continue

        if is_media_request:
            request_prompt = media_request["prompt"] or "请从学习教练角度点评这张作品"
            request_paths = media_request["paths"]
            current_signature = build_media_signature(request_paths)
            previous_signature = list(coach_state.get("current_media_signature", []))
            should_inherit = has_context_carryover_intent(user_input) or has_context_carryover_intent(request_prompt)

            if previous_signature and current_signature != previous_signature and not should_inherit:
                coach_messages = []
                coach_state = dict(DEFAULT_COACH_SESSION_STATE)
                print(
                    "\n[提示] 检测到你换了新的图片，我会按新的学习任务重新点评。"
                    "如果你想延续上一张作品的练习方向，请直接说“继续上一张”。"
                )

            print("\n⏳ 正在读取素材，准备点评…")
            try:
                prepared_items, expanded_paths, _ = prepare_media_items(request_paths)
            except ValueError as e:
                print(f"\n❌ {e}\n")
                continue
            except OSError as e:
                print(f"\n❌ 素材读取失败：{e}\n")
                continue

            print("✅ 图片已加载，学习教练开始点评…")

        coach_messages = trim_context(coach_messages, profile, coach_state)

        try:
            response_text, payload = run_learning_coach_turn(
                client,
                system,
                coach_messages,
                request_prompt if is_media_request else user_input,
                media_items=prepared_items if is_media_request else None,
                total_files=len(expanded_paths),
                handoff_issues=coach_state.get("last_handoff_issues", []),
            )
        except anthropic.AuthenticationError:
            print("\n❌ 鉴权失败，请检查 ANTHROPIC_API_KEY / ANTHROPIC_AUTH_TOKEN 和 ANTHROPIC_BASE_URL。\n")
            sys.exit(1)
        except anthropic.RateLimitError:
            print("\n⏳ 请求太频繁了，稍等一会儿再试。\n")
            continue
        except anthropic.APIConnectionError:
            print("\n❌ 网络连接失败，请检查网络后重试。\n")
            continue
        except anthropic.APIStatusError as e:
            print(f"\n❌ API 错误 {e.status_code}：{e.message}\n")
            continue
        except anthropic.BadRequestError as e:
            print(f"\n❌ 请求出错：{e}\n")
            continue

        profile = update_profile_from_coach_payload(profile, payload)
        coach_state = update_coach_session_state(
            coach_state,
            request_prompt if is_media_request else user_input,
            media_request,
            payload,
            handoff_issues=coach_state.get("last_handoff_issues", []),
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
            maybe_print_media_input_hint(user_input)


def main() -> None:
    from photo import main as unified_main

    unified_main(preferred_module="coach", source_cli="photo_v2.py")


if __name__ == "__main__":
    main()
