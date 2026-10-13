# ai-gitgen — git 변경 사항으로 커밋 메시지와 PR 초안 생성

`git status`, `git diff` 결과를 AI API(Claude 또는 OpenAI)에 보내 커밋 메시지와 Pull Request 초안을 터미널에 출력하는 Python CLI 도구입니다.
Codyssey 미션 B3-2 "내가 고친 코드 설명을 AI가 대신 써주는 도우미 만들기"의 결과물입니다.

생성 결과는 **초안**이며, 검토 후 직접 적용합니다. 이 도구는 `git commit`, `git push`, PR 생성을 실행하지 않습니다.

| 문서 | 내용 |
| --- | --- |
| [docs/01-mission-guide.md](docs/01-mission-guide.md) | 요구사항 분석, 설계, 구현 순서, 보너스 진행법, 점검표 |
| [docs/02-learning-materials.md](docs/02-learning-materials.md) | HTTP/REST, Messages API, 파라미터, git·subprocess, 프롬프트, 검증, 보안·비용 학습 자료 |
| [docs/03-evaluation-answers.md](docs/03-evaluation-answers.md) | 과제 목표 5문항 답변과 예상 추가 질문 |
| [docs/04-prompt-templates.md](docs/04-prompt-templates.md) | 프롬프트 원문과 설계 메모 |
| [docs/05-readme-template.md](docs/05-readme-template.md) | README 작성 양식(이 문서의 원형) |
| [docs/06-openai-api.md](docs/06-openai-api.md) | OpenAI API 대응표, 가격, 오류 코드 |
| [docs/07-result-report.md](docs/07-result-report.md) | 수행 결과 보고서: 테스트, 커버리지, 요구사항 대응, 한계 |

## 1. 설치

요구 사항: Python 3.10 이상, git. 외부 패키지는 쓰지 않으므로 `pip install` 이 필요 없습니다.

```bash
git clone https://github.com/newids/codyssey-b3-2.git
cd codyssey-b3-2
python3 --version          # 3.10 이상
python3 -m ai_gitgen --help
```

다른 프로젝트에서 쓰려면 이 저장소 경로를 `PYTHONPATH` 에 넣거나, `ai_gitgen/` 폴더를 그 프로젝트 루트에 복사합니다.

```bash
export PYTHONPATH=/path/to/codyssey-b3-2
cd /path/to/your-project && python3 -m ai_gitgen commit
```

## 2. 환경변수 설정

API 키는 환경변수로만 읽습니다. 코드에 키를 넣지 마세요.

```bash
export AI_API_KEY="YOUR_KEY"            # macOS / Linux (현재 셸)
setx AI_API_KEY "YOUR_KEY"              # Windows (새 터미널부터 적용)
```

| 환경변수 | 용도 | 기본값 |
| --- | --- | --- |
| `AI_API_KEY` | API 키. 제공자와 무관하게 우선 사용 | 필수 |
| `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` | `AI_API_KEY` 가 없을 때 제공자별로 읽음 | 없음 |
| `AI_PROVIDER` | 기본 제공자 (`claude` 또는 `openai`) | `claude` |
| `AI_GITGEN_HOME` | 모델 레지스트리 파일 위치 | `~/.ai-gitgen/` |
| `AI_API_BASE_URL` | 프록시나 테스트 서버로 엔드포인트를 바꿀 때 | 공식 API 주소 |

키가 없으면 다음 메시지와 함께 종료 코드 1 로 끝납니다.

```text
[ERROR] AI_API_KEY 환경변수가 설정되지 않았습니다.
예) export AI_API_KEY="YOUR_KEY"  (또는 ANTHROPIC_API_KEY)
```

## 3. 사용법

Git 저장소 **루트**에서 실행합니다. 하위 폴더에서 실행하면 루트 경로를 알려 주고 종료합니다.

```bash
python3 -m ai_gitgen commit                       # 커밋 메시지 생성
python3 -m ai_gitgen pr                           # PR 제목/본문 생성
python3 -m ai_gitgen commit --safe-mode           # 민감정보 마스킹 + 전송량 제한
python3 -m ai_gitgen pr --context "로그인 재시도 버그 수정"   # 변경 이유를 직접 제공
python3 -m ai_gitgen commit --dry-run             # API 호출 없이 프롬프트만 확인 (비용 0)
python3 -m ai_gitgen commit --provider openai     # OpenAI 로 생성
```

