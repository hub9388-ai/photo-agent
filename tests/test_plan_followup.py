import unittest
from unittest.mock import patch

import photo
import photo_v1
import photo_v3
from photo_events import BufferEventSink


def build_pending_plan_state() -> dict:
    return {
        **photo_v3.DEFAULT_PLANNING_SESSION_STATE,
        "pending_selection_prompt": "你更想主攻哪个方向，或者想把两套连起来排个完整时间线？",
        "pending_plan_options": [
            {
                "id": "A",
                "title": "外滩观景台 · 蓝调转夜景",
                "location_name": "外滩",
                "time_window": "18:30-19:30",
            },
            {
                "id": "B",
                "title": "外滩南段 · 万国建筑群近景",
                "location_name": "外滩南段",
                "time_window": "19:00-21:00",
            },
        ],
        "last_city": "上海",
        "last_target_location": "外滩",
    }


class PlanningFollowupStateTests(unittest.TestCase):
    def test_should_resume_planning_followup_for_plan_choice(self) -> None:
        session_state = build_pending_plan_state()

        self.assertTrue(
            photo_v3.should_resume_planning_followup(
                "主攻方案 A：外滩观景台 · 蓝调转夜景",
                session_state,
                False,
            )
        )

    def test_should_not_resume_planning_followup_for_explicit_post_switch(self) -> None:
        session_state = build_pending_plan_state()

        self.assertFalse(
            photo_v3.should_resume_planning_followup(
                "给我后期建议，偏冷一点",
                session_state,
                False,
            )
        )


class UnifiedEntryPlanningFollowupTests(unittest.TestCase):
    def test_main_keeps_plan_followup_inside_planning_module(self) -> None:
        sink = BufferEventSink()
        captured_user_texts: list[str] = []

        first_payload = {
            "task_mode": "plan_generate",
            "summary": "今晚外滩适合拍蓝调转夜景。",
            "provider_note": "",
            "execution_timeline": ["18:30 -> 外滩观景台 -> 卡蓝调窗口"],
            "plans": [
                {
                    "id": "A",
                    "title": "外滩观景台 · 蓝调转夜景",
                    "location_name": "外滩",
                    "time_window": "18:30-19:30",
                    "style_handoff": "冷暖对比明显的城市夜景",
                },
                {
                    "id": "B",
                    "title": "外滩南段 · 万国建筑群近景",
                    "location_name": "外滩南段",
                    "time_window": "19:00-21:00",
                    "style_handoff": "偏复古的暖金色建筑夜景",
                },
            ],
            "selection_prompt": "你更想主攻哪个方向，或者想把两套连起来排个完整时间线？",
            "visible_response": "",
        }
        first_brief = {
            "user_intent_summary": "外滩夜景拍摄规划",
            "city": "上海",
            "target_location": "外滩",
            "shoot_date": "2026-04-18",
            "time_window": "晚上",
            "subject": "夜景",
            "style_keywords": ["城市夜景"],
        }

        second_payload = {
            "task_mode": "plan_followup",
            "summary": "已按方案 A 细化成蓝调到夜景的执行时间线。",
            "provider_note": "",
            "execution_timeline": [
                "18:30-18:45 -> 外滩观景台 -> 先找前景并固定机位",
                "18:45-19:30 -> 外滩观景台 -> 主攻蓝调窗口天际线",
            ],
            "plans": [
                {
                    "id": "A",
                    "title": "外滩观景台 · 蓝调转夜景（细化版）",
                    "location_name": "外滩",
                    "time_window": "18:30-20:00",
                    "style_handoff": "保留深蓝天空与暖色建筑反差",
                }
            ],
            "selection_prompt": "",
            "visible_response": "",
        }
        second_brief = {
            "user_intent_summary": "主攻方案 A，继续细化执行时间线",
            "city": "上海",
            "target_location": "外滩",
            "shoot_date": "2026-04-18",
            "time_window": "晚上",
            "subject": "夜景",
            "style_keywords": ["城市夜景"],
        }

        def fake_run_planning_turn(
            client,
            profile,
            session_state,
            skills_knowledge,
            messages,
            user_text,
            media_items=None,
            total_files=0,
            sink=None,
        ):
            del client, profile, session_state, skills_knowledge, messages, media_items, total_files
            captured_user_texts.append(user_text)
            if len(captured_user_texts) == 1:
                if sink is not None:
                    sink.line()
                    sink.line("拍摄规划结果：")
                    sink.line()
                    sink.line("今晚外滩适合拍蓝调转夜景。")
                    sink.line()
                    sink.line("你更想主攻哪个方向，或者想把两套连起来排个完整时间线？")
                return (
                    "今晚外滩适合拍蓝调转夜景。\n\n你更想主攻哪个方向，或者想把两套连起来排个完整时间线？",
                    first_payload,
                    first_brief,
                )

            if sink is not None:
                sink.line()
                sink.line("拍摄规划结果：")
                sink.line()
                sink.line("已按方案 A 细化成蓝调到夜景的执行时间线。")
            return (
                "已按方案 A 细化成蓝调到夜景的执行时间线。",
                second_payload,
                second_brief,
            )

        with patch("photo.create_anthropic_client", return_value=object()):
            with patch("photo.post_module.is_profile_initialized", return_value=True):
                with patch("photo.post_module.load_skills_knowledge", return_value=""):
                    with patch("photo.plan_module.load_planning_skills_knowledge", return_value=""):
                        with patch("photo.trace_event"):
                            with patch("photo.plan_module.run_planning_turn", side_effect=fake_run_planning_turn):
                                with patch(
                                    "builtins.input",
                                    side_effect=[
                                        "今晚想去外滩，帮我做拍摄规划，给我机位和拍摄清单",
                                        "主攻方案 A：外滩观景台 · 蓝调转夜景",
                                        "quit",
                                    ],
                                ):
                                    photo.main(preferred_module="plan", source_cli="photo.py", sink=sink)

        self.assertEqual(len(captured_user_texts), 2)
        self.assertIn("用户这轮回复：主攻方案 A：外滩观景台 · 蓝调转夜景", captured_user_texts[1])
        self.assertIn("已按上一轮拍摄规划继续细化方案", sink.text)
        self.assertIn("已按方案 A 细化成蓝调到夜景的执行时间线", sink.text)
        self.assertNotIn("Do you want post-processing advice", sink.text)

    def test_non_plan_switch_clears_pending_plan_followup(self) -> None:
        session_state = build_pending_plan_state()
        cleared = photo_v3.clear_pending_plan_followup(session_state)

        self.assertTrue(photo_v3.has_pending_plan_followup(session_state))
        self.assertFalse(photo_v3.has_pending_plan_followup(cleared))
        self.assertEqual(cleared["pending_selection_prompt"], "")
        self.assertEqual(cleared["pending_plan_options"], [])


if __name__ == "__main__":
    unittest.main()
