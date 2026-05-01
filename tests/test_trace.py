import json
import shutil
import unittest
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

import photo_trace


def make_workspace_temp_dir() -> Path:
    base_dir = Path.cwd() / ".test_artifacts"
    base_dir.mkdir(exist_ok=True)
    temp_dir = base_dir / uuid4().hex
    temp_dir.mkdir()
    return temp_dir


class TraceTests(unittest.TestCase):
    def test_trace_event_writes_jsonl_record(self) -> None:
        temp_dir = make_workspace_temp_dir()
        try:
            with patch.dict(
                "os.environ",
                {"PHOTO_AGENT_TRACE_DIR": str(temp_dir), "PHOTO_AGENT_TRACE_ENABLED": "1"},
                clear=False,
            ):
                path = photo_trace.trace_event("router.selected_module", module="post", confidence=0.9)

            self.assertIsNotNone(path)
            lines = Path(path).read_text(encoding="utf-8").strip().splitlines()
            self.assertEqual(len(lines), 1)
            payload = json.loads(lines[0])
            self.assertEqual(payload["event"], "router.selected_module")
            self.assertEqual(payload["payload"]["module"], "post")
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_trace_event_records_truncated_user_input_summary(self) -> None:
        temp_dir = make_workspace_temp_dir()
        long_input = "用户输入" * 200
        try:
            with patch.dict(
                "os.environ",
                {"PHOTO_AGENT_TRACE_DIR": str(temp_dir), "PHOTO_AGENT_TRACE_ENABLED": "1"},
                clear=False,
            ):
                path = photo_trace.trace_event(
                    "router.input",
                    user_input=long_input,
                    ANTHROPIC_AUTH_TOKEN="secret",
                    media_data="base64 payload",
                )

            self.assertIsNotNone(path)
            line = Path(path).read_text(encoding="utf-8").strip()
            payload = json.loads(line)
            self.assertIn("user_input_summary", payload)
            self.assertLessEqual(len(payload["user_input_summary"]), 303)
            self.assertTrue(payload["user_input_summary"].endswith("..."))
            self.assertEqual(payload["payload"]["ANTHROPIC_AUTH_TOKEN"], "<redacted>")
            self.assertEqual(payload["payload"]["media_data"], "<redacted>")
            self.assertEqual(payload["payload"]["user_input"], payload["user_input_summary"])
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
