import io
import json
import unittest
import urllib.error
from unittest import mock

from ai_gitgen import providers
from ai_gitgen.errors import AIRequestError, UnsupportedParameterError
from ai_gitgen.records import GenerationSettings

CLAUDE_OK = {
    "content": [{"type": "text", "text": "feat: 제목\n\n- 본문"}, {"type": "thinking", "thinking": ""}],
    "stop_reason": "end_turn",
    "usage": {"input_tokens": 120, "output_tokens": 30},
}
OPENAI_OK = {
    "choices": [{"message": {"content": "feat: 제목"}, "finish_reason": "length"}],
    "usage": {"prompt_tokens": 90, "completion_tokens": 10},
}
GEMINI_OK = {
    "candidates": [
        {
            "content": {"role": "model", "parts": [{"text": "생각...", "thought": True}, {"text": "feat: 제목\n\n- 본문"}]},
            "finishReason": "STOP",
        }
    ],
    "usageMetadata": {"promptTokenCount": 70, "candidatesTokenCount": 12, "thoughtsTokenCount": 8, "totalTokenCount": 90},
}


def settings(provider: str = "claude", temperature: float | None = 0.3, model: str = "m") -> GenerationSettings:
    return GenerationSettings(provider=provider, model=model, temperature=temperature, max_tokens=256)


class ClaudeProviderTest(unittest.TestCase):
    provider = providers.ClaudeProvider()

    def test_prepare_builds_headers_and_body(self) -> None:
        request = self.provider.prepare("SYS", "USER", settings(), "key123")
        self.assertEqual(request.url, providers.ClaudeProvider.url)
        self.assertEqual(request.headers["x-api-key"], "key123")
        self.assertEqual(request.headers["anthropic-version"], "2023-06-01")
        self.assertEqual(request.body["system"], "SYS")
        self.assertEqual(request.body["messages"], [{"role": "user", "content": "USER"}])
        self.assertEqual(request.body["temperature"], 0.3)
        self.assertEqual(request.body["max_tokens"], 256)

    def test_prepare_omits_temperature_when_none(self) -> None:
        request = self.provider.prepare("S", "U", settings(temperature=None), "k")
        self.assertNotIn("temperature", request.body)

    def test_base_url_override_changes_endpoint(self) -> None:
        with mock.patch.dict("os.environ", {"AI_API_BASE_URL": "http://127.0.0.1:9999/"}):
            request = self.provider.prepare("S", "U", settings(), "k")
            openai_request = providers.OpenAIProvider().prepare("S", "U", settings("openai"), "k")
        self.assertEqual(request.url, "http://127.0.0.1:9999/v1/messages")
        self.assertEqual(openai_request.url, "http://127.0.0.1:9999/v1/chat/completions")

    def test_ai_api_url_takes_precedence_over_legacy_name(self) -> None:
        env = {"AI_API_URL": "https://proxy.example.com", "AI_API_BASE_URL": "https://other.example.com"}
        with mock.patch.dict("os.environ", env):
            self.assertEqual(self.provider.prepare("S", "U", settings(), "k").url, "https://proxy.example.com/v1/messages")

    def test_plain_http_base_url_to_remote_host_is_rejected(self) -> None:
        from ai_gitgen.errors import AiGitgenError

        with mock.patch.dict("os.environ", {"AI_API_BASE_URL": "http://proxy.example.com"}):
            with self.assertRaises(AiGitgenError):
                self.provider.prepare("S", "U", settings(), "k")
        with mock.patch.dict("os.environ", {"AI_API_BASE_URL": "https://proxy.example.com/"}):
            self.assertEqual(self.provider.prepare("S", "U", settings(), "k").url, "https://proxy.example.com/v1/messages")

    def test_parse_joins_text_blocks_only(self) -> None:
        result = self.provider.parse(CLAUDE_OK)
        self.assertEqual(result.text, "feat: 제목\n\n- 본문")
        self.assertEqual((result.input_tokens, result.output_tokens, result.stop_reason), (120, 30, "end_turn"))

    def test_translate_temperature_400(self) -> None:
        payload = {"error": {"type": "invalid_request_error", "message": "temperature is not supported"}}
        exc = self.provider.translate_error(400, payload, "claude-opus-5-5")
        self.assertIsInstance(exc, UnsupportedParameterError)
        self.assertEqual(exc.model, "claude-opus-5-5")

    def test_translate_other_errors_include_status_and_hint(self) -> None:
        exc = self.provider.translate_error(401, {"error": {"message": "invalid x-api-key"}}, "m")
        self.assertIn("인증 실패 (HTTP 401): invalid x-api-key", str(exc))
        self.assertIn("AI_API_KEY", str(exc))
        self.assertIn("요청 한도 초과 (HTTP 429)", str(self.provider.translate_error(429, {}, "m")))
        self.assertIn("서버 오류 (HTTP 529)", str(self.provider.translate_error(529, {}, "m")))


