"""생성된 커밋/PR 텍스트의 파싱, 규칙 검증, 후처리.

모든 함수는 컨벤션(기본값: 설정 파일 없음)을 받아 허용 type, 스코프 정책, 제목 길이, PR 섹션을 그 값으로 판단한다.
"""

from __future__ import annotations

import functools
import re
from dataclasses import replace

from . import config
from .convention import DEFAULT_CONVENTION, Convention
from .errors import OutputParseError
from .records import CommitMessage, PullRequestDraft, ValidationReport

FENCE_LINE_PATTERN = re.compile(r"^\s*```")
BULLET_PATTERN = re.compile(r"^\s*[-*] \S", re.MULTILINE)
TITLE_LABEL_PATTERN = re.compile(r"^\s*(?:#+\s*|(?:PR\s*)?(?:Title|제목)\s*[:：]\s*)", re.IGNORECASE)
SCOPE_PATTERN = re.compile(r"^(?P<type>[a-z][a-z0-9-]*)\((?P<scope>[^)]+)\)(?P<bang>!?): ")
FOOTER_RULE = "---"
TEST_SECTION = "How to Test"


@functools.lru_cache(maxsize=8)
def commit_title_pattern(types: tuple[str, ...]) -> re.Pattern[str]:
    """`type(scope)!: 설명` 제목 패턴. 허용 type 목록마다 한 번만 컴파일한다."""
    return re.compile(r"^(?:%s)(?:\([^)]+\))?!?: \S" % "|".join(re.escape(t) for t in types))


@functools.lru_cache(maxsize=8)
def section_pattern(sections: tuple[str, ...]) -> re.Pattern[str]:
    """`## 섹션` 헤더 줄 패턴. 섹션 목록마다 한 번만 컴파일한다."""
    return re.compile(r"^##\s+(%s)\s*$" % "|".join(re.escape(s) for s in sections), re.MULTILINE)


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


def parse_commit_text(text: str, convention: Convention = DEFAULT_CONVENTION) -> CommitMessage:
    """첫 `type:` 형식 줄을 제목으로 삼고, 그 앞의 서두는 버린다."""
    pattern = commit_title_pattern(convention.commit.types)
    cleaned = strip_fences(text)
    lines = cleaned.splitlines()
    start = next((i for i, line in enumerate(lines) if pattern.match(line.strip())), None)
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


def _scope_problem(title: str, policy: str) -> tuple[str, bool]:
    """스코프 정책 위반 메시지와 재생성 필요 여부. 금지는 후처리로 지울 수 있고, 필수는 지어낼 수 없어 재생성한다."""
    has_scope = bool(SCOPE_PATTERN.match(title))
    if policy == "forbidden" and has_scope:
        return "제목에 스코프가 있습니다. 이 저장소는 `type: 설명` 형식만 씁니다.", False
    if policy == "required" and not has_scope:
        return "제목에 스코프가 없습니다 (`type(scope): 설명` 필수).", True
    return "", False


def validate_commit(message: CommitMessage, convention: Convention = DEFAULT_CONVENTION) -> ValidationReport:
    rules = convention.commit
    problems: list[str] = []
    title = message.title
    has_valid_format = bool(title) and bool(commit_title_pattern(rules.types).match(title))
    if not title:
        problems.append("제목이 비어 있습니다.")
    if len(title) > rules.title_hard_limit:
        problems.append(f"제목이 {rules.title_hard_limit}자를 넘습니다 ({len(title)}자).")
    if title.endswith("."):
        problems.append("제목 끝에 마침표가 있습니다.")
    if title and not has_valid_format:
        problems.append(f"제목이 `type: 설명` 형식이 아닙니다 (type 은 {', '.join(rules.types)} 중 하나).")
    scope_problem, scope_needs_regeneration = _scope_problem(title, rules.scope) if has_valid_format else ("", False)
    if scope_problem:
        problems.append(scope_problem)
    if message.body and not BULLET_PATTERN.search(message.body):
        problems.append("본문에 `- ` 불릿이 없습니다.")
    needs_regeneration = not has_valid_format or scope_needs_regeneration
    return ValidationReport(is_valid=not problems, problems=tuple(problems), needs_regeneration=needs_regeneration)


def strip_scope(title: str) -> str:
    """`type(scope)!: 설명` → `type!: 설명`."""
    return SCOPE_PATTERN.sub(lambda m: f"{m.group('type')}{m.group('bang')}: ", title, count=1)


def polish_commit(message: CommitMessage, convention: Convention = DEFAULT_CONVENTION) -> CommitMessage:
    """기계적으로 고칠 수 있는 결함을 고친 새 객체를 돌려준다."""
    rules = convention.commit
    title = message.title.strip().rstrip(".").strip()
    if rules.scope == "forbidden":
        title = strip_scope(title)
    title, remainder = truncate_title(title, rules.title_hard_limit)
    body_lines = [line.rstrip() for line in message.body.splitlines() if line.strip()]
    if remainder:
        body_lines = [f"- {remainder}", *body_lines]
    body = "\n".join(_as_bullet(line) for line in body_lines)
    return replace(message, title=title, body=body)


