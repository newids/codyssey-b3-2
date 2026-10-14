# B2-1 에서 컨벤션 자동 적용 재현하기

B2-1 저장소 루트에 `.ai-gitgen.json` 을 넣은 뒤(2026-10-14, 커밋 `46a991c`), `--convention` 옵션 없이 `ai_gitgen commit` 과 `ai_gitgen pr` 을 실행해도 팀 컨벤션이 적용되는지 확인한 절차입니다. 스크립트 한 번으로 재현됩니다.

## 1. 한 번에 실행

```bash
# codyssey-b3-2 루트에서. 기본값은 GitHub 의 B2-1 을 /tmp/b21-convention-check 에 클론
scripts/b2-1-convention-check.sh

# 로컬 클론과 다른 작업 디렉터리를 쓰려면
scripts/b2-1-convention-check.sh ~/orca/projects/codyssey-b2-1 /tmp/b21-check

# API 를 부르지 않고 프롬프트까지만 확인 (키 불필요)
DRY_RUN_ONLY=1 scripts/b2-1-convention-check.sh
```

전제: `AI_API_KEY`(과 프록시를 쓰면 `AI_API_URL`, `AI_API_MODEL`)가 환경변수에 있어야 합니다. 실제 호출은 4회(`commit` 적용·미적용, `pr` 적용·미적용)이고, 입력 3,500~4,100 토큰씩입니다. 작업 디렉터리와 `<작업 디렉터리>-out/` 이 이미 있으면 덮어쓰지 않고 종료 코드 2 로 끝납니다.

## 2. 스크립트가 하는 일

B2-1 의 `main` 은 PR #1 이 머지되어 깨끗하므로, 그대로 실행하면 `변경 사항이 없습니다 (종료 코드 3)` 으로 끝납니다. 그래서 "PR 변경이 스테이징되어 있고 컨벤션 파일은 추적 중"인 상태를 임시 클론에 다시 만듭니다. 실제 B2-1 저장소는 건드리지 않습니다.

| 단계 | 명령 | 이유 |
| --- | --- | --- |
| 1 | `git clone <B2-1> <WORK>` | 실제 저장소를 더럽히지 않기 위해 |
| 2 | `git checkout -b convention-check 4e293a6` | PR #1 **이전** 커밋(budget_app 최초 구현)으로 |
| 3 | `git checkout main -- .ai-gitgen.json` 후 커밋 (`CONVENTION_REF` 로 다른 ref 지정 가능) | 최신 컨벤션 파일을 **추적 상태**로 만든다. 커밋하지 않으면 `??` 새 파일로 수집되어 diff 에 섞인다 |
| 4 | `git diff 4e293a6 f0b1357 \| git apply --index` | PR #1 의 변경 6개 파일 143줄을 스테이징으로 올린다 |
| 5 | `commit --safe-mode --dry-run` | 프롬프트에 `[팀 컨벤션]` 블록이 들어가는지 확인 (호출 없음) |
| 6 | `commit --safe-mode` | 컨벤션 적용 결과 |
| 7 | `commit --safe-mode --no-convention` | 같은 diff 에 기본 컨벤션 결과 (비교용) |
| 8 | `git branch base-check`, `git checkout -b feature-check`, PR #1 의 메시지로 커밋 | `pr` 은 기준 브랜치 이후 **커밋**을 보므로, "기준 브랜치에는 컨벤션 파일만, 기능 브랜치에 PR 커밋 하나"를 만든다 |
| 9 | `pr --safe-mode --base base-check --context "..."` | PR 컨벤션 적용 결과. `--context` 는 보너스 1·2 와 같은 문구 |
| 10 | 같은 명령 + `--no-convention` | 기본 컨벤션 결과 (비교용) |

커밋 해시: `4e293a6` PR 이전, `f0b1357` PR #1 의 커밋, `59d163a` 머지 커밋, `46a991c` 컨벤션 파일 추가, `c51fddd` `pr.rules` 에 테스트 변경 규칙 추가. 3.6~3.8 은 `46a991c` 시점(`CONVENTION_REF=46a991c`), 3.9 는 `c51fddd` 시점의 결과입니다.

### 처음에 실패한 방법 두 가지

- **`main` 에 PR diff 를 다시 적용.** `git apply` 가 `patch does not apply` 로 실패합니다. `main` 에 이미 그 변경이 들어 있기 때문입니다.
- **클론 안에 출력 파일을 쓰기.** `dry.out` 같은 파일을 클론 안에 만들면 새 파일로 수집되어 "9개 파일 378줄", 입력 8,176 토큰이 됩니다. 출력은 클론 밖(`<WORK>-out/`)에 둡니다.

## 3. 실행 결과 (2026-10-14, `claude-sonnet-4`)

### 3.1 자동 적용 확인

