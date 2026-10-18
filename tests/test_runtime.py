import io
import os
import unittest
import httpx
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
                "PHOTO_MODEL_PROVIDER": "anthropic",
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
                "PHOTO_MODEL_PROVIDER": "anthropic",
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

    def test_deepseek_ignores_legacy_endpoint_model_and_auth(self) -> None:
        values = {
            "DEEPSEEK_API_KEY": "deepseek-test-key",
            "ANTHROPIC_AUTH_TOKEN": "old-token",
            "ANTHROPIC_BASE_URL": "https://old.example.com",
            "ANTHROPIC_MODEL": "claude-old",
        }
        with patch("photo_runtime.resolve_env_value", side_effect=lambda name: values.get(name, "")):
            settings = photo_runtime.resolve_anthropic_client_settings()
            self.assertEqual(settings["provider"], "deepseek")
            self.assertEqual(photo_runtime.resolve_model_name(), "deepseek-flash")
            self.assertEqual(settings["base_url"], "https://api.deepseek.com/anthropic")
            self.assertEqual(settings["auth_token"], "")
            with patch("photo_runtime.anthropic.Anthropic") as constructor:
                photo_runtime.create_anthropic_client(source_cli="test")
            constructor.assert_called_once_with(api_key="deepseek-test-key", auth_token="", base_url=settings["base_url"], default_headers={"Authorization": photo_runtime.anthropic.omit})

    def test_deepseek_request_does_not_send_stale_or_empty_bearer_header(self) -> None:
        values = {"DEEPSEEK_API_KEY": "test-key"}
        def respond(request):
            self.assertEqual(request.headers["x-api-key"], "test-key")
            self.assertNotIn("authorization", request.headers)
            return httpx.Response(200, json={
                "id": "msg_test", "type": "message", "role": "assistant", "model": "deepseek-flash",
                "content": [{"type": "text", "text": "OK"}], "stop_reason": "end_turn",
                "usage": {"input_tokens": 1, "output_tokens": 1},
            })
        with patch("photo_runtime.resolve_env_value", side_effect=lambda name: values.get(name, "")):
            with patch.dict(os.environ, {"ANTHROPIC_AUTH_TOKEN": "stale-system-token"}):
                with photo_runtime.create_anthropic_client(source_cli="test") as client:
                    with httpx.Client(transport=httpx.MockTransport(respond)) as transport:
                        response = client.with_options(http_client=transport).messages.create(
                            model="deepseek-flash", max_tokens=8, messages=[{"role": "user", "content": "Hi"}],
                        )
            self.assertEqual(response.content[0].text, "OK")

    def test_explicit_deepseek_never_falls_back_to_legacy_key(self) -> None:
        values = {"PHOTO_MODEL_PROVIDER": "deepseek", "ANTHROPIC_API_KEY": "old-key"}
        with patch("photo_runtime.resolve_env_value", side_effect=lambda name: values.get(name, "")):
            with patch("sys.stdout", new=io.StringIO()), self.assertRaises(SystemExit):
                photo_runtime.ensure_anthropic_credentials(source_cli="test")

    def test_deepseek_rejects_incompatible_or_untrusted_endpoints(self) -> None:
        for endpoint in ("https://dashscope.aliyuncs.com/compatible-mode/v1", "https://wrong.example/anthropic", "https\\://api.deepseek.com/anthropic"):
            values = {"DEEPSEEK_API_KEY": "test-key", "DEEPSEEK_BASE_URL": endpoint}
            with self.subTest(endpoint=endpoint):
                with patch("photo_runtime.resolve_env_value", side_effect=lambda name: values.get(name, "")):
                    with self.assertRaises(ValueError):
                        photo_runtime.resolve_anthropic_client_settings()

    def test_deepseek_model_override(self) -> None:
        values = {"DEEPSEEK_API_KEY": "test-key", "DEEPSEEK_MODEL": "deepseek-v4-pro"}
        with patch("photo_runtime.resolve_env_value", side_effect=lambda name: values.get(name, "")):
            self.assertEqual(photo_runtime.resolve_model_name(), "deepseek-v4-pro")


if __name__ == "__main__":
    unittest.main()
