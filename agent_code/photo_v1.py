"""
摄影全栈 Agent — V1 后期辅助模块（MVP 基础版）
================================================
功能：
  1. 照片诊断（曝光 / 色彩 / 噪点 / 对焦 / 构图）
  2. 具体参数建议（方向性描述，禁止精确幻觉数值）
  3. 风格识别与 Lightroom 参数配方
  4. Lightroom .xmp 预设脚本生成（仅输出，不自动执行）
  5. 用户档案初始化（设备、风格、软件与交付偏好，跨会话 JSON 持久化）

技术栈：anthropic 0.89.0 + Pillow 11.3.0
运行方式：python photo.py
"""

import anthropic
import base64
import io
import json
import re
import sys
import time
from difflib import SequenceMatcher
from datetime import datetime
from pathlib import Path
from PIL import Image

from photo_events import EventSink, ensure_event_sink
from photo_protocol import RESPONSE_DELIMITER, split_response_sections
from photo_runtime import create_anthropic_client
from photo_storage import (
    atomic_write_json,
    build_profile_document,
    migrate_profile_payload,
    read_json,
    resolve_app_data_dir,
    resolve_profile_path,
)

try:
    import rawpy
except ImportError:
    rawpy = None

# ──────────────────────────────────────────────
# 常量配置
# ──────────────────────────────────────────────

MODEL = "claude-sonnet-4-6"
MAX_TOKENS_STREAM = 1024          # 照片诊断输出上限（不开 thinking，300-500 字诊断足够）
MAX_TOKENS_CHAT = 8192            # 纯文字对话输出上限（拍摄规划 JSON 需要较多 tokens）
MAX_TOKENS_CHAT_THINKING = min(MAX_TOKENS_CHAT, 4096)  # 开 thinking 时收紧上限，降低预算校验失败风险
RATE_LIMIT_RETRY_DELAYS = (2.0, 6.0)
IMAGE_MAX_BYTES = 20 * 1024 * 1024  # 20 MB 原始文件上限（超过此值直接拒绝）
BASE64_SAFE_BYTES = 4 * 1024 * 1024  # 4 MB：base64 后约 5.3 MB，接近 API 上限但实测可通过
SUPPORTED_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".heic", ".heif"}
RAW_EXTS = {".arw", ".cr2", ".cr3", ".dng", ".nef", ".orf", ".raf", ".rw2"}
SUPPORTED_INPUT_EXTS = SUPPORTED_IMAGE_EXTS | RAW_EXTS
MAX_DIRECT_MEDIA_INPUTS = 6
BATCH_SAMPLE_LIMIT = 6
LEGACY_PROFILE_PATH = Path(__file__).parent / "user_profile.json"
PROFILE_PATH = resolve_app_data_dir() / "user_profile.json"
CONTEXT_MAX_ROUNDS = 4            # 超过此轮数只保留档案摘要 + 最近 2 轮

# Skills 知识库路径（从 npx skills 安装的本地 SKILL.md 读取）
SKILLS_DIR = Path.home() / ".agents" / "skills"
SKILLS_OF_INTEREST = [
    "product-photography",         # P1：构图 / 布光 / 角度 / 常见错误
    "video-color-grading",         # P0：调色风格 / 术语 / 参数方向
    "vision-analysis",             # P2：分析模式分类（V2 参考）
]

# ──────────────────────────────────────────────
# 用户档案：跨会话 KV 持久化
# ──────────────────────────────────────────────

DEFAULT_PROFILE = {
    "device_info": "",          # 相机型号 / 镜头焦段 / 是否有无人机等
    "style_preference": "",     # 人文 / 风光 / 人像 / 色调偏好
    "skill_level": "",
    "editing_software": "",
    "favorite_subjects": "",
    "delivery_platform": "",
    "skin_tone_preference": "",
    "retouch_tendency": "",
    "weak_points": [],
    "frequent_locations": [],
    "lesson_history": [],
    "work_quality_distribution": {},
}

PROFILE_CORE_FIELDS = [
    "device_info",
    "style_preference",
    "skill_level",
    "editing_software",
]

DEFAULT_SESSION_STATE = {
    "current_task_mode": "",
    "current_goal": "",
    "current_subject": "",
    "current_media_paths": [],
    "last_summary": "",
    "confirmed_adjustments": [],
    "last_source_note": "",
    "last_xmp_params": {},
    "current_media_signature": [],
}


def load_profile() -> dict:
    """从 JSON 文件加载用户档案；文件不存在时返回默认模板。"""
    profile_path = resolve_profile_path(LEGACY_PROFILE_PATH)
    return migrate_profile_payload(read_json(profile_path), DEFAULT_PROFILE)
            # 合并新字段（兼容旧版本档案）


def save_profile(profile: dict) -> bool:
    """将用户档案增量写入 JSON 文件。"""
    try:
        profile_path = resolve_profile_path(LEGACY_PROFILE_PATH)
        atomic_write_json(profile_path, build_profile_document(profile))
        return True
    except OSError:
        return False
        print(f"\n[提示] 档案保存失败：{e}")


def profile_summary(profile: dict) -> str:
    """生成注入 System Prompt 的档案摘要字符串。"""
    parts = []
    if profile.get("device_info"):
        parts.append(f"设备：{profile['device_info']}")
    if profile.get("style_preference"):
        parts.append(f"风格偏好：{profile['style_preference']}")
    if profile.get("skill_level"):
        parts.append(f"技能水平：{profile['skill_level']}")
    if profile.get("editing_software"):
        parts.append(f"常用修图软件：{profile['editing_software']}")
    if profile.get("favorite_subjects"):
        parts.append(f"常拍题材：{profile['favorite_subjects']}")
    if profile.get("delivery_platform"):
        parts.append(f"交付平台：{profile['delivery_platform']}")
    if profile.get("skin_tone_preference"):
        parts.append(f"肤色偏好：{profile['skin_tone_preference']}")
    if profile.get("retouch_tendency"):
        parts.append(f"修图倾向：{profile['retouch_tendency']}")
    if not parts:
        return "（档案尚未初始化）"
    return "；".join(parts)


def is_profile_initialized(profile: dict) -> bool:
    """判断当前版本的核心个性化字段是否已填写。"""
    return all(bool(profile.get(field)) for field in PROFILE_CORE_FIELDS)


def session_state_summary(session_state: dict) -> str:
    parts = []
    if session_state.get("current_task_mode"):
        parts.append(f"当前任务：{session_state['current_task_mode']}")
    if session_state.get("current_goal"):
        parts.append(f"当前目标：{session_state['current_goal']}")
    if session_state.get("current_subject"):
        parts.append(f"当前素材：{session_state['current_subject']}")
    if session_state.get("last_summary"):
        parts.append(f"上轮结论：{session_state['last_summary']}")
    if session_state.get("confirmed_adjustments"):
        parts.append(f"已确认调整：{'；'.join(session_state['confirmed_adjustments'][:3])}")
    if session_state.get("last_source_note"):
        parts.append(f"素材说明：{session_state['last_source_note']}")
    if not parts:
        return "（当前无活动编辑上下文）"
    return "；".join(parts)


def update_session_state_from_analysis(
    session_state: dict,
    request_prompt: str,
    media_request: dict,
    analysis_payload: dict,
    is_batch: bool,
) -> dict:
    updated = {**DEFAULT_SESSION_STATE, **session_state}
    updated["current_task_mode"] = analysis_payload.get(
        "task_mode",
        "batch_unify" if is_batch else "single_photo",
    )
    updated["current_goal"] = request_prompt.strip() or ("批量统一色调" if is_batch else "默认后期诊断")
    subject_names = [path.name for path in media_request.get("paths", [])[:3]]
    if len(media_request.get("paths", [])) > 3:
        subject_names.append("...")
    updated["current_subject"] = ", ".join(subject_names)
    updated["last_summary"] = analysis_payload.get("summary", "").strip()
    updated["confirmed_adjustments"] = analysis_payload.get("adjustments", [])[:5]
    updated["last_source_note"] = analysis_payload.get("source_note", "").strip()
    updated["last_xmp_params"] = analysis_payload.get("xmp_params", {})
    updated["current_media_paths"] = [str(path) for path in media_request.get("paths", [])]
    updated["current_media_signature"] = build_media_signature(media_request.get("paths", []))
    return updated


def update_session_state_from_chat(session_state: dict, user_text: str) -> dict:
    updated = {**DEFAULT_SESSION_STATE, **session_state}
    text = user_text.strip()
    if not text:
        return updated

    tweak_markers = ("再", "更", "高光", "阴影", "色温", "饱和", "对比", "肤色", "冷", "暖")
    if any(marker in text for marker in tweak_markers):
        base_goal = updated.get("current_goal", "").strip()
        if base_goal:
            updated["current_goal"] = f"{base_goal}；用户追加：{text}"
        else:
            updated["current_goal"] = text
    return updated


def build_media_signature(paths: list[Path]) -> list[str]:
    signature: list[str] = []
    for path in paths:
        try:
            normalized = str(path.resolve(strict=False))
        except OSError:
            normalized = str(path)
        signature.append(normalized.lower())
    return sorted(signature)


def has_context_carryover_intent(text: str) -> bool:
    normalized = str(text).strip().lower()
    if not normalized:
        return False

    markers = (
        "继续上一张",
        "继续上张",
        "延续上一张",
        "沿用上一张",
        "按上一张风格",
        "按上一张风格来",
        "继续上一组",
        "延续上一组",
        "按上一组风格",
        "按上一组风格来",
        "同一组统一",
        "沿用上次风格",
        "继续这个方向",
        "延续这个方向",
        "沿用这个方向",
        "继续这个风格",
        "延续这个风格",
        "沿用这个风格",
    )
    return any(marker in normalized for marker in markers)


def references_current_media(text: str) -> bool:
    normalized = str(text).strip().lower()
    if not normalized:
        return False

    markers = (
        "这张照片",
        "这张图",
        "这张作品",
        "刚才这张",
        "当前这张",
        "这组照片",
        "这组图",
        "这组作品",
        "刚才这组",
        "当前这组",
        "这批照片",
        "这批图",
    )
    return any(marker in normalized for marker in markers)


def merge_note_text(*notes: str) -> str:
    merged: list[str] = []
    seen: set[str] = set()
    for note in notes:
        text = str(note).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        merged.append(text)
    return "；".join(merged)


def collect_preview_notes(media_items: list[dict]) -> list[str]:
    notes: list[str] = []
    seen: set[str] = set()
    for item in media_items:
        note = str(item.get("preview_note", "")).strip()
        if not note or note in seen:
            continue
        seen.add(note)
        notes.append(note)
    return notes


def normalize_note_for_compare(text: str) -> str:
    normalized = str(text).strip().lower()
    normalized = re.sub(r"\s+", "", normalized)
    replacements = {
        "本次分析": "",
        "当前分析": "",
        "本轮分析": "",
        "分析结果": "",
        "涉及极细高光": "细微高光",
        "极细高光边缘": "细微高光",
        "颜色层次": "色彩层次",
        "建议结合原图复核": "结合原图复核",
        "建议结合原片复核": "结合原图复核",
    }
    for old, new in replacements.items():
        normalized = normalized.replace(old, new)
    return normalized.strip("，,。；;")


