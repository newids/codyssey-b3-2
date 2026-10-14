"""팀 컨벤션 설정 파일(.ai-gitgen.json) 읽기와 검증.

파일이 없으면 기본 컨벤션(기존 동작)을 쓴다. 파일의 값은 프롬프트 규칙과 출력 검증·후처리에 함께 반영된다.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from . import config
from .errors import ConventionError

SCOPE_POLICIES = ("optional", "forbidden", "required")
TYPE_PATTERN = re.compile(r"[a-z][a-z0-9-]*")
MIN_TITLE_LIMIT = 20
MAX_TITLE_LIMIT = 120
MAX_RULES = 20  # 설정 파일은 저장소에 들어 있으므로 프롬프트에 넣는 양을 제한한다
MAX_RULE_LENGTH = 300
FOOTER_RULE = "---"
COMMIT_KEYS = ("types", "scope", "title_soft_limit", "title_hard_limit", "rules")
PR_KEYS = ("sections", "title_limit", "test_command", "checklist", "footer", "rules")
TOP_KEYS = ("commit", "pr")


@dataclass(frozen=True)
class CommitConvention:
    types: tuple[str, ...] = config.COMMIT_TYPES
    scope: str = "optional"  # optional | forbidden | required
    title_soft_limit: int = config.COMMIT_TITLE_SOFT_LIMIT
    title_hard_limit: int = config.COMMIT_TITLE_HARD_LIMIT
    rules: tuple[str, ...] = ()  # 프롬프트에 그대로 들어가는 추가 규칙 문장


@dataclass(frozen=True)
class PrConvention:
    sections: tuple[str, ...] = config.PR_REQUIRED_SECTIONS
    title_limit: int = config.PR_TITLE_HARD_LIMIT
    test_command: str = ""  # How to Test 에 반드시 넣을 테스트 명령
    checklist: tuple[str, ...] = ()  # 후처리로 붙이는 "## Checklist" 항목
    footer: str = ""  # 후처리로 본문 끝에 붙이는 한 줄
    rules: tuple[str, ...] = ()


@dataclass(frozen=True)
class Convention:
    commit: CommitConvention = field(default_factory=CommitConvention)
    pr: PrConvention = field(default_factory=PrConvention)
    source: str | None = None  # 읽은 파일 경로. 기본값이면 None

    @property
    def is_default(self) -> bool:
        return self.source is None


DEFAULT_CONVENTION = Convention()


def load_convention(explicit_path: str | None, cwd: str | Path | None = None) -> Convention:
    """--convention 경로가 있으면 그 파일을, 없으면 작업 디렉터리의 .ai-gitgen.json 을 읽는다. 둘 다 없으면 기본값."""
    if explicit_path:
        path = Path(explicit_path)
        if not path.exists():
            raise ConventionError(f"컨벤션 파일을 찾을 수 없습니다: {path}")
    else:
        path = Path(cwd or Path.cwd()) / config.CONVENTION_FILE_NAME
        if not path.exists():
            return DEFAULT_CONVENTION
    if not path.is_file():
        raise ConventionError(f"컨벤션 경로가 파일이 아닙니다: {path}")
    return parse_convention(_read_json(path), source=str(path))


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))  # BOM 허용
    except OSError as exc:
        raise ConventionError(f"컨벤션 파일을 읽을 수 없습니다: {path} ({exc.strerror})") from exc
    except json.JSONDecodeError as exc:
        raise ConventionError(f"컨벤션 파일이 올바른 JSON 이 아닙니다: {path} ({exc.lineno}행 {exc.colno}열: {exc.msg})") from exc
    except (UnicodeDecodeError, RecursionError) as exc:
        raise ConventionError(f"컨벤션 파일을 해석할 수 없습니다: {path} ({type(exc).__name__})") from exc


def parse_convention(data: Any, source: str) -> Convention:
    """JSON 값을 검증해 Convention 으로 바꾼다. 빠진 키는 기본값을 유지한다."""
    if not isinstance(data, dict):
        raise ConventionError(f"{source}: 최상위는 JSON 객체여야 합니다.")
    _reject_unknown_keys(data, TOP_KEYS, prefix="", source=source)
    commit = _parse_commit(_section(data, "commit", source), source)
    pr = _parse_pr(_section(data, "pr", source), source)
    return Convention(commit=commit, pr=pr, source=source)


def _section(data: dict, key: str, source: str) -> dict:
    value = data.get(key, {})
    if not isinstance(value, dict):
        raise ConventionError(f"{source}: {key} 는 객체여야 합니다.")
    return value


def _reject_unknown_keys(data: dict, allowed: tuple[str, ...], prefix: str, source: str) -> None:
    unknown = [k for k in data if k not in allowed]
    if unknown:
        names = ", ".join(f"{prefix}{k}" for k in unknown)
        raise ConventionError(f"{source}: 알 수 없는 키 {names}. 사용 가능: {', '.join(prefix + a for a in allowed)}")


def _parse_commit(data: dict, source: str) -> CommitConvention:
    _reject_unknown_keys(data, COMMIT_KEYS, "commit.", source)
    base = CommitConvention()
    types = _string_list(data, "types", "commit", source, default=base.types)
    for t in types:
        if not TYPE_PATTERN.fullmatch(t):
            raise ConventionError(f"{source}: commit.types 항목은 소문자 영문으로 시작하는 한 단어여야 합니다 (입력: {t!r})")
    _reject_duplicates(types, "commit.types", source)
    scope = data.get("scope", base.scope)
    if scope not in SCOPE_POLICIES:
        raise ConventionError(f"{source}: commit.scope 는 {', '.join(SCOPE_POLICIES)} 중 하나여야 합니다 (입력: {scope!r})")
    hard = _int(data, "title_hard_limit", "commit", source, default=base.title_hard_limit)
    soft = _int(data, "title_soft_limit", "commit", source, default=min(base.title_soft_limit, hard))
    if soft > hard:
        raise ConventionError(f"{source}: commit.title_soft_limit({soft}) 은 title_hard_limit({hard}) 이하여야 합니다.")
    rules = _rules(data, "commit", source)
    return CommitConvention(types=types, scope=scope, title_soft_limit=soft, title_hard_limit=hard, rules=rules)


def _parse_pr(data: dict, source: str) -> PrConvention:
    _reject_unknown_keys(data, PR_KEYS, "pr.", source)
    base = PrConvention()
    sections = tuple(_strip_header(s) for s in _string_list(data, "sections", "pr", source, default=base.sections))
    if any(not s or "#" in s or "\n" in s for s in sections):
        raise ConventionError(f"{source}: pr.sections 항목은 한 줄짜리 제목이어야 합니다 (`#`, 줄바꿈 불가).")
    _reject_duplicates(sections, "pr.sections", source)
    checklist = _string_list(data, "checklist", "pr", source, default=(), allow_empty=True)
    if checklist and config.CHECKLIST_SECTION in sections:
        raise ConventionError(
            f"{source}: pr.checklist 를 쓰면 '{config.CHECKLIST_SECTION}' 섹션은 도구가 붙이므로 pr.sections 에서 빼야 합니다."
        )
    footer = _string(data, "footer", "pr", source)
    if "\n" in footer or footer.startswith("#") or footer == FOOTER_RULE:
        raise ConventionError(f"{source}: pr.footer 는 `#` 으로 시작하지 않는 한 줄이어야 합니다.")
    test_command = _string(data, "test_command", "pr", source)
    if "\n" in test_command:
        raise ConventionError(f"{source}: pr.test_command 는 한 줄이어야 합니다.")
    return PrConvention(
        sections=sections,
        title_limit=_int(data, "title_limit", "pr", source, default=base.title_limit),
        test_command=test_command,
        checklist=checklist,
        footer=footer,
        rules=_rules(data, "pr", source),
    )


def _strip_header(section: str) -> str:
    return section.lstrip("#").strip()


def _reject_duplicates(items: tuple[str, ...], key: str, source: str) -> None:
    if len(set(items)) != len(items):
        raise ConventionError(f"{source}: {key} 에 중복 항목이 있습니다.")


def _rules(data: dict, group: str, source: str) -> tuple[str, ...]:
    rules = _string_list(data, "rules", group, source, default=(), allow_empty=True)
    if len(rules) > MAX_RULES or any(len(r) > MAX_RULE_LENGTH or "\n" in r for r in rules):
        raise ConventionError(f"{source}: {group}.rules 는 최대 {MAX_RULES}개, 각 {MAX_RULE_LENGTH}자 이내의 한 줄이어야 합니다.")
    return rules


def _string_list(
    data: dict, key: str, group: str, source: str, default: tuple[str, ...], allow_empty: bool = False
) -> tuple[str, ...]:
    if key not in data:
        return default
    value = data[key]
    is_list_of_text = isinstance(value, list) and all(isinstance(v, str) and v.strip() for v in value)
    if not is_list_of_text or (not value and not allow_empty):
        kind = "문자열 목록" if allow_empty else "비어 있지 않은 문자열 목록"
        raise ConventionError(f"{source}: {group}.{key} 는 {kind}이어야 합니다.")
    return tuple(v.strip() for v in value)


def _string(data: dict, key: str, group: str, source: str) -> str:
    value = data.get(key, "")
    if not isinstance(value, str):
        raise ConventionError(f"{source}: {group}.{key} 는 문자열이어야 합니다.")
    return value.strip()


def _int(data: dict, key: str, group: str, source: str, default: int) -> int:
    value = data.get(key, default)
    if isinstance(value, bool) or not isinstance(value, int) or not MIN_TITLE_LIMIT <= value <= MAX_TITLE_LIMIT:
        raise ConventionError(f"{source}: {group}.{key} 는 {MIN_TITLE_LIMIT}~{MAX_TITLE_LIMIT} 사이의 정수여야 합니다 (입력: {value!r})")
    return value


def describe(conv: Convention) -> str:
    """`convention show` 출력. 적용 중인 값과 출처를 보여 준다."""
    lines = [
        f"컨벤션 출처: {conv.source or '기본값 (설정 파일 없음)'}",
        "[commit]",
        f"  types            : {', '.join(conv.commit.types)}",
        f"  scope            : {conv.commit.scope}",
        f"  title limit      : 권장 {conv.commit.title_soft_limit}자 / 최대 {conv.commit.title_hard_limit}자",
        f"  rules            : {_join(conv.commit.rules)}",
        "[pr]",
        f"  sections         : {', '.join(conv.pr.sections)}",
        f"  title limit      : {conv.pr.title_limit}자",
        f"  test_command     : {conv.pr.test_command or '-'}",
        f"  checklist        : {_join(conv.pr.checklist)}",
        f"  footer           : {conv.pr.footer or '-'}",
        f"  rules            : {_join(conv.pr.rules)}",
    ]
    return "\n".join(lines) + "\n"


def _join(items: tuple[str, ...]) -> str:
    return " | ".join(items) if items else "-"


def template_json() -> str:
    """`convention init` 이 쓰는 기본값 파일 내용. 그대로 읽으면 기본 컨벤션과 같다."""
    data = {
        "commit": {
            "types": list(config.COMMIT_TYPES),
            "scope": "optional",
            "title_soft_limit": config.COMMIT_TITLE_SOFT_LIMIT,
            "title_hard_limit": config.COMMIT_TITLE_HARD_LIMIT,
            "rules": [],
        },
        "pr": {
            "sections": list(config.PR_REQUIRED_SECTIONS),
            "title_limit": config.PR_TITLE_HARD_LIMIT,
            "test_command": "",
            "checklist": [],
            "footer": "",
            "rules": [],
        },
    }
    return json.dumps(data, ensure_ascii=False, indent=2) + "\n"