def _as_bullet(line: str) -> str:
    stripped = line.strip()
    return stripped if stripped.startswith("- ") else f"- {stripped.lstrip('-* ').strip()}"


def _known_sections(convention: Convention) -> tuple[str, ...]:
    """모델이 써야 하는 섹션 + 도구가 붙이는 체크리스트 섹션(설정된 경우)."""
    sections = convention.pr.sections
    if convention.pr.checklist and config.CHECKLIST_SECTION not in sections:
        sections += (config.CHECKLIST_SECTION,)
    return sections


def split_sections(body: str, convention: Convention = DEFAULT_CONVENTION) -> dict[str, str]:
    parts = section_pattern(_known_sections(convention)).split(body)
    return {parts[i]: parts[i + 1] for i in range(1, len(parts) - 1, 2)}


def missing_sections(body: str, convention: Convention = DEFAULT_CONVENTION) -> tuple[str, ...]:
    sections = split_sections(body, convention)
    return tuple(
        name for name in convention.pr.sections if name not in sections or not BULLET_PATTERN.search(sections[name])
    )


def _test_command_missing(body: str, convention: Convention) -> bool:
    """컨벤션의 테스트 명령이 How to Test 섹션에 들어 있지 않으면 True."""
    command = convention.pr.test_command
    if not command or TEST_SECTION not in convention.pr.sections:
        return False
    return command not in split_sections(body, convention).get(TEST_SECTION, "")


def validate_pr(draft: PullRequestDraft, convention: Convention = DEFAULT_CONVENTION) -> ValidationReport:
    limit = convention.pr.title_limit
    problems: list[str] = []
    if not draft.title:
        problems.append("PR 제목이 비어 있습니다.")
    if len(draft.title) > limit:
        problems.append(f"PR 제목이 {limit}자를 넘습니다 ({len(draft.title)}자).")
    if convention.commit.scope == "forbidden" and SCOPE_PATTERN.match(draft.title):
        problems.append("PR 제목에 스코프가 있습니다. 이 저장소는 `type: 설명` 형식만 씁니다.")
    missing = missing_sections(draft.body, convention)
    for name in missing:
        if f"## {name}" in draft.body:
            problems.append(f'"## {name}" 섹션에 `- ` 불릿이 없습니다.')
        else:
            problems.append(f'"## {name}" 섹션이 없습니다.')
    if _test_command_missing(draft.body, convention):
        problems.append(f'"## {TEST_SECTION}" 에 컨벤션 테스트 명령 `{convention.pr.test_command}` 이 없습니다.')
    return ValidationReport(is_valid=not problems, problems=tuple(problems), needs_regeneration=bool(missing) or not draft.title)


def _strip_footer(body: str, footer: str) -> str:
    """이미 붙어 있는 푸터(`---` 구분선 + 푸터 한 줄)만 떼어 내 두 번 붙지 않게 한다. 본문 끝 문장이 우연히 같아도 건드리지 않는다."""
    if not footer:
        return body
    pattern = re.compile(r"\n+%s[ \t]*\n%s\s*\Z" % (re.escape(FOOTER_RULE), re.escape(footer)))
    return pattern.sub("", body.rstrip())


def _with_test_command(content: str, convention: Convention) -> str:
    """How to Test 첫 줄에 컨벤션 테스트 명령 불릿을 보장한다."""
    command = convention.pr.test_command
    if not command or command in content:
        return content
    return f"- 전체 테스트: `{command}`\n{content}".rstrip("\n")


def polish_pr(draft: PullRequestDraft, convention: Convention = DEFAULT_CONVENTION) -> PullRequestDraft:
    """제목 길이·스코프를 맞추고, 빠진 섹션은 자리 표시자로 채우고, 컨벤션의 테스트 명령·체크리스트·푸터를 붙인다."""
    pr = convention.pr
    title = draft.title.strip().rstrip(".")
    if convention.commit.scope == "forbidden":
        title = strip_scope(title)
    title, _ = truncate_title(title, pr.title_limit)
    sections = split_sections(_strip_footer(draft.body, pr.footer), convention)
    rebuilt: list[str] = []
    for name in pr.sections:
        content = sections.get(name, "").strip("\n")
        if not BULLET_PATTERN.search(content):
            extra = "\n".join(f"- {line.strip()}" for line in content.splitlines() if line.strip())
            content = extra or config.PLACEHOLDER_BULLET
        if name == TEST_SECTION:
            content = _with_test_command(content, convention)
        rebuilt.append(f"## {name}\n{content}")
    if pr.checklist:  # 모델이 체크리스트를 썼더라도 팀 항목으로 고정한다 (설정 검증이 sections 와의 중복을 막는다)
        rebuilt.append(f"## {config.CHECKLIST_SECTION}\n" + "\n".join(f"- [ ] {item}" for item in pr.checklist))
    if pr.footer:
        rebuilt.append(f"{FOOTER_RULE}\n{pr.footer}")
    return PullRequestDraft(title=title, body="\n\n".join(rebuilt) + "\n")
