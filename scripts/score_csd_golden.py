"""lecture24 벤치 CSD 채점 — score_csd_target.py(카테고리당 참조 1장, provisional)를
대체할 정식 경로. 카테고리당 검증된 golden set(refs/lecture24/<slug>/, 15~24장,
scripts/validate_ref_set.py로 검증된 configs/ref_sets/<slug>.yaml)과 비교해
src/scoring.py의 _csd(ref_set 평균 유사도)와 동일한 정의로 채점한다.

결과 컬럼명은 csd_target/csd(bench_v1 프리셋용)와 헷갈리지 않게 csd_golden으로 둔다.

    conda run -n t2i-score python -m scripts.score_csd_golden \
        --dir image-prompts/v243_pixart-sigma-lecture24/images \
        --out bench/scores/v243_pixart-sigma-lecture24/csd_golden.csv
"""
import argparse
import csv
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
from src.scoring import _csd, csd_style_embedding, load_csd_model  # noqa: E402

REF_SETS_DIR = ROOT / "configs" / "ref_sets"
REFS_DIR = ROOT / "refs" / "lecture24"

# vlm-prompts.json의 type 값 -> refs/lecture24/ 아래 골든셋 폴더 슬러그.
TYPE_TO_PRESET = {
    "Data Visualization Chart": "data-viz-chart",
    "Geometric Shape Set": "geometric-shape-set",
    "Historical Figure Portrait": "historical-figure-portrait",
    "Intergenerational Indoor Scene": "intergenerational-indoor",
    "Labeled Science Diagram": "labeled-science-diagram",
    "Multi-Character Classroom Collaboration": "multi-character-collab",
    "Single-Character Cutout": "single-character-cutout",
    "Structured Worksheet Template": "structured-worksheet",
}


def type_to_slug(t):
    return re.sub(r"[^a-z0-9]+", "_", t.lower()).strip("_")


def load_ref_manifest(preset):
    import yaml
    path = REF_SETS_DIR / f"{preset}.yaml"
    manifest = yaml.safe_load(path.read_text(encoding="utf-8"))
    if manifest["status"] not in ("validated", "provisional"):
        raise ValueError(f"{path}: status={manifest['status']} — validate_ref_set.py로 먼저 검증할 것.")
    return [img["path"] for img in manifest["images"]]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True, help="채점할 PNG 디렉토리")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    import json
    categories = json.loads((ROOT / "configs" / "benchmarks" / "vlm-prompts.json").read_text())
    slug_to_type = {type_to_slug(c["type"]): c["type"] for c in categories}

    load_csd_model()  # 캐시 워밍업, ref_set 임베딩은 _csd 내부에서 계산
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
        preset = TYPE_TO_PRESET[cat_type]

        if preset not in ref_cache:
            ref_cache[preset] = load_ref_manifest(preset)
        ref_set = ref_cache[preset]

        sim = _csd(p, ref_set)
        rows.append({"image": p.name, "type": cat_type, "source": source, "csd_golden": sim})
        print(f"{p.name} -> csd_golden={sim}")

    out_path = pathlib.Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["image", "type", "source", "csd_golden"])
        writer.writeheader()
        writer.writerows(rows)
    print(f"{len(rows)}장 -> {out_path}")


if __name__ == "__main__":
    main()
