import tempfile
import unittest
from pathlib import Path

from ai_gitgen.errors import GitCommandError, NotGitRepositoryError
from ai_gitgen.git_collector import collect_changes, parse_porcelain, run_git
from tests.helpers import git, init_repo


class CollectChangesTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self._tmp.name).resolve()
        init_repo(self.repo)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_clean_repository_reports_empty_changes(self) -> None:
        changes = collect_changes(self.repo)
        self.assertTrue(changes.is_empty)
        self.assertEqual(changes.branch, "main")

    def test_modified_and_staged_files_appear_in_diff(self) -> None:
        (self.repo / "app.py").write_text('def main():\n    print("hello")\n', encoding="utf-8")
        (self.repo / "util.py").write_text("X = 1\n", encoding="utf-8")
        git(self.repo, "add", "util.py")

        changes = collect_changes(self.repo)

        self.assertFalse(changes.is_empty)
        self.assertEqual({f.path for f in changes.files}, {"app.py", "util.py"})
        self.assertIn('+    print("hello")', changes.diff_text)  # 작업 트리 변경
        self.assertIn("+X = 1", changes.diff_text)  # 스테이징 변경
        self.assertGreater(changes.line_count, 0)

    def test_untracked_file_content_is_collected_with_no_index_diff(self) -> None:
        (self.repo / "notes.md").write_text("# memo\n", encoding="utf-8")

        changes = collect_changes(self.repo)

        self.assertEqual(changes.untracked_paths, ("notes.md",))
        self.assertIn("+# memo", changes.diff_text)

    def test_large_untracked_file_is_skipped(self) -> None:
        (self.repo / "big.txt").write_text("x" * 250_000, encoding="utf-8")
        changes = collect_changes(self.repo)
        self.assertEqual(changes.untracked_paths, ("big.txt",))
        self.assertNotIn("xxxx", changes.diff_text)

    def test_subdirectory_is_rejected_with_root_hint(self) -> None:
        sub = self.repo / "pkg"
        sub.mkdir()
        with self.assertRaises(NotGitRepositoryError) as ctx:
            collect_changes(sub)
        self.assertIn("저장소 루트에서 실행", str(ctx.exception))
        self.assertIn(str(self.repo), str(ctx.exception))

    def test_non_repository_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as plain:
            with self.assertRaises(NotGitRepositoryError):
                collect_changes(plain)

    def test_other_git_failures_become_git_command_error(self) -> None:
        with self.assertRaises(GitCommandError) as ctx:
            run_git("no-such-subcommand", cwd=self.repo)
        self.assertIn("git no-such-subcommand 실패", str(ctx.exception))


    def test_fresh_repository_without_commits_works(self) -> None:
        with tempfile.TemporaryDirectory() as fresh:
            repo = Path(fresh).resolve()
            git(repo, "init", "-q", "-b", "main")
            (repo / "first.py").write_text("x = 1\n", encoding="utf-8")
            changes = collect_changes(repo)
        self.assertEqual(changes.branch, "main")
        self.assertIn("+x = 1", changes.diff_text)

    def test_korean_and_spaced_filenames_are_collected(self) -> None:
        (self.repo / "메모 파일.md").write_text("# 메모\n", encoding="utf-8")
        changes = collect_changes(self.repo)
        self.assertEqual(changes.untracked_paths, ("메모 파일.md",))
        self.assertIn("+# 메모", changes.diff_text)
        self.assertIn('b/메모 파일.md', changes.diff_text)  # 따옴표 없이 원래 경로

    def test_untracked_directory_lists_each_file(self) -> None:
        (self.repo / "pkg").mkdir()
        (self.repo / "pkg" / "a.py").write_text("A = 1\n", encoding="utf-8")
        (self.repo / "pkg" / "b.py").write_text("B = 2\n", encoding="utf-8")
        changes = collect_changes(self.repo)
        self.assertEqual(set(changes.untracked_paths), {"pkg/a.py", "pkg/b.py"})
        self.assertIn("+B = 2", changes.diff_text)


class ParsePorcelainTest(unittest.TestCase):
    def test_parses_status_and_path(self) -> None:
        files = parse_porcelain(" M a.py\0A  b.py\0?? c.md\0")
        self.assertEqual([(f.status, f.path) for f in files], [(" M", "a.py"), ("A ", "b.py"), ("??", "c.md")])
        self.assertTrue(files[2].is_untracked)

    def test_rename_uses_new_path_and_skips_old(self) -> None:
        files = parse_porcelain("R  new.py\0old.py\0 M other.py\0")
        self.assertEqual([f.path for f in files], ["new.py", "other.py"])

    def test_blank_entries_are_ignored(self) -> None:
        self.assertEqual(parse_porcelain("\0\0"), ())


if __name__ == "__main__":
    unittest.main()
