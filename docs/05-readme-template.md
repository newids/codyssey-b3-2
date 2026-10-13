# README 템플릿 — 도구 저장소용

이 파일을 도구 저장소의 `README.md` 로 복사하고 `{...}` 와 "예시" 블록을 **실제 실행 결과**로 바꿉니다.
과제 "4-6. 리포지토리 및 문서화"의 필수 항목이 어디에 있는지 마지막 점검표로 확인합니다.

---

````markdown
# ai-gitgen — git 변경 사항으로 커밋 메시지와 PR 초안 생성

`git status`, `git diff` 결과를 AI API에 보내 커밋 메시지와 Pull Request 초안을 터미널에 출력하는 CLI 도구입니다.
생성 결과는 **초안**이며, 검토 후 직접 적용합니다. 이 도구는 `git commit`, `git push`, PR 생성을 실행하지 않습니다.

## 1. 설치

요구 사항: Python 3.10 이상, git.

```bash
git clone https://github.com/{user}/{repo}.git
cd {repo}
python3 --version   # 3.10 이상 확인
```

외부 패키지 없이 표준 라이브러리만 사용하므로 `pip install` 이 필요 없습니다.

## 2. 환경변수 설정

API 키는 환경변수로만 읽습니다. 코드에 키를 넣지 마세요.

```bash
export AI_API_KEY="YOUR_KEY"          # macOS / Linux
setx AI_API_KEY "YOUR_KEY"            # Windows (새 터미널에서 적용)
```

`AI_API_KEY` 가 없으면 `ANTHROPIC_API_KEY` 를 대신 읽습니다. 둘 다 없으면 다음 메시지와 함께 종료 코드 1 로 끝납니다.

```text
[ERROR] AI_API_KEY 환경변수가 설정되지 않았습니다.
예) export AI_API_KEY="YOUR_KEY"
```

## 3. 사용법

Git 저장소 루트에서 실행합니다.

```bash
python -m ai_gitgen commit                 # 커밋 메시지 생성
python -m ai_gitgen pr                     # PR 제목/본문 생성
python -m ai_gitgen commit --safe-mode     # 민감정보 마스킹 + 전송량 제한
python -m ai_gitgen pr --context "로그인 재시도 버그 수정"   # 변경 이유를 직접 제공
python -m ai_gitgen commit --dry-run       # API 호출 없이 프롬프트만 확인
```

### 옵션

| 옵션 | 기본값 | 설명 |
| --- | --- | --- |
| `--model` | `claude-sonnet-4-6` | 모델 ID |
| `--temperature` | `0.3` | 0.0(결정적) ~ 1.0(다양). 커밋/PR 은 낮은 값 권장 |
| `--max-tokens` | commit `512`, pr `1024` | 출력 토큰 상한. 잘리면 `[WARN]` 출력 |
| `--safe-mode` | 꺼짐 | 5장 참고 |
| `--context` | 없음 | 변경 이유 한 줄. PR 의 Why 품질이 좋아짐 |
| `--dry-run` | 꺼짐 | 프롬프트만 출력, API 호출·비용 없음 |

> 최신 모델(`claude-opus-5-5`, `claude-sonnet-5-5` 등)은 `temperature` 를 받지 않습니다. 도구가 이런 모델을 알고 있으면 `temperature` 를 자동으로 빼고 `[WARN]` 으로 알립니다. 모르는 모델이 400 을 돌려주면 그 모델을 기록하고 `temperature` 없이 한 번 다시 요청합니다. 자세한 내용은 7장.

로그는 표준 오류, 결과는 표준 출력으로 나옵니다. 결과만 파일로 받아 바로 쓸 수 있습니다.

```bash
python -m ai_gitgen commit > /tmp/msg.txt && git commit -F /tmp/msg.txt
python -m ai_gitgen pr > /tmp/pr.md     # 첫 줄은 제목, 그 아래가 본문
```

## 4. 출력 예시

### 커밋 메시지

```text
$ python -m ai_gitgen commit --safe-mode
[INFO] Git status 수집 완료: 3개 파일 변경 감지
[INFO] Git diff 수집 완료: 128줄
[INFO] safe-mode: 2개 항목 마스킹, 0개 파일 생략
[INFO] AI API 요청 중... (model=claude-sonnet-4-6, temperature=0.3, max_tokens=512)
[INFO] AI API 호출 횟수: 1회 / 토큰 사용: 입력 1,842 · 출력 96
[DONE] 커밋 메시지 생성 완료

--- Commit Message ---
feat(sanitizer): GitHub 토큰 마스킹 규칙 추가

- sanitizer.py 에 ghp_/gho_ 접두 토큰 정규식 추가
- formatter.py 가 마스킹 건수를 [INFO] 로그에 출력
----------------------
```

