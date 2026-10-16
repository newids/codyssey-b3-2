"""AI API 제공자별 요청 조립, 응답 파싱, 오류 번역. HTTP 전송은 표준 라이브러리 urllib."""

from __future__ import annotations

import http.client
import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Protocol

TEMPERATURE_REJECTION_HINTS = ("support", "allow", "deprecat", "remov", "invalid", "unexpected", "unknown", "not ")

from . import config
from .errors import AIRequestError, UnsupportedParameterError
from .records import GenerationResult, GenerationSettings


@dataclass(frozen=True)
class PreparedRequest:
    url: str
    headers: dict[str, str] = field(repr=False)  # API 키가 들어 있으므로 디버그 출력에 찍히지 않게
    body: dict[str, object] = field(repr=False)


class Provider(Protocol):
    name: str

    def prepare(self, system: str, user: str, settings: GenerationSettings, api_key: str) -> PreparedRequest: ...

    def parse(self, payload: dict) -> GenerationResult: ...

    def translate_error(self, status: int, payload: dict, model: str) -> AIRequestError: ...


def _hint_for_status(status: int) -> str:
    if status == 401:
        return "AI_API_KEY 값과 환경변수 이름을 확인하세요."
    if status == 403:
        return "API 키의 권한 또는 워크스페이스 설정을 확인하세요."
    if status == 404:
        return "--model 값을 확인하세요."
    if status == 429:
        return "잠시 후 다시 시도하세요."
    if status >= 500:
        return "서버 측 오류입니다. 잠시 후 다시 시도하세요."
    return ""


def _status_label(status: int) -> str:
    labels = {400: "요청 형식 오류", 401: "인증 실패", 403: "권한 없음", 404: "모델을 찾을 수 없음", 429: "요청 한도 초과"}
    if status in labels:
        return labels[status]
    if status >= 500:
        return "서버 오류"
    return "리디렉션 응답 (따르지 않음)" if 300 <= status < 400 else "요청 오류"


def _error_detail(payload: dict) -> dict:
    """오류 본문의 error 필드. 문자열 등 예상 밖 형태도 dict 로 맞춘다."""
    detail = payload.get("error")
    if isinstance(detail, dict):
        return detail
    return {"message": str(detail)} if detail else {}


def is_temperature_rejection(message: str, param: object = None) -> bool:
    """temperature 미지원 400 인지 판정. 단순 언급만으로는 기록하지 않는다."""
    if param == "temperature":
        return True
    lowered = message.lower()
    return "temperature" in lowered and any(hint in lowered for hint in TEMPERATURE_REJECTION_HINTS)


def _compose_error(status: int, message: str, hint: str) -> AIRequestError:
    text = f"{_status_label(status)} (HTTP {status}): {message or '응답 본문 없음'}"
    if hint:
        text += f"\n       {hint}"
    return AIRequestError(text)


class ClaudeProvider:
    name = "claude"
    url = "https://api.anthropic.com/v1/messages"
    api_version = "2023-06-01"

    def prepare(self, system: str, user: str, settings: GenerationSettings, api_key: str) -> PreparedRequest:
        body: dict[str, object] = {
            "model": settings.model,
            "max_tokens": settings.max_tokens,
            "system": system,
            "messages": [{"role": "user", "content": user}],
        }
        if settings.temperature is not None:
            body["temperature"] = settings.temperature
        headers = {"content-type": "application/json", "x-api-key": api_key, "anthropic-version": self.api_version}
        return PreparedRequest(config.endpoint(self.url, "/v1/messages"), headers, body)

    def parse(self, payload: dict) -> GenerationResult:
        blocks = payload.get("content")
        blocks = blocks if isinstance(blocks, list) else []
        text = "".join(
            str(block.get("text", "")) for block in blocks if isinstance(block, dict) and block.get("type") == "text"
        )
        usage = payload.get("usage")
        usage = usage if isinstance(usage, dict) else {}
        return GenerationResult(
            text=text,
            input_tokens=_as_int(usage.get("input_tokens")),
            output_tokens=_as_int(usage.get("output_tokens")),
            stop_reason=str(payload.get("stop_reason") or ""),
        )

    def translate_error(self, status: int, payload: dict, model: str) -> AIRequestError:
        detail = _error_detail(payload)
        message = str(detail.get("message") or "")
        if status == 400 and is_temperature_rejection(message):
            return UnsupportedParameterError(model=model, parameter="temperature", reason=message)
        return _compose_error(status, message, _hint_for_status(status))


