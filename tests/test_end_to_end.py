import shutil
import unittest
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from PIL import Image

import photo
from photo_events import BufferEventSink


def make_workspace_temp_dir() -> Path:
    base_dir = Path.cwd() / ".test_artifacts"
    base_dir.mkdir(exist_ok=True)
    temp_dir = base_dir / uuid4().hex
    temp_dir.mkdir()
    return temp_dir


class UnifiedEntryEndToEndTests(unittest.TestCase):
    def test_main_imports_project_and_renders_index_summary(self) -> None:
        temp_dir = make_workspace_temp_dir()
        try:
            data_dir = temp_dir / "data_home"
            image_path = temp_dir / "CAT_1.jpg"
            Image.new("RGB", (40, 40), color=(220, 180, 120)).save(image_path)
            sink = BufferEventSink()

            with patch.dict("os.environ", {"PHOTO_AGENT_DATA_DIR": str(data_dir)}, clear=False):
                with patch("photo.create_anthropic_client", return_value=object()):
                    with patch("photo.post_module.is_profile_initialized", return_value=True):
                        with patch("photo.post_module.load_skills_knowledge", return_value=""):
                            with patch("photo.plan_module.load_planning_skills_knowledge", return_value=""):
                                with patch("photo.trace_event"):
                                    with patch("builtins.input", side_effect=[str(temp_dir), "quit"]):
                                        photo.main(preferred_module="asset", source_cli="photo.py", sink=sink)

            self.assertIn("摄影全栈 Agent - 统一入口", sink.text)
            self.assertIn("⏳ 正在扫描项目并建立索引…", sink.text)
            self.assertIn("项目已完成索引", sink.text)
            self.assertIn("继续可以直接说：看典藏 / 看佳片 / 看留存 / 看清理 / 看重复片 / 把典藏或佳片送去后期辅助 / 把清理样片送去学习教练复盘", sink.text)
            self.assertNotIn("鎽勫奖", sink.text)
            self.assertNotIn("鍐疯壊", sink.text)
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_main_completes_asset_to_post_handoff_and_reuses_current_image_context(self) -> None:
        temp_dir = make_workspace_temp_dir()
        try:
            data_dir = temp_dir / "data_home"
            image_path = temp_dir / "CAT_1.jpg"
            Image.new("RGB", (48, 48), color=(180, 150, 110)).save(image_path)
            sink = BufferEventSink()

            def fake_prepare_handoff_assets(index: dict, destination: str) -> tuple[list[dict], str]:
                del destination
                asset = dict(index["assets"][0])
                asset["delivery_grade"] = "B"
                return [asset], "这些典藏 / 佳片更适合继续流转到后期辅助做统一调色和参数建议。"

            def fake_prepare_media_items(paths, sink=None):
                del sink
                return (
                    [
                        {
                            "type": "input_text",
                            "text": "mock image",
                            "label": "CAT_1.jpg",
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
                    sink.line("- 已生成统一调色建议")
                return (
                    f"后期辅助结果：\n- 已生成统一调色建议\n- 诉求：{request_prompt}",
                    {
                        "summary": "已生成统一调色建议",
                        "main_issues": [],
                        "xmp_params": {"Exposure2012": 0.2},
                    },
                )

            def fake_run_learning_coach_turn(
                client,
                system,
                messages,
                user_text,
                media_items=None,
                total_files=0,
                handoff_issues=None,
                sink=None,
            ):
                del client, system, messages, media_items, total_files, handoff_issues
                if sink is not None:
                    sink.line("学习教练结果：")
                    sink.line("- 已转入拍摄指导点评")
                return (
                    "学习教练结果：\n- 已转入拍摄指导点评",
                    {
                        "task_mode": "critique",
                        "handoff_line": "",
                        "summary": f"已接收：{user_text}",
                        "strengths": ["主体明确"],
                        "improvements": ["机位还可以更贴近主体"],
                        "answer": "",
                        "next_exercise": {},
                        "skill_level": "进阶",
                        "weak_points": ["取景稳定性"],
                        "reference_links": [],
                        "visible_response": "",
                    },
                )

            with patch.dict("os.environ", {"PHOTO_AGENT_DATA_DIR": str(data_dir)}, clear=False):
                with patch("photo.create_anthropic_client", return_value=object()):
                    with patch("photo.post_module.is_profile_initialized", return_value=True):
                        with patch("photo.post_module.load_skills_knowledge", return_value=""):
                            with patch("photo.plan_module.load_planning_skills_knowledge", return_value=""):
                                with patch("photo.trace_event"):
                                        with patch("photo.asset_module.prepare_handoff_assets", side_effect=fake_prepare_handoff_assets):
                                            with patch("photo.post_module.build_system_prompt", return_value="system"):
                                                with patch("photo.post_module.prepare_media_items", side_effect=fake_prepare_media_items):
                                                    with patch("photo.post_module.analyze_photo_streaming", side_effect=fake_analyze_photo_streaming):
                                                        with patch("photo.coach_module.run_learning_coach_turn", side_effect=fake_run_learning_coach_turn):
                                                            with patch(
                                                                "builtins.input",
                                                                side_effect=[
                                                                    str(temp_dir),
                                                                    "把佳片送去后期辅助",
                                                                    "all :: 保留暖灰夜景氛围",
                                                                    "评估这张照片，并且指导怎么拍更好",
                                                                    "quit",
                                                                ],
                                                            ):
                                                                photo.main(preferred_module="asset", source_cli="photo.py", sink=sink)

            self.assertIn("已准备进入后期辅助。告诉我你想继续处理哪几张：", sink.text)
            self.assertIn("[佳片]", sink.text)
            self.assertIn("[流转] 已选择 1 张：", sink.text)
            self.assertIn("后期辅助结果：", sink.text)
            self.assertIn("[预设] 当前结果 的 Lightroom 参数已准备好导出", sink.text)
            self.assertIn("[提示] 已沿用当前图片上下文：CAT_1.jpg。", sink.text)
            self.assertIn("学习教练结果：", sink.text)
            self.assertIn("- 已转入拍摄指导点评", sink.text)
            self.assertNotIn("你好像没有附上照片", sink.text)
            self.assertNotIn("检测到新的图片，正在为新任务重置后期分析上下文", sink.text)
            self.assertNotIn("鎽勫奖", sink.text)
            self.assertNotIn("鍐疯壊", sink.text)
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
