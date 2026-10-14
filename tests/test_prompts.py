import unittest

from ai_gitgen import config, prompts
from ai_gitgen.records import SanitizedDiff
from tests.helpers import SAMPLE_DIFF, sample_changes


# 설정 파일이 없을 때의 프롬프트는 컨벤션 기능 도입 전과 바이트 단위로 같아야 한다 (도입 전 커밋에서 계산한 값)
GOLDEN_COMMIT_SHA256 = "132bd3dcb42ec40096f078326239f371246dd4a0c76ecb143438c4eb8cd11584"
GOLDEN_PR_SHA256 = "1a1d32329122974238ac5eeef2711aab8fd344d279f6443fe3fc3b9148bcf43a"


class SystemPromptTest(unittest.TestCase):
    def test_default_prompts_are_unchanged_by_convention_feature(self) -> None:
        import hashlib

        self.assertEqual(hashlib.sha256(prompts.commit_system_prompt().encode()).hexdigest(), GOLDEN_COMMIT_SHA256)
        self.assertEqual(hashlib.sha256(prompts.pr_system_prompt().encode()).hexdigest(), GOLDEN_PR_SHA256)

    def test_commit_system_contains_rules_with_numbers(self) -> None:
        system = prompts.commit_system_prompt()
        self.assertIn(str(config.COMMIT_TITLE_SOFT_LIMIT), system)
        self.assertIn(str(config.COMMIT_TITLE_HARD_LIMIT), system)
        self.assertIn("feat, fix", system)
        self.assertIn("추측", system)

    def test_pr_system_contains_required_sections(self) -> None:
        system = prompts.pr_system_prompt()
        for name in config.PR_REQUIRED_SECTIONS:
            self.assertIn(f"## {name}", system)
        self.assertIn(str(config.PR_TITLE_HARD_LIMIT), system)


class UserPromptTest(unittest.TestCase):
    def test_user_prompt_includes_context_files_and_diff(self) -> None:
        changes = sample_changes(untracked=True)
        sanitized = SanitizedDiff(text=SAMPLE_DIFF, safe_mode=False)

        prompt = prompts.build_commit_prompt(changes, sanitized, context="인사 문구 통일")

        self.assertIn("브랜치: feature/greeting", prompt.user)
        self.assertIn("변경 파일 수: 2", prompt.user)
        self.assertIn("변경 이유(작성자 제공): 인사 문구 통일", prompt.user)
        self.assertIn("?? notes.md  (새 파일)", prompt.user)
        self.assertIn("<diff>\n" + SAMPLE_DIFF.rstrip("\n") + "\n</diff>", prompt.user)
        self.assertTrue(prompt.user.endswith(prompts.COMMIT_INSTRUCTION))

    def test_safe_mode_and_truncation_notes_are_added(self) -> None:
        sanitized = SanitizedDiff(text="x", safe_mode=True, omitted_files=(".env",), truncated_lines=5)
        prompt = prompts.build_pr_prompt(sample_changes(), sanitized)
        self.assertIn("1개 파일은 이름만 제공됩니다", prompt.user)
        self.assertIn("5줄은 길이 제한으로 생략", prompt.user)
        self.assertTrue(prompt.user.endswith(prompts.PR_INSTRUCTION))

    def test_safe_mode_masks_context_and_file_list(self) -> None:
        changes = sample_changes()
        changes = changes.__class__(branch="fix/dev@example.com", files=changes.files, diff_text="")
        prompt = prompts.build_commit_prompt(
            changes, SanitizedDiff(text="x", safe_mode=True), context="토큰 ghp_abcdefghijklmnopqrstuvwxyz0123456789ABCD 교체"
        )
        self.assertIn("[MASKED:GITHUB_TOKEN]", prompt.user)
        self.assertIn("브랜치: fix/[MASKED:EMAIL]", prompt.user)
        self.assertNotIn("ghp_", prompt.user)

    def test_branch_comparison_and_commit_subjects_are_listed(self) -> None:
        from ai_gitgen.records import ChangedFile, GitChanges

        changes = GitChanges(
            branch="feature/x",
            files=(ChangedFile("a.py", "M ", is_committed=True), ChangedFile("b.py", " M")),
            diff_text="x",
            base_branch="main",
            commit_subjects=("feat: 두 번째", "feat: 첫 번째"),
        )
        prompt = prompts.build_pr_prompt(changes, SanitizedDiff(text="x", safe_mode=False))
        self.assertIn("비교 기준: main...feature/x (커밋 2개 + 미커밋 변경)", prompt.user)
        self.assertIn("  - feat: 두 번째\n  - feat: 첫 번째", prompt.user)
        self.assertIn("M  a.py  (커밋됨)", prompt.user)
        self.assertIn(" M b.py\n", prompt.user)

    def test_no_context_omits_context_line(self) -> None:
        prompt = prompts.build_commit_prompt(sample_changes(), SanitizedDiff(text="x", safe_mode=False), context="  ")
        self.assertNotIn("변경 이유", prompt.user)

    def test_regeneration_prompt_lists_problems_and_previous_output(self) -> None:
        base = prompts.build_pr_prompt(sample_changes(), SanitizedDiff(text="x", safe_mode=False))
        regenerated = prompts.build_regeneration_prompt(base, "이전 출력", ('"## How to Test" 섹션이 없습니다.',))
        self.assertEqual(regenerated.system, base.system)
        self.assertIn("<previous_output>\n이전 출력\n</previous_output>", regenerated.user)
        self.assertIn('- "## How to Test" 섹션이 없습니다.', regenerated.user)


class ConventionPromptTest(unittest.TestCase):
    def _team(self):
        from ai_gitgen.convention import CommitConvention, Convention, PrConvention

        return Convention(
            commit=CommitConvention(types=("feat", "fix", "docs"), scope="forbidden", rules=("파일 이름 뒤 조사는 띄어 쓴다",)),
            pr=PrConvention(
                sections=("Why", "What", "How to Test", "Risks"),
                test_command="python -m unittest discover -s tests -t .",
                rules=("불릿은 존댓말 종결(~했습니다)",),
            ),
            source="/repo/.ai-gitgen.json",
        )

    def test_commit_system_reflects_types_scope_and_rules(self) -> None:
        system = prompts.commit_system_prompt(self._team())
        self.assertIn("feat, fix, docs", system)
        self.assertNotIn("refactor", system.split("[제목 규칙]")[1].split("[본문 규칙]")[0])
        self.assertIn("스코프를 쓰지 마십시오", system)
        self.assertIn("- 파일 이름 뒤 조사는 띄어 쓴다", system)
        self.assertIn("[팀 컨벤션]", system)

    def test_required_scope_rule_is_stated(self) -> None:
        from ai_gitgen.convention import CommitConvention, Convention

        system = prompts.commit_system_prompt(Convention(commit=CommitConvention(scope="required")))
        self.assertIn("반드시 `type(scope): 설명` 형식", system)

    def test_pr_system_lists_custom_sections_and_test_command(self) -> None:
        system = prompts.pr_system_prompt(self._team())
        self.assertIn("## Risks", system)
        self.assertIn("네 섹션", system)
        self.assertIn("python -m unittest discover -s tests -t .", system)
        self.assertIn("- 불릿은 존댓말 종결(~했습니다)", system)

    def test_default_convention_has_no_team_block(self) -> None:
        self.assertNotIn("[팀 컨벤션]", prompts.commit_system_prompt())
        self.assertNotIn("[팀 컨벤션]", prompts.pr_system_prompt())
        self.assertNotIn("테스트 명령", prompts.pr_system_prompt())


if __name__ == "__main__":
    unittest.main()
