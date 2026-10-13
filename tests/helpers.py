"""테스트 공용 도구: 임시 git 저장소, 가짜 AI 클라이언트."""

from __future__ import annotations

import subprocess
from pathlib import Path

from ai_gitgen.errors import AIRequestError
from ai_gitgen.records import ChangedFile, GenerationResult, GenerationSettings, GitChanges

SAMPLE_DIFF = """diff --git a/app.py b/app.py
index 1111111..2222222 100644
--- a/app.py
+++ b/app.py
@@ -1,2 +1,3 @@
 def main():
-    print("hi")
+    print("hello")
+    return 0
"""

GOOD_COMMIT = "feat(app): 인사 문구 변경 및 반환값 추가\n\n- app.py 의 출력 문구를 hello 로 변경\n- main 이 0 을 반환"
GOOD_PR = (
    "feat: 인사 문구 변경\n\n## Why\n- 문구 통일\n\n## What\n- app.py 출력 변경\n\n## How to Test\n- python app.py 실행"
)
PR_MISSING_TEST_SECTION = "feat: 인사 문구 변경\n\n## Why\n- 문구 통일\n\n## What\n- app.py 출력 변경\n"


def git(repo: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args], cwd=repo, capture_output=True, text=True, check=False, encoding="utf-8"
    )
    return completed.stdout


def init_repo(repo: Path) -> None:
    """커밋 하나가 있는 저장소를 만든다."""
    git(repo, "init", "-q", "-b", "main")
    git(repo, "config", "user.email", "test@example.com")
    git(repo, "config", "user.name", "tester")
    (repo / "app.py").write_text('def main():\n    print("hi")\n', encoding="utf-8")
    git(repo, "add", ".")
    git(repo, "commit", "-q", "-m", "init")


def sample_changes(diff: str = SAMPLE_DIFF, untracked: bool = False) -> GitChanges:
    files = (ChangedFile("app.py", " M"),)
    if untracked:
        files += (ChangedFile("notes.md", "??"),)
    return GitChanges(branch="feature/greeting", files=files, diff_text=diff)


def result(text: str, stop_reason: str = "end_turn") -> GenerationResult:
    return GenerationResult(text=text, input_tokens=100, output_tokens=20, stop_reason=stop_reason)


class FakeClient:
    """AIClient 대역. 미리 넣은 응답(또는 예외)을 순서대로 돌려준다."""

    def __init__(self, provider=None, api_key: str = "", timeout: float = 0) -> None:
        self.call_count = 0
        self.settings_seen: list[GenerationSettings] = []
        self.prompts_seen: list[tuple[str, str]] = []
        self.responses: list[GenerationResult | Exception] = list(FakeClient.queue)

    queue: list[GenerationResult | Exception] = []

    def generate(self, system: str, user: str, settings: GenerationSettings) -> GenerationResult:
        self.call_count += 1
        self.settings_seen.append(settings)
        self.prompts_seen.append((system, user))
        if not self.responses:
            raise AIRequestError("가짜 클라이언트에 준비된 응답이 없습니다")
        item = self.responses.pop(0)
        if isinstance(item, BaseException):
            raise item
        return item
