"""scripts/verify_rewriter.py의 체크/리포트 조립 로직 테스트. rewrite()에 fake llm_fn을 주입해 네트워크를 안 탄다."""
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
from scripts.verify_rewriter import build_report, check_sample
from src.rewriter import RewriteOptions


def _opts_returning(fixed_output):
    return RewriteOptions(llm_fn=lambda system, user: fixed_output)


class CheckSampleTest(unittest.TestCase):
    def test_passes_when_all_checks_ok(self):
        sample = {"subject": "math", "prompt_ko": "사과 세 개가 담긴 바구니"}
        row = check_sample(sample, _opts_returning("exactly three red apples in a basket"))
        self.assertTrue(row["passed"])

    def test_fails_when_quantity_dropped(self):
        sample = {"subject": "math", "prompt_ko": "사과 세 개가 담긴 바구니"}
        row = check_sample(sample, _opts_returning("red apples in a basket"))
        self.assertFalse(row["quantity_ok"])
        self.assertFalse(row["passed"])

    def test_fails_when_style_word_leaks(self):
        sample = {"subject": "korean", "prompt_ko": "숲 속에서 토끼를 만나는 아이"}
        row = check_sample(sample, _opts_returning("a flat vector illustration of a child and a rabbit"))
        self.assertIn("flat", row["style_hits"])
        self.assertFalse(row["passed"])

    def test_fails_when_too_long(self):
        sample = {"subject": "korean", "prompt_ko": "숲 속에서 토끼를 만나는 아이"}
        long_output = " ".join(["word"] * 50)
        row = check_sample(sample, _opts_returning(long_output))
        self.assertFalse(row["length_ok"])
        self.assertFalse(row["passed"])


class BuildReportTest(unittest.TestCase):
    def test_report_counts_passes(self):
        sample = {"subject": "math", "prompt_ko": "사과 세 개가 담긴 바구니"}
        row = check_sample(sample, _opts_returning("exactly three red apples in a basket"))
        report = build_report([row])
        self.assertIn("통과: 1/1", report)
        self.assertIn("PASS", report)


if __name__ == "__main__":
    unittest.main()
