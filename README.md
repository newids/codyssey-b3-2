# ai-gitgen — git 변경 사항으로 커밋 메시지와 PR 초안 생성

`git status`, `git diff` 결과를 AI API(Claude 또는 OpenAI)에 보내 커밋 메시지와 Pull Request 초안을 터미널에 출력하는 Python CLI 도구입니다.
Codyssey 미션 B3-2 "내가 고친 코드 설명을 AI가 대신 써주는 도우미 만들기"의 결과물입니다.

생성 결과는 **초안**이며, 검토 후 직접 적용합니다. 이 도구는 `git commit`, `git push`, PR 생성을 실행하지 않습니다.

| 문서 | 내용 |
| --- | --- |
| [docs/08-bonus-1-report.md](docs/08-bonus-1-report.md) | 보너스 1: 실제 저장소에 적용한 PR 링크와 "AI 초안 → 최종 PR" 변경점 |
| [docs/09-bonus-2-report.md](docs/09-bonus-2-report.md) | 보너스 2: B2-1 스타일 분석 → 팀 컨벤션 정의 → 설정 파일 적용 전/후 비교 |
| [docs/10-bonus-3-report.md](docs/10-bonus-3-report.md) | 보너스 3: safe-mode 정책(숫자 기준), 정규식 규칙 확장, ON/OFF 비교, 보안 리뷰 반영 |
| [docs/11-temperature-experiment.md](docs/11-temperature-experiment.md) | temperature 0.0 / 0.5 / 1.0 × 3회 실험 원문과 해석 |
| [docs/12-pre-evaluation-feedback.md](docs/12-pre-evaluation-feedback.md) | AI 사전평가(16항목, 10 통과) 지적 사항과 반영 내역, 재검증 방법 |
| [docs/13-b2-1-convention-check.md](docs/13-b2-1-convention-check.md) | B2-1 루트의 `.ai-gitgen.json` 자동 적용 재현 절차(`scripts/b2-1-convention-check.sh`)와 `commit`·`pr` 적용/미적용 비교 |
| [docs/14-evaluation-item-answers.md](docs/14-evaluation-item-answers.md) | 평가 문항 18개에 대한 짧은 답안과 근거 파일 위치·링크 |
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

키는 **실행 시작 시** 확인합니다. 없으면 git 수집이나 API 호출을 하기 전에 아래 메시지를 내고 종료 코드 2 로 끝납니다. 로그에는 키를 읽은 환경변수 **이름**만 적고 값은 어디에도 출력하지 않습니다. `--dry-run` 은 API 를 부르지 않으므로 키 없이 실행됩니다.

```text
$ python3 -m ai_gitgen commit
[ERROR] AI_API_KEY 환경변수가 설정되지 않았습니다. API 를 호출하지 않고 종료합니다.
예) export AI_API_KEY="YOUR_KEY"  (또는 OPENAI_API_KEY)
       프롬프트만 확인하려면 --dry-run 을 쓰세요 (키 불필요).
$ echo $?
2
```

| 환경변수 | 용도 | 기본값 |
| --- | --- | --- |
| `AI_API_KEY` | API 키. 제공자와 무관하게 우선 사용 | 필수 |
| `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` | `AI_API_KEY` 가 없을 때 제공자별로 읽음 | 없음 |
| `AI_API_URL` | 프록시 주소. 설정하면 그 아래 `/v1/...` 경로로 요청 (https 만 허용, 로컬은 http 가능) | 공식 API 주소 |
| `AI_API_MODEL` | 기본 모델 덮어쓰기 | 제공자별 기본값 |
| `AI_SMALL_FAST_MODEL` | `--fast` 옵션이 쓰는 작고 빠른 모델 | claude `claude-haiku-4-5` / openai `gpt-4.1-nano` |
| `AI_PROVIDER` | 요청 형식 (`claude` = Messages API, `openai` = Chat Completions) | `AI_API_URL` 이 있으면 `openai`, 없으면 `claude` |
| `AI_GITGEN_HOME` | 모델 레지스트리 파일 위치 | `~/.ai-gitgen/` |

예: 수업용 프록시(OpenAI 호환 형식)를 쓰는 설정

```bash
export AI_API_KEY="YOUR_KEY"
export AI_API_URL=https://copa.codyssey.kr
export AI_API_MODEL=claude-sonnet-4
export AI_SMALL_FAST_MODEL=claude-haiku-4
```

