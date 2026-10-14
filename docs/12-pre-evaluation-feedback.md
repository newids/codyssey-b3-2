# AI 사전평가 반영 기록

평가 시각 2026-10-14 20:23, 결과 **16항목 중 10개 통과(63%)**. 종합 의견은 "핵심 구조(수집·프롬프트·호출·검증·출력) 분리는 좋으나, API 키 누락 검사와 명시적 종료, 옵션화 이유와 파라미터 영향 설명, 일부 사용자 친화적 오류·종료 흐름이 부족"이었습니다.

FAIL 6개는 모두 같은 유형이었습니다. 기능은 있었지만 **(1) 실행되는 시점이 늦거나 (2) 종료 코드로 구분되지 않거나 (3) 이유가 문서에 없어서** 평가자가 "없다"고 판단할 수 있었습니다. 반영은 코드 5건, 문서 6건이며 같은 날 처리했습니다.

## 1. 항목별 지적과 반영

| # | 결과 | 지적 요지 | 반영 | 확인 |
| --- | --- | --- | --- | --- |
| 1 | PASS | 출력 예시와 "복사 가능" 안내가 없음 | README 3장 "결과를 복사해 적용하기": stdout/stderr 분리 설명, `commit > msg.txt && git commit -e -F msg.txt` 예시 | README 3장 |
| 2 | PASS | 명령 실행 시 기대 출력(터미널 스니펫)이 없음 | README 4장에 커밋·PR·변경 없음·키 없음·401·`max_tokens` 절단·재생성 7종 스니펫. 로그 줄은 현재 형식으로 갱신 | README 4장 |
| 3 | **FAIL** | 시작 시 API 키 미설정 검사·명시적 종료가 안 보임 | `run_generate` 가 **git 수집 전에** `config.resolve_api_key` 호출. 없으면 `MissingApiKeyError` → `[ERROR]` + `export` 예시 + `--dry-run` 안내, 종료 코드 2. 있으면 `[INFO] API 키 확인: AI_API_KEY 설정됨` (값은 출력하지 않음). `--dry-run` 은 키 없이 실행 | `test_missing_api_key_exits_before_git_collection`, `test_api_key_source_is_logged_by_name_only`, `test_dry_run_does_not_need_api_key` |
| 4 | **FAIL** | 변경 없음일 때 명시적 조기 종료(종료 코드)가 없음 | 종료 코드 **3**(`EXIT_NO_CHANGES`) 으로 분리하고 메시지에 코드를 표기. stdout 은 비움. 종료 코드 표를 `--help` 끝과 README 3장에 추가 | `test_no_changes_exits_with_code_three_without_api_call`, `test_exit_codes_are_distinct` |
| 5 | PASS | 누락 섹션별 수정 예시 출력 | 기존 동작 유지: 빠진 섹션을 `## 섹션\n- (작성 필요)` 로 채우고 `[WARN] 후처리로 보정한 항목: "## How to Test" 섹션이 없습니다.` 출력. 섹션별 예문 생성은 모델이 지어낼 수 없어 넣지 않음 | README 9장 |
| 6 | PASS | 옵션별 출력 비교 스크립트 없음 | 비교 절차와 결과를 문서화: temperature 9회(docs/11), `max_tokens` 60/150(README 4장). 실행 스크립트는 아래 3절 | docs/11, 아래 3절 |
| 7 | PASS | soft/hard 리미트 차이 안내 부족 | 권장(50자) 초과 시 `[INFO] 제목 57자: 권장 50자를 넘었습니다 (최대 72자). 더 짧게 쓰려면 ...`, 최대(72자) 초과 시 절단 + `[WARN]`. README 9장 표에 둘을 구분 | `test_title_over_soft_limit_is_noted_with_both_limits` |
| 8 | PASS | 수집/호출 경계와 테스트 방식 설명 | README 10장 "수집 → 호출 → 후처리의 경계와 테스트 지점" 표(단계·모듈·입출력·분리 이유·테스트 방법) | README 10장 |
| 9 | PASS | 후처리 이유·예시 문서화 | 같은 표 아래에 후처리가 해결하는 결함 예(75자 제목, 서두 문장, 코드 펜스)와 Q5 연결 | README 10장, docs/03 Q5 |
| 10 | **FAIL** | 모델/temperature/max_tokens 옵션화의 이유(재현성·실험) 설명 없음 | README 3장 "옵션을 둔 이유와 바꿨을 때의 영향" 표 + `--help` 문구에 목적 명시(`--temperature`: "낮을수록 재현성 ... 실험·비교 목적으로만 올리세요") | `python3 -m ai_gitgen commit --help` |
| 11 | **FAIL** | 키 누락 흐름 미구현, 인증 실패·네트워크 오류와 일관된 종료 동작 | #3 과 함께 종료 코드 체계 정리: 0 성공 / 1 실행 오류(401·429·5xx·네트워크·git) / 2 설정·사용법(키 없음·옵션·설정 파일) / 3 변경 없음 / 130 중단. `ConfigurationError` 계층 도입 | `test_cli.py` 각 시나리오, README 3장 표 |
| 12 | **FAIL** | temperature 가 출력에 미치는 영향 설명 없음 | README 3장에 실측 요약(0.0 제목 3/3 동일, 0.5 불릿 축소 1회, 1.0 구분 기호 매번 다름, 길이 위반·환각 0/9)과 원리 한 단락. 상세는 docs/11, docs/03 Q2 | README 3장 |
| 13 | **FAIL** | max_tokens 절단 위험·컨텍스트 손실 설명 부족 | 실제 실행 예 2종(README 4장): `commit --max-tokens 60` 은 본문 중간 절단, `pr --max-tokens 150` 은 How to Test 소실. 잘린 출력은 **재생성하지 않고** `--max-tokens` 안내(코드 변경). docs/03 Q2 에 표 추가 | `test_truncated_output_is_not_regenerated` |
| 14 | PASS | 민감정보 포함 시 경고·확인 절차 문서화 | safe-mode 가 꺼져 있어도 같은 규칙으로 검사해 `[WARN] safe-mode 꺼짐: 민감정보로 보이는 값 7개 (GENERIC_SECRET 2, EMAIL 3, PHONE_KR 2) · 비밀 파일 1개 (.env) 이(가) 그대로 전송됩니다.` 출력(막지는 않음). README 5장에 확인 절차 3단계 | `test_secrets_without_safe_mode_are_warned_before_sending`, `FindSensitiveTest` |
| 15 | PASS | 재생성 횟수·정책 명시 | README 9장 "재생성 정책": 최대 1회, 재생성하지 않는 경우(잘림, temperature 재요청 후), 실패 시 첫 초안 사용 | README 9장 |
| 16 | PASS | 출력에 눈에 띄는 "자동 적용 금지" 문구 | `[DONE]` 줄을 `커밋 메시지 생성 완료. AI 초안입니다. 내용을 검토·수정한 뒤 적용하세요 (이 도구는 git 에 쓰지 않습니다)` 로 변경. stdout 결과 블록은 그대로 두어 `git commit -F` 호환 유지 | `test_done_line_reminds_review_before_applying` |

