# 보너스 3 — 안전 모드 고도화 (정규식 마스킹 규칙 확장 + 전송 제한 정책 조정)

작성일 2026-10-14.

## 1. 제출 증빙

| 항목 | 내용 |
| --- | --- |
| 정책 | 2장 표 (숫자 기준 포함). 기본값 → 설정 파일 `safe_mode` 섹션 → CLI 옵션 순으로 덮어씀 |
| 구현 | `.ai-gitgen.json` 의 `safe_mode` 섹션(파일·줄 상한, 제외 glob, 정규식 마스킹 규칙 추가, 오탐 규칙 비활성) + `--max-files`, `--max-lines`, `--exclude`, `--mask NAME=REGEX` 옵션 |
| ON/OFF 비교 | 4장. 같은 변경(12개 파일 405줄, 민감 파일·개인정보·내부 식별자 포함)을 `--dry-run` 으로 OFF / ON(기본) / ON(설정 파일) / ON(CLI) 네 가지로 비교 |
| 보안 리뷰 | 5장. security-reviewer 지적 HIGH 2 · MEDIUM 4 모두 반영 (정규식 실행 시간 제한, 끌 수 없는 자격 증명 규칙, 약화 경고) |
| 테스트 | 23개 추가 → 전체 185개, 커버리지 98% |

## 2. safe-mode 정책 (숫자 기준)

| 층 | 정책 | 기본값 | 설정 파일 키 (`safe_mode.*`) | CLI | 허용 범위 |
| --- | --- | --- | --- | --- | --- |
| 제외 | 이름이 패턴에 맞는 파일은 diff 를 보내지 않고 `[생략된 파일: ...]` 에 이름만 | 내장 10개 (`.env`, `.env.*`, `*.pem`, `*.key`, `*.p12`, `*.lock`, `package-lock.json`, `yarn.lock`, `pnpm-lock.yaml`, `*.min.js`) | `exclude` (내장에 **추가**만 가능, 제거 불가) | `--exclude GLOB` (반복) | 최대 50개 |
| 마스킹 | 정규식에 맞는 값을 `[MASKED:이름]` 으로 치환. diff 와 함께 브랜치 이름·파일 목록·`--context` 에도 적용 | 내장 9개 (`PRIVATE_KEY`, `ANTHROPIC_KEY`, `OPENAI_KEY`, `AWS_KEY`, `GITHUB_TOKEN`, `JWT`, `GENERIC_SECRET`, `EMAIL`, `PHONE_KR`) | `mask_rules: [{"name", "pattern"}]` (내장 뒤에 적용), `disabled_rules` (`GENERIC_SECRET`, `EMAIL`, `PHONE_KR` 만 끌 수 있음) | `--mask NAME=REGEX` (반복) | 사용자 규칙 최대 20개, 패턴 200자, 이름 `[A-Z][A-Z0-9_]{1,30}`, 규칙당 실행 2초 |
| 파일 수 | 넘는 파일은 이름만 | 10 | `max_files` | `--max-files N` | 1~200 |
| 파일당 줄 | 넘는 부분은 `... (N줄 생략)` | 200 | `max_lines_per_file` | `--max-lines N` | 10~5000 |
| 전체 줄 | **safe-mode 가 꺼져 있어도** 적용 | 2,000 | `global_max_lines` | 없음 (파일로만) | 100~20,000 |

정책 우선순위: 내장 기본값 < `.ai-gitgen.json` 의 `safe_mode` < CLI 옵션. CLI 옵션은 `--safe-mode` 와 함께 쓸 때만 적용되며, 없이 주면 `[WARN]` 으로 알립니다. 적용된 정책은 매 실행 `[INFO] safe-mode 정책: 파일 10개 · 파일당 200줄 · 전체 2000줄 · 제외 패턴 10개 · 마스킹 규칙 9개` 로 출력되고, `convention show` 의 `[safe_mode]` 블록에서도 볼 수 있습니다.

### 2.1 예시 설정 (4장 비교에 쓴 파일)

```json
{
  "safe_mode": {
    "max_files": 8,
    "max_lines_per_file": 100,
    "exclude": ["*.csv", "docs/*"],
    "mask_rules": [
      {"name": "INTERNAL_ID", "pattern": "EMP-\\d{6}"},
      {"name": "ORDER_ID", "pattern": "ORD-\\d{8}"},
      {"name": "SLACK_TOKEN", "pattern": "xox[abp]-[A-Za-z0-9-]{10,}"}
    ]
  }
}
```

### 2.2 거부되는 설정

