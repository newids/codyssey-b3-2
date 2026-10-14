"""commit / pr / models 명령의 실행 흐름."""

from __future__ import annotations

import argparse
import functools
import sys
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path

from . import config, convention, formatter, prompts, validators
from .errors import AiGitgenError, MaskTimeoutError, UnsupportedParameterError
from .git_collector import collect_changes
from .model_registry import ModelRegistry
from .providers import AIClient, get_provider
from .records import CommitMessage, GenerationResult, GenerationSettings, GitChanges, Prompt, SanitizedDiff
from .sanitizer import active_rules, find_sensitive, sanitize

REVIEW_REMINDER = "AI 초안입니다. 내용을 검토·수정한 뒤 적용하세요 (이 도구는 git 에 쓰지 않습니다)"


POLICY_OPTIONS = ("max_files", "max_lines", "exclude", "mask")


def _effective_policy(args: argparse.Namespace, team: convention.Convention) -> convention.SafeModePolicy:
    """설정 파일의 safe_mode 정책 위에 CLI 옵션을 덮어쓴다. 옵션 값은 cli._validate_args 가 먼저 검사한다."""
    policy = team.safe_mode
    if any(getattr(args, name, None) for name in POLICY_OPTIONS) and not args.safe_mode:
        formatter.warn("--max-files/--max-lines/--exclude/--mask 는 --safe-mode 와 함께 쓸 때만 적용됩니다.")
    cli_rules = tuple(convention.parse_mask_option(value) for value in (args.mask or ()))
    merged = replace(
        policy,
        max_files=policy.max_files if args.max_files is None else args.max_files,
        max_lines_per_file=policy.max_lines_per_file if args.max_lines is None else args.max_lines,
        exclude=policy.exclude + tuple(args.exclude or ()),
        mask_rules=policy.mask_rules + cli_rules,
    )
    if args.safe_mode:
        _warn_weakened_policy(merged, team.source)
    return merged


def _warn_weakened_policy(policy: convention.SafeModePolicy, source: str | None) -> None:
    """저장소가 준 설정이 보호를 약하게 만들면 매 실행마다 알린다."""
    origin = source or "CLI 옵션"
    if policy.disabled_rules:
        formatter.warn(f"safe-mode: 내장 마스킹 규칙 비활성 — {', '.join(policy.disabled_rules)} (출처: {origin})")
    default = convention.SafeModePolicy()
    raised = [
        f"{label} {value} (기본 {base})"
        for label, value, base in (
            ("파일", policy.max_files, default.max_files),
            ("파일당 줄", policy.max_lines_per_file, default.max_lines_per_file),
            ("전체 줄", policy.global_max_lines, default.global_max_lines),
        )
        if value > base
    ]
    if raised:
        formatter.warn(f"safe-mode: 전송 상한이 기본값보다 큽니다 — {', '.join(raised)} (출처: {origin})")


def _describe_policy(policy: convention.SafeModePolicy) -> str:
    return (
        f"파일 {policy.max_files}개 · 파일당 {policy.max_lines_per_file}줄 · 전체 {policy.global_max_lines}줄"
        f" · 제외 패턴 {len(policy.excluded_patterns)}개 · 마스킹 규칙 {len(active_rules(policy))}개"
    )


def _warn_unprotected(changes: GitChanges, sanitized: SanitizedDiff, policy: convention.SafeModePolicy) -> None:
    """safe-mode 가 꺼진 채 민감정보 후보가 보이면 전송 전에 알린다. 막지는 않는다 (스크립트 사용을 깨지 않기 위해).

    검사 대상은 실제로 전송될 텍스트(전체 줄 상한 적용 후)다. 사용자 규칙이 시간 제한에 걸려도 실행은 계속한다.
    """
    try:
        findings = find_sensitive(sanitized.text, tuple(f.path for f in changes.files), policy)
    except MaskTimeoutError as exc:
        formatter.warn(f"민감정보 사전 검사를 건너뜁니다: {exc}")
        return
    if findings.is_empty:
        return
    parts = []
    if findings.rule_counts:
        detail = ", ".join(f"{name} {count}" for name, count in findings.rule_counts)
        parts.append(f"민감정보로 보이는 값 {findings.match_total}개 ({detail})")
    if findings.excluded_paths:
        parts.append(f"비밀 파일로 분류되는 파일 {len(findings.excluded_paths)}개 ({', '.join(findings.excluded_paths)})")
    formatter.warn(
        "safe-mode 꺼짐: " + " · ".join(parts) + " 이(가) 그대로 전송됩니다.\n"
        "       --safe-mode 를 켜거나 (값은 [MASKED:...] 로, 파일은 이름만), 보내도 되는지 확인한 뒤 진행하세요."
    )


