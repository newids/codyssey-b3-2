import unittest

import re

from ai_gitgen.convention import MaskRule, SafeModePolicy, compile_mask_rule
from ai_gitgen.errors import MaskTimeoutError
from ai_gitgen.sanitizer import active_rules, is_excluded, mask_secrets, sanitize, split_diff, truncate_lines


def _file_diff(path: str, lines: int = 3) -> str:
    body = "".join(f"+line {i}\n" for i in range(lines))
    return f"diff --git a/{path} b/{path}\n--- a/{path}\n+++ b/{path}\n@@ -0,0 +1,{lines} @@\n{body}"


class MaskSecretsTest(unittest.TestCase):
    def assert_masked(self, text: str, rule: str) -> None:
        masked, count = mask_secrets(text)
        self.assertIn(f"[MASKED:{rule}]", masked)
        self.assertGreaterEqual(count, 1)

    def test_masks_aws_key(self) -> None:
        self.assert_masked("AKIAABCDEFGHIJKLMNOP", "AWS_KEY")

    def test_masks_anthropic_and_openai_keys(self) -> None:
        self.assert_masked("sk-ant-api03-abcdefghijklmnopqrstuvwxyz0123456789", "ANTHROPIC_KEY")
        self.assert_masked("key = sk-abcdefghijklmnopqrstuvwxyz1234", "OPENAI_KEY")

    def test_masks_github_token_and_jwt(self) -> None:
        self.assert_masked("ghp_abcdefghijklmnopqrstuvwxyz0123456789ABCD", "GITHUB_TOKEN")
        self.assert_masked("eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0In0.abc_DEF-ghi", "JWT")

    def test_masks_generic_assignment_but_keeps_key_name(self) -> None:
        masked, _ = mask_secrets('password = "hunter2hunter2"')
        self.assertEqual(masked, 'password = [MASKED:GENERIC_SECRET]"')

    def test_masks_prefixed_and_quoted_key_names(self) -> None:
        cases = {
            "DB_PASSWORD=supersecret99": "DB_PASSWORD=[MASKED:GENERIC_SECRET]",
            "OPENAI_API_KEY=abcdefgh12345": "OPENAI_API_KEY=[MASKED:GENERIC_SECRET]",
            'access_token = "tok_1234567890"': 'access_token = [MASKED:GENERIC_SECRET]"',
            '"apiKey": "abcdefghij"': '"apiKey": [MASKED:GENERIC_SECRET]"',
        }
        for source, expected in cases.items():
            self.assertEqual(mask_secrets(source)[0], expected, source)

    def test_already_masked_value_is_not_double_counted(self) -> None:
        masked, count = mask_secrets("GITHUB_TOKEN=ghp_abcdefghijklmnopqrstuvwxyz0123456789ABCD")
        self.assertEqual(masked, "GITHUB_TOKEN=[MASKED:GITHUB_TOKEN]")
        self.assertEqual(count, 1)

    def test_masks_email_and_korean_phone(self) -> None:
        self.assert_masked("contact dev@example.com", "EMAIL")
        self.assert_masked("tel 010-1234-5678", "PHONE_KR")

    def test_masks_private_key_block(self) -> None:
        text = "-----BEGIN RSA PRIVATE KEY-----\nMIIE\n-----END RSA PRIVATE KEY-----"
        masked, _ = mask_secrets(text)
        self.assertEqual(masked, "[MASKED:PRIVATE_KEY]")

    def test_plain_code_is_untouched(self) -> None:
        text = "def add(a, b):\n    return a + b\n"
        self.assertEqual(mask_secrets(text), (text, 0))


class SplitAndFilterTest(unittest.TestCase):
    def test_split_diff_by_file_header(self) -> None:
        chunks = split_diff(_file_diff("a.py") + _file_diff("dir/b.py"))
        self.assertEqual([c.path for c in chunks], ["a.py", "dir/b.py"])
        self.assertTrue(chunks[0].text.startswith("diff --git a/a.py"))

    def test_split_diff_without_header_is_single_chunk(self) -> None:
        chunks = split_diff("+just text\n")
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0].path, "")

    def test_excluded_patterns_match_name_and_path(self) -> None:
        self.assertTrue(is_excluded(".env"))
        self.assertTrue(is_excluded("config/.env.local"))
        self.assertTrue(is_excluded("certs/server.pem"))
        self.assertTrue(is_excluded("package-lock.json"))
        self.assertTrue(is_excluded("poetry.lock"))
        self.assertFalse(is_excluded("src/env_loader.py"))
        self.assertFalse(is_excluded("src/clock.py"))  # *lock* 같은 과도한 패턴은 쓰지 않는다

    def test_quoted_header_path_is_unquoted(self) -> None:
        header = 'diff --git "a/\\355\\202\\244.pem" "b/\\355\\202\\244.pem"\n+x\n'
        chunks = split_diff(header)
        self.assertEqual(chunks[0].path, "\\355\\202\\244.pem")
        self.assertTrue(is_excluded(chunks[0].path))
        plain = split_diff('diff --git "a/키 파일.pem" "b/키 파일.pem"\n+x\n')
        self.assertEqual(plain[0].path, "키 파일.pem")

    def test_truncate_lines_adds_marker(self) -> None:
        text, omitted = truncate_lines("a\nb\nc\n", 2)
        self.assertEqual(text, "a\nb\n... (1줄 생략)\n")
        self.assertEqual(omitted, 1)
        self.assertEqual(truncate_lines("a\n", 5), ("a\n", 0))


