"""git status / git diff 결과를 프로그램 입력으로 바꾼다."""

from __future__ import annotations

import subprocess
from pathlib import Path

from .errors import GitCommandError, NotGitRepositoryError
from .records import ChangedFile, GitChanges

NOT_A_REPOSITORY_MARKER = "not a git repository"
UNTRACKED_FILE_MAX_BYTES = 200_000
DIFF_EXIT_CODES = (0, 1)  # git diff --no-index 는 차이가 있으면 1 을 돌려준다

# 사용자 설정(색상, 외부 diff 도구, 경로 따옴표 처리)에 영향받지 않도록 고정한다.
GIT_GLOBAL_OPTIONS = ("-c", "core.quotepath=false", "-c", "color.ui=never")
DIFF_OPTIONS = ("--no-color", "--no-ext-diff", "--no-textconv", "--src-prefix=a/", "--dst-prefix=b/")
RENAME_OR_COPY = ("R", "C")


def run_git(*args: str, cwd: str | Path | None = None, ok_codes: tuple[int, ...] = (0,)) -> str:
    """git 명령을 실행해 표준 출력을 돌려준다. 실패는 사용자용 예외로 바꾼다."""
    try:
        completed = subprocess.run(
            ["git", *GIT_GLOBAL_OPTIONS, *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            cwd=str(cwd) if cwd else None,
        )
    except FileNotFoundError as exc:
        raise GitCommandError("git 실행 파일을 찾을 수 없습니다. git 이 설치되어 있는지 확인하세요.") from exc
    if completed.returncode not in ok_codes:
        stderr = (completed.stderr or "").strip()
        if NOT_A_REPOSITORY_MARKER in stderr.lower():
            raise NotGitRepositoryError(
                "Git 저장소가 아닙니다. Git 이 초기화된 프로젝트 루트 디렉토리에서 실행하세요."
            )
        raise GitCommandError(f"git {' '.join(args)} 실패: {stderr or '알 수 없는 오류'}")
    return completed.stdout


def ensure_repository_root(cwd: str | Path | None = None) -> Path:
    """현재 디렉토리가 저장소 루트인지 확인하고 루트 경로를 돌려준다."""
    current = Path(cwd or Path.cwd()).resolve()
    toplevel = Path(run_git("rev-parse", "--show-toplevel", cwd=current).strip()).resolve()
    if toplevel != current:
        raise NotGitRepositoryError(
            f"저장소 루트에서 실행해야 합니다. 현재: {current}\n루트로 이동: cd \"{toplevel}\""
        )
    return toplevel


def parse_porcelain(text: str) -> tuple[ChangedFile, ...]:
    """`git status --porcelain -z` 출력(NUL 구분)을 파일 목록으로 바꾼다.

    이름 변경/복사 항목은 `XY new\\0old\\0` 로 두 토큰을 차지하므로 원래 경로 토큰은 건너뛴다.
    """
    tokens = [t for t in text.split("\0")]
    files: list[ChangedFile] = []
    index = 0
    while index < len(tokens):
        entry = tokens[index]
        index += 1
        if len(entry) < 4:
            continue
        status, path = entry[:2], entry[3:]
        if status[0] in RENAME_OR_COPY or status[1] in RENAME_OR_COPY:
            index += 1  # 원래 경로는 쓰지 않는다
        files.append(ChangedFile(path=path, status=status))
    return tuple(files)


def current_branch(root: Path) -> str:
    """브랜치 이름. 커밋이 없는 새 저장소에서도 동작한다."""
    name = run_git("branch", "--show-current", cwd=root).strip()
    return name or "(detached)"


def untracked_diff(root: Path, paths: tuple[str, ...]) -> str:
    """추적되지 않은 새 파일을 /dev/null 과 비교해 diff 형태로 만든다. 큰 파일과 바이너리는 건너뛴다."""
    parts: list[str] = []
    for path in paths:
        target = root / path
        if not target.is_file() or target.stat().st_size > UNTRACKED_FILE_MAX_BYTES:
            continue
        output = run_git(
            "diff", *DIFF_OPTIONS, "--no-index", "--", "/dev/null", path, cwd=root, ok_codes=DIFF_EXIT_CODES
        )
        if output and "Binary files" not in output.splitlines()[-1]:
            parts.append(output)
    return "".join(parts)


def _ref_exists(root: Path, ref: str) -> bool:
    try:
        run_git("rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}", cwd=root)
    except GitCommandError:
        return False
    return True


def detect_base_branch(root: Path, requested: str | None = None) -> str | None:
    """PR 비교 기준. --base 가 있으면 그것, 없으면 origin/HEAD → main → master 순서로 찾는다."""
    if requested:
        if not _ref_exists(root, requested):
            raise GitCommandError(f"기준 브랜치를 찾을 수 없습니다: {requested}\n       --base 값을 확인하세요.")
        return requested
    try:
        origin_head = run_git("symbolic-ref", "--short", "-q", "refs/remotes/origin/HEAD", cwd=root).strip()
    except GitCommandError:
        origin_head = ""
    for candidate in (origin_head, "main", "master"):
        if candidate and _ref_exists(root, candidate):
            return candidate
    return None


def parse_name_status(text: str) -> tuple[ChangedFile, ...]:
    """`git diff --name-status -z` 출력. 이름 변경/복사는 `R100\\0old\\0new\\0` 형태."""
    tokens = text.split("\0")
    files: list[ChangedFile] = []
    index = 0
    while index < len(tokens):
        status = tokens[index]
        index += 1
        if not status:
            continue
        path = tokens[index] if index < len(tokens) else ""
        index += 1
        if status[0] in RENAME_OR_COPY and index < len(tokens):
            path = tokens[index]
            index += 1
        files.append(ChangedFile(path=path, status=f"{status[0]} ", is_committed=True))
    return tuple(files)


def branch_changes(root: Path, base: str) -> tuple[tuple[ChangedFile, ...], str, tuple[str, ...]]:
    """기준 브랜치 이후 커밋들의 파일 목록, diff, 커밋 제목."""
    range_spec = f"{base}...HEAD"
    files = parse_name_status(run_git("diff", "--name-status", "-z", range_spec, cwd=root))
    diff_text = run_git("diff", *DIFF_OPTIONS, range_spec, cwd=root)
    subjects = tuple(
        line for line in run_git("log", "--format=%s", f"{base}..HEAD", cwd=root).splitlines() if line.strip()
    )
    return files, diff_text, subjects


def collect_changes(
    cwd: str | Path | None = None, *, include_branch: bool = False, base: str | None = None
) -> GitChanges:
    """status, diff(작업 트리 + 스테이징 + 새 파일), 브랜치를 한 번에 수집한다.

    include_branch 가 참이면(pr 명령) 기준 브랜치 이후 커밋된 변경도 함께 모은다.
    """
    root = ensure_repository_root(cwd)
    files = parse_porcelain(run_git("status", "--porcelain", "-z", "--untracked-files=all", cwd=root))
    untracked = tuple(f.path for f in files if f.is_untracked)
    diff_text = (
        run_git("diff", *DIFF_OPTIONS, cwd=root)
        + run_git("diff", *DIFF_OPTIONS, "--cached", cwd=root)
        + untracked_diff(root, untracked)
    )
    branch = current_branch(root)
    base_branch = detect_base_branch(root, base) if include_branch else None
    if base_branch and base_branch != branch:
        committed_files, committed_diff, subjects = branch_changes(root, base_branch)
        seen = {f.path for f in files}
        files = tuple(f for f in committed_files if f.path not in seen) + files
        return GitChanges(
            branch=branch,
            files=files,
            diff_text=committed_diff + diff_text,
            base_branch=base_branch,
            commit_subjects=subjects,
        )
    return GitChanges(branch=branch, files=files, diff_text=diff_text)
