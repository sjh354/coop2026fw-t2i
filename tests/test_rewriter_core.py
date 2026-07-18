"""src/rewriter/core.py의 rewrite() 디스패치 로직 테스트. llm_fn을 주입해 네트워크를 안 탄다."""
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
from src.rewriter import RewriteOptions, rewrite


def _fake_llm(system, user):
    return "  a red apple on a plain table  "


class RewriteTest(unittest.TestCase):
    def test_returns_stripped_prompt_and_meta(self):
        opts = RewriteOptions(llm_fn=_fake_llm)
        result = rewrite("사과 한 개가 놓인 탁자", opts)
        self.assertEqual(result["prompt_en"], "a red apple on a plain table")
        self.assertEqual(result["meta"]["lang"], "ko")
        self.assertEqual(result["meta"]["max_words"], opts.max_words)

    def test_system_prompt_fills_max_words(self):
        captured = {}

        def capturing_llm(system, user):
            captured["system"] = system
            return "ok"

        opts = RewriteOptions(llm_fn=capturing_llm, max_words=15)
        rewrite("아무 문장", opts)
        self.assertIn("15 words maximum", captured["system"])

    def test_spanish_not_implemented(self):
        opts = RewriteOptions(lang="es", llm_fn=_fake_llm)
        with self.assertRaises(NotImplementedError):
            rewrite("cualquier texto", opts)

    def test_retries_once_when_style_word_leaks(self):
        calls = []

        def leaky_then_clean(system, user):
            calls.append(user)
            if len(calls) == 1:
                return "a red apple with plain neutral background"
            return "a red apple on a plain table"

        opts = RewriteOptions(llm_fn=leaky_then_clean)
        result = rewrite("사과 한 개가 놓인 탁자", opts)
        self.assertEqual(result["prompt_en"], "a red apple on a plain table")
        self.assertTrue(result["meta"]["retried"])
        self.assertEqual(len(calls), 2)

    def test_no_retry_when_checks_pass(self):
        opts = RewriteOptions(llm_fn=lambda system, user: "exactly one red apple on a plain table")
        result = rewrite("사과 한 개가 놓인 탁자", opts)
        self.assertFalse(result["meta"]["retried"])

    def test_retries_only_once_even_if_still_failing(self):
        calls = []

        def always_leaky(system, user):
            calls.append(user)
            return "a red apple with plain neutral background"

        opts = RewriteOptions(llm_fn=always_leaky)
        result = rewrite("사과 한 개가 놓인 탁자", opts)
        self.assertEqual(len(calls), 2)
        self.assertTrue(result["meta"]["retried"])
        self.assertEqual(result["prompt_en"], "a red apple with plain neutral background")


if __name__ == "__main__":
    unittest.main()
