# 미션 수행 가이드 — B3-2 내가 고친 코드 설명을 AI가 대신 써주는 도우미

이 문서는 미션을 처음부터 끝까지 수행하는 순서를 정리한 것입니다.
무엇을 먼저 결정하고, 어떤 순서로 만들고, 각 단계가 끝났는지 어떻게 확인하는지를 다룹니다.
배경 지식은 [02-learning-materials.md](02-learning-materials.md), 평가 질문 답변은 [03-evaluation-answers.md](03-evaluation-answers.md),
프롬프트 원문은 [04-prompt-templates.md](04-prompt-templates.md), 도구 README 양식은 [05-readme-template.md](05-readme-template.md)에 있습니다.

## 1. 미션을 한 문장으로

> `git diff`를 AI API에 넘겨 **커밋 메시지와 PR 초안을 만들되, 결과 품질을 코드로 통제하는** 터미널 도구를 만든다.

핵심은 API 호출 자체가 아니라 세 가지입니다.

1. **입력 설계** — 어떤 git 정보를 어떤 형태로 넘기는가 (민감정보는 빼고, 양은 제한하고)
2. **프롬프트 설계** — 양식(커밋 규칙, PR 템플릿)을 어떻게 지시하는가
3. **출력 검증** — 길이·구조 규칙을 코드로 확인하고 어긋나면 어떻게 고치는가

평가에서 보는 다섯 가지 과제 목표와, 그것을 코드 어디에서 보여 줄지를 먼저 정합니다.

| 과제 목표 | 이 프로젝트에서 보여 줄 곳 |
| --- | --- |
| REST API 요청 구성·응답 처리·예외 대응 | `ai_client.py` (요청 본문, 헤더, HTTP 오류 분기) |
| `temperature`, `max_tokens` 가 품질에 주는 영향 | `cli.py` 옵션, README의 파라미터 설명, 실험 기록 |
| git 명령 결과를 프로그램 입력으로 연결 | `git_collector.py` (`subprocess` → 데이터클래스) |
| 양식과 맥락을 담은 프롬프트 구성 원리 | `prompts.py`, `docs/04-prompt-templates.md` |
| 실무 규칙에 맞게 검증·다듬는 이유와 방법 | `validators.py` (검증 → 재생성 또는 후처리) |

## 2. 요구사항 분석

### 2.1 반드시 지켜야 하는 것

| 영역 | 요구 |
| --- | --- |
| 실행 환경 | Python 3.10 이상, 터미널 전용, Git 저장소 루트에서 실행 |
| Git 수집 | `git status`, `git diff` 결과 수집. 변경 없으면 "변경 사항이 없습니다" 출력 후 종료 |
| API 연동 | 키는 환경변수로만. 실패 시 원인 포함 메시지. 모델·temperature·max_tokens 는 CLI 옵션으로 변경 가능 |
| `commit` 명령 | 제목 1줄 필수, 본문 선택. 본문이 있으면 파일/모듈 1~3개 언급 또는 핵심 변경 불릿 1~2개 |
| `pr` 명령 | 제목 1줄 + 본문. 본문에 `## Why`, `## What`, `## How to Test` 헤더와 각 섹션 불릿 1개 이상 |
| 출력 검증 | 커밋 제목 50자 권장·72자 최대, PR 제목 80자 최대, PR 섹션 구조. 검증 후 **재생성 또는 후처리 중 하나** |
| 출력 형식 | 구분선·헤더로 구획 분리 |
| 호출 횟수 | 1회 실행에 API 호출 1~2회. 호출 횟수를 로그로 출력 |
| 보안 | `--safe-mode` 로 (A) 패턴 마스킹 또는 (B) 전송량 제한 중 하나 이상 |
| 금지 | `git push`, GitHub PR 생성 API 등 원격 반영 기능 |
| 문서 | README에 설치, 환경변수, 사용 예시, 출력 예시, 민감정보 대응 또는 비용/요청 제한 안내 |

> 과제 문서의 옵션 표기는 `-model`, `-safe-mode` 처럼 하이픈 하나입니다. B2-1과 마찬가지로 문서 변환 과정에서 하나가 빠진 것으로 보고,
> Python `argparse` 관례인 `--model`, `--safe-mode` 로 구현합니다. README에 이 결정을 한 줄 적어 둡니다.

### 2.2 스스로 정해야 하는 것

코드를 쓰기 전에 정하고 README에 적습니다. 아래는 이 가이드가 권하는 선택입니다.

| 결정 항목 | 선택 | 이유 |
| --- | --- | --- |
| AI API 제공자 | Claude Messages API (`POST /v1/messages`) | 요청·응답 구조가 단순하고, 시스템 프롬프트 필드가 분리되어 양식 지시를 넣기 좋다 |
| 호출 방식 | 표준 라이브러리 `urllib.request` 로 직접 REST 호출 | 과제 목표 1이 "REST API 방식 연동 과정을 설명"이므로 헤더·본문·상태 코드를 직접 다루는 쪽이 학습 효과가 크다. SDK는 선택 사항으로 README에 안내 |
| 기본 모델 | `claude-sonnet-4-6` | 과제가 요구하는 `--temperature` 옵션을 받아 주는 모델 중 품질과 비용의 균형이 좋다. 자세한 사정은 2.3절 |
| `temperature` 거부 모델 처리 | 내장 목록 + 실행 중 학습한 목록을 레지스트리 파일로 관리, 자동으로 `temperature` 생략 | 사용자가 모델을 바꿔도 400 으로 실행이 실패하지 않고, 새로 거부하는 모델이 나와도 코드 수정 없이 대응된다. 2.3절, 3.4절 |
| 환경변수 이름 | `AI_API_KEY` (없으면 `ANTHROPIC_API_KEY` 도 확인) | 과제 예시(`export AI_API_KEY=...`)와 Anthropic SDK 관례를 모두 수용 |
| diff 범위 | 작업 트리 변경(`git diff`) + 스테이징 변경(`git diff --cached`) 합산 | 사용자가 `git add` 를 했든 안 했든 "지금 커밋할 내용"을 다 보여 준다 |
| 검증 실패 처리 | **후처리 우선**, 구조 결함(섹션 누락)만 1회 재생성 | 호출 1~2회 제한을 지키면서, 길이 초과처럼 기계적으로 고칠 수 있는 것은 API를 다시 부르지 않는다 |
| safe-mode 정책 | (A) 마스킹 + (B) 제한을 둘 다 적용. 기본 OFF, `--safe-mode` 로 ON | 보너스 3번(안전 모드 고도화)으로 이어지기 쉽다 |
| 출력 언어 | 한국어 본문, 커밋 prefix 는 영문(`feat:`, `fix:`) | 과제 예시와 같은 형태 |

