"""judge_spec.py와 같은 spec으로 사람이 터미널에서 y/n을 입력해 손 채점 CSV를 만든다.
30장 안팎을 채점하는 용도의 최소 도구 — judge_spec.py 결과와의 일치율 검증에 쓴다.

    python -m scripts.judge_spec_manual \
        --images image-prompts/v243_pixart-sigma-lecture24/images \
        --spec configs/benchmarks/vlm-prompts-spec.json \
        --out bench/scores/v243_pixart-sigma-lecture24/judge_spec_manual.csv \
        --limit 3

STAGE 3처럼 여러 모델 디렉토리를 섞어 층화 표본만 채점할 때는 scripts/sample_stage3.py로
worklist CSV를 먼저 만들고 --worklist로 넘긴다:

    python -m scripts.judge_spec_manual \
        --worklist bench/scores/stage3_worklist.csv \
        --out bench/scores/stage3_manual.csv

--out에 이미 채점된 (image, item_id)가 있으면 건너뛰고 이어서 추가한다(중복 채점 방지, resume).
"""
import argparse
import csv
import pathlib
import sys

from PIL import Image

ROOT = pathlib.Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
from scripts.judge_spec import FILENAME_RE, load_spec  # noqa: E402

FIELDNAMES = ["image", "prompt_id", "item_id", "type", "verdict"]


def _load_done(out_path):
    if not out_path.exists():
        return set()
    with out_path.open(newline="", encoding="utf-8") as f:
        return {(row["image"], row["item_id"]) for row in csv.DictReader(f)}


def _ask(check_text):
    while True:
        answer = input(f"  {check_text}  [y/n/u]? ").strip().lower()
        if answer in ("y", "n", "u"):
            return {"y": "yes", "n": "no", "u": "unclear"}[answer]
        print("  y, n, u 중 하나를 입력하세요.")


def _iter_worklist(worklist_path, done):
    by_image = {}
    with open(worklist_path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if (row["image"], row["item_id"]) in done:
                continue
            by_image.setdefault((row["image_path"], row["image"]), []).append(row)
    for (img_path, img_name), items in by_image.items():
        yield pathlib.Path(img_path), img_name, [
            {"id": r["item_id"], "type": r["type"], "check": r["check"], "prompt_id": r["prompt_id"]}
            for r in items
        ]


def _iter_directory(images_dir, spec_path, limit, done):
    spec_by_id = load_spec(spec_path)
    images = sorted(pathlib.Path(images_dir).glob("*.png"))
    if limit:
        images = images[:limit]
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
        items = [item for item in entry["spec_items"] if (img_path.name, item["id"]) not in done]
        items = [{**item, "prompt_id": spec_id} for item in items]
        yield img_path, img_path.name, items


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--images", help="PNG 이미지가 있는 디렉토리 (단일 모델)")
    ap.add_argument("--spec", default=str(ROOT / "configs" / "benchmarks" / "vlm-prompts-spec.json"))
    ap.add_argument("--worklist", help="scripts/sample_stage3.py가 만든 표본 CSV (여러 모델 혼합)")
    ap.add_argument("--out", required=True, help="결과 CSV 경로 (이미 있으면 이어서 추가)")
    ap.add_argument("--limit", type=int, help="채점할 이미지 수 제한 (예: 3, --images 전용)")
    args = ap.parse_args()

    if not args.images and not args.worklist:
        sys.exit("--images 또는 --worklist 중 하나는 필요합니다.")

    out_path = pathlib.Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    done = _load_done(out_path)

    if args.worklist:
        source = _iter_worklist(args.worklist, done)
    else:
        source = _iter_directory(args.images, args.spec, args.limit, done)

    is_new = not out_path.exists()
    with out_path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        if is_new:
            writer.writeheader()
        n_written = 0
        for img_path, img_name, items in source:
            if not items:
                continue
            Image.open(img_path).show()
            print(f"\n=== {img_name} ===")
            for item in items:
                verdict = _ask(item["check"])
                writer.writerow({
                    "image": img_name, "prompt_id": item["prompt_id"],
                    "item_id": item["id"], "type": item["type"], "verdict": verdict,
                })
                f.flush()
                n_written += 1
    print(f"\n{n_written}행 추가 -> {out_path}")


if __name__ == "__main__":
    main()
