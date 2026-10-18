"""Credential isolation checks; these tests never call a model or network."""
import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

MODULE = Path(__file__).resolve().parents[1] / "scripts/check_qwen_image.py"
spec = importlib.util.spec_from_file_location("qwen_image_config", MODULE)
qwen = importlib.util.module_from_spec(spec)
spec.loader.exec_module(qwen)


class QwenConfigurationTests(unittest.TestCase):
    def test_repeated_legacy_variables_do_not_select_relay_or_deepseek_key(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "model.env").write_text(
                "ANTHROPIC_AUTH_TOKEN=sk-alibaba\n"
                "ANTHROPIC_BASE_URL=https\\://dashscope.aliyuncs.com/compatible-mode/v1\n"
                "ANTHROPIC_AUTH_TOKEN=sk-relay\n"
                "ANTHROPIC_BASE_URL=https://relay.example\n"
                "ANTHROPIC_BASE_URL=https://api.deepseek.com/anthropic\n"
                "DEEPSEEK_API_KEY=sk-deepseek\n", encoding="utf-8")
            with patch.object(qwen, "ROOT", root):
                key, origin, metadata = qwen.resolve()
            self.assertEqual(key, "sk-alibaba")
            self.assertEqual(origin, "https://dashscope.aliyuncs.com")
            self.assertNotIn(key, str(metadata))

    def test_rejects_untrusted_destination_before_sending_credentials(self):
        for url in ("http://dashscope.aliyuncs.com", "https://dashscope.aliyuncs.com.evil.example",
                    "https://user:password@dashscope.aliyuncs.com", "https://relay.example"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                qwen.official_origin(url)

    def test_refuses_ambiguous_explicit_keys(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "model.env").write_text("DASHSCOPE_API_KEY=sk-one\nQWEN_API_KEY=sk-two\n")
            with patch.object(qwen, "ROOT", root), self.assertRaises(ValueError):
                qwen.resolve()

    def test_configure_does_not_activate_generation_or_change_database(self):
        with tempfile.TemporaryDirectory() as directory:
            private = Path(directory) / "private.env"
            private.write_text("IMAGE_PROVIDER=mock\nDATABASE_URL=original\nDASHSCOPE_API_KEY=\n")
            with patch.object(qwen, "PRIVATE", private):
                qwen.configure("sk-test", "https://dashscope.aliyuncs.com")
            config = dict((name, value) for _, name, value in qwen.records(private))
            self.assertEqual(config["IMAGE_PROVIDER"], "mock")
            self.assertEqual(config["DATABASE_URL"], "original")
            self.assertEqual(config["IMAGE_EDIT_MODEL"], "qwen-image-2.1-pro")


if __name__ == "__main__":
    unittest.main()