### 옵션 (`commit`, `pr` 공통)

| 옵션 | 기본값 | 설명 |
| --- | --- | --- |
| `--provider` | `claude` | `claude` 또는 `openai` |
| `--model` | claude `claude-sonnet-4-6`, openai `gpt-4.1-mini` | 모델 ID |
| `--temperature` | `0.3` | 0.0(결정적) ~ 1.0(다양). 커밋/PR 은 낮은 값 권장 |
| `--max-tokens` | commit `512`, pr `1024` | 출력 토큰 상한. 잘리면 `[WARN]` 출력 |
| `--safe-mode` | 꺼짐 | 5장 참고 |
| `--context` | 없음 | 변경 이유 한 줄. PR 의 Why 섹션 품질이 좋아집니다 |
| `--dry-run` | 꺼짐 | 프롬프트만 출력, API 호출·비용 없음 |

> 과제 문서는 옵션을 `-model` 처럼 적었지만, Python `argparse` 관례에 따라 `--model` 로 구현했습니다.

로그는 표준 오류(stderr), 결과는 표준 출력(stdout)으로 나옵니다. 결과만 파일로 받아 바로 쓸 수 있습니다.

```bash
python3 -m ai_gitgen commit > /tmp/msg.txt && git commit -F /tmp/msg.txt
python3 -m ai_gitgen pr > /tmp/pr.md      # 첫 블록이 제목, 다음 블록이 본문
```

## 4. 출력 예시

> 아래 출력은 이 저장소의 테스트용 데모 저장소(`sanitizer/rules.py` 에 GitHub 토큰 마스킹 규칙을 추가한 변경)에서 실제로 실행해 얻은 로그입니다.
> 단, 이 환경에는 API 키가 없어 **모델 응답 부분은 로컬 모의 서버가 돌려준 준비된 텍스트**입니다. 실제 키로 실행하면 문구는 달라집니다.
> 재현 방법은 [docs/07-result-report.md](docs/07-result-report.md) 3장에 있습니다.

### 커밋 메시지

```text
$ python -m ai_gitgen commit --safe-mode
[INFO] Git status 수집 완료: 3개 파일 변경 감지
[INFO] Git diff 수집 완료: 32줄
[INFO] safe-mode: 1개 항목 마스킹, 1개 파일 생략
[INFO] AI API 요청 중... (model=claude-sonnet-4-6, temperature=0.3, max_tokens=512)
[INFO] AI API 호출 횟수: 1회 / 토큰 사용: 입력 1,842 · 출력 69
[DONE] 커밋 메시지 생성 완료

--- Commit Message ---
feat(sanitizer): GitHub 토큰 마스킹 규칙 추가

- sanitizer.py 의 MASK_RULES 에 ghp_/gho_ 접두 토큰 정규식 추가
- tests/test_sanitizer.py 에 GitHub 토큰 마스킹 케이스 추가
----------------------
```

### PR 초안

```text
$ python -m ai_gitgen pr --context "safe-mode 마스킹 범위 확장" --safe-mode
[INFO] 현재 브랜치: feature/mask-github-token
[INFO] Git status 수집 완료: 3개 파일 변경 감지
[INFO] Git diff 수집 완료: 32줄
[INFO] safe-mode: 1개 항목 마스킹, 1개 파일 생략
[INFO] AI API 요청 중... (model=claude-sonnet-4-6, temperature=0.3, max_tokens=1024)
[INFO] AI API 호출 횟수: 1회 / 토큰 사용: 입력 1,962 · 출력 215
[DONE] PR 초안 생성 완료

--- PR Title ---
feat: safe-mode 마스킹 규칙에 GitHub 토큰 추가

--- PR Body ---
## Why
- safe-mode 가 AWS/Anthropic 키는 가리지만 GitHub 개인 액세스 토큰(ghp_)은 그대로 전송되고 있었습니다.

## What
- sanitizer.py: `gh[pousr]_` 접두 토큰을 잡는 GITHUB_TOKEN 규칙 추가
- tests/test_sanitizer.py: GitHub 토큰이 `[MASKED:GITHUB_TOKEN]` 으로 치환되는지 확인하는 테스트 추가

## How to Test
- `python -m unittest tests.test_sanitizer`
- 토큰이 포함된 파일을 수정한 뒤 `python -m ai_gitgen commit --safe-mode --dry-run` 으로 `[MASKED:GITHUB_TOKEN]` 확인
---------------
```

