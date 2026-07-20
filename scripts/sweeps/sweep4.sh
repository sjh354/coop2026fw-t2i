#!/usr/bin/env bash
# 결과(done)가 없는 모델×실험 조합만 돌린다.
# image-prompts/v*/*.md 의 frontmatter를 스캔해서 status: done 인 노트가
# 이미 있는 조합은 건너뛴다. (running 으로 멈춘 실패 조합은 재실행 대상)
#
#   bash scripts/sweep4.sh
#
# 구조는 sweep3.sh 와 동일 (모델 루프 바깥, 디스크 회수 로직 동일).
# 차이점: 각 model×exp 조합 시작 전 has_done() 으로 이미 끝난 조합을 스킵한다.

set -u

MIN_FREE_GB=20          # 다음 모델을 받기 전 확보돼야 할 최소 여유
LOG_DIR="logs/$(date +%Y%m%d_%H%M%S)_sweep4"
HF_HUB="${HF_HOME:-$HOME/.cache/huggingface}/hub"

MODELS=(
  flux2-klein-4b
  flux2-klein-4b-base
  zimage-turbo
  sdxl
  pixart-sigma
)
EXPS=(
  coloring-book
  flat-illust
  coloring-book-es
  flat-illust-es
  educational-flat
  educational-flat-es
  diagram-clean
  diagram-whiteboard
  formula-chalkboard
  formula-print
  history-flat
  history-storybook
)

mkdir -p "$LOG_DIR"
SUMMARY="$LOG_DIR/summary.tsv"
printf "model\texp\tstatus\tvram_gb\tsec_per_img\n" > "$SUMMARY"

free_gb() { df -BG --output=avail "$HF_HUB" 2>/dev/null | tail -1 | tr -dc '0-9'; }

# configs/models/<name>.yaml 의 repo -> HF 캐시 디렉토리명
cache_dir_of() {
  local repo
  repo=$(grep -E '^repo:' "configs/models/$1.yaml" | awk '{print $2}')
  echo "$HF_HUB/models--${repo//\//--}"
}

# 이미 다운로드돼 있는 모델인지 확인 (snapshots/에 뭔가 있으면 캐시됨).
is_cached() {
  local d
  d=$(cache_dir_of "$1")
  [ -d "$d/snapshots" ] && [ -n "$(ls -A "$d/snapshots" 2>/dev/null)" ]
}

# image-prompts/v*/*.md 중 model+experiment 가 일치하면서 status: done 인 노트가
# 하나라도 있으면 0(true) 반환 — 이미 끝난 조합이므로 스킵.
has_done() {
  local model="$1" exp="$2" f
  for f in image-prompts/v*/*.md; do
    [ -f "$f" ] || continue
    grep -q "^model:[[:space:]]*${model}[[:space:]]*$" "$f" && \
    grep -q "^experiment:[[:space:]]*${exp}[[:space:]]*$" "$f" && \
    grep -q "^status:[[:space:]]*done" "$f" && return 0
  done
  return 1
}

DONE_MODELS=()

# 여유공간이 부족하면 이미 끝난 모델 캐시를 오래된 순으로 지운다.
reclaim() {
  local avail
  avail=$(free_gb)
  [ -z "$avail" ] && return 0
  echo ">>> free: ${avail}GB (need ${MIN_FREE_GB}GB)"
  if [ "${#DONE_MODELS[@]}" -eq 0 ]; then
    echo ">>> free after reclaim: $(free_gb)GB"
    return 0
  fi
  for m in "${DONE_MODELS[@]}"; do
    [ "$(free_gb)" -ge "$MIN_FREE_GB" ] && break
    local d
    d=$(cache_dir_of "$m")
    if [ -d "$d" ]; then
      echo ">>> reclaim: rm $d ($(du -sh "$d" | cut -f1))"
      rm -rf "$d"
    fi
  done
  echo ">>> free after reclaim: $(free_gb)GB"
}

for model in "${MODELS[@]}"; do
  reclaim
  if [ "$(free_gb)" -lt "$MIN_FREE_GB" ] && ! is_cached "$model"; then
    echo "!!! 여유공간 부족 ($(free_gb)GB) 하고 캐시도 없음. $model 건너뜀."
    printf "%s\t-\tSKIP_DISK\t-\t-\n" "$model" >> "$SUMMARY"
    continue
  fi
  is_cached "$model" && echo ">>> $model 은 이미 캐시됨 — 디스크 게이트 건너뜀"

  model_ok=0
  for exp in "${EXPS[@]}"; do
    if has_done "$model" "$exp"; then
      echo "--- $model × $exp: 이미 done — 스킵"
      printf "%s\t%s\tSKIP_DONE\t-\t-\n" "$model" "$exp" >> "$SUMMARY"
      model_ok=1
      continue
    fi

    log="$LOG_DIR/${model}__${exp}.log"
    echo "=== $model × $exp -> $log"

    if python -m src.generate --model "$model" --exp "$exp" > "$log" 2>&1; then
      tail=$(grep -o 'vram_peak=[0-9.]*GB  sec/img=[0-9.]*' "$log" | tail -1)
      vram=$(echo "$tail" | sed -n 's/.*vram_peak=\([0-9.]*\)GB.*/\1/p')
      spi=$(echo "$tail" | sed -n 's/.*sec\/img=\([0-9.]*\).*/\1/p')
      printf "%s\t%s\tOK\t%s\t%s\n" "$model" "$exp" "${vram:--}" "${spi:--}" >> "$SUMMARY"
      echo "    OK  vram=${vram:-?}GB  ${spi:-?}s/img"
      model_ok=1
    else
      printf "%s\t%s\tFAIL\t-\t-\n" "$model" "$exp" >> "$SUMMARY"
      echo "    FAIL — 로그: $log"
      echo "    $(tail -3 "$log" | tr '\n' ' ')"
    fi
  done

  [ "$model_ok" -eq 1 ] && DONE_MODELS+=("$model")
done

echo
echo "=== summary ==="
column -t -s $'\t' "$SUMMARY"
echo
echo "로그: $LOG_DIR/"
echo "리뷰: streamlit run src/review_app.py"

status=ok
grep -q -E $'\t(FAIL|SKIP_DISK)\t' "$SUMMARY" && status=fail
python "$(dirname "$0")/alert.py" --task "sweep4.sh" --status "$status" --log "$SUMMARY"