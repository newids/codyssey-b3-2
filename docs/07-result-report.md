# 수행 결과 보고서 — B3-2 내가 고친 코드 설명을 AI가 대신 써주는 도우미

작성일 2026-10-13. 구현 코드는 `ai_gitgen/`, 테스트는 `tests/`, 사용법은 [README.md](../README.md)에 있습니다.

## 1. 결과물 요약

| 과제 결과물 | 상태 | 위치 |
| --- | --- | --- |
| 1. AI API 연동 및 자동화 흐름 동작 | 완료. `commit`/`pr` 단일 실행으로 수집 → safe-mode → 프롬프트 → API → 검증 → 출력 | `ai_gitgen/commands.py` |
| 2. GitHub 리포지토리 | 완료. 공개 저장소, 커밋 5개(과제 원문 → 문서 → 구현 → 테스트 → README) | <https://github.com/newids/codyssey-b3-2> |
| 3. 사용 가이드 README | 완료. 설치, 환경변수, 사용 예시, 출력 예시, 민감정보 대응, 비용/요청 제한 | `README.md` |

## 2. 기능 요구사항 대응

| 요구 | 구현 | 확인 방법 |
| --- | --- | --- |
| Git 루트에서 실행 | `git rev-parse --show-toplevel` 과 현재 경로 비교. 다르면 루트 경로를 안내하고 종료 | `tests/test_git_collector.py::test_subdirectory_is_rejected_with_root_hint` |
| `git status` 수집 | `--porcelain` 형식 파싱, 이름 변경·새 파일 처리 | `test_git_collector.py::ParsePorcelainTest` |
| `git diff` 수집 | 작업 트리 + 스테이징 + 새 파일(`--no-index`) | `test_modified_and_staged_files_appear_in_diff`, `test_untracked_file_content_is_collected_with_no_index_diff` |
| 변경 없음 메시지 | `[INFO] 변경 사항이 없습니다. ... 종료합니다.` 종료 코드 0 | `test_cli.py::test_no_changes_exits_zero_without_api_call` |
| API 키 환경변수, 하드코딩 금지 | `config.load_api_key` 가 `AI_API_KEY` → 제공자별 변수 순으로 읽음 | `grep -rn "sk-" ai_gitgen/` 결과 없음, `test_missing_api_key_is_reported` |
| 실패 시 원인 포함 메시지 | 상태 코드별 라벨 + API `error.message` + 힌트. 네트워크·시간 초과 분리 | `test_providers.py::ClaudeProviderTest`, `SendRequestTest` |
| 모델·temperature·max_tokens 옵션 | `--model`, `--temperature`, `--max-tokens` 와 기본값 | `test_cli.py::test_options_are_passed_to_settings` |
| 커밋 제목 1줄 필수, 본문 선택 | `parse_commit_text` + `validate_commit`. 본문은 파일/모듈 언급 또는 불릿 | `test_validators.py::ParseCommitTest` |
| PR 제목 + Why/What/How to Test + 섹션별 불릿 | `validate_pr` 가 섹션·불릿 검사, `polish_pr` 가 보강 | `test_validators.py::PullRequestTest` |
| 길이 규칙 50/72, 80 | `truncate_title` 단어 경계 절단, 나머지는 본문으로 | `test_polish_truncates_title_and_moves_remainder_to_body` |
| 검증 후 재생성 또는 후처리 | 길이·기호는 후처리, 구조 결함은 1회 재생성 후 후처리 | `test_cli.py::PullRequestCommandTest` |
| 구분선/헤더 출력 | `--- Commit Message ---`, `--- PR Title ---`, `--- PR Body ---` | README 4장 |
| 호출 1~2회, 로그 출력 | `AIClient.call_count`, `MAX_API_CALLS_PER_RUN = 2`. temperature 재요청과 구조 재생성은 배타적 | `test_temperature_retry_blocks_structural_regeneration` |
| `--safe-mode` (A)+(B) | 마스킹 9종, 제외 7패턴, 10파일/200줄 | `tests/test_sanitizer.py` |
| push·PR 생성 금지 | 코드에 `push`, `api.github.com` 없음 | `grep -rn "push\|api.github" ai_gitgen/` |

