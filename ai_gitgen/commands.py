"""commit / pr / models 명령의 실행 흐름."""

from __future__ import annotations

import argparse
import sys
from dataclasses import replace

from . import config, formatter, prompts, validators
from .errors import AiGitgenError, UnsupportedParameterError
from .git_collector import collect_changes
from .model_registry import ModelRegistry
from .providers import AIClient, get_provider
from .records import GenerationResult, GenerationSettings, GitChanges, Prompt, SanitizedDiff
from .sanitizer import sanitize

EXIT_OK = 0
EXIT_ERROR = 1


def _log_collection(changes: GitChanges, sanitized: SanitizedDiff, kind: str) -> None:
    if kind == "pr":
        formatter.info(f"현재 브랜치: {changes.branch}")
        if changes.base_branch:
            formatter.info(f"기준 브랜치 {changes.base_branch} 이후 커밋 {len(changes.commit_subjects)}개 포함")
        else:
            formatter.warn("기준 브랜치를 찾지 못해 미커밋 변경만 사용합니다. --base 로 지정할 수 있습니다.")
    formatter.info(f"Git status 수집 완료: {len(changes.files)}개 파일 변경 감지")
    formatter.info(f"Git diff 수집 완료: {changes.line_count}줄")
    if sanitized.safe_mode:
        formatter.info(f"safe-mode: {sanitized.masked_count}개 항목 마스킹, {len(sanitized.omitted_files)}개 파일 생략")
    if sanitized.truncated_lines:
        formatter.warn(f"diff {sanitized.truncated_lines}줄이 길이 제한으로 생략되었습니다. 큰 변경은 커밋을 나누는 것을 권장합니다.")


def _resolve_settings(args: argparse.Namespace, registry: ModelRegistry, kind: str) -> GenerationSettings:
    model = config.resolve_model(args.provider, args.model, args.fast)
    max_tokens = args.max_tokens or config.DEFAULT_MAX_TOKENS[kind]
    temperature: float | None = args.temperature
    source = registry.rejects_temperature(args.provider, model)
    if source and temperature is not None:
        formatter.warn(f"'{model}' 는 temperature 를 지원하지 않아 생략합니다 (출처: {source})")
        temperature = None
    return GenerationSettings(provider=args.provider, model=model, temperature=temperature, max_tokens=max_tokens)


def _describe(settings: GenerationSettings) -> str:
    temp = "없음" if settings.temperature is None else str(settings.temperature)
    base = config.api_base_url()
    via = f", url={base}" if base else ""
    return f"provider={settings.provider}, model={settings.model}, temperature={temp}, max_tokens={settings.max_tokens}{via}"


def _generate_with_fallback(
    client: AIClient, prompt: Prompt, settings: GenerationSettings, registry: ModelRegistry
) -> tuple[GenerationResult, GenerationSettings]:
    """temperature 때문에 400 이 나면 기록하고 temperature 없이 1회 재요청한다."""
    formatter.info(f"AI API 요청 중... ({_describe(settings)})")
    try:
        return client.generate(prompt.system, prompt.user, settings), settings
    except UnsupportedParameterError as exc:
        if settings.temperature is None:
            raise
        registry.record_rejection(settings.provider, exc.model, exc.reason)
        formatter.warn("temperature 미지원 모델로 기록했습니다. temperature 없이 다시 요청합니다")
        retried = replace(settings, temperature=None)
        formatter.info(f"AI API 요청 중... ({_describe(retried)})")
        return client.generate(prompt.system, prompt.user, retried), retried


def _warn_stop_reason(result: GenerationResult) -> None:
    if result.stop_reason == "max_tokens":
        formatter.warn("출력이 max_tokens 에서 잘렸습니다. --max-tokens 를 늘려 보세요.")
    elif result.stop_reason == "refusal":
        formatter.warn("모델이 요청을 거절했습니다. diff 내용을 확인하거나 --safe-mode 를 사용해 보세요.")