def notes_are_similar(a: str, b: str) -> bool:
    left = normalize_note_for_compare(a)
    right = normalize_note_for_compare(b)
    if not left or not right:
        return False
    return (
        left == right or
        left in right or
        right in left or
        SequenceMatcher(None, left, right).ratio() >= 0.72
    )


def compact_note_text(text: str) -> str:
    raw = str(text).strip()
    if not raw:
        return ""

    replacements = {
        "本次分析基于压缩预览，涉及极细高光、宽容度和色彩层次时建议结合原图复核": "基于压缩预览，细微高光和色彩建议结合原图复核",
        "基于压缩预览分析，极细高光边缘和色彩层次建议结合原图复核": "基于压缩预览，细微高光和色彩建议结合原图复核",
        "本次分析尽量保留了 PNG 预览，极细高光和颜色层次仍建议结合原图复核": "基于 PNG 预览，细微高光和色彩建议结合原图复核",
        "RAW 已解码为半尺寸预览供分析": "基于 RAW 半尺寸预览分析",
        "HEIC/HEIF 已转换为分析预览": "HEIC 已转换为分析预览",
    }

    segments: list[str] = []
    for segment in re.split(r"[；。]\s*", raw):
        current = segment.strip(" ，,。；;")
        if not current:
            continue
        for old, new in replacements.items():
            current = current.replace(old, new)
        current = current.strip(" ，,。；;")
        if not current:
            continue
        if any(notes_are_similar(current, existing) for existing in segments):
            continue
        segments.append(current)

    return "；".join(segments)


def sanitize_closing_line(text: str) -> str:
    closing_line = str(text).strip()
    if not closing_line:
        return ""

    export_markers = (
        "lightroom 配方",
        "lightroom 预设",
        ".xmp",
        "xmp",
        "预设吗",
        "生成预设",
        "导出预设",
    )
    if not any(marker in closing_line.lower() for marker in export_markers):
        return closing_line

    kept_sentences = [
        sentence.strip()
        for sentence in re.split(r"(?<=[。！？!?])", closing_line)
        if sentence.strip() and not any(marker in sentence.lower() for marker in export_markers)
    ]
    return "".join(kept_sentences).strip()


EXPORT_COMMAND_ALIASES = {
    "xmp",
    "预设",
    "lightroom",
    "生成预设",
    "导出预设",
    "导出xmp",
    "生成xmp",
}


def is_export_command(user_input: str) -> bool:
    text = user_input.strip().lower()
    if not text:
        return False

    if text in EXPORT_COMMAND_ALIASES:
        return True

    normalized = re.sub(r"[`\"'""‘’]", "", text)
    if normalized in EXPORT_COMMAND_ALIASES:
        return True

    parts = [
        part.strip()
        for part in re.split(r"[/／|｜,，、\s]+", normalized)
        if part.strip()
    ]
    if parts and all(part in EXPORT_COMMAND_ALIASES for part in parts):
        return True

    export_verbs = ("导出", "生成", "保存")
    export_targets = ("xmp", "预设", "lightroom")
    return any(verb in normalized for verb in export_verbs) and any(
        target in normalized for target in export_targets
    )


# ──────────────────────────────────────────────
# Skills 知识加载器
# ──────────────────────────────────────────────

def load_skills_knowledge() -> str:
    """
    从本地安装的 SKILL.md 文件中提取摄影相关知识。
    提取策略：只读取知识性段落（表格、列表、术语），跳过 API 调用代码块和安装指南。
    返回拼接后的知识文本，供注入 System Prompt。
    """
    knowledge_parts: list[str] = []

    for skill_name in SKILLS_OF_INTEREST:
        skill_path = SKILLS_DIR / skill_name / "SKILL.md"
        if not skill_path.exists():
            continue

        try:
            raw = skill_path.read_text(encoding="utf-8")
        except OSError:
            continue

        # ── 按 skill 提取有价值的知识段落 ──
        extracted = _extract_skill_knowledge(skill_name, raw)
        if extracted:
            knowledge_parts.append(extracted)

    if not knowledge_parts:
        return ""

    return "\n\n".join(knowledge_parts)


def _extract_skill_knowledge(skill_name: str, raw_text: str) -> str:
    """
    针对不同 skill 提取最有价值的知识段落。
    跳过代码块（```...```）中的 API 调用代码，只保留表格和文字描述。
    """
    if skill_name == "product-photography":
        return _extract_product_photography(raw_text)
    elif skill_name == "video-color-grading":
        return _extract_color_grading(raw_text)
    elif skill_name == "vision-analysis":
        return _extract_vision_analysis(raw_text)
    return ""


def _extract_tables_and_lists(text: str) -> str:
    """从 Markdown 文本中提取所有表格（|...|行）和列表项（- 或数字.开头行）。"""
    lines = text.split("\n")
    result = []
    for line in lines:
        stripped = line.strip()
        # 保留表格行
        if stripped.startswith("|") and stripped.endswith("|"):
            result.append(stripped)
        # 保留列表项
        elif stripped.startswith("- ") or stripped.startswith("* "):
            result.append(stripped)
        # 保留标题行
        elif stripped.startswith("#"):
            result.append(stripped)
        # 保留 Key: / Prompt add: / Avoid: 这类提示
        elif ":" in stripped and any(
            stripped.startswith(k)
            for k in ("Key:", "Prompt add:", "Avoid:", "Best For:")
        ):
            result.append(stripped)
    return "\n".join(result)


def _extract_section(text: str, start_heading: str, stop_headings: list[str] | None = None) -> str:
    """提取从 start_heading 到下一个同级标题之间的文本。"""
    lines = text.split("\n")
    capturing = False
    start_level = 0
    captured = []

    for line in lines:
        stripped = line.strip()
        if not capturing:
            if stripped.startswith("#") and start_heading.lower() in stripped.lower():
                capturing = True
                start_level = len(stripped) - len(stripped.lstrip("#"))
                captured.append(stripped)
            continue

        # 遇到同级或更高级标题 → 停止
        if stripped.startswith("#"):
            level = len(stripped) - len(stripped.lstrip("#"))
            if level <= start_level:
                if stop_headings and any(h.lower() in stripped.lower() for h in stop_headings):
                    break
                elif not stop_headings:
                    break
            captured.append(stripped)
        else:
            captured.append(line)

    return "\n".join(captured)


def _extract_product_photography(raw: str) -> str:
    """从 product-photography 中提取：角度、布光、阴影、构图、常见错误表。"""
    sections = [
        "Camera Angles",
        "Lighting Setups",
        "Shadow Types",
        "Composition Rules",
        "Common Mistakes",
        "Product Categories",
    ]
    parts = ["[知识来源：product-photography skill]"]
    for section_name in sections:
        section_text = _extract_section(raw, section_name)
        if section_text:
            tables = _extract_tables_and_lists(section_text)
            if tables:
                parts.append(tables)
    return "\n".join(parts) if len(parts) > 1 else ""


def _extract_color_grading(raw: str) -> str:
    """从 video-color-grading 中提取：风格分类表、调色术语、Prompt 要素。"""
    parts = ["[知识来源：video-color-grading skill]"]

    # 风格分类表
    style_section = _extract_section(raw, "Color Grading Styles")
    if style_section:
        tables = _extract_tables_and_lists(style_section)
        if tables:
            parts.append(tables)

    # 最佳实践和术语
    for heading in ["Best Practices", "Common Terminology", "Prompt Tips"]:
        section = _extract_section(raw, heading)
        if section:
            extracted = _extract_tables_and_lists(section)
            if extracted:
                parts.append(extracted)

    return "\n".join(parts) if len(parts) > 1 else ""


def _extract_vision_analysis(raw: str) -> str:
    """从 vision-analysis 中提取：分析模式分类表。"""
    section = _extract_section(raw, "Analysis Modes")
    if section:
        tables = _extract_tables_and_lists(section)
        if tables:
            return f"[知识来源：vision-analysis skill]\n{tables}"
    return ""


# ──────────────────────────────────────────────
# System Prompt 构建（人格 + 档案 + 模块指令）
# ──────────────────────────────────────────────

