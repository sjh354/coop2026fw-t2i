"""원자적 spec-item 기반 VLM judge — configs/benchmarks/vlm-prompts-spec.json의
항목당 6~12개 yes/no spec item을 이미지별로 하나씩 독립 질문해 채점한다.

기존 judge_lecture24.py의 4축 pass/fail은 천장 효과(한 모델이 3축 전부 100%)로
변별력이 없어서, "통과한 spec item 수 / 전체 item 수"라는 연속값으로 대체한다.
judge_lecture24.py는 그대로 남겨두고 이 스크립트는 별도로 돌린다.

    conda run -n t2i-judge python -m scripts.judge_spec \
        --images image-prompts/v243_pixart-sigma-lecture24/images \
        --spec configs/benchmarks/vlm-prompts-spec.json \
        --out bench/scores/v243_pixart-sigma-lecture24/judge_spec.csv
"""
import argparse
import csv
import json
import pathlib
import random
import re
import sys

ROOT = pathlib.Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
from scripts.judge import _call_judge_vlm  # noqa: E402

PROMPTS_JSON = ROOT / "configs" / "benchmarks" / "vlm-prompts.json"
SOURCE_SLUG = {"claude": "claude", "chatgpt": "chatgpt", "qwen2.5-vl-7b-instruct": "qwen"}
FILENAME_RE = re.compile(r"v\d+_\d+_(.+)_(claude|chatgpt|qwen)\.png")


def _slug(text):
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")

JUDGE_SYSTEM = (
    "너는 이미지가 주어진 조건을 만족하는지 판정하는 심사위원이다. "
    "조건 하나만 보고 이미지에서 그 조건이 실제로 관찰되는지 판단해라. "
    "판단이 애매하면 unclear로 답해라. "
    "다른 설명 없이 JSON 객체 하나만 출력해라: "
    '{"verdict": "yes"|"no"|"unclear"}'
)


def _expected_ids():
    categories = json.loads(PROMPTS_JSON.read_text(encoding="utf-8"))
    return {f"{_slug(cat['type'])}_{SOURCE_SLUG[source]}"
            for cat in categories for source in SOURCE_SLUG if cat.get(source)}


def load_spec(spec_path):
    entries = json.loads(pathlib.Path(spec_path).read_text(encoding="utf-8"))
    by_id = {}
    for entry in entries:
        if not entry.get("spec_items"):
            sys.exit(f"[중단] spec item이 없는 프롬프트: {entry['id']}")
        by_id[entry["id"]] = entry

    missing = _expected_ids() - set(by_id)
    if missing:
        sys.exit(f"[중단] vlm-prompts.json에는 있지만 spec에 없는 프롬프트: {sorted(missing)}")
    return by_id


def _parse_verdict(raw):
    start, end = raw.find("{"), raw.rfind("}")
    if start == -1 or end == -1:
        raise ValueError(f"JSON 객체를 찾을 수 없음: {raw[:200]!r}")
    parsed = json.loads(raw[start:end + 1])
    verdict = parsed.get("verdict")
    if verdict not in ("yes", "no", "unclear"):
        raise ValueError(f"verdict 값이 yes/no/unclear가 아님: {parsed}")
    return verdict


def _judge_spec_item(image_path, check_text, stats):
    user_text = f"조건: {check_text}"
    raw = _call_judge_vlm(image_path, user_text, system=JUDGE_SYSTEM)
    try:
        return _parse_verdict(raw)
    except (ValueError, json.JSONDecodeError, KeyError):
        stats["parse_errors"] += 1
        return "unclear"


def judge_images(images_dir, spec_by_id, limit=None):
    images_dir = pathlib.Path(images_dir)
    rows = []
    stats = {"parse_errors": 0}
    images = sorted(images_dir.glob("*.png"))
    if limit:
        images = images[:limit]
    for img_path in images:
        m = FILENAME_RE.match(img_path.name)
        if not m:
            print(f"[skip] 파일명 패턴 불일치: {img_path.name}")
            continue
        cat_slug, source = m.group(1), m.group(2)
        spec_id = f"{cat_slug}_{source}"
        entry = spec_by_id.get(spec_id)
        if entry is None:
            print(f"[skip] spec 항목을 찾을 수 없음: {spec_id}")
            continue

        items = list(entry["spec_items"])
        random.shuffle(items)
        passed = 0
        for item in items:
            verdict = _judge_spec_item(img_path, item["check"], stats)
            if verdict == "yes":
                passed += 1
            rows.append({
                "image": img_path.name, "prompt_id": spec_id,
                "item_id": item["id"], "type": item["type"], "verdict": verdict,
            })
        score = passed / len(items)
        print(f"{img_path.name} -> {passed}/{len(items)} ({score:.2f})")
    if stats["parse_errors"]:
        print(f"[warn] 파싱 실패로 unclear 처리된 응답 {stats['parse_errors']}건")
    return rows


def write_csv(rows, out_path):
    out_path = pathlib.Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["image", "prompt_id", "item_id", "type", "verdict"])
        writer.writeheader()
        writer.writerows(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--images", required=True, help="PNG 이미지가 있는 디렉토리")
    ap.add_argument("--spec", default=str(ROOT / "configs" / "benchmarks" / "vlm-prompts-spec.json"))
    ap.add_argument("--out", required=True, help="결과 CSV 경로")
    ap.add_argument("--limit", type=int, help="채점할 이미지 수 제한 (파일럿용, 예: 3)")
    args = ap.parse_args()

    spec_by_id = load_spec(args.spec)
    rows = judge_images(args.images, spec_by_id, limit=args.limit)
    if rows:
        write_csv(rows, args.out)
        print(f"{len(rows)}행 -> {args.out}")


if __name__ == "__main__":
    main()
