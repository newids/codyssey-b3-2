# 보너스 2 — 커밋/PR 템플릿 커스터마이징 (팀 컨벤션 설정 파일)

작성일 2026-10-14.

## 1. 제출 증빙

| 항목 | 내용 |
| --- | --- |
| 분석 대상 저장소 | 이전 미션 B2-1 용돈 기입장 <https://github.com/newids/codyssey-b2-1> (커밋 3개, PR 1개) |
| 컨벤션 문서 | 이 문서 2~3장과 [README 8장](../README.md#8-팀-컨벤션-설정-파일-ai-gitgenjson) |
| 반영 방법 (구현) | ① 설정 파일 `.ai-gitgen.json` 자동 탐색 + `--convention PATH` / `--no-convention` 옵션 ② 프롬프트 규칙 치환 ③ 출력 검증·후처리 규칙 치환 (스코프 제거, 체크리스트·푸터 추가) |
| 컨벤션 파일 | [docs/conventions/codyssey-b2-1.ai-gitgen.json](conventions/codyssey-b2-1.ai-gitgen.json) |
| B2-1 루트 적용 | PR #1 머지 후 같은 파일을 B2-1 루트에 `.ai-gitgen.json` 으로 커밋(`46a991c`, 2026-10-14). `--convention` 없이 자동 적용되는 것을 [13-b2-1-convention-check.md](13-b2-1-convention-check.md) 에서 재현 |
| 적용 전/후 비교 | 5장. 같은 diff(B2-1 `feature/search-amount-range`, 143줄)로 커밋 메시지 1쌍 + PR 초안 1쌍, 수업용 프록시의 `claude-sonnet-4`, temperature 0.3 |
| 테스트 | 33개 추가 → 전체 162개, 커버리지 98% |

## 2. B2-1 저장소 스타일 분석

`git log --format=%B --all` 과 PR #1 본문을 읽고 정리했습니다. 커밋이 3개뿐이라 빈도보다 "일관되게 지킨 것"을 기준으로 삼았습니다.

| 항목 | 관찰 | 컨벤션 결정 |
| --- | --- | --- |
| 커밋 prefix | `feat:` 2회 (초기 커밋 1개 제외). 저장소 문서는 feat/fix/docs/test/refactor/chore 를 언급 | `types` 6개로 제한. `style`, `perf`, `ci`, `build`, `revert` 는 이 저장소에서 쓰지 않음 |
| 스코프 | `feat(search):` 같은 스코프 표기 없음. 대신 제목 안에 대상을 적음 (`search 명령에 …`) | `scope: forbidden` |
| 제목 문체 | 한국어 명사형, "〈대상〉에 〈무엇〉 추가/구현". 44~45자 | 50자 권장 / 72자 최대 유지 + 문체 규칙 1줄 |
| 본문 불릿 | 변경한 파일 이름으로 시작. 파일 이름 뒤 조사를 띄어 씀 (`models.py 의 SearchCriteria 에`) | `commit.rules` 에 명시 |
| 테스트·README 언급 | 두 커밋 모두 테스트 파일과 README 변경을 불릿으로 적음 | `commit.rules` 에 "테스트는 불릿 하나", "README 는 마지막 불릿" |
| PR 섹션 | `## Why`, `## What`, `## How to Test` 세 개 | 기본값 유지 |
| PR 불릿 문체 | 존댓말 종결(`~했습니다`). 파일 경로·식별자는 백틱 | `pr.rules` 에 명시 |
| 테스트 명령 | 표준 라이브러리 전용 프로젝트. `python -m unittest discover -s tests -t .` 와 `python -m unittest tests.모듈.클래스.메서드` | `pr.test_command` 고정. 보너스 1 에서 AI 가 pytest 를 제시해 손으로 고친 항목 |
| 직접 확인 절차 | 전제 조건("거래를 몇 건 등록한 뒤") + 기대 종료 코드·메시지 | `pr.rules` 에 명시. 보너스 1 수정점 6 |
| PR 꼬리말 | 초안을 ai-gitgen 으로 생성했다는 한 줄 | `pr.footer` 고정. 보너스 1 수정점 7 |
| 체크리스트 | 없었음. 저장소가 매번 확인하는 항목(전체 테스트, README 표, 의존성 없음)을 PR 템플릿으로 추가 | `pr.checklist` 3개 |

보너스 1 에서 AI 초안을 손으로 고친 7개 항목 중 5개(스코프 제거, pytest→unittest, 전제 조건, 꼬리말, 조사 띄어쓰기)가 이 표에 그대로 들어갔습니다. 즉 컨벤션 파일은 "지난번에 손으로 고친 것"을 규칙으로 옮긴 결과입니다.

## 3. 팀 컨벤션 정의 (`.ai-gitgen.json`)

```json
{
  "commit": {
    "types": ["feat", "fix", "docs", "test", "refactor", "chore"],
    "scope": "forbidden",
    "title_soft_limit": 50,
    "title_hard_limit": 72,
    "rules": [
      "제목은 '<명령/모듈>에 <무엇> 추가/수정' 처럼 대상과 동작을 명사형으로 쓴다 (예: search 명령에 금액 범위 옵션 추가)",
      "본문 불릿은 변경한 파일 이름으로 시작하고, 파일 이름 뒤 조사는 띄어 쓴다 (예: models.py 의 SearchCriteria 에)",
      "테스트를 바꿨으면 테스트 파일 이름과 추가한 케이스를 불릿 하나로 적는다",
      "README 를 바꿨으면 마지막 불릿에 적는다"
    ]
  },
  "pr": {
    "sections": ["Why", "What", "How to Test"],
    "test_command": "python -m unittest discover -s tests -t .",
    "checklist": [
      "python -m unittest discover -s tests -t . 전체 통과",
      "README 명령 요약 표 갱신 (옵션·명령이 바뀐 경우)",
      "표준 라이브러리만 사용 (새 의존성 없음)"
    ],
    "footer": "이 PR 의 커밋 메시지와 본문 초안은 [ai-gitgen](https://github.com/newids/codyssey-b3-2) 으로 생성한 뒤 검토·수정했습니다.",
    "rules": [
      "What 불릿은 `budget_app/models.py` 처럼 백틱으로 감싼 파일 경로로 시작하고, 함수·클래스·옵션 이름도 백틱으로 감싼다",
      "불릿 종결은 '~했습니다/~합니다' 존댓말로 통일한다",
      "How to Test 에는 전체 테스트 명령, 새 테스트만 실행하는 unittest 명령(tests.모듈.클래스.메서드), 직접 확인 절차를 각각 불릿으로 쓴다",
      "직접 확인 절차에는 전제 조건(예: 거래를 몇 건 등록한 뒤)과 기대하는 종료 코드·메시지를 적는다"
    ]
  }
}
```

키 설명과 각 값이 도구의 어느 단계에 반영되는지는 README 8장의 표에 있습니다. YAML 대신 JSON 을 고른 이유는 표준 라이브러리만 쓰는 프로젝트 원칙(`json` 모듈) 때문입니다.

## 4. 도구에 반영한 방법

| 단계 | 반영 내용 | 코드 |
| --- | --- | --- |
| 읽기·검증 | 실행 위치(저장소 루트)의 `.ai-gitgen.json` 을 자동으로 읽고, `--convention PATH` 로 다른 파일, `--no-convention` 으로 무시. 모르는 키, 잘못된 타입, 범위 밖 숫자, 비어 있거나 중복된 목록, 여러 줄 푸터, 20개·300자를 넘는 rules 는 키 이름을 포함한 오류로 거부하고 API 호출 전에 종료 | `convention.py` (`load_convention`, `parse_convention`) |
| 프롬프트 치환 | 허용 type 목록, 제목 형식(`type:` 만 / 스코프 선택 / 스코프 필수), 길이, 좋은 예, PR 섹션 골격과 섹션별 규칙, 테스트 명령, `[팀 컨벤션]` 블록(rules 그대로). 파일이 없으면 기존 프롬프트와 **바이트 단위로 동일** | `prompts.py` (`commit_system_prompt`, `pr_system_prompt`) |
| 검증 | type 이 목록 밖이면 형식 위반(재생성), `scope: forbidden` 인데 스코프가 있으면 후처리 대상, `scope: required` 인데 없으면 재생성 대상(스코프를 지어낼 수 없으므로), 섹션 목록·제목 길이는 컨벤션 값으로 검사 | `validators.py` (`validate_commit`, `validate_pr`) |
| 후처리 | 커밋·PR 제목의 스코프 제거(`feat(search):` → `feat:`), 컨벤션 섹션 순서로 재조립, How to Test 에 테스트 명령이 없으면 첫 불릿으로 삽입, `## Checklist` 를 팀 항목으로 고정, 푸터 추가. 두 번 적용해도 결과가 같음(멱등) | `validators.py` (`polish_commit`, `polish_pr`) |
| 보조 명령 | `convention show` (적용될 값과 출처 출력), `convention init` (기본값 파일 생성, 있으면 덮어쓰지 않음) | `commands.run_convention`, `cli.py` |

프롬프트에 넣는 것과 후처리로 붙이는 것을 나눈 기준은 "AI 가 판단해야 하는가"입니다. 문체·불릿 구성·테스트 명령 선택은 diff 를 읽고 써야 하므로 프롬프트 규칙으로, 체크리스트·푸터·스코프 제거는 diff 와 무관한 고정 텍스트이므로 토큰을 쓰지 않는 후처리로 처리했습니다.

## 5. 적용 전/후 비교

같은 변경(B2-1 `feature/search-amount-range`, 6개 파일 143줄)을 스크래치 클론에서 `--safe-mode` 로 생성했습니다. 커밋 비교는 `git reset --soft main` 으로 변경을 스테이징 상태로 되돌린 뒤 실행했고, PR 비교는 `--base main` 으로 브랜치 diff 를 썼습니다. 적용 전은 `--no-convention`, 적용 후는 `--convention docs/conventions/codyssey-b2-1.ai-gitgen.json` 입니다.

### 5.1 커밋 메시지

| | 적용 전 | 적용 후 |
| --- | --- | --- |
| 제목 | `feat(search): 금액 범위 필터 옵션 추가 (--min-amount, --max-amount)` | `feat: search 명령에 금액 범위 옵션 추가` |
| 불릿 1 | `models.py의 SearchCriteria에 min_amount/max_amount 필드 및 유효성 검사 추가` | `models.py 의 SearchCriteria 에 min_amount/max_amount 필드 및 유효성 검사 추가` |
| 불릿 2 | `cli.py와 commands.py에 --min-amount, --max-amount 인자 파싱 연결` | `cli.py 와 commands.py 에 --min-amount/--max-amount 인자 파싱 연결` |
| 불릿 3 | `test_cli.py, test_services.py에 금액 범위 필터 및 역전 입력 거부 테스트 추가` | `tests/test_cli.py, tests/test_services.py 에 금액 범위 필터 케이스 추가, README.md 에 옵션 및 예시 반영` |
| 토큰 | 입력 3,552 · 출력 142 | 입력 3,802 · 출력 146 |

달라진 점: ① 스코프가 사라지고 대상이 제목 안으로 들어가 B2-1 의 기존 제목(`feat: search 명령에 …`)과 같은 꼴이 됨 ② 파일 이름 뒤 조사 띄어쓰기 ③ 적용 전에는 빠졌던 README 변경이 들어옴. 보너스 1 에서 손으로 고친 커밋 메시지 변경 3개(스코프, 조사, README 누락)가 모두 자동으로 해결되었습니다. 대신 "역전 입력 거부" 같은 세부 묘사는 사라져 불릿 3개 제한 안에서 README 를 넣느라 테스트 설명이 짧아졌습니다.

### 5.2 PR 초안

| 항목 | 적용 전 | 적용 후 |
| --- | --- | --- |
| 제목 | `feat(search): 금액 범위 필터 옵션(--min-amount, --max-amount) 추가` | `feat: search 명령에 금액 범위 필터 옵션 추가 (--min-amount, --max-amount)` |
| Why 문체 | `… 조회가 불가능했음` (개조식) | `… 조회가 불가능했습니다.` (존댓말, B2-1 PR #1 과 동일) |
| What 구성 | 파일 4개를 한 줄씩, `commands.py` 는 "두 옵션을 파싱해 전달" | `parse_amount` 를 통해 파싱한다고 구체화, `__post_init__` 검증을 별도 불릿으로 분리 |
| How to Test 명령 | `python -m pytest tests/test_cli.py::CliFlowTests::… -v` (**이 저장소에 pytest 없음**) | `python -m unittest discover -s tests -t .` + 새 테스트 3개의 `python -m unittest tests.…` 명령 |
| 직접 확인 전제 | 없음 | "거래를 3건 이상 등록한 뒤" |
| Checklist | 없음 | `- [ ]` 3항목 (후처리) |
| 꼬리말 | 없음 | ai-gitgen 생성 표기 (후처리) |
| 토큰 | 입력 3,800 · 출력 583 | 입력 4,113 · 출력 680 |

보너스 1 에서 PR 초안을 손으로 고친 7개 중 스코프 제거(1), pytest→unittest(2), commands.py 설명 보강(5), 전제 조건(6), 도구 표기(7) 다섯 개가 자동으로 해결되었습니다. 남은 두 개는 "What 에 테스트 변경 추가"(3)와 "Why 에 설계 근거 추가"(4)인데, 후자는 작성자만 아는 내용이라 `--context` 로 줘야 하고, 전자는 6장에 적은 한계입니다.

## 6. 관찰과 한계

코드 리뷰(python-reviewer)에서 나온 지적과 반영:

| 심각도 | 지적 | 반영 |
| --- | --- | --- |
| HIGH | 커밋·PR 프롬프트가 제목 형식 문자열 표를 공유하면서 기본 PR 프롬프트의 어순(`type: 설명` 또는 `type(scope): 설명`)이 바뀜 | PR 전용 표로 분리하고, 기본 프롬프트 두 개의 SHA-256 을 도입 전 커밋 값으로 고정하는 골든 테스트 추가 |
| MEDIUM | 푸터 제거가 `endswith` 라서 본문 마지막 불릿이 푸터 문장으로 끝나면 본문을 잘라 냄 | `---` 구분선 + 푸터 줄 전체가 끝에 있을 때만 제거 |
| MEDIUM | 모델이 쓴 `## Checklist` 가 팀 항목을 덮어씀, `sections` 에 `Checklist` 가 있으면 항목이 안 붙음 | 팀 항목으로 항상 교체, 두 설정을 같이 쓰면 설정 오류 |
| MEDIUM | `test_command` 가 프롬프트 힌트일 뿐 검증·후처리가 없음 | How to Test 에 없으면 `[WARN]` + 첫 불릿으로 삽입 |
| MEDIUM | PR 제목은 스코프 금지 정책을 적용하지 않음 | 커밋과 같은 `strip_scope` 적용 |
| MEDIUM | `convention init` 의 exists→write 사이 경쟁, 심볼릭 링크 추종, OSError 가 "예상하지 못한 오류"로 보임 | `open(..., "x")` 배타적 생성, `FileExistsError`/`OSError` 를 사용자 메시지로 |
| MEDIUM | 저장소에 들어 있는 설정의 `rules` 가 시스템 프롬프트로 들어가므로 신뢰 모델 문서화와 양 제한 필요 | 규칙 20개·300자 제한, README 8장에 `[INFO] 컨벤션 적용:` 로그 확인과 `--no-convention` 안내 |
| LOW | BOM·바이너리 파일, 디렉터리 경로, 중복 섹션·type, `$` 대신 `fullmatch` | 모두 반영. 테스트 7개 추가 |

- **규칙은 대부분 지켜졌지만 전부는 아니다.** PR 의 What 에 `tests/` 변경 불릿이 여전히 빠졌습니다. 컨벤션에는 커밋 쪽에만 "테스트는 불릿 하나" 규칙이 있고 PR 쪽에는 없었기 때문으로, `pr.rules` 에 같은 문장을 추가하면 됩니다. 규칙을 넣어도 모델이 100% 따르는 것은 아니므로 결과는 여전히 초안입니다.
- **비용.** `[팀 컨벤션]` 블록과 섹션 규칙이 늘어 입력 토큰이 커밋 +250, PR +313 늘었습니다(7~8%). 후처리로 붙이는 체크리스트·푸터는 토큰을 쓰지 않습니다.
- **스코프 필수 정책은 재생성에 의존한다.** `scope: required` 인데 스코프가 없으면 도구가 스코프를 지어낼 수 없어 1회 재생성 후에도 없으면 `[WARN]` 과 함께 그대로 출력합니다.
- **설정 파일은 대상 저장소에 두는 것이 원칙**이지만, 이번에는 B2-1 의 열린 PR 을 건드리지 않기 위해 이 저장소의 `docs/conventions/` 에 두고 `--convention` 으로 지정했습니다. B2-1 루트에 `.ai-gitgen.json` 으로 복사하면 옵션 없이 적용됩니다.

## 7. 실행 로그

```text
$ python -m ai_gitgen commit --safe-mode --no-convention
[INFO] Git status 수집 완료: 6개 파일 변경 감지
[INFO] Git diff 수집 완료: 143줄
[INFO] safe-mode: 0개 항목 마스킹, 0개 파일 생략
[INFO] AI API 요청 중... (provider=openai, model=claude-sonnet-4, temperature=0.3, max_tokens=512, url=https://copa.codyssey.kr)
[INFO] AI API 호출 횟수: 1회 / 토큰 사용: 입력 3,552 · 출력 142
[DONE] 커밋 메시지 생성 완료

$ python -m ai_gitgen commit --safe-mode --convention docs/conventions/codyssey-b2-1.ai-gitgen.json
[INFO] 컨벤션 적용: .../docs/conventions/codyssey-b2-1.ai-gitgen.json
[INFO] Git status 수집 완료: 6개 파일 변경 감지
[INFO] Git diff 수집 완료: 143줄
[INFO] safe-mode: 0개 항목 마스킹, 0개 파일 생략
[INFO] AI API 요청 중... (provider=openai, model=claude-sonnet-4, temperature=0.3, max_tokens=512, url=https://copa.codyssey.kr)
[INFO] AI API 호출 횟수: 1회 / 토큰 사용: 입력 3,802 · 출력 146
[DONE] 커밋 메시지 생성 완료

$ python -m ai_gitgen pr --safe-mode --base main --context "search 가 날짜·카테고리·키워드·태그로만 걸러져서 ..." --convention docs/conventions/codyssey-b2-1.ai-gitgen.json
[INFO] 컨벤션 적용: .../docs/conventions/codyssey-b2-1.ai-gitgen.json
[INFO] 현재 브랜치: feature/search-amount-range
[INFO] 기준 브랜치 main 이후 커밋 1개 포함
[INFO] Git status 수집 완료: 6개 파일 변경 감지
[INFO] Git diff 수집 완료: 143줄
[INFO] safe-mode: 0개 항목 마스킹, 0개 파일 생략
[INFO] AI API 요청 중... (provider=openai, model=claude-sonnet-4, temperature=0.3, max_tokens=1024, url=https://copa.codyssey.kr)
[INFO] AI API 호출 횟수: 1회 / 토큰 사용: 입력 4,113 · 출력 680
[DONE] PR 초안 생성 완료
```

적용 후 PR 본문 전체:

```markdown
## Why
- `search` 명령이 날짜·카테고리·키워드·태그 기준만 지원하여 '5만원 이상 지출만 보기' 같은 금액 기준 조회가 불가능했습니다.

## What
- `budget_app/models.py`의 `SearchCriteria`에 `min_amount`, `max_amount` 필드를 추가하고, `matches()` 메서드에서 양 끝 포함 범위 필터링 로직을 구현했습니다.
- `budget_app/models.py`의 `SearchCriteria.__post_init__`에 `min_amount > max_amount`일 때 `ValidationError`를 발생시키는 유효성 검사를 추가했습니다.
- `budget_app/cli.py`에 `--min-amount`, `--max-amount` 인자를 등록하고, `budget_app/commands.py`의 `cmd_search`에서 `parse_amount`를 통해 파싱하여 `SearchCriteria`에 전달하도록 했습니다.
- `README.md`의 명령 옵션 표와 사용 예시를 업데이트했습니다.

## How to Test
- 전체 테스트 실행: `python -m unittest discover -s tests -t .`
- 새 테스트만 실행:
  - `python -m unittest tests.test_services.LedgerTests.test_search_filters_by_amount_range_inclusive`
  - `python -m unittest tests.test_services.LedgerTests.test_search_rejects_min_amount_greater_than_max`
  - `python -m unittest tests.test_cli.CliFlowTests.test_search_by_amount_range`
- 직접 확인: 거래를 3건 이상 등록한 뒤 `python -m budget_app search --type expense --min-amount 50000`을 실행하여 금액이 50,000원 이상인 지출 거래만 출력되는지 확인하고, `python -m budget_app search --min-amount 200 --max-amount 100` 실행 시 종료 코드 1과 함께 "최소 금액" 오류 메시지가 출력되는지 확인합니다.

## Checklist
- [ ] python -m unittest discover -s tests -t . 전체 통과
- [ ] README 명령 요약 표 갱신 (옵션·명령이 바뀐 경우)
- [ ] 표준 라이브러리만 사용 (새 의존성 없음)

---
이 PR 의 커밋 메시지와 본문 초안은 [ai-gitgen](https://github.com/newids/codyssey-b3-2) 으로 생성한 뒤 검토·수정했습니다.
```
