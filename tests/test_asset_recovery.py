import shutil
import unittest
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from PIL import Image

import photo
import photo_v4
from photo_events import BufferEventSink


def make_workspace_temp_dir() -> Path:
    base_dir = Path.cwd() / ".test_artifacts"
    base_dir.mkdir(exist_ok=True)
    temp_dir = base_dir / uuid4().hex
    temp_dir.mkdir()
    return temp_dir


class AssetRecoveryTests(unittest.TestCase):
    def test_asset_search_single_result_becomes_current_focus(self) -> None:
        temp_dir = make_workspace_temp_dir()
        try:
            image_path = temp_dir / "CAT_10.jpg"
            image_path.write_bytes(b"mock")

            state = photo_v4.update_asset_session_state(
                photo_v4.DEFAULT_ASSET_SESSION_STATE,
                search_results=[
                    {
                        "absolute_path": str(image_path),
                        "relative_path": "CAT_10.jpg",
                    }
                ],
            )

            request = photo.build_media_request_from_current_context(
                "对这张照片进行后期",
                "asset",
                photo.post_module.DEFAULT_SESSION_STATE,
                photo.coach_module.DEFAULT_COACH_SESSION_STATE,
                state,
            )

            self.assertIsNotNone(request)
            self.assertEqual(request["paths"], [image_path])
            self.assertEqual(request["prompt"], "对这张照片进行后期")
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_main_restores_handoff_selection_after_post_read_failure(self) -> None:
        temp_dir = make_workspace_temp_dir()
        try:
            data_dir = temp_dir / "data_home"
            seed_image = temp_dir / "CAT_1.jpg"
            Image.new("RGB", (40, 40), color=(120, 140, 180)).save(seed_image)
            sink = BufferEventSink()

            failing_asset = {
                "id": "asset_5",
                "absolute_path": str(temp_dir / "CAT_5.jpg"),
                "relative_path": "CAT_5.jpg",
                "delivery_grade": "B",
                "scene_id": "scene_002",
                "quality_score": 78.90,
            }
            fallback_asset = {
                "id": "asset_20",
                "absolute_path": str(temp_dir / "CAT_20.jpg"),
                "relative_path": "CAT_20.jpg",
                "delivery_grade": "B",
                "scene_id": "scene_003",
                "quality_score": 74.32,
            }

            def fake_prepare_handoff_assets(index: dict, destination: str) -> tuple[list[dict], str]:
                del index, destination
                return [failing_asset, fallback_asset], "这些典藏 / 佳片更适合继续流转到后期辅助做统一调色和参数建议。"

            def fake_prepare_media_items(paths, sink=None):
                del sink
                first_name = Path(paths[0]).name
                if first_name == "CAT_5.jpg":
                    raise ValueError(
                        "没有成功读取到可用于分析的样本。\n"
                        "- CAT_5.jpg: 图片太大了（30.0 MB），超过 20 MB 限制。"
                    )
                return (
                    [
                        {
                            "type": "input_text",
                            "text": "mock image",
                            "label": first_name,
                            "source_note": "本地文件",
                        }
                    ],
                    list(paths),
                    False,
                )

            def fake_analyze_photo_streaming(
                client,
                system,
                messages,
                prepared_items,
                request_prompt,
                total_files,
                is_batch,
                sink=None,
            ):
                del client, system, messages, prepared_items, total_files, is_batch
                if sink is not None:
                    sink.line("后期辅助结果：")
                    sink.line(f"- 已处理 {request_prompt}")
                return (
                    f"后期辅助结果：\n- 已处理 {request_prompt}",
                    {
                        "summary": "已完成后期分析",
                        "main_issues": [],
                        "xmp_params": {"Exposure2012": 0.1},
                    },
                )

            with patch.dict("os.environ", {"PHOTO_AGENT_DATA_DIR": str(data_dir)}, clear=False):
                with patch("photo.create_anthropic_client", return_value=object()):
                    with patch("photo.post_module.is_profile_initialized", return_value=True):
                        with patch("photo.post_module.load_skills_knowledge", return_value=""):
                            with patch("photo.plan_module.load_planning_skills_knowledge", return_value=""):
                                with patch("photo.trace_event"):
                                    with patch("photo.asset_module.prepare_handoff_assets", side_effect=fake_prepare_handoff_assets):
                                        with patch(
                                            "photo.resolve_route",
                                            return_value={
                                                "module": "asset",
                                                "confidence": 0.9,
                                                "reason": "prepare_handoff",
                                                "clarify": False,
                                                "question": "",
                                            },
                                        ):
                                            with patch(
                                                "photo.asset_module.resolve_asset_intent",
                                                return_value={
                                                    "task_mode": "prepare_handoff",
                                                    "destination": "post",
                                                    "needs_project_path": False,
                                                    "clarification_question": "",
                                                    "culling_preference": "",
                                                    "search_query": "",
                                                },
                                            ):
                                                with patch("photo.post_module.build_system_prompt", return_value="system"):
                                                    with patch("photo.post_module.prepare_media_items", side_effect=fake_prepare_media_items):
                                                        with patch("photo.post_module.analyze_photo_streaming", side_effect=fake_analyze_photo_streaming):
                                                            with patch(
                                                                "builtins.input",
                                                                side_effect=[
                                                                    str(temp_dir),
                                                                    "把佳片送去后期辅助",
                                                                    "1",
                                                                    "2",
                                                                    "quit",
                                                                ],
                                                            ):
                                                                photo.main(preferred_module="asset", source_cli="photo.py", sink=sink)

            self.assertGreaterEqual(sink.text.count("已准备进入后期辅助。告诉我你想继续处理哪几张："), 2)
            self.assertIn("刚才选中的素材暂时无法读入", sink.text)
            self.assertIn("CAT_5.jpg: 图片太大了", sink.text)
            self.assertIn("[流转] 已选择 1 张：CAT_20.jpg。接下来进入后期辅助。", sink.text)
            self.assertIn("后期辅助结果：", sink.text)
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_main_reuses_single_search_result_for_asset_followup_post(self) -> None:
        temp_dir = make_workspace_temp_dir()
        try:
            data_dir = temp_dir / "data_home"
            image_path = temp_dir / "CAT_10.jpg"
            Image.new("RGB", (48, 48), color=(170, 140, 120)).save(image_path)
            sink = BufferEventSink()

            def fake_resolve_route(client, user_input, profile, task_history, has_media, active_module):
                del client, profile, task_history, has_media, active_module
                if user_input == "10":
                    return {
                        "module": "asset",
                        "confidence": 0.9,
                        "reason": "search_assets",
                        "clarify": False,
                        "question": "",
                    }
                return {
                    "module": "post",
                    "confidence": 0.9,
                    "reason": "post_followup",
                    "clarify": False,
                    "question": "",
                }

            def fake_prepare_media_items(paths, sink=None):
                del sink
                return (
                    [
                        {
                            "type": "input_text",
                            "text": "mock image",
                            "label": Path(paths[0]).name,
                            "source_note": "本地文件",
                        }
                    ],
                    list(paths),
                    False,
                )

            def fake_analyze_photo_streaming(
                client,
                system,
                messages,
                prepared_items,
                request_prompt,
                total_files,
                is_batch,
                sink=None,
            ):
                del client, system, messages, prepared_items, total_files, is_batch
                if sink is not None:
                    sink.line("后期辅助结果：")
                    sink.line("- 已复用素材管理中的当前图片")
                return (
                    f"后期辅助结果：\n- 已复用素材管理中的当前图片\n- 诉求：{request_prompt}",
                    {
                        "summary": "已复用素材管理中的当前图片",
                        "main_issues": [],
                        "xmp_params": {},
                    },
                )

            search_result = [
                {
                    "id": "asset_10",
                    "absolute_path": str(image_path),
                    "relative_path": "CAT_10.jpg",
                    "project_name": "cat",
                    "delivery_grade": "B",
                    "capture_at": "2026-04-16 19:30:00",
                    "time_of_day": "傍晚",
                    "tags": ["傍晚", "横图"],
                }
            ]

            with patch.dict("os.environ", {"PHOTO_AGENT_DATA_DIR": str(data_dir)}, clear=False):
                with patch("photo.create_anthropic_client", return_value=object()):
                    with patch("photo.post_module.is_profile_initialized", return_value=True):
                        with patch("photo.post_module.load_skills_knowledge", return_value=""):
                            with patch("photo.plan_module.load_planning_skills_knowledge", return_value=""):
                                with patch("photo.trace_event"):
                                    with patch("photo.resolve_route", side_effect=fake_resolve_route):
                                        with patch("photo.asset_module.parse_search_filters", return_value={"limit": 30}):
                                            with patch("photo.asset_module.search_index_records", return_value=search_result):
                                                with patch("photo.post_module.build_system_prompt", return_value="system"):
                                                    with patch("photo.post_module.prepare_media_items", side_effect=fake_prepare_media_items):
                                                        with patch("photo.post_module.analyze_photo_streaming", side_effect=fake_analyze_photo_streaming):
                                                            with patch(
                                                                "builtins.input",
                                                                side_effect=[
                                                                    str(temp_dir),
                                                                    "10",
                                                                    "对这张照片进行后期",
                                                                    "quit",
                                                                ],
                                                            ):
                                                                photo.main(preferred_module="asset", source_cli="photo.py", sink=sink)

            self.assertIn("搜索结果：10", sink.text)
            self.assertIn("[提示] 已沿用当前图片上下文：CAT_10.jpg。", sink.text)
            self.assertIn("后期辅助结果：", sink.text)
            self.assertNotIn("你好像没有附上照片", sink.text)
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
