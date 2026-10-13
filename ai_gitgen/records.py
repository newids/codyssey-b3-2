"""모듈 사이를 오가는 불변 데이터 구조."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ChangedFile:
    path: str
    status: str  # porcelain 의 XY 두 글자

    @property
    def is_untracked(self) -> bool:
        return self.status == "??"


@dataclass(frozen=True)
class GitChanges:
    branch: str
    files: tuple[ChangedFile, ...]
    diff_text: str

    @property
    def line_count(self) -> int:
        return self.diff_text.count("\n")

    @property
    def is_empty(self) -> bool:
        return not self.files and not self.diff_text.strip()

    @property
    def untracked_paths(self) -> tuple[str, ...]:
        return tuple(f.path for f in self.files if f.is_untracked)


@dataclass(frozen=True)
class SanitizedDiff:
    text: str
    safe_mode: bool
    masked_count: int = 0
    omitted_files: tuple[str, ...] = ()
    truncated_lines: int = 0


@dataclass(frozen=True)
class Prompt:
    system: str
    user: str


@dataclass(frozen=True)
class GenerationSettings:
    provider: str
    model: str
    temperature: float | None
    max_tokens: int


@dataclass(frozen=True)
class GenerationResult:
    text: str
    input_tokens: int
    output_tokens: int
    stop_reason: str  # end_turn | max_tokens | refusal | 기타


@dataclass(frozen=True)
class CommitMessage:
    title: str
    body: str = ""

    def render(self) -> str:
        return f"{self.title}\n\n{self.body}".rstrip() + "\n" if self.body else self.title + "\n"


@dataclass(frozen=True)
class PullRequestDraft:
    title: str
    body: str


@dataclass(frozen=True)
class ValidationReport:
    is_valid: bool
    problems: tuple[str, ...] = field(default_factory=tuple)
    needs_regeneration: bool = False


@dataclass(frozen=True)
class UnsupportedModelRecord:
    reason: str
    first_seen: str
    last_seen: str
    count: int = 1


@dataclass(frozen=True)
class RegistryEntry:
    provider: str
    model: str
    source: str  # 내장 목록 | 학습 | 제외(내장)
    reason: str = "-"
    last_seen: str = "-"
    count: str = "-"