로그 첫 줄에 작업 디렉터리의 설정 파일 경로가 나옵니다. `--convention` 을 주지 않았습니다.

```text
[INFO] 컨벤션 적용: /tmp/b21-check/.ai-gitgen.json
```

dry-run 프롬프트의 시스템 메시지 끝에 설정 파일 `commit.rules` 4개가 그대로 들어갑니다.

```text
[팀 컨벤션]
- 제목은 '<명령/모듈>에 <무엇> 추가/수정' 처럼 대상과 동작을 명사형으로 쓴다 (예: search 명령에 금액 범위 옵션 추가)
- 본문 불릿은 변경한 파일 이름으로 시작하고, 파일 이름 뒤 조사는 띄어 쓴다 (예: models.py 의 SearchCriteria 에)
- 테스트를 바꿨으면 테스트 파일 이름과 추가한 케이스를 불릿 하나로 적는다
- README 를 바꿨으면 마지막 불릿에 적는다
```

### 3.2 컨벤션 적용 (6 단계)

```text
$ python3 -m ai_gitgen commit --safe-mode
[INFO] 컨벤션 적용: /tmp/b21-check/.ai-gitgen.json
[INFO] API 키 확인: AI_API_KEY 설정됨
[INFO] Git status 수집 완료: 6개 파일 변경 감지
[INFO] Git diff 수집 완료: 143줄
[INFO] safe-mode 정책: 파일 10개 · 파일당 200줄 · 전체 2000줄 · 제외 패턴 10개 · 마스킹 규칙 9개
[INFO] safe-mode: 0개 항목 마스킹, 0개 파일 생략
[INFO] AI API 요청 중... (provider=openai, model=claude-sonnet-4, temperature=0.3, max_tokens=512, url=https://copa.codyssey.kr)
[INFO] AI API 호출 횟수: 1회 / 토큰 사용: 입력 3,798 · 출력 146
[DONE] 커밋 메시지 생성 완료. AI 초안입니다. 내용을 검토·수정한 뒤 적용하세요 (이 도구는 git 에 쓰지 않습니다)

--- Commit Message ---
feat: search 명령에 금액 범위 옵션 추가

- models.py 의 SearchCriteria 에 min_amount/max_amount 필드 및 유효성 검사 추가
- cli.py 와 commands.py 에 --min-amount/--max-amount 인자 파싱 연결
- tests/test_cli.py, tests/test_services.py 에 금액 범위 필터 케이스 추가, README.md 에 옵션 및 예시 반영
----------------------
```

### 3.3 비교: `--no-convention` (7 단계)

```text
$ python3 -m ai_gitgen commit --safe-mode --no-convention
[INFO] AI API 호출 횟수: 1회 / 토큰 사용: 입력 3,548 · 출력 145

--- Commit Message ---
feat(search): 금액 범위 필터 옵션 추가

- `models.py`의 `SearchCriteria`에 `min_amount`/`max_amount` 필드 및 유효성 검사 추가
- `cli.py`와 `commands.py`에 `--min-amount`/`--max-amount` 인자 파싱 연결
- `test_cli.py`, `test_services.py`에 금액 범위 필터 관련 테스트 케이스 추가
----------------------
```

### 3.4 차이 정리

| 규칙 (설정 파일) | `--no-convention` | 컨벤션 적용 | 반영 경로 |
| --- | --- | --- | --- |
| `commit.scope: forbidden` | `feat(search): ...` | `feat: ...` | 프롬프트 + 후처리(`strip_scope`) |
| 제목은 '<명령>에 <무엇> 추가' 명사형 | `금액 범위 필터 옵션 추가` | `search 명령에 금액 범위 옵션 추가` (설정 파일 예시와 글자 단위로 같음) | 프롬프트 |
| 파일 이름 뒤 조사 띄어쓰기 | `models.py`의 | `models.py 의` | 프롬프트 |
| README 를 바꿨으면 마지막 불릿에 | 언급 없음 | 마지막 불릿에 `README.md 에 옵션 및 예시 반영` | 프롬프트 |
| 백틱 표기 | 사용 | 사용하지 않음 | 프롬프트의 예시 문체를 따른 것으로, 명시 규칙은 아님 |

컨벤션 블록만큼 입력 토큰이 250개(3,548 → 3,798) 늘고, 호출 횟수와 출력 길이는 같습니다. 보너스 2 보고서([09-bonus-2-report.md](09-bonus-2-report.md))에서 `--convention docs/conventions/...json` 으로 명시해 얻은 결과와 제목이 같으며, 이번에는 파일을 저장소 루트에 둔 것만 다릅니다.

### 3.5 남는 차이

