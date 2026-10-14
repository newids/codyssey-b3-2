import os
import unittest
from unittest import mock

from ai_gitgen import config
from ai_gitgen.errors import ConfigurationError, MissingApiKeyError


class ResolveApiKeyTest(unittest.TestCase):
    def setUp(self) -> None:
        self._env = mock.patch.dict(os.environ, {}, clear=False)
        self._env.start()
        for name in ("AI_API_KEY", "ANTHROPIC_API_KEY", "OPENAI_API_KEY"):
            os.environ.pop(name, None)

    def tearDown(self) -> None:
        self._env.stop()

    def test_common_variable_wins_over_provider_variable(self) -> None:
        os.environ.update({"AI_API_KEY": " common ", "ANTHROPIC_API_KEY": "specific"})
        credential = config.resolve_api_key("claude")
        self.assertEqual((credential.key, credential.env_name), ("common", "AI_API_KEY"))

    def test_credential_repr_hides_the_key(self) -> None:
        credential = config.ApiCredential(key="sk-secret-value", env_name="AI_API_KEY")
        self.assertNotIn("secret", repr(credential))
        self.assertNotIn("secret", str(credential))
        self.assertIn("AI_API_KEY", repr(credential))

    def test_provider_variable_is_used_when_common_is_blank(self) -> None:
        os.environ.update({"AI_API_KEY": "   ", "OPENAI_API_KEY": "specific"})
        credential = config.resolve_api_key("openai")
        self.assertEqual((credential.key, credential.env_name), ("specific", "OPENAI_API_KEY"))

    def test_missing_key_is_a_configuration_error_with_hint(self) -> None:
        with self.assertRaises(MissingApiKeyError) as ctx:
            config.resolve_api_key("openai")
        self.assertIsInstance(ctx.exception, ConfigurationError)
        message = str(ctx.exception)
        self.assertIn("AI_API_KEY 환경변수가 설정되지 않았습니다", message)
        self.assertIn("(또는 OPENAI_API_KEY)", message)
        self.assertIn("--dry-run", message)

    def test_exit_codes_are_distinct(self) -> None:
        codes = (config.EXIT_OK, config.EXIT_ERROR, config.EXIT_USAGE, config.EXIT_NO_CHANGES, config.EXIT_INTERRUPTED)
        self.assertEqual(codes, (0, 1, 2, 3, 130))
