"""pass1(vqascore/cv) + csd + judge(축별 판정) CSV를 run×item_id 기준으로 합쳐
최종 채점 CSV 1개 + 마크다운 리포트를 만든다.

    python -m scripts.merge_results \\
        --pass1 bench/scores/v223_lumina2_pass1.csv bench/scores/v224_lumina2_pass1.csv \\
        --csd bench/scores/v223_lumina2_csd.csv \\
        --judge bench/scores/judge_v223_lumina2.csv bench/scores/judge_v224_lumina2.csv \\
        --out bench/scores/merged.csv

--csd/--judge는 생략 가능 — csd가 아직 없으면(정식 ref_set 미수집) 그 컴포넌트만
NaN으로 빠지고 harmonic은 나머지 값들로 계산된다(결측 컬럼에 사유 표시).

조인 키는 (run, item_id) — model은 참고용 컬럼으로 같이 붙는다. "item_id × model
기준"이 아니라 (run, item_id)로 조인하는 이유: 같은 모델이라도 프리셋(run)이 다르면
전혀 다른 스타일 조건의 결과라 model만으로 묶으면 서로 다른 run의 결과가 뒤섞인다.
모델×축 pass율처럼 model 단위로 집계가 필요한 표는 리포트에서 model 컬럼으로
group-by한다.
"""
import argparse
import csv
import pathlib
from collections import defaultdict

ROOT = pathlib.Path(__file__).parent.parent
AXES = ("counting", "spatial", "attribute")


