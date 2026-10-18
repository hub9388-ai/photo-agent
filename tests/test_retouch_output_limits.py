"""Real >20 MiB lossless output, no network or model. Upload limit remains unchanged."""
import io
import random
import sys
import unittest
import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "integrations/ai-retouch-agent/backend"))
from app.models.asset import AssetKind, AssetSource
from app.services import assets, images
from app.services import tools as tool_service, agent as agent_service
from app.models.tool_run import RunStatus


class OutputLimitTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        cls.size = (3072, 2048)
        image = Image.frombytes("RGBA", cls.size, random.Random(17).randbytes(cls.size[0] * cls.size[1] * 4))
        stream = io.BytesIO()
        image.save(stream, "PNG", compress_level=0)
        cls.data = stream.getvalue()
        assert len(cls.data) > images.MAX_FILE_BYTES

    def test_upload_still_rejects_over_20_mib(self):
        with self.assertRaisesRegex(images.ImageRejected, "20 MB"):
            images.probe(self.data)

    async def test_oversize_upload_never_reaches_storage(self):
        with patch.object(assets.storage, "put", AsyncMock()) as put:
            with self.assertRaises(images.ImageRejected):
                await assets.create_from_bytes(None, uuid.uuid4(), self.data, AssetKind.ORIGINAL, AssetSource.UPLOAD)
            put.assert_not_awaited()

    async def test_internal_lossless_result_keeps_size_bytes_and_alpha(self):
        session = SimpleNamespace(add=Mock(), commit=AsyncMock())
        for source in (AssetSource.TOOL, AssetSource.GENERATE):
            with patch.object(assets.storage, "put", AsyncMock()) as put:
                asset = await assets.create_from_bytes(session, uuid.uuid4(), self.data, AssetKind.GENERATED, source)
            self.assertEqual((asset.width, asset.height), self.size)
            self.assertEqual(asset.image_format, "PNG")
            self.assertTrue(asset.has_alpha)
            self.assertEqual(asset.size_bytes, len(self.data))
            self.assertEqual(put.call_args.args[1], self.data)

    def test_internal_limit_and_pixel_guard_still_apply(self):
        with self.assertRaises(images.ImageRejected):
            images.probe(self.data, max_bytes=len(self.data) - 1)
        with patch.object(images, "MAX_PIXELS", 100):
            with self.assertRaisesRegex(images.ImageRejected, "像素"):
                images.probe(self.data, max_bytes=images.MAX_DERIVED_FILE_BYTES)

    async def test_rejected_result_reports_specific_error(self):
        session = SimpleNamespace(rollback=AsyncMock())
        run = SimpleNamespace(tool="adjust_image")
        spec = SimpleNamespace(handler=AsyncMock(side_effect=images.ImageRejected("文件超过 256 MB 上限")))
        with patch.object(tool_service, "spec_of", return_value=spec), \
             patch.object(tool_service.runs, "start", AsyncMock()), \
             patch.object(tool_service.runs, "finish", AsyncMock()) as finish, \
             patch.object(agent_service, "continue_plan", AsyncMock()):
            await tool_service.execute(session, run)
        finish.assert_awaited_once_with(session, run, status=RunStatus.FAILED, error="文件超过 256 MB 上限")
