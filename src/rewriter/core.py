"""한국어 교사 입력 -> 영어 T2I 콘텐츠 프롬프트 rewriter.

    from src.rewriter import rewrite, RewriteOptions
    result = rewrite("사과 세 개가 담긴 바구니")
    result["prompt_en"]

스타일 문구는 이 모듈이 만들지 않는다 — 별도 스타일 프리셋(configs/experiments,
configs/dialects)이 시스템 레벨에서 뒤에 붙인다. rewriter-prompt.md가 시스템
프롬프트의 single source of truth이고, 이 모듈은 그걸 읽어서 LLM에 넘길 뿐이다.
"""
import functools
import pathlib
from dataclasses import dataclass
from typing import Callable, Optional

from .checks import (
    STYLE_FORBIDDEN_WORDS, find_style_words, has_number_output,
    has_quantity_ko, token_count,
)
from .providers import call_openai

PROMPT_PATH = pathlib.Path(__file__).parent.parent.parent / "rewriter-prompt.md"
DEFAULT_MODEL = "gpt-5"
DEFAULT_MAX_WORDS = 40


@dataclass
class RewriteOptions:
    """rewrite() 옵션. lang은 현재 'ko'만 지원 — 'es'는 자리만 마련해뒀다(미구현)."""
    lang: str = "ko"
    max_words: int = DEFAULT_MAX_WORDS
    model: str = DEFAULT_MODEL
    llm_fn: Optional[Callable[[str, str], str]] = None


def _load_system_prompt(max_words):
    """rewriter-prompt.md를 읽어 {MAX_WORDS}를 채운 시스템 프롬프트 문자열을 반환한다."""
    template = PROMPT_PATH.read_text(encoding="utf-8")
    return template.replace("{MAX_WORDS}", str(max_words))


def _check_violations(prompt_ko, prompt_en, max_words):
    """자동 체크(수량/금지어/길이) 위반 사유 문자열 리스트를 반환한다."""
    violations = []
    if has_quantity_ko(prompt_ko) and not has_number_output(prompt_en):
        violations.append("입력에 수량 표현이 있으나 출력에 숫자가 없습니다. 개수를 명시적 숫자로 쓰세요.")
    style_hits = find_style_words(prompt_en, STYLE_FORBIDDEN_WORDS)
    if style_hits:
        violations.append(f"금지 단어 사용: {', '.join(style_hits)}. 해당 구절을 삭제하세요(대체어로 바꾸지 마세요).")
    words = token_count(prompt_en)
    if words > max_words:
        violations.append(f"{max_words}단어 제한 초과 ({words}단어). 형용사/부차 디테일을 삭제해 줄이세요.")
    return violations


def _build_retry_message(prompt_ko, prompt_en, violations):
    """직전 출력의 위반 사유를 피드백으로 넣은 재생성용 user 메시지를 만든다."""
    reasons = "\n".join(f"- {v}" for v in violations)
    return (
        f"{prompt_ko}\n\n"
        f"직전 출력이 다음 규칙을 위반했습니다. 같은 내용을 유지하며 다시 작성하세요.\n"
        f"직전 출력: {prompt_en}\n{reasons}"
    )


def rewrite(prompt_ko, opts=None):
    """한국어 입력을 영어 콘텐츠 프롬프트로 변환한다. {prompt_en, meta}를 반환한다.

    자동 체크(수량/금지어/길이)에 실패하면 위반 사유를 피드백으로 넣어 최대
    1회 재생성한다. meta['retried']에 재시도 여부가 기록된다.
    """
    opts = opts or RewriteOptions()
    if opts.lang != "ko":
        raise NotImplementedError(f"lang={opts.lang!r} is not supported yet (only 'ko')")

    system = _load_system_prompt(opts.max_words)
    llm_fn = opts.llm_fn or functools.partial(call_openai, model=opts.model)
    prompt_en = llm_fn(system, prompt_ko).strip()

    retried = False
    violations = _check_violations(prompt_ko, prompt_en, opts.max_words)
    if violations:
        retried = True
        retry_message = _build_retry_message(prompt_ko, prompt_en, violations)
        prompt_en = llm_fn(system, retry_message).strip()

    return {
        "prompt_en": prompt_en,
        "meta": {
            "lang": opts.lang, "max_words": opts.max_words,
            "model": opts.model, "retried": retried,
        },
    }