### 변경 사항이 없을 때

```text
$ python -m ai_gitgen commit
[INFO] 변경 사항이 없습니다. 커밋 메시지를 생성하지 않고 종료합니다.
```

### API 오류

```text
$ AI_API_KEY=wrong python -m ai_gitgen commit
[INFO] Git status 수집 완료: 3개 파일 변경 감지
[INFO] Git diff 수집 완료: 32줄
[INFO] AI API 요청 중... (model=claude-sonnet-4-6, temperature=0.3, max_tokens=512)
[ERROR] 인증 실패 (HTTP 401): invalid x-api-key
       AI_API_KEY 값과 환경변수 이름을 확인하세요.
```

상태 코드별 메시지: 400 요청 형식 오류(본문 메시지 그대로), 401 인증 실패, 403 권한 없음, 404 모델을 찾을 수 없음, 429 요청 한도 초과(OpenAI 는 크레딧 소진과 구분), 5xx 서버 오류. 네트워크 실패와 시간 초과(60초)도 원인을 출력합니다.

### 출력 구조 검증 실패 → 1회 재생성

```text
$ python -m ai_gitgen pr
[INFO] AI API 요청 중... (model=claude-sonnet-4-6, temperature=0.3, max_tokens=1024)
[WARN] 출력 구조가 규칙에 맞지 않아 1회 재생성합니다: "## How to Test" 섹션이 없습니다.
[INFO] AI API 요청 중... (model=claude-sonnet-4-6, temperature=0.3, max_tokens=1024)
[INFO] AI API 호출 횟수: 2회 / 토큰 사용: 입력 3,924 · 출력 274
[DONE] PR 초안 생성 완료
```

## 5. 민감정보 대응 (safe-mode)

`git diff` 에는 API 키, 개인정보가 섞일 수 있습니다. `--safe-mode` 는 세 층을 적용합니다.

| 층 | 정책 |
| --- | --- |
| 제외 | `.env`, `.env.*`, `*.pem`, `*.key`, `*.p12`, `*.lock`, `package-lock.json`, `yarn.lock`, `pnpm-lock.yaml`, `*.min.js` 는 보내지 않고 파일 이름만 전달 |
| 마스킹 | 프라이빗 키 블록, `sk-ant-`/`sk-`/`AKIA`/`ghp_` 접두 키, JWT, `api_key = "..."` 형태 할당값, 이메일, 휴대전화 번호 → `[MASKED:종류]` |
| 제한 | 최대 10개 파일, 파일당 최대 200줄. 넘는 부분은 `... (N줄 생략)` |

safe-mode 가 꺼져 있어도 전체 2,000줄 상한은 항상 적용됩니다.

같은 데모 저장소에서 `--dry-run` 으로 비교한 결과입니다.

| | safe-mode OFF | safe-mode ON |
| --- | --- | --- |
| `.env` 파일(토큰, 이메일 포함) | diff 전체가 프롬프트에 포함 | 파일 제외, `[생략된 파일: .env]` 로 표시 |
| 테스트 코드 안의 `ghp_...` 문자열 | 그대로 포함 | `[MASKED:GITHUB_TOKEN]` |
| 로그 | 없음 | `[INFO] safe-mode: 1개 항목 마스킹, 1개 파일 생략` |

**한계.** 정규식은 형태가 알려진 값만 잡습니다. 임의 문자열 비밀번호는 통과할 수 있습니다. 비밀값은 커밋에 넣지 않는 것이 원칙이고, safe-mode 는 보조 수단입니다. 전송 내용은 `--dry-run` 으로 미리 확인할 수 있습니다.

## 6. 비용과 요청 횟수

