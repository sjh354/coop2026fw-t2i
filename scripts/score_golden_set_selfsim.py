"""TASK-J: golden set 내부 self-similarity(상한)와 프리셋 간 불일치 CSD(하한)를 계산한다.

    conda run -n t2i-score python -m scripts.score_golden_set_selfsim \
        --dir refs/golden-set \
        --out bench/scores/golden_set_selfsim.csv
"""
import argparse
import csv
import itertools
import pathlib
import sys

ROOT = pathlib.Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
from src.scoring import load_csd_model, csd_style_embedding  # noqa: E402


def embed_all_images(model, golden_dir):
    embeddings = {}
    for preset_dir in sorted(golden_dir.iterdir()):
        if not preset_dir.is_dir():
            continue
        paths = sorted(p for p in preset_dir.iterdir() if p.suffix.lower() in (".png", ".jpg", ".jpeg"))
        embeddings[preset_dir.name] = [csd_style_embedding(model, p) for p in paths]
    return embeddings


def pairwise_sims(embs_a, embs_b, skip_self_pairs):
    sims = []
    for i, a in enumerate(embs_a):
        for j, b in enumerate(embs_b):
            if skip_self_pairs and i == j:
                continue
            if skip_self_pairs and j <= i:
                continue
            sims.append(float((a @ b.T).item()))
    return sims


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    model = load_csd_model()
    embeddings = embed_all_images(model, pathlib.Path(args.dir))

    rows = []
    presets = sorted(embeddings)
    for preset in presets:
        sims = pairwise_sims(embeddings[preset], embeddings[preset], skip_self_pairs=True)
        for sim in sims:
            rows.append({"kind": "within_preset", "preset_a": preset, "preset_b": preset, "csd": round(sim, 4)})

    for preset_a, preset_b in itertools.combinations(presets, 2):
        sims = pairwise_sims(embeddings[preset_a], embeddings[preset_b], skip_self_pairs=False)
        for sim in sims:
            rows.append({"kind": "cross_preset", "preset_a": preset_a, "preset_b": preset_b, "csd": round(sim, 4)})

    out_path = pathlib.Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["kind", "preset_a", "preset_b", "csd"])
        writer.writeheader()
        writer.writerows(rows)
    print(f"{len(rows)}쌍 -> {out_path}")


if __name__ == "__main__":
    main()
