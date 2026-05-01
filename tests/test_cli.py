import unittest
from pathlib import Path

import photo
import photo_handoff
import photo_v1
import photo_v2
import photo_v3
import photo_v4
from photo_cli import CLIOutput
from photo_events import BufferEventSink
from photo_protocol import RESPONSE_DELIMITER


class CLIRenderingTests(unittest.TestCase):
    def test_unified_entry_banner_renders_to_sink(self) -> None:
        sink = BufferEventSink()

        photo.print_banner(CLIOutput(sink))

        self.assertIn("摄影全栈 Agent - 统一入口", sink.text)
        self.assertIn("后期辅助 / 学习教练 / 拍摄规划 / 素材管理", sink.text)

    def test_post_input_tips_render_to_sink(self) -> None:
        sink = BufferEventSink()

        photo_v1.print_input_format_tips(sink=sink)

        self.assertIn("输入格式提示", sink.text)
        self.assertIn("路径里有空格", sink.text)

    def test_post_input_tips_render_to_sink(self) -> None:
        sink = BufferEventSink()

        photo_v1.print_input_format_tips(sink=sink)

        self.assertIn("输入提示", sink.text)
        self.assertIn("只发一张图片路径：默认进入后期辅助", sink.text)
        self.assertIn("只发一个文件夹路径：默认进入素材管理并建立索引", sink.text)
        self.assertIn("想进入学习教练", sink.text)


