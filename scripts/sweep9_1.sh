#!/usr/bin/env bash
# 서버 1: ideogram-4 / sana-1600m / sd35-medium 담당 (sweep8_1 과 동일한 모델 조합
# — 이미 이 서버에 캐시된 모델이라 재다운로드 없이 그대로 이어서 쓴다).
# (서버 2는 sweep9_2.sh 가 qwen-image / flux2-klein-9b / lumina2 담당)
# -es 실험은 계속 제외. sweep8_1 로 diagram-*/formula-chalkboard/history-flat 는
# 이미 끝났으니, 이번엔 각 모델별로 남은 formula-print / history-storybook 만 돈다.
#
# 분배 근거 — sweep8_1 실측 sec/img * 30장 * 남은 실험 2개
# (캐시 재사용을 시간 밸런스보다 우선해서 서버 배정은 sweep8 과 동일하게 유지 — 서버2가 더 오래 걸림):
#   ideogram-4      ~159.4s/img -> ~2.66h
#   sana-1600m      ~3.75s/img  -> ~0.06h
#   sd35-medium     ~13.6s/img  -> ~0.23h
#   합계 서버1 ≈ 2.95h   (서버2: qwen-image ~2.53h + flux2-klein-9b ~0.43h + lumina2(6개 실험) ~1.49h ≈ 4.45h)

set -u

MIN_FREE_GB=35          # ideogram-4 gguf+encoder 합쳐 ~30GB대라 여유 크게
LOG_DIR="logs/$(date +%Y%m%d_%H%M%S)_sweep9_1"
HF_HUB="${HF_HOME:-$HOME/.cache/huggingface}/hub"
TASK="sweep9_1.sh"

MODELS=(
  ideogram-4
  sana-1600m
  sd35-medium
)

EXPS=(
  formula-print
  history-storybook
)

mkdir -p "$LOG_DIR"
SUMMARY="$LOG_DIR/summary.tsv"
printf "model\texp\tstatus\tvram_gb\tsec_per_img\n" > "$SUMMARY"

free_gb() { df -BG --output=avail "$HF_HUB" 2>/dev/null | tail -1 | tr -dc '0-9'; }

cache_dir_of() {
  local repo
  repo=$(grep -E '^repo:' "configs/models/$1.yaml" | awk '{print $2}')
  echo "$HF_HUB/models--${repo//\//--}"
}

env_of() {
  grep -E '^env:' "configs/models/$1.yaml" | awk '{print $2}'
}

keywords_of() {
  grep -E '^keywords:' "configs/experiments/$1.yaml" | awk '{print $2}'
}

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

other_cached_models() {
  for f in configs/models/*.yaml; do
    local name
    name=$(basename "$f" .yaml)
    [[ " ${MODELS[*]} " == *" $name "* ]] && continue
    is_cached "$name" && echo "$name"
  done
}

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
      rm -rf "$d"
    fi
  done
  echo ">>> free after reclaim: $(free_gb)GB"
}

# 조합 하나 끝날 때마다 디스코드로 알림 (예: "SUCCESS : ideogram-4/formula-print/formula30").
notify_attempt() {
  local word="$1" model="$2" exp="$3" kw="$4" extra="$5"
  python "$(dirname "$0")/alert.py" --task "$TASK" --status "$([ "$word" = SUCCESS ] && echo ok || echo fail)" \
    --message "${word} : ${model}/${exp}/${kw}${extra:+ (${extra})}"
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
    kw=$(keywords_of "$exp")

    if has_done "$model" "$exp"; then
      echo "--- $model × $exp: 이미 done — 스킵"
      printf "%s\t%s\tSKIP_DONE\t-\t-\n" "$model" "$exp" >> "$SUMMARY"
      model_ok=1
      continue
    fi

    log="$LOG_DIR/${model}__${exp}.log"
    echo "=== $model ($env) × $exp -> $log"

    if conda run -n "$env" python -m src.generate --model "$model" --exp "$exp" > "$log" 2>&1; then
      tail=$(grep -o 'vram_peak=[0-9.]*GB  sec/img=[0-9.]*' "$log" | tail -1)
      vram=$(echo "$tail" | sed -n 's/.*vram_peak=\([0-9.]*\)GB.*/\1/p')
      spi=$(echo "$tail" | sed -n 's/.*sec\/img=\([0-9.]*\).*/\1/p')
      printf "%s\t%s\tOK\t%s\t%s\n" "$model" "$exp" "${vram:--}" "${spi:--}" >> "$SUMMARY"
      echo "    OK  vram=${vram:-?}GB  ${spi:-?}s/img"
      notify_attempt "SUCCESS" "$model" "$exp" "$kw" "vram=${vram:-?}GB, ${spi:-?}s/img"
      model_ok=1
    else
      printf "%s\t%s\tFAIL\t-\t-\n" "$model" "$exp" >> "$SUMMARY"
      echo "    FAIL — 로그: $log"
      echo "    $(tail -3 "$log" | tr '\n' ' ')"
      notify_attempt "FAIL" "$model" "$exp" "$kw" "$(tail -3 "$log" | tr '\n' ' ' | cut -c1-200)"
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
python "$(dirname "$0")/alert.py" --task "$TASK" --status "$status" --log "$SUMMARY"
