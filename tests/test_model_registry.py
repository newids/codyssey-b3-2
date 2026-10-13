import json
import tempfile
import unittest
from pathlib import Path

from ai_gitgen.errors import RegistryError
from ai_gitgen.model_registry import SOURCE_BUILTIN, SOURCE_EXCLUDED, SOURCE_LEARNED, ModelRegistry


class ModelRegistryTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.path = Path(self._tmp.name) / "nested" / "model_registry.json"

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_builtin_models_are_rejected_without_file(self) -> None:
        registry = ModelRegistry(self.path)
        self.assertEqual(registry.rejects_temperature("claude", "claude-opus-5-5"), SOURCE_BUILTIN)
        self.assertEqual(registry.rejects_temperature("openai", "gpt-5-mini"), SOURCE_BUILTIN)
        self.assertIsNone(registry.rejects_temperature("claude", "claude-sonnet-4-6"))
        # 모델 ID 는 제공자 간에 겹치지 않으므로, 프록시를 거쳐 다른 형식으로 불러도 내장 목록이 적용된다
        self.assertEqual(registry.rejects_temperature("openai", "claude-opus-5-5"), SOURCE_BUILTIN)
        self.assertFalse(self.path.exists())  # 조회만으로는 파일을 만들지 않는다

    def test_record_rejection_persists_and_counts(self) -> None:
        registry = ModelRegistry(self.path)
        registry.record_rejection("openai", "new-model", "temperature unsupported")
        registry.record_rejection("openai", "new-model", "temperature unsupported")

        reloaded = ModelRegistry(self.path)
        self.assertTrue(reloaded.rejects_temperature("openai", "new-model").endswith(SOURCE_LEARNED))
        data = json.loads(self.path.read_text(encoding="utf-8"))
        self.assertEqual(data["no_temperature"]["openai:new-model"]["count"], 2)
        self.assertEqual(data["version"], 1)
        self.assertFalse(self.path.with_suffix(".tmp").exists())

    def test_remove_builtin_adds_to_exclusion_and_restores_temperature(self) -> None:
        registry = ModelRegistry(self.path)
        self.assertTrue(registry.remove("claude", "claude-opus-5-5"))
        self.assertIsNone(ModelRegistry(self.path).rejects_temperature("claude", "claude-opus-5-5"))
        data = json.loads(self.path.read_text(encoding="utf-8"))
        self.assertEqual(data["excluded_builtin"], ["claude:claude-opus-5-5"])

    def test_record_after_exclusion_reinstates_model(self) -> None:
        registry = ModelRegistry(self.path)
        registry.remove("claude", "claude-opus-5-5")
        registry.record_rejection("claude", "claude-opus-5-5", "still rejected")
        self.assertTrue(registry.rejects_temperature("claude", "claude-opus-5-5").endswith(SOURCE_LEARNED))

    def test_remove_unknown_model_returns_false(self) -> None:
        self.assertFalse(ModelRegistry(self.path).remove("claude", "nope"))

    def test_reset_clears_learned_and_excluded(self) -> None:
        registry = ModelRegistry(self.path)
        registry.record_rejection("claude", "x", "r")
        registry.remove("claude", "claude-opus-5-5")
        registry.reset()
        reloaded = ModelRegistry(self.path)
        self.assertIsNone(reloaded.rejects_temperature("claude", "x"))
        self.assertEqual(reloaded.rejects_temperature("claude", "claude-opus-5-5"), SOURCE_BUILTIN)

    def test_entries_show_all_sources(self) -> None:
        registry = ModelRegistry(self.path)
        registry.record_rejection("openai", "learned-model", "reason")
        registry.remove("claude", "claude-sonnet-5-5")
        by_model = {(e.provider, e.model): e for e in registry.entries()}
        self.assertEqual(by_model[("claude", "claude-opus-5-5")].source, SOURCE_BUILTIN)
        self.assertEqual(by_model[("claude", "claude-sonnet-5-5")].source, SOURCE_EXCLUDED)
        learned = by_model[("openai", "learned-model")]
        self.assertEqual((learned.source, learned.reason, learned.count), (SOURCE_LEARNED, "reason", "1"))

    def test_corrupt_file_raises_registry_error(self) -> None:
        self.path.parent.mkdir(parents=True)
        for content in ("{broken", "[1, 2]", '{"no_temperature": [1]}', '{"no_temperature": {"k": {"bogus": 1}}}'):
            self.path.write_text(content, encoding="utf-8")
            with self.assertRaises(RegistryError, msg=content) as ctx:
                ModelRegistry(self.path)
            self.assertIn("models reset", str(ctx.exception))

    def test_save_leaves_no_temp_files(self) -> None:
        registry = ModelRegistry(self.path)
        registry.record_rejection("claude", "m", "r")
        self.assertEqual([p.name for p in self.path.parent.iterdir()], ["model_registry.json"])

    def test_unwritable_location_raises_registry_error(self) -> None:
        blocked = Path(self._tmp.name) / "file"
        blocked.write_text("x", encoding="utf-8")
        registry = ModelRegistry(blocked / "model_registry.json")  # 부모가 파일이므로 mkdir 실패
        with self.assertRaises(RegistryError):
            registry.record_rejection("claude", "m", "r")


if __name__ == "__main__":
    unittest.main()
