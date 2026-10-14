import json
import tempfile
import unittest
from pathlib import Path

from ai_gitgen import config, convention
from ai_gitgen.errors import ConventionError


def write_json(directory: Path, data: dict, name: str = config.CONVENTION_FILE_NAME) -> Path:
    path = directory / name
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return path


class DefaultConventionTest(unittest.TestCase):
    def test_default_matches_config_constants(self) -> None:
        default = convention.DEFAULT_CONVENTION
        self.assertEqual(default.commit.types, config.COMMIT_TYPES)
        self.assertEqual(default.commit.scope, "optional")
        self.assertEqual(default.commit.title_hard_limit, config.COMMIT_TITLE_HARD_LIMIT)
        self.assertEqual(default.pr.sections, config.PR_REQUIRED_SECTIONS)
        self.assertEqual(default.pr.checklist, ())
        self.assertEqual(default.pr.footer, "")
        self.assertIsNone(default.source)

    def test_no_file_in_directory_returns_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            loaded = convention.load_convention(None, cwd=tmp)
        self.assertEqual(loaded, convention.DEFAULT_CONVENTION)


class LoadConventionTest(unittest.TestCase):
    def test_file_in_cwd_is_discovered_and_overrides_only_given_keys(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            write_json(
                Path(tmp),
                {
                    "commit": {"types": ["feat", "fix", "docs"], "scope": "forbidden", "rules": ["조사는 띄어 쓴다"]},
                    "pr": {"test_command": "python -m unittest discover -s tests -t .", "checklist": ["테스트 통과"], "footer": "도구로 생성"},
                },
            )
            loaded = convention.load_convention(None, cwd=tmp)
        self.assertEqual(loaded.commit.types, ("feat", "fix", "docs"))
        self.assertEqual(loaded.commit.scope, "forbidden")
        self.assertEqual(loaded.commit.rules, ("조사는 띄어 쓴다",))
        self.assertEqual(loaded.commit.title_hard_limit, config.COMMIT_TITLE_HARD_LIMIT)  # 생략한 키는 기본값
        self.assertEqual(loaded.pr.sections, config.PR_REQUIRED_SECTIONS)
        self.assertEqual(loaded.pr.test_command, "python -m unittest discover -s tests -t .")
        self.assertEqual(loaded.pr.checklist, ("테스트 통과",))
        self.assertEqual(loaded.pr.footer, "도구로 생성")
        self.assertTrue(str(loaded.source).endswith(config.CONVENTION_FILE_NAME))

    def test_explicit_path_wins_over_cwd_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            write_json(Path(tmp), {"commit": {"scope": "forbidden"}})
            other = write_json(Path(tmp), {"commit": {"scope": "required"}}, name="team.json")
            loaded = convention.load_convention(str(other), cwd=tmp)
        self.assertEqual(loaded.commit.scope, "required")
        self.assertEqual(Path(loaded.source), other)

    def test_explicit_missing_path_is_an_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ConventionError) as ctx:
                convention.load_convention(str(Path(tmp) / "nope.json"), cwd=tmp)
        self.assertIn("찾을 수 없습니다", str(ctx.exception))

    def test_invalid_json_reports_position(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / config.CONVENTION_FILE_NAME
            path.write_text('{"commit": {"types": [}}', encoding="utf-8")
            with self.assertRaises(ConventionError) as ctx:
                convention.load_convention(None, cwd=tmp)
        self.assertIn("JSON", str(ctx.exception))

    def test_schema_violations_are_reported_with_key_names(self) -> None:
        cases = [
            ({"commit": {"scope": "maybe"}}, "commit.scope"),
            ({"commit": {"types": []}}, "commit.types"),
            ({"commit": {"types": ["feat", 3]}}, "commit.types"),
            ({"commit": {"types": ["Feat Ure"]}}, "commit.types"),
            ({"commit": {"title_hard_limit": 10}}, "commit.title_hard_limit"),
            ({"commit": {"title_soft_limit": 80, "title_hard_limit": 72}}, "commit.title_soft_limit"),
            ({"pr": {"sections": "Why"}}, "pr.sections"),
            ({"pr": {"sections": ["Why", ""]}}, "pr.sections"),
            ({"pr": {"footer": ["x"]}}, "pr.footer"),
            ({"pr": {"footer": "---"}}, "pr.footer"),
            ({"pr": {"footer": "두 줄\n푸터"}}, "pr.footer"),
            ({"pr": {"footer": "## Why"}}, "pr.footer"),
            ({"pr": {"sections": ["Why", "Why"]}}, "pr.sections"),
            ({"pr": {"sections": ["Why", "A # B"]}}, "pr.sections"),
            ({"pr": {"sections": ["Why", "Checklist"], "checklist": ["x"]}}, "pr.checklist"),
            ({"pr": {"test_command": "a\nb"}}, "pr.test_command"),
            ({"pr": {"rules": ["x"] * 21}}, "pr.rules"),
            ({"commit": {"rules": ["y" * 301]}}, "commit.rules"),
            ({"commit": {"types": ["feat", "feat"]}}, "commit.types"),
            ({"pr": {"unknown": 1}}, "pr.unknown"),
            ({"version": 2}, "version"),
            ({"commit": []}, "commit"),
            ([], "최상위"),
        ]
        for data, key in cases:
            with self.subTest(key=key), tempfile.TemporaryDirectory() as tmp:
                write_json(Path(tmp), data) if not isinstance(data, list) else (Path(tmp) / config.CONVENTION_FILE_NAME).write_text("[]", encoding="utf-8")
                with self.assertRaises(ConventionError) as ctx:
                    convention.load_convention(None, cwd=tmp)
                self.assertIn(key, str(ctx.exception))

    def test_directory_bom_and_binary_files_are_reported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / config.CONVENTION_FILE_NAME
            target.mkdir()
            with self.assertRaises(ConventionError) as ctx:
                convention.load_convention(None, cwd=tmp)
            self.assertIn("파일이 아닙니다", str(ctx.exception))
            with self.assertRaises(ConventionError):
                convention.load_convention(str(target), cwd=tmp)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / config.CONVENTION_FILE_NAME
            path.write_bytes(b"\xef\xbb\xbf" + json.dumps({"commit": {"scope": "forbidden"}}).encode())
            self.assertEqual(convention.load_convention(None, cwd=tmp).commit.scope, "forbidden")
            path.write_bytes(b"\xff\xfe\x00bad")
            with self.assertRaises(ConventionError) as ctx:
                convention.load_convention(None, cwd=tmp)
            self.assertIn("해석할 수 없습니다", str(ctx.exception))

    def test_section_headers_may_include_hash_prefix(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            write_json(Path(tmp), {"pr": {"sections": ["## Why", "What", "## Checklist"]}})
            loaded = convention.load_convention(None, cwd=tmp)
        self.assertEqual(loaded.pr.sections, ("Why", "What", "Checklist"))


class DescribeAndTemplateTest(unittest.TestCase):
    def test_describe_lists_effective_values(self) -> None:
        text = convention.describe(convention.DEFAULT_CONVENTION)
        self.assertIn("기본값", text)
        self.assertIn("feat, fix", text)
        self.assertIn("Why, What, How to Test", text)

    def test_template_round_trips_through_loader(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / config.CONVENTION_FILE_NAME
            path.write_text(convention.template_json(), encoding="utf-8")
            loaded = convention.load_convention(None, cwd=tmp)
        self.assertEqual(loaded.commit.types, config.COMMIT_TYPES)
        self.assertEqual(loaded.pr.sections, config.PR_REQUIRED_SECTIONS)


if __name__ == "__main__":
    unittest.main()
