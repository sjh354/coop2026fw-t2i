#!/usr/bin/env bash
# 수업용 실험: configs/benchmarks/vlm-prompts.json의 24개 완성 프롬프트를
# 후보 모델 2개(pixart-sigma, flux2-klein-4b-nf4) 각각에 생성만 실행.
# (scripts/lecture_generate.py 참고 — 채점은 이 스크립트 범위 밖, 별도 진행)
#
#     bash scripts/lecture_generate.sh
set -euo pipefail

MODELS=(pixart-sigma flux2-klein-4b-nf4)

TASK="lecture_generate.sh"
LOG_DIR="logs/$(date +%Y%m%d_%H%M%S)_lecture_generate"
mkdir -p "$LOG_DIR"

if [ ! -f "configs/benchmarks/vlm-prompts.json" ]; then
  echo "!!! configs/benchmarks/vlm-prompts.json 없음."
  exit 1
fi

VDIRS=()
for model in "${MODELS[@]}"; do
  env=$(grep -E '^env:' "configs/models/${model}.yaml" | awk '{print $2}')
  log="$LOG_DIR/${model}.log"
  echo "=== $model -> $log"
  if conda run -n "$env" python -m scripts.lecture_generate --model "$model" > "$log" 2>&1; then
    vdir=$(grep -o 'image-prompts/v[0-9_a-zA-Z-]*' "$log" | head -1)
    tail=$(grep -o 'vram_peak=[0-9.]*GB  sec/img=[0-9.]*' "$log" | tail -1)
    echo "    OK -> $vdir ($tail)"
    VDIRS+=("$vdir")
    python3 "$(dirname "$0")/alert.py" --task "$TASK" --status ok \
      --message "SUCCESS: ${model}/lecture24 -> ${vdir} (${tail})"
  else
    echo "    FAIL — 로그: $log"
    python3 "$(dirname "$0")/alert.py" --task "$TASK" --status fail \
      --message "FAIL: ${model}/lecture24 ($(tail -3 "$log" | tr '\n' ' ' | cut -c1-200))"
  fi
done

echo
echo "생성 로그: $LOG_DIR/"
echo "생성 버전: ${VDIRS[*]}"
python3 "$(dirname "$0")/alert.py" --task "$TASK" --status ok \
  --message "수업용 24개 생성 완료 — 로그: $LOG_DIR, 버전: ${VDIRS[*]}"