설정 파일은 저장소 안에 들어 있어 남이 쓴 것일 수 있습니다. 다음은 API 호출 전에 키 이름을 포함한 `[ERROR]` 로 거부합니다.

| 입력 | 이유 |
| --- | --- |
| `"pattern": "(a+)+$"`, `"(a)\\1"` | 중첩 반복·역참조는 역추적 폭발(ReDoS) 위험. 휴리스틱 거부 + 실행 시 2초 제한(아래) |
| `"pattern": "x*"`, `".*"` | 빈 문자열에 매치되어 모든 글자 사이에 `[MASKED:...]` 가 들어감 |
| `"pattern": "\\[MASKED:.*\\]"` | 치환 결과에 다시 매치되어 마스킹이 중첩됨 |
| `"name": "EMAIL"`, `"bad name"` | 내장 규칙과 이름 충돌, 이름 형식 위반 |
| `"disabled_rules": ["PRIVATE_KEY"]` | 자격 증명 규칙 6개는 끌 수 없음 |
| `"max_files": 0`, `true`, `2.5` | 범위 밖 또는 정수 아님 |
| 파일 1MB 초과, 모르는 키 | 크기 제한, 오타 방지 |

## 3. 구현

| 위치 | 내용 |
| --- | --- |
| `convention.py` | `SafeModePolicy`, `MaskRule` 불변 데이터클래스. `_parse_safe_mode` 가 범위·타입·중복·개수 검증, `compile_mask_rule` 이 이름·정규식 검증(컴파일 오류, 빈 매치, 치환 결과 매치, 중첩 반복·역참조 휴리스틱), `parse_mask_option` 이 `--mask NAME=REGEX` 해석 |
| `sanitizer.py` | `active_rules(policy)` = 내장(끈 것 제외) + 사용자 규칙. `mask_secrets(text, rules, timeout)` 는 사용자 규칙만 `SIGALRM` 기반 제한 시간 안에서 실행하고 넘으면 `MaskTimeoutError` (CPython 의 `re` 는 역추적 중에도 시그널을 확인하므로 끊을 수 있음을 실측으로 확인). `sanitize(diff, safe_mode, policy)` |
| `prompts.py` | `--context`·브랜치·파일 목록 마스킹도 같은 `active_rules` 사용 (diff 와 규칙 불일치 방지) |
| `commands.py` | 설정 파일 정책 위에 CLI 옵션 병합, 정책 로그, 약화 경고(끈 규칙 이름, 기본값보다 큰 상한을 출처와 함께) |
| `cli.py` | 네 옵션 추가. 숫자 범위를 설정 파일과 같은 `LIMIT_RANGES` 로 검사, `--mask` 는 파싱 시점에 검증 |

설계 메모: 설정 파일로는 보호를 **더하는 방향**(제외 패턴 추가, 규칙 추가)은 자유롭지만, **빼는 방향**(규칙 끄기, 상한 올리기)은 오탐이 잦은 3개 규칙만 허용하고 매 실행 `[WARN]` 으로 출처를 알립니다. 내장 제외 패턴은 뺄 수 없습니다.

## 4. safe-mode ON/OFF 비교

데모 저장소에 12개 파일을 변경했습니다: `.env`(비밀번호·Slack 토큰), `data/customers.csv`(이메일·휴대전화·사번 `EMP-`), `docs/notes.md`(사번·주문번호·이메일), `app/big_module.py`(300줄), `app/mod_0..7.py`(각 1줄, 주석에 사번). `--context "EMP-123456 요청 반영"` 을 함께 주고 `commit --dry-run` 으로 프롬프트만 출력했습니다(API 호출 없음).

| | OFF | ON (기본값) | ON (2.1 설정 파일) | ON (CLI: `--max-files 3 --max-lines 20 --exclude "*.md" --mask INTERNAL_ID=EMP-[0-9]{6}`) |
| --- | --- | --- | --- | --- |
| 정책 로그 | 없음 | 파일 10 · 200줄 · 제외 10 · 규칙 9 | 파일 8 · 100줄 · 제외 12 · 규칙 12 | 파일 3 · 20줄 · 제외 11 · 규칙 10 |
| `<diff>` 줄 수 | 389 | 270 | 154 | 39 |
| 생략된 파일 | 0 | 2 (`.env`, `docs/notes.md`†) | 5 (`.env`, `app/mod_7.py`, `data/customers.csv`, `docs/notes.md`, `.ai-gitgen.json`) | 10 |
| 마스킹 건수 | 0 | 4 (`EMAIL` 2, `PHONE_KR` 2) | 7 (`INTERNAL_ID` 7) | 2 (`INTERNAL_ID` 2) |
| 사번 `EMP-` 노출 | 13 | 12 (CSV 2 + 주석 8 + context 1 …) | **0** (context 도 `[MASKED:INTERNAL_ID]`) | 0 |
| 이메일 노출 | 3 | 0 | 0 | 0 |
| 길이 절단 | 0 | 106줄 (`big_module.py` 300→200) | 206줄 (→100) | 286줄 (→20) |