class OpenAIProviderTest(unittest.TestCase):
    provider = providers.OpenAIProvider()

    def test_prepare_uses_bearer_and_system_message(self) -> None:
        request = self.provider.prepare("SYS", "USER", settings("openai"), "key")
        self.assertEqual(request.headers["authorization"], "Bearer key")
        self.assertEqual(request.body["messages"][0], {"role": "system", "content": "SYS"})
        self.assertEqual(request.body["max_tokens"], 256)  # gpt-4.1-mini 와 호환 프록시가 알아듣는 필드
        self.assertNotIn("max_completion_tokens", request.body)

    def test_reasoning_models_use_max_completion_tokens(self) -> None:
        for model in ("gpt-5-mini", "o3", "O4-mini", "gpt-5.5", "openai/gpt-5"):
            request = self.provider.prepare("SYS", "USER", settings("openai", model=model), "key")
            self.assertEqual(request.body["max_completion_tokens"], 256, model)
            self.assertNotIn("max_tokens", request.body, model)
        for model in ("gpt-4.1-mini", "gpt-4o", "claude-sonnet-4", "o-ring-model"):
            request = self.provider.prepare("SYS", "USER", settings("openai", model=model), "key")
            self.assertEqual(request.body["max_tokens"], 256, model)

    def test_parse_maps_finish_reason(self) -> None:
        result = self.provider.parse(OPENAI_OK)
        self.assertEqual(result.text, "feat: 제목")
        self.assertEqual(result.stop_reason, "max_tokens")
        self.assertEqual((result.input_tokens, result.output_tokens), (90, 10))

    def test_translate_temperature_by_param(self) -> None:
        payload = {"error": {"message": "Unsupported value", "param": "temperature", "code": "unsupported_value"}}
        self.assertIsInstance(self.provider.translate_error(400, payload, "gpt-5"), UnsupportedParameterError)

    def test_translate_quota_429_has_no_retry_hint(self) -> None:
        payload = {"error": {"message": "quota", "type": "insufficient_quota", "code": "insufficient_quota"}}
        text = str(self.provider.translate_error(429, payload, "m"))
        self.assertIn("크레딧이 소진", text)
        self.assertNotIn("잠시 후", text)

    def test_translate_rate_limit_429_suggests_retry(self) -> None:
        payload = {"error": {"message": "slow", "type": "rate_limit_error", "code": "slow_down"}}
        self.assertIn("잠시 후", str(self.provider.translate_error(429, payload, "m")))


def _http_error(status: int, body: bytes) -> urllib.error.HTTPError:
    return urllib.error.HTTPError("https://x", status, "msg", {}, io.BytesIO(body))


class _FakeResponse(io.BytesIO):
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


OPEN = "ai_gitgen.providers._OPENER.open"


