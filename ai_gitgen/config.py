"""기본값 상수와 환경변수 읽기."""

from __future__ import annotations

import os
import urllib.parse
from dataclasses import dataclass, field
from pathlib import Path

from .errors import ConfigurationError, MissingApiKeyError

APP_NAME = "ai-gitgen"

# 종료 코드. 스크립트에서 `ai-gitgen commit > msg || ...` 처럼 분기할 수 있게 상황별로 나눈다
EXIT_OK = 0
EXIT_ERROR = 1  # 실행 중 오류: API 응답 오류, git 실패, 예상하지 못한 예외
EXIT_USAGE = 2  # 실행 전에 고쳐야 하는 것: 옵션 값, API 키 없음, 설정 파일 오류 (argparse 와 같은 값)
EXIT_NO_CHANGES = 3  # 오류는 아니지만 생성할 것이 없음
EXIT_INTERRUPTED = 130  # Ctrl+C

# 제공자와 모델
DEFAULT_PROVIDER = "claude"
PROVIDER_NAMES = ("claude", "openai", "gemini")
DEFAULT_MODELS = {
    "claude": "claude-sonnet-4-6",
    "openai": "gpt-4.1-mini",
    "gemini": "gemini-3.8-flash",  # 공식 모델 목록이 새 프로젝트에 권장하는 Flash (2026-10 확인)
}
DEFAULT_TEMPERATURE = 0.3
# --temperature 를 주지 않았을 때 제공자별 값. None 이면 요청에서 빼고 모델 기본값을 쓴다.
# Gemini 3 계열은 기본값 1.0 아래로 낮추면 반복·품질 저하가 생길 수 있다고 공식 문서가 권고한다.
DEFAULT_TEMPERATURES: dict[str, float | None] = {"claude": DEFAULT_TEMPERATURE, "openai": DEFAULT_TEMPERATURE, "gemini": None}
DEFAULT_MAX_TOKENS = {"commit": 512, "pr": 1024}
REQUEST_TIMEOUT_SECONDS = 60.0
MAX_API_CALLS_PER_RUN = 2

# 환경변수
API_KEY_ENV = "AI_API_KEY"
PROVIDER_KEY_ENVS = {
    "claude": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
    "gemini": "GEMINI_API_KEY",
}
PROVIDER_ENV = "AI_PROVIDER"
HOME_ENV = "AI_GITGEN_HOME"
URL_ENV = "AI_API_URL"  # 프록시·테스트 서버 주소. 설정되면 그 아래 /v1/... 경로를 쓴다
LEGACY_URL_ENV = "AI_API_BASE_URL"  # 이전 이름. AI_API_URL 이 없을 때만 읽는다
MODEL_ENV = "AI_API_MODEL"  # 기본 모델 덮어쓰기
FAST_MODEL_ENV = "AI_SMALL_FAST_MODEL"  # --fast 옵션이 쓰는 작고 빠른 모델
FAST_MODELS = {  # FAST_MODEL_ENV 가 없을 때
    "claude": "claude-haiku-4-5",
    "openai": "gpt-4.1-nano",
    "gemini": "gemini-3.5-flash-lite",
}
PROXY_DEFAULT_PROVIDER = "openai"  # 프록시는 대개 OpenAI 호환 형식을 받는다
# OpenAI 추론 모델은 출력 상한을 max_completion_tokens 로만 받고 max_tokens 를 400 으로 거부한다.
# 그 밖의 모델과 OpenAI 호환 프록시·로컬 서버는 max_tokens 만 알아듣는 경우가 많다 (수업용 프록시가 그렇다).
OPENAI_COMPLETION_TOKENS_PREFIXES = ("gpt-5", "o1", "o3", "o4")
# Gemini 는 사고(thinking) 토큰이 maxOutputTokens 에 포함된다. 커밋 메시지처럼 짧고 정형화된 작업은 가장 낮은 단계로 고정해
# 출력 상한이 사고에 소진되는 일을 줄인다. thinkingLevel 을 받는다고 확인된 세대(허용 목록)에만 보내고,
# 2.x 계열·gemma 등 그 밖의 모델은 필드 없이 보낸다 (모르는 필드는 400 이 되고 재시도 경로가 없다).
GEMINI_THINKING_LEVEL = "low"
GEMINI_THINKING_LEVEL_PREFIXES = ("gemini-3", "gemini-4")

# diff 전송량 정책
GLOBAL_MAX_DIFF_LINES = 2000
SAFE_MODE_MAX_FILES = 10
SAFE_MODE_MAX_LINES_PER_FILE = 200
SAFE_MODE_EXCLUDED_PATTERNS = (
    ".env",
    ".env.*",
    "*.pem",
    "*.key",
    "*.p12",
    "*.lock",
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "*.min.js",
)