def build_system_prompt(profile: dict, skills_knowledge: str = "") -> str:
    """
    构建 V1 模块的完整 System Prompt。
    人格设定约 250 字，档案摘要动态注入头部，后接模块指令 + 知识库。
    skills_knowledge: 从本地 SKILL.md 动态加载的知识文本。
    """
    summary = profile_summary(profile)

    system = f"""# 用户档案摘要
{summary}

---

# 人格设定（最高优先级，贯穿全部版本）

你是用户的摄影师朋友——有十年以上实战经验，擅长风光、人像和纪实，同时熟悉后期工作流。
你的口吻：专业但不冷漠，像老朋友给建议，不说废话，直接给参数和方向。

说话风格要求：
- 给建议时直接说"高光往下拉一点"或"阴影可以提 10-20 的幅度"，而不是"调整高光"这种笼统说法
- 禁止输出评分表（曝光：7/10 这类），要像真人导师一样描述你看到的具体问题
- 回复长度严格控制：照片诊断全文控制在 300~500 字以内（含参数建议），一句话收尾即可
- 禁止在一次回复中重复分析同一张照片——诊断 + 建议只输出一遍，不要二次展开或换角度再分析
- 结尾用一句简短收尾（例如"想试哪个方向？"或"这样会更耐看一些。"），不要长篇总结
- 每次模块切换时生成一句自然的交接语，保持对话连贯感
- 称呼用"你"，语气平和，偶尔加一句鼓励性的话

关于幻觉防控（重要）：
- 禁止给出精确的具体数值（如"色温精确调至 4850K"）—— Vision 模型无法精确测量，这类数值是幻觉
- 改用方向性描述：方向（升/降/偏暖/偏冷）+ 大致幅度（小幅/中幅/较大幅度，或 ±10~30 这样的区间）
- 如果图像过暗/过模糊/内容无法识别，主动降级描述你看到的情况，请用户确认，不报错中断

---

# V1 模块指令：后期辅助

## 能力范围（首次对话必须说明）
在对话开场白中用一句话说明当前版本能力边界，例如：
"我现在可以帮你分析照片的后期问题，给出具体的调整建议和 Lightroom 参数配方。每次对话独立，暂不跨会话记忆。"

## 照片诊断维度
分析照片时，覆盖以下维度（不必每条都写，只写有问题的）：
- 曝光：过曝 / 欠曝 / 高光溢出 / 阴影死黑
- 色彩：偏色方向 / 白平衡感觉偏冷或偏暖
- 噪点：高 ISO 噪点 / 色噪 / 明度噪点
- 对焦：主体清晰度 / 眼部对焦（人像）/ 运动模糊
- 构图：水平线 / 主体位置 / 前景引导线 / 留白

## 参数建议格式
输出结构化建议，格式示例：
  ▸ 高光：向下拉，中幅（参考区间 -20 ~ -40）
  ▸ 阴影：向上提，小幅（参考区间 +10 ~ +20）
  ▸ 色温：偏暖方向调整，小幅
数值务必用区间，不给精确点值。
- 除非我在分析指令中明确要求你输出 JSON 供程序解析，否则不要输出 JSON、代码块或其他机器可读格式。

## 风格配方（用户主动描述目标风格时触发）
将用户描述的风格拆解为 Lightroom 参数方向配方，
例如"日系胶片感"→ 高光压低、阴影提亮、饱和度降低、HSL 橙色偏黄、淡雅绿色调等方向说明。

## 任务模式
- 当用户上传单张图时，默认做单图后期诊断。
- 当用户上传图片并附带目标风格时，优先按目标风格输出可执行建议。
- 当用户上传文件夹或多张图时，按"批量统一色调"任务处理，输出适合整组复用的参数，并提醒哪些参数需要单张微调。
- 当输入为 RAW 文件时，如果有 RAW 预览图或可读取的 RAW 数据，可基于预览做分析，并明确说明结果主要服务于后期方向判断。

## Lightroom XMP 预设脚本
生成可复制的 .xmp 文本片段时，必须：
1. 在输出前提示"建议先备份原始文件"
2. 使用区间中点值作为脚本数值（不承诺精确效果）
3. 标注"此脚本仅供参考，实际效果因原片而异，请在 Lightroom 中手动微调"

## 用户档案初始化
首次检测到档案未初始化时，在正式分析前用 4 组简短问题收集信息：
1. 常用相机型号和主要镜头焦段？
2. 主要拍摄方向（风光/人像/纪实/街拍等）和偏好色调？
3. 常用修图软件和大概水平？
4. 常拍题材、主要交付平台，以及偏好的肤色方向或修图倾向？
收集后立即写入档案，后续对话自动从档案读取，不重复询问。

---

# 摄影知识参考库

以下知识来自专业摄影 Skills 知识库，在分析照片和给建议时作为参考依据。
不要原封不动输出这些表格，而是将其内化为你的专业判断来源。

## P0：调色风格与参数方向速查

### 8 种主流调色风格
| 风格 | 特征 | 适用场景 |
|------|------|----------|
| 电影感 Cinematic | 黑色压实、色彩对比强、胶片质感 | 叙事、剧情 |
| 橘蓝 Orange & Teal | 肤色暖橘、背景冷蓝 | 动作、大片感 |
| 胶片模拟 Film Emulation | Kodak/Fuji 胶片色科学特征 | 独立、MV |
| 暗调 Moody Dark | 低调、去饱和、氛围感 | 悬疑、情绪 |
| 明亮清新 Bright & Airy | 阴影提亮、柔和粉彩 | 婚礼、生活方式 |
| 复古怀旧 Vintage/Retro | 褪色、暖色、怀旧感 | MV、广告 |
| 黑白 Black & White | 电影级单色、色调控制 | 艺术、戏剧 |
| HDR 增强 | 动态范围扩展、色彩鲜活 | 自然、旅行 |

### 调色术语速查
| 术语 | 含义 |
|------|------|
| Lift（提升） | 调整阴影亮度 |
| Gamma（伽马） | 调整中间调亮度 |
| Gain（增益） | 调整高光亮度 |
| Crush（压黑） | 将黑色压到纯黑以下 |
| Push（色彩推移） | 向某个色调范围添加色偏 |
| Color Cast（色偏） | 画面中不想要的整体色调偏移 |

### 给风格建议时的 7 要素（内部检查清单）
1. 参考片：用户提到的电影、摄影师、视觉风格参考
2. 情绪：想要的情感基调（沉郁、明亮、戏剧化、柔和）
3. 阴影处理：阴影的颜色和深度（压实、提亮、带色偏）
4. 高光处理：高光的温度、滚降方式、颜色
5. 饱和度：整体和局部色彩强度
6. 对比度：高、低，或特定曲线形态
7. 肤色：自然、偏暖，还是风格化处理

## P1：构图与布光知识速查

### 拍摄角度
| 角度 | 适合 |
|------|------|
| 平视 Eye Level | 大多数产品/人像，亲近感 |
| 微俯 30° | 俯拍、食物、化妆品 |
| 鸟瞰 90° | 平铺构图 |
| 低角度 | 让主体显得有力量感/高级感 |
| 3/4 角度 | 最通用，体现纵深 |

### 布光方案
| 方案 | 效果 |
|------|------|
| 柔光箱 Soft Box | 均匀、阴影极少 |
| 轮廓光 Rim/Edge | 戏剧性的轮廓发光 |
| 自然窗光 Natural Window | 温暖、真实、生活化 |
| 硬光定向 Hard Directional | 强阴影、社论风格 |
| 平光 Flat/Even | 电商无影、均匀曝光 |

### 阴影类型
| 类型 | 何时使用 |
|------|----------|
| 无阴影 | 电商/白底合规要求 |
| 接触阴影 | 有落地感但干净 |
| 投影 | 增加层次感，专业 |
| 戏剧阴影 | 社论、奢侈品、氛围 |
| 反射 | 科技、奢侈品、高级感 |

### 构图规则
| 规则 | 应用 |
|------|------|
| 三分法 | 生活类拍摄，主体放在交叉点 |
| 居中主体 | 电商/产品照，主体正中 |
| 留白 | 为文字叠加预留空间 |
| 引导线 | 利用边缘、阴影引导视线到主体 |
| 奇数法则 | 3 或 5 个物体比 2 或 4 更好看 |
| 三角构图 | 3 件物品排成三角形保持平衡 |

### 常见后期错误速查
| 错误 | 问题 | 建议 |
|------|------|------|
| 背景太杂 | 主体被淹没 | 简洁背景，主体为王 |
| 完全正面平拍 | 像证件照，缺乏层次 | 略偏 15-30° 增加纵深 |
| 布光与品类不匹配 | 科技产品用暖木背景 | 品类对应合适的光线气质 |
| 道具过多 | 分散注意力 | 生活场景最多 2-3 个辅助道具 |
| 风格不统一 | 看起来不专业 | 同组照片保持相同布光和背景体系 |
| 没有尺寸参考 | 用户无法判断大小 | 至少一张含手持或已知物体的参照 |
| 分辨率不足 | 无法放大，显得业余 | 至少 1600px 以上长边 |
| 一切都居中 | 静态、无聊 | 生活照用三分法，仅产品照居中 |
"""

    # ── 动态注入 Skills 知识（如果有）──
    if skills_knowledge:
        system += f"""
---

# 扩展知识（来自已安装的 Skills）

以下为从本地 Skills 动态加载的补充知识，作为专业参考。
用户提问时如涉及相关内容，可参考这些知识辅助回答。

{skills_knowledge}
"""

    return system


# ──────────────────────────────────────────────
# 图像预处理
# ──────────────────────────────────────────────

def _format_exts(exts: set[str]) -> str:
    return ", ".join(sorted(exts))


def _is_supported_input_path(path: Path) -> bool:
    raw = str(path).strip()
    if raw in {"/", "\\", ".", "./", ".\\", "|"}:
        return False
    return path.exists() and (path.is_dir() or path.suffix.lower() in SUPPORTED_INPUT_EXTS)


def _clean_extracted_remainder(text: str) -> str:
    cleaned = re.sub(r"\s+", " ", text).strip(" ,;；，、|｜")
    cleaned = re.sub(r"^(?:和|及|跟|与|还有)\s*", "", cleaned)
    cleaned = re.sub(r"\s*(?:和|及|跟|与|还有)$", "", cleaned)
    return cleaned.strip(" ,;；，、|｜")


def looks_like_local_media_reference(text: str) -> bool:
    lowered = text.lower()
    return (
        "::" in text or
        bool(re.search(r"[a-zA-Z]:[\\/]", text)) or
        any(ext in lowered for ext in SUPPORTED_INPUT_EXTS)
    )


def _extract_paths_from_segment(text: str) -> tuple[list[Path], str]:
    matches: list[tuple[int, int, Path]] = []
    seen: set[str] = set()

    def _add_match(candidate: str, start: int, end: int) -> None:
        normalized = candidate.strip().strip("\"'")
        if not normalized:
            return
        path = Path(normalized)
        key = str(path).lower()
        if key in seen or not _is_supported_input_path(path):
            return
        seen.add(key)
        matches.append((start, end, path))

    quoted_matches = list(re.finditer(r'"([^"]+)"|\'([^\']+)\'', text))
    occupied_spans: list[tuple[int, int]] = []
    for match in quoted_matches:
        candidate = match.group(1) or match.group(2)
        _add_match(candidate, *match.span())
        occupied_spans.append(match.span())

    ext_pattern = "|".join(
        sorted((re.escape(ext.lstrip(".")) for ext in SUPPORTED_INPUT_EXTS), key=len, reverse=True)
    )
    windows_file_pattern = re.compile(
        rf"(?i)([a-zA-Z]:[\\/][^\s\"']*?\.(?:{ext_pattern}))"
    )
    for match in windows_file_pattern.finditer(text):
        start, end = match.span(1)
        if any(start < span_end and end > span_start for span_start, span_end in occupied_spans):
            continue
        _add_match(match.group(1), start, end)

    if matches:
        remainder = text
        for start, end, _ in sorted(matches, key=lambda item: item[0], reverse=True):
            remainder = f"{remainder[:start]} {remainder[end:]}"
        ordered_paths = [path for _, _, path in sorted(matches, key=lambda item: item[0])]
        return ordered_paths, _clean_extracted_remainder(remainder)

    tokens = text.split()
    for start_idx in range(len(tokens)):
        for end_idx in range(len(tokens), start_idx, -1):
            candidate = " ".join(tokens[start_idx:end_idx]).strip("\"'")
            path = Path(candidate)
            if _is_supported_input_path(path):
                remainder_tokens = tokens[:start_idx] + tokens[end_idx:]
                return [path], _clean_extracted_remainder(" ".join(remainder_tokens))

    return [], _clean_extracted_remainder(text)


def parse_media_request(user_input: str) -> dict | None:
    """
    支持以下输入方式：
    1. C:/Photos/shot.jpg
    2. "C:/Photos/my shot.jpg" 修成电影感
    3. "C:/Photos/shot.jpg" :: 修成电影感
    4. "C:/Photos/set01" :: 帮我统一这一组的色调
    5. "a.jpg" "b.jpg" :: 统一成同一组风格
    """
    stripped = user_input.strip()
    if not stripped:
        return None

    path_part = stripped
    prompt_hint = ""
    for separator in ("::", "｜", "|"):
        if separator in stripped:
            path_part, prompt_hint = stripped.split(separator, 1)
            break

    paths, leftover = _extract_paths_from_segment(path_part.strip())
    if not paths:
        return None

    prompt = " ".join(
        part for part in [leftover.strip(), prompt_hint.strip()] if part
    ).strip()

    return {
        "paths": paths,
        "prompt": prompt,
    }