### 2.3 `temperature` 와 모델 선택에 관한 주의

과제는 `--temperature` 옵션을 요구하지만, **최신 Claude 모델은 `temperature` 를 받지 않습니다.**

| 모델 | `temperature` | 비고 |
| --- | --- | --- |
| `claude-sonnet-4-6`, `claude-opus-4-6`, `claude-haiku-4-5` | 허용 | 이 과제의 기본 모델로 적합 |
| `claude-sonnet-5-5`, `claude-haiku-5-5` | 기본값 외 400 오류 | 사실상 사용 불가 |
| `claude-opus-5-5`, `claude-opus-5`, `claude-sonnet-5`, `claude-fable-5-1` | 필드 자체가 400 오류 | 대신 `output_config.effort` 로 깊이를 조절 |

따라서 도구는 다음처럼 동작해야 합니다.

- 기본 모델은 `temperature` 를 받는 `claude-sonnet-4-6` 으로 둔다. 저렴하게 실험하려면 `--model claude-haiku-4-5`.
- `temperature` 를 거부하는 모델은 **모델 레지스트리**(`model_registry.py`)로 관리한다. 레지스트리는 두 층이다.
  - **내장 목록**: 위 표의 "거부" 모델을 코드 상수로 둔다. 문서로 이미 알려진 사실이므로 요청 전에 `temperature` 를 빼고 `[WARN]` 으로 알린다.
  - **학습 목록**: 실행 중 400 응답의 `error.message` 에 `temperature` 가 언급되면, 그 모델 ID와 오류 메시지·시각을 사용자 홈의 JSON 파일에 기록한다. 다음 실행부터는 내장 목록과 같이 취급한다.
- 400 이 처음 발생한 그 실행에서는 `temperature` 를 빼고 **1회 자동 재요청**한다. 실패한 요청도 API 호출 1회이므로 호출 횟수에 포함하고, 그 실행에서는 구조 결함 재생성을 건너뛰어 총 호출을 2회 이내로 유지한다.
- 레지스트리는 `models` 서브커맨드(`list`, `add`, `remove`, `reset`)로 사용자가 직접 보고 고칠 수 있다. 상세는 3.4절과 4장 6-b단계.
- 평가 답변(과제 목표 2)에서는 "파라미터 지원 여부가 모델마다 다르며, 문서(내장 목록)와 400 응답(학습 목록) 두 경로로 확인한다"는 점까지 설명하면 좋다.

OpenAI API를 쓰는 경우에도 구조는 같습니다. 엔드포인트·헤더·본문 필드명만 `ai_client.py` 한 곳에서 바뀌도록 설계합니다.
OpenAI 쪽 대응표, 가격, `temperature` 거부 모델 목록, 오류 코드, 두 제공자 동시 지원 설계는 [06-openai-api.md](06-openai-api.md)에 있습니다.

## 3. 설계

### 3.1 데이터 흐름

```text
 사용자: python -m ai_gitgen commit --safe-mode
   │
   ▼
┌─────────────────────────────┐
│ cli.py        옵션 해석, 명령 분기, 종료 코드          │
└──────────────┬──────────────┘
               ▼
┌─────────────────────────────┐
│ git_collector.py  git status --porcelain / git diff   │ → GitChanges(files, diff_text, branch, line_count)
└──────────────┬──────────────┘            변경 없음 → "[INFO] 변경 사항이 없습니다" → exit 0
               ▼
┌─────────────────────────────┐
│ sanitizer.py   --safe-mode 시 마스킹 + 파일/줄 수 제한  │ → SanitizedDiff(text, masked_count, truncated)
└──────────────┬──────────────┘
               ▼
┌─────────────────────────────┐
│ prompts.py     시스템 프롬프트 + 사용자 프롬프트 조립   │ → (system, user)
└──────────────┬──────────────┘
               ▼
┌─────────────────────────────┐
│ model_registry.py  모델이 temperature 거부 목록에 있나? │ → 있으면 temperature 제거 + [WARN]
└──────────────┬──────────────┘
               ▼
┌─────────────────────────────┐
│ ai_client.py   POST /v1/messages, 오류 → AIError       │ → GenerationResult(text, usage, stop_reason)
└──────────────┬──────────────┘            호출 횟수 카운터 +1
               │  400 + "temperature" 언급 → 레지스트리에 기록 → temperature 빼고 1회 재요청
               ▼
┌─────────────────────────────┐
│ validators.py  길이·구조 검증 → 후처리 또는 1회 재생성  │ → CommitMessage / PullRequestDraft
└──────────────┬──────────────┘
               ▼
┌─────────────────────────────┐
│ formatter.py   [INFO]/[DONE] 로그, 구분선 블록 출력     │
└─────────────────────────────┘
```

### 3.2 모듈과 책임

