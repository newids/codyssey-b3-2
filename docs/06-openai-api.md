# OpenAI API 연동 — B3-2 보조 문서

가이드 본문은 Claude Messages API 를 기준으로 썼습니다. 이 문서는 **같은 도구를 OpenAI API 로 만들거나, 두 제공자를 모두 지원하려는 경우**에 필요한 것만 모았습니다.
구조는 같고 바뀌는 것은 엔드포인트, 헤더, 본문 필드 이름, 응답 경로, 오류 형식입니다. 모두 `ai_client.py` 한 곳에 모아 두면 나머지 모듈은 손대지 않아도 됩니다.

가격과 모델 목록은 2026년 10월 13일에 OpenAI 공식 문서(developers.openai.com)에서 확인한 값입니다. 자주 바뀌므로 README 에 적을 때는 확인 날짜를 함께 적으세요.

## 1. 언제 OpenAI 를 고르는가

| 상황 | 권장 |
| --- | --- |
| 이미 OpenAI 키가 있고 크레딧이 남아 있다 | OpenAI. 미션 요구는 제공자를 가리지 않는다 |
| 가장 싸게 실험하고 싶다 | OpenAI `gpt-4.1-nano` 또는 `gpt-5-nano` (입력 $0.05~0.10 / 1M 토큰) |
| `--temperature` 가 확실히 동작하는 모델이 필요하다 | Claude `claude-sonnet-4-6` 또는 OpenAI `gpt-4.1` 계열. 두 제공자 모두 최신 추론 모델은 `temperature` 를 거부한다 (4절) |
| 두 제공자를 전환 가능하게 만들어 평가에서 "추상화"를 보여 주고 싶다 | 7절의 `--provider` 설계 |

## 2. Claude 와 OpenAI 요청·응답 대응표

| 항목 | Claude Messages API | OpenAI Chat Completions API |
| --- | --- | --- |
| 엔드포인트 | `POST https://api.anthropic.com/v1/messages` | `POST https://api.openai.com/v1/chat/completions` |
| 인증 헤더 | `x-api-key: <KEY>` | `Authorization: Bearer <KEY>` |
| 버전 헤더 | `anthropic-version: 2023-06-01` (필수) | 없음 |
| 환경변수 관례 | `ANTHROPIC_API_KEY` | `OPENAI_API_KEY` |
| 시스템 프롬프트 | 최상위 `system` 필드 | `messages` 배열의 첫 항목 `{"role": "system", ...}` (최신 모델은 `developer` 역할도 가능) |
| 사용자 메시지 | `messages: [{"role": "user", "content": "..."}]` | 같음 |
| 출력 상한 | `max_tokens` (필수) | `max_completion_tokens` (선택). `max_tokens` 는 폐기 예정이며 추론 모델에서 오류 |
| 샘플링 | `temperature` 0~1 | `temperature` 0~2 (기본 1). `top_p` 와 동시 사용 비권장 |
| 사고 깊이 | `output_config.effort` | `reasoning_effort` (`none`/`minimal`/`low`/`medium`/`high`/`xhigh`/`max`, 모델별 지원 상이) |
| 생성 텍스트 | `content[]` 중 `type == "text"` 블록의 `text` 를 이어 붙임 | `choices[0].message.content` (문자열) |
| 멈춘 이유 | `stop_reason`: `end_turn`, `max_tokens`, `refusal` | `choices[0].finish_reason`: `stop`, `length`, `content_filter` |
| 토큰 사용량 | `usage.input_tokens`, `usage.output_tokens` | `usage.prompt_tokens`, `usage.completion_tokens`, `usage.total_tokens` |
| 오류 본문 | `{"type":"error","error":{"type":"...","message":"..."}}` | `{"error":{"message":"...","type":"...","param":"...","code":"..."}}` |

도구 내부의 `GenerationResult(text, input_tokens, output_tokens, stop_reason)` 는 그대로 두고, OpenAI 응답을 이 형태로 바꿔 넣습니다. `finish_reason` 은 `length → max_tokens`, `stop → end_turn`, `content_filter → refusal` 로 매핑하면 상위 모듈의 경고 로직을 공유할 수 있습니다.