| 항목 | 값 |
| --- | --- |
| 1회 실행 API 호출 | 기본 1회. 최대 2회 (아래 두 경우 중 하나만 발생). 횟수와 토큰 수를 `[INFO]` 로 출력 |
| 2회가 되는 경우 | (a) PR 본문의 필수 섹션이 빠져 1회 재생성, (b) 레지스트리에 없던 모델이 `temperature` 때문에 400 을 돌려줘 `temperature` 없이 1회 재요청. (b)가 일어나면 (a)는 건너뛰고 후처리만 합니다 |
| 1회 비용 (대략) | 입력 2,000토큰 + 출력 200토큰 기준. `claude-sonnet-4-6` 약 $0.009, `claude-haiku-4-5` 약 $0.003, `gpt-4.1-mini` 약 $0.001 (2026-10 공식 가격) |
| 권장 | 큰 변경은 커밋을 나누고, 프롬프트 확인은 `--dry-run` 으로, 실험은 저렴한 모델로 |

## 7. 모델 호환성 관리 (`temperature` 미지원 모델)

최신 모델(Claude Opus 5.5, Sonnet 5.5, OpenAI gpt-5 계열 등)은 `temperature` 를 받지 않고 400 을 돌려줍니다. 도구는 이런 모델을 두 층으로 관리합니다.

| 층 | 내용 | 위치 |
| --- | --- | --- |
| 내장 목록 | 문서로 확인된 모델. Claude: `claude-opus-5-5`, `claude-opus-5`, `claude-opus-4-8`, `claude-opus-4-7`, `claude-sonnet-5-5`, `claude-sonnet-5`, `claude-haiku-5-5`, `claude-fable-5-1`, `claude-fable-5`. OpenAI: `gpt-5` 계열(5, 5.1, 5.2, 5.4, 5.5 와 mini/nano), `o1`, `o3`, `o3-mini`, `o4-mini` | 코드 상수 |
| 학습 목록 | 실행 중 400 응답에 `temperature` 가 언급된 모델. 사유·최초/최근 시각·횟수 기록 | `~/.ai-gitgen/model_registry.json` |

```text
$ python -m ai_gitgen commit --model claude-opus-5-5 --dry-run
[WARN] 'claude-opus-5-5' 는 temperature 를 지원하지 않아 생략합니다 (출처: 내장 목록)
[INFO] dry-run: API 를 호출하지 않습니다 (model=claude-opus-5-5, temperature=없음, max_tokens=512)

$ python -m ai_gitgen commit --model some-new-model
[INFO] AI API 요청 중... (model=some-new-model, temperature=0.3, max_tokens=512)
[WARN] temperature 미지원 모델로 기록했습니다. temperature 없이 다시 요청합니다
[INFO] AI API 요청 중... (model=some-new-model, temperature=없음, max_tokens=512)
[INFO] AI API 호출 횟수: 2회 / 토큰 사용: 입력 1,842 · 출력 69

$ python -m ai_gitgen commit --model some-new-model --dry-run     # 다음 실행부터
[WARN] 'some-new-model' 는 temperature 를 지원하지 않아 생략합니다 (출처: 2026-10-13 학습)
```

관리 명령:

```bash
python3 -m ai_gitgen models list                           # 내장·학습·제외 목록을 출처와 함께 출력
python3 -m ai_gitgen models add some-model --reason "사전 등록"
python3 -m ai_gitgen models remove claude-sonnet-5-5       # 내장 모델이면 제외 목록에 넣어 다시 temperature 를 보냄
python3 -m ai_gitgen models reset                          # 학습·제외 목록 초기화 (내장 목록 유지)
```

```text
$ python -m ai_gitgen models list
레지스트리 파일: /Users/me/.ai-gitgen/model_registry.json
제공자  모델               출처        사유                                      최근        횟수
claude  claude-opus-5-5    제외(내장)  사용자가 remove                           -           -
claude  claude-sonnet-5-5  내장 목록   -                                         -           -
...
claude  reject-demo-model  학습        temperature is not supported for this...  2026-10-13  1
```

모든 400 을 기록하지는 않습니다. `max_tokens` 범위 오류 같은 400 까지 기록하면 정상 모델이 거부 목록에 들어가므로, 메시지(OpenAI 는 `param` 필드)에 `temperature` 가 명시된 경우만 기록합니다. 레지스트리 파일은 사용자별 데이터이므로 저장소에 커밋하지 않습니다. 파일이 손상되면 `[ERROR]` 로 알리며 `models reset` 으로 복구합니다.

