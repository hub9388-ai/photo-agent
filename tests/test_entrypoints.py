import unittest
from pathlib import Path
from unittest.mock import patch

import photo
import photo_v1
import photo_v2
import photo_v3
import photo_v4


PLAN_PROMPT = "\u53bb\u54ea\u91cc\u62cd\uff0c\u7ed9\u6211\u673a\u4f4d\u548c\u62cd\u6444\u6e05\u5355"
ASSET_PROMPT = "\u5e2e\u6211\u6574\u7406\u8fd9\u6279\u7167\u7247\uff0c\u505a\u5f52\u6863\u548c\u6807\u7b7e\u5efa\u8bae"


class EntrypointTests(unittest.TestCase):
    def test_photo_v1_main_delegates_to_unified_entry(self) -> None:
        with patch("photo.main") as mocked_main:
            photo_v1.main()
        mocked_main.assert_called_once_with(preferred_module="post", source_cli="photo_v1.py")

    def test_photo_v2_main_delegates_to_unified_entry(self) -> None:
        with patch("photo.main") as mocked_main:
            photo_v2.main()
        mocked_main.assert_called_once_with(preferred_module="coach", source_cli="photo_v2.py")

    def test_photo_v3_main_delegates_to_unified_entry(self) -> None:
        with patch("photo.main") as mocked_main:
            photo_v3.main()
        mocked_main.assert_called_once_with(preferred_module="plan", source_cli="photo_v3.py")

    def test_photo_v4_main_delegates_to_unified_entry(self) -> None:
        with patch("photo.main") as mocked_main:
            photo_v4.main()
        mocked_main.assert_called_once_with(preferred_module="asset", source_cli="photo_v4.py")

    def test_entry_module_override_prefers_asset_for_media_requests(self) -> None:
        override = photo.resolve_entry_module_override(
            "asset",
            r"C:\Users\25320\Pictures\cat",
            {"paths": [], "prompt": ""},
        )
        self.assertEqual(override, "asset")

    def test_entry_module_override_prefers_post_for_promptless_media(self) -> None:
        override = photo.resolve_entry_module_override(
            "post",
            r"C:\Users\25320\Pictures\cat\CAT_1.jpg",
            {"paths": [], "prompt": ""},
        )
        self.assertEqual(override, "post")

    def test_entry_module_override_respects_explicit_prompt(self) -> None:
        override = photo.resolve_entry_module_override(
            "post",
            r"C:\Users\25320\Pictures\cat\CAT_1.jpg need coaching feedback",
            {"paths": [], "prompt": "need coaching feedback"},
        )
        self.assertEqual(override, "")

    def test_promptless_single_image_defaults_to_post(self) -> None:
        result = photo.resolve_promptless_media_default_module(
            {
                "paths": [Path(__file__)],
                "prompt": "",
            }
        )

        self.assertEqual(result, "post")

    def test_promptless_single_directory_defaults_to_asset(self) -> None:
        result = photo.resolve_promptless_media_default_module(
            {
                "paths": [Path(__file__).parent],
                "prompt": "",
            }
        )

        self.assertEqual(result, "asset")

    def test_promptless_defaults_do_not_override_explicit_prompt(self) -> None:
        result = photo.resolve_promptless_media_default_module(
            {
                "paths": [Path(__file__)],
                "prompt": "评估这张照片，并指导怎么拍更好",
            }
        )

        self.assertEqual(result, "")

    def test_rule_routing_covers_all_modules(self) -> None:
        cases = [
            ("help me export Lightroom preset and XMP parameters", "post"),
            ("explain ISO and help me improve", "coach"),
            (PLAN_PROMPT, "plan"),
            (ASSET_PROMPT, "asset"),
        ]

        for user_input, expected_module in cases:
            with self.subTest(module=expected_module):
                result = photo.resolve_route(
                    None,
                    user_input,
                    {},
                    [],
                    False,
                    "",
                )
                self.assertEqual(result["module"], expected_module)
                self.assertFalse(result["clarify"])

    def test_asset_handoff_selection_builds_post_media_request(self) -> None:
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

        result = photo.resolve_handoff_selection(
            "all :: keep warm gray night mood",
            "post",
            assets,
        )

        self.assertEqual(result["status"], "ok")
        self.assertEqual(len(result["selected_assets"]), 2)
        self.assertEqual(len(result["media_request"]["paths"]), 2)
        self.assertIn("keep warm gray night mood", result["media_request"]["prompt"])


if __name__ == "__main__":
    unittest.main()
