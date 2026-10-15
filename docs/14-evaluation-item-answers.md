# 평가 문항 답안 — B3-2 내가 고친 코드 설명을 AI가 대신 써주는 도우미

평가 문항(항목 1~4, 18개 질문)에 대해 바로 말할 수 있는 길이로 답을 정리하고, 근거가 되는 파일의 위치와 링크를 붙였습니다. 저장소: <https://github.com/newids/codyssey-b3-2> (아래 링크는 모두 `main` 기준). 로컬 경로는 저장소 루트 기준입니다.

> 과제 문서의 `-temperature`, `-max-tokens` 는 Python `argparse` 관례대로 `--temperature`, `--max-tokens` 로 구현했습니다 (README 3장).

## 항목 1. 실행 확인 (7문항)

모두 저장소 루트에서 `python3 -m ai_gitgen <명령>` 으로 확인합니다. 시연 순서는 ①키 없음 → ②변경 없음 → ③commit → ④pr → ⑤temperature/max_tokens 비교를 권장합니다. 실제 출력 원문은 [README 4장](../README.md#4-출력-예시) 에 있습니다.

| # | 문항 | 확인 명령 | 기대 출력 (요지) | 근거 |
| --- | --- | --- | --- | --- |
| 1-1 | 루트에서 커밋 메시지 생성 명령 실행 시 터미널 출력 | `python3 -m ai_gitgen commit --safe-mode` | stderr 에 `[INFO]` 로그, stdout 에 `--- Commit Message ---` 블록(제목 1줄 + 빈 줄 + `- ` 불릿) | [README 4장 "커밋 메시지"](../README.md#커밋-메시지), 구현 `ai_gitgen/commands.py` `run_generate`, 출력 `ai_gitgen/formatter.py` `render_commit` |
| 1-2 | PR 생성 명령 실행 시 PR 제목·본문 초안 출력 | `python3 -m ai_gitgen pr --safe-mode --context "변경 이유"` | `--- PR Title ---` 1줄, `--- PR Body ---` 아래 `## Why` `## What` `## How to Test` | [README 4장 "PR 초안"](../README.md#pr-초안), 실제 적용 예 [docs/08](08-bonus-1-report.md), B2-1 PR <https://github.com/newids/codyssey-b2-1/pull/1> |
| 1-3 | API Key 없이 실행하면 오류 메시지 출력 후 종료 | `env -u AI_API_KEY -u ANTHROPIC_API_KEY -u OPENAI_API_KEY python3 -m ai_gitgen commit; echo $?` | `[ERROR] AI_API_KEY 환경변수가 설정되지 않았습니다. API 를 호출하지 않고 종료합니다.` + `export` 예시 + `--dry-run` 안내, 종료 코드 **2**. git 수집 전에 끝남 | [README 2장](../README.md#2-환경변수-설정), `ai_gitgen/config.py` `resolve_api_key`, 테스트 `tests/test_cli.py::test_missing_api_key_exits_before_git_collection` |
| 1-4 | 변경 사항 없는 상태에서 실행 시 안내 메시지 | 깨끗한 작업 트리에서 `python3 -m ai_gitgen commit; echo $?` | `[INFO] 변경 사항이 없습니다. 커밋 메시지를 생성하지 않고 종료합니다 (종료 코드 3).` API 호출 없음, 종료 코드 **3** | [README 4장 "변경 사항이 없을 때"](../README.md#변경-사항이-없을-때), `ai_gitgen/commands.py` (`changes.is_empty`), 테스트 `test_no_changes_exits_with_code_three_without_api_call` |
| 1-5 | PR 본문에 Why/What/How to Test 와 섹션별 불릿 1개 이상 | 1-2 의 출력 확인 | 세 섹션 모두 `- ` 불릿 포함. 모델이 빠뜨리면 1회 재생성, 그래도 없으면 `- (작성 필요)` 자리 표시자 + `[WARN]` | [README 9장](../README.md#9-출력-검증-규칙), `ai_gitgen/validators.py` `validate_pr`/`polish_pr`, 테스트 `tests/test_validators.py::PullRequestTest`, `test_cli.py::test_missing_section_triggers_single_regeneration` |
| 1-6 | `temperature`/`max_tokens` 를 바꿨을 때 출력 차이 재현 | `commit --safe-mode --temperature 0.0` vs `1.0`, `commit --safe-mode --max-tokens 60`, `pr --max-tokens 150` | temperature 1.0 은 구분 기호·백틱·불릿 수가 실행마다 달라짐(0.0 은 제목 3/3 동일). max_tokens 60 은 본문이 첫 불릿 중간에서 잘리고 `[WARN] 출력이 max_tokens 에서 잘렸습니다`, 150 은 PR 의 How to Test 가 사라짐 | [docs/11 temperature 실험 9회 원문](11-temperature-experiment.md), [README 4장 "max_tokens 가 모자랄 때"](../README.md#max_tokens-가-모자랄-때), [README 3장 "옵션을 둔 이유"](../README.md#옵션을-둔-이유와-바꿨을-때의-영향) |
| 1-7 | 길이/형식 규칙(제목 길이, 섹션 구조, 불릿 조건) 충족 | 위 출력에서 제목 길이·형식 확인. 길이가 긴 응답을 주면 후처리 로그 확인 | 커밋 제목 72자 최대(50자 권장, 넘으면 `[INFO]` 안내), `type: 설명` 형식, 끝 마침표 없음, 본문 `- ` 불릿. PR 제목 80자. 위반은 후처리 또는 1회 재생성으로 보정하고 로그에 표시 | [README 9장](../README.md#9-출력-검증-규칙) 표, `ai_gitgen/validators.py` (`validate_commit`, `polish_commit`, `truncate_title`), 테스트 `tests/test_validators.py` |

보조 자료: 종료 코드 체계(0/1/2/3/130)는 [README 3장 표](../README.md#결과를-복사해-적용하기) 와 `python3 -m ai_gitgen --help` 끝에 있습니다. 실제 API 없이 같은 흐름을 보려면 `--dry-run`(프롬프트 출력, 키 불필요) 또는 테스트 `python3 -m unittest discover -s tests -t .`(204개, 약 3초)를 실행하면 됩니다.

## 항목 2. 설계 설명 (4문항)

### 2-1. Git 변경 사항 수집 로직과 AI API 호출 로직을 왜 분리했는가?

**답.** 두 로직은 바뀌는 이유가 다릅니다. 수집(`git_collector.py`)은 git 출력 형식(porcelain, 따옴표 경로, 새 파일)의 문제이고, 호출(`providers.py`)은 제공자별 요청 형식·인증·오류 코드의 문제입니다. 분리하면 (1) 수집은 임시 디렉터리에 실제 `git init` 으로, 호출은 `urlopen` 을 가짜로 바꿔 각각 API 키·네트워크 없이 테스트할 수 있고, (2) 제공자를 Claude↔OpenAI 로 바꾸거나 SDK 로 교체해도 수집 코드는 손대지 않으며, (3) 수집 결과를 불변 객체 `GitChanges` 로 넘기므로 호출 전에 safe-mode 정제와 `--dry-run` 을 끼워 넣을 수 있습니다.

**근거.** [README 10장 "수집 → 호출 → 후처리의 경계와 테스트 지점"](../README.md#수집--호출--후처리의-경계와-테스트-지점) 표, [docs/03 Q3](03-evaluation-answers.md#q3-git-status-git-diff-결과를-프로그램-입력으로-연결하는-방식과-자동화-흐름을-설명하라), 코드 `ai_gitgen/git_collector.py`(`collect_changes`), `ai_gitgen/providers.py`(`Provider` 프로토콜, `AIClient`), `ai_gitgen/records.py`(`GitChanges`), 테스트 `tests/test_git_collector.py`, `tests/test_providers.py`.

### 2-2. 프롬프트 구성 로직과 출력 포맷팅(길이 규칙 포함) 로직을 어떻게 분리했고, 왜인가?

**답.** 프롬프트는 `prompts.py` 가 "모델에게 무엇을 요구할지"(형식·길이 규칙·금지 사항·컨벤션 블록)를 문자열로 조립하고, 출력은 `validators.py` 가 "모델이 실제로 무엇을 어겼는지"를 판정해 기계적으로 고칠 수 있는 것은 고칩니다(`ValidationReport` → `polish_*`). 터미널 블록 모양은 `formatter.py` 가 맡습니다. 분리한 이유는 모델이 지시를 확률적으로 따르기 때문입니다. "72자 이내"라고 프롬프트에 써도 넘어올 수 있으므로 길이 규칙은 코드가 최종 보장해야 하고, 그 코드는 모델 출력 문자열만 입력으로 받아 API 없이 테스트할 수 있어야 합니다. 프롬프트를 고쳐도 검증 코드는 그대로이고(기본 프롬프트는 SHA-256 골든 테스트로 고정), 반대로 검증 규칙을 바꿔도 프롬프트 템플릿은 건드리지 않습니다.

**근거.** [docs/03 Q4](03-evaluation-answers.md#q4-commitpr-양식과-코드-변경-맥락을-포함해-요구사항에-맞는-요약을-생성하도록-프롬프트를-구성하는-원리는), [docs/03 Q5](03-evaluation-answers.md#q5-생성된-커밋pr-텍스트가-실무-규칙을-만족하도록-검증하고-다듬는-이유와-방법은), [docs/04 프롬프트 원문](04-prompt-templates.md), [README 9장](../README.md#9-출력-검증-규칙), 코드 `ai_gitgen/prompts.py`, `ai_gitgen/validators.py`, `ai_gitgen/formatter.py`, 테스트 `tests/test_prompts.py`(골든 해시), `tests/test_validators.py`.

### 2-3. API 파라미터를 CLI 옵션으로 설계한 이유(재현성/실험 용이성)는?

**답.** 같은 diff 를 두고 설정만 바꿔 결과 차이를 직접 확인하기 위해서입니다. `--model` 은 품질·비용 비교와 재현 시 모델 고정, `--temperature` 는 "0.3 이 적절한가, 올리면 무엇이 먼저 흔들리는가"의 실험 축, `--max-tokens` 는 절단 위험의 조절 장치입니다. 기본값(0.3, commit 512 / pr 1024)은 커밋 메시지 용도에 맞춰 고정했고, 옵션은 실험·비교용임을 `--help` 문구에도 적었습니다. 실제로 이 옵션으로 temperature 9회 실험과 max_tokens 절단 예시를 만들었습니다. 실행 로그에 `provider/model/temperature/max_tokens` 를 매번 출력하므로 어떤 설정의 결과인지 재현 가능합니다.

**근거.** [README 3장 "옵션을 둔 이유와 바꿨을 때의 영향"](../README.md#옵션을-둔-이유와-바꿨을-때의-영향) 표, [docs/11](11-temperature-experiment.md), [docs/12 항목 10](12-pre-evaluation-feedback.md), 코드 `ai_gitgen/cli.py`(`_add_generation_options` 의 help 문구), `ai_gitgen/commands.py`(`_resolve_settings`, `_describe`), 테스트 `tests/test_cli.py::test_options_are_passed_to_settings`.

### 2-4. 오류 처리(API Key 누락, 네트워크 오류 등)를 어떻게 구현했고, 왜인가?

**답.** 도구의 모든 오류는 `AiGitgenError` 계층으로 통일하고 `cli.main` 한 곳에서 잡아 `[ERROR] 원인 한 줄 + 힌트` 로 출력하며, 스택트레이스는 보여 주지 않습니다. 종류별로 종료 코드를 나눴습니다. 실행 전에 고쳐야 하는 설정·사용법 오류(키 없음, 옵션 범위, 설정 파일)는 `ConfigurationError` → 2, 실행 중 오류(HTTP 4xx/5xx, 네트워크, 시간 초과, git 실패)는 1, 변경 없음은 3, Ctrl+C 는 130 입니다. API 키는 git 수집 전에 확인해 헛수고를 막고, HTTP 오류는 상태 코드별 라벨과 API 의 `error.message`, 상황별 힌트(401 은 키 확인, 429/5xx 는 재시도)를 붙입니다. 네트워크 오류·시간 초과·연결 끊김은 `send_request` 가 잡아 원인을 적습니다. 이렇게 한 이유는 과제가 "원인을 포함한 메시지"를 요구하고, 사용자가 해야 할 일(키 고치기 vs 기다리기)이 오류마다 다르며, 스크립트에서 종료 코드로 분기할 수 있어야 하기 때문입니다.

**근거.** [docs/03 Q1 "예외 대응"](03-evaluation-answers.md#q1-ai-api를-rest-api-방식으로-연동할-때-요청-구성-응답-처리-예외-대응의-전체-흐름을-설명하라), [README 3장 종료 코드 표](../README.md#결과를-복사해-적용하기), [README 4장 "API 키가 없을 때"/"API 오류"](../README.md#api-키가-없을-때), 코드 `ai_gitgen/errors.py`, `ai_gitgen/cli.py`(`main`), `ai_gitgen/providers.py`(`_hint_for_status`, `translate_error`, `send_request`), `ai_gitgen/config.py`(`resolve_api_key`, `EXIT_*`), 테스트 `tests/test_providers.py::SendRequestTest`, `tests/test_cli.py::ArgumentValidationTest`, `tests/test_config.py`.

## 항목 3. 파라미터·프롬프트·검증 (4문항)

### 3-1. `temperature` 를 높이거나 낮추면 결과가 어떻게 달라지는가?

**답.** 다음 토큰을 고를 때 확률 분포를 얼마나 평평하게 보는지의 값입니다. 같은 diff 로 0.0 / 0.5 / 1.0 을 각 3회 실행한 실측에서, 0.0 은 제목이 3회 모두 글자 단위로 같았고 본문 단어만 한두 개 달랐습니다(완전한 결정성은 아님). 0.5 는 1회 불릿이 2개로 줄어 테스트 변경이 빠졌고, 1.0 은 구분 기호(쉼표·백틱·슬래시)가 매번 달랐습니다. 예상과 달리 72자 초과와 근거 없는 내용은 9회 모두 0건이었습니다. 즉 이 작업에서 온도가 오르면 사실성보다 **표기와 분량이 먼저 흔들립니다.** 커밋 메시지는 일관성이 중요하므로 기본값 0.3 을 두되, 0.0 에서도 변동이 있으므로 검증 코드는 온도와 무관하게 필요합니다.

**근거.** [docs/11 실험 9회 원문과 해석](11-temperature-experiment.md), [docs/03 Q2](03-evaluation-answers.md#q2-temperature-max_tokens-등-주요-파라미터가-결과-품질에-어떤-영향을-주는가) 표, [docs/02 3절](02-learning-materials.md), 최신 모델이 temperature 를 거부하는 경우의 처리는 [README 7장](../README.md#7-모델-호환성-관리-temperature-미지원-모델) 과 `ai_gitgen/model_registry.py`.

### 3-2. `max_tokens` 가 결과물에 미치는 영향과 값을 정한 기준은?

**답.** 출력 길이의 상한이지 목표가 아닙니다. 모델은 할 말이 끝나면 그 전에 멈추고(`stop_reason: end_turn`) 실제 생성한 토큰만 과금되므로 넉넉히 둬도 비용이 늘지 않습니다. 모자라면 문장 중간에서 끊깁니다. 실측으로 `commit --max-tokens 60` 은 본문이 첫 불릿 중간에서 잘렸고, `pr --max-tokens 150` 은 What 이 끊기고 How to Test 가 통째로 사라졌습니다. 잘린 출력은 다시 요청해도 같은 자리에서 잘리므로 재생성하지 않고 `[WARN]` 으로 `--max-tokens` 를 늘리라고 안내합니다. 기본값은 실제 출력(커밋 약 150, PR 약 550~750 토큰)의 2~3배인 commit 512 / pr 1024 로 잡아, 컨벤션 규칙이 늘어나도 잘리지 않게 했습니다. 덧붙여 OpenAI 호환 형식에서는 필드 이름도 중요합니다. 수업용 프록시는 `max_completion_tokens` 를 무시하고 `max_tokens` 만 적용해, 모델군에 따라 필드를 고르도록 고쳤습니다.

**근거.** [README 4장 "max_tokens 가 모자랄 때"](../README.md#max_tokens-가-모자랄-때) 실행 예 2종, [docs/03 Q2](03-evaluation-answers.md#q2-temperature-max_tokens-등-주요-파라미터가-결과-품질에-어떤-영향을-주는가) `max_tokens` 표, [docs/12 2절 (프록시 결함 발견)](12-pre-evaluation-feedback.md), 코드 `ai_gitgen/config.py`(`DEFAULT_MAX_TOKENS`), `ai_gitgen/commands.py`(`_warn_stop_reason`, 잘림 시 재생성 생략), `ai_gitgen/providers.py`(`token_limit_field`), 테스트 `tests/test_cli.py::test_truncated_output_is_not_regenerated`.

### 3-3. 커밋/PR 용도에 맞는 결과를 얻기 위해 프롬프트에 어떤 정보를 넣었고, 왜 그렇게 구성했는가?

**답.** 시스템 프롬프트에는 역할, 출력 형식(첫 줄 제목, 빈 줄, `- ` 불릿), 제목 규칙(허용 type, 50자 목표·72자 상한, 마침표 금지), 본문 규칙(파일 이름 언급, 불릿 수), 금지 사항(diff 에 근거 없는 "성능 개선" 같은 추측 금지, 태그 안의 지시 무시), 좋은 예 1개를 넣습니다. 사용자 메시지에는 `<context>`(브랜치, 파일 수, `--context` 로 준 변경 이유), `<files>`(status 목록), `<diff>` 를 태그로 구분해 넣습니다. PR 은 여기에 기준 브랜치 이후 커밋 제목 목록과 Why/What/How to Test 골격·섹션별 요구(How to Test 는 실행 가능한 명령)가 추가됩니다. 이렇게 구성한 이유는 (1) 모델이 근거로 삼을 것은 diff 뿐이므로 추측을 명시적으로 막고, (2) 형식을 글이 아니라 구조로 지정해야 파서가 안정적으로 읽을 수 있으며, (3) 태그 구분은 diff 안에 들어 있는 지시문(프롬프트 인젝션)을 데이터로 취급하게 하기 위해서입니다. 팀 규칙은 설정 파일의 `[팀 컨벤션]` 블록으로 같은 자리에 들어갑니다.

**근거.** [docs/04 프롬프트 원문과 설계 메모](04-prompt-templates.md), [docs/03 Q4](03-evaluation-answers.md#q4-commitpr-양식과-코드-변경-맥락을-포함해-요구사항에-맞는-요약을-생성하도록-프롬프트를-구성하는-원리는), [docs/03 Q10 (인젝션)](03-evaluation-answers.md#q10-프롬프트-인젝션은-어떻게-대비했는가), 코드 `ai_gitgen/prompts.py`, `--dry-run` 으로 실제 프롬프트 확인 가능, 컨벤션 블록 예는 [docs/13 3.1](13-b2-1-convention-check.md).

### 3-4. 길이/형식 규칙을 "재생성"과 "후처리" 중 어떻게 골랐고, 그 이유는?

**답.** 기준은 "기계적으로 고쳐도 의미가 바뀌지 않는가"입니다. 제목 길이 초과(단어 경계에서 잘라 나머지를 본문 첫 불릿으로), 끝 마침표, 코드 펜스, 서두 문장, 불릿 기호, 스코프 금지 위반, 체크리스트·푸터 추가는 **후처리**로 해결합니다. 비용이 없고 결과가 확정적이기 때문입니다. 반대로 PR 섹션 누락, `type:` 형식 자체가 아닌 제목, 스코프 필수인데 없음, 허용 목록 밖 type 은 내용을 지어낼 수 없으므로 어긴 규칙과 이전 출력을 넣어 **1회만 재생성**하고, 그래도 안 되면 `- (작성 필요)` 자리 표시자와 `[WARN]` 으로 사람에게 넘깁니다. 1회로 제한한 것은 과제의 호출 1~2회 제한을 지키기 위해서이고, `max_tokens` 로 잘린 출력은 재생성해도 같은 자리에서 잘리므로 재생성하지 않습니다. 결과적으로 호출 횟수는 최대 2회로 고정되고 로그에 출력됩니다.

**근거.** [docs/03 Q5](03-evaluation-answers.md#q5-생성된-커밋pr-텍스트가-실무-규칙을-만족하도록-검증하고-다듬는-이유와-방법은) 결함별 처리 표, [README 9장 "재생성 정책"](../README.md#9-출력-검증-규칙), [README 6장 호출 횟수](../README.md#6-비용과-요청-횟수), 코드 `ai_gitgen/validators.py`(`needs_regeneration` 판정), `ai_gitgen/commands.py`(`run_generate` 의 재생성 분기), `ai_gitgen/prompts.py`(`build_regeneration_prompt`), 테스트 `tests/test_cli.py::PullRequestCommandTest`, `test_temperature_retry_blocks_structural_regeneration`.

## 항목 4. 운영 관점 (3문항)

### 4-1. AI 가 생성한 커밋/PR 텍스트를 바로 쓰지 않고 검토해야 하는 이유는?

**답.** 세 가지입니다. (1) **사실성**: 모델은 diff 에 보이는 것만 알고 "왜" 바꿨는지는 모릅니다. 실제로 B2-1 PR 초안은 저장소에 없는 `pytest` 명령을 제시했고, Why 의 설계 근거는 작성자가 `--context` 로 줘야 했습니다. (2) **확률적 출력**: 같은 입력에도 불릿 수와 표기가 바뀌므로(temperature 실험) 규칙은 코드가 보장하되 내용 누락(테스트 변경 불릿 빠짐 등)은 사람이 봐야 합니다. (3) **책임**: 커밋 메시지와 PR 은 팀의 기록이고 리뷰어가 읽는 문서라 작성자가 내용을 보증해야 합니다. 그래서 도구는 git 에 쓰지 않고 stdout 으로만 내보내며, `[DONE]` 줄에 "AI 초안입니다. 검토·수정한 뒤 적용하세요"를 매번 출력하고, `commit > msg.txt && git commit -e -F msg.txt` 처럼 편집기를 거치는 적용 경로를 권장합니다. 보너스 1 에서 AI 초안을 최종 PR 로 고친 7곳이 검토가 필요한 이유의 실제 사례입니다.

**근거.** [docs/08 보너스 1 "AI 초안 → 최종 PR 변경점"](08-bonus-1-report.md), [docs/03 Q13](03-evaluation-answers.md#q13-보너스-1에서-ai-초안을-최종-pr-로-어떻게-고쳤는가), [README 3장 "결과를 복사해 적용하기"](../README.md#결과를-복사해-적용하기), [README 12장 "결과는 초안"](../README.md#12-설계-결정), [docs/11](11-temperature-experiment.md), 코드 `ai_gitgen/commands.py`(`REVIEW_REMINDER`), `git push`·PR 생성 API 를 넣지 않은 이유는 [docs/03 Q11](03-evaluation-answers.md#q11-왜-git-push-와-pr-생성-api-를-넣지-않았는가).

### 4-2. `git diff` 에 민감정보가 포함될 수 있는 상황과 방지 방안은?

**답.** 상황: `.env`·키 파일을 실수로 스테이징, 테스트 코드나 픽스처에 박힌 토큰·JWT, 설정 파일의 `password = ...`, 고객 데이터 CSV·이메일·전화번호, 조직 내부 식별자(사번·주문번호). 외부 API 로 보내는 순간 제3자 서버에 남습니다. 방지는 세 층입니다. (1) **제외**: `.env*`, `*.pem`, `*.key`, 잠금 파일 등은 내용을 보내지 않고 이름만 보냅니다. (2) **마스킹**: 프라이빗 키 블록, `sk-`/`AKIA`/`ghp_` 접두 키, JWT, `api_key=` 형태 할당값, 이메일, 휴대전화를 `[MASKED:이름]` 으로 바꾸고, 브랜치명·파일 목록·`--context` 에도 같은 규칙을 적용합니다. (3) **전송량 제한**: 파일 10개·파일당 200줄·전체 2,000줄. 조직 고유 패턴은 설정 파일이나 `--mask NAME=REGEX` 로 추가하고, 자격 증명 규칙 6종은 끌 수 없습니다. safe-mode 를 켜지 않아도 같은 규칙으로 검사해 `[WARN] safe-mode 꺼짐: 민감정보로 보이는 값 N개 ...` 로 전송 전에 알리며, `--dry-run` 으로 보낼 내용을 미리 볼 수 있습니다. 한계도 분명합니다. 정규식은 형태가 알려진 값만 잡으므로 임의 문자열 비밀번호는 통과할 수 있고, 비밀값을 커밋에 넣지 않는 것이 원칙이며 safe-mode 는 보조 수단입니다. 실측으로 같은 변경(12개 파일, `.env`·고객 CSV·사번 포함)에서 사번 노출이 OFF 13건 → 기본 safe-mode 12건 → 설정 파일 적용 0건이었습니다.

**근거.** [README 5장](../README.md#5-민감정보-대응-safe-mode) 정책 표와 OFF/ON 비교, [README 5장 "safe-mode 를 켜지 않았을 때"](../README.md#safe-mode-를-켜지-않았을-때의-경고와-확인-절차), [docs/10 보너스 3 보고서](10-bonus-3-report.md)(숫자 정책, 보안 리뷰 반영), [docs/03 Q8](03-evaluation-answers.md#q8-safe-mode-는-무엇을-어떻게-가리는가-완벽한가), 코드 `ai_gitgen/sanitizer.py`(`MASK_RULES`, `sanitize`, `find_sensitive`), `ai_gitgen/config.py`(`SAFE_MODE_EXCLUDED_PATTERNS`), `ai_gitgen/convention.py`(`SafeModePolicy`, `PROTECTED_MASK_RULES`), 테스트 `tests/test_sanitizer.py`.

### 4-3. 실제 팀 프로젝트에 적용한다면 가장 먼저 추가·개선하고 싶은 기능과 우선순위 근거는?

**답.** 1순위는 **`prepare-commit-msg` 훅 연동**입니다. 지금은 `commit > msg.txt && git commit -e -F msg.txt` 처럼 두 단계가 필요한데, 훅에서 도구를 불러 편집기에 초안이 미리 채워지면 "검토 후 적용"이 자연스러운 기본 흐름이 되고 도입 장벽이 사라집니다. 근거는 보너스 1 에서 직접 써 보니 생성보다 적용 단계의 마찰이 컸고, 검토를 건너뛰지 않게 하는 구조(편집기에서 반드시 한 번 봄)와도 맞기 때문입니다. 2순위는 **팀 컨벤션 파일의 규칙 보강**입니다. 이미 B2-1 루트에 `.ai-gitgen.json` 을 넣어 스코프·테스트 명령·체크리스트가 자동 적용되지만, 규칙을 하나 추가하면 다른 불릿(README)이 밀려나는 것을 확인했으므로 "꼭 지켜야 할 규칙만" 고르는 팀 합의가 필요합니다. 3순위는 **비용·사용량 기록**(`usage` 를 파일에 누적해 월별 확인)과 **429/5xx 자동 재시도**(호출 횟수 상한 안에서)입니다. 보류한 것은 PR 자동 생성·push 입니다. 초안을 사람이 보증한다는 원칙과 충돌하기 때문입니다.

**근거.** [docs/03 Q14](03-evaluation-answers.md#q14-이-도구를-팀에-도입한다면-무엇을-더-해야-하는가), [docs/09 보너스 2 6장·8.5](09-bonus-2-report.md)(규칙 추가 시 다른 항목이 밀려나는 관찰), [docs/13](13-b2-1-convention-check.md)(B2-1 루트 적용 재현), [docs/07 7장 "한계와 다음 단계"](07-result-report.md), [README 6장](../README.md#6-비용과-요청-횟수)(호출 횟수·비용 로그).

## 부록. 근거 파일 한눈에 보기

| 파일 | 내용 | 관련 문항 |
| --- | --- | --- |
| [README.md](../README.md) | 설치, 환경변수, 사용법·옵션 이유·종료 코드, 출력 예시 7종, safe-mode, 비용, 모델 호환성, 컨벤션 파일, 검증 규칙, 구조·경계 표, 설계 결정 | 전부 |
| [docs/03-evaluation-answers.md](03-evaluation-answers.md) | 과제 목표 5문항 + 예상 질문 Q6~Q14 상세 답변 | 2, 3, 4 |
| [docs/04-prompt-templates.md](04-prompt-templates.md) | 프롬프트 원문과 설계 메모, 재생성 프롬프트 | 3-3, 3-4 |
| [docs/07-result-report.md](07-result-report.md) | 요구사항 대응표, 시나리오별 실행 로그, 테스트·커버리지, 코드 리뷰 반영, 한계 | 1, 2-4, 4-3 |
| [docs/08-bonus-1-report.md](08-bonus-1-report.md) | 실제 PR 적용과 AI 초안 → 최종 수정 7곳 | 1-2, 4-1 |
| [docs/09-bonus-2-report.md](09-bonus-2-report.md) | 팀 컨벤션 설정 파일, 적용 전/후 비교, B2-1 루트 적용 결과 | 4-3 |
| [docs/10-bonus-3-report.md](10-bonus-3-report.md) | safe-mode 정책 숫자, 정규식 규칙, OFF/ON 비교 4종, 보안 리뷰 | 4-2 |
| [docs/11-temperature-experiment.md](11-temperature-experiment.md) | temperature 0.0/0.5/1.0 × 3회 원문 | 1-6, 3-1 |
| [docs/12-pre-evaluation-feedback.md](12-pre-evaluation-feedback.md) | 사전평가 16항목 반영, max_tokens 프록시 결함, 재검증 명령 | 1-3, 1-4, 2-3, 3-2 |
| [docs/13-b2-1-convention-check.md](13-b2-1-convention-check.md) | B2-1 에서 commit/pr 컨벤션 자동 적용 재현 (`scripts/b2-1-convention-check.sh`) | 4-3 |
| `ai_gitgen/` | 구현 15개 모듈 (구조는 README 10장) | 전부 |
| `tests/` | 204개 테스트, API 키 불필요, `python3 -m unittest discover -s tests -t .` | 1, 2 |
