#!/usr/bin/env bash
# 새로 추가된 조합(교육용 flat 스타일 × basic30/spanish30)을 5모델에 대해 순차 실행한다.
#
#   bash scripts/sweep2.sh
#
# sweep.sh와 동일한 구조 (모델 루프가 바깥, 디스크 회수 로직 동일) —
# EXPS만 새 실험 2개(educational-flat, educational-flat-es)로 교체.
# educational-flat-es가 spanish30 키워드셋을 쓰므로 이 스윕이 spanish30.yaml도
# 함께 검증한다.

set -u

MIN_FREE_GB=20          # 다음 모델을 받기 전 확보돼야 할 최소 여유
LOG_DIR="logs/$(date +%Y%m%d_%H%M%S)_sweep2"
HF_HUB="${HF_HOME:-$HOME/.cache/huggingface}/hub"

MODELS=(
  pixart-sigma
  flux2-klein-4b
  flux2-klein-4b-base
  zimage-turbo
  sdxl
)
EXPS=(educational-flat educational-flat-es)

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

DONE_MODELS=()

# 여유공간이 부족하면 이미 끝난 모델 캐시를 오래된 순으로 지운다.
reclaim() {
  local avail
  avail=$(free_gb)
  [ -z "$avail" ] && return 0
  echo ">>> free: ${avail}GB (need ${MIN_FREE_GB}GB)"
  for m in "${DONE_MODELS[@]:-}"; do
    [ "$(free_gb)" -ge "$MIN_FREE_GB" ] && break
    local d
    d=$(cache_dir_of "$m")
    if [ -d "$d" ]; then
      echo ">>> reclaim: rm $d ($(du -sh "$d" | cut -f1))"
      rm -rf "$d"          # models--*/ 통째로 지우는 건 안전 (blobs+snapshots+refs가 다 안에 있음)
    fi
  done
  echo ">>> free after reclaim: $(free_gb)GB"
}

for model in "${MODELS[@]}"; do
  reclaim
  if [ "$(free_gb)" -lt "$MIN_FREE_GB" ]; then
    echo "!!! 여유공간 부족 ($(free_gb)GB). $model 건너뜀."
    printf "%s\t-\tSKIP_DISK\t-\t-\n" "$model" >> "$SUMMARY"
    continue
  fi

  model_ok=0
  for exp in "${EXPS[@]}"; do
    log="$LOG_DIR/${model}__${exp}.log"
    echo "=== $model × $exp -> $log"

    if python -m src.generate --model "$model" --exp "$exp" > "$log" 2>&1; then
      # generate.py 마지막 줄: "done. vram_peak=13.2GB  sec/img=4.10"
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
      # 건너뛰고 계속. 두 스타일 다 실패해도 다음 모델로 간다.
    fi
  done

  # 한 번이라도 성공했으면 캐시 삭제 후보에 넣는다.
  # (전부 실패한 모델은 재시도 여지를 남겨 안 지운다)
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
python "$(dirname "$0")/alert.py" --task "sweep2.sh" --status "$status" --log "$SUMMARY"