## 3. 실행 결과

### 3.1 환경과 재현 방법

이 작업 환경에는 AI API 키가 없었습니다. 따라서 README 와 아래 로그의 **모델 응답 텍스트는 로컬 모의 서버가 돌려준 준비된 문구**이고, 나머지(git 수집, safe-mode, 레지스트리, 검증, 재생성, 오류 처리, 호출 횟수)는 실제 코드 경로를 그대로 거친 결과입니다.

재현: `AI_API_BASE_URL` 로 엔드포인트를 로컬 서버로 돌리면 됩니다. 모의 서버는 `/v1/messages` 와 `/v1/chat/completions` 두 경로를 받고, 모델 이름에 `reject` 가 있으면 `temperature` 400 을, `demo-missing` 이 있으면 첫 응답에서 How to Test 섹션을 빼서 재생성 경로를 유도합니다.

```bash
export AI_API_BASE_URL=http://127.0.0.1:8765 AI_API_KEY=fake-key AI_GITGEN_HOME=/tmp/aig-demo
python3 -m ai_gitgen commit --safe-mode
```

실제 키로 다시 실행해 README 4장을 교체하는 것이 제출 전 마지막 단계입니다.

### 3.2 데모 저장소 변경 내용

`sanitizer/rules.py` 의 마스킹 규칙 튜플에 GitHub 토큰 정규식 1줄을 추가하고, `tests/test_sanitizer.py` 에 테스트 1개를 추가했습니다. 추적되지 않은 `.env` 파일(토큰·이메일 포함)도 함께 두어 safe-mode 효과를 확인했습니다. 브랜치는 `feature/mask-github-token`.

### 3.3 시나리오별 로그

| 시나리오 | 명령 | 결과 |
| --- | --- | --- |
| 커밋 메시지 (safe-mode) | `commit --safe-mode` | 호출 1회. `.env` 제외(1개 파일 생략), 테스트 코드의 `ghp_` 문자열 마스킹(1개 항목). 제목 27자 |
| PR 초안 (context 제공) | `pr --context "..." --safe-mode` | 호출 1회. 세 섹션 모두 불릿 포함, 검증 통과 |
| 변경 없음 | `commit` (stash 후) | `[INFO] 변경 사항이 없습니다.` 종료 코드 0, API 호출 없음 |
| 키 없음 | `commit` | `[ERROR] AI_API_KEY 환경변수가 설정되지 않았습니다.` 종료 코드 1 |
| 잘못된 키 | `commit` (401 응답) | `[ERROR] 인증 실패 (HTTP 401): invalid x-api-key` + 힌트 |
| 내장 거부 모델 | `commit --model claude-opus-5-5 --dry-run` | `[WARN] ... 생략합니다 (출처: 내장 목록)`, 요청 본문에 temperature 없음 |
| 미지 모델 400 → 학습 | `commit --model reject-demo-model` | 1차 400 → 기록 → 2차 temperature 없이 성공. 호출 2회 |
| 학습 결과 재사용 | 같은 모델 `--dry-run` | `[WARN] ... (출처: 2026-10-13 학습)` 로 사전 생략 |
| OpenAI 제공자 | `commit --provider openai` | `gpt-4.1-mini`, `Authorization: Bearer`, `prompt_tokens` 매핑 정상 |
| 구조 결함 재생성 | `pr --model demo-missing-model` | 1차 How to Test 누락 감지 → 재생성 프롬프트(이전 출력+어긴 규칙) → 2차 통과. 호출 2회 |
| 레지스트리 관리 | `models add/remove/list/reset` | 학습·제외·내장 항목이 출처와 함께 표로 출력 |

