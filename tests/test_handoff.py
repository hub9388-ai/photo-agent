import unittest

import photo
import photo_v3
import photo_v4
from photo_handoff import create_pending_handoff_request, consume_pending_handoff_input
from photo_utils import normalize_string_list


class SharedUtilsTests(unittest.TestCase):
    def test_normalize_string_list_deduplicates_and_trims(self) -> None:
        values = ["  warm  ", "-warm", " cool ", "", "warm", "  - cool  "]

        normalized = normalize_string_list(values, limit=3)

        self.assertEqual(normalized, ["warm", "cool"])
        self.assertEqual(photo_v3.normalize_string_list(values, limit=3), normalized)
        self.assertEqual(photo_v4.normalize_string_list(values, limit=3), normalized)

    def test_asset_fallback_prefers_handoff_over_grade_view(self) -> None:
        intent = photo_v4.fallback_asset_intent("把精选片送去后期辅助", False, True)

        self.assertEqual(intent["task_mode"], "prepare_handoff")
        self.assertEqual(intent["destination"], "post")

    def test_resolve_asset_intent_prefers_explicit_grade_command(self) -> None:
        class FakeTextBlock:
            type = "text"
            text = '{"task_mode":"show_grade_a","user_goal":"show best picks"}'

        class FakeResponse:
            content = [FakeTextBlock()]

        class FakeMessages:
            @staticmethod
            def create(**kwargs):
                del kwargs
                return FakeResponse()

        class FakeClient:
            messages = FakeMessages()

        intent = photo_v4.resolve_asset_intent(
            FakeClient(),
            "看佳片",
            {},
            {},
            False,
            True,
        )

        self.assertEqual(intent["task_mode"], "show_grade_b")


class HandoffOrchestrationTests(unittest.TestCase):
    def test_handoff_selection_response_uses_grade_labels(self) -> None:
        text = photo.build_handoff_selection_response(
            "post",
            [
                {
                    "absolute_path": r"C:\Users\25320\Pictures\cat\CAT_19.jpg",
                    "relative_path": "CAT_19.jpg",
                    "delivery_grade": "B",
                    "scene_id": "scene_003",
                    "quality_score": 78.54,
                }
            ],
            "这些典藏 / 佳片更适合继续流转到后期辅助做统一调色和参数建议。",
        )

        self.assertIn("1. [佳片] CAT_19.jpg", text)
        self.assertIn("也可以直接回复文件名", text)
        self.assertNotIn("[B]", text)

    def test_consume_pending_handoff_accepts_selected_assets(self) -> None:
        assets = [
            {
                "absolute_path": r"C:\Users\25320\Pictures\cat\CAT_1.jpg",
                "relative_path": "CAT_1.jpg",
                "delivery_grade": "B",
                "scene_id": "scene_001",
                "quality_score": 77.46,
            },
            {
                "absolute_path": r"C:\Users\25320\Pictures\cat\CAT_2.jpg",
                "relative_path": "CAT_2.jpg",
                "delivery_grade": "B",
                "scene_id": "scene_001",
                "quality_score": 72.27,
            },
        ]
        pending_request = create_pending_handoff_request("post", assets, "请选择要继续后期的照片")

        result = consume_pending_handoff_input(
            "1 2 :: keep warm gray night mood",
            pending_request,
            route_labels=photo.ROUTE_LABELS,
            media_request_parser=lambda _: None,
        )

        self.assertEqual(result["status"], "accepted")
        self.assertEqual(result["destination"], "post")
        self.assertEqual(len(result["selected_assets"]), 2)
        self.assertIn("keep warm gray night mood", result["media_request"]["prompt"])

    def test_consume_pending_handoff_reports_invalid_selection(self) -> None:
        assets = [
            {
                "absolute_path": r"C:\Users\25320\Pictures\cat\CAT_1.jpg",
                "relative_path": "CAT_1.jpg",
                "delivery_grade": "B",
                "scene_id": "scene_001",
                "quality_score": 77.46,
            }
        ]
        pending_request = create_pending_handoff_request("coach", assets, "请选择要送去学习教练的照片")

        result = consume_pending_handoff_input(
            "not-a-valid-selection",
            pending_request,
            route_labels=photo.ROUTE_LABELS,
            media_request_parser=lambda _: None,
        )

        self.assertEqual(result["status"], "invalid")
        self.assertIn("没有识别出你的选择", result["message"])


if __name__ == "__main__":
    unittest.main()