| 모듈 | 하는 일 | 하지 않는 일 |
| --- | --- | --- |
| `cli.py` | `argparse` 로 `commit`/`pr`/`models` 서브커맨드와 옵션 정의, 옵션 값 범위 검증, 예외를 사용자 메시지로 변환, 종료 코드 | git 실행, HTTP 호출 |
| `commands.py` | 명령별 실행 흐름(수집 → safe-mode → 프롬프트 → 호출 → 검증 → 출력), 호출 횟수 제한, temperature 재요청과 구조 재생성 분기 | HTTP 전송, 파싱 |
| `config.py` | 기본값 상수(모델, temperature, max_tokens, safe-mode 한도, 길이 규칙), 환경변수 읽기 | 검증 로직 |
| `records.py` | 모듈 사이를 오가는 불변 데이터클래스 | 동작 |
| `git_collector.py` | `subprocess.run` 으로 git 명령 실행, 저장소 루트 확인, 결과를 `GitChanges` 로 묶음 | 민감정보 처리, 출력 |
| `sanitizer.py` | 정규식 마스킹, 제외 파일 필터, 파일 수·줄 수 제한 | git 호출 |
| `prompts.py` | 역할·규칙·양식·예시를 담은 템플릿 문자열과 조립 함수, 재생성 프롬프트 | HTTP 호출 |
| `model_registry.py` | `temperature` 거부 모델의 내장 목록(제공자별)과 학습 목록 관리. 조회, 기록, JSON 파일 읽기·쓰기 | HTTP 호출, 터미널 출력 |
| `providers.py` | 제공자(Claude/OpenAI)별 요청 본문·헤더 구성, 응답 파싱, 상태 코드별 예외 번역, `temperature` 400 감지, `urllib` 전송, 호출 카운터(`AIClient`) | 프롬프트 내용, 검증, 레지스트리 파일 입출력 |
| `validators.py` | 출력 파싱, 커밋/PR 규칙 검증, 후처리(절단·섹션 보강), 재생성 필요 여부 판단 | HTTP 호출 |
| `formatter.py` | 로그 접두어(`[INFO]`, `[WARN]`, `[ERROR]`, `[DONE]`)를 stderr 로, 구분선 블록과 표를 stdout 으로 | 업무 규칙 |
| `errors.py` | `MissingApiKeyError`, `AIRequestError`, `UnsupportedParameterError`, `RegistryError`, `GitCommandError`, `NotGitRepositoryError`, `OutputParseError` | — |

의존 방향은 `cli → commands → (git_collector, sanitizer, prompts, model_registry, providers, validators, formatter) → config/records/errors` 한쪽입니다.
`providers` 는 400 을 `UnsupportedParameterError` 로 바꿔 던지기만 하고, 레지스트리에 기록하고 재요청하는 일은 `commands` 가 `model_registry` 를 불러 처리합니다.

> 아래 4장의 코드 조각은 설계를 설명하기 위한 축약본입니다. 실제 구현은 `ai_gitgen/` 의 각 모듈을 보세요. 조각에서 `ai_client.generate(...)` 라고 쓴 부분은 구현에서 `providers.AIClient.generate(...)` 입니다.
`ai_client` 가 `prompts` 를 모르고 `validators` 가 `ai_client` 를 모르기 때문에, 테스트에서 HTTP 없이 검증 로직만 확인할 수 있습니다.

### 3.3 데이터 구조

```python
from dataclasses import dataclass, field

@dataclass(frozen=True)
class GitChanges:
    branch: str
    files: tuple[str, ...]        # git status --porcelain 에서 뽑은 경로
    diff_text: str                # git diff + git diff --cached
    line_count: int

    @property
    def is_empty(self) -> bool:
        return not self.files and not self.diff_text.strip()

@dataclass(frozen=True)
class SanitizedDiff:
    text: str
    masked_count: int             # 마스킹된 토큰 수 (로그용)
    omitted_files: tuple[str, ...]
    truncated_lines: int

@dataclass(frozen=True)
class GenerationResult:
    text: str
    input_tokens: int
    output_tokens: int
    stop_reason: str              # "end_turn" | "max_tokens" | "refusal" ...

@dataclass(frozen=True)
class CommitMessage:
    title: str
    body: str = ""

@dataclass(frozen=True)
class PullRequestDraft:
    title: str
    body: str                     # ## Why / ## What / ## How to Test

@dataclass(frozen=True)
class ValidationReport:
    is_valid: bool
    problems: tuple[str, ...] = field(default_factory=tuple)
    needs_regeneration: bool = False

@dataclass(frozen=True)
class UnsupportedModelRecord:
    model: str
    reason: str                   # API 가 돌려준 error.message
    first_seen: str               # ISO 8601
    last_seen: str
    count: int = 1
```

**`frozen=True` 와 `dataclasses.replace()` 에 대해.** `@dataclass(frozen=True)` 로 만든 객체는 생성 뒤에 필드 값을 바꿀 수 없습니다.
`msg.title = "..."` 처럼 대입하면 `FrozenInstanceError` 가 납니다. 그래서 제목을 72자로 자르는 것 같은 후처리는 기존 객체를 고치는 대신,
바뀐 값만 넣어 **새 객체를 하나 더 만드는** 방식으로 합니다. 그 일을 해 주는 함수가 `dataclasses.replace()` 입니다.

```python
from dataclasses import replace

original = CommitMessage(title="feat: 아주 긴 제목 ...", body="- 설명")
shortened = replace(original, title=original.title[:72])   # title 만 다른 새 객체. body 는 그대로 복사

print(original.title)    # 원래 제목 그대로
print(shortened.title)   # 잘린 제목
```

이렇게 하면 검증 함수가 받은 객체를 몰래 바꾸는 일이 없어, "입력은 그대로이고 출력은 잘렸다"를 테스트에서 둘 다 확인할 수 있습니다.
이 미션 규모에서 필수는 아니지만, 함수의 입력과 출력이 분명해져 디버깅이 쉬워집니다. 번거롭다면 `frozen=True` 를 빼고 일반 데이터클래스로 써도 과제 요구에는 문제가 없습니다.

### 3.4 모델 레지스트리 (`temperature` 거부 모델 관리)

`temperature` 를 거부하는 모델은 두 경로로 알게 됩니다. 문서로 미리 아는 것과, 실행 중 400 을 맞고 아는 것. 둘을 한 곳에서 관리합니다.

| 층 | 저장 위치 | 바뀌는 때 | 우선순위 |
| --- | --- | --- | --- |
| 내장 목록 | `model_registry.py` 의 상수 `BUILTIN_NO_TEMPERATURE_MODELS` | 코드 수정·배포 | 사용자가 `models remove` 로 빼더라도 다음 실행에는 다시 적용되지 않도록 "제외 목록"에 기록 |
| 학습 목록 | `~/.ai-gitgen/model_registry.json` | 실행 중 400 감지, `models add/remove/reset` | 내장 목록과 합쳐서 조회 |

파일 형식:

```json
{
  "version": 1,
  "no_temperature": {
    "claude-opus-5-5": {
      "reason": "temperature is not supported for this model",
      "first_seen": "2026-10-13T09:12:40+09:00",
      "last_seen": "2026-10-13T09:12:40+09:00",
      "count": 1
    }
  },
  "excluded_builtin": ["claude-sonnet-5-5"]
}
```