def find_sidecar_preview(raw_path: Path) -> Path | None:
    preview_candidates = sorted(
        raw_path.parent.glob(f"{raw_path.stem}.*"),
        key=lambda p: p.suffix.lower(),
    )
    for candidate in preview_candidates:
        if candidate.suffix.lower() in SUPPORTED_IMAGE_EXTS:
            return candidate
    return None


def collect_batch_paths(paths: list[Path]) -> list[Path]:
    collected: list[Path] = []

    for path in paths:
        if path.is_dir():
            folder_items = sorted(
                p for p in path.iterdir()
                if p.is_file() and p.suffix.lower() in SUPPORTED_INPUT_EXTS
            )
            raw_stems = {
                p.stem for p in folder_items
                if p.suffix.lower() in RAW_EXTS
            }
            deduped_items = [
                p for p in folder_items
                if not (
                    p.suffix.lower() in SUPPORTED_IMAGE_EXTS and
                    p.stem in raw_stems
                )
            ]
            collected.extend(deduped_items)
        else:
            collected.append(path)

    return collected


def sample_batch_paths(paths: list[Path], limit: int = BATCH_SAMPLE_LIMIT) -> list[Path]:
    if len(paths) <= limit:
        return paths

    if limit <= 1:
        return [paths[0]]

    step = (len(paths) - 1) / (limit - 1)
    indexes = {round(i * step) for i in range(limit)}
    return [paths[i] for i in sorted(indexes)]


def encode_pil_image(
    img: Image.Image,
    preferred_format: str = "jpeg",
    sink: EventSink | None = None,
) -> tuple[str, str, str]:
    event_sink = ensure_event_sink(sink)
    working_img = img.copy()
    preview_notes: list[str] = []

    max_dim = max(working_img.size)
    if max_dim > 4000:
        ratio = 4000 / max_dim
        new_size = (int(working_img.size[0] * ratio), int(working_img.size[1] * ratio))
        working_img = working_img.resize(new_size, Image.LANCZOS)
        preview_notes.append("为控制传输体积，长边已缩到约 4000px")

    if preferred_format == "png":
        png_img = working_img
        if png_img.mode not in {"RGB", "RGBA", "L"}:
            png_img = png_img.convert("RGBA" if "A" in png_img.mode else "RGB")

        buf = io.BytesIO()
        png_img.save(buf, format="PNG", optimize=True, compress_level=9)
        raw_bytes = buf.getvalue()
        if len(raw_bytes) <= BASE64_SAFE_BYTES:
            data = base64.standard_b64encode(raw_bytes).decode("utf-8")
            compressed_mb = len(raw_bytes) / (1024 * 1024)
            event_sink.line(f"  已压缩至 {compressed_mb:.1f} MB（PNG 预览）")
            preview_notes.append("本次分析尽量保留了 PNG 预览，极细高光和颜色层次仍建议结合原图复核")
            return data, "image/png", "；".join(preview_notes)
        preview_notes.append("PNG 预览仍然过大，已回退为 JPEG 预览")

    jpeg_img = working_img.convert("RGB")
    for quality in (92, 85, 75, 60):
        buf = io.BytesIO()
        jpeg_img.save(buf, format="JPEG", quality=quality, optimize=True)
        raw_bytes = buf.getvalue()
        if len(raw_bytes) <= BASE64_SAFE_BYTES:
            data = base64.standard_b64encode(raw_bytes).decode("utf-8")
            compressed_mb = len(raw_bytes) / (1024 * 1024)
            event_sink.line(f"  已压缩至 {compressed_mb:.1f} MB（quality={quality}）")
            preview_notes.append("本次分析基于压缩预览，涉及极细高光、宽容度和色彩层次时建议结合原图复核")
            return data, "image/jpeg", "；".join(preview_notes)

    for scale in (0.7, 0.5, 0.3):
        new_size = (int(jpeg_img.size[0] * scale), int(jpeg_img.size[1] * scale))
        resized = jpeg_img.resize(new_size, Image.LANCZOS)
        buf = io.BytesIO()
        resized.save(buf, format="JPEG", quality=70, optimize=True)
        raw_bytes = buf.getvalue()
        if len(raw_bytes) <= BASE64_SAFE_BYTES:
            data = base64.standard_b64encode(raw_bytes).decode("utf-8")
            compressed_mb = len(raw_bytes) / (1024 * 1024)
            event_sink.line(f"  已压缩至 {compressed_mb:.1f} MB（缩放 {int(scale*100)}%）")
            preview_notes.append(f"图片预览额外缩放到约 {int(scale * 100)}%")
            preview_notes.append("本次分析基于压缩预览，涉及极细高光、宽容度和色彩层次时建议结合原图复核")
            return data, "image/jpeg", "；".join(preview_notes)

    raise ValueError("图片压缩后仍然过大，请手动缩小后重试。")


def should_standardize_inline_image(path: Path) -> tuple[bool, str]:
    """
    Return whether the file needs a generated preview once it is already
    scheduled for conversion/compression. Small JPG/PNG files are intentionally
    sent as-is in encode_standard_image(), because some model gateways are more
    stable with the original camera file than with a re-encoded preview.
    """
    ext = path.suffix.lower()
    if ext in {".heic", ".heif"}:
        return True, "HEIC/HEIF 需要转换为标准分析预览"

    try:
        with Image.open(path) as img:
            max_dim = max(img.size)
            has_complex_metadata = bool(img.info.get("icc_profile") or img.info.get("exif"))
            incompatible_mode = img.mode not in {"RGB", "RGBA", "L"}
            if max_dim > 4000:
                return True, "图片长边超过 4000px，需要生成标准化预览"
            if has_complex_metadata:
                return True, "图片包含 EXIF/ICC 信息，已生成标准化分析预览以提高 API 兼容性"
            if incompatible_mode:
                return True, f"图片色彩模式 {img.mode} 已转换为标准预览"
    except OSError:
        return False, ""

    return False, ""


def encode_standard_image(path: Path, sink: EventSink | None = None) -> tuple[str, str, str, str]:
    event_sink = ensure_event_sink(sink)
    media_map = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".heic": "image/heic",
        ".heif": "image/heic",
    }

    size = path.stat().st_size
    if size > IMAGE_MAX_BYTES:
        size_mb = size / (1024 * 1024)
        raise ValueError(
            f"图片太大了（{size_mb:.1f} MB），超过 20 MB 限制。\n"
            "建议先在修图软件里导出一张较小的版本。"
        )

    ext = path.suffix.lower()

    if size <= BASE64_SAFE_BYTES and ext not in {".heic", ".heif"}:
        with open(path, "rb") as f:
            data = base64.standard_b64encode(f.read()).decode("utf-8")
        return data, media_map[ext], path.name, ""

    needs_standardize, standardize_reason = should_standardize_inline_image(path)
    if size > BASE64_SAFE_BYTES:
        event_sink.line("  图片超过 4 MB，正在自动压缩（画质优先）…")
    elif standardize_reason:
        event_sink.line(f"  {standardize_reason}…")

    with Image.open(path) as img:
        if ext == ".png" and not needs_standardize:
            data, media_type, preview_note = encode_pil_image(img, preferred_format="png", sink=event_sink)
        else:
            data, media_type, preview_note = encode_pil_image(img, preferred_format="jpeg", sink=event_sink)
            if ext in {".heic", ".heif"}:
                prefix = "HEIC/HEIF 已转换为分析预览"
                preview_note = f"{prefix}；{preview_note}" if preview_note else prefix

    if standardize_reason and standardize_reason not in preview_note:
        preview_note = f"{standardize_reason}；{preview_note}" if preview_note else standardize_reason
    return data, media_type, path.name, preview_note


def encode_raw_image(path: Path, sink: EventSink | None = None) -> tuple[str, str, str, str]:
    event_sink = ensure_event_sink(sink)
    if rawpy is not None:
        event_sink.line(f"  检测到 RAW 文件 {path.name}，正在生成分析预览…")
        with rawpy.imread(str(path)) as raw:
            rgb = raw.postprocess(
                use_camera_wb=True,
                half_size=True,
                no_auto_bright=False,
                output_bps=8,
            )
        img = Image.fromarray(rgb)
        data, media_type, preview_note = encode_pil_image(img, preferred_format="jpeg", sink=event_sink)
        prefix = "RAW 已解码为半尺寸预览供分析"
        preview_note = f"{prefix}；{preview_note}" if preview_note else prefix
        return data, media_type, f"{path.name}（RAW 预览）", preview_note

    preview = find_sidecar_preview(path)
    if preview is not None:
        event_sink.line(f"  检测到 RAW 文件 {path.name}，当前使用同名预览图 {preview.name} 做分析。")
        data, media_type, _, preview_note = encode_standard_image(preview, sink=event_sink)
        prefix = f"当前使用同名预览图 {preview.name} 代替 {path.name} 做分析"
        preview_note = f"{prefix}；{preview_note}" if preview_note else prefix
        return data, media_type, f"{preview.name}（对应 {path.name} 的预览图）", preview_note

    raise ValueError(
        f"已识别 RAW 文件「{path.name}」，但当前环境未安装 rawpy，且未找到同名预览图。\n"
        "你可以：\n"
        "1. 在同目录放一张同名 JPG/PNG/HEIC 预览图\n"
        "2. 先从修图软件导出预览图后再分析\n"
        "3. 安装 rawpy 以直接读取常见 RAW 文件"
    )


def validate_and_encode_image(image_path: str | Path, sink: EventSink | None = None) -> tuple[str, str, str, str]:
    """
    校验图片或 RAW 文件，并返回
    (base64_data, media_type, source_label, preview_note)。
    source_label 用于提示最终实际参与分析的素材来源。
    preview_note 用于提示分析时是否使用了压缩预览或替代预览。
    """
    path = Path(image_path)
    ext = path.suffix.lower()

    if ext in RAW_EXTS:
        return encode_raw_image(path, sink=sink)

    if ext not in SUPPORTED_IMAGE_EXTS:
        raise ValueError(
            f"不支持的图片格式「{ext}」。\n"
            f"目前支持普通图片：{_format_exts(SUPPORTED_IMAGE_EXTS)}\n"
            f"支持 RAW 输入：{_format_exts(RAW_EXTS)}"
        )

    return encode_standard_image(path, sink=sink)


def prepare_media_items(paths: list[Path], sink: EventSink | None = None) -> tuple[list[dict], list[Path], bool]:
    event_sink = ensure_event_sink(sink)
    direct_file_inputs = [path for path in paths if path.is_file()]
    if len(direct_file_inputs) > MAX_DIRECT_MEDIA_INPUTS:
        raise ValueError(
            f"一次最多直接输入 {MAX_DIRECT_MEDIA_INPUTS} 张图片或 RAW 文件。\n"
            "如果你要分析更多素材，建议改为输入文件夹路径，我会自动抽样后给出整组建议。"
        )

    expanded_paths = collect_batch_paths(paths)
    if not expanded_paths:
        raise ValueError("没有找到可分析的图片或 RAW 文件。")

    is_batch = len(expanded_paths) > 1 or any(path.is_dir() for path in paths)
    sampled_paths = sample_batch_paths(expanded_paths, BATCH_SAMPLE_LIMIT if is_batch else 1)
    prepared_items: list[dict] = []
    skipped: list[str] = []

    for path in sampled_paths:
        try:
            data, media_type, source_label, preview_note = validate_and_encode_image(path, sink=event_sink)
        except (OSError, ValueError) as e:
            skipped.append(f"{path.name}: {e}")
            continue

        prepared_items.append(
            {
                "path": path,
                "label": path.name,
                "source_label": source_label,
                "data": data,
                "media_type": media_type,
                "preview_note": preview_note,
            }
        )

    if not prepared_items:
        details = "\n".join(f"- {item}" for item in skipped) if skipped else ""
        raise ValueError(f"没有成功读取到可用于分析的样本。\n{details}".strip())

    if skipped:
        event_sink.line("\n[提示] 以下文件未纳入本次样本分析：")
        for item in skipped:
            event_sink.line(f"  - {item}")
        event_sink.line()

    return prepared_items, expanded_paths, is_batch