def _log_collection(changes: GitChanges, sanitized: SanitizedDiff, kind: str, policy: convention.SafeModePolicy) -> None:
    if kind == "pr":
        formatter.info(f"현재 브랜치: {changes.branch}")
        if changes.base_branch:
            formatter.info(f"기준 브랜치 {changes.base_branch} 이후 커밋 {len(changes.commit_subjects)}개 포함")
        else:
            formatter.warn("기준 브랜치를 찾지 못해 미커밋 변경만 사용합니다. --base 로 지정할 수 있습니다.")
    formatter.info(f"Git status 수집 완료: {len(changes.files)}개 파일 변경 감지")
    formatter.info(f"Git diff 수집 완료: {changes.line_count}줄")
    if sanitized.safe_mode:
        formatter.info(f"safe-mode 정책: {_describe_policy(policy)}")
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


def _note_title_length(message: CommitMessage, team: convention.Convention) -> None:
    """권장(soft)·최대(hard) 길이 차이를 결과와 함께 알린다. hard 초과는 이미 후처리로 잘렸다."""
    rules = team.commit
    length = len(message.title)
    if length <= rules.title_soft_limit:
        return
    formatter.info(
        f"제목 {length}자: 권장 {rules.title_soft_limit}자를 넘었습니다 (최대 {rules.title_hard_limit}자)."
        " 더 짧게 쓰려면 괄호 보충 설명을 본문으로 옮기세요."
    )


def _log_usage(client: AIClient, results: list[GenerationResult]) -> None:
    input_total = sum(r.input_tokens for r in results)
    output_total = sum(r.output_tokens for r in results)
    formatter.info(
        f"AI API 호출 횟수: {client.call_count}회 / 토큰 사용: 입력 {formatter.format_int(input_total)} · 출력 {formatter.format_int(output_total)}"
    )


def _load_convention(args: argparse.Namespace) -> convention.Convention:
    """--no-convention 이면 기본값, 아니면 --convention 경로 또는 작업 디렉터리의 .ai-gitgen.json."""
    if getattr(args, "no_convention", False):
        return convention.DEFAULT_CONVENTION
    loaded = convention.load_convention(getattr(args, "convention", None))
    if not loaded.is_default:
        formatter.info(f"컨벤션 적용: {loaded.source}")
    return loaded


