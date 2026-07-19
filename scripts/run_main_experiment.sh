#!/usr/bin/env bash
# 본 실험: bench_v1(40개) × 후보 모델 × 검증된 스타일 프리셋 → 생성 + 채점 일괄 실행.
#
# 사전 조건 (이 스크립트는 확인만 하고 대신 해주지 않음):
#   1. python -m scripts.build_bench_v1_keywords 로 configs/keywords/bench_v1.yaml 생성 완료
#   2. MODELS 배열 — A트랙 결과로 확정한 후보 (기본값은 bench/results.md 결론 기준 3개)
#   3. configs/experiments/<preset>.yaml 중 status: validated 인 것만 자동으로 씀
#      (scripts/preset_smoke_test.sh 육안 확인 후 status 필드를 직접 바꿔둘 것)
#
#     bash scripts/run_main_experiment.sh
set -euo pipefail

# A트랙 결론(bench/results.md): lumina2(품질 최상)+pixart-sigma(속도)+flux2-klein-4b-nf4
# (16GB 진입용 NF4 조건) 3개 유지, 2모델 축소는 발동 안 함. 확정 후 여기만 수정.
MODELS=(lumina2 pixart-sigma flux2-klein-4b-nf4)

KEYWORDS=bench_v1
TASK="run_main_experiment.sh"
LOG_DIR="logs/$(date +%Y%m%d_%H%M%S)_main_experiment"
mkdir -p "$LOG_DIR"

if [ ! -f "configs/keywords/${KEYWORDS}.yaml" ]; then
  echo "!!! configs/keywords/${KEYWORDS}.yaml 없음. 먼저 실행:"
  echo "    python -m scripts.build_bench_v1_keywords"
  exit 1
fi

# status: validated인 프리셋만 수집 (pending-validation은 제외)
PRESETS=()
for f in configs/experiments/*.yaml; do
  name=$(basename "$f" .yaml)
  [[ "$name" == *-benchv1 ]] && continue  # 이 스크립트가 만든 파생 파일은 건너뜀
  grep -qE '^status:[[:space:]]*validated[[:space:]]*$' "$f" && PRESETS+=("$name")
done

if [ "${#PRESETS[@]}" -eq 0 ]; then
  echo "!!! status: validated 인 프리셋이 없음. scripts/preset_smoke_test.sh로 먼저 검증할 것."
  exit 1
fi
echo "검증된 프리셋: ${PRESETS[*]}"
echo "모델: ${MODELS[*]}"

# 프리셋별로 keywords만 bench_v1로 바꾼 파생 실험 yaml을 만든다 (원본은 건드리지 않음).
VDIRS=()
for preset in "${PRESETS[@]}"; do
  exp="${preset}-benchv1"
  sed "s/^keywords: .*/keywords: ${KEYWORDS}/" "configs/experiments/${preset}.yaml" \
    > "configs/experiments/${exp}.yaml"

  for model in "${MODELS[@]}"; do
    env=$(grep -E '^env:' "configs/models/${model}.yaml" | awk '{print $2}')
    log="$LOG_DIR/${model}__${preset}.log"
    echo "=== $model × $preset -> $log"
    if conda run -n "$env" python -m src.generate --model "$model" --exp "$exp" > "$log" 2>&1; then
      vdir=$(grep -o 'image-prompts/v[0-9_a-zA-Z-]*' "$log" | head -1)
      tail=$(grep -o 'vram_peak=[0-9.]*GB  sec/img=[0-9.]*' "$log" | tail -1)
      echo "    OK -> $vdir ($tail)"
      VDIRS+=("$vdir")
      python3 "$(dirname "$0")/alert.py" --task "$TASK" --status ok \
        --message "SUCCESS: ${model}/${preset} -> ${vdir} (${tail})"
    else
      echo "    FAIL — 로그: $log"
      python3 "$(dirname "$0")/alert.py" --task "$TASK" --status fail \
        --message "FAIL: ${model}/${preset} ($(tail -3 "$log" | tr '\n' ' ' | cut -c1-200))"
    fi
  done
done

echo
echo "=== 채점 단계 (t2i-score env) ==="
mkdir -p bench/scores
for vdir in "${VDIRS[@]}"; do
  version=$(basename "$vdir")
  out="bench/scores/${version}.csv"
  log="$LOG_DIR/score__${version}.log"
  if conda run -n t2i-score python -m src.scoring --dir "${vdir}/images" --out "$out" --vlm > "$log" 2>&1; then
    echo "    OK  $version -> $out"
    python3 "$(dirname "$0")/alert.py" --task "$TASK" --status ok \
      --message "SCORE OK: ${version} -> ${out}"
  else
    echo "    FAIL 채점 — 로그: $log"
    python3 "$(dirname "$0")/alert.py" --task "$TASK" --status fail \
      --message "SCORE FAIL: ${version} ($(tail -3 "$log" | tr '\n' ' ' | cut -c1-200))"
  fi
done

echo
echo "생성 로그: $LOG_DIR/"
echo "채점 결과: bench/scores/*.csv, *.md"
python3 "$(dirname "$0")/alert.py" --task "$TASK" --status ok --message "본 실험 완료 — 로그: $LOG_DIR, 채점: bench/scores/"