## 8. 출력 검증 규칙

| 대상 | 규칙 | 위반 시 |
| --- | --- | --- |
| 커밋 제목 | 50자 권장, 72자 최대, `type: 설명` 형식, 끝 마침표 없음 | 단어 경계에서 절단(잘린 부분은 본문 첫 불릿으로), 마침표 제거, 서두 문장·코드 펜스 제거 (후처리) |
| 커밋 본문 | `- ` 불릿 | 불릿 아닌 줄을 불릿으로 변환 (후처리) |
| PR 제목 | 80자 최대 | 절단 (후처리) |
| PR 본문 | `## Why`, `## What`, `## How to Test` 헤더 + 각 1개 이상 불릿 | 1회 재생성 → 그래도 실패면 `- (작성 필요)` 로 채우고 `[WARN]` |

## 9. 프로젝트 구조

```text
ai_gitgen/
  cli.py             옵션 해석, 최상위 예외 처리, 종료 코드
  commands.py        commit / pr / models 실행 흐름, 호출 횟수 제한
  config.py          기본값 상수, 환경변수
  records.py         불변 데이터클래스 (GitChanges, GenerationResult, CommitMessage, ...)
  git_collector.py   git status --porcelain, git diff, git diff --cached, 새 파일은 diff --no-index
  sanitizer.py       safe-mode 마스킹·제외·제한
  prompts.py         시스템/사용자 프롬프트 템플릿, 재생성 프롬프트
  providers.py       Claude/OpenAI 요청 조립·응답 파싱·오류 번역, urllib 전송, 호출 카운터
  model_registry.py  temperature 미지원 모델 목록 (내장 + 학습), JSON 파일
  validators.py      파싱, 규칙 검증, 후처리
  formatter.py       [INFO]/[WARN]/[ERROR]/[DONE] 로그(stderr), 구분선 블록(stdout)
  errors.py          예외 클래스
tests/               115개 단위·통합 테스트 (API 키 불필요)
docs/                가이드, 학습 자료, 평가 답변, 프롬프트, 결과 보고서
```

## 10. 테스트

```bash
python3 -m unittest discover -s tests -t . -v        # 표준 라이브러리만으로 실행
```

API 키 없이 실행됩니다. HTTP 전송은 mock 으로, AI 클라이언트는 응답 큐를 가진 가짜 객체로 바꿔 검증하고, git 수집은 임시 디렉터리에 실제 `git init` 을 합니다. 커버리지(pytest-cov 기준) 98%.

## 11. 설계 결정

- **표준 라이브러리 `urllib` 로 직접 REST 호출.** 과제 목표가 "REST API 연동 흐름 설명"이므로 헤더·본문·상태 코드를 직접 다룹니다. SDK 로 바꾸려면 `providers.py` 만 교체하면 됩니다.
- **기본 모델 `claude-sonnet-4-6`.** 과제가 요구하는 `--temperature` 옵션을 실제로 받아 주는 모델 중 품질·비용 균형이 좋습니다. 최신 모델은 `temperature` 를 거부하므로 7장의 레지스트리로 처리합니다.
- **검증 실패는 후처리 우선, 구조 결함만 1회 재생성.** 호출 1~2회 제한을 지키면서 길이·기호 결함은 비용 없이 고칩니다.
- **결과는 초안.** 도구가 git 에 직접 쓰지 않고 stdout 으로 내보냅니다. 사용자가 검토 후 `git commit -F` 등으로 적용합니다.
- **새 파일도 내용 수집.** 추적되지 않은 파일은 `git diff` 에 나오지 않으므로 `git diff --no-index /dev/null <file>` 로 수집합니다(200KB 초과·바이너리 제외).
- **git 출력 형식 고정.** `core.quotepath=false`, `--no-color`, `--no-ext-diff`, `--no-textconv`, `status -z` 를 써서 사용자 설정이나 한글·공백 파일명이 파싱과 safe-mode 제외 규칙을 깨지 않게 합니다.
- **키 유출 방지.** `AI_API_BASE_URL` 은 https 만 허용(로컬 테스트 서버만 http)하고, HTTP 리디렉션을 따르지 않아 키 헤더가 다른 호스트로 가지 않습니다.
