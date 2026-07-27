#!/usr/bin/env bash
# TASK-D: VRAM/latency 실측. 서버 157(camp-16, env t2i)에서 실행.
#
# 1) 확정 후보 3개(lumina2, pixart-sigma, flux2-klein-4b-nf4) 기본 실측
# 2) FLUX.2-klein-4b 세 조건 비교 (nf4 / bf16 distilled / base 미증류) —
#    현재 11.39s/img가 NF4 dequant 오버헤드 때문인지, base 체크포인트를
#    쓰고 있어서인지 갈라내기 위함. 세 조건 모두 --seed 42로 고정해
#    같은 인덱스의 이미지를 나란히 비교할 수 있다.
#
# 결과: bench/cost/vram_latency.csv (모델별 한 줄씩 append)
#       bench/cost_images/<model>/ (조건별 육안 비교용 이미지)

set -u

ENV=t2i
TASK="bench_cost_candidates.sh"
PROMPTS=configs/keywords/basic30.yaml
OUT_CSV=bench/cost/vram_latency.csv
LOG_DIR="logs/$(date +%Y%m%d_%H%M%S)_bench_cost"
mkdir -p "$LOG_DIR"

# flux2-klein-4b-nf4/flux2-klein-4b는 이미 캐시된 FLUX.2-klein-4B 가중치를 공유해서
# 먼저 돌리고, flux2-klein-4b-base/lumina2/pixart-sigma는 새로 다운로드가 필요해 뒤에 둔다.
MODELS=(
  flux2-klein-4b-nf4
  flux2-klein-4b
  flux2-klein-4b-base
  lumina2
  pixart-sigma
)

# 모델별 다운로드 필요 여부를 repo 기준 카운트해서, 같은 repo를 쓰는 모든 모델의
# 벤치가 끝난 뒤에만(더 이상 필요 없을 때) 디스크가 부족하면 그 repo 캐시를 지운다.
HF_HUB_DIR="$HOME/.cache/huggingface/hub"
DISK_THRESHOLD_GB=15
declare -A repo_remaining
for model in "${MODELS[@]}"; do
  repo=$(grep '^repo:' "configs/models/${model}.yaml" | awk '{print $2}')
  repo_remaining[$repo]=$(( ${repo_remaining[$repo]:-0} + 1 ))
done

free_gb() {
  df --output=avail -BG / | tail -1 | tr -dc '0-9'
}

cache_dir_for_repo() {
  local repo="$1"
  echo "${HF_HUB_DIR}/models--${repo//\//--}"
}

fail=0
for model in "${MODELS[@]}"; do
  log="$LOG_DIR/${model}.log"
  echo "=== $model -> $log"
  if conda run -n "$ENV" python -m scripts.bench_cost \
      --config "configs/models/${model}.yaml" \
      --prompts "$PROMPTS" \
      --out "$OUT_CSV" \
      --seed 42 > "$log" 2>&1; then
    echo "    OK"
    python "$(dirname "$0")/../alert.py" --task "$TASK" --status ok \
      --message "$(tail -3 "$log" | tr '\n' ' ' | cut -c1-500)"
  else
    echo "    FAIL — 로그: $log"
    fail=1
    python "$(dirname "$0")/../alert.py" --task "$TASK" --status fail \
      --message "${model} 실패: $(tail -5 "$log" | tr '\n' ' ' | cut -c1-300)"
  fi

  repo=$(grep '^repo:' "configs/models/${model}.yaml" | awk '{print $2}')
  repo_remaining[$repo]=$(( repo_remaining[$repo] - 1 ))
  if [ "${repo_remaining[$repo]}" -le 0 ]; then
    avail=$(free_gb)
    if [ -n "$avail" ] && [ "$avail" -lt "$DISK_THRESHOLD_GB" ]; then
      cdir=$(cache_dir_for_repo "$repo")
      if [ -d "$cdir" ]; then
        echo "    디스크 여유 ${avail}G < ${DISK_THRESHOLD_GB}G — ${repo} 캐시 삭제 (${cdir})"
        rm -rf "$cdir"
        python "$(dirname "$0")/../alert.py" --task "$TASK" --status ok \
          --message "디스크 확보: ${repo} 캐시 삭제 (삭제 전 여유 ${avail}G)"
      fi
    fi
  fi
done

echo
echo "결과: $OUT_CSV"
echo "로그: $LOG_DIR/"

if [ "$fail" -eq 0 ]; then
  python "$(dirname "$0")/../alert.py" --task "$TASK" --status ok --log "$OUT_CSV"
else
  python "$(dirname "$0")/../alert.py" --task "$TASK" --status fail \
    --message "일부 모델 실패 — 로그: $LOG_DIR/"
fi