class UserFacingTextTests(unittest.TestCase):
    def test_v2_instruction_uses_shared_response_delimiter(self) -> None:
        instruction = photo_v2.build_learning_instruction("请点评这张图")

        self.assertIn(RESPONSE_DELIMITER, instruction)
        self.assertNotIn("<<<COACH_JSON>>>", instruction)

    def test_v2_render_response_uses_clean_chinese_headings(self) -> None:
        payload = {
            "handoff_line": "",
            "summary": "主体判断是准确的，但前景控制还可以更克制。",
            "strengths": ["主体明确", "色调稳定"],
            "improvements": ["前景边缘有点乱", "层次还不够清晰"],
            "answer": "",
            "next_exercise": {
                "title": "雨夜层次练习",
                "scene": "夜景街头",
                "requirements": ["保留前景层次"],
                "acceptance": ["主体边缘干净"],
            },
            "skill_level": "进阶",
            "weak_points": ["边缘控制不稳定"],
            "reference_links": [],
            "visible_response": "",
        }

        text = photo_v2.render_coach_response(payload)

        self.assertIn("整体判断：", text)
        self.assertIn("做得好的地方：", text)
        self.assertIn("优先改进：", text)
        self.assertIn("下次练习：", text)

    def test_v3_planning_headers_are_clean(self) -> None:
        self.assertEqual(photo_v3.PLANNING_PROGRESS_MESSAGE, "⏳ AI 正在生成拍摄方案…")
        self.assertEqual(photo_v3.PLANNING_RESULT_HEADER, "拍摄规划结果：")

    def test_v3_render_planning_response_uses_clean_chinese_headers(self) -> None:
        text = photo_v3.render_planning_response(
            {
                "summary": "明天嘉兴适合拍水面与街区。",
                "provider_note": "地点数据来自高德 POI：嘉兴南湖旅游区（评分 4.8）；天气来自高德预报：2026-04-18 晴 12~22°C",
                "execution_timeline": ["07:00-09:00 -> 嘉兴南湖旅游区 -> 拍晨光倒影"],
                "plans": [],
                "selection_prompt": "",
                "visible_response": "",
            },
            {
                "brief": {"shoot_date": "2026-04-18"},
                "weather": {
                    "target_date": "2026-04-18",
                    "days": [
                        {
                            "date": "2026-04-18",
                            "condition": "晴",
                            "temp_min_c": "12",
                            "temp_max_c": "22",
                        }
                    ],
                },
                "places": {"results": []},
            },
        )

        self.assertIn("[数据说明]", text)
        self.assertIn("[天气参考] 2026-04-18 晴，12~22°C", text)
        self.assertIn("[执行表]", text)
        self.assertNotIn("鏁版嵁", text)
        self.assertNotIn("澶╂皵", text)
        self.assertNotIn("鎵ц", text)
        self.assertNotIn("掳C", text)

    def test_asset_subset_uses_grade_labels_numbering_and_score_sort(self) -> None:
        text = photo_v4.render_asset_subset(
            "佳片：",
            [
                {
                    "delivery_grade": "B",
                    "relative_path": "CAT_1.jpg",
                    "scene_id": "scene_001",
                    "quality_score": 72.27,
                },
                {
                    "delivery_grade": "B",
                    "relative_path": "CAT_19.jpg",
                    "scene_id": "scene_003",
                    "quality_score": 78.54,
                },
            ],
            "empty",
        )

        self.assertIn("1. [佳片] CAT_19.jpg", text)
        self.assertIn("2. [佳片] CAT_1.jpg", text)
        self.assertNotIn("[B]", text)

    def test_scene_preview_puts_grade_breakdown_on_new_line(self) -> None:
        index_text = photo_v4.render_index_response(
            {
                "project_root": r"C:\Users\25320\Pictures\cat",
                "project_name": "cat",
                "culling_preference": "balanced",
                "scene_groups": [
                    {
                        "scene_id": "scene_001",
                        "count": 3,
                        "time_range": "21:17 - 21:17",
                        "top_tags": ["夜间", "暖色", "竖图"],
                        "grade_counts": {"A": 0, "B": 3, "C": 0, "Reject": 0},
                    }
                ],
                "stats": {
                    "date_range": "2026-04-15 ~ 2026-04-15",
                    "total_assets": 3,
                    "scene_count": 1,
                    "grade_counts": {"A": 0, "B": 3, "C": 0, "Reject": 0},
                    "duplicate_count": 0,
                },
                "suggestions": {},
            },
            Path(r"C:\cache\cat.json"),
        )

        self.assertIn(
            "- scene_001：3 张，21:17 - 21:17，标签 夜间 / 暖色 / 竖图\n  分档：典藏 0 / 佳片 3 / 留存 0 / 清理 0",
            index_text,
        )

    def test_key_chinese_outputs_do_not_contain_mojibake_fragments(self) -> None:
        coach_text = photo_v2.render_coach_response(
            {
                "handoff_line": "",
                "summary": "整体方向是对的。",
                "strengths": ["主体明确"],
                "improvements": ["边缘还可以更干净"],
                "answer": "",
                "next_exercise": {},
                "skill_level": "进阶",
                "weak_points": [],
                "reference_links": [],
                "visible_response": "",
            }
        )
        handoff_text = photo_handoff.build_handoff_selection_response(
            "post",
            [
                {
                    "delivery_grade": "B",
                    "relative_path": "CAT_1.jpg",
                    "scene_id": "scene_001",
                    "quality_score": 77.46,
                }
            ],
            "这些典藏 / 佳片更适合继续流转到后期辅助做统一调色和参数建议。",
        )
        index_text = photo_v4.render_index_response(
            {
                "project_root": r"C:\Users\25320\Pictures\cat",
                "project_name": "cat",
                "culling_preference": "balanced",
                "scene_groups": [],
                "stats": {
                    "date_range": "2026-04-15 ~ 2026-04-15",
                    "total_assets": 3,
                    "scene_count": 1,
                    "grade_counts": {"A": 1, "B": 2, "C": 0, "Reject": 0},
                    "highlight_count": 2,
                    "reject_count": 0,
                    "duplicate_count": 0,
                    "cache_hit_count": 2,
                    "rebuilt_asset_count": 1,
                    "parallel_workers": 2,
                    "top_tags": ["夜间", "暖色", "竖图"],
                    "camera_top": ["未知设备"],
                },
                "suggestions": {
                    "project_name_suggestions": ["2026-04-15_cat"],
                    "folder_suggestion": "2026/2026-04-15_项目_摄影",
                    "naming_suggestion": "{date}_{scene}_{sequence}_{grade}",
                    "recommended_tags": ["夜间", "暖色", "竖图"],
                },
            },
            Path(r"C:\cache\cat.json"),
        )

        combined = "\n".join([coach_text, handoff_text, index_text])
        for fragment in ("鎽勫奖", "鍐疯壊", "妯″潡", "绱犳潗"):
            self.assertNotIn(fragment, combined)


if __name__ == "__main__":
    unittest.main()
