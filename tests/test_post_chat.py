import unittest

import anthropic
import httpx
from unittest.mock import patch

import photo_v1
from photo_events import BufferEventSink


def build_bad_request_error(message: str) -> anthropic.BadRequestError:
    request = httpx.Request("POST", "https://example.com/v1/messages")
    response = httpx.Response(400, request=request)
    return anthropic.BadRequestError(message, response=response, body={})


def build_rate_limit_error(message: str = "rate limited") -> anthropic.RateLimitError:
    request = httpx.Request("POST", "https://example.com/v1/messages")
    response = httpx.Response(429, request=request)
    return anthropic.RateLimitError(message, response=response, body={})


class FakeStream:
    def __init__(self, chunks: list[str]) -> None:
        self.text_stream = chunks

    def __enter__(self) -> "FakeStream":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        del exc_type, exc, tb
        return False


class FallbackMessagesAPI:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def stream(self, **kwargs):
        self.calls.append(kwargs)
        if len(self.calls) == 1:
            raise build_bad_request_error(
                "thinking requires budget_tokens and max_tokens to be configured correctly"
            )
        return FakeStream(["你好", "，世界"])


class AlwaysBadMessagesAPI:
    def __init__(self, message: str) -> None:
        self.calls: list[dict] = []
        self.message = message

    def stream(self, **kwargs):
        self.calls.append(kwargs)
        raise build_bad_request_error(self.message)


class RateLimitedStreamMessagesAPI:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def stream(self, **kwargs):
        self.calls.append(kwargs)
        if len(self.calls) == 1:
            raise build_rate_limit_error()
        return FakeStream(["retry ", "ok"])


class FakeClient:
    def __init__(self, messages_api) -> None:
        self.messages = messages_api


class ChatStreamingFallbackTests(unittest.TestCase):
    def test_chat_streaming_retries_without_thinking_on_budget_error(self) -> None:
        messages_api = FallbackMessagesAPI()
        client = FakeClient(messages_api)
        sink = BufferEventSink()

        response_text = photo_v1.chat_streaming(
            client,
            "system prompt",
            [],
            "帮我继续讲讲这组照片的后期思路",
            sink=sink,
        )

        self.assertEqual(response_text, "你好，世界")
        self.assertEqual(len(messages_api.calls), 2)
        self.assertEqual(messages_api.calls[0]["max_tokens"], photo_v1.MAX_TOKENS_CHAT_THINKING)
        self.assertEqual(messages_api.calls[1]["max_tokens"], photo_v1.MAX_TOKENS_CHAT)
        self.assertIn("thinking", messages_api.calls[0])
        self.assertNotIn("thinking", messages_api.calls[1])
        self.assertIn("已自动切换为标准回复模式", sink.text)

    def test_chat_streaming_preserves_non_thinking_bad_request(self) -> None:
        messages_api = AlwaysBadMessagesAPI("maximum context length exceeded")
        client = FakeClient(messages_api)

        with self.assertRaises(anthropic.BadRequestError):
            photo_v1.chat_streaming(
                client,
                "system prompt",
                [],
                "继续",
                sink=BufferEventSink(),
            )

        self.assertEqual(len(messages_api.calls), 1)

    def test_chat_streaming_retries_rate_limit_once(self) -> None:
        messages_api = RateLimitedStreamMessagesAPI()
        client = FakeClient(messages_api)
        sink = BufferEventSink()

        with patch("photo_v1.time.sleep", return_value=None) as sleep:
            response_text = photo_v1.chat_streaming(
                client,
                "system prompt",
                [],
                "继续",
                sink=sink,
            )

        self.assertEqual(response_text, "retry ok")
        self.assertEqual(len(messages_api.calls), 2)
        sleep.assert_called_once_with(photo_v1.RATE_LIMIT_RETRY_DELAYS[0])
        self.assertIn("请求被限流", sink.text)


if __name__ == "__main__":
    unittest.main()
