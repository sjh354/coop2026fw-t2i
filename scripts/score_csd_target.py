"""수업용 lecture24 벤치 전용 CSD 채점 — 카테고리당 정식 ref_set(15~25장) 대신
refs/vlm-target/의 단일 참조 이미지(그 카테고리 프롬프트를 뽑아낸 원본) 하나와
비교한다. src/scoring.py의 --components csd(검증된 ref_set 전제)와는 별개 경로라
CLI를 건드리지 않고 별도 스크립트로 뺐다.

n=1이라 스타일 분포 매칭이 아니라 "그 한 장과 얼마나 닮았는가"에 가까운 약한 신호다
— 참고용. 결과 컬럼명은 기존 csd(ref_set 평균)와 헷갈리지 않게 csd_target으로 둔다.

    conda run -n t2i-score python -m scripts.score_csd_target \
        --dir image-prompts/v243_pixart-sigma-lecture24/images \
        --out bench/scores/v243_pixart-sigma-lecture24/csd_target.csv
"""
import argparse
import csv
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
from src.scoring import load_csd_model, csd_style_embedding  # noqa: E402

REFS_DIR = ROOT / "refs" / "vlm-target"

# 파일명이 카테고리 type과 문자 그대로 일치하지 않는 2건 — 이미지 내용을 직접 봐서
# 확정한 매핑(vlm-prompts.json 채우던 세션에서 결정).
FILENAME_OVERRIDE = {
    "Data Visualization Chart": "Data Visualization Worksheet.png",
    "Historical Figure Portrait": "Educational Infographic.png",
}


def type_to_slug(t):
    return re.sub(r"[^a-z0-9]+", "_", t.lower()).strip("_")


def ref_path_for_type(cat_type):
    fname = FILENAME_OVERRIDE.get(cat_type, f"{cat_type}.png")
    path = REFS_DIR / fname
    if not path.exists():
        raise FileNotFoundError(f"참조 이미지 없음: {path}")
    return path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True, help="채점할 PNG 디렉토리 (image-prompts/vNNN_model/images)")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    import json
    categories = json.loads((ROOT / "configs" / "benchmarks" / "vlm-prompts.json").read_text())
    slug_to_type = {type_to_slug(c["type"]): c["type"] for c in categories}

    model = load_csd_model()
    ref_cache = {}

    paths = sorted(pathlib.Path(args.dir).glob("*.png"))
    rows = []
    for p in paths:
        m = re.match(r"v\d+_\d+_(.+)_(claude|chatgpt|qwen)\.png", p.name)
        if not m:
            print(f"[skip] 파일명 패턴 불일치: {p.name}")
            continue
        slug, source = m.group(1), m.group(2)
        cat_type = slug_to_type[slug]

        if cat_type not in ref_cache:
            ref_cache[cat_type] = csd_style_embedding(model, ref_path_for_type(cat_type))
        ref_emb = ref_cache[cat_type]

        img_emb = csd_style_embedding(model, p)
        sim = round(max(float((img_emb @ ref_emb.T).item()), 0.0), 4)
        rows.append({"image": p.name, "type": cat_type, "source": source, "csd_target": sim})
        print(f"{p.name} -> csd_target={sim}")

    out_path = pathlib.Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["image", "type", "source", "csd_target"])
        writer.writeheader()
        writer.writerows(rows)
    print(f"{len(rows)}장 -> {out_path}")


if __name__ == "__main__":
    main()
