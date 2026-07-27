"""lecture24 3-모델 paired 벤치 결과 통계 리포트. 읽기 전용.

    python -m scripts.stats_report --in bench/scores --out reports/stats_lecture24
"""
import argparse
import csv
import itertools
import math
import pathlib
import re
import sys
import warnings
from collections import defaultdict

from scipy.stats import fisher_exact, norm, wilcoxon

CONTINUOUS_METRICS = ("vqascore", "custom_cv", "csd_target")
JUDGE_AXES = ("content_present", "text_legibility", "layout_structure", "educational_fit")
STRUCTURAL = {"structured_worksheet_template", "data_visualization_chart",
              "labeled_science_diagram", "geometric_shape_set"}
ILLUSTRATION = {"historical_figure_portrait", "multi_character_classroom_collaboration",
                 "intergenerational_indoor_scene", "single_character_cutout"}
RUN_DIR_RE = re.compile(r"^v\d+_(.+)-lecture24$")


def _read_csv(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def prompt_id_from_image(image_name):
    """v243_00_structured_worksheet_template_claude.png -> (category, source)"""
    parts = image_name.rsplit(".", 1)[0].split("_")[2:]  # drop vNNN_, index
    return "_".join(parts[:-1]), parts[-1]


def load_model_data(run_dir):
    """(category, source) prompt_id -> row dict, 모델 하나 분량."""
    data = {}
    for row in _read_csv(run_dir / "pass1.csv"):
        category, source = prompt_id_from_image(row["image"])
        d = data.setdefault(f"{category}_{source}", {"category": category, "prompt_source": source})
        d["vqascore"] = float(row["vqascore"])
        d["custom_cv"] = float(row["custom_cv"])
    for row in _read_csv(run_dir / "csd_target.csv"):
        category, source = prompt_id_from_image(row["image"])
        d = data.setdefault(f"{category}_{source}", {"category": category, "prompt_source": source})
        d["csd_target"] = float(row["csd_target"])
    for row in _read_csv(run_dir / "judge_lecture24.csv"):
        d = data.setdefault(f"{row['type']}_{row['source']}",
                             {"category": row["type"], "prompt_source": row["source"]})
        d.setdefault("judge", {})[row["axis"]] = row["verdict"]
    return data


def assert_full_match(model_data):
    id_sets = {m: set(d) for m, d in model_data.items()}
    union = set().union(*id_sets.values())
    for m, ids in id_sets.items():
        missing = union - ids
        if missing:
            sys.exit(f"[FATAL] {m}: missing prompt_ids: {sorted(missing)}")
    if len(union) != 24:
        sys.exit(f"[FATAL] expected 24 prompt_ids, found {len(union)}: {sorted(union)}")
    print(f"[ok] {len(union)} prompt_ids matched across {len(model_data)} models")


def wilcoxon_report(model_data, models, metric):
    rows = []
    for m1, m2 in itertools.combinations(models, 2):
        pids = sorted(set(model_data[m1]) & set(model_data[m2]))
        pairs = [(model_data[m1][p][metric], model_data[m2][p][metric]) for p in pids
                  if metric in model_data[m1][p] and metric in model_data[m2][p]]
        n = len(pairs)
        n_ties = sum(1 for a, b in pairs if a == b)
        if n_ties:
            warnings.warn(f"{metric} {m1} vs {m2}: {n_ties}/{n} pairs tied (zero diff)")
        if n - n_ties == 0:
            stat, p, r = float("nan"), float("nan"), float("nan")
        else:
            stat, p = wilcoxon([a for a, _ in pairs], [b for _, b in pairs])
            z = abs(norm.isf(p / 2))
            r = z / math.sqrt(n)
        rows.append({"metric": metric, "model_a": m1, "model_b": m2, "n": n, "n_ties": n_ties,
                      "statistic": round(stat, 4) if stat == stat else "",
                      "p_value": round(p, 6) if p == p else "",
                      "effect_r": round(r, 4) if r == r else ""})
    return rows


def wilson_ci(k, n, z=1.959963984540054):
    if n == 0:
        return float("nan"), float("nan"), float("nan")
    phat = k / n
    denom = 1 + z * z / n
    center = (phat + z * z / (2 * n)) / denom
    half = z * math.sqrt(phat * (1 - phat) / n + z * z / (4 * n * n)) / denom
    return phat, max(0.0, center - half), min(1.0, center + half)


def judge_pass_rate_report(model_data, models):
    rows = []
    for model in models:
        for axis in JUDGE_AXES:
            verdicts = [d["judge"][axis] for d in model_data[model].values()
                        if "judge" in d and axis in d["judge"]]
            total = len(verdicts)
            na = sum(1 for v in verdicts if v == "n/a")
            evaluable = total - na
            passed = sum(1 for v in verdicts if v == "pass")
            phat, lo, hi = wilson_ci(passed, evaluable)
            emit = round(evaluable / total, 4) if axis == "text_legibility" and total else ""
            rows.append({"model": model, "axis": axis, "n_total": total, "n_na_excluded": na,
                         "n_evaluable": evaluable, "n_pass": passed,
                         "pass_rate": round(phat, 4) if phat == phat else "",
                         "ci_low": round(lo, 4) if lo == lo else "",
                         "ci_high": round(hi, 4) if hi == hi else "",
                         "emission_rate": emit})
    return rows


def fisher_report(model_data, models):
    rows = []
    for m1, m2 in itertools.combinations(models, 2):
        for axis in JUDGE_AXES:
            counts = {}
            for m in (m1, m2):
                vs = [d["judge"][axis] for d in model_data[m].values()
                      if "judge" in d and d["judge"].get(axis) in ("pass", "fail")]
                counts[m] = (sum(1 for v in vs if v == "pass"), sum(1 for v in vs if v == "fail"))
            a, b = counts[m1]
            c, d_ = counts[m2]
            if a + b == 0 or c + d_ == 0:
                odds, p = float("nan"), float("nan")
            else:
                odds, p = fisher_exact([[a, b], [c, d_]])
            rows.append({"axis": axis, "model_a": m1, "model_b": m2, "a_pass": a, "a_fail": b,
                         "b_pass": c, "b_fail": d_,
                         "odds_ratio": round(odds, 4) if odds == odds else "",
                         "p_value": round(p, 6) if p == p else ""})
    return rows


def track_of(category):
    if category in STRUCTURAL:
        return "structural"
    if category in ILLUSTRATION:
        return "illustration"
    return "unknown"


def stratified_table(model_data, models, key_fn, key_name):
    rows = []
    for model in models:
        strata = defaultdict(list)
        for d in model_data[model].values():
            strata[key_fn(d)].append(d)
        for stratum, items in sorted(strata.items()):
            row = {key_name: stratum, "model": model, "n": len(items)}
            for metric in CONTINUOUS_METRICS:
                vals = [it[metric] for it in items if metric in it]
                row[f"{metric}_mean"] = round(sum(vals) / len(vals), 4) if vals else ""
            for axis in JUDGE_AXES:
                vs = [it["judge"][axis] for it in items if "judge" in it and axis in it["judge"]]
                ev = [v for v in vs if v != "n/a"]
                row[f"{axis}_pass_rate"] = round(sum(v == "pass" for v in ev) / len(ev), 4) if ev else ""
            rows.append(row)
    return rows


def write_csv(path, rows, fieldnames):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)
    print(f"[wrote] {path} ({len(rows)} rows)")


