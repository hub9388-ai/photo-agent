"""Deterministic, approximate Post-to-slider policy; never calls a model.

These are conservative initial values, NOT Lightroom/Pillow equivalence.
Only structured XMP values are interpreted. Narrative instructions stay narrative.
"""
import math

POLICY_VERSION = "post-sliders-v1"
RULES = {
    "Contrast2012": ("contrast", "对比度", .25),
    "Highlights2012": ("highlights", "高光", .40),
    "Shadows2012": ("shadows", "阴影", .35),
    "Saturation": ("saturation", "饱和度", .30),
    "Vibrance": ("vibrance", "自然饱和度", .20),
    "Clarity2012": ("clarity", "清晰度", .20),
}


def convert_post_advice(source: dict, *, job_id: str, media_id: str, result_id: str) -> dict:
    params, converted, skipped = {}, [], []
    def skip(key, raw, reason):
        # JSON-safe original evidence, including invalid input, without treating text as executable advice.
        safe = raw if raw is None or isinstance(raw, (str, bool, int)) or isinstance(raw, float) and math.isfinite(raw) else str(raw)
        if isinstance(safe, str):
            safe = safe[:300]
        skipped.append({"parameter": key, "source_value": safe, "reason": reason})

    for key, raw in source.items():
        key = str(key)
        rule = RULES.get(key)
        if rule is None:
            skip(key, raw, "没有已确认的对应转换规则，未替代为亮度或锐化。")
            continue
        if isinstance(raw, bool) or not isinstance(raw, (int, float)) or abs(raw) > 100 or not math.isfinite(raw):
            skip(key, raw, "需要 -100 到 100 的有限数值，未从文字或区间猜测。")
            continue
        target, label, limit = rule
        if target == "clarity" and raw < 0:
            skip(key, raw, "负向清晰度尚未校准，未自动执行。")
            continue
        value = round(max(-limit, min(limit, raw / 100)), 4)
        params[target] = value
        converted.append({"parameter": key, "label": label, "source_value": raw,
                          "source_unit": "摄影软件参考刻度（-100～100）", "target": target,
                          "value": value, "approximate": True, "clamped": abs(raw / 100) > limit,
                          "rule": f"原值 / 100；初始幅度限制 ±{limit}",
                          "preview": target != "clarity"})
    return {"policy_version": POLICY_VERSION, "source_job_id": job_id,
            "source_media_id": media_id, "source_result_id": result_id,
            "params": params, "converted": converted, "skipped": skipped}