class OpenAIProvider:
    name = "openai"
    url = "https://api.openai.com/v1/chat/completions"
    finish_reason_map = {"stop": "end_turn", "length": "max_tokens", "content_filter": "refusal"}
    quota_codes = {"insufficient_quota", "credit_balance_exhausted"}

    @staticmethod
    def token_limit_field(model: str) -> str:
        """모델에 맞는 출력 상한 필드 이름. 추론 모델만 max_completion_tokens, 나머지는 호환성이 넓은 max_tokens."""
        bare = model.lower().rsplit("/", 1)[-1]  # 프록시가 쓰는 "openai/gpt-5" 형태의 벤더 접두 제거
        if bare.startswith(config.OPENAI_COMPLETION_TOKENS_PREFIXES):
            return "max_completion_tokens"
        return "max_tokens"

    def prepare(self, system: str, user: str, settings: GenerationSettings, api_key: str) -> PreparedRequest:
        body: dict[str, object] = {
            "model": settings.model,
            self.token_limit_field(settings.model): settings.max_tokens,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        }
        if settings.temperature is not None:
            body["temperature"] = settings.temperature
        headers = {"content-type": "application/json", "authorization": f"Bearer {api_key}"}
        return PreparedRequest(config.endpoint(self.url, "/v1/chat/completions"), headers, body)

    def parse(self, payload: dict) -> GenerationResult:
        choices = payload.get("choices")
        choice = choices[0] if isinstance(choices, list) and choices and isinstance(choices[0], dict) else {}
        message = choice.get("message")
        message = message if isinstance(message, dict) else {}
        finish = str(choice.get("finish_reason") or "")
        usage = payload.get("usage")
        usage = usage if isinstance(usage, dict) else {}
        return GenerationResult(
            text=str(message.get("content") or ""),
            input_tokens=_as_int(usage.get("prompt_tokens")),
            output_tokens=_as_int(usage.get("completion_tokens")),
            stop_reason=self.finish_reason_map.get(finish, finish),
        )

    def translate_error(self, status: int, payload: dict, model: str) -> AIRequestError:
        detail = _error_detail(payload)
        message = str(detail.get("message") or "")
        param, code = detail.get("param"), str(detail.get("code") or detail.get("type") or "")
        if status == 400 and is_temperature_rejection(message, param):
            return UnsupportedParameterError(model=model, parameter="temperature", reason=message)
        if status == 429 and code in self.quota_codes:
            return _compose_error(status, message, "크레딧이 소진되었습니다. 결제 설정을 확인하세요. 재시도로는 해결되지 않습니다.")
        return _compose_error(status, message, _hint_for_status(status))


class GeminiProvider:
    """Google Gemini API (generateContent). 키는 쿼리 문자열이 아니라 헤더로 보내 URL 로그에 남지 않게 한다."""

    name = "gemini"
    base_url = "https://generativelanguage.googleapis.com"  # 경로에 모델 ID 가 들어가므로 기본 주소만 둔다
    finish_reason_map = {
        "STOP": "end_turn",
        "MAX_TOKENS": "max_tokens",
        "SAFETY": "refusal",
        "RECITATION": "refusal",
        "BLOCKLIST": "refusal",
        "PROHIBITED_CONTENT": "refusal",
        "SPII": "refusal",
        "IMAGE_SAFETY": "refusal",
        "IMAGE_PROHIBITED_CONTENT": "refusal",
        "LANGUAGE": "refusal",
    }
    MODELS_PREFIX = "models/"

    @classmethod
    def endpoint_path(cls, model: str) -> str:
        """`models/` 접두는 벗기고, 나머지는 URL 인코딩한다 (`/`, `?`, `#` 가 경로를 바꾸지 못하게)."""
        name = model[len(cls.MODELS_PREFIX):] if model.startswith(cls.MODELS_PREFIX) else model
        return f"/v1beta/models/{urllib.parse.quote(name, safe='-._')}:generateContent"

    @staticmethod
    def uses_thinking_level(model: str) -> bool:
        bare = model.lower().rsplit("/", 1)[-1]
        return bare.startswith(config.GEMINI_THINKING_LEVEL_PREFIXES)

    def prepare(self, system: str, user: str, settings: GenerationSettings, api_key: str) -> PreparedRequest:
        generation: dict[str, object] = {"maxOutputTokens": settings.max_tokens}
        if settings.temperature is not None:
            generation["temperature"] = settings.temperature
        if self.uses_thinking_level(settings.model):
            generation["thinkingConfig"] = {"thinkingLevel": config.GEMINI_THINKING_LEVEL}
        body: dict[str, object] = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": user}]}],
            "generationConfig": generation,
        }
        headers = {"content-type": "application/json", "x-goog-api-key": api_key}
        path = self.endpoint_path(settings.model)
        return PreparedRequest(config.endpoint(self.base_url + path, path), headers, body)

    @staticmethod
    def _answer_text(candidate: dict) -> str:
        """사고(thought) 조각을 빼고 문자열 text 만 이어 붙인다. null·숫자 같은 값은 무시한다."""
        content = candidate.get("content")
        raw_parts = content.get("parts") if isinstance(content, dict) else None
        parts = raw_parts if isinstance(raw_parts, list) else []
        return "".join(
            p["text"] for p in parts if isinstance(p, dict) and isinstance(p.get("text"), str) and not p.get("thought")
        )

    def parse(self, payload: dict) -> GenerationResult:
        raw_candidates = payload.get("candidates")
        has_candidate = isinstance(raw_candidates, list) and bool(raw_candidates) and isinstance(raw_candidates[0], dict)
        first: dict = raw_candidates[0] if has_candidate else {}
        finish = str(first.get("finishReason") or "")
        feedback = payload.get("promptFeedback")
        if not first and isinstance(feedback, dict) and feedback.get("blockReason"):
            finish = "SAFETY"  # 입력 자체가 차단되면 candidates 가 비고 promptFeedback 만 온다
        raw_usage = payload.get("usageMetadata")
        usage = raw_usage if isinstance(raw_usage, dict) else {}
        return GenerationResult(
            text=self._answer_text(first),
            input_tokens=_as_int(usage.get("promptTokenCount")),
            # 사고 토큰도 출력 상한과 과금에 포함되므로 함께 센다
            output_tokens=_as_int(usage.get("candidatesTokenCount")) + _as_int(usage.get("thoughtsTokenCount")),
            stop_reason=self.finish_reason_map.get(finish, finish.lower()),
        )

    def translate_error(self, status: int, payload: dict, model: str) -> AIRequestError:
        detail = _error_detail(payload)
        message = str(detail.get("message") or "")
        status_name = str(detail.get("status") or "")
        if status == 400 and is_temperature_rejection(message):
            return UnsupportedParameterError(model=model, parameter="temperature", reason=message)
        shown = f"{message} [{status_name}]" if status_name else message
        if status in (400, 401, 403) and "api key" in message.lower():
            return _compose_error(status, shown, "AI_API_KEY(또는 GEMINI_API_KEY) 값과 환경변수 이름을 확인하세요.")
        if status == 429:
            return _compose_error(status, shown, "요청 한도 또는 무료 할당량을 넘었습니다. 잠시 후 다시 시도하거나 결제 설정을 확인하세요.")
        return _compose_error(status, shown, _hint_for_status(status))


