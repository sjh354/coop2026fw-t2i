"""TASK-F 3~4번: qwen-image vs qwen-image-lightning VRAM/latency/quality 비교표를
Markdown으로 떨군다.

VRAM/latency는 bench/cost/vram_latency.csv(scripts/bench_cost.py 결과)에서 바로 읽는다.
quality(vqascore/csd_target)는 서버 23에서 채점하므로, 이 스크립트가 서버 157에서 먼저
돌 때는 아직 없을 수 있다 — 없으면 "채점 대기(서버 23)"로 표시하고, 채점 CSV 경로를
--v-full/--v-lightning으로 나중에 넘기면 그때 채워서 다시 생성한다.

    python -m scripts.build_taskf_report \
        --cost-csv bench/cost/vram_latency.csv \
        --v-full image-prompts/v255_qwen-image-lecture24 \
        --v-lightning image-prompts/v256_qwen-image-lightning-lecture24 \
        --out reports/task-f_qwen_lightning_comparison.md
"""
import argparse
import csv
import pathlib
import statistics
import sys

ROOT = pathlib.Path(__file__).parent.parent

MODELS = ["qwen-image", "qwen-image-lightning"]


def load_cost_rows(cost_csv):
    rows = {}
    if not pathlib.Path(cost_csv).exists():
        return rows
    with open(cost_csv, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row["model"] in MODELS:
                rows[row["model"]] = row  # 마지막 측정값으로 덮어씀
    return rows


def load_quality(score_dir):
    """bench/scores/<vdir_name>/pass1.csv(vqascore) + csd_target.csv 평균을 읽는다.
    디렉토리나 파일이 없으면 None을 돌려준다 — 아직 서버 23에서 채점 전이라는 뜻."""
    if score_dir is None:
        return None, None
    score_dir = pathlib.Path(score_dir)
    vqa_path = score_dir / "pass1.csv"
    csd_path = score_dir / "csd_target.csv"

    vqa_mean = None
    if vqa_path.exists():
        with vqa_path.open(newline="", encoding="utf-8") as f:
            vals = [float(r["vqascore"]) for r in csv.DictReader(f) if r.get("vqascore")]
        if vals:
            vqa_mean = round(statistics.mean(vals), 4)

    csd_mean = None
    if csd_path.exists():
        with csd_path.open(newline="", encoding="utf-8") as f:
            vals = [float(r["csd_target"]) for r in csv.DictReader(f) if r.get("csd_target")]
        if vals:
            csd_mean = round(statistics.mean(vals), 4)

    return vqa_mean, csd_mean


def fmt(v):
    return "채점 대기(서버 23)" if v is None else v


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cost-csv", default=str(ROOT / "bench" / "cost" / "vram_latency.csv"))
    ap.add_argument("--score-dir-full", default=None,
                     help="bench/scores/<v..._qwen-image-lecture24> (없으면 채점 대기로 표시)")
    ap.add_argument("--score-dir-lightning", default=None,
                     help="bench/scores/<v..._qwen-image-lightning-lecture24>")
    ap.add_argument("--out", default=str(ROOT / "reports" / "task-f_qwen_lightning_comparison.md"))
    args = ap.parse_args()

    cost = load_cost_rows(args.cost_csv)
    missing = [m for m in MODELS if m not in cost]
    if missing:
        print(f"[warn] bench_cost.py 결과 없음: {missing} — 해당 행은 비워둔다.", file=sys.stderr)

    vqa_full, csd_full = load_quality(args.score_dir_full)
    vqa_light, csd_light = load_quality(args.score_dir_lightning)

    lines = [
        "# TASK-F · qwen-image vs qwen-image-lightning quality/latency/VRAM 비교",
        "",
        "생성: 서버 157 (`scripts/sweeps/task_f_qwen_pipeline.sh`). "
        "quality(vqascore/csd_target)는 서버 23 채점 완료 후 --score-dir-full/--score-dir-lightning "
        "인자로 재실행해야 채워진다.",
        "",
        "| 항목 | qwen-image (full) | qwen-image-lightning |",
        "|---|---|---|",
    ]

    def row(label, key):
        full = cost.get("qwen-image", {}).get(key, "-")
        light = cost.get("qwen-image-lightning", {}).get(key, "-")
        lines.append(f"| {label} | {full} | {light} |")

    row("dtype/quantization", "quantization")
    lines[-1] = (f"| dtype/quantization | "
                 f"{cost.get('qwen-image', {}).get('dtype', '-')}/{cost.get('qwen-image', {}).get('quantization', '-')} | "
                 f"{cost.get('qwen-image-lightning', {}).get('dtype', '-')}/{cost.get('qwen-image-lightning', {}).get('quantization', '-')} |")
    row("steps", "num_inference_steps")
    row("peak VRAM (torch) GB", "peak_vram_gb_torch")
    row("peak VRAM (nvidia-smi) GB", "peak_vram_gb_smi")
    row("latency p50 (s)", "latency_p50_s")
    row("latency p90 (s)", "latency_p90_s")
    lines.append(f"| vqascore (mean, 24 prompts) | {fmt(vqa_full)} | {fmt(vqa_light)} |")
    lines.append(f"| csd_target (mean, 24 prompts) | {fmt(csd_full)} | {fmt(csd_light)} |")

    out_path = pathlib.Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"done. {out_path}")


if __name__ == "__main__":
    main()
