"""Offline deterministic trace evaluation; standard library only, no model calls."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VERSION = "1.0"


def finite_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def evaluate(case: dict, trace: dict) -> dict:
    contract = case["contract"]
    checks = []

    def check(name, passed, expected, actual):
        checks.append({"id": name, "passed": bool(passed), "expected": expected, "actual": actual})

    calls = trace.get("tool_calls")
    calls = calls if isinstance(calls, list) else []
    shape_ok = len(calls) == contract["required_call_count"] and all(
        isinstance(call, dict) and call.get("tool") == contract["required_tool"]
        and isinstance(call.get("params"), dict) for call in calls
    )
    check("tool_call_shape", shape_ok, "exactly one adjust_image call with params object", calls)
    # Never select the last call to hide duplicate/unrelated tool calls.
    params = calls[0]["params"] if shape_ok else {}
    supported = contract["supported_directions"]
    neutral = contract["must_remain_neutral"]
    allowed = set(supported) | set(neutral) | {"layer_id"}
    unknown = sorted(set(params) - allowed)
    invalid = {k: v for k, v in params.items() if k != "layer_id" and (
        not finite_number(v) or not (-1 <= v <= 1)
        or (k == "vignette" and v < 0)
    )}
    layer_ok = params.get("layer_id") in (None, "base")
    check("parameter_schema", shape_ok and not unknown and not invalid and layer_ok,
          "finite tool-range numbers, recognized keys, base/default layer",
          {"unknown": unknown, "invalid": invalid, "layer_id": params.get("layer_id")})
    for name, direction in supported.items():
        value = params.get(name)
        ok = finite_number(value) and (value < 0 if direction == "negative" else value > 0)
        check(f"direction.{name}", ok, direction, value)
    for name in neutral:
        value = params.get(name, 0)
        check(f"no_substitution.{name}", finite_number(value) and value == 0,
              "absent or zero; no authorized substitute", value)
    handling = trace.get("unsupported_handling")
    handling = handling if isinstance(handling, dict) else {}
    for feature in contract["unsupported_source_features"]:
        item = handling.get(feature)
        item = item if isinstance(item, dict) else {}
        reason = item.get("reason")
        check(f"unsupported.{feature}", item.get("action") == "skipped"
              and isinstance(reason, str) and bool(reason.strip()),
              "skipped with nonempty reason", item)
    return {
        "case_id": case["case_id"], "case_version": case["version"],
        "evaluator_version": VERSION, "evaluation_mode": "offline_trace_replay",
        "trace_kind": trace.get("trace_kind", "unspecified"),
        "tool_execution_status": trace.get("execution_status", "unknown"),
        "semantic_contract_passed": all(item["passed"] for item in checks),
        "failed_checks": [item["id"] for item in checks if not item["passed"]],
        "checks": checks, "limits": case["out_of_scope"],
    }


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trace", type=Path, default=ROOT / "historical_trace.json")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    case_path = ROOT / "case.json"
    try:
        case = json.loads(case_path.read_text(encoding="utf-8"))
        trace = json.loads(args.trace.read_text(encoding="utf-8"))
        if not isinstance(trace, dict):
            raise ValueError("trace must be a JSON object")
        report = evaluate(case, trace)
        report["sha256"] = {"case": digest(case_path), "trace": digest(args.trace),
                            "evaluator": digest(Path(__file__))}
    except (OSError, ValueError, TypeError, KeyError) as exc:
        parser.exit(2, f"Invalid evaluation input: {exc}\n")
    result = json.dumps(report, ensure_ascii=True, indent=2, allow_nan=False)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(result + "\n", encoding="utf-8")
    print(result)
    return 0 if report["semantic_contract_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