class SanitizeTest(unittest.TestCase):
    def test_safe_mode_off_only_applies_global_limit(self) -> None:
        diff = _file_diff("a.py", lines=10) + "AKIAABCDEFGHIJKLMNOP\n"
        result = sanitize(diff, safe_mode=False, policy=SafeModePolicy(global_max_lines=1000))
        self.assertFalse(result.safe_mode)
        self.assertIn("AKIAABCDEFGHIJKLMNOP", result.text)  # 마스킹 없음
        self.assertEqual(result.masked_count, 0)

    def test_safe_mode_off_truncates_huge_diff(self) -> None:
        result = sanitize(_file_diff("a.py", lines=50), safe_mode=False, policy=SafeModePolicy(global_max_lines=10))
        self.assertGreater(result.truncated_lines, 0)
        self.assertIn("줄 생략", result.text)

    def test_safe_mode_excludes_sensitive_files_and_masks(self) -> None:
        diff = _file_diff("app.py") + "+EMAIL=dev@example.com\n" + _file_diff(".env")
        result = sanitize(diff, safe_mode=True)
        self.assertEqual(result.omitted_files, (".env",))
        self.assertIn("[생략된 파일: .env]", result.text)
        self.assertIn("[MASKED:EMAIL]", result.text)
        self.assertEqual(result.masked_count, 1)

    def test_safe_mode_limits_file_count(self) -> None:
        diff = "".join(_file_diff(f"f{i}.py") for i in range(12))
        result = sanitize(diff, safe_mode=True, policy=SafeModePolicy(max_files=10))
        self.assertEqual(result.omitted_files, ("f10.py", "f11.py"))
        self.assertNotIn("diff --git a/f11.py", result.text)

    def test_safe_mode_limits_lines_per_file(self) -> None:
        result = sanitize(_file_diff("a.py", lines=300), safe_mode=True, policy=SafeModePolicy(max_lines_per_file=200))
        self.assertGreater(result.truncated_lines, 0)
        self.assertNotIn("+line 299", result.text)

    def test_masking_happens_before_truncation(self) -> None:
        key_block = "+-----BEGIN RSA PRIVATE KEY-----\n" + "+MIIE\n" * 20 + "+-----END RSA PRIVATE KEY-----\n"
        diff = "diff --git a/k.txt b/k.txt\n" + key_block
        result = sanitize(diff, safe_mode=True, policy=SafeModePolicy(max_lines_per_file=5))
        self.assertIn("[MASKED:PRIVATE_KEY]", result.text)
        self.assertNotIn("MIIE", result.text)


class CustomPolicyTest(unittest.TestCase):
    def setUp(self) -> None:
        self.policy = SafeModePolicy(
            max_files=2,
            max_lines_per_file=50,
            exclude=("*.csv",),
            mask_rules=(compile_mask_rule("INTERNAL_ID", r"EMP-\d{6}"),),
            disabled_rules=("EMAIL",),
        )

    def test_custom_rule_masks_and_disabled_rule_is_skipped(self) -> None:
        rules = active_rules(self.policy)
        names = [name for name, _ in rules]
        self.assertIn("INTERNAL_ID", names)
        self.assertNotIn("EMAIL", names)
        self.assertEqual(names[-1], "INTERNAL_ID")  # 사용자 규칙은 내장 규칙 뒤에
        masked, count = mask_secrets("사번 EMP-123456, 메일 dev@example.com", rules)
        self.assertEqual(masked, "사번 [MASKED:INTERNAL_ID], 메일 dev@example.com")
        self.assertEqual(count, 1)

    def test_default_rules_are_unchanged_without_policy(self) -> None:
        self.assertEqual(len(active_rules(SafeModePolicy())), 9)

    def test_sanitize_applies_policy_exclusions_limits_and_rules(self) -> None:
        diff = _file_diff("a.py") + "+EMP-654321\n" + _file_diff("data.csv") + _file_diff("b.py") + _file_diff("c.py")
        result = sanitize(diff, safe_mode=True, policy=self.policy)
        self.assertEqual(result.omitted_files, ("data.csv", "c.py"))
        self.assertIn("[MASKED:INTERNAL_ID]", result.text)
        self.assertEqual(result.masked_count, 1)

    def test_catastrophic_custom_rule_is_stopped_by_timeout(self) -> None:
        # compile_mask_rule 은 (a+)+ 를 거부하므로 검증을 우회한 규칙을 직접 만들어 실행 시간 제한만 확인한다
        evil = MaskRule("EVIL_X", re.compile(r"(a+)+$"))
        rules = (("EVIL_X", evil.pattern),)
        with self.assertRaises(MaskTimeoutError) as ctx:
            mask_secrets("a" * 40 + "b", rules, timeout=0.2)
        self.assertIn("EVIL_X", str(ctx.exception))
        self.assertEqual(mask_secrets("fine", rules, timeout=0.2), ("fine", 0))  # 타이머가 해제되어 다음 호출은 정상

    def test_builtin_rules_are_not_time_limited(self) -> None:
        text, count = mask_secrets("AKIAABCDEFGHIJKLMNOP", timeout=0.0)
        self.assertEqual(count, 1)

    def test_mask_rule_is_immutable_value(self) -> None:
        rule = compile_mask_rule("A_B", "x")
        self.assertIsInstance(rule, MaskRule)
        with self.assertRaises(Exception):
            rule.name = "C"  # type: ignore[misc]


if __name__ == "__main__":
    unittest.main()
