from pathlib import Path
from unittest.mock import patch
import unittest

import photo_v1
import photo_v2


def build_payload(**overrides):
    payload = {
        "task_mode": "exercise_plan",
        "handoff_line": "",
        "summary": "",
        "strengths": [],
        "improvements": [],
        "next_exercise": {
            "title": "",
            "scene": "",
            "requirements": [],
            "acceptance": [],
        },
        "skill_level": "",
        "weak_points": [],
        "answer": "",
        "reference_query": "",
        "reference_links": [],
        "lesson_status_update": "",
        "lesson_target_title": "",
        "lesson_review_note": "",
        "visible_response": "",
    }
    payload.update(overrides)
    return payload


class CoachLifecycleTests(unittest.TestCase):
    @patch("photo_v2.save_profile", return_value=True)
    def test_lesson_history_moves_from_assigned_to_completed(self, _mocked_save_profile) -> None:
        profile = dict(photo_v1.DEFAULT_PROFILE)

        assign_payload = build_payload(
            summary="Start with a focused practice.",
            next_exercise={
                "title": "Rainy street layered composition",
                "scene": "night street",
                "requirements": ["Keep foreground layers"],
                "acceptance": ["Subject edge is clean"],
            },
        )
        profile = photo_v2.update_profile_from_coach_payload(
            profile,
            assign_payload,
            user_text="Give me a weekly exercise",
            media_request=None,
        )

        self.assertEqual(profile["lesson_history"][0]["status"], "assigned")
        lesson_title = profile["lesson_history"][0]["title"]

        in_progress_payload = build_payload(
            lesson_target_title=lesson_title,
            lesson_status_update="in_progress",
        )
        profile = photo_v2.update_profile_from_coach_payload(
            profile,
            in_progress_payload,
            user_text="I will start practicing this tonight",
            media_request=None,
        )

        self.assertEqual(profile["lesson_history"][0]["status"], "in_progress")
        self.assertTrue(profile["lesson_history"][0]["started_at"])

        completed_payload = build_payload(
            task_mode="critique",
            summary="This submission already meets the acceptance target.",
            lesson_target_title=lesson_title,
            lesson_status_update="completed",
            lesson_review_note="Foreground layers and edges are both stable now.",
        )
        media_request = {"paths": [Path("CAT_1.jpg")], "prompt": "review my assignment"}
        profile = photo_v2.update_profile_from_coach_payload(
            profile,
            completed_payload,
            user_text="This is my assignment submission",
            media_request=media_request,
        )

        active_lesson = profile["lesson_history"][0]
        self.assertEqual(active_lesson["status"], "completed")
        self.assertEqual(active_lesson["latest_submission_count"], 1)
        self.assertTrue(active_lesson["submitted_at"])
        self.assertTrue(active_lesson["reviewed_at"])
        self.assertTrue(active_lesson["completed_at"])


if __name__ == "__main__":
    unittest.main()

