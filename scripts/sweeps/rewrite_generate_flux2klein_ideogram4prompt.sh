#!/usr/bin/env bash
# v264에서 ideogram-4로 생성했던, Ideogram-4-v1 magic-prompt가 리라이팅한 24프롬프트
# (image-prompts/rewrite/ideogram_magicprompt.json)를 flux2-klein-4b-nf4에도 그대로
# 흘려 생성해본다 (scripts/lecture_generate.py --prompts-json). 172.10.5.157에서 실행.
#
#     bash scripts/sweeps/rewrite_generate_flux2klein_ideogram4prompt.sh
set -euo pipefail

for conda_sh in "$HOME/miniconda3/etc/profile.d/conda.sh" "$HOME/anaconda3/etc/profile.d/conda.sh"; do
  if [ -f "$conda_sh" ]; then
    # shellcheck disable=SC1090
    source "$conda_sh"
    break
  fi
done

MODEL=flux2-klein-4b-nf4
PROMPTS_JSON=image-prompts/rewrite/ideogram_magicprompt.json

TASK="rewrite_generate_flux2klein_ideogram4prompt.sh"
LOG_DIR="logs/$(date +%Y%m%d_%H%M%S)_rewrite_generate_flux2klein_ideogram4prompt"
mkdir -p "$LOG_DIR"

env=$(grep -E '^env:' "configs/models/${MODEL}.yaml" | awk '{print $2}')

log="$LOG_DIR/run.log"
echo "=== $MODEL / ideogram_magicprompt -> $log"
if conda run -n "$env" python -m scripts.lecture_generate \
    --model "$MODEL" --prompts-json "$PROMPTS_JSON" > "$log" 2>&1; then
  vdir=$(grep -o 'image-prompts/v[0-9_a-zA-Z-]*' "$log" | head -1)
  tail=$(grep -o 'vram_peak=[0-9.]*GB  sec/img=[0-9.]*' "$log" | tail -1)
  echo "    OK -> $vdir ($tail)"
  python3 "$(dirname "$0")/../alert.py" --task "$TASK" --status ok \
    --message "SUCCESS: ${MODEL}/ideogram_magicprompt -> ${vdir} (${tail})"
  exit 0
else
  echo "    FAIL — 로그: $log"
  python3 "$(dirname "$0")/../alert.py" --task "$TASK" --status fail \
    --message "FAIL: ${MODEL}/ideogram_magicprompt ($(tail -3 "$log" | tr '\n' ' ' | cut -c1-200))"
  exit 1
fi