"테스트 불릿 하나 + README 는 마지막 불릿"이라는 두 규칙을 모델은 한 불릿에 합쳤습니다(세 번째 불릿). 시스템 프롬프트의 "불릿 1~3개" 제한과 규칙 두 개가 겹친 결과로 보이며, 이런 부분은 후처리로 확정할 수 없어 사용자가 커밋 전에 두 줄로 나누면 됩니다. 결과가 초안인 이유입니다.

### 3.6 PR: 컨벤션 적용 (9 단계)

```text
$ python3 -m ai_gitgen pr --safe-mode --base base-check --context "search 가 날짜·카테고리·키워드·태그로만 걸러져서 '5만원 이상 지출만 보기' 같은 금액 기준 조회가 불가능했음"
[INFO] 컨벤션 적용: /tmp/b21-check/.ai-gitgen.json
[INFO] API 키 확인: AI_API_KEY 설정됨
[INFO] 현재 브랜치: feature-check
[INFO] 기준 브랜치 base-check 이후 커밋 1개 포함
[INFO] Git status 수집 완료: 6개 파일 변경 감지
[INFO] Git diff 수집 완료: 143줄
[INFO] safe-mode 정책: 파일 10개 · 파일당 200줄 · 전체 2000줄 · 제외 패턴 10개 · 마스킹 규칙 9개
[INFO] safe-mode: 0개 항목 마스킹, 0개 파일 생략
[INFO] AI API 요청 중... (provider=openai, model=claude-sonnet-4, temperature=0.3, max_tokens=1024, url=https://copa.codyssey.kr)
[INFO] AI API 호출 횟수: 1회 / 토큰 사용: 입력 4,107 · 출력 664
[DONE] PR 초안 생성 완료. AI 초안입니다. 내용을 검토·수정한 뒤 적용하세요 (이 도구는 git 에 쓰지 않습니다)

--- PR Title ---
feat: search 명령에 금액 범위 필터 옵션(--min-amount, --max-amount) 추가

--- PR Body ---
## Why
- `search` 명령이 날짜·카테고리·키워드·태그 기준만 지원하여 '5만원 이상 지출만 보기' 같은 금액 기준 조회가 불가능했습니다.

## What
- `budget_app/models.py`의 `SearchCriteria`에 `min_amount`, `max_amount` 필드를 추가하고, `matches()` 메서드에서 양 끝 포함 범위 필터링 로직을 구현했습니다.
- `budget_app/cli.py`에 `--min-amount`, `--max-amount` 인자를 `search` 서브커맨드에 등록했습니다.
- `budget_app/commands.py`의 `cmd_search`에서 두 옵션 값을 `parse_amount`로 파싱하여 `SearchCriteria`에 전달하도록 했습니다.
- `README.md` 명령 표와 사용 예시에 `--min-amount`/`--max-amount` 옵션 및 예제를 추가했습니다.

## How to Test
- 전체 테스트 실행: `python -m unittest discover -s tests -t .`
- 금액 범위 단위 테스트만 실행: `python -m unittest tests.test_services.LedgerTests.test_search_filters_by_amount_range_inclusive tests.test_services.LedgerTests.test_search_rejects_min_amount_greater_than_max`
- CLI 통합 테스트만 실행: `python -m unittest tests.test_cli.CliFlowTests.test_search_by_amount_range`
- 직접 확인: 거래를 3건 이상 등록한 뒤 `python -m budget_app search --type expense --min-amount 50000` 을 실행하여 금액이 50,000원 이상인 지출 거래만 출력되는지 확인합니다. `--min-amount 200 --max-amount 100` 처럼 역전된 범위를 입력하면 종료 코드 1과 함께 "최소 금액" 오류 메시지가 출력되어야 합니다.

## Checklist
- [ ] python -m unittest discover -s tests -t . 전체 통과
- [ ] README 명령 요약 표 갱신 (옵션·명령이 바뀐 경우)
- [ ] 표준 라이브러리만 사용 (새 의존성 없음)

---
이 PR 의 커밋 메시지와 본문 초안은 [ai-gitgen](https://github.com/newids/codyssey-b3-2) 으로 생성한 뒤 검토·수정했습니다.
---------------
```

### 3.7 PR 비교: `--no-convention` (10 단계)

