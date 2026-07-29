"""TASK-I 파트 1: 리라이팅(passthrough→wan_style_cn/promptenhancer_cn) 효과가
structural(counting/attribute-binding) 카테고리와 illustration 카테고리에서
다르게 나타나는지 분석. 새 생성/채점 없음 — 기존 bench/scores/v250,v261,v262
run dir를 읽기만 한다. 카테고리 분류는 scripts/stats_report.py의 STRUCTURAL/
ILLUSTRATION(TASK-A에서 이미 확정된 track 정의)을 그대로 재사용한다.

    python -m scripts.analyze_rewrite_by_category \
        --baseline bench/scores/v250_flux2-klein-4b-nf4-lecture24 \
        --rewrite bench/scores/v261_flux2-klein-4b-nf4-lecture24 wan_style_cn \
        --rewrite bench/scores/v262_flux2-klein-4b-nf4-lecture24 promptenhancer_cn \
        --out reports/length-effect-taski
"""
import argparse
import pathlib

from scipy.stats import mannwhitneyu
import numpy as np

from scripts.stats_report import (
    CONTINUOUS_METRICS, JUDGE_AXES, load_model_data, track_of, write_csv,
)

N_BOOTSTRAP = 10000
RNG_SEED = 0


def judge_pass_rate_per_item(model_data):
    for d in model_data.values():
        judge = d.get("judge", {})
        evaluable = [v for a in JUDGE_AXES for v in [judge.get(a)] if v not in (None, "n/a")]
        d["judge_pass_rate"] = (
            sum(v == "pass" for v in evaluable) / len(evaluable) if evaluable else None
        )


def bootstrap_mean_diff_ci(group_a, group_b, n=N_BOOTSTRAP, seed=RNG_SEED):
    rng = np.random.default_rng(seed)
    a, b = np.asarray(group_a), np.asarray(group_b)
    diffs = np.empty(n)
    for i in range(n):
        diffs[i] = rng.choice(a, size=len(a), replace=True).mean() - rng.choice(b, size=len(b), replace=True).mean()
    return float(diffs.mean()), float(np.percentile(diffs, 2.5)), float(np.percentile(diffs, 97.5))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--baseline", required=True, type=pathlib.Path)
    ap.add_argument("--rewrite", action="append", nargs=2, metavar=("DIR", "LABEL"), required=True)
    ap.add_argument("--out", required=True, type=pathlib.Path)
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    base = load_model_data(args.baseline)
    judge_pass_rate_per_item(base)

    metrics = list(CONTINUOUS_METRICS) + ["judge_pass_rate"]
    rows = []
    for rewrite_dir, label in args.rewrite:
        rw = load_model_data(pathlib.Path(rewrite_dir))
        judge_pass_rate_per_item(rw)

        pids = sorted(set(base) & set(rw))
        missing = (set(base) | set(rw)) - set(pids)
        if missing:
            print(f"[warn] {label}: {len(missing)} prompt_id(s) not matched, excluded: {sorted(missing)}")

        for metric in metrics:
            deltas_by_track = {"structural": [], "illustration": []}
            for pid in pids:
                bv, rv = base[pid].get(metric), rw[pid].get(metric)
                if bv is None or rv is None:
                    continue
                track = track_of(base[pid]["category"])
                if track not in deltas_by_track:
                    continue
                deltas_by_track[track].append(rv - bv)

            s_deltas, i_deltas = deltas_by_track["structural"], deltas_by_track["illustration"]
            if len(s_deltas) < 2 or len(i_deltas) < 2:
                print(f"[warn] {label}/{metric}: too few paired points "
                      f"(structural n={len(s_deltas)}, illustration n={len(i_deltas)}) — skipped")
                continue

            u_stat, p = mannwhitneyu(s_deltas, i_deltas, alternative="two-sided")
            mean_diff, ci_lo, ci_hi = bootstrap_mean_diff_ci(s_deltas, i_deltas)

            rows.append({
                "rewrite_condition": label,
                "metric": metric,
                "n_structural": len(s_deltas),
                "n_illustration": len(i_deltas),
                "structural_mean_delta": round(sum(s_deltas) / len(s_deltas), 4),
                "illustration_mean_delta": round(sum(i_deltas) / len(i_deltas), 4),
                "mannwhitney_u": round(u_stat, 4),
                "mannwhitney_p": round(p, 6),
                "bootstrap_mean_diff": round(mean_diff, 4),
                "bootstrap_ci_low": round(ci_lo, 4),
                "bootstrap_ci_high": round(ci_hi, 4),
            })

    write_csv(args.out / "length_effect_by_track.csv", rows,
              ["rewrite_condition", "metric", "n_structural", "n_illustration",
               "structural_mean_delta", "illustration_mean_delta",
               "mannwhitney_u", "mannwhitney_p",
               "bootstrap_mean_diff", "bootstrap_ci_low", "bootstrap_ci_high"])

    print("\n=== structural vs illustration: rewrite-delta comparison (Mann-Whitney U) ===")
    for r in rows:
        print(f"  {r['rewrite_condition']:20s} {r['metric']:18s} "
              f"structural_delta={r['structural_mean_delta']:+.4f}(n={r['n_structural']}) "
              f"illustration_delta={r['illustration_mean_delta']:+.4f}(n={r['n_illustration']}) "
              f"p={r['mannwhitney_p']} "
              f"boot_diff={r['bootstrap_mean_diff']:+.4f} "
              f"CI=[{r['bootstrap_ci_low']:+.4f}, {r['bootstrap_ci_high']:+.4f}]")


if __name__ == "__main__":
    main()
