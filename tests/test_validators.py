import unittest

from ai_gitgen import config, validators
from ai_gitgen.errors import OutputParseError
from ai_gitgen.records import CommitMessage, PullRequestDraft
from tests.helpers import GOOD_COMMIT, GOOD_PR, PR_MISSING_TEST_SECTION


class ParseCommitTest(unittest.TestCase):
    def test_parses_title_and_body(self) -> None:
        message = validators.parse_commit_text(GOOD_COMMIT)
        self.assertEqual(message.title, "feat(app): 인사 문구 변경 및 반환값 추가")
        self.assertTrue(message.body.startswith("- app.py"))

    def test_drops_preamble_and_code_fences(self) -> None:
        text = "다음은 커밋 메시지입니다:\n```\nfix: 널 체크 추가\n\n- a.py 수정\n```"
        message = validators.parse_commit_text(text)
        self.assertEqual(message.title, "fix: 널 체크 추가")
        self.assertEqual(message.body, "- a.py 수정")

    def test_falls_back_to_first_line_when_no_type_prefix(self) -> None:
        message = validators.parse_commit_text("그냥 제목\n\n- 본문")
        self.assertEqual(message.title, "그냥 제목")

    def test_empty_output_gives_empty_title_for_regeneration(self) -> None:
        message = validators.parse_commit_text("```\n```")
        self.assertEqual(message.title, "")
        self.assertTrue(validators.validate_commit(message).needs_regeneration)
        with self.assertRaises(OutputParseError):
            validators.ensure_title(message.title)


class ValidateAndPolishCommitTest(unittest.TestCase):
    def test_good_message_is_valid(self) -> None:
        report = validators.validate_commit(validators.parse_commit_text(GOOD_COMMIT))
        self.assertTrue(report.is_valid)
        self.assertEqual(report.problems, ())

    def test_detects_length_period_and_format_problems(self) -> None:
        message = CommitMessage(title="제목만 " + "x" * 80 + ".", body="본문 불릿 없음")
        report = validators.validate_commit(message)
        self.assertFalse(report.is_valid)
        joined = " ".join(report.problems)
        self.assertIn("72자를 넘습니다", joined)
        self.assertIn("마침표", joined)
        self.assertIn("형식이 아닙니다", joined)
        self.assertIn("불릿이 없습니다", joined)
        self.assertTrue(report.needs_regeneration)  # 형식 불량은 후처리로 못 고치므로 재생성 대상

    def test_length_only_problem_is_not_regeneration(self) -> None:
        report = validators.validate_commit(CommitMessage(title="feat: " + "x" * 80))
        self.assertFalse(report.is_valid)
        self.assertFalse(report.needs_regeneration)

    def test_empty_title_needs_regeneration(self) -> None:
        self.assertTrue(validators.validate_commit(CommitMessage(title="")).needs_regeneration)

    def test_polish_truncates_title_and_moves_remainder_to_body(self) -> None:
        long_title = "feat: " + " ".join(["단어"] * 40)
        polished = validators.polish_commit(CommitMessage(title=long_title + ".", body="- 기존 불릿"))
        self.assertLessEqual(len(polished.title), config.COMMIT_TITLE_HARD_LIMIT)
        self.assertFalse(polished.title.endswith("."))
        lines = polished.body.splitlines()
        self.assertTrue(lines[0].startswith("- 단어"))
        self.assertEqual(lines[-1], "- 기존 불릿")

    def test_polish_turns_plain_lines_into_bullets(self) -> None:
        polished = validators.polish_commit(CommitMessage(title="fix: x", body="첫 줄\n* 둘째"))
        self.assertEqual(polished.body, "- 첫 줄\n- 둘째")

    def test_polish_does_not_mutate_original(self) -> None:
        original = CommitMessage(title="fix: x.", body="")
        validators.polish_commit(original)
        self.assertEqual(original.title, "fix: x.")


class TruncateTitleTest(unittest.TestCase):
    def test_cuts_at_word_boundary(self) -> None:
        title, rest = validators.truncate_title("feat: add a very long description here", 20)
        self.assertEqual(title, "feat: add a very")
        self.assertEqual(rest, "long description here")

    def test_cuts_hard_when_no_space(self) -> None:
        title, rest = validators.truncate_title("a" * 30, 10)
        self.assertEqual((len(title), len(rest)), (10, 20))


class PullRequestTest(unittest.TestCase):
    def test_parse_pr_strips_labels_and_blank_leading_lines(self) -> None:
        draft = validators.parse_pr_text("\n\nPR Title: feat: 제목\n\n## Why\n- a")
        self.assertEqual(draft.title, "feat: 제목")
        self.assertTrue(draft.body.startswith("## Why"))

    def test_missing_sections_detects_absent_and_bulletless(self) -> None:
        self.assertEqual(validators.missing_sections(validators.parse_pr_text(GOOD_PR).body), ())
        body = "## Why\n- a\n\n## What\n(불릿 없음)\n"
        self.assertEqual(validators.missing_sections(body), ("What", "How to Test"))

    def test_validate_pr_flags_structure_for_regeneration(self) -> None:
        report = validators.validate_pr(validators.parse_pr_text(PR_MISSING_TEST_SECTION))
        self.assertTrue(report.needs_regeneration)
        self.assertIn('"## How to Test" 섹션이 없습니다.', report.problems)

    def test_validate_pr_title_length_is_not_regeneration(self) -> None:
        draft = PullRequestDraft(title="t" * 90, body=validators.parse_pr_text(GOOD_PR).body)
        report = validators.validate_pr(draft)
        self.assertFalse(report.is_valid)
        self.assertFalse(report.needs_regeneration)

    def test_polish_pr_fills_missing_sections_and_truncates_title(self) -> None:
        draft = PullRequestDraft(title="feat: " + "x " * 60, body="## Why\n- 배경\n\n## What\n설명만 있음\n")
        polished = validators.polish_pr(draft)
        self.assertLessEqual(len(polished.title), config.PR_TITLE_HARD_LIMIT)
        self.assertIn("## What\n- 설명만 있음", polished.body)
        self.assertIn(f"## How to Test\n{config.PLACEHOLDER_BULLET}", polished.body)
        self.assertEqual(validators.missing_sections(polished.body), ())


if __name__ == "__main__":
    unittest.main()