## 3. 요청·응답 예시

### 3.1 터미널에서 먼저 성공시키기

```bash
export OPENAI_API_KEY="YOUR_KEY"
curl -s https://api.openai.com/v1/chat/completions \
  -H "content-type: application/json" \
  -H "Authorization: Bearer $OPENAI_API_KEY" \
  -d '{"model":"gpt-4.1-mini","max_completion_tokens":256,"temperature":0.3,
       "messages":[{"role":"system","content":"한 줄로 답하십시오."},
                   {"role":"user","content":"인사해 줘"}]}' | python3 -m json.tool
```

응답에서 볼 곳: `choices[0].message.content`, `choices[0].finish_reason`, `usage`.

### 3.2 표준 라이브러리 `urllib` 구현

가이드 6단계의 `generate()` 와 같은 서명을 유지합니다.

```python
import json, os, urllib.error, urllib.request
from .errors import AIRequestError, MissingApiKeyError, UnsupportedParameterError

OPENAI_URL = "https://api.openai.com/v1/chat/completions"
FINISH_REASON_MAP = {"stop": "end_turn", "length": "max_tokens", "content_filter": "refusal"}

def load_openai_key() -> str:
    key = os.environ.get("AI_API_KEY") or os.environ.get("OPENAI_API_KEY")
    if not key:
        raise MissingApiKeyError('AI_API_KEY 환경변수가 설정되지 않았습니다.\n예) export AI_API_KEY="YOUR_KEY"')
    return key

def generate_openai(system: str, user: str, *, model: str, temperature: float | None,
                    max_tokens: int, timeout: float = 60.0) -> GenerationResult:
    body: dict[str, object] = {
        "model": model,
        "max_completion_tokens": max_tokens,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
    }
    if temperature is not None:
        body["temperature"] = temperature
    request = urllib.request.Request(
        OPENAI_URL, data=json.dumps(body).encode("utf-8"), method="POST",
        headers={"content-type": "application/json", "authorization": f"Bearer {load_openai_key()}"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.load(response)
    except urllib.error.HTTPError as exc:
        raise _translate_openai_error(exc, model) from exc
    except urllib.error.URLError as exc:
        raise AIRequestError(f"네트워크 오류: {exc.reason}") from exc
    except TimeoutError as exc:
        raise AIRequestError(f"응답 시간 초과 ({timeout:.0f}초)") from exc

    choice = payload["choices"][0]
    usage = payload.get("usage", {})
    return GenerationResult(
        text=choice["message"].get("content") or "",
        input_tokens=usage.get("prompt_tokens", 0),
        output_tokens=usage.get("completion_tokens", 0),
        stop_reason=FINISH_REASON_MAP.get(choice.get("finish_reason", ""), choice.get("finish_reason", "")),
    )
```

### 3.3 Responses API 에 대해

OpenAI 는 신규 개발에 `POST /v1/responses` 를 권장합니다. 본문은 `model`, `instructions`(시스템 프롬프트에 해당), `input`(문자열 또는 메시지 배열), `max_output_tokens`, `reasoning: {"effort": ...}` 이고, 텍스트는 `output[]` 중 `type == "message"` 항목의 `content[]` 에서 `type == "output_text"` 인 블록의 `text` 를 모읍니다.
이 미션은 단일 호출·텍스트 출력이므로 Chat Completions 로 충분하며, 학습 자료와 예제가 더 많습니다. 도구 호출이나 대화 상태 유지가 필요해지면 그때 옮기면 됩니다.

## 4. 모델 선택과 `temperature` 지원

### 4.1 가격 (표준 등급, 1M 토큰당 USD, 2026-10-13 확인)