## 2. 반영 중 발견한 결함: `--max-tokens` 가 프록시에서 무시됨

#13 의 예시를 만들려고 `commit --max-tokens 60` 을 실행했더니 출력이 134 토큰으로 잘리지 않았습니다. 원인은 OpenAI 호환 요청에 `max_completion_tokens` 만 보내고 있었는데, 수업용 프록시는 이 필드를 무시하고 `max_tokens` 만 적용하기 때문입니다.

| 요청 필드 (값 20) | 프록시 응답 |
| --- | --- |
| `max_tokens` | `completion_tokens: 20`, `finish_reason: length` (적용됨) |
| `max_completion_tokens` | `completion_tokens: 302`, `finish_reason: end_turn` (무시됨) |

반대로 OpenAI 의 추론 모델(`gpt-5*`, `o1/o3/o4*`)은 `max_tokens` 를 400 으로 거부합니다. 그래서 모델 이름으로 필드를 고르도록 고쳤습니다(`OpenAIProvider.token_limit_field`, 접두 목록은 `config.OPENAI_COMPLETION_TOKENS_PREFIXES`). 고친 뒤 같은 명령은 정확히 60 토큰에서 잘리고 `[WARN]` 이 나왔습니다. docs/06 의 관련 서술도 함께 고쳤습니다.

## 2-b. 반영 코드의 리뷰 결과

반영한 코드를 python-reviewer 로 검토해 HIGH 2건·MEDIUM 3건·LOW 2건을 받았고 모두 고쳤습니다.

