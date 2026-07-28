#!/usr/bin/env bash
# TASK-C 3차 judge 파일럿: Qwen2.5-VL 계열이 아닌 judge(InternVL3-8B)를
# v243(pixart-sigma, lecture24) 파일럿 3장에 붙여 자기 계열 선호(self-enhancement
# bias) 여부를 확인한다. 172.10.5.23(채점 전용 서버)에서 실행.
# OpenGVLab/InternVL3-8B-hf(15.9GB, transformers 5.14.1 네이티브
# InternVLForConditionalGeneration, trust_remote_code 불필요)를 쓴다 —
# 원본 OpenGVLab/InternVL3-8B는 커스텀 InternVLChatModel 클래스라 judge.py의
# 범용 AutoModelForImageTextToText 백엔드와 호환되지 않아 제외. gemma3와 같은
# env(t2i-judge2, torch 2.6.0+cu124, transformers 5.14.1)를 그대로 쓴다.
#
# 산출물:
#   bench/scores/v243_pixart-sigma-lecture24/judge_spec_internvl3.csv
#   bench/scores/v243_pixart-sigma-lecture24/judge_disagreement_internvl3_vs_manual.csv

set -u

ENV=t2i-judge2
TASK="pilot_judge_internvl3.sh"
RUN_DIR="v243_pixart-sigma-lecture24"
IMAGES="image-prompts/${RUN_DIR}/images"
JUDGE_MODEL="OpenGVLab/InternVL3-8B-hf"
OUT_CSV="bench/scores/${RUN_DIR}/judge_spec_internvl3.csv"
MANUAL_CSV="bench/scores/${RUN_DIR}/judge_spec_manual.csv"
AGREEMENT_OUT="bench/scores/${RUN_DIR}/judge_disagreement_internvl3_vs_manual.csv"
LOG_DIR="logs/$(date +%Y%m%d_%H%M%S)_pilot_judge_internvl3"

mkdir -p "$LOG_DIR"
JUDGE_LOG="$LOG_DIR/judge_spec_internvl3.log"
AGREEMENT_LOG="$LOG_DIR/judge_agreement.log"

echo "=== [1/2] judge_spec.py --judge-model $JUDGE_MODEL (파일럿 3장) -> $JUDGE_LOG"
if conda run -n "$ENV" python -m scripts.judge_spec \
    --images "$IMAGES" --out "$OUT_CSV" --limit 3 --mode probe \
    --judge-model "$JUDGE_MODEL" > "$JUDGE_LOG" 2>&1; then
  vram=$(grep -o 'vram_peak=[0-9.]*GB' "$JUDGE_LOG" | tail -1 | sed -n 's/vram_peak=\([0-9.]*\)GB/\1/p')
  echo "    OK  vram_peak=${vram:-?}GB"
  conda run -n "$ENV" python "$(dirname "$0")/../alert.py" --task "$TASK" --status ok \
    --message "internvl3 judge_spec 파일럿 OK (vram_peak=${vram:-?}GB, model=${JUDGE_MODEL})"
else
  echo "    FAIL — 로그: $JUDGE_LOG"
  conda run -n "$ENV" python "$(dirname "$0")/../alert.py" --task "$TASK" --status fail \
    --message "internvl3 judge_spec 파일럿 실패: $(tail -5 "$JUDGE_LOG" | tr '\n' ' ' | cut -c1-300)"
  exit 1
fi

echo "=== [2/2] judge_agreement.py (internvl3 vs 사람 손 채점) -> $AGREEMENT_LOG"
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
