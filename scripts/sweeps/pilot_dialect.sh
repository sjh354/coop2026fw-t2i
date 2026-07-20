#!/usr/bin/env bash
# 방언(dialect) 효과 검증 파일럿 전용 러너. (.claude/plans/task-snoopy-star.md)
#
# 9개 모델(계열별 대표) 각각에 대해 shared(공용 educational-flat-pilot)와
# dialect(edu-<model>) 두 조건을 순차 생성한다. sweep*.sh의 has_done는
# model+experiment로만 키잉해서 shared/dialect가 서로 skip되므로 여기선 쓰지 않고,
# condition까지 포함한 자체 idempotency 체크(has_done_pilot)를 쓴다.
#
# 서버 디스크가 작아서 sweep*.sh의 "여유 없을 때만 지우기" 방식 대신, 모델 하나가
# shared+dialect 두 조건을 다 끝내면 여유 공간과 무관하게 그 모델 캐시를 즉시
# 삭제한다(cleanup_model). 캐시 재사용 이득은 포기하고 디스크 확보를 우선한다 —
# 재실행하면 그 모델은 처음부터 다시 다운로드된다.
#
# ideogram-4 safety filter block은 재시도 없이 기록만 하고 계속 진행한다.
# 주의: ideogram4는 raise_on_caption_issues=False라 block이 나도 exit 0으로
# 끝날 수 있다 — 아래 BLOCK 판정은 exit!=0 + 로그 문자열 매칭에 의존하므로
# block을 놓칠 수 있다. summary.tsv를 맹신하지 말고 ideogram-4 결과 이미지를
# 육안으로 확인해서 빈/차단된 프레임이 있는지 봐야 block rate가 정확하다.

set -u

MIN_FREE_GB=35          # 모델 하나(가장 큰 건 qwen-image/ideogram-4 ~30GB대)가 들어갈 최소 여유
LOG_DIR="logs/$(date +%Y%m%d_%H%M%S)_pilot_dialect"
HF_HUB="${HF_HOME:-$HOME/.cache/huggingface}/hub"
TASK="pilot_dialect.sh"
EXP="educational-flat-pilot"

MODELS=(
  sdxl
  flux2-klein-4b
  sana-1600m
  pixart-sigma
  sd35-medium
  zimage-turbo
  lumina2
  qwen-image
  ideogram-4
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

# model+experiment+condition(+status:done)이 모두 일치하는 노트가 있으면 스킵.
# shared/dialect가 서로를 skip하지 않도록 condition까지 체크.
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

# shared+dialect 두 조건이 다 끝난 모델의 캐시를 여유 공간과 무관하게 바로 지운다.
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

  # ideogram-4 safety filter block: 재시도 없이 BLOCK으로 기록 (로그에 block/safety 흔적이 있으면 구분)
  local status_word="FAIL"
  if [[ "$model" == "ideogram-4" ]] && grep -qiE 'block|safety|caption.?issue' "$log"; then
    status_word="BLOCK"
  fi
  printf "%s\t%s\t%s\t-\t-\n" "$model" "$condition" "$status_word" >> "$SUMMARY"
  echo "    $status_word — 로그: $log"
  echo "    $(tail -3 "$log" | tr '\n' ' ')"
  notify_attempt "$status_word" "$model" "$condition" "$(tail -3 "$log" | tr '\n' ' ' | cut -c1-200)"
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
    run_one "$model" "dialect" "--dialect edu-${model}"
  fi

  # 이 모델의 두 조건이 다 끝났으니(성공/실패/스킵 무관) 캐시를 바로 지운다.
  cleanup_model "$model"
done

echo
echo "=== summary ==="
column -t -s $'\t' "$SUMMARY"
echo
echo "로그: $LOG_DIR/"
echo "그리드: python scripts/build_pilot_grid.py"

status=ok
grep -q -E $'\t(FAIL|SKIP_DISK)\t' "$SUMMARY" && status=fail
python "$(dirname "$0")/alert.py" --task "$TASK" --status "$status" --log "$SUMMARY"
