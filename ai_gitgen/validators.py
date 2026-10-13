"""생성된 커밋/PR 텍스트의 파싱, 규칙 검증, 후처리."""

from __future__ import annotations

import re
from dataclasses import replace

from . import config
from .errors import OutputParseError
from .records import CommitMessage, PullRequestDraft, ValidationReport

COMMIT_TITLE_PATTERN = re.compile(r"^(?:%s)(?:\([^)]+\))?!?: \S" % "|".join(config.COMMIT_TYPES))
FENCE_LINE_PATTERN = re.compile(r"^\s*```")
SECTION_PATTERN = re.compile(r"^##\s+(%s)\s*$" % "|".join(re.escape(s) for s in config.PR_REQUIRED_SECTIONS), re.MULTILINE)
BULLET_PATTERN = re.compile(r"^\s*[-*] \S", re.MULTILINE)
TITLE_LABEL_PATTERN = re.compile(r"^\s*(?:#+\s*|(?:PR\s*)?(?:Title|제목)\s*[:：]\s*)", re.IGNORECASE)


def strip_fences(text: str) -> str:
    """코드 펜스 줄(```)만 제거한다."""
    return "\n".join(line for line in text.splitlines() if not FENCE_LINE_PATTERN.match(line)).strip("\n")


def _split_title_body(text: str) -> tuple[str, str]:
    """첫 줄과 나머지. 빈 출력은 빈 제목으로 돌려주어 검증 단계가 재생성을 결정하게 한다."""
    lines = text.strip().splitlines()
    if not lines:
        return "", ""
    title = lines[0].strip()
    body = "\n".join(lines[1:]).strip("\n")
    return title, body


def ensure_title(title: str) -> None:
    """재생성까지 끝난 뒤에도 제목이 없으면 더 할 수 있는 일이 없다."""
    if not title.strip():
        raise OutputParseError("모델 출력에서 제목을 찾을 수 없습니다. --max-tokens 를 늘리거나 다시 시도하세요.")


def parse_commit_text(text: str) -> CommitMessage:
    """첫 `type:` 형식 줄을 제목으로 삼고, 그 앞의 서두는 버린다."""
    cleaned = strip_fences(text)
    lines = cleaned.splitlines()
    start = next((i for i, line in enumerate(lines) if COMMIT_TITLE_PATTERN.match(line.strip())), None)
    if start is not None:
        cleaned = "\n".join(lines[start:])
    title, body = _split_title_body(cleaned)
    return CommitMessage(title=title, body=body)


def parse_pr_text(text: str) -> PullRequestDraft:
    """첫 줄을 제목으로, 나머지를 본문으로. 제목의 라벨/헤더 기호는 제거."""
    cleaned = strip_fences(text)
    lines = cleaned.splitlines()
    start = next((i for i, line in enumerate(lines) if line.strip()), 0)
    title, body = _split_title_body("\n".join(lines[start:]))
    return PullRequestDraft(title=TITLE_LABEL_PATTERN.sub("", title).strip(), body=body)


def truncate_title(title: str, limit: int) -> tuple[str, str]:
    """limit 안에서 단어 경계로 자른다. (잘린 제목, 나머지) 를 돌려준다."""
    if len(title) <= limit:
        return title, ""
    cut = title.rfind(" ", 0, limit + 1)
    if cut <= limit // 2:
        cut = limit
    return title[:cut].rstrip(" ,;:"), title[cut:].strip()


def validate_commit(message: CommitMessage) -> ValidationReport:
    problems: list[str] = []
    title = message.title
    if not title:
        problems.append("제목이 비어 있습니다.")
    if len(title) > config.COMMIT_TITLE_HARD_LIMIT:
        problems.append(f"제목이 {config.COMMIT_TITLE_HARD_LIMIT}자를 넘습니다 ({len(title)}자).")
    if title.endswith("."):
        problems.append("제목 끝에 마침표가 있습니다.")
    if title and not COMMIT_TITLE_PATTERN.match(title):
        problems.append("제목이 `type: 설명` 형식이 아닙니다.")
    if message.body and not BULLET_PATTERN.search(message.body):
        problems.append("본문에 `- ` 불릿이 없습니다.")
    has_valid_title = bool(title) and bool(COMMIT_TITLE_PATTERN.match(title))
    return ValidationReport(is_valid=not problems, problems=tuple(problems), needs_regeneration=not has_valid_title)


def polish_commit(message: CommitMessage) -> CommitMessage:
    """기계적으로 고칠 수 있는 결함을 고친 새 객체를 돌려준다."""
    title = message.title.strip().rstrip(".").strip()
    title, remainder = truncate_title(title, config.COMMIT_TITLE_HARD_LIMIT)
    body_lines = [line.rstrip() for line in message.body.splitlines() if line.strip()]
    if remainder:
        body_lines = [f"- {remainder}", *body_lines]
    body = "\n".join(_as_bullet(line) for line in body_lines)
    return replace(message, title=title, body=body)


def _as_bullet(line: str) -> str:
    stripped = line.strip()
    return stripped if stripped.startswith("- ") else f"- {stripped.lstrip('-* ').strip()}"


def split_sections(body: str) -> dict[str, str]:
    parts = SECTION_PATTERN.split(body)
    return {parts[i]: parts[i + 1] for i in range(1, len(parts) - 1, 2)}


def missing_sections(body: str) -> tuple[str, ...]:
    sections = split_sections(body)
    return tuple(
        name
        for name in config.PR_REQUIRED_SECTIONS
        if name not in sections or not BULLET_PATTERN.search(sections[name])
    )


def validate_pr(draft: PullRequestDraft) -> ValidationReport:
    problems: list[str] = []
    if not draft.title:
        problems.append("PR 제목이 비어 있습니다.")
    if len(draft.title) > config.PR_TITLE_HARD_LIMIT:
        problems.append(f"PR 제목이 {config.PR_TITLE_HARD_LIMIT}자를 넘습니다 ({len(draft.title)}자).")
    missing = missing_sections(draft.body)
    for name in missing:
        if f"## {name}" in draft.body:
            problems.append(f'"## {name}" 섹션에 `- ` 불릿이 없습니다.')
        else:
            problems.append(f'"## {name}" 섹션이 없습니다.')
    return ValidationReport(is_valid=not problems, problems=tuple(problems), needs_regeneration=bool(missing) or not draft.title)


def polish_pr(draft: PullRequestDraft) -> PullRequestDraft:
    """제목 길이를 맞추고, 빠진 섹션은 자리 표시자로 채운다."""
    title, _ = truncate_title(draft.title.strip().rstrip("."), config.PR_TITLE_HARD_LIMIT)
    sections = split_sections(draft.body)
    rebuilt: list[str] = []
    for name in config.PR_REQUIRED_SECTIONS:
        content = sections.get(name, "").strip("\n")
        if not BULLET_PATTERN.search(content):
            extra = "\n".join(f"- {line.strip()}" for line in content.splitlines() if line.strip())
            content = extra or config.PLACEHOLDER_BULLET
        rebuilt.append(f"## {name}\n{content}")
    return PullRequestDraft(title=title, body="\n\n".join(rebuilt) + "\n")
