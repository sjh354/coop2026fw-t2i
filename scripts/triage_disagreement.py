"""compare_judge_spec.py가 찾은 불일치 건을 사람이 분류할 수 있게 CSV로 뽑는다.
각 행은 (image, item_id) 하나. classification 컬럼은 비워서 내보내며,
사람이 A(judge 지각 오류)/B(spec 문구 모호)/C(사람 채점 오류) 중 하나로 채운다.

    python -m scripts.triage_disagreement \
        --auto bench/scores/v243_pixart-sigma-lecture24/judge_spec_pilot.csv \
        --manual bench/scores/v243_pixart-sigma-lecture24/judge_spec_manual.csv \
        --spec configs/benchmarks/vlm-prompts-spec.json \
        --out bench/scores/v243_pixart-sigma-lecture24/triage.csv
"""
import argparse
import csv
import json
import pathlib

ROOT = pathlib.Path(__file__).parent.parent


def load_verdicts(path):
    with open(path, newline="", encoding="utf-8") as f:
        return {(row["image"], row["item_id"]): row for row in csv.DictReader(f)}


def load_checks(spec_path):
    entries = json.loads(pathlib.Path(spec_path).read_text(encoding="utf-8"))
    checks = {}
    for entry in entries:
        for item in entry["spec_items"]:
            checks[(entry["id"], item["id"])] = item["check"]
    return checks


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--auto", required=True)
    ap.add_argument("--manual", required=True)
    ap.add_argument("--spec", default=str(ROOT / "configs" / "benchmarks" / "vlm-prompts-spec.json"))
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    auto = load_verdicts(args.auto)
    manual = load_verdicts(args.manual)
    checks = load_checks(args.spec)

    keys = sorted(k for k in set(auto) & set(manual) if auto[k]["verdict"] != manual[k]["verdict"])
    rows = []
    for image, item_id in keys:
        a, m = auto[(image, item_id)], manual[(image, item_id)]
        rows.append({
            "image": image, "prompt_id": a["prompt_id"], "item_id": item_id,
            "type": a["type"], "check": checks.get((a["prompt_id"], item_id), ""),
            "auto_verdict": a["verdict"], "manual_verdict": m["verdict"],
            "classification": "",
        })

    out_path = pathlib.Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "image", "prompt_id", "item_id", "type", "check",
            "auto_verdict", "manual_verdict", "classification",
        ])
        writer.writeheader()
        writer.writerows(rows)
    print(f"불일치 {len(rows)}건 -> {out_path}")


if __name__ == "__main__":
    main()
