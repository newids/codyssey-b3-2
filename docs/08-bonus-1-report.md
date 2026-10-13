# 보너스 1 — 실제 리포지토리에 적용하여 PR 1건 완성

작성일 2026-10-13.

## 1. 제출 증빙

| 항목 | 내용 |
| --- | --- |
| 대상 저장소 | 이전 미션 B2-1 용돈 기입장 <https://github.com/newids/codyssey-b2-1> |
| 브랜치 | `feature/search-amount-range` |
| 변경 내용 | `search` 명령에 금액 범위 옵션 `--min-amount`, `--max-amount` 추가 (모델 검증, CLI, 핸들러, 테스트 3개, README) |
| **PR 링크** | **<https://github.com/newids/codyssey-b2-1/pull/1>** |
| 도구 호출 | 커밋 메시지 1회 + PR 초안 1회 (각 API 호출 1회, 총 2회) |
| 모델 | 수업용 프록시 `https://copa.codyssey.kr` 의 `claude-sonnet-4` (OpenAI 호환 형식, temperature 0.3) |

## 2. 진행 순서

1. B2-1 저장소에서 `feature/search-amount-range` 브랜치 생성.
2. "의미 있는 변경"으로 금액 범위 검색을 구현. 기존 `parse_amount`(쉼표 표기 허용)와 `SearchCriteria.__post_init__` 검증 패턴을 재사용. 테스트 94개 통과.
3. `python -m ai_gitgen commit --safe-mode` 로 커밋 메시지 초안 생성 → 검토·수정 → `git commit -F`.
4. 커밋 뒤 `python -m ai_gitgen pr --safe-mode --context "..."` 로 PR 초안 생성. 처음 실행에서는 "변경 사항이 없습니다"로 끝났는데(작업 트리가 비어 있었음), PR 은 브랜치 전체 변경을 봐야 하므로 도구를 보완한 뒤(4장) 재실행.
5. 초안 검토·수정 → 브랜치 push → `gh pr create` 로 PR 작성.

## 3. AI 초안 → 최종 PR 변경점

### 커밋 메시지

| | AI 초안 | 최종 |
| --- | --- | --- |
| 제목 | `feat(search): 금액 범위 필터 옵션 추가 (--min-amount, --max-amount)` | `feat: search 명령에 금액 범위 옵션(--min-amount, --max-amount) 추가` |
| 본문 | 모델·CLI·테스트 3개 불릿. README 변경 누락 | README 불릿 추가, "쉼표 표기 허용" 명시, 조사 띄어쓰기를 저장소 관례(`models.py 의`)에 맞춤 |

### PR 제목/본문

1. **제목 스코프 제거.** AI 는 `feat(search):` 를 썼지만 B2-1 의 기존 커밋은 스코프 없이 `feat:` 만 쓰므로 저장소 관례에 맞췄다.
2. **How to Test 의 테스트 명령 교체.** AI 는 `python -m pytest tests/test_cli.py::CliFlowTests::...` 를 제시했는데, B2-1 은 표준 라이브러리만 쓰는 프로젝트라 pytest 가 없다. `python -m unittest tests.test_cli.CliFlowTests.test_search_by_amount_range` 형식으로 바꿨다. 클래스·메서드 이름 자체는 AI 가 diff 에서 정확히 읽어 냈다.
3. **What 에 테스트 변경 추가.** AI 는 모델·CLI·핸들러·README 네 파일만 적고 `tests/` 변경을 빠뜨렸다. 테스트 3개와 통과 수(94개)를 불릿으로 추가했다.
4. **Why 에 설계 근거 한 줄 추가.** AI 의 Why 는 내가 `--context` 로 준 문장을 그대로 썼다(정확하지만 한 줄). `export`·`update` 가 쓰는 `parse_amount` 를 재사용해 금액 규칙을 일관되게 유지했다는 근거를 덧붙였다.
5. **What 의 commands.py 설명 보강.** "두 옵션을 파싱해 전달" → "`parse_amount` 로 해석해 전달, `100,000` 같은 쉼표 표기 허용"으로 구체화했다.
6. **직접 확인 절차에 전제 추가.** AI 의 "search 실행 후 확인"은 빈 저장소에서는 결과가 없으므로 "거래를 몇 건 등록한 뒤"를 앞에 넣었다.
7. **도구 사용 사실 표기.** 본문 끝에 초안을 ai-gitgen 으로 생성했다는 한 줄을 추가했다.

