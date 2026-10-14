# temperature 실험 기록 (평가 답변 Q2 의 근거)

실행일 2026-10-14. 학습 자료 3절의 절차(같은 diff 로 `--temperature 0.0`, `0.5`, `1.0` 각 3회)를 그대로 따랐습니다.

## 1. 조건

| 항목 | 값 |
| --- | --- |
| 입력 diff | B2-1 `feature/search-amount-range` 의 변경 6개 파일 143줄 (보너스 1·2 와 같은 diff). 스크래치 클론에서 `git reset --soft main` 으로 스테이징 상태로 되돌려 `commit` 명령 사용 |
| 명령 | `python -m ai_gitgen commit --safe-mode --no-convention --temperature {T}` (기본 프롬프트, 컨벤션 파일 없음) |
| 모델 | 수업용 프록시 `https://copa.codyssey.kr` 의 `claude-sonnet-4` (OpenAI 호환 형식) |
| 호출 | 9회 (각 1회, 재생성 없음). 입력 3,552 토큰 고정, 출력 101~158 토큰 |
| 판정 기준 | (1) 제목이 3회 모두 같은가 (2) 72자 초과 (3) diff 에 근거 없는 내용 (4) 그 밖의 양식·내용 차이 |

## 2. 결과

| temperature | 제목이 3회 모두 같았나 | 72자 초과 | diff 에 없는 내용 | 그 밖의 차이 |
| --- | --- | --- | --- | --- |
| 0.0 | **예** (57자, 글자 단위로 동일) | 0회 | 0회 | 본문도 거의 같음. 3번째 불릿의 단어만 다름("검증" ↔ "거부", "파싱 연결" ↔ "파싱 및 전달 구현") |
| 0.5 | 아니오 (2회 같고 1회는 괄호 옵션명 생략, 28자) | 0회 | 0회 | 1회는 불릿이 2개로 줄어 테스트 변경 언급이 빠짐. 1회는 식별자에 백틱 사용 |
| 1.0 | 아니오 (3회 모두 다름: 쉼표 구분 / 백틱 / 슬래시 구분, 57~61자) | 0회 | 0회 | 백틱 사용 2회. 1회는 3번째 불릿에서 테스트 파일 이름을 빼고 "검증하는 테스트 케이스 추가"로 일반화. "역전 시 ValidationError" 같은 세부를 더 쓴 회차도 있음(diff 에 근거 있음) |

9회 모두 `type(scope): 설명` 형식, 마침표 없음, 불릿 `- ` 형식을 지켰고 README 변경은 9회 모두 언급하지 않았습니다(온도와 무관한 일관된 누락).

## 3. 해석

- **0.0 은 재현성이 매우 높지만 완전한 결정성은 아닙니다.** 프록시를 거친 `claude-sonnet-4` 는 temperature 0 에서도 본문 단어가 한두 개 바뀌었습니다. "같은 입력 → 같은 출력"을 테스트 기준으로 삼으면 깨질 수 있습니다.
- **예상과 달리 1.0 에서도 길이 위반·환각이 없었습니다.** 작성 전 예상표에는 "1.0 에서 72자 초과 1회, 근거 없는 '성능 개선' 1회"라고 적었는데, 3회 실험에서는 둘 다 0회였습니다. 입력이 명확한 diff 이고 시스템 프롬프트가 금지 사항을 명시한 덕으로 보입니다. 다만 3회는 적은 표본이라 "없다"가 아니라 "이 조건에서 관찰되지 않았다"입니다.
- **온도가 올라가면 먼저 흔들리는 것은 표기와 분량입니다.** 백틱 사용, 괄호·슬래시 같은 구분 기호, 불릿 수(2~3개), 파일 이름 생략이 1.0 에서 눈에 띄게 늘었습니다. 커밋 메시지는 팀 안에서 표기가 일정해야 하므로, 이 변동 자체가 비용입니다.
- **기본값 0.3 을 유지합니다.** 0.0 의 반복적 어색함은 이번 표본에서 보이지 않았지만, 0.0~0.5 구간에서 양식·사실성 차이가 없었으므로 표현 다양성을 조금 허용하는 0.3 이 합리적입니다. 표기 일관성이 더 중요하면 0.0 도 무방합니다.
- **검증 코드는 여전히 필요합니다.** 9회 중 위반이 없었다고 코드 검증을 뺄 수는 없습니다. 불릿 2개로 줄어드는 식의 내용 누락은 사람이 봐야 하고, 길이·형식은 코드가 확인해야 운이 아닌 보장이 됩니다.

