"""Judge tests, not tests proving that the live agent has been repaired."""
import copy
import json
import unittest
from pathlib import Path

from evaluate import evaluate

ROOT = Path(__file__).resolve().parent


class EvaluationTests(unittest.TestCase):
    def setUp(self):
        self.case = json.loads((ROOT / "case.json").read_text(encoding="utf-8"))
        self.history = json.loads((ROOT / "historical_trace.json").read_text(encoding="utf-8"))
        self.synthetic = json.loads((ROOT / "fixtures/synthetic_pass.json").read_text(encoding="utf-8"))

    def test_historical_successful_tool_is_semantic_failure(self):
        result = evaluate(self.case, self.history)
        self.assertEqual(result["tool_execution_status"], "succeeded")
        self.assertFalse(result["semantic_contract_passed"])
        self.assertEqual(set(result["failed_checks"]), {
            "direction.shadows", "no_substitution.brightness", "no_substitution.sharpness",
            "unsupported.Blacks2012", "unsupported.Dehaze",
        })

    def test_synthetic_positive_control_is_only_a_judge_test(self):
        result = evaluate(self.case, self.synthetic)
        self.assertTrue(result["semantic_contract_passed"])
        self.assertEqual(result["trace_kind"], "synthetic_judge_test_only")
        self.assertEqual(result["tool_execution_status"], "not_executed")

    def test_direction_and_neutral_shadow_cannot_pass(self):
        for value in (0, 0.12, None, True, "-0.1", float("nan")):
            trace = copy.deepcopy(self.synthetic)
            trace["tool_calls"][0]["params"]["shadows"] = value
            self.assertIn("direction.shadows", evaluate(self.case, trace)["failed_checks"])

    def test_explanation_without_correct_execution_does_not_pass(self):
        trace = copy.deepcopy(self.history)
        trace["unsupported_handling"] = self.synthetic["unsupported_handling"]
        result = evaluate(self.case, trace)
        self.assertIn("no_substitution.brightness", result["failed_checks"])
        self.assertIn("no_substitution.sharpness", result["failed_checks"])

    def test_skipped_without_reason_does_not_pass(self):
        trace = copy.deepcopy(self.synthetic)
        trace["unsupported_handling"]["Dehaze"]["reason"] = " "
        self.assertIn("unsupported.Dehaze", evaluate(self.case, trace)["failed_checks"])

    def test_missing_duplicate_unknown_and_out_of_range_calls_fail(self):
        traces = []
        missing = copy.deepcopy(self.synthetic)
        missing["tool_calls"] = []
        traces.append(missing)
        duplicate = copy.deepcopy(self.synthetic)
        duplicate["tool_calls"] *= 2
        traces.append(duplicate)
        for key, value in [("shadows", -2), ("dehaze", 0.08), ("layer_id", "other-layer")]:
            trace = copy.deepcopy(self.synthetic)
            trace["tool_calls"][0]["params"][key] = value
            traces.append(trace)
        for trace in traces:
            self.assertFalse(evaluate(self.case, trace)["semantic_contract_passed"])


if __name__ == "__main__":
    unittest.main()