† 기본 정책에서 `docs/notes.md` 가 빠진 이유는 민감해서가 아니라 11번째 파일이어서입니다(10개 상한). 내부 식별자 같은 **조직 고유 패턴은 내장 규칙이 모르므로** 기본 safe-mode 로는 12건이 그대로 나갔고, 설정 파일의 규칙 한 줄로 0건이 되었습니다. 이것이 보너스 3 의 핵심 효과입니다.

OFF 와 ON(설정 파일)의 `<context>` 블록:

```text
# OFF
변경 이유(작성자 제공): EMP-123456 요청 반영
# ON (설정 파일)
변경 이유(작성자 제공): [MASKED:INTERNAL_ID] 요청 반영
일부 민감정보는 [MASKED:...] 로 가려져 있고, 5개 파일은 이름만 제공됩니다.
diff 중 206줄은 길이 제한으로 생략되었습니다.
```

잘못된 규칙은 즉시 거부됩니다:

```text
$ python -m ai_gitgen commit --safe-mode --mask "X=("
[ERROR] --mask 'X=(': 마스킹 규칙 이름은 대문자·숫자·밑줄 2~31자여야 합니다 (입력: 'X')
```

## 5. 보안 리뷰 반영

| 심각도 | 지적 | 반영 |
| --- | --- | --- |
| HIGH | 저장소가 준 정규식이 역추적 폭발로 도구를 멈출 수 있음 (`(a+)+$` 에 28자 입력으로 4초, 글자마다 2배) | 중첩 반복·역참조 패턴을 컴파일 단계에서 거부 + 사용자 규칙 실행에 `SIGALRM` 2초 제한. 넘으면 규칙 이름을 담은 오류로 중단(조용히 건너뛰지 않음). 시그널이 없는 환경(Windows)은 휴리스틱만 적용됨을 문서화 |
| HIGH | `disabled_rules` 로 내장 마스킹을 조용히 끌 수 있음 | 자격 증명 규칙 6개는 끌 수 없음. 끈 규칙은 매 실행 `[WARN] safe-mode: 내장 마스킹 규칙 비활성 — EMAIL (출처: 경로)` |
| MEDIUM | 상한을 조용히 올릴 수 있음 (`global_max_lines` 20,000 까지) | 기본값보다 큰 상한은 매 실행 `[WARN]` 으로 값·기본값·출처 표시 |
| MEDIUM | 빈 문자열에 매치되는 패턴(`x*`)이 모든 글자 사이에 마커를 넣음 | `pattern.search("")` 가 매치되면 거부. 치환 결과 `[MASKED:X]` 에 매치되는 패턴도 거부 |
| MEDIUM | CLI 상한이 설정 파일과 다른 범위 검사(0 만 거부) | `LIMIT_RANGES` 를 공유해 1~200, 10~5000 으로 통일 |
| MEDIUM | 설정 파일 크기 제한 없음 | 1MB 초과 거부 |
| LOW | 사용자 규칙이 `[MASKED:...]` 안쪽에 매치될 수 있음 | 위 치환 결과 매치 거부로 해결. 그 밖의 LOW(글로브는 파일시스템을 건드리지 않음, 치환 문자열 주입 불가, 비밀값 로그 없음)는 확인만 |

## 6. 한계

- **정규식은 형태가 알려진 값만 잡습니다.** 임의 문자열 비밀번호는 `GENERIC_SECRET`(키 이름 기반)이 아니면 통과합니다. 비밀값을 커밋에 넣지 않는 것이 원칙이고 safe-mode 는 보조 수단입니다.
- **실행 시간 제한은 Unix 주 스레드에서만** 동작합니다. 그 밖의 환경에서는 컴파일 단계 휴리스틱만 적용됩니다.
- **설정 파일은 저장소 소유자가 통제합니다.** 남의 저장소에서 `--safe-mode` 를 쓸 때는 `[INFO] 컨벤션 적용:` 과 `[WARN]` 줄을 확인하거나 `--no-convention` 으로 파일을 무시하세요. CLI 옵션은 사용자가 직접 입력하므로 신뢰합니다.
- 전송 내용은 언제든 `--dry-run` 으로 미리 볼 수 있습니다.