safe-mode ON/OFF 비교(`--dry-run` 의 `<diff>` 부분):

| | OFF | ON |
| --- | --- | --- |
| `.env` | `+GITHUB_TOKEN=ghp_abc...`, `+ADMIN_EMAIL=admin@example.com` 그대로 전송 | 파일 자체 제외, `[생략된 파일: .env]` |
| 테스트 코드의 토큰 리터럴 | 그대로 | `[MASKED:GITHUB_TOKEN]` |
| context 안내 | 없음 | "일부 민감정보는 [MASKED:...] 로 가려져 있고, 1개 파일은 이름만 제공됩니다." |

## 4. 테스트

```text
$ python3 -m unittest discover -s tests -t .
Ran 115 tests in 2.4s
OK
```

커버리지 (`pytest --cov=ai_gitgen`, 외부 도구로 측정):

| 모듈 | 커버리지 | 미실행 줄 |
| --- | --- | --- |
| `commands.py` | 97% | `pr` 브랜치 로그 분기, refusal 경고 분기 |
| `git_collector.py` | 97% | git 실행 파일 없음 분기 |
| `providers.py` | 99% | 403 힌트 분기 |
| `cli.py`, `config.py`, `records.py`, `errors.py` | 100% | |
| 나머지 6개 모듈 | 97~99% | |
| **전체** | **98%** | 895 문장 중 17 (`__main__.py` 4줄 포함) |

테스트 전략: HTTP 전송은 `providers._OPENER.open` 을 mock, CLI 통합 테스트는 `AIClient` 를 응답 큐를 가진 가짜 객체로 교체, git 수집은 임시 디렉터리에 실제 저장소를 만들어 검증. API 키 없이 전부 실행됩니다.

## 5. 코드 리뷰 반영

구현 후 Python 리뷰 에이전트로 보안·정확성 검토를 받아 CRITICAL 0건, HIGH 2건, MEDIUM 6건, LOW 9건을 확인했고 아래를 반영했습니다. 각 항목에 회귀 테스트를 추가했습니다.

| 심각도 | 지적 | 반영 |
| --- | --- | --- |
| HIGH | 일반 비밀값 정규식이 `DB_PASSWORD=`, `access_token =`, `"apiKey":` 처럼 접두·접미가 붙거나 따옴표로 감싼 키 이름을 놓침 | 키 이름 패턴을 `[A-Za-z0-9_-]*(api_key|secret|token|password)[A-Za-z0-9_-]*` 로 확장, 따옴표 허용, 이미 마스킹된 값은 재집계 제외 |
| HIGH | 한글·공백 파일명을 git 이 따옴표로 감싸 `*.pem`, `.env` 제외 규칙이 우회됨 | `core.quotepath=false` 로 고정하고, 헤더 파서가 따옴표도 처리 |
| MEDIUM | `status --porcelain` 의 따옴표 경로와 디렉터리 축약으로 새 파일 내용이 조용히 누락 | `status --porcelain -z --untracked-files=all` 로 NUL 구분 파싱 |
| MEDIUM | 커밋이 없는 새 저장소에서 `rev-parse --abbrev-ref HEAD` 실패 | `git branch --show-current` 로 교체 |
| MEDIUM | `RemoteDisconnected`, `ConnectionResetError`, 문자열형 오류 본문 등이 스택트레이스로 노출 | `send_request` 가 `OSError`·`HTTPException` 을 잡고, 응답 파서에 `isinstance` 방어, `main` 에 최종 예외 처리 추가 |
| MEDIUM | 재생성 요청이 실패하면 쓸 수 있던 첫 초안까지 버림 | 재생성 실패 시 경고 후 첫 초안으로 후처리 |
| MEDIUM | 빈 출력이 재생성 경로를 타지 못하고 즉시 실패 | 파서가 빈 제목을 돌려주고 검증이 재생성을 결정, 재생성 후에도 비면 오류 |
| MEDIUM | 레지스트리 JSON 최상위가 배열이면 `AttributeError` | 형식 검사 추가, `RegistryError` 로 통일 |
| LOW | `*lock*` 패턴이 `clock.py` 같은 소스를 제외 | `*.lock`, `package-lock.json`, `yarn.lock`, `pnpm-lock.yaml` 로 한정 |
| LOW | 절단이 마스킹보다 먼저라 잘린 PEM 블록이 전송될 수 있음 | 파일 조각마다 마스킹 후 절단 |
| LOW | 브랜치명·파일 목록·`--context` 는 마스킹되지 않음 | safe-mode 에서 세 값도 마스킹 |
| LOW | 서두 문장이 제목이 되어도 재생성하지 않음 | `type:` 형식이 아니면 재생성 대상 |
| LOW | `temperature` 가 언급된 모든 400 을 기록 | "support/allow/deprecat/invalid" 등 거부 어구가 함께 있을 때만 기록 (OpenAI 는 `param` 필드 우선) |
| LOW | `AI_API_BASE_URL` 에 http 허용, 리디렉션 시 키 헤더 전달 | https 만 허용(로컬 호스트 예외), 리디렉션 미추종 |
| LOW | git 사용자 설정(색상, 외부 diff)이 출력에 섞임 | `--no-color --no-ext-diff --no-textconv` 고정 |
| LOW | 레지스트리 임시 파일 이름 고정으로 동시 실행 경쟁 | `tempfile.NamedTemporaryFile` + `os.replace` |
| LOW (미반영) | 추론 모델에서 작은 `max_tokens` 가 추론 토큰에 소진되어 빈 출력 | 빈 출력 시 재생성 1회 후 `--max-tokens` 안내 메시지로 대응. 기본값 상향은 비용 때문에 보류 |

