"""LLM provider 얇은 추상화. rewrite()의 opts.llm_fn으로 통째로 교체 가능하다."""


def call_anthropic(system, user, *, model):
    """Anthropic Messages API 호출. ANTHROPIC_API_KEY 환경변수가 필요하다."""
    try:
        import anthropic
    except ImportError as exc:
        raise RuntimeError(
            "anthropic 패키지가 없습니다. `pip install anthropic` 후 ANTHROPIC_API_KEY를 "
            "설정하거나, opts.llm_fn으로 다른 provider를 주입하세요."
        ) from exc

    client = anthropic.Anthropic()
    response = client.messages.create(
        model=model,
        max_tokens=300,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return response.content[0].text


def call_openai(system, user, *, model):
    """OpenAI Chat Completions API 호출. OPENAI_API_KEY 환경변수가 필요하다."""
    try:
        import openai
    except ImportError as exc:
        raise RuntimeError(
            "openai 패키지가 없습니다. `pip install openai` 후 OPENAI_API_KEY를 "
            "설정하거나, opts.llm_fn으로 다른 provider를 주입하세요."
        ) from exc

    client = openai.OpenAI()
    response = client.chat.completions.create(
        model=model,
        max_completion_tokens=900,
        reasoning_effort="low",
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )
    return response.choices[0].message.content