| 심각도 | 지적 | 반영 |
| --- | --- | --- |
| HIGH | safe-mode 꺼짐 검사가 전체 줄 상한을 적용하기 **전**의 원본 diff 를 훑어, 수 MB diff 에서 느려지고 전송되지 않는 줄의 값까지 "그대로 전송됩니다"로 잘못 경고 | 실제 전송 텍스트(`SanitizedDiff.text`, 2,000줄 상한 적용 후)만 검사 |
| HIGH | 경고용 검사에서 저장소 설정의 사용자 정규식이 시간 제한에 걸리면 `MaskTimeoutError` 가 실행 전체를 중단 | `MaskTimeoutError` 를 잡아 `[WARN] 민감정보 사전 검사를 건너뜁니다` 로 바꾸고 계속 진행 |
| MEDIUM | `ApiCredential` 의 자동 `repr` 에 키 값이 포함되어 디버그 출력·테스트 실패 메시지로 샐 수 있음 | `field(repr=False)`, repr/str 에 값이 없는지 테스트 |
| MEDIUM | `AI_API_URL` 의 https 검사가 요청 직전에야 실행 | 키 검사와 같이 실행 시작 시 검사(`--dry-run` 포함), 종료 코드 2 |
| MEDIUM | `convention init` 의 "이미 있음"이 1, 다른 설정 오류는 2 로 불일치 | "이미 있음"은 2(사용법), 파일 쓰기 실패(OSError)는 1(환경) 로 정리 |
| LOW | `load_api_key` 가 코드에서 더 이상 쓰이지 않음, 종료 코드 상수가 세 모듈에 중복 | 함수 제거, `config.EXIT_*` 로 통일 |
| LOW | `openai/gpt-5` 처럼 벤더 접두가 붙은 모델 ID 는 추론 모델로 인식되지 않음 | `/` 뒤의 이름으로 판정 |

## 3. 재검증 방법

API 키 없이 확인할 수 있는 것:

```bash
python3 -m unittest discover -s tests -t .          # 204개, 약 3초
python3 -m ai_gitgen --help | tail -3               # 종료 코드 설명
env -u AI_API_KEY -u ANTHROPIC_API_KEY -u OPENAI_API_KEY python3 -m ai_gitgen commit; echo "exit=$?"   # 2, git 수집 로그 없음
python3 -m ai_gitgen commit --dry-run               # 키 없이 프롬프트 확인, safe-mode 꺼짐 경고 확인
```

깨끗한 저장소에서 `python3 -m ai_gitgen commit; echo "exit=$?"` 는 3 입니다.

옵션별 출력 비교(#6)는 같은 diff 를 두고 옵션만 바꿔 stdout 을 파일로 받아 `diff` 로 봅니다. temperature 실험(docs/11)에 쓴 절차와 같습니다.

```bash
for T in 0.0 0.5 1.0; do for i in 1 2 3; do
  python3 -m ai_gitgen commit --safe-mode --temperature $T > out_t${T}_$i.txt 2> log_t${T}_$i.txt
done; done
python3 -m ai_gitgen commit --safe-mode --max-tokens 60 > out_mt60.txt 2> log_mt60.txt
grep -h "^feat\|^fix" out_t*.txt | sort | uniq -c     # 제목이 몇 가지로 나뉘는지
grep -h "max_tokens 에서 잘렸습니다" log_mt60.txt
```

## 4. 반영하지 않은 것과 이유

- **#5 누락 섹션별 수정 예시 출력.** How to Test 가 비었을 때 예문을 도구가 써 넣으면 diff 에 근거 없는 내용이 들어갑니다. 자리 표시자 `- (작성 필요)` 와 `[WARN]` 으로 사람이 채우게 두는 편이 과제의 "근거 없는 내용 금지"와 맞습니다.
- **safe-mode 꺼짐 경고를 대화형 확인(y/N)으로 바꾸는 것.** 파이프·스크립트 사용을 깨뜨리므로 경고만 합니다. 막고 싶으면 `--safe-mode` 를 기본으로 쓰는 셸 별칭을 권장합니다.
- **변경 없음을 종료 코드 0 으로 두는 선택.** 오류가 아니라는 점에서 0 도 가능하지만, 스크립트에서 "초안이 생겼는가"를 분기하려면 구분이 필요해 3 을 택했습니다. `grep` 이 "일치 없음"에 1 을 돌려주는 것과 같은 관례입니다.