def plot_diff_boxplots(model_data, models, out_dir):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    for metric in CONTINUOUS_METRICS:
        labels, data = [], []
        for m1, m2 in itertools.combinations(models, 2):
            pids = sorted(set(model_data[m1]) & set(model_data[m2]))
            diffs = [model_data[m1][p][metric] - model_data[m2][p][metric] for p in pids
                      if metric in model_data[m1][p] and metric in model_data[m2][p]]
            if diffs:
                labels.append(f"{m1}\nvs {m2}")
                data.append(diffs)
        if not data:
            continue
        fig, ax = plt.subplots(figsize=(max(4, 2.2 * len(data)), 5))
        ax.boxplot(data, tick_labels=labels)
        ax.axhline(0, color="gray", linestyle="--", linewidth=1)
        ax.set_title(f"per-prompt diff: {metric}")
        ax.set_ylabel(f"{metric} (A - B)")
        fig.tight_layout()
        out_path = out_dir / f"diff_boxplot_{metric}.png"
        fig.savefig(out_path, dpi=150)
        plt.close(fig)
        print(f"[wrote] {out_path}")


def print_summary(wilcoxon_rows, pass_rate_rows, fisher_rows):
    print("\n=== Wilcoxon signed-rank ===")
    for r in wilcoxon_rows:
        print(f"  {r['metric']:12s} {r['model_a']:20s} vs {r['model_b']:20s} "
              f"n={r['n']:>3} ties={r['n_ties']:>2} p={r['p_value']} r={r['effect_r']}")
    print("\n=== Judge pass rate (Wilson 95% CI) ===")
    for r in pass_rate_rows:
        extra = f" emission_rate={r['emission_rate']}" if r["emission_rate"] != "" else ""
        print(f"  {r['model']:20s} {r['axis']:18s} pass={r['n_pass']}/{r['n_evaluable']} "
              f"(na_excluded={r['n_na_excluded']}) rate={r['pass_rate']} "
              f"CI=[{r['ci_low']}, {r['ci_high']}]{extra}")
    print("\n=== Fisher's exact ===")
    for r in fisher_rows:
        print(f"  {r['axis']:18s} {r['model_a']:20s} vs {r['model_b']:20s} "
              f"[{r['a_pass']}/{r['a_fail']}] vs [{r['b_pass']}/{r['b_fail']}] p={r['p_value']}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="in_dir", required=True, type=pathlib.Path)
    ap.add_argument("--out", dest="out_dir", required=True, type=pathlib.Path)
    args = ap.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    runs = {m.group(1): d for d in sorted(args.in_dir.iterdir()) if d.is_dir()
            for m in [RUN_DIR_RE.match(d.name)] if m}
    if not runs:
        sys.exit(f"[FATAL] no *-lecture24 run dirs found under {args.in_dir}")
    models = sorted(runs)
    print(f"[ok] found models: {models}")

    model_data = {m: load_model_data(runs[m]) for m in models}
    assert_full_match(model_data)

    wilcoxon_rows = [r for metric in ("vqascore", "csd_target")
                      for r in wilcoxon_report(model_data, models, metric)]
    write_csv(args.out_dir / "wilcoxon.csv", wilcoxon_rows,
              ["metric", "model_a", "model_b", "n", "n_ties", "statistic", "p_value", "effect_r"])

    pass_rate_rows = judge_pass_rate_report(model_data, models)
    write_csv(args.out_dir / "judge_pass_rate.csv", pass_rate_rows,
              ["model", "axis", "n_total", "n_na_excluded", "n_evaluable", "n_pass",
               "pass_rate", "ci_low", "ci_high", "emission_rate"])

    fisher_rows = fisher_report(model_data, models)
    write_csv(args.out_dir / "fisher_exact.csv", fisher_rows,
              ["axis", "model_a", "model_b", "a_pass", "a_fail", "b_pass", "b_fail",
               "odds_ratio", "p_value"])

    strat_cols = ["model", "n"] + [f"{m}_mean" for m in CONTINUOUS_METRICS] \
        + [f"{a}_pass_rate" for a in JUDGE_AXES]
    for key_name, key_fn in (("category", lambda d: d["category"]),
                              ("prompt_source", lambda d: d["prompt_source"]),
                              ("track", lambda d: track_of(d["category"]))):
        rows = stratified_table(model_data, models, key_fn, key_name)
        write_csv(args.out_dir / f"stratified_{key_name}.csv", rows, [key_name] + strat_cols)

    plot_diff_boxplots(model_data, models, args.out_dir)
    print_summary(wilcoxon_rows, pass_rate_rows, fisher_rows)


if __name__ == "__main__":
    main()