| 모델 | 입력 | 출력 | `temperature` | 이 미션 적합도 |
| --- | --- | --- | --- | --- |
| `gpt-4.1-nano` | 0.10 | 0.40 | 허용 | 가장 싼 실험용 |
| `gpt-4.1-mini` | 0.40 | 1.60 | 허용 | **권장 기본값** (품질·비용 균형, 옵션 요구 충족) |
| `gpt-4.1` | 2.00 | 8.00 | 허용 | 품질 비교용 |
| `gpt-4o-mini` | 0.15 | 0.60 | 허용 | 구세대, 저렴 |
| `gpt-5-nano` | 0.05 | 0.40 | 추론 켜짐 → 거부 | `--temperature` 생략 시 가장 저렴 |
| `gpt-5-mini` | 0.25 | 2.00 | 추론 켜짐 → 거부 | 품질 좋음, 옵션 요구와 충돌 |
| `gpt-5` | 1.25 | 10.00 | 추론 켜짐 → 거부 | 동일 |
| `gpt-5.4-mini` | 0.75 | 4.50 | 추론 켜짐 → 거부 | 동일 |
| `gpt-5.5` | 5.00 | 30.00 | 추론 켜짐 → 거부 | 이 미션에는 과함 |

diff 2,000토큰 + 출력 200토큰 기준 1회 비용은 `gpt-4.1-mini` 약 0.001달러, `gpt-4.1-nano` 약 0.0003달러입니다. Claude Sonnet 4.6(약 0.008달러)보다 저렴하므로 실험 횟수를 늘리기 좋습니다.

### 4.2 `temperature` 거부 규칙

OpenAI 의 추론 모델(gpt-5 계열, o 시리즈)은 **추론이 켜져 있으면** `temperature`, `top_p` 를 받지 않습니다. 기본값 1 외의 값을 보내면 다음 400 이 옵니다.

```json
{
  "error": {
    "message": "Unsupported value: 'temperature' does not support 0.3 with this model. Only the default (1) value is supported.",
    "type": "invalid_request_error",
    "param": "temperature",
    "code": "unsupported_value"
  }
}
```

`reasoning_effort` 를 `none` 으로 둘 수 있는 모델에서는 `temperature` 가 다시 허용됩니다. 어떤 모델이 `none` 을 지원하는지는 세대마다 다르므로(공식 문서에 모델별로 명시), 사용하려는 모델로 직접 한 번 시험해 보는 것이 가장 확실합니다. 같은 가족 안에서도 다르다는 보고가 있습니다.

이 미션의 요구(`--temperature` 옵션이 실제로 영향을 줘야 함)를 기준으로 하면 **`gpt-4.1` 계열이 안전한 선택**입니다.

### 4.3 레지스트리 내장 목록 (OpenAI 용)

가이드 3.4절의 모델 레지스트리를 OpenAI 에도 그대로 적용합니다. 내장 목록은 제공자별로 나눕니다.

```python
BUILTIN_NO_TEMPERATURE_MODELS: dict[str, frozenset[str]] = {
    "claude": frozenset({
        "claude-fable-5-1", "claude-fable-5", "claude-opus-5-5", "claude-opus-5",
        "claude-opus-4-8", "claude-opus-4-7", "claude-sonnet-5-5", "claude-sonnet-5", "claude-haiku-5-5",
    }),
    "openai": frozenset({
        "gpt-5", "gpt-5-mini", "gpt-5-nano", "gpt-5.1", "gpt-5.2",
        "gpt-5.4", "gpt-5.4-mini", "gpt-5.4-nano", "gpt-5.5",
        "o1", "o3", "o3-mini", "o4-mini",
    }),
}
```

`reasoning_effort: "none"` 으로 `temperature` 를 쓰고 싶은 모델은 `models remove <id>` 로 제외 목록에 넣으면 됩니다. 그 뒤 400 이 나면 다시 학습 목록에 들어가므로 안전합니다.

## 5. 오류 처리 대응표

OpenAI 오류 본문에는 `param` 과 `code` 가 있어 Claude 보다 분류가 쉽습니다. 특히 `param == "temperature"` 를 보면 **메시지 문자열 검색 없이** 레지스트리 기록 조건을 판정할 수 있습니다.

