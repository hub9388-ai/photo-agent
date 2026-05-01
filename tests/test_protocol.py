import json
import unittest

import photo_v1
import photo_v2
import photo_v3
from photo_protocol import RESPONSE_DELIMITER, split_response_sections


class ProtocolTests(unittest.TestCase):
    def test_split_response_sections_with_delimiter(self) -> None:
        raw_text = (
            "Visible response for the user\n"
            f"{RESPONSE_DELIMITER}\n"
            '{"summary": "ok", "task_mode": "single_photo"}'
        )

        visible_text, payload_text, has_structured_tail = split_response_sections(
            raw_text,
            anchor_keys=("summary", "task_mode"),
        )

        self.assertTrue(has_structured_tail)
        self.assertEqual(visible_text, "Visible response for the user")
        self.assertEqual(json.loads(payload_text)["task_mode"], "single_photo")

    def test_split_response_sections_with_json_anchor(self) -> None:
        raw_text = 'Natural language summary\n{"task_mode": "coaching_chat", "summary": "keep going"}'

        visible_text, payload_text, has_structured_tail = split_response_sections(
            raw_text,
            anchor_keys=("task_mode", "summary"),
        )

        self.assertTrue(has_structured_tail)
        self.assertEqual(visible_text, "Natural language summary")
        self.assertEqual(json.loads(payload_text)["task_mode"], "coaching_chat")

    def test_split_response_sections_without_structured_tail(self) -> None:
        raw_text = "Only a visible response with no structured tail"

        visible_text, payload_text, has_structured_tail = split_response_sections(
            raw_text,
            anchor_keys=("summary", "task_mode"),
        )

        self.assertFalse(has_structured_tail)
        self.assertEqual(visible_text, "")
        self.assertEqual(payload_text, raw_text)

    def test_v1_analysis_payload_parses_tail(self) -> None:
        payload_text = json.dumps(
            {
                "summary": "Overall direction is correct, but highlights are too hard.",
                "main_issues": ["Highlights are bright", "Shadows are heavy"],
                "adjustments": ["- Lower highlights", "- Lift shadows slightly"],
                "closing_line": "This will feel more natural.",
                "task_mode": "single_photo",
                "xmp_params": {"Highlights2012": -30},
                "source_note": "RAW preview",
                "batch_note": "",
            },
            ensure_ascii=False,
        )

        payload = photo_v1.parse_analysis_payload(payload_text)

        self.assertEqual(payload["task_mode"], "single_photo")
        self.assertEqual(
            payload["summary"],
            "Overall direction is correct, but highlights are too hard.",
        )
        self.assertEqual(payload["xmp_params"]["Highlights2012"], -30)

    def test_v2_split_and_parse_half_stream_payload(self) -> None:
        payload_dict = {
            "task_mode": "critique",
            "handoff_line": "I will pick up this sample first.",
            "summary": "Good base. Next step is practicing selection.",
            "strengths": ["Clear subject", "Stable color"],
            "improvements": ["Background edges are messy", "Foreground guidance is weak"],
            "next_exercise": {
                "title": "Rainy street layered composition",
                "scene": "night street",
                "requirements": ["Keep foreground layers", "Control subject edges"],
                "acceptance": ["Subject edge is clean", "Background is not cluttered"],
            },
            "skill_level": "intermediate",
            "weak_points": ["Edge control is unstable"],
            "answer": "",
            "reference_query": "",
            "visible_response": "",
        }
        raw_text = (
            "The subject already works. Next, focus on edge control.\n"
            f"{RESPONSE_DELIMITER}\n"
            f"{json.dumps(payload_dict, ensure_ascii=False)}"
        )

        visible_text, payload_text, has_structured_tail = split_response_sections(
            raw_text,
            anchor_keys=("task_mode", "summary"),
        )
        payload = photo_v2.parse_coach_payload(payload_text)

        self.assertTrue(has_structured_tail)
        self.assertIn("subject already works", visible_text)
        self.assertEqual(payload["task_mode"], "critique")
        self.assertEqual(payload["skill_level"], "进阶")
        self.assertEqual(payload["next_exercise"]["title"], "Rainy street layered composition")

    def test_v3_planning_payload_parses_tail(self) -> None:
        payload_text = json.dumps(
            {
                "task_mode": "plan_generate",
                "summary": "Morning at Broken Bridge, evening at Lakeside.",
                "provider_note": "",
                "execution_timeline": ["07:30-09:30 Broken Bridge: shoot reflections"],
                "plans": [
                    {
                        "id": "A",
                        "title": "Broken Bridge mist",
                        "fit_reason": "Lower crowds and stable reflections.",
                        "location_candidate_rank": 1,
                        "location_name": "Broken Bridge",
                        "location_address": "Beishan Street, Hangzhou",
                        "time_window": "07:30-09:30",
                        "light_notes": ["Soft light"],
                        "weather_notes": ["Watch for slippery ground"],
                        "composition_notes": ["Center the bridge arch"],
                        "lighting_setup": ["Natural light"],
                        "shot_list": {
                            "opening": ["Entry wide shot"],
                            "must_have": ["Bridge reflection"],
                            "bonus": ["Willow foreground"],
                        },
                        "starter_settings": ["70mm / f5.6 / 1/250s / ISO 200"],
                        "gear_checklist": ["Body", "Telephoto"],
                        "departure_checklist": ["Non-slip shoes"],
                        "risks": ["Crowds increase quickly"],
                        "fallback_plan": "Switch to tighter frames when crowded.",
                        "style_handoff": "Low saturation, preserve mist.",
                    }
                ],
                "selection_prompt": "Do you want the hour-by-hour execution table for plan A?",
                "visible_response": "",
            },
            ensure_ascii=False,
        )

        payload = photo_v3.parse_planning_payload(payload_text)

        self.assertEqual(payload["task_mode"], "plan_generate")
        self.assertEqual(payload["plans"][0]["location_name"], "Broken Bridge")
        self.assertEqual(
            payload["execution_timeline"][0],
            "07:30-09:30 Broken Bridge: shoot reflections",
        )

    def test_v3_truncated_payload_salvages_first_complete_plan(self) -> None:
        raw_text = """{
  "task_mode": "plan_generate",
  "summary": "Morning at Broken Bridge, afternoon at Lakeside.",
  "execution_timeline": ["07:30-09:30 Broken Bridge: shoot bridge reflections"],
  "plans": [
    {
      "id": "A",
      "title": "Broken Bridge mist",
      "fit_reason": "Lower crowds and stable reflections.",
      "location_candidate_rank": 1,
      "location_name": "Broken Bridge",
      "location_address": "Beishan Street, Hangzhou",
      "time_window": "07:30-09:30",
      "light_notes": ["Soft light"],
      "weather_notes": ["Watch for slippery ground"],
      "composition_notes": ["Center the bridge arch"],
      "lighting_setup": ["Natural light"],
      "shot_list": {
        "opening": ["Entry wide shot"],
        "must_have": ["Bridge reflection"],
        "bonus": ["Willow foreground"]
      },
      "starter_settings": ["70mm / f5.6 / 1/250s / ISO 200"],
      "gear_checklist": ["Body", "Telephoto"],
      "departure_checklist": ["Non-slip shoes"],
      "risks": ["Crowds increase quickly"],
      "fallback_plan": "Switch to tighter frames when crowded.",
      "style_handoff": "Low saturation, preserve mist."
    },
    {
      "id": "B",
      "title": "Lakeside evening"
"""

        payload = photo_v3.parse_planning_payload(raw_text)

        self.assertGreaterEqual(len(payload["plans"]), 1)
        self.assertEqual(payload["plans"][0]["location_name"], "Broken Bridge")
        self.assertEqual(payload["plans"][0]["id"], "A")

    def test_v3_extract_planning_brief_falls_back_to_user_text_when_model_returns_non_json(self) -> None:
        class FakeTextBlock:
            type = "text"
            text = "我建议你优先确认城市和拍摄时间，再决定候选地点。"

        class FakeResponse:
            content = [FakeTextBlock()]

        class FakeMessages:
            @staticmethod
            def create(**kwargs):
                del kwargs
                return FakeResponse()

        class FakeClient:
            messages = FakeMessages()

        brief = photo_v3.extract_planning_brief(
            FakeClient(),
            {},
            {},
            "明天想去嘉兴，有无推荐的风景与拍摄方式？",
        )

        tomorrow = photo_v3.datetime.now().date().fromordinal(photo_v3.datetime.now().date().toordinal() + 1).isoformat()
        self.assertEqual(brief["city"], "嘉兴")
        self.assertEqual(brief["shoot_date"], tomorrow)
        self.assertEqual(brief["subject"], "风光")
        self.assertFalse(brief["needs_clarification"])
        self.assertTrue(brief["place_search_queries"])


if __name__ == "__main__":
    unittest.main()
