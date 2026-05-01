import io
import os
import unittest
from unittest.mock import patch

import photo_runtime


class RuntimeTests(unittest.TestCase):
    def test_ensure_required_env_exits_early_when_missing(self) -> None:
        buffer = io.StringIO()
        with patch.dict(os.environ, {}, clear=True):
            with patch("photo_runtime.load_local_env_files"):
                with patch("photo_runtime.read_windows_persistent_env", return_value=""):
                    with patch("sys.stdout", new=buffer):
                        with self.assertRaises(SystemExit) as raised:
                            photo_runtime.ensure_required_env(
                                ["ANTHROPIC_API_KEY"],
                                source_cli="photo.py",
                            )

        self.assertEqual(raised.exception.code, 1)
        output = buffer.getvalue()
        self.assertIn("ANTHROPIC_API_KEY", output)
        self.assertIn("photo.py", output)

    def test_resolve_env_value_falls_back_to_persistent_env(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            with patch("photo_runtime.load_local_env_files"):
                with patch("photo_runtime.read_windows_persistent_env", return_value="persistent-key"):
                    value = photo_runtime.resolve_env_value("ANTHROPIC_API_KEY")
                    self.assertEqual(os.environ["ANTHROPIC_API_KEY"], "persistent-key")

        self.assertEqual(value, "persistent-key")

    def test_ensure_anthropic_credentials_accepts_auth_token(self) -> None:
        with patch.dict(
            os.environ,
            {
                "ANTHROPIC_AUTH_TOKEN": "token-123",
                "ANTHROPIC_BASE_URL": "https://example.com/anthropic",
            },
            clear=True,
        ):
            with patch("photo_runtime.load_local_env_files"):
                settings = photo_runtime.ensure_anthropic_credentials(source_cli="photo.py")

        self.assertEqual(settings["auth_token"], "token-123")
        self.assertEqual(settings["base_url"], "https://example.com/anthropic")
        self.assertEqual(settings["active_auth_mode"], "auth_token")

    def test_create_anthropic_client_prefers_auth_token_mode(self) -> None:
        with patch.dict(
            os.environ,
            {
                "ANTHROPIC_API_KEY": "legacy-key",
                "ANTHROPIC_AUTH_TOKEN": "token-123",
                "ANTHROPIC_BASE_URL": "https://example.com/anthropic",
            },
            clear=True,
        ):
            with patch("photo_runtime.load_local_env_files"):
                with patch("photo_runtime.anthropic.Anthropic") as mocked_client:
                    photo_runtime.create_anthropic_client(source_cli="photo.py")

        mocked_client.assert_called_once_with(
            auth_token="token-123",
            base_url="https://example.com/anthropic",
        )


if __name__ == "__main__":
    unittest.main()
