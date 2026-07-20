#!/usr/bin/env bash
# 복합 프롬프트(수량/공간/속성 결합) 2라운드 파일럿 러너. pilot_dialect.sh(1라운드) 구조 재사용.
#
# 5개 모델(flux2-klein-4b, pixart-sigma, sd35-medium, zimage-turbo, lumina2) 각각에
# 대해 shared(educational-flat-v2-complex)와 dialect(edu-<model>-v2) 두 조건을
# pilot-complex3(수량/공간/속성 키워드 3개)로 생성한다. v2 스타일 사용 —
# "textbook infographic style" 명사 누출을 제거한 버전(Step1~3에서 lumina2/
# flux2-klein-4b로 재검증 완료).
#
# 디스크가 작아 1라운드와 동일하게, 모델 하나가 두 조건을 다 끝내면 여유 공간과
# 무관하게 그 모델 캐시를 즉시 삭제한다(cleanup_model).

set -u

MIN_FREE_GB=20
LOG_DIR="logs/$(date +%Y%m%d_%H%M%S)_pilot_complex3"
HF_HUB="${HF_HOME:-$HOME/.cache/huggingface}/hub"
TASK="pilot_complex3.sh"
EXP="educational-flat-v2-complex"

MODELS=(
  flux2-klein-4b
  pixart-sigma
  sd35-medium
  zimage-turbo
  lumina2
)

mkdir -p "$LOG_DIR"
SUMMARY="$LOG_DIR/summary.tsv"
printf "model\tcondition\tstatus\tvram_gb\tsec_per_img\n" > "$SUMMARY"

free_gb() { df -BG --output=avail "$HF_HUB" 2>/dev/null | tail -1 | tr -dc '0-9'; }

cache_dir_of() {
  local repo
  repo=$(grep -E '^repo:' "configs/models/$1.yaml" | awk '{print $2}')
  echo "$HF_HUB/models--${repo//\//--}"
}

env_of() {
  grep -E '^env:' "configs/models/$1.yaml" | awk '{print $2}'
}

is_cached() {
  local d
  d=$(cache_dir_of "$1")
  [ -d "$d/snapshots" ] && [ -n "$(ls -A "$d/snapshots" 2>/dev/null)" ]
}

has_done_pilot() {
  local model="$1" condition="$2" f
  for f in image-prompts/v*/*.md; do
    [ -f "$f" ] || continue
    grep -q "^model:[[:space:]]*${model}[[:space:]]*$" "$f" && \
    grep -q "^experiment:[[:space:]]*${EXP}[[:space:]]*$" "$f" && \
    grep -q "^condition:[[:space:]]*${condition}[[:space:]]*$" "$f" && \
    grep -q "^status:[[:space:]]*done" "$f" && return 0
  done
  return 1
}

cleanup_model() {
  local model="$1" d
  d=$(cache_dir_of "$model")
  if [ -d "$d" ]; then
    echo ">>> cleanup: rm $d ($(du -sh "$d" 2>/dev/null | cut -f1))"
    rm -rf "$d"
  fi
  echo ">>> free after cleanup: $(free_gb)GB"
}

notify_attempt() {
  local word="$1" model="$2" condition="$3" extra="$4"
  python "$(dirname "$0")/alert.py" --task "$TASK" --status "$([ "$word" = SUCCESS ] && echo ok || echo fail)" \
    --message "${word} : ${model}/${condition}${extra:+ (${extra})}"
}

run_one() {
  local model="$1" condition="$2" dialect_args="$3"
  local log="$LOG_DIR/${model}__${condition}.log"
  echo "=== $model ($env) × $condition -> $log"

  if conda run -n "$env" python -m src.generate --model "$model" --exp "$EXP" $dialect_args > "$log" 2>&1; then
    local tail vram spi
    tail=$(grep -o 'vram_peak=[0-9.]*GB  sec/img=[0-9.]*' "$log" | tail -1)
    vram=$(echo "$tail" | sed -n 's/.*vram_peak=\([0-9.]*\)GB.*/\1/p')
    spi=$(echo "$tail" | sed -n 's/.*sec\/img=\([0-9.]*\).*/\1/p')
    printf "%s\t%s\tOK\t%s\t%s\n" "$model" "$condition" "${vram:--}" "${spi:--}" >> "$SUMMARY"
    echo "    OK  vram=${vram:-?}GB  ${spi:-?}s/img"
    notify_attempt "SUCCESS" "$model" "$condition" "vram=${vram:-?}GB, ${spi:-?}s/img"
    return 0
  fi

  printf "%s\t%s\tFAIL\t-\t-\n" "$model" "$condition" >> "$SUMMARY"
  echo "    FAIL — 로그: $log"
  echo "    $(tail -3 "$log" | tr '\n' ' ')"
  notify_attempt "FAIL" "$model" "$condition" "$(tail -3 "$log" | tr '\n' ' ' | cut -c1-200)"
}

for model in "${MODELS[@]}"; do
  avail=$(free_gb)
  if [ -n "$avail" ] && [ "$avail" -lt "$MIN_FREE_GB" ] && ! is_cached "$model"; then
    echo "!!! 여유공간 부족 (${avail}GB) 하고 캐시도 없음. $model 건너뜀."
    printf "%s\t-\tSKIP_DISK\t-\t-\n" "$model" >> "$SUMMARY"
    continue
  fi

  env=$(env_of "$model")
  if [ -z "$env" ]; then
    echo "!!! configs/models/$model.yaml 에 env 필드 없음. 건너뜀."
    printf "%s\t-\tSKIP_NOENV\t-\t-\n" "$model" >> "$SUMMARY"
    continue
  fi

  if has_done_pilot "$model" "shared"; then
    echo "--- $model × shared: 이미 done — 스킵"
    printf "%s\tshared\tSKIP_DONE\t-\t-\n" "$model" >> "$SUMMARY"
  else
    run_one "$model" "shared" ""
  fi

  if has_done_pilot "$model" "dialect"; then
    echo "--- $model × dialect: 이미 done — 스킵"
    printf "%s\tdialect\tSKIP_DONE\t-\t-\n" "$model" >> "$SUMMARY"
  else
    run_one "$model" "dialect" "--dialect edu-${model}-v2"
  fi

  cleanup_model "$model"
done

echo
echo "=== summary ==="
column -t -s $'\t' "$SUMMARY"
echo
echo "로그: $LOG_DIR/"
echo "그리드: python scripts/build_pilot_grid.py --exp educational-flat-v2-complex --out image-prompts/pilot-complex3-report.md"

status=ok
grep -q -E $'\t(FAIL|SKIP_DISK)\t' "$SUMMARY" && status=fail
python "$(dirname "$0")/alert.py" --task "$TASK" --status "$status" --log "$SUMMARY"
