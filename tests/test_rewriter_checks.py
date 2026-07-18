"""src/rewriter/checks.py 순수 함수 유닛 테스트. API 키/네트워크 불필요."""
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
from src.rewriter.checks import (
    STYLE_FORBIDDEN_WORDS, find_style_words, has_number_output,
    has_quantity_ko, token_count,
)


class HasQuantityKoTest(unittest.TestCase):
    def test_counter_word_detected(self):
        self.assertTrue(has_quantity_ko("사과 세 개가 담긴 바구니"))

    def test_digit_with_counter_detected(self):
        self.assertTrue(has_quantity_ko("달 8개가 순서대로 나열된 그림"))

    def test_particle_not_false_positive(self):
        # "이"는 조사일 뿐 수량이 아니다 — 단위명사 없이 오탐하면 안 된다.
        self.assertFalse(has_quantity_ko("이것은 사과입니다"))

    def test_plain_sentence_no_quantity(self):
        self.assertFalse(has_quantity_ko("숲 속에서 토끼를 만나는 아이"))


class HasNumberOutputTest(unittest.TestCase):
    def test_digit_detected(self):
        self.assertTrue(has_number_output("exactly 3 red apples in a basket"))

    def test_number_word_detected(self):
        self.assertTrue(has_number_output("exactly three red apples in a basket"))

    def test_no_number_detected(self):
        self.assertFalse(has_number_output("a basket full of red apples"))


class FindStyleWordsTest(unittest.TestCase):
    def test_contamination_found(self):
        text = "a flat vector illustration of a red apple"
        hits = find_style_words(text, STYLE_FORBIDDEN_WORDS)
        self.assertIn("flat", hits)
        self.assertIn("vector", hits)
        self.assertIn("illustration", hits)

    def test_clean_output_no_hits(self):
        text = "a smiling child holding a large yellow umbrella"
        self.assertEqual(find_style_words(text, STYLE_FORBIDDEN_WORDS), [])


class TokenCountTest(unittest.TestCase):
    def test_counts_whitespace_tokens(self):
        self.assertEqual(token_count("a red apple on a table"), 6)


if __name__ == "__main__":
    unittest.main()