BUILTIN_MASK_RULE_NAMES = (  # sanitizer.MASK_RULES 와 같은 순서. 설정 파일의 disabled_rules 검증에 쓴다
    "PRIVATE_KEY",
    "ANTHROPIC_KEY",
    "OPENAI_KEY",
    "AWS_KEY",
    "GITHUB_TOKEN",
    "JWT",
    "GENERIC_SECRET",
    "EMAIL",
    "PHONE_KR",
)

# 출력 규칙
COMMIT_TITLE_SOFT_LIMIT = 50
COMMIT_TITLE_HARD_LIMIT = 72
PR_TITLE_HARD_LIMIT = 80
PR_REQUIRED_SECTIONS = ("Why", "What", "How to Test")
COMMIT_TYPES = ("feat", "fix", "docs", "style", "refactor", "test", "chore", "perf", "ci", "build", "revert")
PLACEHOLDER_BULLET = "- (작성 필요)"
CHECKLIST_SECTION = "Checklist"  # 컨벤션의 checklist 항목을 붙이는 섹션 이름

# 팀 컨벤션 설정 파일. 저장소 루트(실행 위치)에서 찾고, --convention 으로 다른 경로를 줄 수 있다
CONVENTION_FILE_NAME = ".ai-gitgen.json"


def registry_path() -> Path:
    """모델 레지스트리 JSON 파일 경로. AI_GITGEN_HOME 으로 바꿀 수 있다."""
    home = os.environ.get(HOME_ENV) or os.path.join(os.path.expanduser("~"), ".ai-gitgen")
    return Path(home) / "model_registry.json"


@dataclass(frozen=True)
class ApiCredential:
    """API 키와 그 키를 읽은 환경변수 이름. 로그에는 이름만 쓰고 값은 절대 쓰지 않는다."""

    key: str = field(repr=False)  # 디버그 출력·테스트 실패 메시지에도 값이 찍히지 않게
    env_name: str


def resolve_api_key(provider: str) -> ApiCredential:
    """AI_API_KEY 를 우선 읽고, 없으면 제공자별 환경변수를 읽는다. 둘 다 없으면 MissingApiKeyError."""
    fallback_env = PROVIDER_KEY_ENVS.get(provider, "")
    for env_name in (API_KEY_ENV, fallback_env):
        key = os.environ.get(env_name, "").strip() if env_name else ""
        if key:
            return ApiCredential(key=key, env_name=env_name)
    hint = f"예) export {API_KEY_ENV}=\"YOUR_KEY\""
    if fallback_env:
        hint += f"  (또는 {fallback_env})"
    raise MissingApiKeyError(
        f"{API_KEY_ENV} 환경변수가 설정되지 않았습니다. API 를 호출하지 않고 종료합니다.\n{hint}\n"
        "       프롬프트만 확인하려면 --dry-run 을 쓰세요 (키 불필요)."
    )


LOCAL_HOSTS = ("localhost", "127.0.0.1", "::1")


def api_base_url() -> str:
    """AI_API_URL (없으면 AI_API_BASE_URL) 값. 끝의 / 는 제거. 설정이 없으면 빈 문자열."""
    return (os.environ.get(URL_ENV) or os.environ.get(LEGACY_URL_ENV) or "").strip().rstrip("/")


def validate_api_base_url() -> str:
    """AI_API_URL 을 검사해 돌려준다(없으면 빈 문자열). 실행 시작 시 한 번 부른다.

    API 키가 평문으로 나가지 않도록 https 만 허용한다. 로컬 테스트 서버만 http 를 허용한다.
    """
    base = api_base_url()
    if not base:
        return ""
    parsed = urllib.parse.urlparse(base)
    is_local = (parsed.hostname or "") in LOCAL_HOSTS
    if parsed.scheme != "https" and not (parsed.scheme == "http" and is_local):
        raise ConfigurationError(f"{URL_ENV} 는 https:// 주소여야 합니다 (로컬 테스트 서버만 http 허용): {base}")
    return base


def endpoint(default_url: str, path: str) -> str:
    """AI_API_URL 이 있으면 그 주소 아래의 path 를, 없으면 공식 URL 을 쓴다."""
    base = validate_api_base_url()
    return f"{base}{path}" if base else default_url


def default_provider() -> str:
    """AI_PROVIDER 가 있으면 그 값. 없고 AI_API_URL 이 있으면 OpenAI 호환 형식, 둘 다 없으면 claude."""
    value = os.environ.get(PROVIDER_ENV, "").strip().lower()
    if value in PROVIDER_NAMES:
        return value
    return PROXY_DEFAULT_PROVIDER if api_base_url() else DEFAULT_PROVIDER


def resolve_model(provider: str, explicit: str | None, fast: bool) -> str:
    """모델 결정 순서: --model > --fast(AI_SMALL_FAST_MODEL 또는 제공자별 기본) > AI_API_MODEL > 제공자 기본."""
    if explicit:
        return explicit
    if fast:
        return os.environ.get(FAST_MODEL_ENV, "").strip() or FAST_MODELS[provider]
    return os.environ.get(MODEL_ENV, "").strip() or DEFAULT_MODELS[provider]
