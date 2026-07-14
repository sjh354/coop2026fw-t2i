#!/usr/bin/env bash
# sweep6.sh에서 실패했던 모델들만 다시 실행 (qwen-image: generic.py 양자화 config 버그 수정함, ideogram-4: 게이트 리포 접근 문제 미해결)

set -u

MIN_FREE_GB=20          # 다음 모델을 받기 전 확보돼야 할 최소 여유
LOG_DIR="logs/$(date +%Y%m%d_%H%M%S)_sweep7"
HF_HUB="${HF_HOME:-$HOME/.cache/huggingface}/hub"

MODELS=(
  qwen-image
  ideogram-4
)
EXPS=(
  coloring-book
  flat-illust
  educational-flat
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

# configs/models/<name>.yaml 의 env 필드 (conda env 이름)
env_of() {
  grep -E '^env:' "configs/models/$1.yaml" | awk '{print $2}'
}

# 이미 다운로드돼 있는 모델인지 확인 (snapshots/에 뭔가 있으면 캐시됨).
is_cached() {
  local d
  d=$(cache_dir_of "$1")
  [ -d "$d/snapshots" ] && [ -n "$(ls -A "$d/snapshots" 2>/dev/null)" ]
}

DONE_MODELS=()

# 이번 실행의 MODELS에 없는 다른 모델들의 캐시 (예전 sweep들이 남긴 것) 도 정리 대상에 넣는다.
other_cached_models() {
  for f in configs/models/*.yaml; do
    local name
    name=$(basename "$f" .yaml)
    [[ " ${MODELS[*]} " == *" $name "* ]] && continue
    is_cached "$name" && echo "$name"
  done
}

# 여유공간이 부족하면 이미 끝난 모델 + 이번 실행에 없는 모델의 캐시를 지운다.
reclaim() {
  local avail
  avail=$(free_gb)
  [ -z "$avail" ] && return 0
  echo ">>> free: ${avail}GB (need ${MIN_FREE_GB}GB)"
  local candidates=("${DONE_MODELS[@]}")
  while IFS= read -r m; do
    [ -n "$m" ] && candidates+=("$m")
  done < <(other_cached_models)
  if [ "${#candidates[@]}" -eq 0 ]; then
    echo ">>> free after reclaim: $(free_gb)GB"
    return 0
  fi
  for m in "${candidates[@]}"; do
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
  if [ "$(free_gb)" -lt "$MIN_FREE_GB" ] && ! is_cached "$model"; then
    echo "!!! 여유공간 부족 ($(free_gb)GB) 하고 캐시도 없음. $model 건너뜀."
    printf "%s\t-\tSKIP_DISK\t-\t-\n" "$model" >> "$SUMMARY"
    continue
  fi
  is_cached "$model" && echo ">>> $model 은 이미 캐시됨 — 디스크 게이트 건너뜀"

  env=$(env_of "$model")
  if [ -z "$env" ]; then
    echo "!!! configs/models/$model.yaml 에 env 필드 없음. 건너뜀."
    printf "%s\t-\tSKIP_NOENV\t-\t-\n" "$model" >> "$SUMMARY"
    continue
  fi

  model_ok=0
  for exp in "${EXPS[@]}"; do
    log="$LOG_DIR/${model}__${exp}.log"
    echo "=== $model ($env) × $exp -> $log"

    if conda run -n "$env" python -m src.generate --model "$model" --exp "$exp" > "$log" 2>&1; then
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
      # 건너뛰고 계속. 세 실험 다 실패해도 다음 모델로 간다.
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
python "$(dirname "$0")/alert.py" --task "sweep7.sh" --status "$status" --log "$SUMMARY"