PROVIDERS: dict[str, Provider] = {"claude": ClaudeProvider(), "openai": OpenAIProvider(), "gemini": GeminiProvider()}


def get_provider(name: str) -> Provider:
    try:
        return PROVIDERS[name]
    except KeyError as exc:
        raise AIRequestError(f"지원하지 않는 제공자입니다: {name} (가능: {', '.join(PROVIDERS)})") from exc


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    """리디렉션을 따르지 않는다. API 키 헤더가 다른 호스트로 전달되는 일을 막는다."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: D401, ANN001
        return None


_OPENER = urllib.request.build_opener(_NoRedirectHandler)


def send_request(request: PreparedRequest, timeout: float) -> tuple[int, dict]:
    """HTTP POST 를 보내고 (상태 코드, JSON 본문) 을 돌려준다. 응답이 없는 실패만 예외."""
    http_request = urllib.request.Request(
        request.url, data=json.dumps(request.body).encode("utf-8"), headers=request.headers, method="POST"
    )
    try:
        with _OPENER.open(http_request, timeout=timeout) as response:
            return response.status, _read_json(response.read())
    except urllib.error.HTTPError as exc:
        return exc.code, _read_json(exc.read())
    except TimeoutError as exc:
        raise AIRequestError(f"응답 시간 초과 ({timeout:.0f}초). 잠시 후 다시 시도하세요.") from exc
    except urllib.error.URLError as exc:
        raise AIRequestError(f"네트워크 오류: {exc.reason}\n       인터넷 연결과 프록시 설정을 확인하세요.") from exc
    except (OSError, http.client.HTTPException) as exc:
        raise AIRequestError(f"네트워크 오류: {type(exc).__name__}: {exc}\n       잠시 후 다시 시도하세요.") from exc


def _as_int(value: object) -> int:
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0


def _read_json(raw: bytes) -> dict:
    try:
        parsed = json.loads(raw.decode("utf-8", errors="replace"))
    except json.JSONDecodeError:
        return {"error": {"message": raw.decode("utf-8", errors="replace")[:200]}}
    if isinstance(parsed, list) and len(parsed) == 1 and isinstance(parsed[0], dict):
        return parsed[0]  # Gemini 는 오류를 한 원소짜리 배열로 돌려주기도 한다
    return parsed if isinstance(parsed, dict) else {}


class AIClient:
    """제공자를 감싸고 호출 횟수를 센다. 1회 실행에 하나만 만든다."""

    def __init__(self, provider: Provider, api_key: str, timeout: float = config.REQUEST_TIMEOUT_SECONDS) -> None:
        self._provider = provider
        self._api_key = api_key
        self._timeout = timeout
        self.call_count = 0

    def generate(self, system: str, user: str, settings: GenerationSettings) -> GenerationResult:
        request = self._provider.prepare(system, user, settings, self._api_key)
        self.call_count += 1
        status, payload = send_request(request, self._timeout)
        if status >= 300:
            raise self._provider.translate_error(status, payload, settings.model)
        return self._provider.parse(payload)