- `no_temperature`: 학습 목록. 같은 모델이 다시 걸리면 `last_seen` 과 `count` 만 갱신한다.
- `excluded_builtin`: 사용자가 `models remove` 로 내장 목록에서 뺀 모델. API 가 지원을 추가했을 때 코드 수정 없이 다시 쓸 수 있게 한다.
- 파일 위치는 환경변수 `AI_GITGEN_HOME` 으로 바꿀 수 있다 (테스트에서 임시 폴더를 쓰기 위해).

조회 규칙: `(내장 목록 − excluded_builtin) ∪ 학습 목록` 에 모델 ID가 있으면 "거부 모델"입니다.

실행 흐름에서의 동작:

```text
--temperature 가 주어졌고 모델이 거부 목록에 있다
  → 본문에서 temperature 제거
  → [WARN] 'claude-opus-5-5' 는 temperature 를 지원하지 않아 생략합니다 (출처: 내장 목록 | 2026-10-13 학습)

거부 목록에 없는데 400 + error.message 에 "temperature" 포함
  → 학습 목록에 기록 (파일 저장)
  → [WARN] temperature 미지원 모델로 기록했습니다. temperature 없이 다시 요청합니다
  → temperature 제거 후 1회 재요청 (호출 횟수 2회, 이 실행에서 구조 결함 재생성은 생략)

거부 목록에 없는 다른 400
  → 그대로 AIRequestError 로 보고 (레지스트리에 기록하지 않음)
```

왜 모든 400 을 기록하지 않는가: `max_tokens` 값 오류처럼 모델과 무관한 400 을 기록하면 멀쩡한 모델이 거부 목록에 들어갑니다. 메시지에 `temperature` 가 명시된 경우로 한정합니다.

관리 명령:

| 명령 | 동작 |
| --- | --- |
| `python -m ai_gitgen models list` | 내장·학습·제외 목록을 출처와 함께 표로 출력 |
| `python -m ai_gitgen models add <model-id> [--reason "..."]` | 학습 목록에 수동 추가 (400 을 보기 전에 미리 등록) |
| `python -m ai_gitgen models remove <model-id>` | 학습 목록에서 삭제. 내장 목록의 모델이면 `excluded_builtin` 에 추가 |
| `python -m ai_gitgen models reset` | 학습 목록과 제외 목록을 비움 (내장 목록은 유지) |

## 4. 구현 순서

각 단계는 "확인 방법"이 통과하면 끝입니다. 순서를 지키면 API 키 없이도 5단계까지 테스트할 수 있습니다.

### 1단계. 프로젝트 골격과 CLI

```bash
mkdir -p ai_gitgen tests && touch ai_gitgen/__init__.py tests/__init__.py
```

`cli.py` 의 옵션 설계:

```python
import argparse
from . import config

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ai-gitgen",
        description="git 변경 사항으로 커밋 메시지와 PR 초안을 생성합니다.",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    for name, help_text in (("commit", "커밋 메시지 생성"), ("pr", "PR 제목/본문 초안 생성")):
        cmd = sub.add_parser(name, help=help_text)
        cmd.add_argument("--model", default=config.DEFAULT_MODEL)
        cmd.add_argument("--temperature", type=float, default=config.DEFAULT_TEMPERATURE)
        cmd.add_argument("--max-tokens", type=int, default=config.DEFAULT_MAX_TOKENS)
        cmd.add_argument("--safe-mode", action="store_true", help="민감정보 마스킹과 전송량 제한 적용")
        cmd.add_argument("--dry-run", action="store_true", help="API를 호출하지 않고 프롬프트만 출력")
    models = sub.add_parser("models", help="temperature 미지원 모델 목록 관리")
    models_sub = models.add_subparsers(dest="models_command", required=True)
    models_sub.add_parser("list")
    add = models_sub.add_parser("add"); add.add_argument("model_id"); add.add_argument("--reason", default="수동 등록")
    remove = models_sub.add_parser("remove"); remove.add_argument("model_id")
    models_sub.add_parser("reset")
    return parser
```

`--dry-run` 은 과제 요구는 아니지만, 프롬프트에 무엇이 들어가는지 눈으로 확인하고 비용 없이 테스트하는 데 꼭 필요합니다.

**확인:** `python -m ai_gitgen commit --help` 가 옵션 네 개를 보여 준다.

### 2단계. git 변경 사항 수집

```python
import subprocess
from .errors import GitCommandError, NotGitRepositoryError

def _run_git(*args: str) -> str:
    try:
        completed = subprocess.run(
            ["git", *args], capture_output=True, text=True, check=True, encoding="utf-8",
        )
    except FileNotFoundError as exc:
        raise GitCommandError("git 실행 파일을 찾을 수 없습니다.") from exc
    except subprocess.CalledProcessError as exc:
        if "not a git repository" in exc.stderr:
            raise NotGitRepositoryError("Git 저장소 루트에서 실행해 주세요.") from exc
        raise GitCommandError(f"git {' '.join(args)} 실패: {exc.stderr.strip()}") from exc
    return completed.stdout

def collect_changes() -> GitChanges:
    status = _run_git("status", "--porcelain")
    files = tuple(line[3:] for line in status.splitlines() if line.strip())
    diff_text = _run_git("diff") + _run_git("diff", "--cached")
    branch = _run_git("rev-parse", "--abbrev-ref", "HEAD").strip()
    return GitChanges(branch, files, diff_text, diff_text.count("\n"))
```

주의할 점.

- `--porcelain` 은 사용자 설정(색상, 언어)에 영향받지 않는 기계 친화 형식입니다. 사람용 `git status` 출력을 파싱하지 않습니다.
- 인자를 리스트로 넘기고 `shell=False`(기본값)를 유지합니다. 파일명에 공백이나 특수문자가 있어도 안전합니다.
- 추적되지 않은 새 파일(`??`)은 `git diff` 에 나오지 않습니다. 파일 목록에는 포함되므로 프롬프트에 "새 파일: ..." 로 따로 알려 주면 요약 품질이 좋아집니다.

