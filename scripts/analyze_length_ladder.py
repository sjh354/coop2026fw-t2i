"""TASK-I 파트 2: 순수 길이 효과 분석. 하나의 리라이팅 계열(promptenhancer_cn)을
short(=passthrough 원본, v250) / medium(=문장 단위 중간 길이 절단, v263 신규 생성) /
long(=전체 리라이팅, v262) 3단으로 놓고, structural(counting/attribute-binding) 12개
항목에서 지표가 단어 수와 단조 관계를 보이는지 본다. 어휘 계열은 세 조건 모두
promptenhancer_cn 하나로 고정(단, short는 리라이팅 이전 원본이므로 어휘 자체는 다르다 —
이 한계는 TASK-I 설계 문서에 이미 명시됨).

    python -m scripts.analyze_length_ladder \
        --short bench/scores/v250_flux2-klein-4b-nf4-lecture24 \
        --medium bench/scores/v263_flux2-klein-4b-nf4-lecture24 \
        --long bench/scores/v262_flux2-klein-4b-nf4-lecture24 \
        --out reports/length-effect-taski
"""
import argparse
import json
import pathlib

from scipy.stats import spearmanr, wilcoxon

from scripts.stats_report import CONTINUOUS_METRICS, JUDGE_AXES, STRUCTURAL, load_model_data, write_csv
from scripts.analyze_rewrite_by_category import judge_pass_rate_per_item

METRICS = list(CONTINUOUS_METRICS) + ["judge_pass_rate"]
TIERS = ("short", "medium", "long")
SOURCE_SLUG = {"claude": "claude", "chatgpt": "chatgpt", "qwen2.5-vl-7b-instruct": "qwen"}


def word_counts():
    """prompt_id(category_source) -> {tier: word_count}, structural 12개만."""
    passthrough = json.loads(pathlib.Path("image-prompts/rewrite/passthrough.json").read_text())
    medium = json.loads(pathlib.Path("image-prompts/rewrite/promptenhancer_cn_medium.json").read_text())
    long_ = json.loads(pathlib.Path("image-prompts/rewrite/promptenhancer_cn.json").read_text())
    counts = {}
    for cat in passthrough:
        slug = cat["type"].lower().replace(" ", "_").replace("-", "_")
        if slug not in STRUCTURAL:
            continue
        for source, src_slug in SOURCE_SLUG.items():
            pid = f"{slug}_{src_slug}"
            counts.setdefault(pid, {})["short"] = len(cat[source]["prompt"].split())
    for cat, tier in ((medium, "medium"), (long_, "long")):
        for entry in cat:
            slug = entry["type"].lower().replace(" ", "_").replace("-", "_")
            for source, src_slug in SOURCE_SLUG.items():
                pid = f"{slug}_{src_slug}"
                counts.setdefault(pid, {})[tier] = len(entry[source]["prompt"].split())
    return counts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--short", required=True, type=pathlib.Path)
    ap.add_argument("--medium", required=True, type=pathlib.Path)
    ap.add_argument("--long", required=True, type=pathlib.Path)
    ap.add_argument("--out", required=True, type=pathlib.Path)
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    tier_dirs = {"short": args.short, "medium": args.medium, "long": args.long}
    tier_data = {}
    for tier, d in tier_dirs.items():
        data = load_model_data(d)
        judge_pass_rate_per_item(data)
        tier_data[tier] = {pid: row for pid, row in data.items()
                            if row["category"] in STRUCTURAL}

    wc = word_counts()

    pids = sorted(set(tier_data["short"]) & set(tier_data["medium"]) & set(tier_data["long"]))
    missing = (set(tier_data["short"]) | set(tier_data["medium"]) | set(tier_data["long"])) - set(pids)
    if missing:
        print(f"[warn] 3단 전부에서 안 잡힌 prompt_id, 제외: {sorted(missing)}")
    print(f"[ok] {len(pids)}개 structural prompt_id 매칭 (기대: 12)")

    trend_rows, pair_rows = [], []
    for metric in METRICS:
        xs, ys = [], []
        for tier in TIERS:
            for pid in pids:
                v = tier_data[tier][pid].get(metric)
                if v is None:
                    continue
                xs.append(wc[pid][tier])
                ys.append(v)
        if len(xs) >= 3:
            rho, p = spearmanr(xs, ys)
        else:
            rho, p = float("nan"), float("nan")
        trend_rows.append({"metric": metric, "n_points": len(xs),
                            "spearman_rho": round(rho, 4) if rho == rho else "",
                            "spearman_p": round(p, 6) if p == p else ""})

        for t1, t2 in (("short", "medium"), ("medium", "long"), ("short", "long")):
            a = [tier_data[t1][pid][metric] for pid in pids
                 if metric in tier_data[t1][pid] and metric in tier_data[t2][pid]]
            b = [tier_data[t2][pid][metric] for pid in pids
                 if metric in tier_data[t1][pid] and metric in tier_data[t2][pid]]
            if len(a) < 2 or all(x == y for x, y in zip(a, b)):
                stat, p2 = float("nan"), float("nan")
            else:
                stat, p2 = wilcoxon(a, b)
            pair_rows.append({"metric": metric, "tier_a": t1, "tier_b": t2, "n": len(a),
                               "mean_a": round(sum(a) / len(a), 4) if a else "",
                               "mean_b": round(sum(b) / len(b), 4) if b else "",
                               "wilcoxon_p": round(p2, 6) if p2 == p2 else ""})

    write_csv(args.out / "length_ladder_trend.csv", trend_rows,
              ["metric", "n_points", "spearman_rho", "spearman_p"])
    write_csv(args.out / "length_ladder_pairwise.csv", pair_rows,
              ["metric", "tier_a", "tier_b", "n", "mean_a", "mean_b", "wilcoxon_p"])

    print("\n=== word count vs metric: Spearman (short+medium+long 36점) ===")
    for r in trend_rows:
        print(f"  {r['metric']:18s} n={r['n_points']:>3} rho={r['spearman_rho']} p={r['spearman_p']}")
    print("\n=== tier간 paired Wilcoxon (n=12) ===")
    for r in pair_rows:
        print(f"  {r['metric']:18s} {r['tier_a']:6s} vs {r['tier_b']:6s} "
              f"mean {r['mean_a']} vs {r['mean_b']}  p={r['wilcoxon_p']}")


if __name__ == "__main__":
    main()
