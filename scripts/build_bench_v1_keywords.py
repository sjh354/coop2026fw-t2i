"""bench_v1(한국어 prompt_ko 40개)를 rewriter에 통과시켜 영어 키워드셋으로 만든다.

    python -m scripts.build_bench_v1_keywords

출력:
    configs/keywords/bench_v1.yaml  — generate.py가 바로 읽을 수 있는 영어 키워드 리스트
    bench/bench_v1-rewrite-report.md — id/한국어/영어/재시도여부 대조표 (본 실험 전 스팟체크용)

OPENAI_API_KEY 환경변수가 필요하다 (scripts/verify_rewriter.py와 동일한 provider).
"""
import pathlib
import sys

ROOT = pathlib.Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
import yaml  # noqa: E402

from scripts.alert import load_env_file  # noqa: E402
from src.rewriter import RewriteOptions, rewrite  # noqa: E402

BENCH_PATH = ROOT / "configs" / "benchmarks" / "bench_v1.yaml"
KEYWORDS_OUT = ROOT / "configs" / "keywords" / "bench_v1.yaml"
REPORT_OUT = ROOT / "bench" / "bench_v1-rewrite-report.md"


def build_keywords_yaml(rows):
    lines = [
        "# bench_v1(configs/benchmarks/bench_v1.yaml)를 rewriter로 영어 변환한 결과.",
        "# 직접 수정하지 말고 `python -m scripts.build_bench_v1_keywords`로 재생성할 것.",
        "# 대조표: bench/bench_v1-rewrite-report.md",
        "name: bench_v1",
        "keywords:",
    ]
    for row in rows:
        prompt_en = row["prompt_en"].replace('"', '\\"')
        lines.append(f'  - "{prompt_en}"')
    return "\n".join(lines) + "\n"


def build_report(rows):
    retried = sum(row["retried"] for row in rows)
    lines = [
        "# bench_v1 rewriter 변환 리포트",
        "",
        f"총 {len(rows)}개, 재시도 발생 {retried}개.",
        "",
        "본 실험 전 육안 스팟체크: 카테고리별 몇 개씩 골라 원문 의도가 유지됐는지,",
        "출력이 비지 않았는지 확인할 것 (D 검증에서 발견된 빈 출력 버그와 동일 클래스).",
        "",
        "| # | id | 과목 | 카테고리 | 입력(ko) | 출력(en) | 재시도 |",
        "|---|-----|------|---------|----------|----------|--------|",
    ]
    for i, row in enumerate(rows, 1):
        p = row["prompt"]
        lines.append(
            f"| {i} | {p['id']} | {p['subject']} | {p['category']} | {p['prompt_ko']} | "
            f"{row['prompt_en']} | {'OK' if row['retried'] else '-'} |"
        )
    return "\n".join(lines) + "\n"


def main():
    load_env_file(str(ROOT / ".env"))
    bench = yaml.safe_load(BENCH_PATH.read_text(encoding="utf-8"))
    opts = RewriteOptions()

    rows = []
    for i, p in enumerate(bench["prompts"], 1):
        result = rewrite(p["prompt_ko"], opts)
        prompt_en = result["prompt_en"]
        if not prompt_en.strip():
            print(f"[warn] {p['id']} 빈 출력 (재시도 후에도) — 리포트에서 확인할 것")
        print(f"[{i}/{len(bench['prompts'])}] {p['id']} -> {prompt_en[:60]}")
        rows.append({"prompt": p, "prompt_en": prompt_en, "retried": result["meta"]["retried"]})

    KEYWORDS_OUT.write_text(build_keywords_yaml(rows), encoding="utf-8")
    REPORT_OUT.parent.mkdir(exist_ok=True)
    REPORT_OUT.write_text(build_report(rows), encoding="utf-8")
    empty = sum(1 for r in rows if not r["prompt_en"].strip())
    print(f"\n{len(rows)}개 변환 완료 -> {KEYWORDS_OUT}")
    print(f"리포트 -> {REPORT_OUT}")
    if empty:
        print(f"[warn] 빈 출력 {empty}개 — 리포트 확인 후 재실행하거나 수동 보정할 것")


if __name__ == "__main__":
    main()