**확인:** 저장소를 깨끗하게 만든 뒤 실행하면 `[INFO] 변경 사항이 없습니다. 커밋 메시지를 생성하지 않고 종료합니다.` 가 나오고 종료 코드 0.
파일을 하나 수정하면 `[INFO] Git status 수집 완료: 1개 파일 변경 감지` 가 나온다.

### 3단계. safe-mode (마스킹 + 전송량 제한)

정책을 숫자로 고정하고 README에 적습니다.

| 항목 | 기본값 | 근거 |
| --- | --- | --- |
| 전송 파일 수 상한 | 10개 | 과제 예시 값. 넘는 파일은 이름만 전달 |
| 전송 줄 수 상한 | 파일당 200줄 | 과제 예시 값. 넘으면 `... (N줄 생략)` 표시 |
| 제외 파일 패턴 | `.env*`, `*.pem`, `*.key`, `*.p12`, `*.lock`, `package-lock.json`, `yarn.lock`, `pnpm-lock.yaml`, `*.min.js` | 비밀값 가능성이 높거나 요약 가치가 없는 파일 |
| 마스킹 치환 문자 | `[MASKED:종류]` | 무엇이 가려졌는지는 알려 주되 값은 숨김 |

마스킹 규칙은 `(이름, 정규식)` 튜플 목록으로 두고, 적용 순서는 구체적인 것(키 형식)부터 일반적인 것(이메일)까지입니다.

```python
import re

MASK_RULES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("PRIVATE_KEY", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----")),
    ("ANTHROPIC_KEY", re.compile(r"sk-ant-[A-Za-z0-9_\-]{20,}")),
    ("OPENAI_KEY", re.compile(r"sk-[A-Za-z0-9]{20,}")),
    ("AWS_KEY", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("GITHUB_TOKEN", re.compile(r"gh[pousr]_[A-Za-z0-9]{36,}")),
    ("JWT", re.compile(r"eyJ[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+")),
    ("GENERIC_SECRET", re.compile(r"(?i)\b(api[_-]?key|secret|token|password|passwd)\b(\s*[:=]\s*)[\"']?[^\s\"']{8,}")),
    ("EMAIL", re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")),
    ("PHONE_KR", re.compile(r"\b01[016789]-?\d{3,4}-?\d{4}\b")),
)

def mask_secrets(text: str) -> tuple[str, int]:
    total = 0
    for name, pattern in MASK_RULES:
        text, count = pattern.subn(lambda m, n=name: _replacement(m, n), text)
        total += count
    return text, total
```

`GENERIC_SECRET` 은 `api_key = "..."` 처럼 키 이름은 남기고 값만 가리도록 치환 함수에서 그룹 1·2를 보존합니다.

**확인:** 테스트 파일에 `AKIAABCDEFGHIJKLMNOP` 와 이메일을 넣고 `--safe-mode --dry-run` 을 실행하면 프롬프트에 `[MASKED:AWS_KEY]`, `[MASKED:EMAIL]` 이 보인다.
`--safe-mode` 없이 실행하면 원문이 보인다 (이 차이가 보너스 3번의 증빙입니다).

### 4단계. 프롬프트 설계

원칙은 네 가지입니다. 원문은 [04-prompt-templates.md](04-prompt-templates.md)에 있습니다.

