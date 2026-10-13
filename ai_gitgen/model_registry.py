"""temperature 를 거부하는 모델의 내장 목록과 학습 목록을 관리한다."""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict, replace
from datetime import datetime, timezone
from pathlib import Path

from .errors import RegistryError
from .records import RegistryEntry, UnsupportedModelRecord

BUILTIN_NO_TEMPERATURE_MODELS: dict[str, frozenset[str]] = {
    "claude": frozenset(
        {
            "claude-fable-5-1",
            "claude-fable-5",
            "claude-opus-5-5",
            "claude-opus-5",
            "claude-opus-4-8",
            "claude-opus-4-7",
            "claude-sonnet-5-5",
            "claude-sonnet-5",
            "claude-haiku-5-5",
        }
    ),
    "openai": frozenset(
        {
            "gpt-5",
            "gpt-5-mini",
            "gpt-5-nano",
            "gpt-5.1",
            "gpt-5.2",
            "gpt-5.4",
            "gpt-5.4-mini",
            "gpt-5.4-nano",
            "gpt-5.5",
            "o1",
            "o3",
            "o3-mini",
            "o4-mini",
        }
    ),
}
SOURCE_BUILTIN = "내장 목록"
SOURCE_LEARNED = "학습"
SOURCE_EXCLUDED = "제외(내장)"
FILE_VERSION = 1


def registry_key(provider: str, model: str) -> str:
    return f"{provider}:{model}"


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def is_builtin(provider: str, model: str) -> bool:
    """내장 거부 목록에 있는가. 모델 ID 는 제공자 간에 겹치지 않으므로, 프록시(OpenAI 호환 형식으로
    Claude 모델을 호출하는 경우 등)를 고려해 제공자와 무관하게 전체 목록에서 찾는다."""
    del provider  # 키 생성에만 쓰이고 조회에는 쓰지 않는다
    return any(model in models for models in BUILTIN_NO_TEMPERATURE_MODELS.values())


class ModelRegistry:
    def __init__(self, path: Path) -> None:
        self._path = path
        self._learned: dict[str, UnsupportedModelRecord] = {}
        self._excluded_builtin: frozenset[str] = frozenset()
        self._load()

    @property
    def path(self) -> Path:
        return self._path

    def rejects_temperature(self, provider: str, model: str) -> str | None:
        """거부 모델이면 출처 문자열, 아니면 None."""
        key = registry_key(provider, model)
        if key in self._learned:
            return f"{self._learned[key].first_seen[:10]} {SOURCE_LEARNED}"
        if is_builtin(provider, model) and key not in self._excluded_builtin:
            return SOURCE_BUILTIN
        return None

    def record_rejection(self, provider: str, model: str, reason: str) -> UnsupportedModelRecord:
        """400 응답으로 알게 된 거부 모델을 기록한다. 같은 모델이면 횟수와 최근 시각만 갱신."""
        key = registry_key(provider, model)
        now = _now()
        previous = self._learned.get(key)
        record = (
            replace(previous, last_seen=now, count=previous.count + 1, reason=reason or previous.reason)
            if previous
            else UnsupportedModelRecord(reason=reason or "-", first_seen=now, last_seen=now)
        )
        self._learned = {**self._learned, key: record}
        self._excluded_builtin = self._excluded_builtin - {key}
        self._save()
        return record

    def remove(self, provider: str, model: str) -> bool:
        """학습 목록에서 지운다. 내장 모델이면 제외 목록에 넣는다. 바뀐 것이 없으면 False."""
        key = registry_key(provider, model)
        changed = key in self._learned
        self._learned = {k: v for k, v in self._learned.items() if k != key}
        if is_builtin(provider, model) and key not in self._excluded_builtin:
            self._excluded_builtin = self._excluded_builtin | {key}
            changed = True
        if changed:
            self._save()
        return changed

    def reset(self) -> None:
        self._learned = {}
        self._excluded_builtin = frozenset()
        self._save()

    def entries(self) -> tuple[RegistryEntry, ...]:
        """내장·학습·제외 항목을 표시용으로 모은다."""
        rows: list[RegistryEntry] = []
        for provider, models in BUILTIN_NO_TEMPERATURE_MODELS.items():
            for model in sorted(models):
                key = registry_key(provider, model)
                if key in self._learned:
                    continue
                source = SOURCE_EXCLUDED if key in self._excluded_builtin else SOURCE_BUILTIN
                reason = "사용자가 remove" if source == SOURCE_EXCLUDED else "-"
                rows.append(RegistryEntry(provider=provider, model=model, source=source, reason=reason))
        for key, record in sorted(self._learned.items()):
            provider, _, model = key.partition(":")
            rows.append(
                RegistryEntry(
                    provider=provider,
                    model=model,
                    source=SOURCE_LEARNED,
                    reason=record.reason,
                    last_seen=record.last_seen[:10],
                    count=str(record.count),
                )
            )
        return tuple(rows)

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                raise ValueError("최상위가 JSON 객체가 아닙니다")
            learned_raw = data.get("no_temperature") or {}
            excluded_raw = data.get("excluded_builtin") or []
            if not isinstance(learned_raw, dict) or not isinstance(excluded_raw, list):
                raise ValueError("필드 형식이 올바르지 않습니다")
            learned = {key: UnsupportedModelRecord(**record) for key, record in learned_raw.items()}
            excluded = frozenset(str(item) for item in excluded_raw)
        except (OSError, ValueError, TypeError, AttributeError) as exc:
            raise RegistryError(
                f"모델 레지스트리 파일을 읽을 수 없습니다: {self._path} ({exc})\n"
                "       `models reset` 으로 초기화하거나 파일을 삭제하세요."
            ) from exc
        self._learned, self._excluded_builtin = learned, excluded

    def _save(self) -> None:
        payload = {
            "version": FILE_VERSION,
            "no_temperature": {key: asdict(record) for key, record in self._learned.items()},
            "excluded_builtin": sorted(self._excluded_builtin),
        }
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(
                "w", encoding="utf-8", dir=self._path.parent, prefix=".registry-", suffix=".tmp", delete=False
            ) as handle:
                handle.write(json.dumps(payload, ensure_ascii=False, indent=2))
                temp_path = handle.name
            os.replace(temp_path, self._path)
        except OSError as exc:
            raise RegistryError(f"모델 레지스트리 파일을 저장할 수 없습니다: {self._path} ({exc})") from exc
