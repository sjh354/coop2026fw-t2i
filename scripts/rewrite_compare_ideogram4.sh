#!/usr/bin/env bash
# TASK-G 후속: 리라이팅 4조건(passthrough=v257 / wan_style=v258 / promptenhancer=v259 /
# ideogram_guide=v260, ideogram-4) 생성 결과에 세 가지 지표를 채점한다. 전부 서버 23(채점
# 전용)에서 실행: vqascore+custom_cv(t2i-score, src.scoring), csd_target(t2i-score,
# PYTHONPATH=vendor), vlm-judge(t2i-judge2, InternVL3-8B, scripts/judge_lecture24 — 참고용,
# TASK-B2/TASK-C에서 이미 κ<0.6로 신뢰도 낮음이 확정된 경로).
#
# passthrough/wan_style/promptenhancer는 순수 텍스트를 어댑터가 naive JSON으로 감싸 넣고,
# ideogram_guide는 손으로 작성한 공식 스키마 JSON(style_description + type:"text" 포함)이라
# "리라이팅 품질"과 "캡션 포맷"이 섞여 있는 confound다 — 4-way 순위표가 아니라 참고 수치로
# 취급할 것 (bench/results.md에 이 문구 그대로 남길 것).
#
#     bash scripts/rewrite_compare_ideogram4.sh
#
# 산출물 (버전별 bench/scores/<run>/ 아래):
#   pass1.csv, csd_target.csv, judge_lecture24.csv
# 합본:
#   bench/scores/rewrite_ideogram4_pass1.csv
#   bench/scores/rewrite_ideogram4_csd_target.csv
#   bench/scores/rewrite_ideogram4_judge_lecture24.csv
set -u

for conda_sh in "$HOME/miniconda3/etc/profile.d/conda.sh" "$HOME/anaconda3/etc/profile.d/conda.sh"; do
  if [ -f "$conda_sh" ]; then
    # shellcheck disable=SC1090
    source "$conda_sh"
    break
  fi
done

TASK="rewrite_compare_ideogram4.sh"
LOG_DIR="logs/$(date +%Y%m%d_%H%M%S)_rewrite_compare_ideogram4"
mkdir -p "$LOG_DIR"
ALERT="$(dirname "$0")/alert.py"
EXPECT_N=24

RUN_DIRS=(
  "v257_ideogram-4-lecture24"
  "v258_ideogram-4-lecture24"
  "v259_ideogram-4-lecture24"
  "v260_ideogram-4-lecture24"
)
declare -A BACKEND=(
  ["v257_ideogram-4-lecture24"]="passthrough"
  ["v258_ideogram-4-lecture24"]="wan_style"
  ["v259_ideogram-4-lecture24"]="promptenhancer"
  ["v260_ideogram-4-lecture24"]="ideogram_guide"
)

fail=0
pass1_parts=()
csd_parts=()
judge_parts=()

check_rows() {
  # $1=csv path, $2=label, $3=run_dir(for images-count re-check)
  local csv="$1" label="$2" run_dir="$3"
  local img_n
  img_n=$(ls "image-prompts/${run_dir}/images" 2>/dev/null | wc -l | tr -d ' ')
  if [ "$img_n" -ne "$EXPECT_N" ]; then
    echo "    FAIL: ${run_dir}/images now has ${img_n} files, expected ${EXPECT_N} (deleted mid-run?)"
    return 1
  fi
  local n
  n=$(tail -n +2 "$csv" 2>/dev/null | wc -l | tr -d ' ')
  if [ "$n" -ne "$EXPECT_N" ]; then
    echo "    FAIL: $label got $n rows, expected $EXPECT_N"
    return 1
  fi
  echo "    OK ($n rows)"
  return 0
}

for run_dir in "${RUN_DIRS[@]}"; do
  backend="${BACKEND[$run_dir]}"
  images="image-prompts/${run_dir}/images"
  scores_dir="bench/scores/${run_dir}"
  mkdir -p "$scores_dir"

  pass1_log="$LOG_DIR/pass1_${run_dir}.log"
  echo "=== [$backend] src.scoring vqascore,cv -> $scores_dir/pass1.csv"
  if conda run -n t2i-score python -m src.scoring \
      --dir "$images" --out "$scores_dir/pass1.csv" --components vqascore,cv \
      > "$pass1_log" 2>&1 && check_rows "$scores_dir/pass1.csv" "[$backend/$run_dir] pass1" "$run_dir"; then
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
      > "$csd_log" 2>&1 && check_rows "$scores_dir/csd_target.csv" "[$backend/$run_dir] csd_target" "$run_dir"; then
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
      > "$judge_log" 2>&1 && check_rows "$scores_dir/judge_lecture24.csv" "[$backend/$run_dir] judge_lecture24" "$run_dir"; then
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
merge_csv bench/scores/rewrite_ideogram4_pass1.csv "${pass1_parts[@]}" \
  && echo "    -> bench/scores/rewrite_ideogram4_pass1.csv"
merge_csv bench/scores/rewrite_ideogram4_csd_target.csv "${csd_parts[@]}" \
  && echo "    -> bench/scores/rewrite_ideogram4_csd_target.csv"
merge_csv bench/scores/rewrite_ideogram4_judge_lecture24.csv "${judge_parts[@]}" \
  && echo "    -> bench/scores/rewrite_ideogram4_judge_lecture24.csv"

echo
echo "로그: $LOG_DIR/"
conda run -n t2i-score python "$ALERT" --task "$TASK" --status $([ "$fail" -eq 0 ] && echo ok || echo fail) \
  --message "TASK-G 리라이팅 4조건(ideogram-4) 3지표 채점 완료 — 로그: $LOG_DIR"
exit "$fail"
