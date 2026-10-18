"""Offline checks of the local upstream adapter patch; no database or model calls."""
import sys
import io
import unittest
import uuid
import base64
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "integrations/ai-retouch-agent/backend"))
from app.agent import llm
from app.agent import graph
from app.providers.base import EditRequest, ProviderError
from app.providers.dashscope import DashScopeImageProvider
from app.providers import dashscope
from app.services import agent as agent_service
from app.models.tool_run import RunStatus


class PlannerFailureTests(unittest.IsolatedAsyncioTestCase):
    async def test_execution_check_does_not_plan_another_edit(self):
        with patch.object(graph, "_graph") as factory:
            reply, steps = await graph.run("是按照上述给出的曝光+0.25EV和阴影+25进行修改的吗？", "canvas")
        factory.assert_not_called()
        self.assertEqual(steps, [])
        self.assertIn("不再次修改", reply)

    async def test_actual_edit_instruction_still_reaches_planner(self):
        planner = SimpleNamespace(ainvoke=AsyncMock(return_value={"reply": "ok", "plan": []}))
        with patch.object(graph, "_graph", return_value=planner):
            await graph.run("请将亮度提高20%", "canvas")
        planner.ainvoke.assert_awaited_once()

    async def test_rollback_does_not_read_expired_record_and_saves_failure(self):
        class Record:
            expired = False
            def __getattribute__(self, name):
                if name in {"id", "user_id", "revision"} and self.expired:
                    raise AssertionError("ORM attribute read after rollback")
                return object.__getattribute__(self, name)
        record = Record()
        record.id, record.user_id, record.revision = uuid.uuid4(), uuid.uuid4(), 1
        expected_id, expected_user = record.id, record.user_id
        def expire():
            record.expired = True
        session = SimpleNamespace(rollback=AsyncMock(side_effect=expire), add=Mock(),
                                  commit=AsyncMock(), refresh=AsyncMock())
        failure = RuntimeError("private provider response must not be displayed")
        failure.body = {"error": {"code": "Arrearage"}}
        failure.status_code = 400
        with patch.object(agent_service, "describe", AsyncMock(return_value="canvas")), \
             patch.object(agent_service.agent, "run", AsyncMock(side_effect=failure)):
            turn = await agent_service.respond(session, record, "test")
        self.assertEqual((turn.session_id, turn.user_id), (expected_id, expected_user))
        self.assertEqual(turn.status, RunStatus.FAILED)
        self.assertEqual(turn.plan, [])
        self.assertIn("Arrearage", turn.error)
        self.assertNotIn("private", turn.error)
        session.commit.assert_awaited_once()

    async def test_unclassified_failure_also_survives_rollback(self):
        record = SimpleNamespace(id=uuid.uuid4(), user_id=uuid.uuid4(), revision=1)
        session = SimpleNamespace(rollback=AsyncMock(), add=Mock(), commit=AsyncMock(), refresh=AsyncMock())
        with patch.object(agent_service, "describe", AsyncMock(side_effect=ValueError("test"))), \
             patch.object(agent_service.logger, "exception"):
            turn = await agent_service.respond(session, record, "test")
        self.assertEqual(turn.status, RunStatus.FAILED)
        self.assertEqual(turn.plan, [])
        session.rollback.assert_awaited_once()

    def test_wrapped_provider_errors_and_timeout_are_safe(self):
        for status, fragment in [(401, "认证"), (403, "权限"), (429, "限流")]:
            inner = RuntimeError("secret")
            inner.status_code = status
            outer = RuntimeError("wrapper")
            outer.__cause__ = inner
            self.assertIn(fragment, llm.planner_failure_message(outer))
        self.assertIn("超时", llm.planner_failure_message(TimeoutError()))
        self.assertIsNone(llm.planner_failure_message(ValueError("secret")))