## 4. 원문 (9회)

```text
# T=0.0 #1  (출력 142)
feat(search): 금액 범위 필터 옵션 추가 (--min-amount, --max-amount)

- models.py의 SearchCriteria에 min_amount/max_amount 필드 및 유효성 검사 추가
- cli.py와 commands.py에 --min-amount, --max-amount 인자 파싱 연결
- test_cli.py, test_services.py에 금액 범위 필터 및 역전 입력 검증 테스트 추가

# T=0.0 #2  (출력 145)
feat(search): 금액 범위 필터 옵션 추가 (--min-amount, --max-amount)

- models.py의 SearchCriteria에 min_amount/max_amount 필드 및 유효성 검사 추가
- cli.py와 commands.py에 --min-amount, --max-amount 인자 파싱 연결
- test_cli.py, test_services.py에 금액 범위 필터 동작 및 역전 입력 거부 테스트 추가

# T=0.0 #3  (출력 147)
feat(search): 금액 범위 필터 옵션 추가 (--min-amount, --max-amount)

- models.py의 SearchCriteria에 min_amount/max_amount 필드 및 유효성 검사 추가
- cli.py와 commands.py에 --min-amount, --max-amount 인자 파싱 및 전달 구현
- test_cli.py, test_services.py에 금액 범위 필터 및 역전 입력 검증 테스트 추가

# T=0.5 #1  (출력 101)
feat(search): 금액 범위 필터 옵션 추가 (--min-amount, --max-amount)

- models.py의 SearchCriteria에 min_amount/max_amount 필드 및 유효성 검사 추가
- cli.py와 commands.py에 --min-amount, --max-amount 인자 파싱 연결

# T=0.5 #2  (출력 150)
feat(search): 금액 범위 필터 옵션 추가 (--min-amount, --max-amount)

- models.py의 SearchCriteria에 min_amount/max_amount 필드 및 유효성 검사 추가
- cli.py와 commands.py에 --min-amount, --max-amount 인수 파싱 및 전달 구현
- test_cli.py, test_services.py에 금액 범위 필터 동작 및 역전 입력 오류 테스트 추가

# T=0.5 #3  (출력 145)
feat(search): 금액 범위 필터 옵션 추가

- `models.py`의 `SearchCriteria`에 `min_amount`/`max_amount` 필드 및 유효성 검사 추가
- `cli.py`와 `commands.py`에 `--min-amount`/`--max-amount` 인자 파싱 연결
- `test_cli.py`, `test_services.py`에 금액 범위 필터 관련 테스트 케이스 추가

# T=1.0 #1  (출력 142)
feat(search): 금액 범위 필터 옵션 추가 (--min-amount, --max-amount)

- models.py의 SearchCriteria에 min_amount/max_amount 필드 및 유효성 검사 추가
- cli.py, commands.py에 --min-amount/--max-amount 인자 파싱 및 전달 연결
- test_cli.py, test_services.py에 금액 범위 필터 관련 테스트 케이스 추가

# T=1.0 #2  (출력 158)
feat(search): 금액 범위 필터 옵션 추가 (`--min-amount`, `--max-amount`)

- `models.py` SearchCriteria에 `min_amount`/`max_amount` 필드 및 역전 시 ValidationError 추가
- `cli.py`, `commands.py`에 `--min-amount`/`--max-amount` 인자 파싱 연결
- `test_cli.py`, `test_services.py`에 금액 범위 필터 동작 및 유효성 검사 테스트 추가

# T=1.0 #3  (출력 150)
feat(search): 금액 범위 필터 옵션 추가 (--min-amount / --max-amount)

- models.py의 SearchCriteria에 min_amount/max_amount 필드 및 유효성 검증 로직 추가
- cli.py와 commands.py에 --min-amount, --max-amount 인자 파싱 및 전달 연결
- 금액 범위 필터 동작과 역전 입력 오류를 검증하는 테스트 케이스 추가
```