### PR 초안

```text
$ python -m ai_gitgen pr --context "safe-mode 마스킹 범위 확장"
[INFO] 현재 브랜치: feature/mask-github-token
[INFO] Git diff 수집 완료: 128줄
[INFO] AI API 요청 중... (model=claude-sonnet-4-6, temperature=0.3, max_tokens=1024)
[INFO] AI API 호출 횟수: 1회 / 토큰 사용: 입력 1,901 · 출력 243
[DONE] PR 초안 생성 완료

--- PR Title ---
feat: safe-mode 마스킹 규칙에 GitHub 토큰 추가

--- PR Body ---
## Why
- safe-mode 가 AWS/Anthropic 키는 가리지만 GitHub 개인 토큰(ghp_)은 그대로 전송되고 있었습니다.

## What
- sanitizer.py: `gh[pousr]_` 접두 토큰 정규식 추가
- formatter.py: 마스킹 건수를 로그에 출력
- tests/test_sanitizer.py: GitHub 토큰 케이스 추가

## How to Test
- `python -m unittest tests.test_sanitizer`
- 토큰이 포함된 파일을 수정한 뒤 `python -m ai_gitgen commit --safe-mode --dry-run` 으로 `[MASKED:GITHUB_TOKEN]` 확인
----------------
```

### 변경 사항이 없을 때

```text
$ python -m ai_gitgen commit
[INFO] 변경 사항이 없습니다. 커밋 메시지를 생성하지 않고 종료합니다.
```

### API 오류

```text
$ AI_API_KEY=wrong python -m ai_gitgen commit
[ERROR] 인증 실패 (HTTP 401): invalid x-api-key
       AI_API_KEY 값과 환경변수 이름을 확인하세요.
```

## 5. 민감정보 대응 (safe-mode)

`git diff` 에는 API 키, 개인정보가 섞일 수 있습니다. `--safe-mode` 는 세 가지를 적용합니다.

| 층 | 정책 |
| --- | --- |
| 제외 | `.env*`, `*.pem`, `*.key`, `*.p12`, `*.lock`, `package-lock.json`, `yarn.lock`, `pnpm-lock.yaml`, `*.min.js` 는 보내지 않고 파일 이름만 전달 |
| 마스킹 | 프라이빗 키 블록, `sk-ant-`/`sk-`/`AKIA`/`ghp_` 접두 키, JWT, `api_key = "..."` 형태 값, 이메일, 휴대전화 번호 → `[MASKED:종류]` |
| 제한 | 최대 10개 파일, 파일당 최대 200줄. 넘는 부분은 `... (N줄 생략)` |

safe-mode 가 꺼져 있어도 전체 2,000줄 상한은 항상 적용됩니다.

**한계.** 정규식은 형태가 알려진 값만 잡습니다. 임의 문자열 비밀번호는 통과할 수 있습니다. 비밀값은 커밋에 넣지 않는 것이 원칙이고, safe-mode 는 보조 수단입니다. 전송 내용은 `--dry-run` 으로 미리 확인할 수 있습니다.

## 6. 비용과 요청 횟수

| 항목 | 값 |
| --- | --- |
| 1회 실행 API 호출 | 기본 1회. 출력이 양식 검증에 실패하면 1회 재생성 (최대 2회). 횟수는 `[INFO]` 로 출력 |
| 1회 비용 (대략) | 입력 2,000토큰 + 출력 200토큰, Sonnet 4.6 기준 약 0.01달러 |
| 저렴한 실험 | `--model claude-haiku-4-5` |
| 권장 | 큰 변경은 커밋을 나누고, 테스트는 `--dry-run` 으로, 토큰 사용량 로그를 확인 |

## 7. 모델 호환성 관리 (`temperature` 미지원 모델)

`temperature` 를 거부하는 모델은 두 층으로 관리합니다.

