"""safe-mode: 민감정보 마스킹, 파일 제외, 전송량 제한."""

from __future__ import annotations

import re
from dataclasses import dataclass
from fnmatch import fnmatch
from pathlib import PurePosixPath

from . import config
from .records import SanitizedDiff

MASKED_PREFIX = "[MASKED:"
MASK_RULES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("PRIVATE_KEY", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----")),
    ("ANTHROPIC_KEY", re.compile(r"sk-ant-[A-Za-z0-9_\-]{20,}")),
    ("OPENAI_KEY", re.compile(r"sk-[A-Za-z0-9]{20,}")),
    ("AWS_KEY", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("GITHUB_TOKEN", re.compile(r"gh[pousr]_[A-Za-z0-9]{36,}")),
    ("JWT", re.compile(r"eyJ[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+")),
    (
        # 키 이름(DB_PASSWORD, access_token, "apiKey" 등)은 남기고 값만 가린다.
        "GENERIC_SECRET",
        re.compile(
            r"(?i)([A-Za-z0-9_\-]*(?:api[_-]?key|secret|token|passw(?:or)?d)[A-Za-z0-9_\-]*)"
            r"([\"']?\s*[:=]\s*)[\"']?(?!\[MASKED:)([^\s\"']{8,})"
        ),
    ),
    ("EMAIL", re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")),
    ("PHONE_KR", re.compile(r"\b01[016789]-?\d{3,4}-?\d{4}\b")),
)
DIFF_HEADER_PREFIX = "diff --git "


@dataclass(frozen=True)
class FileDiff:
    path: str
    text: str

    @property
    def line_count(self) -> int:
        return self.text.count("\n")


def _path_from_header(header: str) -> str:
    """`diff --git a/x b/y` 에서 y 를 꺼낸다. git 이 경로를 따옴표로 감싼 경우도 처리한다."""
    rest = header[len(DIFF_HEADER_PREFIX):].strip()
    marker = ' b/' if ' b/' in rest else ' "b/'
    index = rest.rfind(marker)
    path = rest[index + len(marker):] if index >= 0 else rest
    return path.strip().strip('"')


def split_diff(diff_text: str) -> tuple[FileDiff, ...]:
    """diff 전체를 파일 단위 조각으로 나눈다."""
    chunks: list[FileDiff] = []
    current_path, current_lines = "", []
    for line in diff_text.splitlines(keepends=True):
        if line.startswith(DIFF_HEADER_PREFIX):
            if current_lines:
                chunks.append(FileDiff(current_path, "".join(current_lines)))
            current_path, current_lines = _path_from_header(line), [line]
        else:
            current_lines.append(line)
    if current_lines:
        chunks.append(FileDiff(current_path, "".join(current_lines)))
    return tuple(chunks)


def is_excluded(path: str, patterns: tuple[str, ...] = config.SAFE_MODE_EXCLUDED_PATTERNS) -> bool:
    name = PurePosixPath(path).name
    return any(fnmatch(name, p) or fnmatch(path, p) for p in patterns)


def _replacement(match: re.Match[str], rule_name: str) -> str:
    if rule_name == "GENERIC_SECRET":
        return f"{match.group(1)}{match.group(2)}{MASKED_PREFIX}{rule_name}]"
    return f"{MASKED_PREFIX}{rule_name}]"


def mask_secrets(text: str) -> tuple[str, int]:
    """알려진 비밀값 형태를 치환하고 치환 건수를 돌려준다."""
    total = 0
    for name, pattern in MASK_RULES:
        text, count = pattern.subn(lambda m, n=name: _replacement(m, n), text)
        total += count
    return text, total


def truncate_lines(text: str, max_lines: int) -> tuple[str, int]:
    """max_lines 를 넘는 부분을 잘라 내고 잘린 줄 수를 돌려준다."""
    lines = text.splitlines(keepends=True)
    if len(lines) <= max_lines:
        return text, 0
    omitted = len(lines) - max_lines
    return "".join(lines[:max_lines]) + f"... ({omitted}줄 생략)\n", omitted


def sanitize(
    diff_text: str,
    *,
    safe_mode: bool,
    max_files: int = config.SAFE_MODE_MAX_FILES,
    max_lines_per_file: int = config.SAFE_MODE_MAX_LINES_PER_FILE,
    global_max_lines: int = config.GLOBAL_MAX_DIFF_LINES,
    excluded_patterns: tuple[str, ...] = config.SAFE_MODE_EXCLUDED_PATTERNS,
) -> SanitizedDiff:
    """safe-mode 정책을 적용한 diff 를 돌려준다. 전체 줄 수 상한은 항상 적용한다.

    마스킹은 절단보다 먼저 한다. 절단으로 PEM 블록의 END 표식이 잘리면 정규식이 못 잡기 때문이다.
    """
    if not safe_mode:
        text, truncated = truncate_lines(diff_text, global_max_lines)
        return SanitizedDiff(text=text, safe_mode=False, truncated_lines=truncated)

    kept: list[str] = []
    omitted: list[str] = []
    masked_total = 0
    truncated_total = 0
    for chunk in split_diff(diff_text):
        if is_excluded(chunk.path, excluded_patterns) or len(kept) >= max_files:
            omitted.append(chunk.path)
            continue
        masked, masked_count = mask_secrets(chunk.text)
        text, truncated = truncate_lines(masked, max_lines_per_file)
        masked_total += masked_count
        truncated_total += truncated
        kept.append(text)

    joined = "".join(kept)
    if omitted:
        joined += "\n[생략된 파일: " + ", ".join(omitted) + "]\n"
    final_text, truncated = truncate_lines(joined, global_max_lines)
    return SanitizedDiff(
        text=final_text,
        safe_mode=True,
        masked_count=masked_total,
        omitted_files=tuple(omitted),
        truncated_lines=truncated_total + truncated,
    )
