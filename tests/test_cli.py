import contextlib
import io
import os
import tempfile
import unittest
from unittest import mock

from ai_gitgen import cli
from ai_gitgen.errors import UnsupportedParameterError
from ai_gitgen.records import ChangedFile, GitChanges
from tests.helpers import GOOD_COMMIT, GOOD_PR, PR_MISSING_TEST_SECTION, SAMPLE_DIFF, FakeClient, result, sample_changes


class CliTestCase(unittest.TestCase):
    """공통 준비: 임시 레지스트리 홈, 가짜 API 키, 가짜 git 수집, 가짜 클라이언트."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        env = {"AI_GITGEN_HOME": self._tmp.name, "AI_API_KEY": "test-key"}
        for name in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "AI_PROVIDER", "AI_API_URL", "AI_API_BASE_URL", "AI_API_MODEL", "AI_SMALL_FAST_MODEL"):
            os.environ.pop(name, None)
        self._patches = [
            mock.patch.dict(os.environ, env),
            mock.patch("ai_gitgen.commands.collect_changes", return_value=sample_changes()),
            mock.patch("ai_gitgen.commands.AIClient", FakeClient),
        ]
        for p in self._patches:
            p.start()
        FakeClient.queue = []
        self.created: list[FakeClient] = []
        original_init = FakeClient.__init__

        def tracking_init(instance, *args, **kwargs):
            original_init(instance, *args, **kwargs)
            self.created.append(instance)

        self._init_patch = mock.patch.object(FakeClient, "__init__", tracking_init)
        self._init_patch.start()

    def tearDown(self) -> None:
        self._init_patch.stop()
        for p in reversed(self._patches):
            p.stop()
        self._tmp.cleanup()

    def run_cli(self, *argv: str) -> tuple[int, str, str]:
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = cli.main(list(argv))
        return code, out.getvalue(), err.getvalue()

    @property
    def client(self) -> FakeClient:
        return self.created[-1]


class CommitCommandTest(CliTestCase):
    def test_commit_prints_block_and_logs(self) -> None:
        FakeClient.queue = [result(GOOD_COMMIT)]
        code, out, err = self.run_cli("commit")
        self.assertEqual(code, 0)
        self.assertIn("--- Commit Message ---\nfeat(app): 인사 문구 변경 및 반환값 추가\n\n- app.py", out)
        self.assertIn("[INFO] Git status 수집 완료: 1개 파일 변경 감지", err)
        self.assertIn("[INFO] AI API 호출 횟수: 1회 / 토큰 사용: 입력 100 · 출력 20", err)
        self.assertIn("[DONE] 커밋 메시지 생성 완료", err)
        self.assertEqual(self.client.settings_seen[0].model, "claude-sonnet-4-6")
        self.assertEqual(self.client.settings_seen[0].temperature, 0.3)

    def test_options_are_passed_to_settings(self) -> None:
        FakeClient.queue = [result(GOOD_COMMIT)]
        self.run_cli("commit", "--provider", "openai", "--model", "gpt-4.1", "--temperature", "0", "--max-tokens", "99")
        seen = self.client.settings_seen[0]
        self.assertEqual((seen.provider, seen.model, seen.temperature, seen.max_tokens), ("openai", "gpt-4.1", 0.0, 99))

    def test_env_model_url_and_fast_model_are_used(self) -> None:
        env = {"AI_API_URL": "https://copa.example.kr", "AI_API_MODEL": "claude-sonnet-4", "AI_SMALL_FAST_MODEL": "claude-haiku-4"}
        with mock.patch.dict(os.environ, env):
            FakeClient.queue = [result(GOOD_COMMIT)]
            _, _, err = self.run_cli("commit")
            default_seen = self.client.settings_seen[0]
            FakeClient.queue = [result(GOOD_COMMIT)]
            self.run_cli("commit", "--fast")
            fast_seen = self.client.settings_seen[0]
            FakeClient.queue = [result(GOOD_COMMIT)]
            self.run_cli("commit", "--model", "gpt-4.1")
            explicit_seen = self.client.settings_seen[0]
        self.assertEqual((default_seen.provider, default_seen.model), ("openai", "claude-sonnet-4"))  # URL 이 있으면 OpenAI 호환 형식
        self.assertEqual(fast_seen.model, "claude-haiku-4")
        self.assertEqual(explicit_seen.model, "gpt-4.1")
        self.assertIn("url=https://copa.example.kr", err)

    def test_fast_without_env_uses_provider_default_small_model(self) -> None:
        FakeClient.queue = [result(GOOD_COMMIT)]
        self.run_cli("commit", "--fast")
        self.assertEqual(self.client.settings_seen[0].model, "claude-haiku-4-5")
        code, _, err = self.run_cli("commit", "--fast", "--model", "x")
        self.assertEqual(code, 2)
        self.assertIn("함께 쓸 수 없습니다", err)

    def test_explicit_provider_env_overrides_proxy_default(self) -> None:
        with mock.patch.dict(os.environ, {"AI_API_URL": "https://copa.example.kr", "AI_PROVIDER": "claude"}):
            FakeClient.queue = [result(GOOD_COMMIT)]
            self.run_cli("commit")
        self.assertEqual(self.client.settings_seen[0].provider, "claude")

    def test_builtin_rejection_applies_across_providers(self) -> None:
        FakeClient.queue = [result(GOOD_COMMIT)]
        _, _, err = self.run_cli("commit", "--provider", "openai", "--model", "claude-opus-5-5")
        self.assertIn("출처: 내장 목록", err)
        self.assertIsNone(self.client.settings_seen[0].temperature)

    def test_no_changes_exits_with_code_three_without_api_call(self) -> None:
        with mock.patch("ai_gitgen.commands.collect_changes", return_value=GitChanges("main", (), "")):
            code, out, err = self.run_cli("commit")
        self.assertEqual(code, 3)
        self.assertIn("[INFO] 변경 사항이 없습니다. 커밋 메시지를 생성하지 않고 종료합니다 (종료 코드 3).", err)
        self.assertEqual(out, "")
        self.assertEqual(self.created, [])

    def test_done_line_reminds_review_before_applying(self) -> None:
        FakeClient.queue = [result(GOOD_COMMIT)]
        _, _, err = self.run_cli("commit")
        self.assertIn("[DONE] 커밋 메시지 생성 완료. AI 초안입니다. 내용을 검토·수정한 뒤 적용하세요", err)
        FakeClient.queue = [result(GOOD_PR)]
        _, _, err = self.run_cli("pr")
        self.assertIn("[DONE] PR 초안 생성 완료. AI 초안입니다.", err)

    def test_title_over_soft_limit_is_noted_with_both_limits(self) -> None:
        FakeClient.queue = [result("feat(search): 금액 범위 필터 옵션 추가 (--min-amount, --max-amount)\n\n- 본문")]
        _, _, err = self.run_cli("commit")
        self.assertIn("[INFO] 제목 57자: 권장 50자를 넘었습니다 (최대 72자).", err)
        FakeClient.queue = [result(GOOD_COMMIT)]
        _, _, err = self.run_cli("commit")
        self.assertNotIn("권장 50자", err)

    def test_secrets_without_safe_mode_are_warned_before_sending(self) -> None:
        diff = SAMPLE_DIFF + "diff --git a/.env b/.env\n+ADMIN=admin@example.com\n+TOKEN=ghp_" + "a" * 36 + "\n"
        changes = sample_changes(diff)
        changes = GitChanges(changes.branch, changes.files + (ChangedFile(".env", "A "),), diff)
        with mock.patch("ai_gitgen.commands.collect_changes", return_value=changes):
            FakeClient.queue = [result(GOOD_COMMIT)]
            _, _, err = self.run_cli("commit")
            self.assertIn(
                "[WARN] safe-mode 꺼짐: 민감정보로 보이는 값 2개 (GITHUB_TOKEN 1, EMAIL 1) · 비밀 파일로 분류되는 파일 1개 (.env) 이(가) 그대로 전송됩니다.",
                err,
            )
            self.assertIn("--safe-mode 를 켜거나", err)
            FakeClient.queue = [result(GOOD_COMMIT)]
            _, _, err = self.run_cli("commit", "--safe-mode")
        self.assertNotIn("safe-mode 꺼짐", err)
        FakeClient.queue = [result(GOOD_COMMIT)]
        _, _, err = self.run_cli("commit")  # 평범한 diff 에는 경고가 없다
        self.assertNotIn("safe-mode 꺼짐", err)

    def test_unprotected_scan_timeout_is_a_warning_not_a_failure(self) -> None:
        from ai_gitgen.errors import MaskTimeoutError

        FakeClient.queue = [result(GOOD_COMMIT)]
        with mock.patch("ai_gitgen.commands.find_sensitive", side_effect=MaskTimeoutError("규칙 X 가 2초 안에 끝나지 않아 중단했습니다.")):
            code, out, err = self.run_cli("commit")
        self.assertEqual(code, 0)
        self.assertIn("[WARN] 민감정보 사전 검사를 건너뜁니다: 규칙 X", err)
        self.assertIn("--- Commit Message ---", out)

    def test_unprotected_scan_only_covers_text_that_is_sent(self) -> None:
        body = "".join(f"+line {i}\n" for i in range(2100)) + "+leak=a@example.com\n"  # 전체 2,000줄 상한 뒤에 있는 값
        with mock.patch("ai_gitgen.commands.collect_changes", return_value=sample_changes(SAMPLE_DIFF + body)):
            FakeClient.queue = [result(GOOD_COMMIT)]
            _, _, err = self.run_cli("commit")
        self.assertNotIn("safe-mode 꺼짐", err)
        self.assertIn("길이 제한으로 생략", err)

    def test_bad_api_url_fails_before_git_collection(self) -> None:
        with mock.patch.dict(os.environ, {"AI_API_URL": "http://evil.example.com"}), mock.patch(
            "ai_gitgen.commands.collect_changes", return_value=sample_changes()
        ) as collect:
            code, _, err = self.run_cli("commit", "--dry-run")
        self.assertEqual(code, 2)
        self.assertIn("https:// 주소여야 합니다", err)
        collect.assert_not_called()

    def test_dry_run_prints_prompts_without_client(self) -> None:
        code, out, err = self.run_cli("commit", "--dry-run", "--safe-mode")
        self.assertEqual(code, 0)
        self.assertIn("--- System Prompt ---", out)
        self.assertIn("<diff>", out)
        self.assertIn("[INFO] safe-mode:", err)
        self.assertEqual(self.created, [])

    def test_missing_api_key_exits_before_git_collection(self) -> None:
        with mock.patch.dict(os.environ, {"AI_API_KEY": ""}), mock.patch(
            "ai_gitgen.commands.collect_changes", return_value=sample_changes()
        ) as collect:
            code, out, err = self.run_cli("commit")
        self.assertEqual(code, 2)
        self.assertIn("[ERROR] AI_API_KEY 환경변수가 설정되지 않았습니다. API 를 호출하지 않고 종료합니다.", err)
        self.assertIn('export AI_API_KEY="YOUR_KEY"  (또는 ANTHROPIC_API_KEY)', err)
        self.assertIn("--dry-run", err)
        self.assertEqual(out, "")
        collect.assert_not_called()
        self.assertEqual(self.created, [])

    def test_api_key_source_is_logged_by_name_only(self) -> None:
        FakeClient.queue = [result(GOOD_COMMIT)]
        _, _, err = self.run_cli("commit")
        self.assertIn("[INFO] API 키 확인: AI_API_KEY 설정됨", err)
        self.assertNotIn("test-key", err)
        with mock.patch.dict(os.environ, {"AI_API_KEY": "", "OPENAI_API_KEY": "sk-other"}):
            FakeClient.queue = [result(GOOD_COMMIT)]
            _, _, err = self.run_cli("commit", "--provider", "openai")
        self.assertIn("[INFO] API 키 확인: OPENAI_API_KEY 설정됨", err)
        self.assertNotIn("sk-other", err)

    def test_dry_run_does_not_need_api_key(self) -> None:
        with mock.patch.dict(os.environ, {"AI_API_KEY": ""}):
            code, out, err = self.run_cli("commit", "--dry-run")
        self.assertEqual(code, 0)
        self.assertIn("--- System Prompt ---", out)
        self.assertNotIn("API 키 확인", err)

    def test_long_title_is_polished_with_warning(self) -> None:
        FakeClient.queue = [result("feat: " + "단어 " * 40 + "\n\n- 본문")]
        code, out, err = self.run_cli("commit")
        self.assertEqual(code, 0)
        title = out.split("--- Commit Message ---\n", 1)[1].splitlines()[0]
        self.assertLessEqual(len(title), 72)
        self.assertIn("[WARN] 후처리로 보정한 항목", err)

    def test_max_tokens_stop_reason_warns(self) -> None:
        FakeClient.queue = [result(GOOD_COMMIT, stop_reason="max_tokens")]
        _, _, err = self.run_cli("commit")
        self.assertIn("max_tokens 에서 잘렸습니다", err)

    def test_truncated_output_is_not_regenerated(self) -> None:
        FakeClient.queue = [result(PR_MISSING_TEST_SECTION, stop_reason="max_tokens"), result(GOOD_PR)]
        code, out, err = self.run_cli("pr")
        self.assertEqual(code, 0)
        self.assertEqual(self.client.call_count, 1)
        self.assertIn("[WARN] 출력이 잘려 구조가 깨졌습니다. 재생성하지 않고 후처리만 합니다. --max-tokens 를 늘려", err)
        self.assertNotIn("1회 재생성합니다", err)
        self.assertIn("## How to Test\n- (작성 필요)", out)


class TemperatureRegistryTest(CliTestCase):
    def test_builtin_rejecting_model_skips_temperature(self) -> None:
        FakeClient.queue = [result(GOOD_COMMIT)]
        _, _, err = self.run_cli("commit", "--model", "claude-opus-5-5")
        self.assertIn("temperature 를 지원하지 않아 생략합니다 (출처: 내장 목록)", err)
        self.assertIsNone(self.client.settings_seen[0].temperature)
        self.assertEqual(self.client.call_count, 1)

    def test_unknown_model_400_is_recorded_and_retried_once(self) -> None:
        FakeClient.queue = [UnsupportedParameterError("new-model", "temperature", "not supported"), result(GOOD_COMMIT)]
        code, out, err = self.run_cli("commit", "--model", "new-model")
        self.assertEqual(code, 0)
        self.assertIn("temperature 미지원 모델로 기록했습니다", err)
        self.assertEqual([s.temperature for s in self.client.settings_seen], [0.3, None])
        self.assertIn("AI API 호출 횟수: 2회", err)
        # 다음 실행부터는 미리 생략한다
        FakeClient.queue = [result(GOOD_COMMIT)]
        _, _, err2 = self.run_cli("commit", "--model", "new-model")
        self.assertIn("학습)", err2)
        self.assertIsNone(self.client.settings_seen[0].temperature)

    def test_temperature_retry_blocks_structural_regeneration(self) -> None:
        FakeClient.queue = [
            UnsupportedParameterError("new-model", "temperature", "x"),
            result(PR_MISSING_TEST_SECTION),
            result(GOOD_PR),  # 쓰이면 안 된다
        ]
        code, out, err = self.run_cli("pr", "--model", "new-model")
        self.assertEqual(code, 0)
        self.assertEqual(self.client.call_count, 2)
        self.assertIn("## How to Test\n- (작성 필요)", out)

    def test_models_subcommands(self) -> None:
        code, out, _ = self.run_cli("models", "add", "x-model", "--reason", "실험")
        self.assertEqual(code, 0)
        code, out, _ = self.run_cli("models", "list")
        self.assertIn("x-model", out)
        self.assertIn("학습", out)
        code, _, err = self.run_cli("models", "remove", "claude-opus-5-5")
        self.assertEqual(code, 0)
        _, out, _ = self.run_cli("models", "list")
        self.assertIn("제외(내장)", out)
        code, _, err = self.run_cli("models", "remove", "never-added")
        self.assertEqual(code, 1)
        self.assertIn("목록에 없습니다", err)
        code, _, _ = self.run_cli("models", "reset")
        self.assertEqual(code, 0)
        _, out, _ = self.run_cli("models", "list")
        self.assertNotIn("x-model", out)


class PullRequestCommandTest(CliTestCase):
    def test_pr_collects_branch_changes_with_base_option(self) -> None:
        FakeClient.queue = [result(GOOD_PR)]
        with mock.patch("ai_gitgen.commands.collect_changes", return_value=sample_changes()) as collect:
            self.run_cli("pr", "--base", "develop")
        collect.assert_called_once_with(include_branch=True, base="develop")
        FakeClient.queue = [result(GOOD_COMMIT)]
        with mock.patch("ai_gitgen.commands.collect_changes", return_value=sample_changes()) as collect:
            self.run_cli("commit")
        collect.assert_called_once_with()

    def test_pr_without_detectable_base_warns(self) -> None:
        FakeClient.queue = [result(GOOD_PR)]
        _, _, err = self.run_cli("pr")
        self.assertIn("[WARN] 기준 브랜치를 찾지 못해", err)

    def test_pr_prints_title_and_body(self) -> None:
        FakeClient.queue = [result(GOOD_PR)]
        code, out, err = self.run_cli("pr", "--context", "문구 통일")
        self.assertEqual(code, 0)
        self.assertIn("--- PR Title ---\nfeat: 인사 문구 변경\n\n--- PR Body ---\n## Why", out)
        self.assertIn("[INFO] 현재 브랜치: feature/greeting", err)
        self.assertIn("변경 이유(작성자 제공): 문구 통일", self.client.prompts_seen[0][1])
        self.assertEqual(self.client.settings_seen[0].max_tokens, 1024)

    def test_missing_section_triggers_single_regeneration(self) -> None:
        FakeClient.queue = [result(PR_MISSING_TEST_SECTION), result(GOOD_PR)]
        code, out, err = self.run_cli("pr")
        self.assertEqual(code, 0)
        self.assertEqual(self.client.call_count, 2)
        self.assertIn("[WARN] 출력 구조가 규칙에 맞지 않아 1회 재생성합니다", err)
        self.assertIn("<previous_output>", self.client.prompts_seen[1][1])
        self.assertIn("## How to Test\n- python app.py 실행", out)
        self.assertIn("AI API 호출 횟수: 2회", err)

    def test_regeneration_failure_falls_back_to_placeholder(self) -> None:
        FakeClient.queue = [result(PR_MISSING_TEST_SECTION), result(PR_MISSING_TEST_SECTION), result(GOOD_PR)]
        code, out, _ = self.run_cli("pr")
        self.assertEqual(code, 0)
        self.assertEqual(self.client.call_count, 2)
        self.assertIn("- (작성 필요)", out)

    def test_regeneration_api_error_keeps_first_draft(self) -> None:
        from ai_gitgen.errors import AIRequestError

        FakeClient.queue = [result(PR_MISSING_TEST_SECTION), AIRequestError("요청 한도 초과 (HTTP 429)")]
        code, out, err = self.run_cli("pr")
        self.assertEqual(code, 0)
        self.assertIn("[WARN] 재생성 요청이 실패해 첫 초안을 사용합니다", err)
        self.assertIn("## Why\n- 문구 통일", out)
        self.assertIn("- (작성 필요)", out)

    def test_empty_output_is_regenerated_then_reported(self) -> None:
        FakeClient.queue = [result(""), result(GOOD_COMMIT)]
        code, out, err = self.run_cli("commit")
        self.assertEqual(code, 0)
        self.assertEqual(self.client.call_count, 2)
        self.assertIn("feat(app)", out)

        FakeClient.queue = [result(""), result("")]
        code, _, err = self.run_cli("commit")
        self.assertEqual(code, 1)
        self.assertIn("[ERROR] 모델 출력에서 제목을 찾을 수 없습니다", err)

    def test_preamble_only_title_triggers_regeneration(self) -> None:
        FakeClient.queue = [result("다음은 커밋 메시지입니다"), result(GOOD_COMMIT)]
        code, out, err = self.run_cli("commit")
        self.assertEqual(code, 0)
        self.assertIn("형식이 아닙니다", err)
        self.assertIn("feat(app)", out)


class ArgumentValidationTest(CliTestCase):
    def test_temperature_out_of_range(self) -> None:
        code, _, err = self.run_cli("commit", "--temperature", "1.5")
        self.assertEqual(code, 2)
        self.assertIn("0.0~1.0", err)

    def test_max_tokens_must_be_positive(self) -> None:
        code, _, err = self.run_cli("pr", "--max-tokens", "0")
        self.assertEqual(code, 2)
        self.assertIn("--max-tokens", err)

    def test_api_error_is_reported_with_exit_one(self) -> None:
        from ai_gitgen.errors import AIRequestError

        FakeClient.queue = [AIRequestError("인증 실패 (HTTP 401): bad key")]
        code, _, err = self.run_cli("commit")
        self.assertEqual(code, 1)
        self.assertIn("[ERROR] 인증 실패 (HTTP 401): bad key", err)

    def test_unexpected_exception_is_reported_without_traceback(self) -> None:
        FakeClient.queue = [RuntimeError("boom")]
        code, _, err = self.run_cli("commit")
        self.assertEqual(code, 1)
        self.assertIn("[ERROR] 예상하지 못한 오류 (RuntimeError): boom", err)
        self.assertNotIn("Traceback", err)

    def test_keyboard_interrupt_exits_130(self) -> None:
        FakeClient.queue = [KeyboardInterrupt()]
        code, _, err = self.run_cli("commit")
        self.assertEqual(code, 130)
        self.assertIn("중단", err)


class ConventionCliTest(CliTestCase):
    """컨벤션 파일은 작업 디렉터리에서 찾으므로 임시 디렉터리로 이동해 실행한다."""

    def setUp(self) -> None:
        super().setUp()
        self._cwd = os.getcwd()
        os.chdir(self._tmp.name)

    def tearDown(self) -> None:
        os.chdir(self._cwd)
        super().tearDown()

    def _write(self, data: dict, name: str = ".ai-gitgen.json") -> str:
        import json

        path = os.path.join(self._tmp.name, name)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False)
        return path

    def test_file_in_cwd_changes_prompt_and_strips_scope(self) -> None:
        self._write({"commit": {"scope": "forbidden", "rules": ["파일 이름 뒤 조사는 띄어 쓴다"]}})
        FakeClient.queue = [result(GOOD_COMMIT)]
        code, out, err = self.run_cli("commit")
        self.assertEqual(code, 0)
        self.assertIn("[INFO] 컨벤션 적용: ", err)
        self.assertIn(".ai-gitgen.json", err)
        self.assertIn("조사는 띄어 쓴다", self.client.prompts_seen[0][0])
        self.assertIn("--- Commit Message ---\nfeat: 인사 문구 변경 및 반환값 추가", out)
        self.assertIn("스코프", err)  # 후처리 보정 경고

    def test_no_convention_flag_ignores_file(self) -> None:
        self._write({"commit": {"scope": "forbidden"}})
        FakeClient.queue = [result(GOOD_COMMIT)]
        _, out, err = self.run_cli("commit", "--no-convention")
        self.assertNotIn("컨벤션 적용", err)
        self.assertIn("feat(app): 인사 문구", out)

    def test_explicit_path_and_pr_extras(self) -> None:
        path = self._write(
            {"pr": {"test_command": "python -m unittest discover -s tests -t .", "checklist": ["테스트 통과"], "footer": "초안은 ai-gitgen 으로 생성"}},
            name="team.json",
        )
        FakeClient.queue = [result(GOOD_PR)]
        code, out, err = self.run_cli("pr", "--convention", path)
        self.assertEqual(code, 0)
        self.assertIn("python -m unittest discover -s tests -t .", self.client.prompts_seen[0][0])
        self.assertIn("## Checklist\n- [ ] 테스트 통과", out)
        self.assertIn("초안은 ai-gitgen 으로 생성", out)

    def test_both_convention_flags_is_an_error(self) -> None:
        code, _, err = self.run_cli("commit", "--convention", "x.json", "--no-convention")
        self.assertEqual(code, 2)
        self.assertIn("함께 쓸 수 없습니다", err)

    def test_invalid_file_fails_before_api_call(self) -> None:
        self._write({"commit": {"scope": "maybe"}})
        code, _, err = self.run_cli("commit")
        self.assertEqual(code, 2)
        self.assertIn("[ERROR]", err)
        self.assertIn("commit.scope", err)
        self.assertEqual(self.created, [])

    def test_convention_show_and_init(self) -> None:
        code, out, _ = self.run_cli("convention", "show")
        self.assertEqual(code, 0)
        self.assertIn("기본값", out)
        code, _, err = self.run_cli("convention", "init")
        self.assertEqual(code, 0)
        self.assertTrue(os.path.exists(os.path.join(self._tmp.name, ".ai-gitgen.json")))
        self.assertIn("[DONE]", err)
        code, _, err = self.run_cli("convention", "init")
        self.assertEqual(code, 2)  # 설정·사용법 오류: 기존 파일을 덮어쓰지 않는다
        self.assertIn("이미 있습니다", err)
        code, out, _ = self.run_cli("convention", "show")
        self.assertIn(".ai-gitgen.json", out)

    def test_convention_init_reports_os_errors(self) -> None:
        os.chmod(self._tmp.name, 0o500)
        try:
            code, _, err = self.run_cli("convention", "init")
        finally:
            os.chmod(self._tmp.name, 0o700)
        self.assertEqual(code, 1)
        self.assertIn("만들 수 없습니다", err)


class SafeModePolicyCliTest(ConventionCliTest):
    def test_cli_options_override_policy_and_are_logged(self) -> None:
        code, out, err = self.run_cli(
            "commit", "--dry-run", "--safe-mode", "--max-files", "3", "--max-lines", "40",
            "--exclude", "*.md", "--mask", r"INTERNAL_ID=EMP-\d{6}", "--context", "사번 EMP-123456 요청으로 수정",
        )
        self.assertEqual(code, 0)
        self.assertIn("[INFO] safe-mode 정책: 파일 3개 · 파일당 40줄 · 전체 2000줄 · 제외 패턴 11개 · 마스킹 규칙 10개", err)
        self.assertIn("[MASKED:INTERNAL_ID]", out)
        self.assertNotIn("EMP-123456", out)

    def test_policy_options_without_safe_mode_warn(self) -> None:
        code, _, err = self.run_cli("commit", "--dry-run", "--max-files", "3")
        self.assertEqual(code, 0)
        self.assertIn("[WARN] --max-files/--max-lines/--exclude/--mask 는 --safe-mode 와 함께 쓸 때만 적용됩니다", err)

    def test_bad_mask_option_is_rejected_before_api_call(self) -> None:
        code, _, err = self.run_cli("commit", "--safe-mode", "--mask", "bad")
        self.assertEqual(code, 2)
        self.assertIn("--mask", err)
        self.assertEqual(self.created, [])
        for value in ("0", "-1", "201"):
            code, _, err = self.run_cli("commit", "--safe-mode", "--max-files", value)
            self.assertEqual(code, 2, value)
            self.assertIn("--max-files 는 1~200", err)
        self.assertEqual(self.created, [])

    def test_weakened_policy_is_warned_every_run(self) -> None:
        self._write({"safe_mode": {"disabled_rules": ["EMAIL"], "global_max_lines": 5000, "max_files": 20}})
        code, _, err = self.run_cli("commit", "--dry-run", "--safe-mode")
        self.assertEqual(code, 0)
        self.assertIn("[WARN] safe-mode: 내장 마스킹 규칙 비활성 — EMAIL (출처: ", err)
        self.assertIn("[WARN] safe-mode: 전송 상한이 기본값보다 큽니다 — 파일 20 (기본 10), 전체 줄 5000 (기본 2000)", err)
        _, _, err_off = self.run_cli("commit", "--dry-run")
        self.assertNotIn("내장 마스킹 규칙 비활성", err_off)  # safe-mode 가 아니면 정책 자체가 쓰이지 않는다

    def test_file_policy_is_applied_and_shown(self) -> None:
        self._write({"safe_mode": {"max_files": 4, "mask_rules": [{"name": "ORDER_ID", "pattern": "ORD-[0-9]{8}"}], "disabled_rules": ["EMAIL"]}})
        code, out, err = self.run_cli("commit", "--dry-run", "--safe-mode", "--context", "ORD-12345678 건, 문의 dev@example.com")
        self.assertEqual(code, 0)
        self.assertIn("파일 4개 · 파일당 200줄", err)
        self.assertIn("마스킹 규칙 9개", err)  # 내장 9 - EMAIL 1 + ORDER_ID 1
        self.assertIn("[MASKED:ORDER_ID]", out)
        self.assertIn("dev@example.com", out)  # EMAIL 규칙 비활성
        code, out, _ = self.run_cli("convention", "show")
        self.assertIn("[safe_mode]", out)
        self.assertIn("ORDER_ID", out)


if __name__ == "__main__":
    unittest.main()