# ──────────────────────────────────────────────
# Lightroom XMP 预设生成
# ──────────────────────────────────────────────

XMP_PARAM_SPECS = {
    "Exposure2012": {"type": "float", "min": -5.0, "max": 5.0},
    "Contrast2012": {"type": "int", "min": -100, "max": 100},
    "Highlights2012": {"type": "int", "min": -100, "max": 100},
    "Shadows2012": {"type": "int", "min": -100, "max": 100},
    "Whites2012": {"type": "int", "min": -100, "max": 100},
    "Blacks2012": {"type": "int", "min": -100, "max": 100},
    "Clarity2012": {"type": "int", "min": -100, "max": 100},
    "Dehaze": {"type": "int", "min": -100, "max": 100},
    "Vibrance": {"type": "int", "min": -100, "max": 100},
    "Saturation": {"type": "int", "min": -100, "max": 100},
    "Temperature": {"type": "int", "min": 2000, "max": 50000},
    "Tint": {"type": "int", "min": -150, "max": 150},
    "Sharpness": {"type": "int", "min": 0, "max": 150},
    "LuminanceSmoothing": {"type": "int", "min": 0, "max": 100},
    "ColorNoiseReduction": {"type": "int", "min": 0, "max": 100},
    # HSL 色相调整
    "HueAdjustmentRed": {"type": "int", "min": -100, "max": 100},
    "HueAdjustmentOrange": {"type": "int", "min": -100, "max": 100},
    "HueAdjustmentYellow": {"type": "int", "min": -100, "max": 100},
    "HueAdjustmentGreen": {"type": "int", "min": -100, "max": 100},
    "HueAdjustmentAqua": {"type": "int", "min": -100, "max": 100},
    "HueAdjustmentBlue": {"type": "int", "min": -100, "max": 100},
    "HueAdjustmentPurple": {"type": "int", "min": -100, "max": 100},
    "HueAdjustmentMagenta": {"type": "int", "min": -100, "max": 100},
    # HSL 饱和度调整
    "SaturationAdjustmentRed": {"type": "int", "min": -100, "max": 100},
    "SaturationAdjustmentOrange": {"type": "int", "min": -100, "max": 100},
    "SaturationAdjustmentYellow": {"type": "int", "min": -100, "max": 100},
    "SaturationAdjustmentGreen": {"type": "int", "min": -100, "max": 100},
    "SaturationAdjustmentAqua": {"type": "int", "min": -100, "max": 100},
    "SaturationAdjustmentBlue": {"type": "int", "min": -100, "max": 100},
    "SaturationAdjustmentPurple": {"type": "int", "min": -100, "max": 100},
    "SaturationAdjustmentMagenta": {"type": "int", "min": -100, "max": 100},
    # HSL 明度调整
    "LuminanceAdjustmentRed": {"type": "int", "min": -100, "max": 100},
    "LuminanceAdjustmentOrange": {"type": "int", "min": -100, "max": 100},
    "LuminanceAdjustmentYellow": {"type": "int", "min": -100, "max": 100},
    "LuminanceAdjustmentGreen": {"type": "int", "min": -100, "max": 100},
    "LuminanceAdjustmentAqua": {"type": "int", "min": -100, "max": 100},
    "LuminanceAdjustmentBlue": {"type": "int", "min": -100, "max": 100},
    "LuminanceAdjustmentPurple": {"type": "int", "min": -100, "max": 100},
    "LuminanceAdjustmentMagenta": {"type": "int", "min": -100, "max": 100},
}


def normalize_xmp_params(params: dict | None) -> dict:
    if not isinstance(params, dict):
        return {}

    normalized: dict = {}
    for key, value in params.items():
        spec = XMP_PARAM_SPECS.get(key)
        if spec is None:
            continue

        try:
            numeric = float(value)
        except (TypeError, ValueError):
            continue

        numeric = max(spec["min"], min(spec["max"], numeric))
        if spec["type"] == "int":
            normalized[key] = int(round(numeric))
        else:
            normalized[key] = round(numeric, 2)

    return normalized


def format_xmp_value(value: int | float) -> str:
    if isinstance(value, float):
        return f"{value:.2f}".rstrip("0").rstrip(".")
    return str(value)


def build_xmp_preset(params: dict, preset_name: str = "AI摄影助手建议") -> str:
    """
    根据参数字典生成 Lightroom Classic .xmp 预设文本。
    params 键名对应 Lightroom 内部参数名，值来自结构化参数对象。
    """
    now = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    normalized_params = normalize_xmp_params(params)
    if not normalized_params:
        raise ValueError("缺少可写入 XMP 的结构化参数。")

    attr_lines = "\n         ".join(
        f'crs:{k}="{format_xmp_value(v)}"' for k, v in normalized_params.items()
    )

    xmp = f"""<?xpacket begin="" id="W5M0MpCehiHzreSzNTczkc9d"?>
<x:xmpmeta xmlns:x="adobe:ns:meta/">
  <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
    <rdf:Description
         xmlns:crs="http://ns.adobe.com/camera-raw-settings/1.0/"
         crs:Version="14.0"
         crs:ProcessVersion="11.0"
         crs:PresetType="Normal"
         crs:Cluster=""
         crs:UUID="{preset_name.replace(' ', '_')}_v1"
         crs:SupportsAmount="False"
         crs:SupportsColor="True"
         crs:SupportsMonochrome="False"
         crs:SupportsHighDynamicRange="True"
         crs:SupportsNormalDynamicRange="True"
         crs:SupportsScaledSystemPanel="True"
         crs:Name="{preset_name}"
         crs:ShortName="{preset_name}"
         crs:SortName="{preset_name}"
         crs:Author="摄影全栈Agent V1"
         crs:CreateDate="{now}"
         {attr_lines}
    />
  </rdf:RDF>
</x:xmpmeta>
<?xpacket end="w"?>"""
    return xmp


def extract_xmp_params_from_text(text: str) -> dict:
    """
    向后兼容：从自然语言中反推参数。
    V2 主链路不再依赖该函数，仅在旧会话或兜底场景中使用。

    从 Claude 输出的参数建议文本中提取数值，用于生成 XMP。
    支持多种常见输出格式，使用区间中点值或单一数值。

    能匹配的格式举例：
      ▸ 高光：向下拉，中幅（参考区间 -20 ~ -40）
      ▸ 高光：-30 左右
      ▸ 高光降低约 30
      ▸ 高光：向下拉（约 -30）
      ▸ 高光 -20 到 -40
      ▸ **高光**：-25～-40
    """
    params = {}

    # 中文参数名 → Lightroom 内部参数名
    param_map = {
        "高光": "Highlights2012",
        "阴影": "Shadows2012",
        "曝光": "Exposure2012",
        "对比度": "Contrast2012",
        "清晰度": "Clarity2012",
        "自然饱和度": "Vibrance",
        "饱和度": "Saturation",
        "白色色阶": "Whites2012",
        "白色": "Whites2012",
        "黑色色阶": "Blacks2012",
        "黑色": "Blacks2012",
        "去朦胧": "Dehaze",
        "锐度": "Sharpness",
        "降噪": "LuminanceSmoothing",
        "色噪": "ColorNoiseReduction",
    }

    for cn_name, lr_key in param_map.items():
        # 先去掉 Markdown 加粗标记 **xxx**
        clean_text = text.replace("**", "")

        # 策略 1：区间格式 → "参数名 ... -20 ~ -40" 或 "-20 到 -40" 或 "-20～-40"
        # 分隔符：~ ～ – —
        pattern_range = rf"{cn_name}[^。\n]*?([-+]\d+)\s*[~～–—]\s*([-+]\d+)"
        match = re.search(pattern_range, clean_text)
        if not match:
            # "到" 作为分隔词单独处理
            pattern_range_dao = rf"{cn_name}[^。\n]*?([-+]\d+)\s*到\s*([-+]\d+)"
            match = re.search(pattern_range_dao, clean_text)
        if match:
            v1, v2 = int(match.group(1)), int(match.group(2))
            params[lr_key] = (v1 + v2) // 2
            continue

        # 策略 2：单一带符号数值 → "参数名 ... +30" 或 "-30 左右" 或 "约 -30"
        # 强制要求 +/- 符号，避免误匹配中文字符编码中的数字
        pattern_single = rf"{cn_name}[^。\n]*?([-+]\d+)"
        match = re.search(pattern_single, clean_text)
        if match:
            params[lr_key] = int(match.group(1))
            continue

        # 策略 3：无符号数值 + 方向词推断符号
        # 匹配 "高光降30" "阴影提20" 等
        dir_match = re.search(
            rf"{cn_name}[^。\n]{{0,20}}(降|压|减|下|拉低|降低)\D{{0,10}}(\d+)",
            clean_text,
        )
        if dir_match:
            params[lr_key] = -int(dir_match.group(2))
            continue
        dir_match = re.search(
            rf"{cn_name}[^。\n]{{0,20}}(提|升|加|上|提高|增加)\D{{0,10}}(\d+)",
            clean_text,
        )
        if dir_match:
            params[lr_key] = int(dir_match.group(2))
            continue

    return params


# ──────────────────────────────────────────────
# 对话上下文管理（超过 8 轮裁剪）
# ──────────────────────────────────────────────

def trim_context(messages: list, profile: dict, session_state: dict) -> list:
    """
    对话超过 CONTEXT_MAX_ROUNDS 轮时，只保留最近 2 轮 + 一条摘要提示。
    保留结构：[档案/编辑上下文注入消息, 最近2轮(4条消息)]
    """
    # 每轮 = 1 user + 1 assistant = 2 条消息
    if len(messages) <= CONTEXT_MAX_ROUNDS * 2:
        return messages

    summary_msg = {
        "role": "user",
        "content": (
            "[系统提示] 对话历史已自动压缩。"
            f"当前用户档案：{profile_summary(profile)}。"
            f"当前编辑上下文：{session_state_summary(session_state)}。"
            "请继续保持一致的摄影师朋友口吻，并优先延续同一组照片的目标、已确认风格方向和上轮参数倾向。"
        ),
    }
    recent = messages[-4:]  # 最近 2 轮
    return [summary_msg] + recent


