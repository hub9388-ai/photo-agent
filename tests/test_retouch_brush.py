"""Selection pixel semantics and portrait alpha boundaries; no model/network calls."""
import io
import sys
import unittest
from pathlib import Path

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "integrations/ai-retouch-agent/backend"))
from app.edits.mask import apply_masked, rasterize_strokes
from app.schemas.session import SelectIn
from app.tools.context import ToolError
from app.tools.region import validate_body_candidate


def png(image):
    out = io.BytesIO()
    image.save(out, "PNG")
    return out.getvalue()


class BrushTests(unittest.TestCase):
    def test_paint_does_not_fill_unpainted_triangle(self):
        points = [[(.2,.2),(.8,.2),(.8,.8)]]
        paint = rasterize_strokes((100,100), points, radius=.04, shape="paint")
        lasso = rasterize_strokes((100,100), points, radius=.04, shape="lasso")
        self.assertEqual(paint.getpixel((65,35)), 0)
        self.assertEqual(lasso.getpixel((65,35)), 255)
        self.assertEqual(paint.getpixel((50,20)), 255)

    def test_subtract_removes_only_brush_and_keeps_base_immutable(self):
        base = Image.new("L", (100,100), 255)
        mask = rasterize_strokes(base.size, [[(.5,.2),(.5,.8)]], radius=.08,
                                 base=base, shape="paint", operation="subtract")
        self.assertEqual(mask.getpixel((50,50)), 0)
        self.assertEqual(mask.getpixel((20,50)), 255)
        self.assertEqual(base.getpixel((50,50)), 255)

    def test_single_click_width_and_empty_eraser(self):
        small = rasterize_strokes((100,100), [[(.5,.5)]], radius=.02, shape="paint")
        large = rasterize_strokes((100,100), [[(.5,.5)]], radius=.12, shape="paint")
        self.assertEqual(small.getpixel((54,50)), 0)
        self.assertEqual(large.getpixel((54,50)), 255)
        self.assertIsNone(rasterize_strokes((100,100), [[(.5,.5)]], radius=.1, operation="subtract").getbbox())

    def test_protocol_defaults_and_invalid_controls(self):
        self.assertEqual(SelectIn(revision=1).shape, "lasso")  # older clients keep their semantics
        for params in [{"shape":"guess"}, {"operation":"delete-photo"}, {"radius":.001}]:
            with self.assertRaises(ValueError):
                SelectIn(revision=1, **params)

    def test_transparency_outside_selection_is_discarded(self):
        mask = Image.new("L", (40,40), 0)
        ImageDraw.Draw(mask).rectangle((12,12,26,26), fill=255)
        edited = Image.new("RGBA", (40,40), (220,180,160,0))
        edited.putalpha(mask)
        validate_body_candidate(png(edited), png(mask), mask.size)
        original = Image.new("RGBA", mask.size, (40,60,80,255))
        result = Image.open(io.BytesIO(apply_masked(png(original), png(edited), png(mask), strict=True)))
        for y in range(40):
            for x in range(40):
                self.assertEqual(result.getpixel((x,y))[3], 255)
                if not mask.getpixel((x,y)):
                    self.assertEqual(result.getpixel((x,y)), original.getpixel((x,y)))
        edited.putpixel((20,20),(220,180,160,0))
        with self.assertRaisesRegex(ToolError, "选区内.*透明缺口"):
            validate_body_candidate(png(edited), png(mask), mask.size)

    def test_resized_candidate_hole_in_selected_region_is_rejected(self):
        mask = Image.new("L", (40,40), 0)
        ImageDraw.Draw(mask).rectangle((10,10,30,30), fill=255)
        with self.assertRaises(ToolError):
            validate_body_candidate(png(Image.new("RGBA", (20,20), (1,2,3,0))), png(mask), mask.size)
