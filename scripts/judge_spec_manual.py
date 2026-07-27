"""judge_spec.py와 같은 spec으로 사람이 터미널에서 y/n을 입력해 손 채점 CSV를 만든다.
30장 안팎을 채점하는 용도의 최소 도구 — judge_spec.py 결과와의 일치율 검증에 쓴다.

    python -m scripts.judge_spec_manual \
        --images image-prompts/v243_pixart-sigma-lecture24/images \
        --spec configs/benchmarks/vlm-prompts-spec.json \
        --out bench/scores/v243_pixart-sigma-lecture24/judge_spec_manual.csv \
        --limit 3
"""
import argparse
import csv
import pathlib
import sys

from PIL import Image

ROOT = pathlib.Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
from scripts.judge_spec import FILENAME_RE, load_spec  # noqa: E402


def _ask(check_text):
    while True:
        answer = input(f"  {check_text}  [y/n/u]? ").strip().lower()
        if answer in ("y", "n", "u"):
            return {"y": "yes", "n": "no", "u": "unclear"}[answer]
        print("  y, n, u 중 하나를 입력하세요.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--images", required=True, help="PNG 이미지가 있는 디렉토리")
    ap.add_argument("--spec", default=str(ROOT / "configs" / "benchmarks" / "vlm-prompts-spec.json"))
    ap.add_argument("--out", required=True, help="결과 CSV 경로")
    ap.add_argument("--limit", type=int, help="채점할 이미지 수 제한 (예: 3)")
    args = ap.parse_args()

    spec_by_id = load_spec(args.spec)
    images = sorted(pathlib.Path(args.images).glob("*.png"))
    if args.limit:
        images = images[:args.limit]

    out_path = pathlib.Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    for img_path in images:
        m = FILENAME_RE.match(img_path.name)
        if not m:
            print(f"[skip] 파일명 패턴 불일치: {img_path.name}")
            continue
        spec_id = f"{m.group(1)}_{m.group(2)}"
        entry = spec_by_id.get(spec_id)
        if entry is None:
            print(f"[skip] spec 항목을 찾을 수 없음: {spec_id}")
            continue

        Image.open(img_path).show()
        print(f"\n=== {img_path.name} ===")
        for item in entry["spec_items"]:
            verdict = _ask(item["check"])
            rows.append({
                "image": img_path.name, "prompt_id": spec_id,
                "item_id": item["id"], "type": item["type"], "verdict": verdict,
            })

    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["image", "prompt_id", "item_id", "type", "verdict"])
        writer.writeheader()
        writer.writerows(rows)
    print(f"\n{len(rows)}행 -> {out_path}")


if __name__ == "__main__":
    main()
