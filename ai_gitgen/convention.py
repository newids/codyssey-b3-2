"""팀 설정 파일(.ai-gitgen.json) 읽기와 검증: 커밋/PR 컨벤션과 safe-mode 정책.

파일이 없으면 기본값(기존 동작)을 쓴다. 컨벤션은 프롬프트 규칙과 출력 검증·후처리에, safe-mode 정책은 sanitizer 에 반영된다.
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
SAFE_MODE_KEYS = ("max_files", "max_lines_per_file", "global_max_lines", "exclude", "mask_rules", "disabled_rules")
MASK_RULE_KEYS = ("name", "pattern")
TOP_KEYS = ("commit", "pr", "safe_mode")
MASK_NAME_PATTERN = re.compile(r"[A-Z][A-Z0-9_]{1,30}")
MAX_MASK_RULES = 20
MAX_MASK_PATTERN_LENGTH = 200
MAX_EXCLUDE_PATTERNS = 50
MAX_CONFIG_BYTES = 1_000_000  # 저장소가 주는 파일이므로 크기를 제한한다
# 자격 증명 규칙은 설정 파일로 끌 수 없다. 오탐이 잦은 GENERIC_SECRET, EMAIL, PHONE_KR 만 끌 수 있다.
PROTECTED_MASK_RULES = ("PRIVATE_KEY", "ANTHROPIC_KEY", "OPENAI_KEY", "AWS_KEY", "GITHUB_TOKEN", "JWT")
NESTED_QUANTIFIER = re.compile(r"\([^()]*[+*}][^()]*\)\s*[+*{]")  # (a+)+ 같은 중첩 반복: 역추적 폭발 위험
BACKREFERENCE = re.compile(r"\\[1-9]|\(\?P=")
LIMIT_RANGES = {  # (최소, 최대)
    "max_files": (1, 200),
    "max_lines_per_file": (10, 5000),
    "global_max_lines": (100, 20000),
}


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
class MaskRule:
    """사용자 정의 마스킹 규칙. 치환 결과는 `[MASKED:name]`."""

    name: str
    pattern: re.Pattern[str]


@dataclass(frozen=True)
class SafeModePolicy:
    """safe-mode 전송량 제한과 마스킹 정책. 설정 파일의 safe_mode 섹션과 CLI 옵션이 채운다."""

    max_files: int = config.SAFE_MODE_MAX_FILES
    max_lines_per_file: int = config.SAFE_MODE_MAX_LINES_PER_FILE
    global_max_lines: int = config.GLOBAL_MAX_DIFF_LINES  # safe-mode 가 꺼져 있어도 적용
    exclude: tuple[str, ...] = ()  # 내장 제외 패턴에 더하는 glob
    mask_rules: tuple[MaskRule, ...] = ()  # 내장 규칙 뒤에 적용
    disabled_rules: tuple[str, ...] = ()  # 끄는 내장 규칙 이름

    @property
    def excluded_patterns(self) -> tuple[str, ...]:
        return config.SAFE_MODE_EXCLUDED_PATTERNS + self.exclude


@dataclass(frozen=True)
class Convention:
    commit: CommitConvention = field(default_factory=CommitConvention)
    pr: PrConvention = field(default_factory=PrConvention)
    safe_mode: SafeModePolicy = field(default_factory=SafeModePolicy)
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
        if path.stat().st_size > MAX_CONFIG_BYTES:
            raise ConventionError(f"컨벤션 파일이 너무 큽니다 ({path.stat().st_size:,} 바이트 > {MAX_CONFIG_BYTES:,}): {path}")
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
    safe_mode = _parse_safe_mode(_section(data, "safe_mode", source), source)
    return Convention(commit=commit, pr=pr, safe_mode=safe_mode, source=source)


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


def _parse_safe_mode(data: dict, source: str) -> SafeModePolicy:
    _reject_unknown_keys(data, SAFE_MODE_KEYS, "safe_mode.", source)
    base = SafeModePolicy()
    limits = {
        key: _bounded_int(data.get(key, getattr(base, key)), key, LIMIT_RANGES[key], f"{source}: safe_mode.{key}")
        for key in LIMIT_RANGES
    }
    exclude = _string_list(data, "exclude", "safe_mode", source, default=(), allow_empty=True)
    if len(exclude) > MAX_EXCLUDE_PATTERNS:
        raise ConventionError(f"{source}: safe_mode.exclude 는 최대 {MAX_EXCLUDE_PATTERNS}개입니다.")
    disabled = _string_list(data, "disabled_rules", "safe_mode", source, default=(), allow_empty=True)
    unknown = [name for name in disabled if name not in config.BUILTIN_MASK_RULE_NAMES]
    if unknown:
        raise ConventionError(
            f"{source}: safe_mode.disabled_rules 에 모르는 규칙 {', '.join(unknown)}. 내장 규칙: {', '.join(config.BUILTIN_MASK_RULE_NAMES)}"
        )
    protected = [name for name in disabled if name in PROTECTED_MASK_RULES]
    if protected:
        raise ConventionError(
            f"{source}: safe_mode.disabled_rules 의 {', '.join(protected)} 는 자격 증명 규칙이라 끌 수 없습니다. "
            f"끌 수 있는 규칙: {', '.join(n for n in config.BUILTIN_MASK_RULE_NAMES if n not in PROTECTED_MASK_RULES)}"
        )
    return SafeModePolicy(
        exclude=exclude, mask_rules=_parse_mask_rules(data.get("mask_rules", []), source), disabled_rules=disabled, **limits
    )


def _bounded_int(value: Any, key: str, bounds: tuple[int, int], label: str) -> int:
    low, high = bounds
    if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
        raise ConventionError(f"{label} 는 {low}~{high} 사이의 정수여야 합니다 (입력: {value!r})")
    return value


def _parse_mask_rules(value: Any, source: str) -> tuple[MaskRule, ...]:
    label = f"{source}: safe_mode.mask_rules"
    if not isinstance(value, list) or len(value) > MAX_MASK_RULES:
        raise ConventionError(f"{label} 는 최대 {MAX_MASK_RULES}개의 {{\"name\", \"pattern\"}} 객체 목록이어야 합니다.")
    rules: list[MaskRule] = []
    for item in value:
        if not isinstance(item, dict) or set(item) != set(MASK_RULE_KEYS) or not all(isinstance(item[k], str) for k in MASK_RULE_KEYS):
            raise ConventionError(f"{label} 항목은 name, pattern 문자열 두 키를 가진 객체여야 합니다 (입력: {item!r})")
        try:
            rules.append(compile_mask_rule(item["name"], item["pattern"]))
        except ConventionError as exc:
            raise ConventionError(f"{label}: {exc}") from exc
    names = tuple(rule.name for rule in rules)
    _reject_duplicates(names, "safe_mode.mask_rules(name)", source)
    return tuple(rules)


def compile_mask_rule(name: str, pattern: str) -> MaskRule:
    """이름·정규식을 검증해 MaskRule 을 만든다. 내장 규칙 이름과 겹치면 거부한다."""
    if not MASK_NAME_PATTERN.fullmatch(name):
        raise ConventionError(f"마스킹 규칙 이름은 대문자·숫자·밑줄 2~31자여야 합니다 (입력: {name!r})")
    if name in config.BUILTIN_MASK_RULE_NAMES:
        raise ConventionError(f"마스킹 규칙 이름 {name} 은 내장 규칙과 겹칩니다. disabled_rules 로 끄고 다른 이름을 쓰세요.")
    if not pattern or len(pattern) > MAX_MASK_PATTERN_LENGTH:
        raise ConventionError(f"마스킹 규칙 {name} 의 pattern 은 1~{MAX_MASK_PATTERN_LENGTH}자여야 합니다.")
    if NESTED_QUANTIFIER.search(pattern) or BACKREFERENCE.search(pattern):
        raise ConventionError(f"마스킹 규칙 {name} 의 정규식에 중첩 반복((a+)+ 꼴)이나 역참조가 있어 거부합니다. 단순한 패턴으로 바꾸세요.")
    try:
        compiled = re.compile(pattern)
    except re.error as exc:
        raise ConventionError(f"마스킹 규칙 {name} 의 정규식이 잘못되었습니다: {exc}") from exc
    if compiled.search("") or compiled.search(f"[MASKED:{name}]"):
        raise ConventionError(f"마스킹 규칙 {name} 의 정규식은 빈 문자열이나 치환 결과([MASKED:...])에 매치되면 안 됩니다.")
    return MaskRule(name=name, pattern=compiled)


def parse_mask_option(value: str) -> MaskRule:
    """`--mask NAME=REGEX` 옵션 값."""
    name, sep, pattern = value.partition("=")
    if not sep:
        raise ConventionError(f"--mask 값은 NAME=REGEX 형식이어야 합니다 (입력: {value!r})")
    try:
        return compile_mask_rule(name.strip(), pattern)
    except ConventionError as exc:
        raise ConventionError(f"--mask {value!r}: {exc}") from exc


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
        "[safe_mode]",
        f"  max_files        : {conv.safe_mode.max_files}",
        f"  max_lines/file   : {conv.safe_mode.max_lines_per_file}",
        f"  global_max_lines : {conv.safe_mode.global_max_lines} (safe-mode 가 꺼져 있어도 적용)",
        f"  exclude (+내장 {len(config.SAFE_MODE_EXCLUDED_PATTERNS)}개): {_join(conv.safe_mode.exclude)}",
        f"  mask_rules       : {_join(tuple(f'{r.name}={r.pattern.pattern}' for r in conv.safe_mode.mask_rules))}",
        f"  disabled_rules   : {_join(conv.safe_mode.disabled_rules)}",
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
        "safe_mode": {
            "max_files": config.SAFE_MODE_MAX_FILES,
            "max_lines_per_file": config.SAFE_MODE_MAX_LINES_PER_FILE,
            "global_max_lines": config.GLOBAL_MAX_DIFF_LINES,
            "exclude": [],
            "mask_rules": [],
            "disabled_rules": [],
        },
    }
    return json.dumps(data, ensure_ascii=False, indent=2) + "\n"