1. **역할과 규칙은 시스템 프롬프트에, 데이터(diff)는 사용자 메시지에.** 모델이 지시와 자료를 구분하기 쉽고, 규칙은 매번 같으므로 캐시에 유리합니다.
2. **양식을 글로 설명하지 말고 보여 준다.** 커밋은 Conventional Commits 형식과 예시 1개, PR은 `## Why / ## What / ## How to Test` 틀을 그대로 넣습니다.
3. **길이 제한을 숫자로 명시한다.** "제목은 50자 이내, 절대 72자를 넘기지 말 것". 그래도 넘어오므로 코드 검증이 필요합니다(5단계).
4. **파싱하기 쉬운 출력 형태를 강제한다.** 첫 줄은 제목, 둘째 줄은 빈 줄, 그 아래 본문. 코드 펜스(```)나 "다음은 커밋 메시지입니다" 같은 서두를 금지합니다.

사용자 메시지에는 diff 외에 **맥락**을 함께 넣습니다. 브랜치 이름(`feature/login-retry` 는 그 자체로 변경 이유를 암시), 변경 파일 목록, 새 파일 목록, safe-mode로 생략된 파일 수.
사용자가 `--context "로그인 재시도 버그 수정"` 처럼 변경 이유를 직접 줄 수 있는 옵션을 추가하면 PR의 Why 섹션 품질이 눈에 띄게 좋아집니다.

**확인:** `--dry-run` 으로 시스템/사용자 프롬프트를 출력해 보고, 규칙과 데이터가 섞이지 않았는지 눈으로 확인한다.

### 5단계. 출력 검증과 다듬기

규칙을 상수로 두고, 검증 함수는 문제 목록을 돌려줍니다.

```python
COMMIT_TITLE_SOFT_LIMIT = 50
COMMIT_TITLE_HARD_LIMIT = 72
PR_TITLE_HARD_LIMIT = 80
PR_REQUIRED_SECTIONS = ("## Why", "## What", "## How to Test")

def validate_commit(message: CommitMessage) -> ValidationReport:
    problems: list[str] = []
    if not message.title.strip():
        problems.append("제목이 비어 있습니다.")
    if len(message.title) > COMMIT_TITLE_HARD_LIMIT:
        problems.append(f"제목이 {COMMIT_TITLE_HARD_LIMIT}자를 넘습니다 ({len(message.title)}자).")
    if message.title.rstrip().endswith("."):
        problems.append("제목 끝의 마침표를 제거해야 합니다.")
    return ValidationReport(is_valid=not problems, problems=tuple(problems))
```

처리 정책 (호출 1~2회 제한을 지키는 방식):

| 문제 유형 | 처리 | API 재호출 |
| --- | --- | --- |
| 제목 길이 초과 | 단어 경계에서 잘라 `…` 없이 마무리, 잘린 내용은 본문 첫 불릿으로 이동 | 없음 |
| 제목 끝 마침표, 앞뒤 공백, 코드 펜스 | 제거 | 없음 |
| 서두 문장("다음은 ...") | 첫 줄이 `type:` 형식이 아니면 첫 `type:` 줄까지 버림 | 없음 |
| PR 섹션 헤더 누락, 섹션에 불릿 없음 | **1회 재생성.** 재생성 프롬프트에 "이전 출력에서 `## How to Test` 섹션이 빠졌다"고 문제를 명시 | 1회 |
| 재생성 후에도 실패 | 빠진 섹션을 `- (작성 필요)` 불릿으로 채우고 `[WARN]` 출력 | 없음 |

이렇게 하면 최대 호출 횟수가 2회로 고정되고, 로그에 `[INFO] AI API 호출 횟수: 2회` 를 출력할 수 있습니다.

**확인:** 단위 테스트로 "73자 제목 → 72자 이하로 잘리고 본문에 나머지가 들어간다", "How to Test 가 없으면 `needs_regeneration=True`" 를 검증한다. API 없이 가능합니다.

### 6단계. AI API 호출

```python
import json, os, urllib.error, urllib.request
from .errors import AIRequestError, MissingApiKeyError

API_URL = "https://api.anthropic.com/v1/messages"
API_VERSION = "2023-06-01"

def load_api_key() -> str:
    key = os.environ.get("AI_API_KEY") or os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise MissingApiKeyError('AI_API_KEY 환경변수가 설정되지 않았습니다.\n예) export AI_API_KEY="YOUR_KEY"')
    return key

def generate(system: str, user: str, *, model: str, temperature: float | None,
             max_tokens: int, timeout: float = 60.0) -> GenerationResult:
    body: dict[str, object] = {
        "model": model, "max_tokens": max_tokens, "system": system,
        "messages": [{"role": "user", "content": user}],
    }
    if temperature is not None:
        body["temperature"] = temperature
    request = urllib.request.Request(
        API_URL, data=json.dumps(body).encode("utf-8"), method="POST",
        headers={"content-type": "application/json", "x-api-key": load_api_key(),
                 "anthropic-version": API_VERSION},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.load(response)
    except urllib.error.HTTPError as exc:
        raise AIRequestError(_describe_http_error(exc)) from exc
    except urllib.error.URLError as exc:
        raise AIRequestError(f"네트워크 오류: {exc.reason}") from exc
    except TimeoutError as exc:
        raise AIRequestError(f"응답 시간 초과 ({timeout:.0f}초)") from exc
    text = "".join(block["text"] for block in payload["content"] if block.get("type") == "text")
    usage = payload.get("usage", {})
    return GenerationResult(text, usage.get("input_tokens", 0), usage.get("output_tokens", 0),
                            payload.get("stop_reason", ""))
```

`_describe_http_error` 는 상태 코드별로 사람이 읽을 메시지를 만듭니다. 응답 본문은 `{"type":"error","error":{"type":"...","message":"..."}}` 형태이므로 `error.message` 를 꺼내 함께 보여 줍니다.

| 상태 | 뜻 | 사용자에게 보여 줄 힌트 |
| --- | --- | --- |
| 400 | 요청 형식 오류 | 본문 메시지 그대로. `temperature` 언급 시 2.3절 힌트 추가 |
| 401 | 인증 실패 | 키 값 또는 환경변수 이름 확인 |
| 403 | 권한 없음 | 키의 워크스페이스/권한 확인 |
| 404 | 모델 ID 오류 | `--model` 값 확인 |
| 429 | 요청 한도 초과 | 잠시 후 재시도, `retry-after` 헤더 값 안내 |
| 500/529 | 서버 오류/과부하 | 잠시 후 재시도 |

응답을 받은 뒤에는 `stop_reason` 을 확인합니다. `max_tokens` 이면 "출력이 잘렸습니다. `--max-tokens` 를 늘려 보세요" 를, `refusal` 이면 "모델이 요청을 거절했습니다" 를 출력합니다.

**확인:** 키 없이 실행 → `[ERROR] AI_API_KEY 환경변수가 설정되지 않았습니다.` 종료 코드 1. 잘못된 키 → `[ERROR] 인증 실패 (HTTP 401): ...`.
`--model no-such-model` → 404 메시지. 정상 키 → 커밋 메시지 블록 출력과 `[INFO] 토큰 사용: 입력 N / 출력 M`.

### 6-b단계. 모델 레지스트리

`ai_client` 는 400 응답 본문의 `error.message` 에 `temperature` 가 들어 있으면 일반 `AIRequestError` 대신 `UnsupportedParameterError(model, parameter="temperature", reason=message)` 를 던집니다.
기록과 재요청 판단은 `cli` 가 합니다.

```python
import json, os, re
from dataclasses import asdict, replace
from datetime import datetime, timezone
from pathlib import Path

BUILTIN_NO_TEMPERATURE_MODELS: frozenset[str] = frozenset({
    "claude-fable-5-1", "claude-fable-5", "claude-opus-5-5", "claude-opus-5",
    "claude-opus-4-8", "claude-opus-4-7", "claude-sonnet-5-5", "claude-sonnet-5", "claude-haiku-5-5",
})
TEMPERATURE_ERROR_PATTERN = re.compile(r"temperature", re.IGNORECASE)

def registry_path() -> Path:
    home = os.environ.get("AI_GITGEN_HOME") or os.path.join(os.path.expanduser("~"), ".ai-gitgen")
    return Path(home) / "model_registry.json"

class ModelRegistry:
    def __init__(self, path: Path) -> None:
        self._path = path
        self._learned: dict[str, UnsupportedModelRecord] = {}
        self._excluded_builtin: set[str] = set()
        self._load()

    def rejects_temperature(self, model: str) -> str | None:
        """거부 모델이면 출처 문자열('내장 목록' 또는 'YYYY-MM-DD 학습'), 아니면 None."""
        if model in self._learned:
            return f"{self._learned[model].first_seen[:10]} 학습"
        if model in BUILTIN_NO_TEMPERATURE_MODELS and model not in self._excluded_builtin:
            return "내장 목록"
        return None

    def record_rejection(self, model: str, reason: str) -> None:
        now = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
        previous = self._learned.get(model)
        record = (replace(previous, last_seen=now, count=previous.count + 1, reason=reason)
                  if previous else UnsupportedModelRecord(model, reason, now, now))
        self._learned = {**self._learned, model: record}
        self._save()

    def remove(self, model: str) -> None:
        self._learned = {k: v for k, v in self._learned.items() if k != model}
        if model in BUILTIN_NO_TEMPERATURE_MODELS:
            self._excluded_builtin = self._excluded_builtin | {model}
        self._save()

    def reset(self) -> None:
        self._learned, self._excluded_builtin = {}, set()
        self._save()

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RegistryError(f"모델 레지스트리 파일을 읽을 수 없습니다: {self._path} ({exc})") from exc
        self._learned = {m: UnsupportedModelRecord(model=m, **r) for m, r in data.get("no_temperature", {}).items()}
        self._excluded_builtin = set(data.get("excluded_builtin", []))

    def _save(self) -> None:
        payload = {
            "version": 1,
            "no_temperature": {m: {k: v for k, v in asdict(r).items() if k != "model"} for m, r in self._learned.items()},
            "excluded_builtin": sorted(self._excluded_builtin),
        }
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, self._path)
```

`cli` 쪽 흐름:

```python
registry = ModelRegistry(registry_path())
temperature = args.temperature
source = registry.rejects_temperature(args.model)
if source and temperature is not None:
    warn(f"'{args.model}' 는 temperature 를 지원하지 않아 생략합니다 (출처: {source})")
    temperature = None

try:
    result = generate(system, user, model=args.model, temperature=temperature, max_tokens=args.max_tokens)
except UnsupportedParameterError as exc:
    registry.record_rejection(exc.model, exc.reason)
    warn("temperature 미지원 모델로 기록했습니다. temperature 없이 다시 요청합니다")
    result = generate(system, user, model=args.model, temperature=None, max_tokens=args.max_tokens)
    allow_regeneration = False     # 이 실행은 이미 2회 호출
```

주의할 점.

- 파일 쓰기는 임시 파일에 쓴 뒤 `os.replace` 로 바꿉니다. 저장 도중 중단되어도 기존 파일이 깨지지 않습니다.
- 레지스트리 파일이 손상되면 조용히 무시하지 말고 `RegistryError` 로 알립니다. 사용자는 `models reset` 으로 복구할 수 있습니다.
- `--dry-run` 에서도 `rejects_temperature` 조회와 `[WARN]` 은 수행합니다. 사용자가 미리 알 수 있어야 합니다.
- 기록은 `temperature` 가 명시된 400 에만 합니다. 다른 400 을 기록하면 멀쩡한 모델이 거부 목록에 들어갑니다.

**확인:** `AI_GITGEN_HOME` 을 임시 폴더로 두고 `--model claude-opus-5-5 --temperature 0.3 --dry-run` → `[WARN] ... (출처: 내장 목록)`.
`models add test-model --reason "실험"` 뒤 `models list` 에 `test-model` 이 "학습" 출처로 보임. `models remove claude-opus-5-5` 뒤 같은 dry-run 에서 경고가 사라지고, `models list` 의 제외 목록에 보임. `models reset` 뒤 경고가 다시 나타남.

### 7단계. 출력 형식

```text
[INFO] Git status 수집 완료: 3개 파일 변경 감지
[INFO] Git diff 수집 완료: 128줄
[INFO] safe-mode: 2개 항목 마스킹, 0개 파일 생략
[INFO] AI API 요청 중... (model=claude-sonnet-4-6, temperature=0.3, max_tokens=1024)
[INFO] AI API 호출 횟수: 1회 / 토큰 사용: 입력 1,842 · 출력 96
[DONE] 커밋 메시지 생성 완료

--- Commit Message ---
feat: safe-mode 마스킹 규칙에 GitHub 토큰 패턴 추가

- sanitizer.py 에 ghp_/gho_ 접두 토큰 정규식 추가
- 마스킹 결과 수를 로그에 출력하도록 formatter 수정
----------------------
```

로그는 표준 오류(`stderr`)로, 생성 결과는 표준 출력(`stdout`)으로 보냅니다. 그러면 `python -m ai_gitgen commit > msg.txt` 로 결과만 파일에 담아 `git commit -F msg.txt` 에 바로 쓸 수 있습니다.

### 8단계. 테스트

API 키 없이 돌아가는 테스트가 대부분이어야 합니다. `ai_client.generate` 는 `unittest.mock.patch` 로 바꿉니다.

| 테스트 파일 | 검증 내용 |
| --- | --- |
| `test_git_collector.py` | 임시 디렉터리에 `git init` 후 파일 수정 → `files`, `diff_text` 확인. 깨끗한 저장소 → `is_empty` |
| `test_sanitizer.py` | 각 마스킹 규칙별 1건, 제외 파일 필터, 파일 수/줄 수 상한, 마스킹 수 집계 |
| `test_validators.py` | 길이 초과 절단, 마침표 제거, 서두 제거, PR 섹션 누락 감지, 불릿 없음 감지, 보강 후처리 |
| `test_prompts.py` | 시스템 프롬프트에 규칙 숫자가 들어 있는지, 사용자 프롬프트에 브랜치·파일 목록이 들어 있는지 |
| `test_ai_client.py` | `urlopen` 을 가짜로 바꿔 200 응답 파싱, 401/429 응답을 `AIRequestError` 로 변환, 키 없음, `temperature` 400 → `UnsupportedParameterError` |
| `test_model_registry.py` | 내장 목록 조회, 400 기록 후 파일 내용, 같은 모델 재기록 시 `count` 증가, `remove` 가 내장 모델을 제외 목록에 넣음, `reset`, 손상 파일 → `RegistryError`, 임시 파일 교체 |
| `test_cli.py` | `commit`/`pr` 전체 흐름(generate 를 mock), 변경 없음 종료, 옵션 전달, 종료 코드, 거부 모델이면 `temperature=None` 으로 호출, `UnsupportedParameterError` 후 1회 재요청과 총 호출 2회, `models` 서브커맨드 |

### 9단계. README와 GitHub

[05-readme-template.md](05-readme-template.md)를 채워 `README.md` 로 저장합니다. 반드시 실제 실행 출력을 붙여 넣습니다.
저장소를 만들고 push 한 뒤 README의 명령을 다른 폴더에서 **처음부터 그대로 따라 해** 봅니다. 문서만 보고 실행되는지가 결과물 3의 기준입니다.

```bash
gh repo create codyssey-b3-2 --public --source . --push
```

## 5. 보너스 과제 진행 방법

### 보너스 1. 실제 PR 1건

1. 이전 미션 저장소(예: `codyssey-b2-1`)에서 브랜치를 만들고 의미 있는 변경을 한다 (예: README 오탈자 수정보다 "검색 기능에 날짜 범위 옵션 추가" 수준).
2. `python -m ai_gitgen commit --safe-mode` → 출력 저장 → 검토 후 수정 → `git commit -F`.
3. `python -m ai_gitgen pr` → 출력을 PR 본문에 붙이고 수정.
4. **증빙:** PR 링크 + "AI 초안 → 최종" 비교표. 무엇을 왜 고쳤는지 5~10줄. 예: "AI는 테스트 방법을 `pytest` 로 적었지만 이 저장소는 `unittest` 를 쓰므로 명령을 바꿨다".

### 보너스 2. 컨벤션 커스터마이징

1. 대상 저장소의 `git log --oneline -30` 을 보고 prefix 사용 빈도, 스코프 표기, 언어를 표로 정리한다.
2. `.ai-gitgen.yml` 또는 `.ai-gitgen.json` 을 설계한다 (표준 라이브러리만 쓰려면 JSON이 편합니다).

```json
{
  "commit": {"types": ["feat", "fix", "docs", "test", "refactor", "chore"], "scope": "required", "language": "ko"},
  "pr": {"sections": ["## Why", "## What", "## How to Test", "## Checklist"], "tone": "formal"}
}
```

3. `prompts.py` 가 설정 파일을 읽어 규칙 문장을 치환하도록 한다. 설정 파일이 없으면 기본 템플릿.
4. **증빙:** 컨벤션 문서(README 섹션) + 같은 diff로 설정 전/후 생성 결과 비교.

### 보너스 3. 안전 모드 고도화

1. 마스킹 규칙을 설정 파일에서 추가할 수 있게 한다 (`"mask_rules": [{"name": "INTERNAL_ID", "pattern": "EMP-\\d{6}"}]`).
2. `--max-files`, `--max-lines` 옵션으로 상한을 바꿀 수 있게 한다.
3. **증빙:** 정책 표(숫자 포함) + 같은 diff로 safe-mode ON/OFF `--dry-run` 결과 비교.

## 6. 제출 전 점검표

| 요구사항 | 확인 방법 | 증빙 위치 |
| --- | --- | --- |
| Git 루트에서 실행, status/diff 수집 | 수정 파일 있는 저장소에서 실행 → `[INFO] Git status 수집 완료` | README 출력 예시 |
| 변경 없음 메시지 | 깨끗한 저장소에서 실행 → 안내 후 종료 코드 0 | README 출력 예시 |
| API 키 환경변수, 하드코딩 없음 | `grep -rn "sk-" ai_gitgen/` 결과 없음 | 코드 |
| 호출 실패 시 원인 포함 메시지 | 잘못된 키로 실행 → 401 메시지 | README 주의사항 |
| `--model`, `--temperature`, `--max-tokens` 옵션과 기본값 | `--help` 출력 | README 사용법 |
| `temperature` 거부 모델 관리 | `--model claude-opus-5-5 --dry-run` 경고, `models list/add/remove/reset` 동작 | README 모델 호환성 섹션, `test_model_registry.py` |
| 커밋 제목 1줄 필수, 본문 품질 기준 | 출력 확인 + `validate_commit` 테스트 | 테스트 |
| PR 제목 + Why/What/How to Test + 섹션별 불릿 | 출력 확인 + `validate_pr` 테스트 | 테스트 |
| 길이 규칙(50/72, 80) 적용 | 길이 초과 케이스 테스트 | 테스트 |
| 구분선/헤더로 구획 | 출력 확인 | README 출력 예시 |
| 호출 횟수 1~2회, 로그 출력 | `[INFO] AI API 호출 횟수` | README |
| `--safe-mode` (A) 또는 (B) | ON/OFF `--dry-run` 비교 | README 민감정보 섹션 |
| push 금지, PR 생성 API 금지 | 코드에 `push`, `api.github.com` 없음 | 코드 |
| README 6항목 | 5장 템플릿 체크리스트 | README |
| GitHub push 완료 | 저장소 URL 접속 | 제출 링크 |

## 7. 자주 하는 실수

- **diff 전체를 그대로 보낸다.** 수천 줄 diff는 비용이 크고 요약 품질도 떨어집니다. safe-mode가 아니어도 전체 상한(예: 2,000줄)은 두는 편이 낫습니다. 과제의 safe-mode 요구와 별개로 README의 "비용/요청 제한" 항목이 됩니다.
- **모델 출력을 그대로 믿는다.** "제목 50자 이내"라고 지시해도 넘어옵니다. 검증 코드가 없는 구현은 과제 목표 5를 설명할 수 없습니다.
- **`print` 로 모든 걸 stdout 에 쓴다.** 로그와 결과가 섞여 `git commit -F` 에 쓸 수 없습니다.
- **예외를 `except Exception: print("오류")` 로 삼킨다.** 과제는 "오류 원인을 포함한 메시지"를 요구합니다. 상태 코드와 API의 `error.message` 를 보여 줘야 합니다.
- **`temperature` 를 거부하는 최신 모델을 기본값으로 둔다.** 2.3절 참고. 400 응답이 왜 나는지 설명할 수 있어야 합니다.
- **모든 400 을 "temperature 미지원"으로 기록한다.** `max_tokens` 범위 오류 같은 400 까지 레지스트리에 넣으면 정상 모델이 거부 목록에 들어갑니다. `error.message` 에 `temperature` 가 있을 때만 기록합니다.
- **레지스트리 파일을 저장소에 커밋한다.** 사용자별 학습 데이터이므로 홈 디렉터리(`~/.ai-gitgen/`)에 두고, 저장소에는 넣지 않습니다.
- **API 키를 테스트 코드나 커밋 메시지에 남긴다.** `.gitignore` 에 `.env` 를 넣고, 커밋 전에 `git diff --cached | grep -i "sk-"` 를 습관화합니다.
