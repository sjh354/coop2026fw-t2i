"""rewrite() 출력을 검증하는 순수 함수들. LLM 호출 없이 문자열만 본다."""
import re

QUANTITY_RE_KO = re.compile(
    r"(\d+|하나|둘|셋|넷|다섯|여섯|일곱|여덟|아홉|열|한|두|세|네)"
    r"\s?(개|명|마리|그루|송이|장|권|대|채|가지|줄|칸)"
)

NUMBER_WORDS_EN = {
    "one", "two", "three", "four", "five", "six", "seven", "eight",
    "nine", "ten", "eleven", "twelve",
}

STYLE_FORBIDDEN_WORDS = [
    "flat", "vector", "line art", "outline", "color palette", "background",
    "illustration", "cartoon", "watercolor", "3d", "photo",
]


def has_quantity_ko(text):
    """한국어 입력에 '숫자/수관형사 + 단위명사' 형태의 수량 표현이 있는지 판별한다."""
    return bool(QUANTITY_RE_KO.search(text))


def has_number_output(text):
    """영어 출력에 숫자 표현(디지트 또는 숫자 단어)이 있는지 판별한다."""
    if re.search(r"\d", text):
        return True
    tokens = re.findall(r"[a-zA-Z]+", text.lower())
    return any(token in NUMBER_WORDS_EN for token in tokens)


def find_style_words(text, forbidden_words):
    """출력에 섞인 금지 스타일 단어들을 찾아 리스트로 반환한다."""
    lowered = text.lower()
    return [word for word in forbidden_words if word in lowered]


def token_count(text):
    """공백 기준 토큰(단어) 수."""
    return len(text.split())