def _read_csv(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _harmonic_mean(values):
    vals = [v for v in values if v is not None]
    if not vals:
        return None
    if any(v <= 0 for v in vals):
        return 0.0
    return round(len(vals) / sum(1 / v for v in vals), 4)


def _load_pass1(paths, merged):
    for path in paths:
        for row in _read_csv(path):
            key = (row["run"], row["item_id"])
            if key in merged and merged[key].get("_image") not in (None, row.get("image")):
                raise ValueError(
                    f"(run, item_id)={key} 중복 — {merged[key]['_image']!r}와 {row.get('image')!r}가 "
                    "같은 키로 충돌합니다. item_id가 빈 문자열이면(비-bench_v1 run) 이미지별로 "
                    "구분이 안 되어 조인 시 데이터가 섞입니다 — bench_v1 run만 merge_results.py로 합칠 것."
                )
            merged[key]["_image"] = row.get("image")
            merged[key]["run"] = row["run"]
            merged[key]["model"] = row["model"]
            merged[key]["item_id"] = row["item_id"]
            if row.get("vqascore"):
                merged[key]["vqascore"] = float(row["vqascore"])
            if row.get("custom_cv"):
                merged[key]["custom_cv"] = float(row["custom_cv"])


def _load_csd(paths, merged):
    for path in paths:
        for row in _read_csv(path):
            key = (row["run"], row["item_id"])
            merged[key]["run"] = row["run"]
            merged[key]["model"] = row.get("model") or merged[key].get("model")
            merged[key]["item_id"] = row["item_id"]
            if row.get("csd"):
                merged[key]["csd"] = float(row["csd"])
                merged[key]["csd_provisional"] = row.get("csd_provisional") == "True"


def _load_judge(paths, merged):
    all_rows = []
    by_key = defaultdict(list)
    for path in paths:
        for row in _read_csv(path):
            key = (row["run"], row["item_id"])
            by_key[key].append(row)
            all_rows.append(row)

    for key, rows in by_key.items():
        merged[key]["run"], merged[key]["item_id"] = key
        merged[key]["model"] = rows[0].get("model") or merged[key].get("model")
        applicable = [r for r in rows if r["verdict"] in ("pass", "fail")]
        if applicable:
            passed = sum(1 for r in applicable if r["verdict"] == "pass")
            merged[key]["judge_pass_rate"] = round(passed / len(applicable), 4)
            merged[key]["judge_axes_applicable"] = ",".join(sorted(r["axis"] for r in applicable))
        parse_errors = [r["axis"] for r in rows if r["verdict"] == "parse_error"]
        if parse_errors:
            merged[key]["judge_parse_errors"] = ",".join(sorted(parse_errors))
    return all_rows


def merge(pass1_paths, csd_paths, judge_paths):
    merged = defaultdict(dict)
    _load_pass1(pass1_paths, merged)
    _load_csd(csd_paths or [], merged)
    judge_raw_rows = _load_judge(judge_paths or [], merged)

    rows = []
    any_provisional = False
    for key, row in sorted(merged.items()):
        components = {
            "vqascore": row.get("vqascore"),
            "custom_cv": row.get("custom_cv"),
            "csd": row.get("csd"),
            "judge_pass_rate": row.get("judge_pass_rate"),
        }
        missing = [k for k, v in components.items() if v is None]
        harmonic = _harmonic_mean(list(components.values()))
        if row.get("csd_provisional"):
            any_provisional = True

        rows.append({
            "run": row.get("run", key[0]),
            "model": row.get("model", ""),
            "item_id": row.get("item_id", key[1]),
            "vqascore": components["vqascore"],
            "custom_cv": components["custom_cv"],
            "csd": components["csd"],
            "csd_provisional": row.get("csd_provisional", False),
            "judge_pass_rate": components["judge_pass_rate"],
            "judge_axes_applicable": row.get("judge_axes_applicable", ""),
            "judge_parse_errors": row.get("judge_parse_errors", ""),
            "harmonic": harmonic,
            "missing_components": ",".join(missing),
        })
    return rows, any_provisional, judge_raw_rows


def write_csv(rows, out_path):
    fieldnames = ["run", "model", "item_id", "vqascore", "custom_cv", "csd", "csd_provisional",
                  "judge_pass_rate", "judge_axes_applicable", "judge_parse_errors",
                  "harmonic", "missing_components"]
    out_path = pathlib.Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _mean(values):
    vals = [v for v in values if v is not None]
    return round(sum(vals) / len(vals), 4) if vals else None


def _write_report(rows, any_provisional, judge_raw_rows, out_path):
    lines = ["# 채점 결과 병합 리포트", ""]
    if any_provisional:
        lines += ["> ⚠ csd 일부/전체가 provisional ref_set(정식 골든셋 미수집) 기준입니다 — "
                  "정식 ref_set 수집 후 재해석 필요.", ""]

    models = sorted({r["model"] for r in rows if r["model"]})

    lines += ["## 모델별 컴포넌트 평균", "", "| model | vqascore | custom_cv | csd | judge_pass_rate | harmonic |",
              "|---|---|---|---|---|---|"]
    for model in models:
        mrows = [r for r in rows if r["model"] == model]
        lines.append(
            f"| {model} | {_mean([r['vqascore'] for r in mrows])} | "
            f"{_mean([r['custom_cv'] for r in mrows])} | {_mean([r['csd'] for r in mrows])} | "
            f"{_mean([r['judge_pass_rate'] for r in mrows])} | {_mean([r['harmonic'] for r in mrows])} |"
        )

    lines += ["", "## 모델×축 pass율 (judge)", "", "| model | " + " | ".join(AXES) + " |",
              "|---|" + "---|" * len(AXES)]
    judge_models = sorted({r["model"] for r in judge_raw_rows if r.get("model")})
    for model in judge_models:
        cells = []
        for axis in AXES:
            applicable = [r for r in judge_raw_rows
                          if r["model"] == model and r["axis"] == axis
                          and r["verdict"] in ("pass", "fail")]
            if not applicable:
                cells.append("n/a")
            else:
                passed = sum(1 for r in applicable if r["verdict"] == "pass")
                cells.append(f"{passed}/{len(applicable)} ({passed / len(applicable):.0%})")
        lines.append(f"| {model} | " + " | ".join(cells) + " |")

    pathlib.Path(out_path).write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pass1", nargs="+", required=True, help="scores_*_pass1.csv 경로들")
    ap.add_argument("--csd", nargs="*", default=[], help="scores_*_csd.csv 경로들 (생략 가능)")
    ap.add_argument("--judge", nargs="*", default=[], help="judge_*.csv 경로들 (생략 가능)")
    ap.add_argument("--out", required=True, help="출력 CSV 경로 (같은 이름의 .md 리포트도 생성)")
    args = ap.parse_args()

    rows, any_provisional, judge_raw_rows = merge(args.pass1, args.csd, args.judge)
    write_csv(rows, args.out)
    _write_report(rows, any_provisional, judge_raw_rows, pathlib.Path(args.out).with_suffix(".md"))

    print(f"{len(rows)}행(run×item_id) 병합 완료 -> {args.out}")
    if any_provisional:
        print("[warn] csd provisional 포함 — 리포트 상단 경고 문구 확인")


if __name__ == "__main__":
    main()