# ──────────────────────────────────────────────
# 流式打印辅助
# ──────────────────────────────────────────────

def _print_streaming(
    text: str,
    line_delay: float = 0.03,
    char_delay: float = 0.01,
    sink: EventSink | None = None,
) -> None:
    """
    模拟流式逐行打印文本，给用户「逐步出现」的体验。
    - 每行之间有 line_delay 秒间隔
    - 每个字符之间有 char_delay 秒间隔（打字机效果）
    """
    event_sink = ensure_event_sink(sink)
    lines = text.split("\n")
    for i, line in enumerate(lines):
        for char in line:
            event_sink.write(char, end="", flush=True)
            time.sleep(char_delay)
        if i < len(lines) - 1:
            event_sink.line()  # 换行
            time.sleep(line_delay)
    event_sink.line()  # 最后一行的换行


# ──────────────────────────────────────────────
# Vision 分析（流式输出 + 进度反馈）
# ──────────────────────────────────────────────

def extract_json_object(text: str) -> dict:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?", "", cleaned, flags=re.IGNORECASE).strip()
        cleaned = re.sub(r"```$", "", cleaned).strip()

    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("未找到 JSON 对象。")

    return json.loads(cleaned[start:end + 1])


def parse_analysis_payload(raw_text: str) -> dict:
    payload = extract_json_object(raw_text)
    summary = str(payload.get("summary", "")).strip()
    main_issues = [
        str(item).strip()
        for item in payload.get("main_issues", [])
        if str(item).strip()
    ]
    adjustments = [
        str(item).strip()
        for item in payload.get("adjustments", [])
        if str(item).strip()
    ]
    closing_line = str(payload.get("closing_line", "")).strip()
    visible_response = str(payload.get("visible_response", "")).strip()
    task_mode = str(payload.get("task_mode", "")).strip() or "single_photo"
    xmp_params = normalize_xmp_params(payload.get("xmp_params", {}))
    source_note = str(payload.get("source_note", "")).strip()
    batch_note = str(payload.get("batch_note", "")).strip()

    return {
        "summary": summary,
        "main_issues": main_issues,
        "adjustments": adjustments,
        "closing_line": closing_line,
        "visible_response": visible_response,
        "task_mode": task_mode,
        "xmp_params": xmp_params,
        "source_note": source_note,
        "batch_note": batch_note,
    }


def render_analysis_response(payload: dict) -> str:
    summary = payload.get("summary", "").strip()
    main_issues = payload.get("main_issues", [])
    adjustments = payload.get("adjustments", [])
    closing_line = sanitize_closing_line(payload.get("closing_line", ""))
    fallback_response = payload.get("visible_response", "").strip()

    if not any([summary, main_issues, adjustments, closing_line]):
        return fallback_response

    normalized_issues = []
    for item in main_issues:
        text = str(item).strip()
        if text.startswith("-"):
            text = text[1:].strip()
        if text:
            normalized_issues.append(text)

    normalized_adjustments = []
    for item in adjustments:
        text = str(item).strip()
        if not text:
            continue
        if not text.startswith("▸"):
            text = f"▸ {text.lstrip('-').strip()}"
        normalized_adjustments.append(text)

    lines: list[str] = []
    if summary:
        lines.append(summary)

    if normalized_issues:
        if lines:
            lines.append("")
        lines.append("主要问题：")
        lines.extend(f"- {item}" for item in normalized_issues)

    if normalized_adjustments:
        if lines:
            lines.append("")
        lines.append("建议调整：")
        lines.extend(normalized_adjustments)

    if closing_line:
        if lines:
            lines.append("")
        lines.append(closing_line)

    return "\n".join(lines).strip()


def build_analysis_instruction(
    user_text: str,
    media_items: list[dict],
    total_files: int,
    is_batch: bool,
) -> str:
    preview_notes = collect_preview_notes(media_items)
    preprocess_summary = "；".join(preview_notes) if preview_notes else "无"
    sample_lines = "\n".join(
        f"- 样本 {idx}: 原始文件 {item['label']}；实际分析来源 {item['source_label']}；预处理说明 {item.get('preview_note') or '无'}"
        for idx, item in enumerate(media_items, 1)
    )

    task_mode = "batch_unify" if is_batch else "single_photo"
    default_goal = (
        "请帮我统一这一组照片的基础色调和后期方向，并告诉我哪些参数适合整组复用。"
        if is_batch else
        "请帮我做一次后期诊断，并给出适合导出成 Lightroom 预设的参数。"
    )
    user_goal = user_text.strip() or default_goal

    return f"""用户诉求：{user_goal}
任务模式：{task_mode}
本次样本数：{len(media_items)} 张（原始素材总数：{total_files}）
全局预处理提示：{preprocess_summary}
样本说明：
{sample_lines}

[重要] 上方消息中已通过 base64 内联方式传入了 {len(media_items)} 张图片，请直接分析这些图片内容，不要说"未收到图片"或"上传目录为空"。

请严格按下面顺序输出，不要省略分隔符，也不要输出 Markdown 代码块：
第一部分：先直接写给用户看的自然中文正文，内容要和后面的结构化 JSON 保持一致。
第二部分：单独一行原样输出 {RESPONSE_DELIMITER}
第三部分：再输出一个 JSON 对象，字段如下：
{{
  "summary": "1 段自然中文总结，1~2 句，不要加标题",
  "main_issues": [
    "问题 1",
    "问题 2"
  ],
  "adjustments": [
    "● 高光：向下拉，中幅（参考区间 -30 ~ -50）",
    "● 阴影：向上提，较大幅度（参考区间 +40 ~ +60）"
  ],
  "closing_line": "1 句简短收尾，例如这样能让阴影细节回来一些。",
  "task_mode": "{task_mode}",
  "xmp_params": {{
    "Highlights2012": -30,
    "Shadows2012": 18
  }},
  "source_note": "可选，说明 RAW 预览、样本分析等信息",
  "batch_note": "可选，仅批量任务，说明哪些参数适合整组复用、哪些需要逐张微调",
  "visible_response": "可选，仅当上方正文缺失或不完整时作为兜底"
}}

规则：
1. 分隔符必须单独占一行，并且完全等于 {RESPONSE_DELIMITER}。
2. summary / main_issues / adjustments / closing_line 都必须是自然中文，不要输出 JSON 解释、代码块或额外说明。
3. main_issues 输出 2~3 条，adjustments 输出 3~5 条。
4. adjustments 每条都按"● 参数：方向 + 幅度 + 参考区间"的格式写；色温这种不适合精确点值的参数，可以不给区间，但要说方向和幅度。
5. closing_line 保持 1 句即可，适合作为最后收尾，不要重复追问是否生成 Lightroom 配方、预设或 XMP。
6. xmp_params 里写的是供 Lightroom 预设导出的确定数值，只写你有把握的字段；不确定就留空。
7. 如果用户有明确风格目标，回复优先围绕该目标，不要只做通用点评。
8. 如果样本图像不清晰或信息不足，summary 也要主动降级说明，xmp_params 保持稀疏。
9. 批量任务时，优先输出适合整组复用的参数，不要把明显因单张差异而变化很大的值硬写进去。
10. 如果用了 RAW 预览图或同名 JPG 预览图，请在 source_note 里简要说明。
11. 如果预处理说明里提到压缩预览、RAW 半尺寸预览、HEIC 转换或替代预览，请降低对细微高光边缘、极细色偏和宽容度的置信度，优先给稳妥建议。
"""


def analyze_photo_streaming(
    client: anthropic.Anthropic,
    system: str,
    messages: list,
    media_items: list[dict],
    user_text: str,
    total_files: int,
    is_batch: bool,
    sink: EventSink | None = None,
) -> tuple[str, dict]:
    """
    调用 Vision API，要求模型返回结构化 JSON。
    返回 (给用户展示的回复文本, 结构化分析结果)。
    """
    event_sink = ensure_event_sink(sink)
    preview_notes = collect_preview_notes(media_items)
    local_preprocess_note = "；".join(preview_notes)
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
            "text": build_analysis_instruction(user_text, media_items, total_files, is_batch),
        }
    )

    current_messages = messages + [{"role": "user", "content": content}]

    # 非流式调用 API 获取结构化 JSON（JSON 不适合直接展示给用户）
    response = _call_with_rate_limit_retries(
        lambda: client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS_CHAT,
            system=system,
            messages=current_messages,
        ),
        event_sink,
    )
    raw_text = "".join(
        block.text for block in response.content
        if getattr(block, "type", "") == "text"
    ).strip()
    visible_text, payload_text, has_structured_tail = split_response_sections(
        raw_text,
        anchor_keys=("summary", "main_issues", "adjustments", "task_mode", "xmp_params"),
    )
    payload_source = payload_text if has_structured_tail else raw_text

    model_source_note = ""
    try:
        payload = parse_analysis_payload(payload_source)
        model_source_note = compact_note_text(payload.get("source_note", ""))
        visible_response = visible_text or render_analysis_response(payload) or (
            "这次我先给了结构化结果，但可读回复不完整。你可以换个方向再让我细化。"
        )
    except (ValueError, json.JSONDecodeError):
        payload = {
            "summary": "",
            "main_issues": [],
            "adjustments": [],
            "closing_line": "",
            "visible_response": visible_text or raw_text,
            "task_mode": "batch_unify" if is_batch else "single_photo",
            "xmp_params": {},
            "source_note": "",
            "batch_note": "",
        }
        visible_response = visible_text or raw_text or (
            "这张图的光线比较特殊，我暂时没能给出具体分析。你可以换一张试试，或者用文字描述你想解决的问题，我继续帮你。"
        )

    compact_preprocess_note = compact_note_text(local_preprocess_note)
    merged_source_note = compact_note_text(merge_note_text(model_source_note, compact_preprocess_note))
    payload["source_note"] = merged_source_note
    payload["batch_note"] = compact_note_text(payload.get("batch_note", ""))

    if merged_source_note:
        visible_response = f"{visible_response}\n\n[提示] {merged_source_note}"
    if payload["batch_note"]:
        visible_response = f"{visible_response}\n\n[批量复用] {payload['batch_note']}"

    # 模拟流式逐段打印人类可读的渲染结果
    event_sink.line()
    event_sink.line("分析结果：")
    event_sink.line()
    _print_streaming(visible_response, sink=event_sink)
    event_sink.line()
    return visible_response, payload


def _call_with_rate_limit_retries(operation, event_sink: EventSink):
    for attempt, delay in enumerate(RATE_LIMIT_RETRY_DELAYS, 1):
        try:
            return operation()
        except anthropic.RateLimitError:
            event_sink.line(
                f"[提示] 请求被限流，{delay:g} 秒后自动重试"
                f"（第 {attempt}/{len(RATE_LIMIT_RETRY_DELAYS)} 次）。"
            )
            time.sleep(delay)
    return operation()