class LiveAdapterTests(unittest.TestCase):
    @staticmethod
    def image_bytes(image_format="PNG"):
        buffer = io.BytesIO()
        Image.new("RGB", (64, 48), (80, 90, 100)).save(buffer, image_format)
        return buffer.getvalue()

    def tearDown(self):
        llm.planner.cache_clear()

    def test_planner_has_bounded_timeout_and_no_automatic_retry(self):
        settings = SimpleNamespace(dashscope_api_key="sk-fake", planner_model="qwen-plus",
                                   dashscope_base_url="https://dashscope.aliyuncs.com/")
        factory = Mock()
        with patch.object(llm, "get_settings", return_value=settings), patch.object(llm, "ChatOpenAI", factory):
            llm.planner.cache_clear()
            llm.planner()
        options = factory.call_args.kwargs
        self.assertEqual(options["timeout"], 45)
        self.assertEqual(options["max_retries"], 0)
        self.assertEqual(options["base_url"], "https://dashscope.aliyuncs.com/compatible-mode/v1")

    def test_unsupported_negative_prompt_rejected_before_network(self):
        provider = object.__new__(DashScopeImageProvider)
        provider._edit_model = "qwen-image-2.1-pro"
        with self.assertRaises(ProviderError):
            provider._edit_payload(EditRequest(prompt="edit", image=b"test", negative_prompt="noise"))

    def test_supported_payload_keeps_single_output_and_native_size_syntax(self):
        provider = object.__new__(DashScopeImageProvider)
        provider._edit_model = "qwen-image-2.1-pro"
        payload = provider._edit_payload(EditRequest(prompt="edit", image=self.image_bytes(), width=768, height=1024))
        self.assertEqual(payload["model"], "qwen-image-2.1-pro")
        self.assertEqual(payload["parameters"]["n"], 1)
        self.assertEqual(payload["parameters"]["size"], "768*1024")
        self.assertNotIn("negative_prompt", payload["parameters"])

    def test_original_jpeg_is_not_mislabeled_as_png(self):
        provider = object.__new__(DashScopeImageProvider)
        provider._edit_model = "qwen-image-2.1-pro"
        payload = provider._edit_payload(EditRequest(prompt="edit", image=self.image_bytes("JPEG")))
        self.assertTrue(payload["input"]["messages"][0]["content"][0]["image"].startswith("data:image/jpeg;base64,"))

    def test_invalid_image_fails_before_submission(self):
        provider = object.__new__(DashScopeImageProvider)
        provider._edit_model = "qwen-image-2.1-pro"
        with self.assertRaises(ProviderError):
            provider._edit_payload(EditRequest(prompt="edit", image=b"invalid"))

    def test_oversized_opaque_image_gets_transport_copy_at_same_size(self):
        source = Image.effect_noise((256, 256), 90).convert("RGB")
        buffer = io.BytesIO()
        source.save(buffer, "PNG")
        original = buffer.getvalue()
        with patch.object(dashscope, "_MAX_INPUT_BYTES", 60000):
            uri = dashscope._inline_image(original)
        encoded = base64.b64decode(uri.split(",", 1)[1])
        self.assertTrue(uri.startswith("data:image/jpeg;"))
        self.assertLessEqual(len(encoded), 60000)
        self.assertEqual(original, buffer.getvalue())
        with Image.open(io.BytesIO(encoded)) as image:
            self.assertEqual(image.size, source.size)

    def test_oversized_transparent_image_preserves_alpha(self):
        source = Image.effect_noise((256, 256), 90).convert("RGBA")
        source.putalpha(128)
        buffer = io.BytesIO()
        source.save(buffer, "PNG")
        with patch.object(dashscope, "_MAX_INPUT_BYTES", 60000):
            uri = dashscope._inline_image(buffer.getvalue())
        self.assertTrue(uri.startswith("data:image/webp;"))
        with Image.open(io.BytesIO(base64.b64decode(uri.split(",", 1)[1]))) as image:
            self.assertEqual(image.size, source.size)
            self.assertEqual(image.convert("RGBA").getchannel("A").tobytes(), source.getchannel("A").tobytes())


if __name__ == "__main__":
    unittest.main()
