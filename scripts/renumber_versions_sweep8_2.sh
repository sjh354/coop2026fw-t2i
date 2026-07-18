#!/bin/bash
# 2026s-cuop-2 (sweep8_2)에서 실행: v151~v158 -> v164~v171 재명명
set -euo pipefail
cd ~/t2i

declare -A MAP=(
  [151]=164
  [152]=165
  [153]=166
  [154]=167
  [155]=168
  [156]=169
  [157]=170
  [158]=171
)

for old in "${!MAP[@]}"; do
  new=${MAP[$old]}
  old_v=$(printf "v%03d" "$old")
  new_v=$(printf "v%03d" "$new")

  src_dir=$(ls -d image-prompts/${old_v}_* 2>/dev/null || true)
  if [ -z "$src_dir" ]; then
    echo "skip: $old_v not found"
    continue
  fi

  model_suffix=${src_dir#image-prompts/${old_v}_}
  new_dir="image-prompts/${new_v}_${model_suffix}"

  echo "$src_dir -> $new_dir"
  mv "$src_dir" "$new_dir"

  # md 파일 이름 변경 + 내부 문자열(old_v -> new_v) 치환
  md_old="$new_dir/${old_v}_${model_suffix}.md"
  md_new="$new_dir/${new_v}_${model_suffix}.md"
  if [ -f "$md_old" ]; then
    mv "$md_old" "$md_new"
    sed -i "s/${old_v}/${new_v}/g" "$md_new"
  fi

  # 이미지 파일명 변경 (vNNN_00_xxx.png 형태)
  if [ -d "$new_dir/images" ]; then
    for img in "$new_dir"/images/${old_v}_*; do
      [ -e "$img" ] || continue
      base=$(basename "$img")
      mv "$img" "$new_dir/images/${base/${old_v}/${new_v}}"
    done
  fi
done

echo "done. git status로 확인:"
git status
