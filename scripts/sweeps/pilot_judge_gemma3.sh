#!/usr/bin/env bash
# TASK-C 2차 judge 파일럿: Qwen2.5-VL 계열이 아닌 judge(Gemma-3-12B 4bit)를
# v243(pixart-sigma, lecture24) 파일럿 3장에 붙여 자기 계열 선호(self-enhancement
# bias) 여부를 확인한다. 172.10.5.23(채점 전용 서버)에서 실행.
# unsloth/gemma-3-12b-it-bnb-4bit(사전 4bit 양자화, ~7.3GB, ungated)를 쓴다 —
# google/gemma-3-12b-it 원본(22.7GB, gated)은 서버 여유 디스크에 안 들어가서
# 내려온 선택. 이 체크포인트가 내부적으로 torch>=2.6을 요구해서 기존 t2i-judge
# (Qwen2.5-VL용, torch 2.5.1 고정)를 건드리지 않고 별도 env t2i-judge2
# (torch 2.6.0+cu124, transformers 5.14.1)를 새로 만들어 썼다 — envs/README.md에
# 추가 기록 필요.
#
# 산출물:
#   bench/scores/v243_pixart-sigma-lecture24/judge_spec_gemma3.csv
#   bench/scores/v243_pixart-sigma-lecture24/judge_disagreement_gemma3_vs_manual.csv

set -u

ENV=t2i-judge2
TASK="pilot_judge_gemma3.sh"
RUN_DIR="v243_pixart-sigma-lecture24"
IMAGES="image-prompts/${RUN_DIR}/images"
JUDGE_MODEL="unsloth/gemma-3-12b-it-bnb-4bit"
OUT_CSV="bench/scores/${RUN_DIR}/judge_spec_gemma3.csv"
MANUAL_CSV="bench/scores/${RUN_DIR}/judge_spec_manual.csv"
AGREEMENT_OUT="bench/scores/${RUN_DIR}/judge_disagreement_gemma3_vs_manual.csv"
LOG_DIR="logs/$(date +%Y%m%d_%H%M%S)_pilot_judge_gemma3"

mkdir -p "$LOG_DIR"
JUDGE_LOG="$LOG_DIR/judge_spec_gemma3.log"
AGREEMENT_LOG="$LOG_DIR/judge_agreement.log"

echo "=== [1/2] judge_spec.py --judge-model $JUDGE_MODEL (파일럿 3장) -> $JUDGE_LOG"
if conda run -n "$ENV" python -m scripts.judge_spec \
    --images "$IMAGES" --out "$OUT_CSV" --limit 3 --mode probe \
    --judge-model "$JUDGE_MODEL" > "$JUDGE_LOG" 2>&1; then
  vram=$(grep -o 'vram_peak=[0-9.]*GB' "$JUDGE_LOG" | tail -1 | sed -n 's/vram_peak=\([0-9.]*\)GB/\1/p')
  echo "    OK  vram_peak=${vram:-?}GB"
  conda run -n "$ENV" python "$(dirname "$0")/../alert.py" --task "$TASK" --status ok \
    --message "gemma3 judge_spec 파일럿 OK (vram_peak=${vram:-?}GB, model=${JUDGE_MODEL})"
else
  echo "    FAIL — 로그: $JUDGE_LOG"
  conda run -n "$ENV" python "$(dirname "$0")/../alert.py" --task "$TASK" --status fail \
    --message "gemma3 judge_spec 파일럿 실패: $(tail -5 "$JUDGE_LOG" | tr '\n' ' ' | cut -c1-300)"
  exit 1
fi

echo "=== [2/2] judge_agreement.py (gemma3 vs 사람 손 채점) -> $AGREEMENT_LOG"
if conda run -n "$ENV" python -m scripts.judge_agreement \
    --a "$MANUAL_CSV" --b "$OUT_CSV" --out "$AGREEMENT_OUT" > "$AGREEMENT_LOG" 2>&1; then
  echo "    OK"
  cat "$AGREEMENT_LOG"
  conda run -n "$ENV" python "$(dirname "$0")/../alert.py" --task "$TASK" --status ok --log "$AGREEMENT_LOG"
else
  echo "    FAIL — 로그: $AGREEMENT_LOG"
  conda run -n "$ENV" python "$(dirname "$0")/../alert.py" --task "$TASK" --status fail \
    --message "judge_agreement 실패: $(tail -5 "$AGREEMENT_LOG" | tr '\n' ' ' | cut -c1-300)"
  exit 1
fi

echo
echo "로그: $LOG_DIR/"
echo "결과: $OUT_CSV, $AGREEMENT_OUT"
