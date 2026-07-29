#!/usr/bin/env bash
# TASK-I 파트 2: 길이만 분리한 "medium" 조건(image-prompts/rewrite/promptenhancer_cn_medium.json,
# structural 카테고리 4개 x 3소스 = 12개)을 flux2-klein-4b-nf4로 생성한다. short(v250 passthrough)와
# long(v262 promptenhancer_cn) 사이의 중간 지점 — model/steps/guidance/seed는 v250/v262와 동일.
# 172.10.5.157(생성 전용 서버)에서 실행.
#
#     bash scripts/sweeps/rewrite_generate_length_ladder.sh
set -euo pipefail

for conda_sh in "$HOME/miniconda3/etc/profile.d/conda.sh" "$HOME/anaconda3/etc/profile.d/conda.sh"; do
  if [ -f "$conda_sh" ]; then
    # shellcheck disable=SC1090
    source "$conda_sh"
    break
  fi
done

MODEL=flux2-klein-4b-nf4
PROMPTS_JSON=image-prompts/rewrite/promptenhancer_cn_medium.json

TASK="rewrite_generate_length_ladder.sh"
LOG_DIR="logs/$(date +%Y%m%d_%H%M%S)_rewrite_generate_length_ladder"
mkdir -p "$LOG_DIR"

env=$(grep -E '^env:' "configs/models/${MODEL}.yaml" | awk '{print $2}')

log="$LOG_DIR/promptenhancer_cn_medium.log"
echo "=== $MODEL / promptenhancer_cn_medium -> $log"
if conda run -n "$env" python -m scripts.lecture_generate \
    --model "$MODEL" --prompts-json "$PROMPTS_JSON" > "$log" 2>&1; then
  vdir=$(grep -o 'image-prompts/v[0-9_a-zA-Z-]*' "$log" | head -1)
  tail=$(grep -o 'vram_peak=[0-9.]*GB  sec/img=[0-9.]*' "$log" | tail -1)
  echo "    OK -> $vdir ($tail)"
  python3 "$(dirname "$0")/../alert.py" --task "$TASK" --status ok \
    --message "SUCCESS: ${MODEL}/rewrite-promptenhancer_cn_medium -> ${vdir} (${tail})"
else
  echo "    FAIL — 로그: $log"
  python3 "$(dirname "$0")/../alert.py" --task "$TASK" --status fail \
    --message "FAIL: ${MODEL}/rewrite-promptenhancer_cn_medium ($(tail -3 "$log" | tr '\n' ' ' | cut -c1-200))"
  exit 1
fi

echo
echo "생성 로그: $LOG_DIR/"
echo "생성 버전: $vdir"
