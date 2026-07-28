#!/usr/bin/env bash
# TASK-F 2~4번(bench/results.md "다음 단계" 참고): qwen-image(full) vs
# qwen-image-lightning을 서버 157에서 순차 실행.
#
#   b) scripts/bench_cost.py로 정식 VRAM/latency 측정 (basic30.yaml, TASK-D와 동일 조건)
#   c) scripts/lecture_generate.py로 동일 시드(0)·24프롬프트 전체 생성
#      (spec+CSD 채점은 서버 23에서 별도 진행 — 이 스크립트 범위 밖)
#   d) scripts/build_taskf_report.py로 quality/latency/VRAM 비교표 작성
#      (이 시점엔 quality가 아직 없으니 "채점 대기(서버 23)"로 표시된 초안만 나온다 —
#       서버 23 채점 완료 후 --score-dir-full/--score-dir-lightning으로 재실행해서 채울 것)
#
#     bash scripts/sweeps/task_f_qwen_pipeline.sh
set -u

ENV=t2i-qwen
TASK="task_f_qwen_pipeline.sh"
MODELS=(qwen-image qwen-image-lightning)
COST_PROMPTS=configs/keywords/basic30.yaml
COST_CSV=bench/cost/vram_latency.csv
REPORT_OUT=reports/task-f_qwen_lightning_comparison.md
LOG_DIR="logs/$(date +%Y%m%d_%H%M%S)_task_f_qwen_pipeline"
mkdir -p "$LOG_DIR"

fail=0

echo "=== b) bench_cost.py: VRAM/latency ==="
for model in "${MODELS[@]}"; do
  log="$LOG_DIR/bench_cost_${model}.log"
  echo "--- $model -> $log"
  if conda run -n "$ENV" python -m scripts.bench_cost \
      --config "configs/models/${model}.yaml" \
      --prompts "$COST_PROMPTS" \
      --out "$COST_CSV" \
      --seed 42 > "$log" 2>&1; then
    echo "    OK"
    python "$(dirname "$0")/../alert.py" --task "$TASK" --status ok \
      --message "bench_cost/${model}: $(tail -3 "$log" | tr '\n' ' ' | cut -c1-500)"
  else
    echo "    FAIL — 로그: $log"
    fail=1
    python "$(dirname "$0")/../alert.py" --task "$TASK" --status fail \
      --message "bench_cost/${model} 실패: $(tail -5 "$log" | tr '\n' ' ' | cut -c1-300)"
  fi
done

echo
echo "=== c) lecture_generate.py: 동일 시드·24프롬프트 생성 ==="
VDIRS=()
for model in "${MODELS[@]}"; do
  log="$LOG_DIR/lecture_generate_${model}.log"
  echo "--- $model -> $log"
  if conda run -n "$ENV" python -m scripts.lecture_generate --model "$model" > "$log" 2>&1; then
    vdir=$(grep -o 'image-prompts/v[0-9_a-zA-Z-]*' "$log" | head -1)
    tail=$(grep -o 'vram_peak=[0-9.]*GB  sec/img=[0-9.]*' "$log" | tail -1)
    echo "    OK -> $vdir ($tail)"
    VDIRS+=("$vdir")
    python "$(dirname "$0")/../alert.py" --task "$TASK" --status ok \
      --message "lecture_generate/${model} -> ${vdir} (${tail})"
  else
    echo "    FAIL — 로그: $log"
    fail=1
    python "$(dirname "$0")/../alert.py" --task "$TASK" --status fail \
      --message "lecture_generate/${model} 실패: $(tail -5 "$log" | tr '\n' ' ' | cut -c1-300)"
  fi
done

echo
echo "=== d) build_taskf_report.py: 비교표 초안 (quality는 서버 23 채점 후 채울 것) ==="
if conda run -n "$ENV" python -m scripts.build_taskf_report \
    --cost-csv "$COST_CSV" \
    --out "$REPORT_OUT" > "$LOG_DIR/build_report.log" 2>&1; then
  echo "    OK -> $REPORT_OUT"
else
  echo "    FAIL — 로그: $LOG_DIR/build_report.log"
  fail=1
fi

echo
echo "로그: $LOG_DIR/"
echo "생성 버전: ${VDIRS[*]:-}"
echo "비교표: $REPORT_OUT"

if [ "$fail" -eq 0 ]; then
  python "$(dirname "$0")/../alert.py" --task "$TASK" --status ok \
    --message "b/c/d 완료 — 생성 버전: ${VDIRS[*]:-}, 비교표(quality 대기): ${REPORT_OUT}"
else
  python "$(dirname "$0")/../alert.py" --task "$TASK" --status fail \
    --message "일부 단계 실패 — 로그: $LOG_DIR/"
fi