## 6. 과제 목표별 근거 위치

| 과제 목표 | 코드 | 문서 |
| --- | --- | --- |
| 1. REST 연동 흐름(요청·응답·예외) | `providers.py` (`prepare`, `parse`, `translate_error`, `send_request`) | 평가 답변 Q1 |
| 2. 파라미터 영향 | `cli.py` 옵션, `model_registry.py`, `commands._resolve_settings` | 평가 답변 Q2, 학습 자료 3절 |
| 3. git 결과를 입력으로 연결 | `git_collector.py` | 평가 답변 Q3 |
| 4. 프롬프트 구성 원리 | `prompts.py`, `docs/04-prompt-templates.md` | 평가 답변 Q4 |
| 5. 검증·다듬기 | `validators.py`, `commands.run_generate` | 평가 답변 Q5 |

## 7. 한계와 다음 단계

- **실제 모델 출력 미확인.** 모델 응답을 제외한 모든 경로는 검증했지만, 프롬프트가 실제 모델에서 어떤 품질을 내는지는 키가 있어야 확인됩니다. 키 설정 후 `commit`, `pr` 을 각 1회 실행해 README 4장을 실제 출력으로 교체하고, 학습 자료 3절의 temperature 실험(0.0 / 0.5 / 1.0 × 3회)을 수행해 평가 답변 Q2 의 표를 채워야 합니다.
- **보너스 과제 미수행.** 보너스 1(이전 미션 저장소에 실제 PR), 2(컨벤션 설정 파일), 3(safe-mode 규칙 확장)은 가이드 5장의 절차대로 진행할 수 있습니다. 보너스 3 의 토대(`--provider` 별 내장 목록, `AI_API_BASE_URL`)는 이미 있습니다.
- **마스킹의 한계.** 정규식은 알려진 형태만 잡습니다. README 5장에 명시했습니다.
- **재시도 없음.** 429/5xx 에 자동 재시도를 하지 않고 안내만 합니다. 호출 횟수 제한을 명확히 지키기 위한 선택이며, 운영 환경이라면 SDK 의 재시도를 쓰는 편이 낫습니다.