| HTTP | `error.type` / `error.code` | 뜻 | 도구의 처리 |
| --- | --- | --- | --- |
| 400 | `invalid_request_error`, `param: "temperature"`, `code: "unsupported_value"` | 추론 모델에 `temperature` 전송 | `UnsupportedParameterError` → 레지스트리 기록 → `temperature` 없이 1회 재요청 |
| 400 | `invalid_request_error`, `param: "max_tokens"` | 추론 모델에 폐기된 `max_tokens` 전송 | 코드 버그. `max_completion_tokens` 사용 |
| 400 | 기타 | 형식 오류, 모델 ID 오류(일부는 404) | 메시지 그대로 출력 |
| 401 | `invalid_api_key` 등 | 키 오류, 조직 미소속, IP 미허용 | "키 값과 환경변수 이름 확인" |
| 403 | 지역 미지원 | 접속 지역 문제 | 메시지 그대로 |
| 404 | `model_not_found` | 모델 ID 오류 | "`--model` 값 확인" |
| 429 | `insufficient_quota` / `credit_balance_exhausted` | **크레딧 소진.** 기다려도 해결되지 않음 | "결제·크레딧 확인". 재시도 안내 금지 |
| 429 | `rate_limit_error`, `code: "slow_down"` 또는 요청 한도 | 분당 요청·토큰 초과 | "잠시 후 재시도" |
| 429 | `*_spend_limit_exceeded`, `*_usage_limit_exceeded` | 지출·사용 한도 설정에 걸림 | "한도 설정 확인" |
| 500 | 서버 오류 | OpenAI 측 문제 | "잠시 후 재시도" |
| 503 | `service_unavailable_error`, `code: "server_is_overloaded"` | 과부하 | "잠시 후 재시도" |

429 가 두 종류라는 점이 중요합니다. 크레딧 소진을 "잠시 후 재시도"로 안내하면 사용자가 계속 실패합니다. `error.code` 로 구분하세요.

```python
def _translate_openai_error(exc: urllib.error.HTTPError, model: str) -> AIRequestError:
    try:
        detail = json.loads(exc.read().decode("utf-8", errors="replace")).get("error", {})
    except json.JSONDecodeError:
        detail = {}
    message, param, code = detail.get("message", ""), detail.get("param"), detail.get("code")

    if exc.code == 400 and param == "temperature":
        return UnsupportedParameterError(model=model, parameter="temperature", reason=message)
    if exc.code == 401:
        return AIRequestError(f"인증 실패 (HTTP 401): {message}\n       AI_API_KEY 값과 환경변수 이름을 확인하세요.")
    if exc.code == 404:
        return AIRequestError(f"모델을 찾을 수 없습니다 (HTTP 404): {message}\n       --model 값을 확인하세요.")
    if exc.code == 429 and code in {"insufficient_quota", "credit_balance_exhausted"}:
        return AIRequestError(f"크레딧이 소진되었습니다 (HTTP 429): {message}\n       결제 설정을 확인하세요. 재시도로는 해결되지 않습니다.")
    if exc.code == 429:
        return AIRequestError(f"요청 한도 초과 (HTTP 429): {message}\n       잠시 후 다시 시도하세요.")
    if exc.code >= 500:
        return AIRequestError(f"서버 오류 (HTTP {exc.code}): {message}\n       잠시 후 다시 시도하세요.")
    return AIRequestError(f"요청 오류 (HTTP {exc.code}): {message}")
```

## 6. Python SDK 를 쓰는 경우

```bash
pip install openai
```

```python
from openai import OpenAI
import openai

client = OpenAI()   # OPENAI_API_KEY 환경변수를 읽는다

try:
    completion = client.chat.completions.create(
        model="gpt-4.1-mini", max_completion_tokens=512, temperature=0.3,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
    )
except openai.AuthenticationError as exc:      # 401
    ...
except openai.RateLimitError as exc:           # 429. exc.code 로 insufficient_quota 구분
    ...
except openai.BadRequestError as exc:          # 400. exc.param == "temperature" 확인
    ...
except openai.APIStatusError as exc:           # 그 외 4xx/5xx
    ...
except openai.APIConnectionError as exc:       # 네트워크, 타임아웃(APITimeoutError 는 이 클래스의 하위)
    ...

text = completion.choices[0].message.content or ""
```