```text
[INFO] AI API 호출 횟수: 1회 / 토큰 사용: 입력 3,794 · 출력 530

--- PR Title ---
feat(search): 금액 범위 필터 옵션(--min-amount, --max-amount) 추가

--- PR Body ---
## Why
- 기존 `search` 명령이 날짜·카테고리·키워드·태그 기준만 지원하여 '5만원 이상 지출만 보기' 같은 금액 기반 조회가 불가능했음

## What
- `budget_app/cli.py`: `search` 서브커맨드에 `--min-amount`, `--max-amount` 인자 추가 (양 끝 포함)
- `budget_app/models.py`: `SearchCriteria`에 `min_amount`, `max_amount` 필드 추가, `matches()` 필터 로직 반영 및 최솟값이 최댓값보다 클 경우 `ValidationError` 발생
- `budget_app/commands.py`: `cmd_search`에서 두 옵션을 파싱해 `SearchCriteria`에 전달
- `README.md`: 명령 옵션 표 및 사용 예시에 금액 범위 옵션 문서화

## How to Test
- `python -m pytest tests/test_cli.py -k test_search_by_amount_range` 실행 후 금액 범위 필터·역전 입력 오류·잘못된 값 처리가 모두 통과하는지 확인
- `python -m pytest tests/test_services.py -k "test_search_filters_by_amount_range_inclusive or test_search_rejects_min_amount_greater_than_max"` 실행 후 경계값 포함 여부 및 ValidationError 발생 여부 확인
- 직접 실행: `python -m budget_app search --type expense --min-amount 50000` 으로 5만원 이상 지출 거래만 출력되는지 확인
---------------
```

### 3.8 PR 차이 정리

| 규칙 (설정 파일) | `--no-convention` | 컨벤션 적용 | 반영 경로 |
| --- | --- | --- | --- |
| `commit.scope: forbidden` (PR 제목에도 적용) | `feat(search): ...` | `feat: ...` | 프롬프트 + 후처리 |
| `pr.test_command` (unittest) | `python -m pytest ...` 2개 (저장소에 pytest 없음, 보너스 1 에서 손으로 고친 항목) | 첫 불릿 `python -m unittest discover -s tests -t .`, 새 테스트는 `python -m unittest tests.모듈.클래스.메서드` | 프롬프트 + 검증(없으면 삽입) |
| How to Test 세 종류(전체·새 테스트·직접 확인) | 2 + 1 | 전체 1, 새 테스트 2, 직접 확인 1 | 프롬프트 |
| 직접 확인에 전제 조건과 기대 종료 코드·메시지 | 전제 없음, 기대 메시지 없음 | "거래를 3건 이상 등록한 뒤", "종료 코드 1과 함께 \"최소 금액\" 오류 메시지" | 프롬프트 |
| 불릿 종결 존댓말 | `~불가능했음`, `~추가` | `~불가능했습니다.`, `~구현했습니다.` | 프롬프트 |
| `pr.checklist` 3개 | 없음 | `## Checklist` 에 `- [ ]` 3개 | 후처리 (토큰 비용 없음) |
| `pr.footer` | 없음 | `---` 뒤 도구 표기 한 줄 | 후처리 |

입력 토큰은 313개(3,794 → 4,107) 늘었고, 출력은 규칙대로 불릿이 늘어 530 → 664 입니다. 보너스 1 에서 AI 초안을 손으로 고친 7곳 중 스코프·pytest→unittest·전제 조건·도구 표기가 이번에도 자동으로 해결되었고, 보너스 2 보고서 5장과 같은 결과입니다.

### 3.9 `pr.rules` 에 테스트 변경 규칙을 추가한 뒤 (`c51fddd`)

B2-1 루트 파일에 다섯 번째 PR 규칙 "테스트를 바꿨으면 What 에 `tests/test_cli.py` 처럼 테스트 파일 경로와 추가한 케이스 이름을 불릿 하나로 적는다" 을 추가하고 스크립트를 다시 실행했습니다. What 이 다음과 같이 바뀌었습니다(입력 4,174 · 출력 751).

```text
## What
- `budget_app/models.py`의 `SearchCriteria`에 `min_amount`, `max_amount` 필드를 추가하고, `matches()` 메서드에 양 끝 포함 금액 범위 필터 로직을 구현했습니다.
- `budget_app/models.py`의 `SearchCriteria.__post_init__`에 `min_amount > max_amount`일 때 `ValidationError`를 발생시키는 유효성 검사를 추가했습니다.
- `budget_app/cli.py`에 `--min-amount`, `--max-amount` 인자를 등록하고, `budget_app/commands.py`의 `cmd_search`에서 `parse_amount`로 파싱하여 `SearchCriteria`에 전달하도록 했습니다.
- `tests/test_cli.py`에 `test_search_by_amount_range`, `tests/test_services.py`에 `test_search_filters_by_amount_range_inclusive` 및 `test_search_rejects_min_amount_greater_than_max` 케이스를 추가했습니다.
```

테스트 불릿은 규칙대로 들어왔지만 README 불릿이 빠졌습니다. 해석과 다음 조정은 보너스 2 보고서 8.5 절에 있습니다. `--no-convention` 결과는 이전과 같았습니다.

## 4. 정리 후

```bash
rm -rf /tmp/b21-convention-check /tmp/b21-convention-check-out
```

임시 클론의 `convention-check` 브랜치와 재현용 커밋은 푸시하지 않습니다.
