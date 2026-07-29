#!/usr/bin/env bash
# TASK-E 후속: 공식 레포 구조에 맞게 개량한 시스템 프롬프트(wan_style_cn/promptenhancer_cn)로
# 리라이팅한 24프롬프트를 flux2-klein-4b-nf4로 생성한다. v251(wan_style)/v252(promptenhancer)를
# 대체하는 새 baseline 후보 — scripts/rewrite.py가 이미 만들어둔
# image-prompts/rewrite/{wan_style_cn,promptenhancer_cn}.json을 그대로 흘려보낸다
# (scripts/lecture_generate.py --prompts-json). 172.10.5.157(생성 전용 서버)에서 실행.
#
#     bash scripts/sweeps/rewrite_generate_flux2klein_cn.sh
set -euo pipefail

for conda_sh in "$HOME/miniconda3/etc/profile.d/conda.sh" "$HOME/anaconda3/etc/profile.d/conda.sh"; do
  if [ -f "$conda_sh" ]; then
    # shellcheck disable=SC1090
    source "$conda_sh"
    break
  fi
done

MODEL=flux2-klein-4b-nf4
BACKENDS=(wan_style_cn promptenhancer_cn)

TASK="rewrite_generate_flux2klein_cn.sh"
LOG_DIR="logs/$(date +%Y%m%d_%H%M%S)_rewrite_generate_flux2klein_cn"
mkdir -p "$LOG_DIR"

env=$(grep -E '^env:' "configs/models/${MODEL}.yaml" | awk '{print $2}')

VDIRS=()
fail=0
for backend in "${BACKENDS[@]}"; do
  prompts_json="image-prompts/rewrite/${backend}.json"
  if [ ! -f "$prompts_json" ]; then
    echo "!!! $prompts_json 없음, 건너뜀"
    fail=1
    continue
  fi

  log="$LOG_DIR/${backend}.log"
  echo "=== $MODEL / $backend -> $log"
  if conda run -n "$env" python -m scripts.lecture_generate \
      --model "$MODEL" --prompts-json "$prompts_json" > "$log" 2>&1; then
    vdir=$(grep -o 'image-prompts/v[0-9_a-zA-Z-]*' "$log" | head -1)
    tail=$(grep -o 'vram_peak=[0-9.]*GB  sec/img=[0-9.]*' "$log" | tail -1)
    echo "    OK -> $vdir ($tail)"
    VDIRS+=("$vdir")
    python3 "$(dirname "$0")/../alert.py" --task "$TASK" --status ok \
      --message "SUCCESS: ${MODEL}/rewrite-${backend} -> ${vdir} (${tail})"
  else
    echo "    FAIL — 로그: $log"
    python3 "$(dirname "$0")/../alert.py" --task "$TASK" --status fail \
      --message "FAIL: ${MODEL}/rewrite-${backend} ($(tail -3 "$log" | tr '\n' ' ' | cut -c1-200))"
    fail=1
  fi
done

echo
echo "생성 로그: $LOG_DIR/"
echo "생성 버전: ${VDIRS[*]}"
python3 "$(dirname "$0")/../alert.py" --task "$TASK" --status ok \
  --message "TASK-E 리라이팅 개량 시스템 프롬프트 2조건(wan_style_cn/promptenhancer_cn) 생성 완료 — 로그: $LOG_DIR, 버전: ${VDIRS[*]}"

exit "$fail"
