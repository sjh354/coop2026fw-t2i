#!/usr/bin/env bash
# STAGE 3(TASK-B2) 자동(VLM) 채점 + kappa 계산.
# v246(pixart-sigma)/v247(flux2-klein-4b-nf4)/v249(qwen-image) 세 모델 디렉토리
# 각각에 대해 judge_spec.py(기본 judge-model Qwen2.5-VL-7B-Instruct, mode=yesno —
# stage3_manual_v2.csv도 probe가 아니라 check 문구로 손 채점했으므로 mode를 맞춘다)를
# 전체 실행하고, 세 결과를 합쳐 judge_agreement.py로 사람 손 채점(stage3_manual_v2.csv)과
# kappa를 계산한다. 172.10.5.23(채점 전용 서버), env는 t2i-judge에서 실행.
#
# 산출물:
#   bench/scores/v246_pixart-sigma-lecture24/judge_spec_qwen.csv
#   bench/scores/v247_flux2-klein-4b-nf4-lecture24/judge_spec_qwen.csv
#   bench/scores/v249_qwen-image-lecture24/judge_spec_qwen.csv
#   bench/scores/stage3_auto_v2.csv (위 세 개를 합친 것)
#   bench/scores/stage3_disagreement_v2.csv (사람 vs VLM 불일치 목록)

set -u

for conda_sh in "$HOME/miniconda3/etc/profile.d/conda.sh" "$HOME/anaconda3/etc/profile.d/conda.sh"; do
  if [ -f "$conda_sh" ]; then
    # shellcheck disable=SC1090
    source "$conda_sh"
    break
  fi
done

ENV=t2i-judge
TASK="stage3_auto_judge.sh"
MANUAL_CSV="bench/scores/stage3_manual_v2.csv"
AUTO_CSV="bench/scores/stage3_auto_v2.csv"
AGREEMENT_OUT="bench/scores/stage3_disagreement_v2.csv"
LOG_DIR="logs/$(date +%Y%m%d_%H%M%S)_stage3_auto_judge"
RUN_DIRS=(
  "v246_pixart-sigma-lecture24"
  "v247_flux2-klein-4b-nf4-lecture24"
  "v249_qwen-image-lecture24"
)

mkdir -p "$LOG_DIR"
ALERT="$(dirname "$0")/../alert.py"

fail=0
auto_parts=()
for run_dir in "${RUN_DIRS[@]}"; do
  images="image-prompts/${run_dir}/images"
  out_csv="bench/scores/${run_dir}/judge_spec_qwen.csv"
  log="$LOG_DIR/judge_spec_${run_dir}.log"

  echo "=== judge_spec.py $run_dir -> $log"
  if conda run -n "$ENV" python -m scripts.judge_spec \
      --images "$images" --out "$out_csv" > "$log" 2>&1; then
    vram=$(grep -o 'vram_peak=[0-9.]*GB' "$log" | tail -1 | sed -n 's/vram_peak=\([0-9.]*\)GB/\1/p')
    n=$(($(wc -l < "$out_csv") - 1))
    echo "    OK  n=${n} vram_peak=${vram:-?}GB"
    conda run -n "$ENV" python "$ALERT" --task "$TASK" --status ok \
      --message "judge_spec $run_dir OK (n=${n}, vram_peak=${vram:-?}GB)"
    auto_parts+=("$out_csv")
  else
    echo "    FAIL — 로그: $log"
    conda run -n "$ENV" python "$ALERT" --task "$TASK" --status fail \
      --message "judge_spec $run_dir 실패: $(tail -5 "$log" | tr '\n' ' ' | cut -c1-300)"
    fail=1
  fi
done

if [ "${#auto_parts[@]}" -eq 0 ]; then
  echo "=== 자동 채점 결과가 하나도 없어 judge_agreement를 건너뜁니다."
  conda run -n "$ENV" python "$ALERT" --task "$TASK" --status fail \
    --message "STAGE 3 자동 채점 전부 실패, judge_agreement 건너뜀"
  exit 1
fi

echo "=== 자동 채점 결과 합치기 -> $AUTO_CSV"
head -1 "${auto_parts[0]}" > "$AUTO_CSV"
for part in "${auto_parts[@]}"; do
  tail -n +2 "$part" >> "$AUTO_CSV"
done

agreement_log="$LOG_DIR/judge_agreement.log"
echo "=== judge_agreement.py (사람 vs VLM) -> $agreement_log"
if conda run -n "$ENV" python -m scripts.judge_agreement \
    --a "$MANUAL_CSV" --b "$AUTO_CSV" --out "$AGREEMENT_OUT" > "$agreement_log" 2>&1; then
  echo "    OK"
  cat "$agreement_log"
  conda run -n "$ENV" python "$ALERT" --task "$TASK" --status ok --log "$agreement_log"
else
  echo "    FAIL — 로그: $agreement_log"
  conda run -n "$ENV" python "$ALERT" --task "$TASK" --status fail \
    --message "judge_agreement 실패: $(tail -5 "$agreement_log" | tr '\n' ' ' | cut -c1-300)"
  fail=1
fi

echo
echo "로그: $LOG_DIR/"
echo "결과: $AUTO_CSV, $AGREEMENT_OUT"
exit "$fail"
