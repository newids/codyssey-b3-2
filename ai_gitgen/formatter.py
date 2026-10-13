"""로그(stderr)와 결과 블록(stdout) 출력."""

from __future__ import annotations

import sys
import unicodedata
from typing import TextIO

from .records import CommitMessage, PullRequestDraft, RegistryEntry

COMMIT_HEADER = "--- Commit Message ---"
PR_TITLE_HEADER = "--- PR Title ---"
PR_BODY_HEADER = "--- PR Body ---"


def _log(level: str, message: str, stream: TextIO | None = None) -> None:
    out = stream or sys.stderr
    first, *rest = message.split("\n")
    out.write(f"[{level}] {first}\n")
    for line in rest:
        out.write(f"{line}\n")
    out.flush()


def info(message: str) -> None:
    _log("INFO", message)


def warn(message: str) -> None:
    _log("WARN", message)


def error(message: str) -> None:
    _log("ERROR", message)


def done(message: str) -> None:
    _log("DONE", message)


def format_int(value: int) -> str:
    return f"{value:,}"


def render_commit(message: CommitMessage) -> str:
    rule = "-" * len(COMMIT_HEADER)
    return f"{COMMIT_HEADER}\n{message.render()}{rule}\n"


def render_pr(draft: PullRequestDraft) -> str:
    rule = "-" * len(PR_BODY_HEADER)
    return f"{PR_TITLE_HEADER}\n{draft.title}\n\n{PR_BODY_HEADER}\n{draft.body.rstrip()}\n{rule}\n"


def render_prompt_preview(system: str, user: str) -> str:
    return f"--- System Prompt ---\n{system}\n\n--- User Prompt ---\n{user}\n---------------------\n"


def display_width(text: str) -> int:
    """터미널 표시 폭. 한글 등 동아시아 전각 문자는 2칸."""
    return sum(2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1 for ch in text)


def pad(text: str, width: int) -> str:
    return text + " " * max(0, width - display_width(text))


def render_registry_table(entries: tuple[RegistryEntry, ...], path: str) -> str:
    headers = ("제공자", "모델", "출처", "사유", "최근", "횟수")
    rows = [(e.provider, e.model, e.source, _clip(e.reason, 40), e.last_seen, e.count) for e in entries]
    if not rows:
        return f"레지스트리 파일: {path}\n(등록된 모델 없음)\n"
    widths = [max(display_width(h), *(display_width(r[i]) for r in rows)) for i, h in enumerate(headers)]
    line = "  ".join(pad(h, w) for h, w in zip(headers, widths)).rstrip()
    body = "\n".join("  ".join(pad(c, w) for c, w in zip(r, widths)).rstrip() for r in rows)
    return f"레지스트리 파일: {path}\n{line}\n{body}\n"


def _clip(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[: limit - 3] + "..."
