"""judge_spec.py(자동)와 judge_spec_manual.py(손 채점) 결과를 (image, item_id) 기준으로
맞춰 일치율을 계산한다. 파일럿 검증용 — 일치율이 0.8 미만이면 경고를 출력한다.

    python -m scripts.compare_judge_spec --auto bench/scores/.../judge_spec.csv \
        --manual bench/scores/.../judge_spec_manual.csv
"""
import argparse
import csv
import pathlib


def load_verdicts(path):
    with open(path, newline="", encoding="utf-8") as f:
        return {(row["image"], row["item_id"]): row["verdict"] for row in csv.DictReader(f)}


def cohens_kappa(auto, manual, keys):
    n = len(keys)
    po = sum(1 for k in keys if auto[k] == manual[k]) / n
    categories = {auto[k] for k in keys} | {manual[k] for k in keys}
    pe = sum(
        (sum(1 for k in keys if auto[k] == c) / n) * (sum(1 for k in keys if manual[k] == c) / n)
        for c in categories
    )
    if pe == 1:
        return 1.0
    return (po - pe) / (1 - pe)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--auto", required=True, help="judge_spec.py가 만든 CSV")
    ap.add_argument("--manual", required=True, help="judge_spec_manual.py가 만든 CSV")
    args = ap.parse_args()

    auto = load_verdicts(args.auto)
    manual = load_verdicts(args.manual)
    keys = sorted(set(auto) & set(manual))
    if not keys:
        raise SystemExit("두 CSV에 공통되는 (image, item_id)가 없습니다.")

    agree = sum(1 for k in keys if auto[k] == manual[k])
    rate = agree / len(keys)
    kappa = cohens_kappa(auto, manual, keys)
    print(f"비교 대상: {len(keys)}건, 일치: {agree}건, 일치율: {rate:.2f}, Cohen's kappa: {kappa:.2f}")
    if rate < 0.8:
        print(f"[경고] 일치율이 0.8 미만입니다 ({rate:.2f}) — spec item 문구나 judge 프롬프트를 재검토하세요.")

    lenient = sum(1 for k in keys if auto[k] != manual[k] and auto[k] == "yes" and manual[k] == "no")
    strict = sum(1 for k in keys if auto[k] != manual[k] and auto[k] == "no" and manual[k] == "yes")
    other = len(keys) - agree - lenient - strict
    print(f"불일치 방향: auto관대(yes/no) {lenient}건, auto엄격(no/yes) {strict}건, 그 외 {other}건")


if __name__ == "__main__":
    main()
