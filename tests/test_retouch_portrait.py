"""Offline portrait guards. Mock providers only; no database or model requests."""
import io
import sys
import unittest
import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "integrations/ai-retouch-agent/backend"))
from app.edits.mask import apply_masked
from app.layers import Layer, LayerDocument, LayerKind
from app.models.tool_run import RunStatus
from app.services import agent
from app.tools import layers, region
from app.tools.context import ToolError


def png(image):
    buffer = io.BytesIO()
    image.save(buffer, "PNG")
    return buffer.getvalue()


def mask():
    image = Image.new("L", (32, 32), 0)
    for x in range(12, 20):
        for y in range(12, 20):
            image.putpixel((x, y), 255)
    return png(image)


def record():
    aid = uuid.uuid4()
    doc = LayerDocument(width=32, height=32, layers=[
        Layer(id="base", name="original", kind=LayerKind.IMAGE, width=32, height=32, asset_id=aid),
    ])
    return SimpleNamespace(id=uuid.uuid4(), user_id=uuid.uuid4(), revision=1,
                           original_asset_id=aid, current_asset_id=aid, document=doc.model_dump(mode="json"))


def session():
    return SimpleNamespace(add=Mock(), commit=AsyncMock(), refresh=AsyncMock(), rollback=AsyncMock())


