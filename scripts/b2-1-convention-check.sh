#!/usr/bin/env bash
# B2-1 저장소에서 .ai-gitgen.json 컨벤션이 자동 적용되는지 재현한다.
#
# 사용법:
#   scripts/b2-1-convention-check.sh [B2-1 경로 또는 URL] [작업 디렉터리]
#   기본값: git@github.com:newids/codyssey-b2-1.git, /tmp/b21-convention-check
#   환경변수 DRY_RUN_ONLY=1 이면 API 를 호출하지 않는다 (키 불필요).
#
# 하는 일:
#   1. B2-1 을 임시 디렉터리에 클론한다 (실제 저장소는 건드리지 않는다).
#   2. PR #1 이전 커밋(4e293a6)에 브랜치를 만들고 .ai-gitgen.json(46a991c)만 커밋한다.
#   3. PR #1 의 변경(4e293a6..f0b1357)을 스테이징 상태로 올린다.
#      -> "컨벤션 파일은 추적 중이고 diff 에는 없음 + PR 변경 6개 파일 143줄 스테이징" 상태가 된다.
#   4. commit --dry-run 으로 [팀 컨벤션] 블록을 확인하고, 실제 호출로 컨벤션 적용/미적용 출력을 비교한다.
set -euo pipefail

SOURCE="${1:-git@github.com:newids/codyssey-b2-1.git}"
WORK="${2:-/tmp/b21-convention-check}"
TOOL_ROOT="$(cd "$(dirname "$0")/.." && pwd)"   # 이 저장소(codyssey-b3-2) 루트

BEFORE_PR="4e293a6"      # PR #1 이전 커밋 (budget_app 최초 구현)
PR_HEAD="f0b1357"        # PR #1 의 커밋
CONVENTION_COMMIT="46a991c"  # .ai-gitgen.json 을 추가한 커밋

OUT="$WORK-out"   # 출력은 클론 밖에 둔다. 클론 안에 쓰면 새 파일로 수집되어 diff 가 오염된다

if [ -e "$WORK" ] || [ -e "$OUT" ]; then
  echo "작업 디렉터리가 이미 있습니다: $WORK 또는 $OUT (지우고 다시 실행하세요)" >&2
  exit 2
fi
mkdir -p "$OUT"

echo "== 1. 클론: $SOURCE -> $WORK"
git clone -q "$SOURCE" "$WORK"
cd "$WORK"

echo "== 2. PR 이전 커밋에 컨벤션 파일만 커밋"
git checkout -q -b convention-check "$BEFORE_PR"
git checkout "$CONVENTION_COMMIT" -- .ai-gitgen.json
git -c user.name=check -c user.email=check@example.com commit -q -m "chore: 컨벤션 파일 (재현용, 푸시하지 않음)"

echo "== 3. PR #1 변경을 스테이징으로 올림"
git diff "$BEFORE_PR" "$PR_HEAD" | git apply --index
git status --short

export PYTHONPATH="$TOOL_ROOT"
echo
echo "== 4-a. dry-run: 프롬프트의 [팀 컨벤션] 블록 (API 호출 없음)"
python3 -m ai_gitgen commit --safe-mode --dry-run > "$OUT/dry.out" 2> "$OUT/dry.err"
grep "컨벤션 적용" "$OUT/dry.err"
grep -A5 "\[팀 컨벤션\]" "$OUT/dry.out"

if [ "${DRY_RUN_ONLY:-0}" = "1" ]; then
  echo
  echo "DRY_RUN_ONLY=1: 실제 호출은 생략했습니다."
  exit 0
fi

echo
echo "== 4-b. 실제 호출: 컨벤션 적용 (루트의 .ai-gitgen.json 자동 사용)"
python3 -m ai_gitgen commit --safe-mode | tee "$OUT/with-convention.out"

echo
echo "== 4-c. 실제 호출: --no-convention (비교용, 기본 컨벤션)"
python3 -m ai_gitgen commit --safe-mode --no-convention | tee "$OUT/without-convention.out"

echo
echo "== 5. 제목 비교 (결과 블록의 첫 줄)"
printf '적용   : %s\n' "$(grep -A1 -- '--- Commit Message ---' "$OUT/with-convention.out" | tail -1)"
printf '미적용 : %s\n' "$(grep -A1 -- '--- Commit Message ---' "$OUT/without-convention.out" | tail -1)"
echo "결과 파일: $OUT/"
