"""옵션 해석과 최상위 예외 처리."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from . import __version__, commands, config, formatter
from .errors import AiGitgenError
from .model_registry import ModelRegistry

EXIT_INTERRUPTED = 130


def _add_generation_options(parser: argparse.ArgumentParser, kind: str) -> None:
    parser.add_argument(
        "--provider",
        choices=config.PROVIDER_NAMES,
        default=config.default_provider(),
        help=f"AI API 제공자 (기본: {config.default_provider()}, 환경변수 {config.PROVIDER_ENV})",
    )
    parser.add_argument("--model", default=None, help=f"모델 ID (기본: claude {config.DEFAULT_MODELS['claude']}, openai {config.DEFAULT_MODELS['openai']})")
    parser.add_argument("--temperature", type=float, default=config.DEFAULT_TEMPERATURE, help=f"0.0~1.0 (기본: {config.DEFAULT_TEMPERATURE})")
    parser.add_argument("--max-tokens", type=int, default=None, help=f"출력 토큰 상한 (기본: {config.DEFAULT_MAX_TOKENS[kind]})")
    parser.add_argument("--safe-mode", action="store_true", help="민감정보 마스킹과 전송량 제한 적용")
    parser.add_argument("--context", default=None, help="변경 이유 한 줄. PR 의 Why 품질이 좋아집니다")
    parser.add_argument("--dry-run", action="store_true", help="API 를 호출하지 않고 프롬프트만 출력")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=config.APP_NAME,
        description="git 변경 사항으로 커밋 메시지와 PR 초안을 생성합니다. 결과는 초안이며 검토 후 적용하세요.",
    )
    parser.add_argument("--version", action="version", version=f"{config.APP_NAME} {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    commit = sub.add_parser("commit", help="커밋 메시지 생성")
    _add_generation_options(commit, "commit")
    pr = sub.add_parser("pr", help="PR 제목/본문 초안 생성")
    _add_generation_options(pr, "pr")

    models = sub.add_parser("models", help="temperature 미지원 모델 목록 관리")
    models_sub = models.add_subparsers(dest="models_command", required=True)
    models_sub.add_parser("list", help="목록 출력")
    add = models_sub.add_parser("add", help="학습 목록에 수동 추가")
    add.add_argument("model_id")
    add.add_argument("--provider", choices=config.PROVIDER_NAMES, default=config.default_provider())
    add.add_argument("--reason", default="수동 등록")
    remove = models_sub.add_parser("remove", help="목록에서 제거 (내장 모델은 제외 목록에 기록)")
    remove.add_argument("model_id")
    remove.add_argument("--provider", choices=config.PROVIDER_NAMES, default=config.default_provider())
    models_sub.add_parser("reset", help="학습·제외 목록 초기화")
    return parser


def _validate_args(args: argparse.Namespace) -> None:
    if args.command in ("commit", "pr"):
        if args.temperature is not None and not 0.0 <= args.temperature <= 1.0:
            raise AiGitgenError(f"--temperature 는 0.0~1.0 사이여야 합니다 (입력: {args.temperature})")
        if args.max_tokens is not None and args.max_tokens <= 0:
            raise AiGitgenError(f"--max-tokens 는 1 이상이어야 합니다 (입력: {args.max_tokens})")


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        _validate_args(args)
        registry = ModelRegistry(config.registry_path())
        if args.command == "models":
            return commands.run_models(args, registry)
        return commands.run_generate(args, args.command, registry)
    except AiGitgenError as exc:
        formatter.error(str(exc))
        return commands.EXIT_ERROR
    except KeyboardInterrupt:
        formatter.error("사용자가 중단했습니다.")
        return EXIT_INTERRUPTED
    except Exception as exc:  # noqa: BLE001 - 스택트레이스 대신 원인 한 줄을 보여 준다
        formatter.error(f"예상하지 못한 오류 ({type(exc).__name__}): {exc}")
        return commands.EXIT_ERROR
