"""rewrite() 검증 하네스. 과목별 샘플 20개에 자동 체크를 돌리고 마크다운 리포트를 남긴다.

    python -m scripts.verify_rewriter

OPENAI_API_KEY 환경변수가 필요하다 (src/rewriter/providers.py 참고). 다른
provider를 쓰려면 RewriteOptions(llm_fn=...)를 이 파일에서 opts에 넘기면 된다.
"""
import pathlib
import sys

ROOT = pathlib.Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
from scripts.alert import load_env_file
from src.rewriter import RewriteOptions, rewrite
from src.rewriter.checks import (
    STYLE_FORBIDDEN_WORDS, find_style_words, has_number_output,
    has_quantity_ko, token_count,
)
from tests.rewriter_samples_ko import SAMPLES

REPORT_PATH = ROOT / "bench" / "rewriter-verification-report.md"


def check_sample(sample, opts):
    """샘플 하나를 rewrite()에 태우고 체크 결과 딕셔너리를 반환한다."""
    result = rewrite(sample["prompt_ko"], opts)
    prompt_en = result["prompt_en"]
    quantity_ok = (not has_quantity_ko(sample["prompt_ko"])) or has_number_output(prompt_en)
    style_hits = find_style_words(prompt_en, STYLE_FORBIDDEN_WORDS)
    length_ok = token_count(prompt_en) <= opts.max_words
    return {
        "sample": sample,
        "prompt_en": prompt_en,
        "quantity_ok": quantity_ok,
        "style_hits": style_hits,
        "length_ok": length_ok,
        "passed": quantity_ok and not style_hits and length_ok,
    }


def build_report(rows):
    """체크 결과 리스트 -> 마크다운 리포트 문자열."""
    passed = sum(row["passed"] for row in rows)
    lines = [
        "# Rewriter 검증 리포트",
        "",
        f"통과: {passed}/{len(rows)}",
        "",
        "| # | 과목 | 입력 | 출력 | 수량 | 스타일오염 | 길이 | 결과 |",
        "|---|------|------|------|------|-----------|------|------|",
    ]
    for i, row in enumerate(rows, 1):
        sample = row["sample"]
        style = ", ".join(row["style_hits"]) if row["style_hits"] else "-"
        lines.append(
            f"| {i} | {sample['subject']} | {sample['prompt_ko']} | {row['prompt_en']} | "
            f"{'OK' if row['quantity_ok'] else 'FAIL'} | {style} | "
            f"{'OK' if row['length_ok'] else 'FAIL'} | {'PASS' if row['passed'] else 'FAIL'} |"
        )
    return "\n".join(lines) + "\n"


def main():
    """20개 샘플 전부 검증하고 리포트를 파일로 저장한다."""
    load_env_file(str(ROOT / ".env"))
    opts = RewriteOptions()
    rows = [check_sample(sample, opts) for sample in SAMPLES]
    REPORT_PATH.parent.mkdir(exist_ok=True)
    REPORT_PATH.write_text(build_report(rows), encoding="utf-8")
    passed = sum(row["passed"] for row in rows)
    print(f"{passed}/{len(rows)} passed -> {REPORT_PATH}")


if __name__ == "__main__":
    main()