class PortraitTests(unittest.IsolatedAsyncioTestCase):
    async def test_corner_and_auto_split_blocked_before_any_processing(self):
        for mode in ("corner", "auto"):
            with patch.object(layers, "get_settings", return_value=SimpleNamespace(matting_provider=mode)), \
                 patch.object(layers, "require_session", AsyncMock()) as read, \
                 patch.object(layers, "get_image_provider") as provider:
                with self.assertRaises(ToolError):
                    await layers.split_layers_exec(None, None)
                read.assert_not_awaited()
                provider.assert_not_called()

    def test_original_source_rejects_candidate_split_and_transformed_layers(self):
        for change in ("candidate", "split", "transform"):
            rec = record()
            doc = LayerDocument.model_validate(rec.document)
            if change == "candidate":
                doc.layers[0].asset_id = uuid.uuid4()
            elif change == "split":
                doc.layers[0].id = "subject"
            else:
                doc.layers[0].transform.scale_x = 1.2
            with self.assertRaises(ToolError):
                region.original_body_layer(rec, doc)

    def test_mask_must_be_local_nonempty_and_current_size(self):
        region.validate_body_mask(mask(), (32, 32))
        for bad in (None, png(Image.new("L", (32, 32), 0)),
                    png(Image.new("L", (32, 32), 255)), png(Image.new("L", (16, 16), 255))):
            with self.assertRaises(ToolError):
                region.validate_body_mask(bad, (32, 32))

    def test_strict_composite_preserves_all_unselected_pixels(self):
        original = Image.new("RGBA", (32, 32), (50, 70, 90, 255))
        edited = Image.new("RGBA", (32, 32), (200, 180, 160, 255))
        output = Image.open(io.BytesIO(apply_masked(png(original), png(edited), mask(), strict=True)))
        for x in range(32):
            for y in range(32):
                if not (12 <= x < 20 and 12 <= y < 20):
                    self.assertEqual(output.getpixel((x, y)), original.getpixel((x, y)))
        self.assertNotEqual(output.getpixel((16, 16)), original.getpixel((16, 16)))

    async def test_no_selection_saves_explanation_without_model_or_tool(self):
        with patch.object(agent, "selection_mask", AsyncMock(return_value=None)), \
             patch.object(agent.agent, "run", AsyncMock()) as planner, \
             patch.object(agent, "_advance", AsyncMock()) as submit:
            turn = await agent.respond(session(), record(), "让人物自然瘦一些，不要拆层")
        planner.assert_not_awaited()
        submit.assert_not_awaited()
        self.assertEqual(turn.status, RunStatus.FAILED)
        self.assertEqual(turn.plan, [])
        self.assertIn("笔刷", turn.error)

    async def test_selected_body_edit_waits_for_confirmation_without_planner(self):
        mid = str(uuid.uuid4())
        with patch.object(agent, "selection_mask", AsyncMock(return_value=mask())), \
             patch.object(agent.selections, "get", AsyncMock(return_value={"mask_asset_id": mid})), \
             patch.object(agent.agent, "run", AsyncMock()) as planner, \
             patch.object(agent, "_advance", AsyncMock()) as submit:
            turn = await agent.respond(session(), record(), "请轻微瘦腰")
        planner.assert_not_awaited()
        submit.assert_not_awaited()
        self.assertEqual(turn.status, RunStatus.QUEUED)
        self.assertEqual([step["tool"] for step in turn.plan], ["replace_region"])
        self.assertEqual(turn.plan[0]["status"], "waiting")
        self.assertEqual(turn.plan[0]["params"]["mask_asset_id"], mid)
        self.assertEqual(turn.plan[0]["params"]["revision"], 1)

    async def test_direct_tool_stale_selection_blocks_before_provider(self):
        rec = record()
        run = SimpleNamespace(params={"prompt": "slim figure", "layer_id": "base", "revision": 1,
                                      "mask_asset_id": str(uuid.uuid4())})
        with patch.object(region, "require_session", AsyncMock(return_value=rec)), \
             patch.object(region.selections, "get", AsyncMock(return_value={"mask_asset_id": "changed"})), \
             patch.object(region, "get_image_provider") as provider:
            with self.assertRaises(ToolError):
                await region.replace_region_exec(None, run)
        provider.assert_not_called()

    async def test_transparent_candidate_not_written_or_adopted(self):
        rec = record()
        mid = str(uuid.uuid4())
        run = SimpleNamespace(params={"prompt": "slim figure", "layer_id": "base", "revision": 1,
                                      "mask_asset_id": mid})
        provider = SimpleNamespace(edit=AsyncMock(return_value=[png(Image.new("RGBA", (32, 32), (0, 0, 0, 0)))]))
        with patch.object(region, "require_session", AsyncMock(return_value=rec)), \
             patch.object(region.selections, "get", AsyncMock(return_value={"mask_asset_id": mid})), \
             patch.object(region, "selection_mask", AsyncMock(return_value=mask())), \
             patch.object(region, "layer_image", AsyncMock(return_value=png(Image.new("RGB", (32, 32))))), \
             patch.object(region.runs, "report", AsyncMock()), \
             patch.object(region, "get_image_provider", return_value=provider), \
             patch.object(region, "write_layer_image", AsyncMock()) as write:
            with self.assertRaisesRegex(ToolError, "透明缺口"):
                await region.replace_region_exec(None, run)
        write.assert_not_awaited()

    def test_body_intent_and_read_only_check_are_distinct(self):
        self.assertTrue(region.is_body_edit("slim figure, natural proportions"))
        self.assertTrue(region.is_body_edit("让人物瘦一些"))
        self.assertFalse(region.is_body_edit("是否已经瘦身了吗？"))
        self.assertFalse(region.is_body_edit("亮度提高20%"))

    def test_explicit_pet_rounding_does_not_match_human_or_read_only_requests(self):
        for text in ("让猫变得圆润一些", "make the kitten chubby", "把小狗变胖一点"):
            self.assertTrue(region.is_pet_rounding_edit(text))
        for text in ("让人物瘦一些", "给猫旁边的人物瘦腰", "把猫旁边的手臂变圆润", "猫变圆润同时给女士瘦身", "不要让猫变圆润", "是否已经让猫变圆润了吗？", "把猫调亮"):
            self.assertFalse(region.is_pet_rounding_edit(text))

    async def test_pet_rounding_without_selection_waits_for_confirmation_not_brush(self):
        with patch.object(agent.selections, "get", AsyncMock(return_value=None)), \
             patch.object(agent, "selection_mask", AsyncMock()) as read_mask, \
             patch.object(agent.agent, "run", AsyncMock()) as planner, \
             patch.object(agent, "_advance", AsyncMock()) as submit:
            turn = await agent.respond(session(), record(), "让猫变得圆润一些，其他不变")
        planner.assert_not_awaited()
        read_mask.assert_not_awaited()
        submit.assert_not_awaited()
        self.assertIsNone(turn.error)
        self.assertEqual(turn.status, RunStatus.QUEUED)
        self.assertEqual([step["tool"] for step in turn.plan], ["replace_region"])
        self.assertEqual(turn.plan[0]["status"], "waiting")
        self.assertFalse(turn.plan[0]["params"].get("mask_asset_id"))
        self.assertFalse(region.is_body_edit(turn.plan[0]["params"]["prompt"]))
        self.assertIn("无需先用画笔", turn.reply)

    async def test_pet_rounding_respects_existing_selection_and_ambiguous_layers(self):
        mid = str(uuid.uuid4())
        with patch.object(agent.selections, "get", AsyncMock(return_value={"mask_asset_id": mid})), \
             patch.object(agent.agent, "run", AsyncMock()) as planner:
            turn = await agent.respond(session(), record(), "将猫变圆润")
        self.assertEqual(turn.plan[0]["params"]["mask_asset_id"], mid)
        self.assertIn("当前选区", turn.reply)
        rec = record()
        doc = LayerDocument.model_validate(rec.document)
        doc.layers.append(doc.layers[0].model_copy(update={"id": "other"}))
        rec.document = doc.model_dump(mode="json")
        with patch.object(agent.selections, "get", AsyncMock(return_value=None)), \
             patch.object(agent.agent, "run", AsyncMock()) as planner:
            turn = await agent.respond(session(), rec, "将猫变圆润")
        planner.assert_not_awaited()
        self.assertEqual(turn.plan, [])
        self.assertIn("图层", turn.reply)


if __name__ == "__main__":
    unittest.main()
