#!/usr/bin/env bash
# TASK-C 확장: 비-Qwen judge(Gemma-3-12B-4bit)를 STAGE 3 규모(v246/v247/v249, 125건)로
# 다시 돌려 자기 계열 선호(self-enhancement bias) 질문에 제대로 힘 실린 답을 얻는다.
# 이전 TASK-C 파일럿(v243 3장, 29건, κ=0.31)은 프롬프트 드리프트로 무효화된 옛 이미지
# 기준이었다. env는 t2i-judge2(torch>=2.6, Gemma-3 체크포인트가 요구) — t2i-judge(Qwen용,
# torch 2.5.1 고정)는 건드리지 않는다. 172.10.5.23(채점 전용 서버)에서 실행.
#
# 산출물:
#   bench/scores/v246_pixart-sigma-lecture24/judge_spec_gemma3.csv
#   bench/scores/v247_flux2-klein-4b-nf4-lecture24/judge_spec_gemma3.csv
#   bench/scores/v249_qwen-image-lecture24/judge_spec_gemma3.csv
#   bench/scores/stage3_auto_gemma3_v2.csv (위 세 개를 합친 것)
#   bench/scores/stage3_disagreement_manual_vs_gemma3_v2.csv (사람 vs Gemma-3 불일치)
#   bench/scores/stage3_disagreement_qwen_vs_gemma3_v2.csv (Qwen vs Gemma-3 불일치,
#     자기 계열 선호 삼각비교용 — 두 judge가 같은 소스에서 갈리는지가 핵심 질문)

set -u

for conda_sh in "$HOME/miniconda3/etc/profile.d/conda.sh" "$HOME/anaconda3/etc/profile.d/conda.sh"; do
  if [ -f "$conda_sh" ]; then
    # shellcheck disable=SC1090
    source "$conda_sh"
    break
  fi
done

ENV=t2i-judge2
TASK="stage3_gemma3_judge.sh"
JUDGE_MODEL="unsloth/gemma-3-12b-it-bnb-4bit"
MANUAL_CSV="bench/scores/stage3_manual_v2.csv"
QWEN_AUTO_CSV="bench/scores/stage3_auto_v2.csv"
GEMMA3_AUTO_CSV="bench/scores/stage3_auto_gemma3_v2.csv"
AGREEMENT_MANUAL_OUT="bench/scores/stage3_disagreement_manual_vs_gemma3_v2.csv"
AGREEMENT_QWEN_OUT="bench/scores/stage3_disagreement_qwen_vs_gemma3_v2.csv"
LOG_DIR="logs/$(date +%Y%m%d_%H%M%S)_stage3_gemma3_judge"
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
  out_csv="bench/scores/${run_dir}/judge_spec_gemma3.csv"
  log="$LOG_DIR/judge_spec_${run_dir}.log"

  echo "=== judge_spec.py --judge-model $JUDGE_MODEL $run_dir -> $log"
  if conda run -n "$ENV" python -m scripts.judge_spec \
      --images "$images" --out "$out_csv" --judge-model "$JUDGE_MODEL" > "$log" 2>&1; then
    vram=$(grep -o 'vram_peak=[0-9.]*GB' "$log" | tail -1 | sed -n 's/vram_peak=\([0-9.]*\)GB/\1/p')
    n=$(($(wc -l < "$out_csv") - 1))
    echo "    OK  n=${n} vram_peak=${vram:-?}GB"
    conda run -n "$ENV" python "$ALERT" --task "$TASK" --status ok \
      --message "gemma3 judge_spec $run_dir OK (n=${n}, vram_peak=${vram:-?}GB)"
    auto_parts+=("$out_csv")
  else
    echo "    FAIL — 로그: $log"
    conda run -n "$ENV" python "$ALERT" --task "$TASK" --status fail \
      --message "gemma3 judge_spec $run_dir 실패: $(tail -5 "$log" | tr '\n' ' ' | cut -c1-300)"
    fail=1
  fi
done

if [ "${#auto_parts[@]}" -eq 0 ]; then
  echo "=== gemma3 채점 결과가 하나도 없어 judge_agreement를 건너뜁니다."
  conda run -n "$ENV" python "$ALERT" --task "$TASK" --status fail \
    --message "gemma3 자동 채점 전부 실패, judge_agreement 건너뜀"
  exit 1
fi

echo "=== gemma3 채점 결과 합치기 -> $GEMMA3_AUTO_CSV"
head -1 "${auto_parts[0]}" > "$GEMMA3_AUTO_CSV"
for part in "${auto_parts[@]}"; do
  tail -n +2 "$part" >> "$GEMMA3_AUTO_CSV"
done

manual_log="$LOG_DIR/judge_agreement_manual.log"
echo "=== judge_agreement.py (사람 vs Gemma-3) -> $manual_log"
if conda run -n "$ENV" python -m scripts.judge_agreement \
    --a "$MANUAL_CSV" --b "$GEMMA3_AUTO_CSV" --out "$AGREEMENT_MANUAL_OUT" > "$manual_log" 2>&1; then
  echo "    OK"
  cat "$manual_log"
  conda run -n "$ENV" python "$ALERT" --task "$TASK" --status ok --log "$manual_log"
else
  echo "    FAIL — 로그: $manual_log"
  conda run -n "$ENV" python "$ALERT" --task "$TASK" --status fail \
    --message "judge_agreement(사람 vs gemma3) 실패: $(tail -5 "$manual_log" | tr '\n' ' ' | cut -c1-300)"
  fail=1
fi

if [ -f "$QWEN_AUTO_CSV" ]; then
  qwen_log="$LOG_DIR/judge_agreement_qwen_vs_gemma3.log"
  echo "=== judge_agreement.py (Qwen2.5-VL vs Gemma-3, 자기 계열 선호 삼각비교) -> $qwen_log"
  if conda run -n "$ENV" python -m scripts.judge_agreement \
      --a "$QWEN_AUTO_CSV" --b "$GEMMA3_AUTO_CSV" --out "$AGREEMENT_QWEN_OUT" > "$qwen_log" 2>&1; then
    echo "    OK"
    cat "$qwen_log"
    conda run -n "$ENV" python "$ALERT" --task "$TASK" --status ok --log "$qwen_log"
  else
    echo "    FAIL — 로그: $qwen_log"
    conda run -n "$ENV" python "$ALERT" --task "$TASK" --status fail \
      --message "judge_agreement(qwen vs gemma3) 실패: $(tail -5 "$qwen_log" | tr '\n' ' ' | cut -c1-300)"
    fail=1
  fi
else
  echo "=== $QWEN_AUTO_CSV 없음 — Qwen vs Gemma3 삼각비교 건너뜀"
fi

echo
echo "로그: $LOG_DIR/"
echo "결과: $GEMMA3_AUTO_CSV, $AGREEMENT_MANUAL_OUT, $AGREEMENT_QWEN_OUT"
exit "$fail"
