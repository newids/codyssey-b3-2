"""기본값 상수와 환경변수 읽기."""

from __future__ import annotations

import os
import urllib.parse
from pathlib import Path

from .errors import AiGitgenError, MissingApiKeyError

APP_NAME = "ai-gitgen"

# 제공자와 모델
DEFAULT_PROVIDER = "claude"
PROVIDER_NAMES = ("claude", "openai")
DEFAULT_MODELS = {"claude": "claude-sonnet-4-6", "openai": "gpt-4.1-mini"}
DEFAULT_TEMPERATURE = 0.3
DEFAULT_MAX_TOKENS = {"commit": 512, "pr": 1024}
REQUEST_TIMEOUT_SECONDS = 60.0
MAX_API_CALLS_PER_RUN = 2

# 환경변수
API_KEY_ENV = "AI_API_KEY"
PROVIDER_KEY_ENVS = {"claude": "ANTHROPIC_API_KEY", "openai": "OPENAI_API_KEY"}
PROVIDER_ENV = "AI_PROVIDER"
HOME_ENV = "AI_GITGEN_HOME"
BASE_URL_ENV = "AI_API_BASE_URL"  # 프록시·테스트 서버로 엔드포인트를 바꿀 때

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

# 출력 규칙
COMMIT_TITLE_SOFT_LIMIT = 50
COMMIT_TITLE_HARD_LIMIT = 72
PR_TITLE_HARD_LIMIT = 80
PR_REQUIRED_SECTIONS = ("Why", "What", "How to Test")
COMMIT_TYPES = ("feat", "fix", "docs", "style", "refactor", "test", "chore", "perf", "ci", "build", "revert")
PLACEHOLDER_BULLET = "- (작성 필요)"


def registry_path() -> Path:
    """모델 레지스트리 JSON 파일 경로. AI_GITGEN_HOME 으로 바꿀 수 있다."""
    home = os.environ.get(HOME_ENV) or os.path.join(os.path.expanduser("~"), ".ai-gitgen")
    return Path(home) / "model_registry.json"


def load_api_key(provider: str) -> str:
    """AI_API_KEY 를 우선 읽고, 없으면 제공자별 환경변수를 읽는다."""
    fallback_env = PROVIDER_KEY_ENVS.get(provider, "")
    key = (os.environ.get(API_KEY_ENV) or (os.environ.get(fallback_env) if fallback_env else "") or "").strip()
    if key:
        return key
    hint = f"예) export {API_KEY_ENV}=\"YOUR_KEY\""
    if fallback_env:
        hint += f"  (또는 {fallback_env})"
    raise MissingApiKeyError(f"{API_KEY_ENV} 환경변수가 설정되지 않았습니다.\n{hint}")


LOCAL_HOSTS = ("localhost", "127.0.0.1", "::1")


def endpoint(default_url: str, path: str) -> str:
    """AI_API_BASE_URL 이 있으면 그 주소 아래의 path 를, 없으면 기본 URL 을 쓴다.

    API 키가 평문으로 나가지 않도록 https 만 허용한다. 로컬 테스트 서버만 http 를 허용한다.
    """
    base = os.environ.get(BASE_URL_ENV, "").strip().rstrip("/")
    if not base:
        return default_url
    parsed = urllib.parse.urlparse(base)
    is_local = (parsed.hostname or "") in LOCAL_HOSTS
    if parsed.scheme != "https" and not (parsed.scheme == "http" and is_local):
        raise AiGitgenError(f"{BASE_URL_ENV} 는 https:// 주소여야 합니다 (로컬 테스트 서버만 http 허용): {base}")
    return f"{base}{path}"


def default_provider() -> str:
    value = os.environ.get(PROVIDER_ENV, DEFAULT_PROVIDER).strip().lower()
    return value if value in PROVIDER_NAMES else DEFAULT_PROVIDER
