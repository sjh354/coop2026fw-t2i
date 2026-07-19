#!/usr/bin/env bash
# C트랙 R9 스모크 테스트 (bench/style-presets-v2.md 참고).
# pending-validation 프리셋 4개를 lumina2 + r9-smoke3(3키워드: apple/cat/book)로
# 생성한다. "book" 키워드는 1라운드에서 실제로 누출됐던 오브젝트라 일부러 포함.
#
# 이 스크립트는 leakage 여부를 판정하지 않는다 — 생성된 이미지 3장씩을 육안으로
# 보고, 스타일 문구의 명사(예: storybook)가 화면에 실제 객체로 등장하는지 확인할 것.
# 통과로 보이면 해당 configs/experiments/<preset>.yaml의
# `status: pending-validation` 줄을 `status: validated`로 직접 수정한다
# (이 스크립트는 자동으로 바꾸지 않음 — 육안 판단이 필요한 단계라서).
#
#     bash scripts/preset_smoke_test.sh
set -euo pipefail

MODEL=lumina2
KEYWORDS=r9-smoke3
PRESETS=(edu-flat-v2 observational playful-soft storybook-scene)
TASK="preset_smoke_test.sh"
LOG_DIR="logs/$(date +%Y%m%d_%H%M%S)_preset_smoke"
SCRATCH_DIR="/tmp/t2i-preset-smoke-scratch"
mkdir -p "$LOG_DIR" "$SCRATCH_DIR"

env=$(grep -E '^env:' "configs/models/${MODEL}.yaml" | awk '{print $2}')

status=ok
for preset in "${PRESETS[@]}"; do
  tmp_exp="${preset}-r9smoke"
  sed "s/^keywords: .*/keywords: ${KEYWORDS}/" "configs/experiments/${preset}.yaml" \
    > "configs/experiments/${tmp_exp}.yaml"

  log="$LOG_DIR/${preset}.log"
  echo "=== $preset -> $log"
  if conda run -n "$env" python -m src.generate --model "$MODEL" --exp "$tmp_exp" > "$log" 2>&1; then
    vdir=$(grep -o 'image-prompts/v[0-9_a-zA-Z-]*' "$log" | head -1)
    echo "    OK -> ${vdir}/images/ 육안 확인할 것"
    python3 "$(dirname "$0")/alert.py" --task "$TASK" --status ok \
      --message "SUCCESS: ${preset} smoke -> ${vdir}"
  else
    status=fail
    echo "    FAIL — 로그: $log"
    python3 "$(dirname "$0")/alert.py" --task "$TASK" --status fail \
      --message "FAIL: ${preset} smoke ($(tail -3 "$log" | tr '\n' ' ' | cut -c1-200))"
  fi
  # rm 대신 scratch로 옮김 (실수로 커밋되는 것 방지, 삭제는 나중에 수동으로)
  mv "configs/experiments/${tmp_exp}.yaml" "$SCRATCH_DIR/${tmp_exp}.yaml"
done

echo
echo "각 preset 이미지 3장씩(an apple / a cat / a book) 육안 확인할 것 —"
echo "특히 'a book' 결과에서 스타일 문구 명사가 오브젝트로 새는지 집중 확인."
echo "통과 시 configs/experiments/<preset>.yaml status: pending-validation -> validated로 수동 변경."
python3 "$(dirname "$0")/alert.py" --task "$TASK" --status "$status" --log "$LOG_DIR"