def _stream_chat_response(
    client: anthropic.Anthropic,
    system: str,
    current_messages: list,
    event_sink: EventSink,
    *,
    max_tokens: int,
    thinking: dict | None = None,
) -> str:
    request_kwargs = {
        "model": MODEL,
        "max_tokens": max_tokens,
        "system": system,
        "messages": current_messages,
    }
    if thinking is not None:
        request_kwargs["thinking"] = thinking

    def collect_stream() -> str:
        full_response = ""
        with client.messages.stream(**request_kwargs) as stream:
            for chunk in stream.text_stream:
                event_sink.write(chunk, end="", flush=True)
                full_response += chunk
        return full_response

    return _call_with_rate_limit_retries(collect_stream, event_sink)


def _looks_like_thinking_budget_issue(exc: anthropic.BadRequestError) -> bool:
    message = str(exc).lower()
    return any(
        keyword in message
        for keyword in (
            "thinking",
            "adaptive",
            "budget_tokens",
            "budget tokens",
            "max_tokens",
        )
    )


def chat_streaming(
    client: anthropic.Anthropic,
    system: str,
    messages: list,
    user_text: str,
    sink: EventSink | None = None,
) -> str:
    """
    纯文字对话（无图片），流式输出。
    """
    event_sink = ensure_event_sink(sink)
    current_messages = messages + [{"role": "user", "content": user_text}]
    event_sink.line()

    try:
        full_response = _stream_chat_response(
            client,
            system,
            current_messages,
            event_sink,
            max_tokens=MAX_TOKENS_CHAT_THINKING,
            thinking={"type": "adaptive"},
        )
    except anthropic.BadRequestError as exc:
        if not _looks_like_thinking_budget_issue(exc):
            raise
        event_sink.line("[提示] 当前会话已自动切换为标准回复模式，以保证回复继续输出。")
        full_response = _stream_chat_response(
            client,
            system,
            current_messages,
            event_sink,
            max_tokens=MAX_TOKENS_CHAT,
        )

    if not full_response:
        full_response = "抱歉，我暂时没能生成回复，请再试一次或换个方式描述你的问题。"
        event_sink.line(full_response)

    event_sink.line()
    return full_response


# ──────────────────────────────────────────────
# 用户档案初始化流程
# ──────────────────────────────────────────────

def init_profile_interactive(profile: dict) -> dict:
    """
    首次使用时通过多个问题收集基础档案信息。
    Agent 引导用户回答，解析后写入档案。
    """
    print("\n" + "─" * 60)
    print("🎞️  在开始分析之前，我需要了解一下你的拍摄和修图习惯（共 8 个小问题，可留空跳过）")
    print("─" * 60)

    questions = [
        ("device_info", "你平时用什么相机拍照？主要用哪个焦段的镜头？（例如：索尼 A7M4，主要用 35mm 定焦）"),
        ("style_preference", "你主要拍什么类型的题材？偏好什么样的色调风格？（例如：人像为主，喜欢日系清新色调）"),
        ("editing_software", "你平时主要用什么修图软件？（例如：Lightroom、Camera Raw、Capture One、手机软件）"),
        ("skill_level", "你觉得自己现在的后期水平大概在哪个阶段？（例如：入门 / 进阶 / 接单）"),
        ("favorite_subjects", "你最常拍的题材是什么？（例如：婚礼人像、旅行风光、街拍纪实、电商静物）"),
        ("delivery_platform", "你的照片主要交付到哪里？（例如：朋友圈、小红书、客片、作品集、电商详情页）"),
        ("skin_tone_preference", "如果拍人像，你偏好的肤色方向是什么？（例如：自然一点、偏暖通透、冷白一些）"),
        ("retouch_tendency", "你的修图倾向更偏哪种？（例如：保守自然、轻微风格化、电影感明显）"),
    ]

    for i, (field, question) in enumerate(questions, 1):
        print(f"\n问题 {i}：{question}")
        ans = input("你的回答（留空跳过）：").strip()
        if ans:
            profile[field] = ans

    save_profile(profile)
    print("\n✅ 档案已保存！以后不用重复填写了。\n")
    return profile


# ──────────────────────────────────────────────
# XMP 预设输出辅助
# ──────────────────────────────────────────────

def offer_xmp_export(
    xmp_params: dict | None,
    image_name: str = "",
    analysis_text: str = "",
) -> None:
    """
    直接生成 XMP 预设文件（不再二次询问，由调用方决定是否触发）。
    默认从结构化参数对象生成，仅在兼容旧结果时回退到自然语言反推。
    image_name: 原始图片文件名（不含扩展名），用于预设命名。
    """
    print("\n⚠️  建议先备份原始文件，再导入以下预设。")
    print("📌 此脚本优先基于结构化参数生成；实际效果因原片而异，请在 Lightroom 中手动微调。\n")

    params = normalize_xmp_params(xmp_params)
    if not params and analysis_text:
        params = normalize_xmp_params(extract_xmp_params_from_text(analysis_text))

    if not params:
        print("（当前没有足够稳定的结构化参数可导出，请先重新分析或继续微调后再导出）")
        return

    # 预设名称包含图片名
    preset_name = f"AI建议_{image_name}" if image_name else "AI摄影助手建议"
    xmp_content = build_xmp_preset(params, preset_name=preset_name)

    # 保存到专用文件夹，文件名包含图片名，不会互相覆盖
    preset_dir = Path(__file__).parent / "presets"
    preset_dir.mkdir(exist_ok=True)
    file_name = f"{image_name}.xmp" if image_name else "ai_preset.xmp"
    xmp_path = preset_dir / file_name

    try:
        with open(xmp_path, "w", encoding="utf-8") as f:
            f.write(xmp_content)
        print(f"✅ 预设文件已保存至：{xmp_path}")
        print("   导入方法：Lightroom → 预设面板 → 右键「导入预设」→ 选择此文件\n")
    except OSError:
        # 如果无法写文件，直接打印到终端供复制
        print("── .xmp 预设内容（复制以下内容保存为 .xmp 文件）──")
        print(xmp_content)


# ──────────────────────────────────────────────
# 主交互循环
# ──────────────────────────────────────────────

def print_banner() -> None:
    print("=" * 60)
    print("  📷  摄影全栈 Agent — V1 后期辅助模块")
    print("  支持单图、RAW 预览分析、文件夹批量统一与路径 + 目标描述输入")
    print("  支持格式：JPEG / PNG / HEIC / 常见 RAW（≤ 20 MB，部分大图自动压缩）")
    print(f"  可直接把图片拖进终端；一次最多直接输入 {MAX_DIRECT_MEDIA_INPUTS} 张，文件夹模式最多抽样 {BATCH_SAMPLE_LIMIT} 张")
    print("  输入 'quit' 或 'exit' 退出")
    print("=" * 60)


def _render_input_format_tips_message() -> str:
    return (
        "\n输入提示：\n"
        "  默认理解规则：\n"
        "  1. 只发一张图片路径：默认进入后期辅助\n"
        "  2. 只发一个文件夹路径：默认进入素材管理并建立索引\n"
        '  3. 想进入学习教练：请在路径后补一句"点评 / 评估 / 指导怎么拍更好"\n'
        '  4. 想明确分开"路径"和"说明"：推荐用 ::\n'
        "  常见示例：\n"
        "  5. 单图后期：\"C:/Photos/shot.jpg\" 修成电影感\n"
        '  6. 单图点评：\"C:/Photos/shot.jpg\" 评估这张照片，并指导怎么拍更好\n'
        "  7. 文件夹筛片：\"C:/Photos/set01\"\n"
        "  8. 多图统一风格：\"C:/A.jpg\" \"C:/B.jpg\" :: 统一成日系\n"
        "  路径格式：\n"
        "  9. 可以直接把图片或文件夹拖进终端，系统会自动粘贴本地路径；这是正常的\n"
        "  10. 路径里没有空格：可直接输入，例如 C:/Photos/shot.jpg\n"
        '  11. 路径里有空格：请用英文双引号包住，例如 \"C:/My Photos/shot 01.jpg\"\n'
        f"  12. 一次最多直接输入 {MAX_DIRECT_MEDIA_INPUTS} 张图片或 RAW 文件；超过时建议改为输入文件夹\n"
        f"  13. 文件夹批量分析时，程序会自动抽样最多 {BATCH_SAMPLE_LIMIT} 张作为代表样本\n"
        "  14. 换新图片时默认按新任务重新分析；如果你想延续上一张或上一组的风格，请直接说明\n"
    )


def print_input_format_tips(sink: EventSink | None = None) -> None:
    event_sink = ensure_event_sink(sink)
    event_sink.line(_render_input_format_tips_message())


def print_help() -> None:
    print("""
可用命令：
  [图片路径]                      上传图片进行后期诊断，例如：C:/Photos/shot.jpg
  "图片路径" 修成电影感            单图 + 目标风格，例如："C:/Photos/shot.jpg" 修成电影感
  "图片1" "图片2" :: 统一成日系     一次最多直接输入 6 张图片或 RAW 文件
  "文件夹路径" :: 统一成日系        批量统一一组照片的色调（程序最多抽样 6 张代表图）
  xmp / 预设 / 生成预设            任选其一，为当前结果生成 Lightroom 预设
  profile      查看当前用户档案
  reset        重置用户档案（重新填写）
  quit / exit  退出程序
""")
    print_input_format_tips()


def prompt_yes_no(question: str) -> bool:
    valid_yes = {"y", "yes", "是"}
    valid_no = {"n", "no", "否"}

    while True:
        answer = input(question).strip().lower()
        if answer in valid_yes:
            return True
        if answer in valid_no:
            return False
        print('请输入 y 或 n；如果你想用中文，也可以输入"是"或"否"。')


def maybe_print_media_input_hint(user_input: str, sink: EventSink | None = None) -> None:
    event_sink = ensure_event_sink(sink)
    lowered = user_input.lower()
    if "::" in user_input or any(ext in lowered for ext in SUPPORTED_INPUT_EXTS):
        event_sink.line(
            "\n[提示] 如果你想上传图片或文件夹，请参考输入格式：\n"
            "  - 把图片或文件夹拖进终端后，最终看到的仍然是本地路径文本，这是正常的\n"
            "  - 只有当程序成功解析到这些路径时，我才能真正读取图片；否则模型只会把它当普通文字\n"
            "  - 路径里有空格时，请用英文双引号包住\n"
            "  - 路径后面要接完整说明时，推荐用 :: 分隔\n"
            "  - 多张图更稳妥的写法是每个路径都加引号，再在后面补说明\n"
            f"  - 一次最多直接输入 {MAX_DIRECT_MEDIA_INPUTS} 张图片；更多素材建议直接输入文件夹\n"
            f"  - 文件夹模式会自动抽样最多 {BATCH_SAMPLE_LIMIT} 张做分析\n"
            "  - 例如：\"C:/Users/25320/Pictures/R.jpg\" \"C:/Users/25320/Pictures/G_1.jpg\" :: 这两张应该怎么后期？\n"
            "  - 例如：\"C:/My Photos/shot 01.jpg\" 修成电影感\n"
            "  - 例如：\"C:/Photos/set01\" :: 统一成日系\n"
        )


