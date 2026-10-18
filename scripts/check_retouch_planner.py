"""Two real text planning calls; validate plans but never execute any tool."""
import asyncio
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "integrations/ai-retouch-agent/backend"))


async def main() -> int:
    from app.agent.graph import run
    from app.config import get_settings
    settings = get_settings()
    report = {"planner_model": settings.planner_model, "image_provider": settings.image_provider,
              "image_model": settings.image_edit_model, "tools_executed": 0,
              "image_requests": 0, "cases": [], "status": "passed"}
    context = "当前画布768×1024，只有一张猫咪照片图层，id=background；无选区。"
    for goal, expected in [
        ("只将整张照片的亮度提高20%，其他保持不变。", "adjust_image"),
        ("让照片中的猫咪脸颊略微圆润，眼神有点好奇迷惑，保持毛色、坐姿和街景。", "replace_region"),
    ]:
        started = time.monotonic()
        case = {"goal": goal, "expected_tool": expected, "status": "failed"}
        try:
            reply, plan = await run(goal, context)
            case.update(reply=reply, plan=plan, elapsed_ms=round((time.monotonic() - started) * 1000))
            if len(plan) == 1 and plan[0]["tool"] == expected:
                case["status"] = "passed"
        except Exception as exc:
            case["error_type"] = type(exc).__name__
        if case["status"] != "passed":
            report["status"] = "failed"
        report["cases"].append(case)
    out = ROOT / ".test_artifacts/retouch-live"
    out.mkdir(parents=True, exist_ok=True)
    (out / "planner-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=True, indent=2))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
