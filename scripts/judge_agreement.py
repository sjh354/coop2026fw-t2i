"""두 채점 CSV(사람 vs VLM, 또는 VLM A vs VLM B)를 비교해 Cohen's kappa/일치율을
전체 및 prompt_source(claude/chatgpt/qwen)별로 쪼개서 보고하고, 불일치 항목을
CSV로 남긴다. TASK-C(judge 신뢰성 검증)용 — 자기 계열 선호(self-enhancement bias)
확인이 핵심 질문이라 소스별 분리가 필수.

    python -m scripts.judge_agreement \
        --a bench/scores/v243_.../judge_spec_qwen.csv \
        --b bench/scores/v243_.../judge_spec_gemma3.csv \
        --out bench/scores/v243_.../judge_disagreement.csv
"""
import argparse
import csv
import pathlib

SOURCES = ("claude", "chatgpt", "qwen")


def load_verdicts(path):
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    return {(row["image"], row["item_id"]): row for row in rows}


def prompt_source(prompt_id):
    for source in SOURCES:
        if prompt_id.endswith(f"_{source}"):
            return source
    return "unknown"


def cohens_kappa(a, b, keys):
    n = len(keys)
    if n == 0:
        return None
    po = sum(1 for k in keys if a[k] == b[k]) / n
    categories = {a[k] for k in keys} | {b[k] for k in keys}
    pe = sum(
        (sum(1 for k in keys if a[k] == c) / n) * (sum(1 for k in keys if b[k] == c) / n)
        for c in categories
    )
    if pe == 1:
        return 1.0
    return (po - pe) / (1 - pe)


def report(label, a, b, keys):
    if not keys:
        print(f"  {label}: 공통 항목 없음")
        return
    n = len(keys)
    agree = sum(1 for k in keys if a[k] == b[k])
    rate = agree / n
    kappa = cohens_kappa(a, b, keys)
    flag = " [경고: 0.6 미만 — 이 judge 결과는 신뢰할 수 없음]" if kappa is not None and kappa < 0.6 else ""
    print(f"  {label}: n={n}, 일치율={rate:.2f}, kappa={kappa:.2f}{flag}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--a", required=True, help="채점 CSV A (사람 손 채점 또는 judge_spec.py 결과)")
    ap.add_argument("--b", required=True, help="채점 CSV B")
    ap.add_argument("--out", required=True, help="불일치 항목 CSV 출력 경로")
    args = ap.parse_args()

    a = load_verdicts(args.a)
    b = load_verdicts(args.b)
    keys = sorted(set(a) & set(b))
    if not keys:
        raise SystemExit("두 CSV에 공통되는 (image, item_id)가 없습니다.")

    print(f"전체 ({args.a} vs {args.b}):")
    report("전체", {k: a[k]["verdict"] for k in keys}, {k: b[k]["verdict"] for k in keys}, keys)

    print("prompt_source별:")
    for source in SOURCES:
        source_keys = [k for k in keys if prompt_source(a[k]["prompt_id"]) == source]
        report(source, {k: a[k]["verdict"] for k in source_keys}, {k: b[k]["verdict"] for k in source_keys}, source_keys)

    disagreements = [k for k in keys if a[k]["verdict"] != b[k]["verdict"]]
    out_path = pathlib.Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["image", "prompt_id", "item_id", "type", "verdict_a", "verdict_b"])
        writer.writeheader()
        for k in disagreements:
            writer.writerow({
                "image": k[0], "prompt_id": a[k]["prompt_id"], "item_id": k[1],
                "type": a[k]["type"], "verdict_a": a[k]["verdict"], "verdict_b": b[k]["verdict"],
            })
    print(f"불일치 {len(disagreements)}건 -> {out_path}")


if __name__ == "__main__":
    main()