| 층 | 내용 | 위치 |
| --- | --- | --- |
| 내장 목록 | 문서로 확인된 모델: `claude-opus-5-5`, `claude-opus-5`, `claude-opus-4-8`, `claude-opus-4-7`, `claude-sonnet-5-5`, `claude-sonnet-5`, `claude-haiku-5-5`, `claude-fable-5-1`, `claude-fable-5` | 코드 상수 |
| 학습 목록 | 실행 중 400 응답에 `temperature` 가 언급된 모델. 사유·최초/최근 시각·횟수 기록 | `~/.ai-gitgen/model_registry.json` (`AI_GITGEN_HOME` 으로 변경 가능) |

동작:

```text
$ python -m ai_gitgen commit --model claude-opus-5-5 --temperature 0.3
[WARN] 'claude-opus-5-5' 는 temperature 를 지원하지 않아 생략합니다 (출처: 내장 목록)
[INFO] AI API 요청 중... (model=claude-opus-5-5, temperature=없음, max_tokens=512)

$ python -m ai_gitgen commit --model some-new-model --temperature 0.3
[INFO] AI API 요청 중... (model=some-new-model, temperature=0.3, max_tokens=512)
[WARN] temperature 미지원 모델로 기록했습니다. temperature 없이 다시 요청합니다
[INFO] AI API 호출 횟수: 2회 / ...
```

관리 명령:

```bash
python -m ai_gitgen models list                       # 내장·학습·제외 목록을 출처와 함께 출력
python -m ai_gitgen models add some-model --reason "사전 등록"
python -m ai_gitgen models remove claude-sonnet-5-5   # 내장 모델이면 제외 목록에 넣어 다시 temperature 를 보냄
python -m ai_gitgen models reset                      # 학습·제외 목록 초기화
```

`models list` 출력 예:

```text
모델                   출처          사유                                      최근         횟수
claude-opus-5-5        내장 목록     -                                         -            -
some-new-model         학습          temperature is not supported for this...  2026-10-13   1
claude-sonnet-5-5      제외(내장)    사용자가 remove                           -            -
```

레지스트리 파일은 사용자별 데이터이므로 저장소에 커밋하지 않습니다. 파일이 손상되면 `[ERROR]` 로 알리며, `models reset` 으로 복구할 수 있습니다.

## 8. 출력 검증 규칙

| 대상 | 규칙 | 위반 시 |
| --- | --- | --- |
| 커밋 제목 | 50자 권장, 72자 최대, 끝 마침표 없음 | 단어 경계 절단, 마침표 제거 (후처리) |
| PR 제목 | 80자 최대 | 절단 (후처리) |
| PR 본문 | `## Why`, `## What`, `## How to Test` 헤더 + 각 1개 이상 불릿 | 1회 재생성 → 그래도 실패면 `- (작성 필요)` 로 채우고 `[WARN]` |

## 9. 프로젝트 구조

```text
ai_gitgen/
  cli.py            옵션 해석, 명령 분기
  config.py         기본값, 환경변수
  git_collector.py  git status/diff 수집
  sanitizer.py      safe-mode 마스킹·제한
  prompts.py        프롬프트 템플릿
  model_registry.py temperature 미지원 모델 목록(내장+학습)
  ai_client.py      REST 호출, 오류 변환
  validators.py     규칙 검증, 후처리
  formatter.py      로그, 구분선 출력
  errors.py         예외 클래스
tests/
docs/
```

## 10. 테스트

```bash
python -m unittest discover -s tests -v
```

API 키 없이 실행됩니다. 실제 API 호출 테스트는 `AI_API_KEY` 가 설정된 경우에만 실행됩니다.

## 11. 설계 결정

- 옵션 표기는 과제 문서의 `-model` 대신 argparse 관례인 `--model` 을 사용합니다.
- 표준 라이브러리 `urllib` 로 직접 REST 호출합니다. SDK 로 바꾸려면 `ai_client.py` 만 교체하면 됩니다.
- 생성 결과는 초안이며 도구가 git 에 직접 쓰지 않습니다.
````

---

## 점검표 (과제 4-6)

| 필수 항목 | 템플릿 위치 |
| --- | --- |
| 설치 및 실행 방법 | 1장, 3장 |
| 환경변수(API Key) 설정 방법 | 2장 |
| 커밋/PR 생성 명령 사용 예시 | 3장 |
| 출력 예시(커밋 메시지 / PR 본문) | 4장 |
| 민감정보 포함 가능성과 대응 | 5장 |
| 비용/요청 횟수 제한 및 권장 사용법 | 6장 |

추가로 보너스를 했다면 "12. 컨벤션 설정", "13. safe-mode 정책 조정" 절을 덧붙이고 전/후 비교 결과를 넣습니다.