프록시가 어떤 형식을 받는지 모르면 `curl "$AI_API_URL/v1/models" -H "authorization: Bearer $AI_API_KEY"` 로 모델 목록이 나오는지 확인하세요. Anthropic 형식만 받는 프록시라면 `AI_PROVIDER=claude` 를 함께 설정합니다.

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
python3 -m ai_gitgen pr --convention team.json    # 팀 컨벤션 설정 파일 지정 (8장)
```

### 옵션 (`commit`, `pr` 공통)

| 옵션 | 기본값 | 설명 |
| --- | --- | --- |
| `--provider` | `claude` (`AI_API_URL` 설정 시 `openai`) | 요청 형식 `claude` 또는 `openai` |
| `--model` | `AI_API_MODEL`, 없으면 claude `claude-sonnet-4-6` / openai `gpt-4.1-mini` | 모델 ID. 품질·비용 비교나 재현을 위해 고정할 때 지정 (아래 "옵션을 둔 이유") |
| `--fast` | 꺼짐 | `AI_SMALL_FAST_MODEL`(없으면 제공자별 소형 모델)로 생성. `--model` 과 함께 쓸 수 없음 |
| `--base` (pr 전용) | `origin/HEAD` → `main` → `master` 자동 탐지 | PR 비교 기준 브랜치. 기준 이후 커밋과 미커밋 변경을 함께 수집 |
| `--temperature` | `0.3` | 0.0(같은 diff 에 거의 같은 결과) ~ 1.0(표기·분량이 흔들림). 실험·비교 목적으로만 올림. 아래 "옵션을 둔 이유" |
| `--max-tokens` | commit `512`, pr `1024` | 출력 토큰 상한. 목표 길이가 아니라 안전장치. 부족하면 본문이 잘리고 `[WARN]`, 잘린 출력은 재생성하지 않음 |
| `--safe-mode` | 꺼짐 | 5장 참고 |
| `--max-files`, `--max-lines` | `10`, `200` | safe-mode 전송 상한 (파일 수 1~200, 파일당 줄 10~5000). 5장 |
| `--exclude GLOB`, `--mask NAME=REGEX` | 없음 | safe-mode 제외 패턴·마스킹 규칙 추가 (반복 가능). 5장 |
| `--context` | 없음 | 변경 이유 한 줄. PR 의 Why 섹션 품질이 좋아집니다 |
| `--dry-run` | 꺼짐 | 프롬프트만 출력, API 호출·비용 없음 |
| `--convention` | 현재 디렉터리의 `.ai-gitgen.json` | 팀 컨벤션 설정 파일 경로. 8장 참고 |
| `--no-convention` | 꺼짐 | 설정 파일이 있어도 기본 컨벤션 사용 (적용 전/후 비교용) |

> 과제 문서는 옵션을 `-model` 처럼 적었지만, Python `argparse` 관례에 따라 `--model` 로 구현했습니다.

### 결과를 복사해 적용하기

로그는 표준 오류(stderr), 결과는 표준 출력(stdout)으로 나옵니다. 결과 블록(`--- Commit Message ---` 아래)은 그대로 복사해 쓸 수 있고, 파일로 받아 편집기에서 검토한 뒤 커밋할 수도 있습니다. 도구는 git 에 직접 쓰지 않으며, `[DONE]` 줄에 "AI 초안입니다. 내용을 검토·수정한 뒤 적용하세요"를 매번 출력합니다.

```bash
python3 -m ai_gitgen commit > /tmp/msg.txt && git commit -e -F /tmp/msg.txt   # -e: 편집기에서 검토·수정 후 커밋
python3 -m ai_gitgen pr > /tmp/pr.md                                          # 첫 블록이 제목, 다음 블록이 본문
```

종료 코드로 상황을 구분하므로 스크립트에서 분기할 수 있습니다 (`--help` 끝에도 표시).

| 코드 | 상황 | 예 |
| --- | --- | --- |
| 0 | 초안 생성 성공 (`--dry-run`, `models`, `convention` 포함) | |
| 1 | 실행 중 오류 | API 401/429/5xx, 네트워크 오류, git 실행 실패 |
| 2 | 실행 전에 고쳐야 하는 설정·사용법 오류 | API 키 없음, `--temperature 1.5`, `--model` 과 `--fast` 동시 지정, 설정 파일 형식 오류 |
| 3 | 변경 사항 없음 (오류 아님, 생성할 것이 없음) | 깨끗한 작업 트리에서 `commit` |
| 130 | 사용자가 Ctrl+C 로 중단 | |

### 옵션을 둔 이유와 바꿨을 때의 영향

세 옵션은 "모델 출력은 설정에 따라 달라진다"는 사실을 **같은 diff 로 직접 확인**하기 위한 것입니다. 기본값은 커밋 메시지 용도에 맞춰 고정했고, 옵션은 재현·비교·실험용입니다.

| 옵션 | 둔 이유 | 바꾸면 달라지는 것 (실측) | 기록 |
| --- | --- | --- | --- |
| `--model` | 같은 diff 를 다른 모델로 돌려 품질·비용·속도를 비교하고, 재현할 때 모델을 고정하기 위해. 프록시처럼 모델 이름이 다른 환경에 맞추기 위해 | 가격(6장), `temperature` 지원 여부(7장), 출력 상한 필드 이름(12장) | 보너스 1·2 는 `claude-sonnet-4` |
| `--temperature` | "0.3 이 적절한가, 올리면 무엇이 먼저 흔들리는가"를 확인하기 위해. 재현성 실험의 축 | 0.0: 제목 3회 모두 글자 단위로 같음. 0.5: 1회는 불릿이 2개로 줄어 테스트 변경 누락. 1.0: 구분 기호(쉼표·백틱·슬래시)가 매번 다름. 72자 초과·근거 없는 내용은 9회 모두 0 | [docs/11](docs/11-temperature-experiment.md) |
| `--max-tokens` | 출력 상한은 비용 상한이 아니라 **절단 위험**의 조절 장치. 기본값이 충분한지, 모자라면 어떻게 깨지는지 보기 위해 | 60: 커밋 본문이 첫 불릿 중간에서 잘림. 150: PR 의 How to Test 가 통째로 사라짐 (4장 예시) | 4장 |

`temperature` 는 다음 토큰을 고를 때 확률 분포를 얼마나 평평하게 보는지입니다. 0 에 가까우면 거의 항상 가장 확률 높은 표현을 고르고, 1 에 가까우면 낮은 확률의 표현도 섞입니다. 커밋 메시지는 창의성보다 **사실성과 표기 일관성**이 중요하므로 낮게 두되, 0.0 도 완전한 결정성은 아니었기(본문 단어가 바뀜) 때문에 검증 코드는 온도와 무관하게 필요합니다.

`max_tokens` 는 모델이 할 말을 마치면 그 전에 멈추므로(`stop_reason: end_turn`) 넉넉히 둬도 비용이 늘지 않습니다. 반대로 모자라면 문장 중간에서 끊기고(`max_tokens`), 끊긴 PR 은 섹션이 사라져 구조 검증에 걸립니다. 이때 다시 요청해도 같은 자리에서 잘리므로 도구는 **재생성하지 않고** `--max-tokens` 를 늘리라고 안내합니다.

## 4. 출력 예시

> 커밋 메시지와 PR 초안 예시는 이전 미션 저장소 [codyssey-b2-1](https://github.com/newids/codyssey-b2-1) 의 `feature/search-amount-range` 브랜치에서
> 수업용 프록시(`claude-sonnet-4`)로 **실제 생성**한 출력입니다(2026-10-13). 이 초안을 검토·수정해 올린 PR 과 수정 내역은 [docs/08-bonus-1-report.md](docs/08-bonus-1-report.md)에 있습니다.
> 변경 없음·키 없음·max_tokens 절단 예시는 2026-10-14 사전평가 반영 후 다시 실행한 출력이고, 401 예시는 로컬 모의 서버로 재현한 것입니다([docs/07-result-report.md](docs/07-result-report.md) 3장).
> 커밋·PR 예시의 로그 줄(`API 키 확인`, `safe-mode 정책`, `제목 N자`, `[DONE]` 문구)은 현재 형식으로 맞췄습니다.

### 커밋 메시지

```text
$ python -m ai_gitgen commit --safe-mode
[INFO] API 키 확인: AI_API_KEY 설정됨
[INFO] Git status 수집 완료: 6개 파일 변경 감지
[INFO] Git diff 수집 완료: 143줄
[INFO] safe-mode 정책: 파일 10개 · 파일당 200줄 · 전체 2000줄 · 제외 패턴 10개 · 마스킹 규칙 9개
[INFO] safe-mode: 0개 항목 마스킹, 0개 파일 생략
[INFO] AI API 요청 중... (provider=openai, model=claude-sonnet-4, temperature=0.3, max_tokens=512, url=https://copa.codyssey.kr)
[INFO] AI API 호출 횟수: 1회 / 토큰 사용: 입력 3,552 · 출력 145
[INFO] 제목 57자: 권장 50자를 넘었습니다 (최대 72자). 더 짧게 쓰려면 괄호 보충 설명을 본문으로 옮기세요.
[DONE] 커밋 메시지 생성 완료. AI 초안입니다. 내용을 검토·수정한 뒤 적용하세요 (이 도구는 git 에 쓰지 않습니다)

--- Commit Message ---
feat(search): 금액 범위 필터 옵션 추가 (--min-amount, --max-amount)

- models.py의 SearchCriteria에 min_amount/max_amount 필드 및 유효성 검사 추가
- cli.py, commands.py에 --min-amount/--max-amount 인자 파싱 및 전달 처리 추가
- test_cli.py, test_services.py에 금액 범위 필터 관련 테스트 케이스 추가
----------------------
```

`[INFO] 제목 57자` 줄은 권장(50자)과 최대(72자)의 차이를 알립니다. 권장 초과는 그대로 두고 알리기만 하며, 최대를 넘으면 단어 경계에서 잘라 나머지를 본문 첫 불릿으로 옮기고 `[WARN] 후처리로 보정한 항목` 으로 표시합니다(9장).

### PR 초안

`pr` 은 기준 브랜치(`main`) 이후의 커밋과 미커밋 변경을 함께 수집하므로, 커밋을 마친 뒤에도 실행할 수 있습니다.

```text
$ python -m ai_gitgen pr --safe-mode --context "search 가 날짜·카테고리·키워드·태그로만 걸러져서 '5만원 이상 지출만 보기' 같은 금액 기준 조회가 불가능했음"
[INFO] API 키 확인: AI_API_KEY 설정됨
[INFO] 현재 브랜치: feature/search-amount-range
[INFO] 기준 브랜치 main 이후 커밋 1개 포함
[INFO] Git status 수집 완료: 6개 파일 변경 감지
[INFO] Git diff 수집 완료: 143줄
[INFO] safe-mode 정책: 파일 10개 · 파일당 200줄 · 전체 2000줄 · 제외 패턴 10개 · 마스킹 규칙 9개
[INFO] safe-mode: 0개 항목 마스킹, 0개 파일 생략
[INFO] AI API 요청 중... (provider=openai, model=claude-sonnet-4, temperature=0.3, max_tokens=1024, url=https://copa.codyssey.kr)
[INFO] AI API 호출 횟수: 1회 / 토큰 사용: 입력 3,800 · 출력 580
[DONE] PR 초안 생성 완료. AI 초안입니다. 내용을 검토·수정한 뒤 적용하세요 (이 도구는 git 에 쓰지 않습니다)

--- PR Title ---
feat(search): 금액 범위 필터 옵션(--min-amount, --max-amount) 추가

--- PR Body ---
## Why
- `search` 명령이 날짜·카테고리·키워드·태그 기준만 지원해 '5만원 이상 지출만 보기' 같은 금액 기준 조회가 불가능했음

## What
- `budget_app/models.py`: `SearchCriteria`에 `min_amount`, `max_amount` 필드 추가 및 `matches()` 메서드에 양 끝 포함 금액 필터 로직 구현; `min_amount > max_amount`일 때 `ValidationError` 발생
- `budget_app/cli.py`: `search` 서브커맨드에 `--min-amount`, `--max-amount` 인자 등록
- `budget_app/commands.py`: `cmd_search`에서 두 옵션을 파싱해 `SearchCriteria`에 전달
- `README.md`: `search` 명령 옵션 표와 사용 예시에 금액 범위 옵션 문서화

## How to Test
- `tests/test_cli.py`의 `test_search_by_amount_range` 실행: `python -m pytest tests/test_cli.py::CliFlowTests::test_search_by_amount_range -v`
- `tests/test_services.py`의 금액 범위 관련 테스트 실행: `python -m pytest tests/test_services.py::LedgerTests::test_search_filters_by_amount_range_inclusive tests/test_services.py::LedgerTests::test_search_rejects_min_amount_greater_than_max -v`
- 직접 확인: `python -m budget_app search --type expense --min-amount 50000` 실행 후 50,000원 이상 지출만 출력되는지 확인; `--min-amount 200 --max-amount 100` 입력 시 종료 코드 1과 "최소 금액" 오류 메시지 출력 확인
---------------
```

### 변경 사항이 없을 때

API 를 부르지 않고 종료 코드 3 으로 끝납니다. stdout 에는 아무것도 쓰지 않으므로 `commit > msg.txt` 로 받았을 때 빈 파일이 됩니다.

```text
$ python -m ai_gitgen commit
[INFO] API 키 확인: AI_API_KEY 설정됨
[INFO] 변경 사항이 없습니다. 커밋 메시지를 생성하지 않고 종료합니다 (종료 코드 3).
$ echo $?
3
```

### API 키가 없을 때

git 수집 전에 끝납니다(2장). 종료 코드 2.

```text
$ python -m ai_gitgen commit
[ERROR] AI_API_KEY 환경변수가 설정되지 않았습니다. API 를 호출하지 않고 종료합니다.
예) export AI_API_KEY="YOUR_KEY"  (또는 OPENAI_API_KEY)
       프롬프트만 확인하려면 --dry-run 을 쓰세요 (키 불필요).
```

### API 오류

키가 있지만 틀린 경우는 서버가 401 을 돌려주므로 요청 뒤에 알 수 있습니다. 종료 코드 1.

```text
$ AI_API_KEY=wrong python -m ai_gitgen commit
[INFO] API 키 확인: AI_API_KEY 설정됨
[INFO] Git status 수집 완료: 3개 파일 변경 감지
[INFO] Git diff 수집 완료: 32줄
[INFO] AI API 요청 중... (model=claude-sonnet-4-6, temperature=0.3, max_tokens=512)
[ERROR] 인증 실패 (HTTP 401): invalid x-api-key
       AI_API_KEY 값과 환경변수 이름을 확인하세요.
```

상태 코드별 메시지: 400 요청 형식 오류(본문 메시지 그대로), 401 인증 실패, 403 권한 없음, 404 모델을 찾을 수 없음, 429 요청 한도 초과(OpenAI 는 크레딧 소진과 구분), 5xx 서버 오류. 네트워크 실패와 시간 초과(60초)도 원인을 출력합니다.

### `max_tokens` 가 모자랄 때

같은 B2-1 변경에 `--max-tokens 60` 을 주면 본문이 첫 불릿 중간에서 끊깁니다. 잘림은 `[WARN]` 으로 알리고, 결과는 그대로 내보냅니다(사용자가 보고 늘려서 다시 실행).

```text
$ python -m ai_gitgen commit --safe-mode --max-tokens 60
[INFO] AI API 요청 중... (provider=openai, model=claude-sonnet-4, temperature=0.3, max_tokens=60, url=https://copa.codyssey.kr)
[WARN] 출력이 max_tokens 에서 잘렸습니다. --max-tokens 를 늘려 보세요.
[INFO] AI API 호출 횟수: 1회 / 토큰 사용: 입력 3,552 · 출력 60
[DONE] 커밋 메시지 생성 완료. AI 초안입니다. 내용을 검토·수정한 뒤 적용하세요 (이 도구는 git 에 쓰지 않습니다)

--- Commit Message ---
feat(search): 금액 범위 필터 옵션 추가 (--min-amount, --max-amount)

- models.py의 SearchCriteria에 min_amount/max_amount 필드 및 유효
----------------------
```

PR 은 뒤쪽 섹션부터 사라집니다. `--max-tokens 150` 이면 What 이 중간에서 끊기고 How to Test 는 아예 없습니다. 이 경우 구조 검증은 실패하지만 **재생성하지 않습니다**. 다시 요청해도 같은 자리에서 잘리기 때문이며, 호출 1회로 끝내고 원인을 알립니다.

```text
$ python -m ai_gitgen pr --safe-mode --base main --max-tokens 150
[WARN] 출력이 max_tokens 에서 잘렸습니다. --max-tokens 를 늘려 보세요.
[WARN] 출력이 잘려 구조가 깨졌습니다. 재생성하지 않고 후처리만 합니다. --max-tokens 를 늘려 다시 실행하세요.
[WARN] 후처리로 보정한 항목: "## How to Test" 섹션이 없습니다.
[INFO] AI API 호출 횟수: 1회 / 토큰 사용: 입력 3,630 · 출력 150

--- PR Body ---
## Why
- 기존 `search` 명령은 날짜·카테고리·태그 등으로만 필터링할 수 있어, 특정 금액 이상/이하의 거래를 조회하는 수단이 없었음.

## What
- `budget_app/models.py`: `SearchCriteria`에 `min_amount`, `max_amount` 필드 추가, `matches()`

## How to Test
- (작성 필요)
---------------
```

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

`git diff` 에는 API 키, 개인정보, 조직 내부 식별자가 섞일 수 있습니다. `--safe-mode` 는 세 층을 적용하고, 각 층은 설정 파일(`.ai-gitgen.json` 의 `safe_mode` 섹션, 8장과 같은 파일)과 CLI 옵션으로 조정할 수 있습니다. 우선순위는 내장 기본값 < 설정 파일 < CLI 옵션입니다.

| 층 | 정책 | 기본값 | 설정 파일 `safe_mode.*` | CLI | 범위 |
| --- | --- | --- | --- | --- | --- |
| 제외 | 패턴에 맞는 파일은 보내지 않고 `[생략된 파일: ...]` 에 이름만 | `.env`, `.env.*`, `*.pem`, `*.key`, `*.p12`, `*.lock`, `package-lock.json`, `yarn.lock`, `pnpm-lock.yaml`, `*.min.js` | `exclude` (추가만) | `--exclude GLOB` | 최대 50개 |
| 마스킹 | 정규식에 맞는 값을 `[MASKED:이름]` 으로. diff 와 브랜치·파일 목록·`--context` 에 같은 규칙 | 프라이빗 키 블록, `sk-ant-`/`sk-`/`AKIA`/`ghp_` 접두 키, JWT, `api_key = "..."` 형태 할당값, 이메일, 휴대전화 (9종) | `mask_rules: [{"name", "pattern"}]`, `disabled_rules` (`GENERIC_SECRET`, `EMAIL`, `PHONE_KR` 만) | `--mask NAME=REGEX` | 사용자 규칙 20개, 패턴 200자, 규칙당 실행 2초 |
| 제한 | 넘는 파일은 이름만, 넘는 줄은 `... (N줄 생략)` | 10개 파일, 파일당 200줄, 전체 2,000줄 | `max_files`, `max_lines_per_file`, `global_max_lines` | `--max-files`, `--max-lines` | 1~200, 10~5000, 100~20000 |

전체 2,000줄 상한은 safe-mode 가 꺼져 있어도 적용됩니다. 적용된 정책은 매 실행 `[INFO] safe-mode 정책: 파일 10개 · 파일당 200줄 · 전체 2000줄 · 제외 패턴 10개 · 마스킹 규칙 9개` 로 출력되고 `convention show` 로도 볼 수 있습니다.

```bash
python3 -m ai_gitgen commit --safe-mode --mask "INTERNAL_ID=EMP-\d{6}" --exclude "*.csv"   # 조직 식별자 규칙과 제외 패턴 추가
python3 -m ai_gitgen commit --safe-mode --max-files 5 --max-lines 100                        # 전송 상한 조정
```

설정 파일 예시 (`.ai-gitgen.json`):

```json
{
  "safe_mode": {
    "max_files": 8,
    "max_lines_per_file": 100,
    "exclude": ["*.csv", "docs/*"],
    "mask_rules": [{"name": "INTERNAL_ID", "pattern": "EMP-\\d{6}"}, {"name": "ORDER_ID", "pattern": "ORD-\\d{8}"}],
    "disabled_rules": []
  }
}
```

같은 변경(12개 파일 405줄, `.env`·고객 CSV·사번 포함)을 `--dry-run` 으로 비교한 결과입니다. 전체 표는 [docs/10-bonus-3-report.md](docs/10-bonus-3-report.md) 4장.

| | OFF | ON (기본값) | ON (위 설정 파일) |
| --- | --- | --- | --- |
| `<diff>` 줄 수 | 389 | 270 | 154 |
| 생략된 파일 | 0 | 2 (`.env` 외 1) | 5 (`.env`, CSV, docs, …) |
| 마스킹 | 0 | 4 (이메일 2, 전화 2) | 7 (사번 7) |
| 사번 `EMP-` 노출 | 13 | 12 (내장 규칙이 모르는 패턴) | **0** (`--context` 포함) |
| 이메일 노출 | 3 | 0 | 0 |

**설정 파일은 저장소 소유자가 통제합니다.** 보호를 더하는 설정(제외·규칙 추가)은 자유롭지만, 빼는 설정은 제한됩니다: 자격 증명 규칙 6종(`PRIVATE_KEY`, `ANTHROPIC_KEY`, `OPENAI_KEY`, `AWS_KEY`, `GITHUB_TOKEN`, `JWT`)은 끌 수 없고, 규칙을 끄거나 상한을 기본값보다 올리면 매 실행 `[WARN]` 으로 출처와 함께 알립니다. 사용자 정규식은 중첩 반복(`(a+)+`)·역참조·빈 매치 패턴을 거부하고, 실행 시간이 2초를 넘으면 규칙 이름과 함께 중단합니다(Unix 주 스레드에서만 동작하는 시그널 기반 제한). 남의 저장소에서는 `--no-convention` 으로 파일을 무시할 수 있습니다.

**한계.** 정규식은 형태가 알려진 값만 잡습니다. 임의 문자열 비밀번호는 통과할 수 있습니다. 비밀값은 커밋에 넣지 않는 것이 원칙이고, safe-mode 는 보조 수단입니다. 전송 내용은 `--dry-run` 으로 미리 확인할 수 있습니다.

### safe-mode 를 켜지 않았을 때의 경고와 확인 절차

`--safe-mode` 가 꺼져 있어도 같은 규칙으로 diff 를 **검사만** 해서, 걸리는 것이 있으면 전송 전에 무엇이 몇 개인지 알립니다(값은 바꾸지 않고 전송은 막지 않습니다. 스크립트 사용을 깨지 않기 위해서입니다).

```text
$ python -m ai_gitgen commit --dry-run
[INFO] Git status 수집 완료: 13개 파일 변경 감지
[INFO] Git diff 수집 완료: 405줄
[WARN] safe-mode 꺼짐: 민감정보로 보이는 값 7개 (GENERIC_SECRET 2, EMAIL 3, PHONE_KR 2) · 비밀 파일로 분류되는 파일 1개 (.env) 이(가) 그대로 전송됩니다.
       --safe-mode 를 켜거나 (값은 [MASKED:...] 로, 파일은 이름만), 보내도 되는지 확인한 뒤 진행하세요.
```

권장 절차: (1) 경고가 보이면 `--dry-run` 으로 `<diff>` 안의 해당 값을 확인하고, (2) 비밀값이면 커밋에서 빼거나 `--safe-mode` 로 다시 실행하고, (3) 내장 규칙이 모르는 조직 식별자라면 `--mask` 또는 설정 파일 `mask_rules` 에 추가합니다. 경고에 나오는 규칙 이름은 위 표의 마스킹 규칙과 같습니다.

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

## 8. 팀 컨벤션 설정 파일 (`.ai-gitgen.json`)

저장소마다 커밋 prefix, 스코프 표기, PR 섹션, 테스트 명령이 다릅니다. 저장소 루트(실행 위치)에 `.ai-gitgen.json` 을 두면 도구가 자동으로 읽어 **프롬프트 규칙**과 **출력 검증·후처리**에 함께 반영합니다. 파일이 없으면 아래 기본값으로 동작하며, 이때 프롬프트는 설정 기능이 없던 때와 완전히 같습니다.

```bash
python3 -m ai_gitgen convention init              # 기본값으로 채운 .ai-gitgen.json 생성 (있으면 덮어쓰지 않음)
python3 -m ai_gitgen convention show              # 적용될 값과 출처 확인
python3 -m ai_gitgen pr --convention path/to.json # 다른 위치의 파일 사용
python3 -m ai_gitgen pr --no-convention           # 파일을 무시하고 기본값으로 (전/후 비교)
```

| 키 | 기본값 | 반영 위치 | 설명 |
| --- | --- | --- | --- |
| `commit.types` | `feat, fix, docs, style, refactor, test, chore, perf, ci, build, revert` | 프롬프트 + 검증 | 허용 type. 목록 밖 type 은 형식 위반으로 1회 재생성 |
| `commit.scope` | `optional` | 프롬프트 + 검증 + 후처리 | `forbidden` 이면 커밋·PR 제목의 `feat(search):` 를 `feat:` 으로 고침. `required` 인데 없으면 재생성 (스코프는 지어낼 수 없음) |
| `commit.title_soft_limit` / `title_hard_limit` | `50` / `72` | 프롬프트 + 후처리 | 20~120 사이 정수, soft ≤ hard |
| `commit.rules` | 없음 | 프롬프트 `[팀 컨벤션]` 블록 | 자유 문장 규칙. 문체, 불릿 구성 등 |
| `pr.sections` | `Why, What, How to Test` | 프롬프트 + 검증 + 후처리 | 섹션 이름(`##` 생략 가능). 빠진 섹션은 재생성 후 `- (작성 필요)` |
| `pr.title_limit` | `80` | 프롬프트 + 후처리 | PR 제목 최대 길이 |
| `pr.test_command` | 없음 | 프롬프트 + 검증 + 후처리 | How to Test 에 그대로 넣을 테스트 명령. 모델이 빠뜨리면 첫 불릿으로 삽입 |
| `pr.checklist` | 없음 | 후처리 | `## Checklist` 섹션에 `- [ ]` 항목으로 추가. 모델이 쓴 체크리스트는 팀 항목으로 교체 (`sections` 에 `Checklist` 를 같이 쓰면 오류) |
| `pr.footer` | 없음 | 후처리 | 본문 끝에 `---` 뒤 한 줄 추가 (예: 도구 사용 표기) |
| `pr.rules` | 없음 | 프롬프트 `[팀 컨벤션]` 블록 | 자유 문장 규칙 |
| `safe_mode.*` | 5장 표 | sanitizer | safe-mode 전송 상한·제외 패턴·마스킹 규칙. 5장 참고 |

모르는 키, 잘못된 타입, 비어 있거나 중복된 `types`/`sections`, 범위 밖 숫자, 여러 줄 푸터는 키 이름을 포함한 `[ERROR]` 로 거부하고 API 를 호출하지 않습니다. 설정 파일은 저장소 안에 있으므로 `rules` 는 프롬프트에 그대로 들어갑니다. 남의 저장소를 받아 실행할 때는 `[INFO] 컨벤션 적용:` 로그로 어떤 파일이 읽혔는지 확인하거나 `--no-convention` 을 쓰세요 (규칙은 최대 20개, 각 300자로 제한).

B2-1 용돈 기입장 저장소를 분석해 만든 실제 예시가 [docs/conventions/codyssey-b2-1.ai-gitgen.json](docs/conventions/codyssey-b2-1.ai-gitgen.json) 에 있습니다 (스코프 금지, 6개 type, unittest 명령, 존댓말 불릿, 체크리스트 3개, 도구 표기 푸터). 같은 diff 로 적용 전/후를 비교하면 다음과 같습니다. 전체 비교는 [docs/09-bonus-2-report.md](docs/09-bonus-2-report.md) 5장. 같은 파일을 B2-1 루트에 넣어 옵션 없이 자동 적용되는 것을 확인한 절차는 [docs/13](docs/13-b2-1-convention-check.md) 과 `scripts/b2-1-convention-check.sh` 에 있습니다.

| | 적용 전 | 적용 후 |
| --- | --- | --- |
| 커밋 제목 | `feat(search): 금액 범위 필터 옵션 추가 (--min-amount, --max-amount)` | `feat: search 명령에 금액 범위 옵션 추가` |
| 커밋 불릿 | `models.py의 SearchCriteria에 …`, README 누락 | `models.py 의 SearchCriteria 에 …`, README 불릿 포함 |
| PR How to Test | `python -m pytest tests/test_cli.py::…` (저장소에 pytest 없음) | `python -m unittest discover -s tests -t .` + `python -m unittest tests.…` |
| PR 본문 | Why/What/How to Test 만 | + `## Checklist` 3항목 + 도구 표기 푸터 (후처리, 토큰 비용 없음) |

## 9. 출력 검증 규칙

| 대상 | 규칙 | 위반 시 |
| --- | --- | --- |
| 커밋 제목 | 50자 권장(soft), 72자 최대(hard), `type: 설명` 형식, 끝 마침표 없음 | 50자 초과: 그대로 두고 `[INFO] 제목 N자: 권장 50자를 넘었습니다` 로 안내. 72자 초과: 단어 경계에서 절단(잘린 부분은 본문 첫 불릿으로)하고 `[WARN]`. 마침표 제거, 서두 문장·코드 펜스 제거 (후처리) |
| 커밋 본문 | `- ` 불릿 | 불릿 아닌 줄을 불릿으로 변환 (후처리) |
| PR 제목 | 80자 최대 | 절단 (후처리) |
| PR 본문 | `## Why`, `## What`, `## How to Test` 헤더 + 각 1개 이상 불릿 | 1회 재생성 → 그래도 실패면 `- (작성 필요)` 로 채우고 `[WARN]` |
| 컨벤션 (8장) | 허용 type, 스코프 정책, 길이, 섹션 목록이 설정 파일 값으로 바뀜 | 스코프 금지 위반은 후처리로 제거, 스코프 필수 누락·목록 밖 type 은 재생성 |

**재생성 정책.** 재생성은 실행당 **최대 1회**이고, 어긴 규칙 목록과 이전 출력을 프롬프트에 넣어 요청합니다. 다음 경우에는 재생성하지 않습니다: 출력이 `max_tokens` 에서 잘린 경우(다시 요청해도 같은 자리에서 잘림), 이미 `temperature` 때문에 1회 재요청한 경우(호출 2회 상한). 재생성 요청 자체가 실패하면 첫 초안으로 후처리합니다. 재생성 뒤에도 결함이 남으면 `- (작성 필요)` 자리 표시자를 넣고 `[WARN]` 으로 알리며, 사용자가 채웁니다.

## 10. 프로젝트 구조

```text
ai_gitgen/
  cli.py             옵션 해석, 최상위 예외 처리, 종료 코드
  commands.py        commit / pr / models / convention 실행 흐름, 호출 횟수 제한
  config.py          기본값 상수, 환경변수
  convention.py      설정 파일(.ai-gitgen.json) 읽기·검증: 커밋/PR 컨벤션 + safe-mode 정책
  records.py         불변 데이터클래스 (GitChanges, GenerationResult, CommitMessage, ...)
  git_collector.py   git status --porcelain, git diff, git diff --cached, 새 파일은 diff --no-index
  sanitizer.py       safe-mode 마스킹·제외·제한 (정책 객체 적용, 사용자 규칙 실행 시간 제한)
  prompts.py         시스템/사용자 프롬프트 템플릿, 재생성 프롬프트
  providers.py       Claude/OpenAI 요청 조립·응답 파싱·오류 번역, urllib 전송, 호출 카운터
  model_registry.py  temperature 미지원 모델 목록 (내장 + 학습), JSON 파일
  validators.py      파싱, 규칙 검증, 후처리 (컨벤션 값 적용)
  formatter.py       [INFO]/[WARN]/[ERROR]/[DONE] 로그(stderr), 구분선 블록(stdout)
  errors.py          예외 클래스
tests/               204개 단위·통합 테스트 (API 키 불필요)
docs/                가이드, 학습 자료, 평가 답변, 프롬프트, 결과 보고서, 보너스 보고서, conventions/ 예시
scripts/             b2-1-convention-check.sh: B2-1 에서 commit·pr 컨벤션 자동 적용을 재현하는 스크립트 (docs/13)
```

### 수집 → 호출 → 후처리의 경계와 테스트 지점

각 단계는 **불변 데이터클래스**(`records.py`)를 주고받습니다. 앞 단계의 출력이 뒤 단계의 유일한 입력이므로, 단계마다 가짜 입력을 넣어 따로 테스트할 수 있습니다.

| 단계 | 모듈 | 입력 → 출력 | 분리한 이유 | 테스트 방법 |
| --- | --- | --- | --- | --- |
| 수집 | `git_collector.py` | 작업 디렉터리 → `GitChanges`(브랜치, 파일 목록, diff 문자열) | git 출력 형식(porcelain, 따옴표 경로, 새 파일)의 복잡성을 한곳에 가둠 | 임시 디렉터리에 실제 `git init` 후 파일을 바꿔 가며 확인 (`test_git_collector.py`) |
| 정제 | `sanitizer.py` | diff 문자열 + 정책 → `SanitizedDiff` | 마스킹·제외·절단은 네트워크·git 과 무관한 순수 문자열 처리 | 문자열 입력만으로 규칙별 확인 (`test_sanitizer.py`) |
| 프롬프트 | `prompts.py` | `GitChanges` + `SanitizedDiff` + 컨벤션 → `Prompt(system, user)` | 프롬프트 변경이 수집·호출 코드에 영향을 주지 않게. 기본 프롬프트는 SHA-256 골든 테스트로 고정 | 템플릿 조립 결과 문자열 검사 (`test_prompts.py`) |
| 호출 | `providers.py` | `Prompt` + `GenerationSettings` → `GenerationResult(text, 토큰, stop_reason)` | 제공자별 요청 형식·오류 번역을 `Provider` 프로토콜 뒤에 둠. SDK 로 바꿔도 여기만 수정 | `urlopen` 을 가짜로 바꿔 상태 코드별 응답 확인 (`test_providers.py`) |
| 검증·후처리 | `validators.py` | `GenerationResult.text` → `CommitMessage`/`PullRequestDraft` + `ValidationReport` | 모델이 무엇을 어겼는지(길이, 마침표, 서두 문장, 섹션 누락)를 코드가 판정하고, 기계적으로 고칠 수 있는 것은 API 없이 고침 | 결함을 심은 문자열로 판정과 교정 확인 (`test_validators.py`) |
| 흐름 | `commands.py`, `cli.py` | 옵션 → 위 단계 호출 → 종료 코드 | 호출 횟수 상한, 재생성 1회, 종료 코드 같은 정책을 한곳에서 | `collect_changes` 와 `AIClient` 를 가짜로 바꿔 전체 흐름과 로그 확인 (`test_cli.py`) |

후처리로 해결하는 문제의 예: 모델이 제목을 75자로 쓰면 단어 경계에서 잘라 나머지를 본문으로 옮기고, "다음은 커밋 메시지입니다:" 같은 서두를 붙이면 첫 `type:` 줄까지 버리며, 코드 펜스로 감싸면 벗깁니다. 이런 결함은 프롬프트로 줄일 수는 있어도 없앨 수 없어서 코드가 맡습니다(평가 답변 Q5).

## 11. 테스트

```bash
python3 -m unittest discover -s tests -t . -v        # 표준 라이브러리만으로 실행
```

API 키 없이 실행됩니다. HTTP 전송은 mock 으로, AI 클라이언트는 응답 큐를 가진 가짜 객체로 바꿔 검증하고, git 수집은 임시 디렉터리에 실제 `git init` 을 합니다. 커버리지(pytest-cov 기준) 98%.

## 12. 설계 결정

- **표준 라이브러리 `urllib` 로 직접 REST 호출.** 과제 목표가 "REST API 연동 흐름 설명"이므로 헤더·본문·상태 코드를 직접 다룹니다. SDK 로 바꾸려면 `providers.py` 만 교체하면 됩니다.
- **기본 모델 `claude-sonnet-4-6`.** 과제가 요구하는 `--temperature` 옵션을 실제로 받아 주는 모델 중 품질·비용 균형이 좋습니다. 최신 모델은 `temperature` 를 거부하므로 7장의 레지스트리로 처리합니다.
- **검증 실패는 후처리 우선, 구조 결함만 1회 재생성.** 호출 1~2회 제한을 지키면서 길이·기호 결함은 비용 없이 고칩니다.
- **결과는 초안.** 도구가 git 에 직접 쓰지 않고 stdout 으로 내보냅니다. 사용자가 검토 후 `git commit -F` 등으로 적용합니다.
- **새 파일도 내용 수집.** 추적되지 않은 파일은 `git diff` 에 나오지 않으므로 `git diff --no-index /dev/null <file>` 로 수집합니다(200KB 초과·바이너리 제외).
- **`pr` 은 브랜치 전체를 본다.** `commit` 은 미커밋 변경만 보지만, PR 은 보통 커밋을 마친 뒤 쓰므로 `git diff <base>...HEAD` 와 커밋 제목 목록(`git log`)을 함께 수집해 Why/What 의 근거로 넘깁니다. 기준 브랜치는 `--base` 또는 자동 탐지.
- **프록시 친화.** 수업용 프록시처럼 OpenAI 호환 형식으로 여러 회사 모델을 내주는 서버를 위해 `AI_API_URL`, `AI_API_MODEL`, `AI_SMALL_FAST_MODEL` 환경변수를 지원하고, 내장 `temperature` 거부 목록은 제공자와 무관하게 모델 ID 로 적용합니다.
- **git 출력 형식 고정.** `core.quotepath=false`, `--no-color`, `--no-ext-diff`, `--no-textconv`, `status -z` 를 써서 사용자 설정이나 한글·공백 파일명이 파싱과 safe-mode 제외 규칙을 깨지 않게 합니다.
- **키 유출 방지.** `AI_API_BASE_URL` 은 https 만 허용(로컬 테스트 서버만 http)하고, HTTP 리디렉션을 따르지 않아 키 헤더가 다른 호스트로 가지 않습니다.
- **키는 시작 시 확인, 종료 코드는 상황별로.** 키가 없으면 git 수집 전에 종료 코드 2 로 끝내고(로그에는 환경변수 이름만), 변경 없음은 3, 실행 오류는 1 로 나눠 스크립트에서 분기할 수 있게 했습니다(3장 표).
- **OpenAI 형식의 출력 상한 필드는 모델군으로 고른다.** 추론 모델(`gpt-5*`, `o1/o3/o4*`)만 `max_completion_tokens` 를 쓰고 나머지는 `max_tokens` 를 보냅니다. 수업용 프록시가 `max_completion_tokens` 를 무시해 `--max-tokens` 가 듣지 않는 것을 사전평가 반영 중 실측으로 발견했습니다([docs/12](docs/12-pre-evaluation-feedback.md)).
- **safe-mode 가 꺼져 있어도 검사는 한다.** 같은 규칙으로 세어서 경고만 하고 막지는 않습니다. 사용자가 모르고 보내는 일을 줄이면서 스크립트 사용은 깨지 않기 위해서입니다.