class SendRequestTest(unittest.TestCase):
    request = providers.PreparedRequest("https://x", {"content-type": "application/json"}, {"a": 1})

    def test_success_returns_status_and_json(self) -> None:
        with mock.patch(OPEN, return_value=_FakeResponse(json.dumps(CLAUDE_OK).encode())):
            status, payload = providers.send_request(self.request, 5.0)
        self.assertEqual((status, payload["stop_reason"]), (200, "end_turn"))

    def test_http_error_returns_status_and_body(self) -> None:
        body = json.dumps({"error": {"message": "bad key"}}).encode()
        with mock.patch(OPEN, side_effect=_http_error(401, body)):
            status, payload = providers.send_request(self.request, 5.0)
        self.assertEqual((status, payload["error"]["message"]), (401, "bad key"))

    def test_non_json_error_body_is_wrapped(self) -> None:
        with mock.patch(OPEN, side_effect=_http_error(502, b"<html>Bad Gateway</html>")):
            status, payload = providers.send_request(self.request, 5.0)
        self.assertEqual(status, 502)
        self.assertIn("Bad Gateway", payload["error"]["message"])

    def test_network_failure_raises_ai_request_error(self) -> None:
        with mock.patch(OPEN, side_effect=urllib.error.URLError("dns fail")):
            with self.assertRaises(AIRequestError) as ctx:
                providers.send_request(self.request, 5.0)
        self.assertIn("네트워크 오류", str(ctx.exception))

    def test_timeout_raises_ai_request_error(self) -> None:
        with mock.patch(OPEN, side_effect=TimeoutError()):
            with self.assertRaises(AIRequestError) as ctx:
                providers.send_request(self.request, 7.0)
        self.assertIn("7초", str(ctx.exception))

    def test_connection_reset_and_http_exception_are_reported(self) -> None:
        import http.client

        for raised in (ConnectionResetError("reset"), http.client.RemoteDisconnected("closed")):
            with mock.patch(OPEN, side_effect=raised):
                with self.assertRaises(AIRequestError) as ctx:
                    providers.send_request(self.request, 5.0)
            self.assertIn("네트워크 오류", str(ctx.exception))

    def test_redirects_are_not_followed(self) -> None:
        self.assertIsNone(providers._NoRedirectHandler().redirect_request(None, None, 302, "", {}, "https://evil"))
        client = providers.AIClient(providers.ClaudeProvider(), "k")
        with mock.patch("ai_gitgen.providers.send_request", return_value=(302, {})):
            with self.assertRaises(AIRequestError) as ctx:
                client.generate("S", "U", settings())
        self.assertIn("리디렉션", str(ctx.exception))


class RobustnessTest(unittest.TestCase):
    def test_string_error_payload_does_not_crash(self) -> None:
        exc = providers.ClaudeProvider().translate_error(500, {"error": "boom"}, "m")
        self.assertIn("boom", str(exc))

    def test_malformed_success_payload_yields_empty_result(self) -> None:
        claude = providers.ClaudeProvider().parse({"content": "oops", "usage": [], "stop_reason": None})
        openai = providers.OpenAIProvider().parse({"choices": "oops", "usage": {"prompt_tokens": "x"}})
        self.assertEqual((claude.text, claude.input_tokens, claude.stop_reason), ("", 0, ""))
        self.assertEqual((openai.text, openai.input_tokens), ("", 0))

    def test_temperature_rejection_requires_rejection_phrase(self) -> None:
        self.assertTrue(providers.is_temperature_rejection("temperature is not supported"))
        self.assertTrue(providers.is_temperature_rejection("anything", param="temperature"))
        self.assertFalse(providers.is_temperature_rejection("temperature must be between 0 and 1"))
        exc = providers.ClaudeProvider().translate_error(400, {"error": {"message": "temperature: 3 is out of range"}}, "m")
        self.assertNotIsInstance(exc, UnsupportedParameterError)