def run_generate(args: argparse.Namespace, kind: str, registry: ModelRegistry) -> int:
    team = _load_convention(args)  # 설정 파일·URL·키 오류는 git 수집과 API 호출 전에 알린다
    config.validate_api_base_url()
    credential = None
    if not args.dry_run:  # dry-run 은 API 를 안 부르므로 키가 필요 없다
        credential = config.resolve_api_key(args.provider)
        formatter.info(f"API 키 확인: {credential.env_name} 설정됨")
    policy = _effective_policy(args, team)
    team = replace(team, safe_mode=policy)  # 프롬프트의 브랜치·메모 마스킹도 같은 규칙을 쓴다
    if kind == "pr":
        changes = collect_changes(include_branch=True, base=getattr(args, "base", None))
    else:
        changes = collect_changes()
    if changes.is_empty:
        target = "커밋 메시지를" if kind == "commit" else "PR 초안을"
        formatter.info(f"변경 사항이 없습니다. {target} 생성하지 않고 종료합니다 (종료 코드 {config.EXIT_NO_CHANGES}).")
        return config.EXIT_NO_CHANGES

    sanitized = sanitize(changes.diff_text, safe_mode=args.safe_mode, policy=policy)
    _log_collection(changes, sanitized, kind, policy)
    if not args.safe_mode:
        _warn_unprotected(changes, sanitized, policy)
    build = prompts.build_commit_prompt if kind == "commit" else prompts.build_pr_prompt
    prompt = build(changes, sanitized, args.context, team)
    settings = _resolve_settings(args, registry, kind)

    if args.dry_run:
        formatter.info(f"dry-run: API 를 호출하지 않습니다 ({_describe(settings)})")
        sys.stdout.write(formatter.render_prompt_preview(prompt.system, prompt.user))
        return config.EXIT_OK

    client = AIClient(get_provider(args.provider), credential.key)
    result, settings = _generate_with_fallback(client, prompt, settings, registry)
    results = [result]
    _warn_stop_reason(result)

    parse, validate, polish = _validators_for(kind, team)
    draft = parse(result.text)
    report = validate(draft)
    if report.needs_regeneration and result.stop_reason == "max_tokens":
        # 잘려서 구조가 깨진 출력은 다시 요청해도 같은 자리에서 잘린다. 호출을 아끼고 원인을 알린다
        formatter.warn("출력이 잘려 구조가 깨졌습니다. 재생성하지 않고 후처리만 합니다. --max-tokens 를 늘려 다시 실행하세요.")
    elif report.needs_regeneration and client.call_count < config.MAX_API_CALLS_PER_RUN:
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
        _note_title_length(final, team)
        formatter.done(f"커밋 메시지 생성 완료. {REVIEW_REMINDER}")
        sys.stdout.write("\n" + formatter.render_commit(final))
    else:
        formatter.done(f"PR 초안 생성 완료. {REVIEW_REMINDER}")
        sys.stdout.write("\n" + formatter.render_pr(final))
    return config.EXIT_OK


def _validators_for(kind: str, team: convention.Convention) -> tuple[Callable, Callable, Callable]:
    """kind 에 맞는 (파싱, 검증, 후처리) 함수. 컨벤션을 미리 바인딩한다."""
    if kind == "commit":
        return (
            functools.partial(validators.parse_commit_text, convention=team),
            functools.partial(validators.validate_commit, convention=team),
            functools.partial(validators.polish_commit, convention=team),
        )
    return (
        validators.parse_pr_text,
        functools.partial(validators.validate_pr, convention=team),
        functools.partial(validators.polish_pr, convention=team),
    )


def run_convention(args: argparse.Namespace) -> int:
    if args.convention_command == "show":
        sys.stdout.write(convention.describe(convention.load_convention(args.convention)))
        return config.EXIT_OK
    target = Path.cwd() / config.CONVENTION_FILE_NAME
    try:
        with open(target, "x", encoding="utf-8") as fh:  # 배타적 생성: 기존 파일·심볼릭 링크를 덮어쓰지 않는다
            fh.write(convention.template_json())
    except FileExistsError:
        formatter.error(f"{target} 가 이미 있습니다. 내용을 확인하려면 `convention show` 를 실행하세요.")
        return config.EXIT_USAGE
    except OSError as exc:
        raise AiGitgenError(f"컨벤션 파일을 만들 수 없습니다: {target} ({exc.strerror})") from exc
    formatter.done(f"기본 컨벤션 파일을 만들었습니다: {target}\n값을 저장소 규칙에 맞게 고친 뒤 commit / pr 을 실행하세요.")
    return config.EXIT_OK


def run_models(args: argparse.Namespace, registry: ModelRegistry) -> int:
    action = args.models_command
    if action == "list":
        sys.stdout.write(formatter.render_registry_table(registry.entries(), str(registry.path)))
        return config.EXIT_OK
    if action == "add":
        registry.record_rejection(args.provider, args.model_id, args.reason)
        formatter.done(f"'{args.provider}:{args.model_id}' 를 temperature 미지원 목록에 추가했습니다.")
        return config.EXIT_OK
    if action == "remove":
        if registry.remove(args.provider, args.model_id):
            formatter.done(f"'{args.provider}:{args.model_id}' 를 목록에서 제거했습니다.")
            return config.EXIT_OK
        formatter.error(f"'{args.provider}:{args.model_id}' 는 목록에 없습니다.")
        return config.EXIT_ERROR
    registry.reset()
    formatter.done("학습 목록과 제외 목록을 초기화했습니다. 내장 목록은 유지됩니다.")
    return config.EXIT_OK