def legacy_standalone_main() -> None:
    # ── 初始化 ──
    client = create_anthropic_client(source_cli="photo_v1.py")
    profile = load_profile()
    session_state = dict(DEFAULT_SESSION_STATE)
    messages: list = []
    last_analysis: str = ""
    last_analysis_payload: dict = {}
    last_image_name: str = ""        # 上一次分析的图片名（用于 XMP 命名）
    first_run = True

    # ── 加载 Skills 知识库 ──
    skills_knowledge = load_skills_knowledge()
    if skills_knowledge:
        loaded_count = skills_knowledge.count("[知识来源：")
        print(f"  📚 已加载 {loaded_count} 个摄影知识 Skills")
    else:
        print("  📚 未检测到已安装的 Skills（可用 npx skills find 搜索安装）")

    print_banner()

    # 首次能力边界说明
    print(
        "\n💬 你好！我现在可以帮你分析照片的后期问题，"
        "给出具体的调整建议和 Lightroom 参数配方。\n"
        "   每次对话内容独立，会话结束后不保留照片，但你的设备和风格档案会跨会话保存。\n"
    )
    print_input_format_tips()

    # ── 主循环 ──
    while True:
        try:
            user_input = input("你：").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n\n再见！下次带着新作品来聊 📷")
            break

        if not user_input:
            continue

        cmd = user_input.lower()

        # ── 退出 ──
        if cmd in {"quit", "exit", "q", "退出"}:
            print("再见！下次带着新作品来聊 📷")
            break

        # ── 帮助 ──
        if cmd in {"help", "帮助", "?"}:
            print_help()
            continue

        # ── 查看档案 ──
        if cmd in {"profile", "档案", "我的档案"}:
            print(f"\n📋 当前用户档案：\n{profile_summary(profile)}\n")
            continue

        # ── 重置档案 ──
        if cmd in {"reset", "重置", "重新填写"}:
            profile = dict(DEFAULT_PROFILE)
            session_state = dict(DEFAULT_SESSION_STATE)
            last_analysis = ""
            last_analysis_payload = {}
            last_image_name = ""
            save_profile(profile)
            print("档案已重置，下次对话时重新填写。\n")
            continue

        # ── XMP 导出 ──
        if is_export_command(user_input):
            xmp_params = last_analysis_payload.get("xmp_params") or session_state.get("last_xmp_params")
            if last_analysis or xmp_params:
                offer_xmp_export(
                    xmp_params,
                    last_image_name,
                    analysis_text=last_analysis,
                )
            else:
                print("请先上传照片进行分析，再生成预设。\n")
            continue

        # ── 首次对话：档案初始化 ──
        if first_run and not is_profile_initialized(profile):
            profile = init_profile_interactive(profile)
            first_run = False

        first_run = False

        # ── 重建 System Prompt（档案可能已更新）──
        system = build_system_prompt(profile, skills_knowledge)

        # ── 解析媒体输入（单图 / RAW / 文件夹批量 / 路径 + 目标描述）──
        media_request = parse_media_request(user_input)
        is_media_request = media_request is not None
        prepared_items: list[dict] = []
        expanded_paths: list[Path] = []
        is_batch = False
        request_prompt = user_input

        if not is_media_request and looks_like_local_media_reference(user_input):
            print(
                "\n[提示] 我识别到你输入的是本地图片路径，但这轮没有成功解析成可读取的图片内容，"
                "所以如果继续发给模型，它只会把这些路径当普通文字。\n"
                "请优先用更稳妥的格式重试，例如：\n"
                "  \"C:/Users/25320/Pictures/R.jpg\" \"C:/Users/25320/Pictures/G_1.jpg\" :: 这两张应该怎么后期？\n"
                "  \"C:/Users/25320/Pictures/R.jpg\" 修成电影感\n"
            )
            print_input_format_tips()
            continue

        if is_media_request:
            request_prompt = media_request["prompt"]
            request_paths = media_request["paths"]
            current_media_signature = build_media_signature(request_paths)
            previous_media_signature = list(session_state.get("current_media_signature", []))
            should_inherit_context = has_context_carryover_intent(user_input) or has_context_carryover_intent(request_prompt)

            if (
                previous_media_signature and
                current_media_signature != previous_media_signature and
                not should_inherit_context
            ):
                # 换图片时清理对话历史，但保留上组风格摘要供"继续上一组风格"使用
                prev_style_summary = ''
                if session_state.get('last_summary'):
                    prev_style_summary = session_state['last_summary']
                prev_adjustments = list(session_state.get('confirmed_adjustments', []))[:5]
                prev_xmp_params = dict(session_state.get('last_xmp_params', {}))

                # 清空对话历史，注入上组风格摘要作为上下文桥梁
                style_bridge_parts = []
                if prev_style_summary:
                    style_bridge_parts.append(f'上组风格结论：{prev_style_summary}')
                if prev_adjustments:
                    adj_text = '；'.join(prev_adjustments)
                    style_bridge_parts.append(f'上组调整方向：{adj_text}')
                if style_bridge_parts:
                    bridge_text = '；'.join(style_bridge_parts)
                    messages = [
                        {
                            'role': 'user',
                            'content': (
                                '[系统提示] 用户切换了新素材。以下是上一组照片的风格摘要，'
                                '仅在用户主动要求"延续上组风格"时参考，否则按新任务独立分析。\n'
                                + bridge_text
                            ),
                        },
                        {
                            'role': 'assistant',
                            'content': '好的，已记录上组风格方向。请上传新素材，我来分析。',
                        },
                    ]
                else:
                    messages = []

                # 重置 session_state，但保留上组的 xmp_params 和风格信息
                session_state = dict(DEFAULT_SESSION_STATE)
                session_state["last_xmp_params"] = prev_xmp_params
                session_state["last_summary"] = prev_style_summary
                session_state["confirmed_adjustments"] = prev_adjustments
                last_analysis = ''
                last_analysis_payload = {"xmp_params": prev_xmp_params} if prev_xmp_params else {}
                last_image_name = ''
                print(
                    '\n[提示] 检测到你换了新的图片/素材，我会按新任务重新分析。'
                    '上一张图的对话历史已清空，但风格方向和预设参数已保留；'
                    '如果你想延续上一组的风格，请直接说"继续上一张"或"按上一组风格来"。'
                )

            print("\n⏳ 正在读取素材，准备分析…")
            try:
                prepared_items, expanded_paths, is_batch = prepare_media_items(request_paths)
            except ValueError as e:
                print(f"\n❌ {e}\n")
                continue
            except OSError as e:
                print(f"\n❌ 素材读取失败：{e}\n")
                continue

            if is_batch:
                print(
                    f"✅ 已载入 {len(prepared_items)} 张分析样本"
                    f"（原始素材共 {len(expanded_paths)} 张），AI 开始生成整组后期方案…"
                )
            else:
                print("✅ 图片已加载，AI 开始分析（30 秒内返回结果）…")

        # ── 上下文裁剪 ──
        messages = trim_context(messages, profile, session_state)

        # ── 调用 API ──
        try:
            if is_media_request:
                response_text, analysis_payload = analyze_photo_streaming(
                    client,
                    system,
                    messages,
                    prepared_items,
                    request_prompt,
                    len(expanded_paths),
                    is_batch,
                )
                last_analysis = response_text
                last_analysis_payload = analysis_payload

                first_path = media_request["paths"][0]
                if is_batch:
                    last_image_name = (
                        f"{first_path.name}_batch" if first_path.is_dir()
                        else f"{first_path.stem}_batch"
                    )
                else:
                    last_image_name = first_path.stem

                session_state = update_session_state_from_analysis(
                    session_state,
                    request_prompt,
                    media_request,
                    analysis_payload,
                    is_batch,
                )

                if analysis_payload.get("xmp_params"):
                    print("─" * 60)
                    xmp_label = "整组统一" if is_batch else "当前结果"
                    print(
                        f"[预设] 已准备好{xmp_label}可导出的 Lightroom 参数。"
                        "想继续微调就直接说下一步；要导出 .xmp 时，输入 xmp、预设 或 生成预设 任一命令即可。"
                    )
                else:
                    print("─" * 60)
                    print("这次结果里还没有足够稳定的结构化参数，我先不建议直接导出预设。\n")

            else:
                response_text = chat_streaming(
                    client, system, messages, user_input
                )
                session_state = update_session_state_from_chat(session_state, user_input)
                text_xmp_params = normalize_xmp_params(extract_xmp_params_from_text(response_text))
                if text_xmp_params:
                    last_analysis = response_text
                    last_analysis_payload = {
                        **last_analysis_payload,
                        "xmp_params": text_xmp_params,
                    }
                    session_state["last_xmp_params"] = text_xmp_params
                maybe_print_media_input_hint(user_input)

        except anthropic.BadRequestError as e:
            err_str = str(e)
            msg = err_str.lower()
            # 仅在确实是上下文长度超限时才清空（需要同时匹配关键词组合）
            is_context_too_long = (
                ("上下文" in err_str and "超出" in err_str) or
                ("context" in msg and ("too long" in msg or "exceed" in msg or "limit" in msg)) or
                ("too many tokens" in msg) or
                ("maximum context length" in msg)
            )
            if is_context_too_long:
                # 上下文超限 → 强制清空历史，只保留最新请求
                print(
                    "\n⚠️ 对话历史太长了，我已自动清空上下文。请重新输入你的图片或问题。\n"
                )
                messages = []
                session_state = dict(DEFAULT_SESSION_STATE)
                last_analysis = ""
                last_analysis_payload = {}
                last_image_name = ""
                continue
            elif "image" in msg or "media" in msg:
                print(
                    "\n❌ 图片格式有问题，API 无法解析。\n"
                    "   这张图的光线比较特殊，我先说一下我的判断，你来告诉我理解是否准确：\n"
                    "   图片可能存在极暗、极模糊或不是摄影照片的情况。\n"
                    "   可以换一张或用文字描述你的问题，我继续帮你分析。\n"
                )
            else:
                print(f"\n❌ 请求出错：{e}\n")
            continue

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
            if e.status_code >= 500:
                print(f"\n❌ 服务器暂时出了点问题（{e.status_code}），稍后重试。\n")
            else:
                print(f"\n❌ API 错误 {e.status_code}：{e.message}\n")
            continue

        # ── 更新对话历史 ──
        if is_media_request:
            request_summary = request_prompt or ("批量统一色调" if is_batch else "默认后期诊断")
            upload_label = "批量素材" if is_batch else "图片"
            uploaded_names = [path.name for path in media_request["paths"][:3]]
            if len(media_request["paths"]) > 3:
                uploaded_names.append("...")
            messages.append(
                {
                    "role": "user",
                    "content": f"[已上传{upload_label}] {', '.join(uploaded_names)} | 诉求: {request_summary}",
                }
            )
        else:
            messages.append({"role": "user", "content": user_input})

        messages.append({"role": "assistant", "content": response_text})

        print()


# ──────────────────────────────────────────────
# 入口
# ──────────────────────────────────────────────

def main() -> None:
    from photo import main as unified_main

    unified_main(preferred_module="post", source_cli="photo_v1.py")


if __name__ == "__main__":
    main()