def _log_usage(client: AIClient, results: list[GenerationResult]) -> None:
    input_total = sum(r.input_tokens for r in results)
    output_total = sum(r.output_tokens for r in results)
    formatter.info(
        f"AI API 호출 횟수: {client.call_count}회 / 토큰 사용: 입력 {formatter.format_int(input_total)} · 출력 {formatter.format_int(output_total)}"
    )


def run_generate(args: argparse.Namespace, kind: str, registry: ModelRegistry) -> int:
    if kind == "pr":
        changes = collect_changes(include_branch=True, base=getattr(args, "base", None))
    else:
        changes = collect_changes()
    if changes.is_empty:
        target = "커밋 메시지를" if kind == "commit" else "PR 초안을"
        formatter.info(f"변경 사항이 없습니다. {target} 생성하지 않고 종료합니다.")
        return EXIT_OK

    sanitized = sanitize(changes.diff_text, safe_mode=args.safe_mode)
    _log_collection(changes, sanitized, kind)
    build = prompts.build_commit_prompt if kind == "commit" else prompts.build_pr_prompt
    prompt = build(changes, sanitized, args.context)
    settings = _resolve_settings(args, registry, kind)

    if args.dry_run:
        formatter.info(f"dry-run: API 를 호출하지 않습니다 ({_describe(settings)})")
        sys.stdout.write(formatter.render_prompt_preview(prompt.system, prompt.user))
        return EXIT_OK

    client = AIClient(get_provider(args.provider), config.load_api_key(args.provider))
    result, settings = _generate_with_fallback(client, prompt, settings, registry)
    results = [result]
    _warn_stop_reason(result)

    parse, validate, polish = (
        (validators.parse_commit_text, validators.validate_commit, validators.polish_commit)
        if kind == "commit"
        else (validators.parse_pr_text, validators.validate_pr, validators.polish_pr)
    )
    draft = parse(result.text)
    report = validate(draft)
    if report.needs_regeneration and client.call_count < config.MAX_API_CALLS_PER_RUN:
        formatter.warn("출력 구조가 규칙에 맞지 않아 1회 재생성합니다: " + "; ".join(report.problems))
        retry_prompt = prompts.build_regeneration_prompt(prompt, result.text, report.problems)
        formatter.info(f"AI API 요청 중... ({_describe(settings)})")
        try:
            retried = client.generate(retry_prompt.system, retry_prompt.user, settings)
        except AiGitgenError as exc:
            formatter.warn(f"재생성 요청이 실패해 첫 초안을 사용합니다: {exc}")
        else:
            results.append(retried)
            _warn_stop_reason(retried)
            draft = parse(retried.text)
            report = validate(draft)

    validators.ensure_title(draft.title)
    if not report.is_valid:
        formatter.warn("후처리로 보정한 항목: " + "; ".join(report.problems))
    final = polish(draft)
    _log_usage(client, results)

    if kind == "commit":
        formatter.done("커밋 메시지 생성 완료")
        sys.stdout.write("\n" + formatter.render_commit(final))
    else:
        formatter.done("PR 초안 생성 완료")
        sys.stdout.write("\n" + formatter.render_pr(final))
    return EXIT_OK


def run_models(args: argparse.Namespace, registry: ModelRegistry) -> int:
    action = args.models_command
    if action == "list":
        sys.stdout.write(formatter.render_registry_table(registry.entries(), str(registry.path)))
        return EXIT_OK
    if action == "add":
        registry.record_rejection(args.provider, args.model_id, args.reason)
        formatter.done(f"'{args.provider}:{args.model_id}' 를 temperature 미지원 목록에 추가했습니다.")
        return EXIT_OK
    if action == "remove":
        if registry.remove(args.provider, args.model_id):
            formatter.done(f"'{args.provider}:{args.model_id}' 를 목록에서 제거했습니다.")
            return EXIT_OK
        formatter.error(f"'{args.provider}:{args.model_id}' 는 목록에 없습니다.")
        return EXIT_ERROR
    registry.reset()
    formatter.done("학습 목록과 제외 목록을 초기화했습니다. 내장 목록은 유지됩니다.")
    return EXIT_OK