SDK 는 429 와 5xx 를 자동 재시도(기본 2회)합니다. 과제의 "호출 1~2회" 로그에 재시도를 포함할지 정해 README 에 적으세요. 표준 라이브러리 방식과 SDK 방식을 한 프로젝트에 섞지 않습니다.

## 7. 두 제공자를 함께 지원하는 설계

`--provider claude|openai` 옵션(기본값은 환경변수 `AI_PROVIDER`, 없으면 `claude`)을 두고, 제공자별 차이를 작은 클래스로 가둡니다.

```python
from typing import Protocol

class AIProvider(Protocol):
    name: str
    default_model: str
    def generate(self, system: str, user: str, *, model: str, temperature: float | None,
                 max_tokens: int, timeout: float) -> GenerationResult: ...

PROVIDERS: dict[str, AIProvider] = {"claude": ClaudeProvider(), "openai": OpenAIProvider()}
```

| 구성 요소 | 공유 | 제공자별 |
| --- | --- | --- |
| git 수집, sanitizer, prompts, validators, formatter | 예 | — |
| `GenerationResult`, `UnsupportedParameterError` | 예 | — |
| 엔드포인트, 헤더, 본문 조립, 응답 파싱, 오류 번역 | — | `ClaudeProvider`, `OpenAIProvider` |
| 기본 모델 | — | `claude-sonnet-4-6` / `gpt-4.1-mini` |
| 환경변수 | `AI_API_KEY` 우선 | 없으면 `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` |
| 레지스트리 내장 목록 | 파일은 하나 | 제공자별 집합(4.3절). 학습 목록 키는 `"openai:gpt-5-mini"` 처럼 제공자 접두 |

프롬프트는 두 제공자에서 그대로 통합니다. 시스템 프롬프트가 Claude 에서는 `system` 필드로, OpenAI 에서는 첫 메시지로 들어간다는 차이만 `Provider.generate` 안에서 처리합니다.

평가에서 "제공자를 바꾸면 어디를 고치나"라는 질문에 "`providers/` 아래 파일 하나 추가, 나머지 무변경"이라고 답할 수 있으면 과제 목표 1(연동 흐름 설명)에 좋은 근거가 됩니다.

## 8. 미션 요구와의 대응 점검

| 과제 요구 | OpenAI 로 구현 시 확인할 것 |
| --- | --- |
| API 키 환경변수 | `AI_API_KEY` 또는 `OPENAI_API_KEY`. README 에 둘 다 적는다 |
| `--model`, `--temperature`, `--max-tokens` 옵션 | 기본 모델은 `temperature` 를 받는 `gpt-4.1-mini`. `--max-tokens` 는 본문에서 `max_completion_tokens` 로 보낸다 |
| 호출 실패 시 원인 포함 메시지 | `error.message` + `error.code` 를 함께 출력. 429 두 종류 구분 |
| 호출 1~2회 | SDK 자동 재시도 여부를 README 에 명시 |
| 비용/요청 제한 안내 | 4.1절 가격표와 `usage.total_tokens` 로그 |
| 민감정보 | 제공자와 무관. 같은 sanitizer |

## 9. 참고 링크

- Chat Completions API 레퍼런스: <https://developers.openai.com/api/docs/api-reference/chat/create>
- Responses API 레퍼런스: <https://developers.openai.com/api/docs/api-reference/responses/create>
- 오류 코드 안내: <https://developers.openai.com/api/docs/guides/error-codes>
- 가격: <https://developers.openai.com/api/docs/pricing>
- 최신 모델 안내(추론 모델에서 `temperature` 제거 지침 포함): <https://developers.openai.com/api/docs/guides/latest-model>
- 추론 모델의 `temperature` 오류 사례(커뮤니티): <https://community.openai.com/t/temperature-in-gpt-5-models/1337133>
- Python SDK 저장소: <https://github.com/openai/openai-python>
