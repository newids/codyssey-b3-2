# B2-1 에서 컨벤션 자동 적용 재현하기

B2-1 저장소 루트에 `.ai-gitgen.json` 을 넣은 뒤(2026-10-14, 커밋 `46a991c`), `--convention` 옵션 없이 `ai_gitgen commit` 만 실행해도 팀 컨벤션이 적용되는지 확인한 절차입니다. 스크립트 한 번으로 재현됩니다.

## 1. 한 번에 실행

```bash
# codyssey-b3-2 루트에서. 기본값은 GitHub 의 B2-1 을 /tmp/b21-convention-check 에 클론
scripts/b2-1-convention-check.sh

# 로컬 클론과 다른 작업 디렉터리를 쓰려면
scripts/b2-1-convention-check.sh ~/orca/projects/codyssey-b2-1 /tmp/b21-check

# API 를 부르지 않고 프롬프트까지만 확인 (키 불필요)
DRY_RUN_ONLY=1 scripts/b2-1-convention-check.sh
```

전제: `AI_API_KEY`(과 프록시를 쓰면 `AI_API_URL`, `AI_API_MODEL`)가 환경변수에 있어야 합니다. 실제 호출은 2회(컨벤션 적용 1회, 비교용 `--no-convention` 1회)이고, 입력 약 3,800 토큰씩입니다. 작업 디렉터리와 `<작업 디렉터리>-out/` 이 이미 있으면 덮어쓰지 않고 종료 코드 2 로 끝납니다.

## 2. 스크립트가 하는 일

B2-1 의 `main` 은 PR #1 이 머지되어 깨끗하므로, 그대로 실행하면 `변경 사항이 없습니다 (종료 코드 3)` 으로 끝납니다. 그래서 "PR 변경이 스테이징되어 있고 컨벤션 파일은 추적 중"인 상태를 임시 클론에 다시 만듭니다. 실제 B2-1 저장소는 건드리지 않습니다.

| 단계 | 명령 | 이유 |
| --- | --- | --- |
| 1 | `git clone <B2-1> <WORK>` | 실제 저장소를 더럽히지 않기 위해 |
| 2 | `git checkout -b convention-check 4e293a6` | PR #1 **이전** 커밋(budget_app 최초 구현)으로 |
| 3 | `git checkout 46a991c -- .ai-gitgen.json` 후 커밋 | 컨벤션 파일을 **추적 상태**로 만든다. 커밋하지 않으면 `??` 새 파일로 수집되어 diff 에 섞인다 |
| 4 | `git diff 4e293a6 f0b1357 \| git apply --index` | PR #1 의 변경 6개 파일 143줄을 스테이징으로 올린다 |
| 5 | `commit --safe-mode --dry-run` | 프롬프트에 `[팀 컨벤션]` 블록이 들어가는지 확인 (호출 없음) |
| 6 | `commit --safe-mode` | 컨벤션 적용 결과 |
| 7 | `commit --safe-mode --no-convention` | 같은 diff 에 기본 컨벤션 결과 (비교용) |

커밋 해시: `4e293a6` PR 이전, `f0b1357` PR #1 의 커밋, `59d163a` 머지 커밋, `46a991c` 컨벤션 파일 추가.

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

## 4. 정리 후

```bash
rm -rf /tmp/b21-convention-check /tmp/b21-convention-check-out
```

임시 클론의 `convention-check` 브랜치와 재현용 커밋은 푸시하지 않습니다.
