"""Replay the original case through production conversion code, without editing an image.

This verifies the proposed numeric tool payload, not an executed Agent trace.
Historical observations and the artificial evaluator fixture remain unchanged.
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "backend"))
from app.orchestration.retouch_advice import convert_post_advice
from evaluate import evaluate


def main():
    case = json.loads((HERE / "case.json").read_text(encoding="utf-8"))
    advice = convert_post_advice(case["input"]["post_xmp_params"], job_id="case_replay",
                                 media_id="case_replay", result_id="case_replay")
    trace = {"trace_kind": "production_converter_output_not_executed", "execution_status": "not_executed",
             "tool_calls": [{"tool": "adjust_image", "params": advice["params"]}],
             "unsupported_handling": {r["parameter"]: {"action": "skipped", "reason": r["reason"]}
                                      for r in advice["skipped"]}}
    report = evaluate(case, trace)
    report["conversion_policy"] = advice["policy_version"]
    report["scope"] = "Production converter replay only; no browser, image execution or aesthetic assessment."
    out = HERE / "reports"
    out.mkdir(exist_ok=True)
    (out / "converter-result.json").write_text(json.dumps({"advice": advice, "trace": trace, "report": report},
                                                        ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"semantic_contract_passed": report["semantic_contract_passed"],
                      "failed_checks": report["failed_checks"], "checks": len(report["checks"]),
                      "tool_execution_status": report["tool_execution_status"]}, indent=2))
    return 0 if report["semantic_contract_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
