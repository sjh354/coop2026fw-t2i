"""STAGE 3 라벨링 대상 표본을 뽑는다. type(count/attribute/spatial/text/style)별로
최소 --per-axis 건을 채우도록, 이미 채점된 항목(--exclude CSV들)을 뺀 나머지 풀에서
모델(이미지 디렉토리)별로 고르게 섞어 뽑는다.

    python -m scripts.sample_stage3 \
        --images image-prompts/v243_pixart-sigma-lecture24/images \
                 image-prompts/v244_flux2-klein-4b-nf4-lecture24/images \
                 image-prompts/v245_qwen-image-lecture24/images \
        --exclude bench/scores/v243_pixart-sigma-lecture24/judge_spec_manual.csv \
        --per-axis 25 \
        --out bench/scores/stage3_worklist.csv
"""
import argparse
import csv
import pathlib
import random
import sys

ROOT = pathlib.Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
from scripts.judge_spec import FILENAME_RE, load_spec  # noqa: E402

TYPES = ["count", "attribute", "spatial", "text", "style"]


def _load_done(paths):
    done = set()
    for p in paths:
        p = pathlib.Path(p)
        if not p.exists():
            continue
        with p.open(newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                done.add((row["image"], row["item_id"]))
    return done


def _already_counts(paths):
    counts = {t: 0 for t in TYPES}
    for p in paths:
        p = pathlib.Path(p)
        if not p.exists():
            continue
        with p.open(newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                if row["type"] in counts:
                    counts[row["type"]] += 1
    return counts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--images", nargs="+", required=True, help="모델별 이미지 디렉토리 (여러 개)")
    ap.add_argument("--spec", default=str(ROOT / "configs" / "benchmarks" / "vlm-prompts-spec.json"))
    ap.add_argument("--exclude", nargs="*", default=[], help="이미 채점된 manual CSV들 (제외 대상)")
    ap.add_argument("--per-axis", type=int, default=25)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    spec_by_id = load_spec(args.spec)
    done = _load_done(args.exclude)
    already = _already_counts(args.exclude)

    # pool[type][model_dir] -> 후보 리스트. 모델별로 고르게 뽑기 위해 모델 단위로 버킷을 나눈다.
    pool = {t: {img_dir: [] for img_dir in args.images} for t in TYPES}
    for img_dir in args.images:
        img_dir_path = pathlib.Path(img_dir)
        for img_path in sorted(img_dir_path.glob("*.png")):
            m = FILENAME_RE.match(img_path.name)
            if not m:
                continue
            spec_id = f"{m.group(1)}_{m.group(2)}"
            entry = spec_by_id.get(spec_id)
            if entry is None:
                continue
            for item in entry["spec_items"]:
                if item["type"] not in pool:
                    continue
                if (img_path.name, item["id"]) in done:
                    continue
                pool[item["type"]][img_dir].append({
                    "image_path": str(img_path), "image": img_path.name,
                    "prompt_id": spec_id, "item_id": item["id"],
                    "type": item["type"], "check": item["check"],
                })

    rng = random.Random(args.seed)
    picked = []
    for t in TYPES:
        need = max(0, args.per_axis - already[t])
        buckets = list(pool[t].values())
        for b in buckets:
            rng.shuffle(b)
        chosen = []
        # 모델 버킷을 라운드로빈으로 순회해 모델별로 고르게 뽑는다.
        while len(chosen) < need and any(buckets):
            for b in buckets:
                if b and len(chosen) < need:
                    chosen.append(b.pop())
        picked.extend(chosen)
        available = sum(len(b) for b in pool[t].values()) + len(chosen)
        print(f"{t}: 기존 {already[t]}건, 추가 {len(chosen)}건 (필요 {need}건, 가용 {available}건)")

    out_path = pathlib.Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["image_path", "image", "prompt_id", "item_id", "type", "check"])
        writer.writeheader()
        writer.writerows(picked)
    print(f"\n총 {len(picked)}건 -> {out_path}")


if __name__ == "__main__":
    main()
