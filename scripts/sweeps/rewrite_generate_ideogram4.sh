#!/usr/bin/env bash
# TASK-G: 리라이팅 4조건(passthrough/wan_style/promptenhancer/guide) x 24프롬프트를
# ideogram-4로 실제 생성한다. passthrough/wan_style/promptenhancer는 TASK-E에서 이미 만든
# image-prompts/rewrite/*.json(모델 비의존적 텍스트 리라이팅 결과)을 재사용하고, guide는
# TASK-G에서 손으로 작성한 공식 스키마 캡션(image-prompts/rewrite/ideogram_guide.json)이다.
# scripts/lecture_generate.py --prompts-json으로 그대로 흘려보낸다. 172.10.5.157(생성 전용
# 서버)에서 실행. 2026-07-28 기준 ideogram-4는 이 24프롬프트 세트로 생성된 적이 없다
# (v105~v198은 전부 coloring-book/flat-illust/diagram-* 등 다른 실험).
#
# 4조건 x 24장 x 48-step ≈ 165초/장 기준 약 4.4시간 소요.
#
#     bash scripts/sweeps/rewrite_generate_ideogram4.sh
set -euo pipefail

for conda_sh in "$HOME/miniconda3/etc/profile.d/conda.sh" "$HOME/anaconda3/etc/profile.d/conda.sh"; do
  if [ -f "$conda_sh" ]; then
    # shellcheck disable=SC1090
    source "$conda_sh"
    break
  fi
done

MODEL=ideogram-4
BACKENDS=(passthrough wan_style promptenhancer ideogram_guide)

TASK="rewrite_generate_ideogram4.sh"
LOG_DIR="logs/$(date +%Y%m%d_%H%M%S)_rewrite_generate_ideogram4"
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
  --message "TASK-G 리라이팅 4조건(ideogram-4) 생성 완료 — 로그: $LOG_DIR, 버전: ${VDIRS[*]}"

exit "$fail"
