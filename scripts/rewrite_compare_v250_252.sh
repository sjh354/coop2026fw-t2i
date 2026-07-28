#!/usr/bin/env bash
# TASK-E 후속: 리라이팅 3백엔드(passthrough=v250 / wan_style=v251 / promptenhancer=v252,
# flux2-klein-4b-nf4) 생성 결과에 네 가지 지표를 전부 채점한다. 전부 서버 23(채점 전용)에서
# 실행: vqascore+custom_cv(t2i-score, src.scoring), csd_target(t2i-score, PYTHONPATH=vendor),
# vlm-judge(t2i-judge2, InternVL3-8B 기본값, scripts/judge_lecture24).
#
#     bash scripts/rewrite_compare_v250_252.sh
#
# 산출물 (버전별 bench/scores/<run>/ 아래):
#   pass1.csv, csd_target.csv, judge_lecture24.csv
# 합본:
#   bench/scores/rewrite_v250_252_pass1.csv
#   bench/scores/rewrite_v250_252_csd_target.csv
#   bench/scores/rewrite_v250_252_judge_lecture24.csv
set -u

for conda_sh in "$HOME/miniconda3/etc/profile.d/conda.sh" "$HOME/anaconda3/etc/profile.d/conda.sh"; do
  if [ -f "$conda_sh" ]; then
    # shellcheck disable=SC1090
    source "$conda_sh"
    break
  fi
done

TASK="rewrite_compare_v250_252.sh"
LOG_DIR="logs/$(date +%Y%m%d_%H%M%S)_rewrite_compare_v250_252"
mkdir -p "$LOG_DIR"
ALERT="$(dirname "$0")/alert.py"

RUN_DIRS=(
  "v250_flux2-klein-4b-nf4-lecture24"
  "v251_flux2-klein-4b-nf4-lecture24"
  "v252_flux2-klein-4b-nf4-lecture24"
)
declare -A BACKEND=(
  ["v250_flux2-klein-4b-nf4-lecture24"]="passthrough"
  ["v251_flux2-klein-4b-nf4-lecture24"]="wan_style"
  ["v252_flux2-klein-4b-nf4-lecture24"]="promptenhancer"
)

fail=0
pass1_parts=()
csd_parts=()
judge_parts=()

for run_dir in "${RUN_DIRS[@]}"; do
  backend="${BACKEND[$run_dir]}"
  images="image-prompts/${run_dir}/images"
  scores_dir="bench/scores/${run_dir}"
  mkdir -p "$scores_dir"

  pass1_log="$LOG_DIR/pass1_${run_dir}.log"
  echo "=== [$backend] src.scoring vqascore,cv -> $scores_dir/pass1.csv"
  if conda run -n t2i-score python -m src.scoring \
      --dir "$images" --out "$scores_dir/pass1.csv" --components vqascore,cv \
      > "$pass1_log" 2>&1; then
    echo "    OK"
    conda run -n t2i-score python "$ALERT" --task "$TASK" --status ok \
      --message "[$backend/$run_dir] pass1(vqascore+cv) OK"
    pass1_parts+=("$scores_dir/pass1.csv")
  else
    echo "    FAIL — 로그: $pass1_log"
    conda run -n t2i-score python "$ALERT" --task "$TASK" --status fail \
      --message "[$backend/$run_dir] pass1 실패: $(tail -5 "$pass1_log" | tr '\n' ' ' | cut -c1-300)"
    fail=1
  fi

  csd_log="$LOG_DIR/csd_target_${run_dir}.log"
  echo "=== [$backend] score_csd_target -> $scores_dir/csd_target.csv"
  if PYTHONPATH=vendor conda run -n t2i-score python -m scripts.score_csd_target \
      --dir "$images" --out "$scores_dir/csd_target.csv" \
      > "$csd_log" 2>&1; then
    echo "    OK"
    conda run -n t2i-score python "$ALERT" --task "$TASK" --status ok \
      --message "[$backend/$run_dir] csd_target OK"
    csd_parts+=("$scores_dir/csd_target.csv")
  else
    echo "    FAIL — 로그: $csd_log"
    conda run -n t2i-score python "$ALERT" --task "$TASK" --status fail \
      --message "[$backend/$run_dir] csd_target 실패: $(tail -5 "$csd_log" | tr '\n' ' ' | cut -c1-300)"
    fail=1
  fi

  judge_log="$LOG_DIR/judge_lecture24_${run_dir}.log"
  echo "=== [$backend] judge_lecture24 (InternVL3-8B) -> $scores_dir/judge_lecture24.csv"
  if conda run -n t2i-judge2 python -m scripts.judge_lecture24 \
      --runs "image-prompts/${run_dir}" \
      > "$judge_log" 2>&1; then
    echo "    OK"
    vram=$(grep -o 'vram_peak=[0-9.]*GB' "$judge_log" | tail -1)
    conda run -n t2i-score python "$ALERT" --task "$TASK" --status ok \
      --message "[$backend/$run_dir] judge_lecture24 OK ($vram)"
    judge_parts+=("$scores_dir/judge_lecture24.csv")
  else
    echo "    FAIL — 로그: $judge_log"
    conda run -n t2i-score python "$ALERT" --task "$TASK" --status fail \
      --message "[$backend/$run_dir] judge_lecture24 실패: $(tail -5 "$judge_log" | tr '\n' ' ' | cut -c1-300)"
    fail=1
  fi
done

merge_csv() {
  local out="$1"; shift
  local parts=("$@")
  [ "${#parts[@]}" -eq 0 ] && return 1
  head -1 "${parts[0]}" > "$out"
  for p in "${parts[@]}"; do
    tail -n +2 "$p" >> "$out"
  done
}

echo "=== 합본 CSV 생성"
merge_csv bench/scores/rewrite_v250_252_pass1.csv "${pass1_parts[@]}" \
  && echo "    -> bench/scores/rewrite_v250_252_pass1.csv"
merge_csv bench/scores/rewrite_v250_252_csd_target.csv "${csd_parts[@]}" \
  && echo "    -> bench/scores/rewrite_v250_252_csd_target.csv"
merge_csv bench/scores/rewrite_v250_252_judge_lecture24.csv "${judge_parts[@]}" \
  && echo "    -> bench/scores/rewrite_v250_252_judge_lecture24.csv"

echo
echo "로그: $LOG_DIR/"
conda run -n t2i-score python "$ALERT" --task "$TASK" --status $([ "$fail" -eq 0 ] && echo ok || echo fail) \
  --message "TASK-E 리라이팅 3조건(passthrough/wan_style/promptenhancer) 4지표 채점 완료 — 로그: $LOG_DIR"
exit "$fail"
