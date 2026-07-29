#!/usr/bin/env bash
# TASK-I 파트 2: 길이 사다리 "medium" 조건 1개 run을 4지표로 채점한다.
# rewrite_compare_v261_262.sh와 동일 패턴, run 1개짜리로 축소. 서버 23(채점 전용)에서 실행.
#
#     bash scripts/rewrite_score_ladder.sh v263_flux2-klein-4b-nf4-lecture24
set -u

RUN_DIR="${1:?사용법: rewrite_score_ladder.sh <run_dir, 예: v263_flux2-klein-4b-nf4-lecture24>}"

for conda_sh in "$HOME/miniconda3/etc/profile.d/conda.sh" "$HOME/anaconda3/etc/profile.d/conda.sh"; do
  if [ -f "$conda_sh" ]; then
    # shellcheck disable=SC1090
    source "$conda_sh"
    break
  fi
done

TASK="rewrite_score_ladder.sh"
LOG_DIR="logs/$(date +%Y%m%d_%H%M%S)_rewrite_score_ladder"
mkdir -p "$LOG_DIR"
ALERT="$(dirname "$0")/alert.py"

images="image-prompts/${RUN_DIR}/images"
scores_dir="bench/scores/${RUN_DIR}"
mkdir -p "$scores_dir"
fail=0

pass1_log="$LOG_DIR/pass1.log"
echo "=== src.scoring vqascore,cv -> $scores_dir/pass1.csv"
if conda run -n t2i-score python -m src.scoring \
    --dir "$images" --out "$scores_dir/pass1.csv" --components vqascore,cv \
    > "$pass1_log" 2>&1; then
  echo "    OK"
  conda run -n t2i-score python "$ALERT" --task "$TASK" --status ok --message "[$RUN_DIR] pass1 OK"
else
  echo "    FAIL — 로그: $pass1_log"
  conda run -n t2i-score python "$ALERT" --task "$TASK" --status fail \
    --message "[$RUN_DIR] pass1 실패: $(tail -5 "$pass1_log" | tr '\n' ' ' | cut -c1-300)"
  fail=1
fi

csd_log="$LOG_DIR/csd_target.log"
echo "=== score_csd_target -> $scores_dir/csd_target.csv"
if PYTHONPATH=vendor conda run -n t2i-score python -m scripts.score_csd_target \
    --dir "$images" --out "$scores_dir/csd_target.csv" \
    > "$csd_log" 2>&1; then
  echo "    OK"
  conda run -n t2i-score python "$ALERT" --task "$TASK" --status ok --message "[$RUN_DIR] csd_target OK"
else
  echo "    FAIL — 로그: $csd_log"
  conda run -n t2i-score python "$ALERT" --task "$TASK" --status fail \
    --message "[$RUN_DIR] csd_target 실패: $(tail -5 "$csd_log" | tr '\n' ' ' | cut -c1-300)"
  fail=1
fi

judge_log="$LOG_DIR/judge_lecture24.log"
echo "=== judge_lecture24 (InternVL3-8B) -> $scores_dir/judge_lecture24.csv"
if conda run -n t2i-judge2 python -m scripts.judge_lecture24 \
    --runs "image-prompts/${RUN_DIR}" \
    > "$judge_log" 2>&1; then
  echo "    OK"
  vram=$(grep -o 'vram_peak=[0-9.]*GB' "$judge_log" | tail -1)
  conda run -n t2i-score python "$ALERT" --task "$TASK" --status ok \
    --message "[$RUN_DIR] judge_lecture24 OK ($vram)"
else
  echo "    FAIL — 로그: $judge_log"
  conda run -n t2i-score python "$ALERT" --task "$TASK" --status fail \
    --message "[$RUN_DIR] judge_lecture24 실패: $(tail -5 "$judge_log" | tr '\n' ' ' | cut -c1-300)"
  fail=1
fi

echo
echo "로그: $LOG_DIR/"
conda run -n t2i-score python "$ALERT" --task "$TASK" --status $([ "$fail" -eq 0 ] && echo ok || echo fail) \
  --message "TASK-I 파트2 길이 사다리 medium 조건($RUN_DIR) 4지표 채점 완료 — 로그: $LOG_DIR"
exit "$fail"