class AIClientTest(unittest.TestCase):
    def test_generate_counts_calls_and_parses(self) -> None:
        client = providers.AIClient(providers.ClaudeProvider(), "k")
        with mock.patch("ai_gitgen.providers.send_request", return_value=(200, CLAUDE_OK)):
            result = client.generate("S", "U", settings())
        self.assertEqual(client.call_count, 1)
        self.assertEqual(result.output_tokens, 30)

    def test_generate_raises_translated_error_and_still_counts(self) -> None:
        client = providers.AIClient(providers.ClaudeProvider(), "k")
        with mock.patch("ai_gitgen.providers.send_request", return_value=(401, {"error": {"message": "x"}})):
            with self.assertRaises(AIRequestError):
                client.generate("S", "U", settings())
        self.assertEqual(client.call_count, 1)

    def test_unknown_provider_is_rejected(self) -> None:
        with self.assertRaises(AIRequestError):
            providers.get_provider("mistral")
        self.assertIsInstance(providers.get_provider("gemini"), providers.GeminiProvider)


if __name__ == "__main__":
    unittest.main()


class GeminiProviderTest(unittest.TestCase):
    provider = providers.GeminiProvider()

    def test_prepare_uses_header_key_and_generate_content_body(self) -> None:
        request = self.provider.prepare("SYS", "USER", settings("gemini", model="gemini-3.8-flash"), "key123")
        self.assertEqual(request.url, "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.8-flash:generateContent")
        self.assertNotIn("key123", request.url)  # 키는 쿼리 문자열이 아니라 헤더로
        self.assertEqual(request.headers["x-goog-api-key"], "key123")
        self.assertEqual(request.body["systemInstruction"], {"parts": [{"text": "SYS"}]})
        self.assertEqual(request.body["contents"], [{"role": "user", "parts": [{"text": "USER"}]}])
        self.assertEqual(
            request.body["generationConfig"],
            {"maxOutputTokens": 256, "temperature": 0.3, "thinkingConfig": {"thinkingLevel": "low"}},
        )

    def test_temperature_omitted_and_legacy_models_get_no_thinking_level(self) -> None:
        for model in ("gemini-2.5-flash", "gemma-3-27b-it", "learnlm-2.0", "custom-proxy-model"):
            request = self.provider.prepare("S", "U", settings("gemini", temperature=None, model=model), "k")
            self.assertEqual(request.body["generationConfig"], {"maxOutputTokens": 256}, model)
        for model in ("gemini-3.5-flash-lite", "google/gemini-4-argon", "GEMINI-3.8-FLASH", "models/gemini-3-flash-preview"):
            request = self.provider.prepare("S", "U", settings("gemini", model=model), "k")
            self.assertIn("thinkingConfig", request.body["generationConfig"], model)

    def test_endpoint_path_strips_models_prefix_and_encodes_the_rest(self) -> None:
        self.assertEqual(self.provider.endpoint_path("models/gemini-3.8-flash"), "/v1beta/models/gemini-3.8-flash:generateContent")
        self.assertEqual(self.provider.endpoint_path("vendor/gemini-x"), "/v1beta/models/vendor%2Fgemini-x:generateContent")
        encoded = self.provider.endpoint_path("../x?key=1#frag")
        self.assertNotIn("?", encoded)
        self.assertNotIn("#", encoded)
        self.assertNotIn("/x", encoded.replace("/v1beta/models/", ""))

    def test_prepared_request_repr_hides_key(self) -> None:
        request = self.provider.prepare("S", "U", settings("gemini", model="gemini-3.8-flash"), "sk-secret")
        self.assertNotIn("sk-secret", repr(request))
        self.assertNotIn("sk-secret", str(request))

    def test_proxy_base_url_keeps_generate_content_path(self) -> None:
        with mock.patch.dict("os.environ", {"AI_API_URL": "https://proxy.example.com/"}):
            request = self.provider.prepare("S", "U", settings("gemini", model="gemini-3.8-flash"), "k")
        self.assertEqual(request.url, "https://proxy.example.com/v1beta/models/gemini-3.8-flash:generateContent")

    def test_parse_skips_thought_parts_and_counts_thought_tokens(self) -> None:
        result = self.provider.parse(GEMINI_OK)
        self.assertEqual(result.text, "feat: 제목\n\n- 본문")
        self.assertEqual(result.stop_reason, "end_turn")
        self.assertEqual((result.input_tokens, result.output_tokens), (70, 20))

    def test_parse_maps_finish_reasons_and_blocked_prompt(self) -> None:
        for reason, expected in (("MAX_TOKENS", "max_tokens"), ("SAFETY", "refusal"), ("RECITATION", "refusal"), ("OTHER", "other")):
            payload = {"candidates": [{"content": {"parts": [{"text": "x"}]}, "finishReason": reason}]}
            self.assertEqual(self.provider.parse(payload).stop_reason, expected, reason)
        blocked = {"promptFeedback": {"blockReason": "PROHIBITED_CONTENT"}, "usageMetadata": {"promptTokenCount": 5}}
        result = self.provider.parse(blocked)
        self.assertEqual((result.text, result.stop_reason, result.input_tokens), ("", "refusal", 5))
        not_blocked = {"promptFeedback": {"blockReason": "X"}, "candidates": [{"content": {"parts": [{"text": "ok"}]}, "finishReason": "STOP"}]}
        self.assertEqual(self.provider.parse(not_blocked).stop_reason, "end_turn")
        self.assertEqual(self.provider.parse({}).text, "")

    def test_parse_survives_malformed_payloads(self) -> None:
        payloads = (
            {"candidates": None},
            {"candidates": "oops"},
            {"candidates": ["str"]},
            {"candidates": [{"content": ["list"]}]},
            {"candidates": [{"content": {"parts": "str"}}]},
            {"candidates": [{"content": {"parts": [{"text": None}, {"text": 7}, "x"]}}], "usageMetadata": []},
        )
        for payload in payloads:
            result = self.provider.parse(payload)
            self.assertEqual((result.text, result.output_tokens), ("", 0), payload)

    def test_thought_only_max_tokens_reply_is_empty_text(self) -> None:
        payload = {
            "candidates": [{"content": {"parts": [{"text": "생각", "thought": True}]}, "finishReason": "MAX_TOKENS"}],
            "usageMetadata": {"promptTokenCount": 50, "candidatesTokenCount": 0, "thoughtsTokenCount": 256},
        }
        result = self.provider.parse(payload)
        self.assertEqual((result.text, result.stop_reason, result.output_tokens), ("", "max_tokens", 256))

    def test_translate_errors_include_status_name_and_hints(self) -> None:
        bad_key = {"error": {"code": 400, "message": "API key not valid. Please pass a valid API key.", "status": "INVALID_ARGUMENT"}}
        text = str(self.provider.translate_error(400, bad_key, "gemini-3.8-flash"))
        self.assertIn("[INVALID_ARGUMENT]", text)
        self.assertIn("GEMINI_API_KEY", text)
        quota = {"error": {"code": 429, "message": "Quota exceeded", "status": "RESOURCE_EXHAUSTED"}}
        self.assertIn("할당량", str(self.provider.translate_error(429, quota, "m")))
        temp = {"error": {"code": 400, "message": "temperature is not supported for this model", "status": "INVALID_ARGUMENT"}}
        self.assertIsInstance(self.provider.translate_error(400, temp, "m"), UnsupportedParameterError)
        not_found = {"error": {"code": 404, "message": "models/x is not found", "status": "NOT_FOUND"}}
        self.assertIn("--model", str(self.provider.translate_error(404, not_found, "x")))
        no_status = {"error": {"message": "plain"}}
        self.assertIn("plain", str(self.provider.translate_error(500, no_status, "x")))
        self.assertNotIn("[]", str(self.provider.translate_error(500, no_status, "x")))

    def test_list_wrapped_error_body_is_unwrapped(self) -> None:
        raw = json.dumps([{"error": {"code": 400, "message": "bad", "status": "INVALID_ARGUMENT"}}]).encode()
        self.assertEqual(providers._read_json(raw)["error"]["message"], "bad")
        self.assertEqual(providers._read_json(b"[1, 2]"), {})
