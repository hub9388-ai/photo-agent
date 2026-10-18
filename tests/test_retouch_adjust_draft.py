"""No network: provenance must not reach Pillow; stale applies must fail before pixels."""
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "integrations/ai-retouch-agent/backend"))
from app.tools import retouch
from app.tools.context import ToolError


class AdjustDraftTests(unittest.IsolatedAsyncioTestCase):
    async def test_stale_revision_rejected_before_read_or_write(self):
        run = SimpleNamespace(params={"expected_revision": 1, "shadows": -.1})
        with patch.object(retouch, "require_session", AsyncMock(return_value=SimpleNamespace(revision=2))), \
             patch.object(retouch, "layer_image", AsyncMock()) as read:
            with self.assertRaises(ToolError):
                await retouch.adjust_image_exec(None, run)
            read.assert_not_awaited()

    async def test_provenance_is_audit_only_and_exact_user_values_reach_pixels(self):
        params = {"expected_revision": 1, "advice_context": '{"source_job_id":"job_test"}', "layer_id": "base",
                  "shadows": -.08, "contrast": .06, "brightness": 0}
        run = SimpleNamespace(params=params.copy())
        with patch.object(retouch, "require_session", AsyncMock(return_value=SimpleNamespace(revision=1))), \
             patch.object(retouch, "document_of", return_value=None), \
             patch.object(retouch, "resolve_target", return_value=SimpleNamespace(id="base")), \
             patch.object(retouch.runs, "report", AsyncMock()), \
             patch.object(retouch, "layer_image", AsyncMock(return_value=b"source")), \
             patch.object(retouch, "adjust", return_value=b"output") as pixels, \
             patch.object(retouch, "write_layer_image", AsyncMock(return_value={"ok": True})):
            await retouch.adjust_image_exec(None, run)
        pixels.assert_called_once_with(b"source", shadows=-.08, contrast=.06)
        self.assertEqual(run.params, params)

    def test_audit_fields_hidden_from_planner_and_bounded(self):
        self.assertIn("advice_context", retouch.ADJUST_IMAGE.agent_hidden)
        with self.assertRaises(ValueError):
            retouch.AdjustIn(advice_context="x" * 16001)