AI 초안에서 그대로 쓴 부분: Why 의 핵심 문장, What 의 네 파일 설명 구조, How to Test 의 세 단계 구성, 오류 케이스(`--min-amount 200 --max-amount 100` → 종료 코드 1, "최소 금액" 메시지) 확인 방법. diff 에 없는 내용을 지어낸 곳은 없었다.

## 4. 보너스 수행 중 도구에 반영한 개선

| 발견 | 반영 |
| --- | --- |
| 커밋을 마친 뒤 `pr` 을 실행하면 작업 트리가 비어 "변경 사항이 없습니다"로 끝남 | `pr` 은 기준 브랜치(`--base`, 없으면 `origin/HEAD` → `main` → `master`) 이후 커밋의 diff 와 커밋 제목 목록을 함께 수집. 파일 목록에 `(커밋됨)` 표시 |
| 수업용 프록시는 OpenAI 호환 형식(`/v1/chat/completions`, Bearer)으로 Claude 모델을 제공하고, Anthropic 형식 경로는 이 키로 403 | `AI_API_URL` 이 설정되면 기본 제공자를 OpenAI 호환 형식으로. `AI_PROVIDER` 로 바꿀 수 있음 |
| 프록시 모델 이름(`claude-sonnet-4`, `claude-haiku-4`)을 매번 옵션으로 주기 번거로움 | `AI_API_MODEL`(기본 모델), `AI_SMALL_FAST_MODEL`(`--fast` 옵션) 환경변수 지원 |
| 프록시를 거치면 제공자 이름과 모델 이름이 어긋나 내장 `temperature` 거부 목록이 적용되지 않음 | 모델 ID 는 제공자 간에 겹치지 않으므로 내장 목록을 제공자와 무관하게 조회 |

이 개선에 테스트 14개를 추가해 전체 129개가 통과합니다.

## 5. 실행 로그

커밋 메시지 생성:

```text
$ python -m ai_gitgen commit --safe-mode
[INFO] Git status 수집 완료: 6개 파일 변경 감지
[INFO] Git diff 수집 완료: 143줄
[INFO] safe-mode: 0개 항목 마스킹, 0개 파일 생략
[INFO] AI API 요청 중... (provider=openai, model=claude-sonnet-4, temperature=0.3, max_tokens=512, url=https://copa.codyssey.kr)
[INFO] AI API 호출 횟수: 1회 / 토큰 사용: 입력 3,552 · 출력 145
[DONE] 커밋 메시지 생성 완료

--- Commit Message ---
feat(search): 금액 범위 필터 옵션 추가 (--min-amount, --max-amount)

- models.py의 SearchCriteria에 min_amount/max_amount 필드 및 유효성 검사 추가
- cli.py, commands.py에 --min-amount/--max-amount 인자 파싱 및 전달 처리 추가
- test_cli.py, test_services.py에 금액 범위 필터 관련 테스트 케이스 추가
----------------------
```

PR 초안 생성(커밋 후):

```text
$ python -m ai_gitgen pr --safe-mode --context "search 가 날짜·카테고리·키워드·태그로만 걸러져서 '5만원 이상 지출만 보기' 같은 금액 기준 조회가 불가능했음"
[INFO] 현재 브랜치: feature/search-amount-range
[INFO] 기준 브랜치 main 이후 커밋 1개 포함
[INFO] Git status 수집 완료: 6개 파일 변경 감지
[INFO] Git diff 수집 완료: 143줄
[INFO] safe-mode: 0개 항목 마스킹, 0개 파일 생략
[INFO] AI API 요청 중... (provider=openai, model=claude-sonnet-4, temperature=0.3, max_tokens=1024, url=https://copa.codyssey.kr)
[INFO] AI API 호출 횟수: 1회 / 토큰 사용: 입력 3,800 · 출력 580
[DONE] PR 초안 생성 완료
```

AI 초안 본문 전체는 [README 4장](../README.md)에, 최종 본문은 PR 페이지에 있습니다.
