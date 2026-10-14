"""옵션 해석과 최상위 예외 처리."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from . import __version__, commands, config, convention, formatter
from .errors import AiGitgenError, ConfigurationError, UsageError
from .model_registry import ModelRegistry

EXIT_CODE_HELP = (
    "종료 코드: 0 성공 / 1 실행 오류(API 응답·git 실패) / 2 설정·사용법 오류(옵션 값, API 키 없음, 설정 파일) / "
    "3 변경 사항 없음 / 130 사용자 중단. "
    "결과 블록은 stdout, [INFO]/[WARN]/[ERROR] 로그는 stderr 로 나가므로 `commit > msg.txt` 처럼 결과만 저장할 수 있습니다."
)


def _add_generation_options(parser: argparse.ArgumentParser, kind: str) -> None:
    parser.add_argument(
        "--provider",
        choices=config.PROVIDER_NAMES,
        default=config.default_provider(),
        help=f"AI API 제공자 (기본: {config.default_provider()}, 환경변수 {config.PROVIDER_ENV})",
    )
    parser.add_argument(
        "--model",
        default=None,
        help=(
            f"모델 ID (기본: 환경변수 {config.MODEL_ENV}, 없으면 claude {config.DEFAULT_MODELS['claude']} / openai {config.DEFAULT_MODELS['openai']}). "
            "같은 diff 를 다른 모델로 돌려 품질·비용을 비교하거나, 재현을 위해 모델을 고정할 때 지정"
        ),
    )
    parser.add_argument(
        "--fast",
        action="store_true",
        help=f"작고 빠른 모델 사용 (환경변수 {config.FAST_MODEL_ENV}, 없으면 claude {config.FAST_MODELS['claude']} / openai {config.FAST_MODELS['openai']})",
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=config.DEFAULT_TEMPERATURE,
        help=(
            f"0.0~1.0 (기본: {config.DEFAULT_TEMPERATURE}). 낮을수록 같은 diff 에 거의 같은 결과(재현성), "
            "높을수록 표기·분량이 흔들림. 실험·비교 목적으로만 올리세요"
        ),
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=None,
        help=(
            f"출력 토큰 상한 (기본: {config.DEFAULT_MAX_TOKENS[kind]}). 목표 길이가 아니라 안전장치이며, "
            "부족하면 본문이 중간에 잘리고 [WARN] 이 출력됨. 비용은 실제 생성량만큼만 발생"
        ),
    )
    parser.add_argument("--safe-mode", action="store_true", help="민감정보 마스킹과 전송량 제한 적용")
    parser.add_argument("--max-files", type=int, default=None, metavar="N", help=f"safe-mode 최대 파일 수 (기본 {config.SAFE_MODE_MAX_FILES}, 설정 파일 safe_mode.max_files)")
    parser.add_argument("--max-lines", type=int, default=None, metavar="N", help=f"safe-mode 파일당 최대 줄 수 (기본 {config.SAFE_MODE_MAX_LINES_PER_FILE})")
    parser.add_argument("--exclude", action="append", default=None, metavar="GLOB", help="safe-mode 에서 이름만 보낼 파일 패턴 추가 (반복 가능)")
    parser.add_argument("--mask", action="append", default=None, metavar="NAME=REGEX", help="safe-mode 마스킹 규칙 추가 (반복 가능). 예: INTERNAL_ID=EMP-\\d{6}")
    parser.add_argument("--context", default=None, help="변경 이유 한 줄. PR 의 Why 품질이 좋아집니다")
    parser.add_argument("--dry-run", action="store_true", help="API 를 호출하지 않고 프롬프트만 출력")
    parser.add_argument("--convention", default=None, metavar="PATH", help=f"팀 컨벤션 설정 파일 (기본: 현재 디렉터리의 {config.CONVENTION_FILE_NAME})")
    parser.add_argument("--no-convention", action="store_true", help="설정 파일이 있어도 기본 컨벤션 사용")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=config.APP_NAME,
        description="git 변경 사항으로 커밋 메시지와 PR 초안을 생성합니다. 결과는 초안이며 검토 후 적용하세요.",
        epilog=EXIT_CODE_HELP,
    )
    parser.add_argument("--version", action="version", version=f"{config.APP_NAME} {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    commit = sub.add_parser("commit", help="커밋 메시지 생성")
    _add_generation_options(commit, "commit")
    pr = sub.add_parser("pr", help="PR 제목/본문 초안 생성 (기준 브랜치 이후 커밋 + 미커밋 변경)")
    _add_generation_options(pr, "pr")
    pr.add_argument("--base", default=None, help="비교 기준 브랜치 (기본: origin/HEAD → main → master 자동 탐지)")

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

    conv = sub.add_parser("convention", help=f"팀 컨벤션 설정 파일({config.CONVENTION_FILE_NAME}) 관리")
    conv_sub = conv.add_subparsers(dest="convention_command", required=True)
    show = conv_sub.add_parser("show", help="적용될 컨벤션 값 출력")
    show.add_argument("--convention", default=None, metavar="PATH", help="확인할 설정 파일 경로")
    conv_sub.add_parser("init", help=f"현재 디렉터리에 기본값으로 채운 {config.CONVENTION_FILE_NAME} 생성")
    return parser


def _validate_args(args: argparse.Namespace) -> None:
    if args.command in ("commit", "pr"):
        if args.temperature is not None and not 0.0 <= args.temperature <= 1.0:
            raise UsageError(f"--temperature 는 0.0~1.0 사이여야 합니다 (입력: {args.temperature})")
        if args.max_tokens is not None and args.max_tokens <= 0:
            raise UsageError(f"--max-tokens 는 1 이상이어야 합니다 (입력: {args.max_tokens})")
        if args.model and args.fast:
            raise UsageError("--model 과 --fast 는 함께 쓸 수 없습니다. 하나만 지정하세요.")
        if args.convention and args.no_convention:
            raise UsageError("--convention 과 --no-convention 은 함께 쓸 수 없습니다.")
        for name, key, value in (("--max-files", "max_files", args.max_files), ("--max-lines", "max_lines_per_file", args.max_lines)):
            low, high = convention.LIMIT_RANGES[key]
            if value is not None and not low <= value <= high:
                raise UsageError(f"{name} 는 {low}~{high} 사이여야 합니다 (입력: {value})")
        for value in args.mask or ():
            convention.parse_mask_option(value)  # 형식·정규식 오류를 API 호출 전에 알린다


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        _validate_args(args)
        registry = ModelRegistry(config.registry_path())
        if args.command == "models":
            return commands.run_models(args, registry)
        if args.command == "convention":
            return commands.run_convention(args)
        return commands.run_generate(args, args.command, registry)
    except ConfigurationError as exc:  # 옵션·키·설정 파일: 고치고 다시 실행하면 된다
        formatter.error(str(exc))
        return config.EXIT_USAGE
    except AiGitgenError as exc:
        formatter.error(str(exc))
        return config.EXIT_ERROR
    except KeyboardInterrupt:
        formatter.error("사용자가 중단했습니다.")
        return config.EXIT_INTERRUPTED
    except Exception as exc:  # noqa: BLE001 - 스택트레이스 대신 원인 한 줄을 보여 준다
        formatter.error(f"예상하지 못한 오류 ({type(exc).__name__}): {exc}")
        return config.EXIT_ERROR
