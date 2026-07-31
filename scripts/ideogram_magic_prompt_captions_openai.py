"""TASK-G 후속: v264(magic-prompt, ideogram-4-v1 호스티드 API)와 같은 시스템 프롬프트
(ideogram4 공식 magic_prompt_system_prompts/v1.txt)를 OpenAI gpt-4o-mini에 직접 태워
24개 캡션을 변환한다. ideogram-4-v1은 무료 호스티드 서비스라 caption-특화 경량 모델일
가능성이 높아, 비교 기준을 플래그십(gpt-5)이 아니라 가벼운 gpt-4o-mini로 맞춘다.

ideogram4.magic_prompt의 build_messages/reorder_caption_keys/strip_aspect_ratio_and_bboxes를
그대로 재사용해 후처리(스키마 key 순서, aspect_ratio/bbox 제거)를 v264와 동일하게 맞춘다 —
LLM 모델만 바뀌고 나머지 변환 경로는 동일해야 비교가 성립한다.

OPENAI_API_KEY는 <repo_root>/.env 또는 환경변수로 공급한다(하드코딩 금지).

    conda run -n t2i-ideogram python -m scripts.ideogram_magic_prompt_captions_openai \
        --out image-prompts/rewrite/ideogram_magicprompt_openai.json
"""
import argparse
import json
import os
import pathlib
import time

import requests

ROOT = pathlib.Path(__file__).parent.parent
PROMPTS_JSON = ROOT / "configs" / "benchmarks" / "vlm-prompts.json"
SOURCES = ("claude", "chatgpt", "qwen2.5-vl-7b-instruct")
OPENAI_CHAT_URL = "https://api.openai.com/v1/chat/completions"


def load_env_file(path):
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key, value = key.strip(), value.strip()
            if key and key not in os.environ:
                os.environ[key] = value


def openai_expand(messages, api_key, model, *, timeout=120.0):
    resp = requests.post(
        OPENAI_CHAT_URL,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={"model": model, "messages": messages, "max_completion_tokens": 6000},
        timeout=timeout,
    )
    resp.raise_for_status()
    data = resp.json()
    choices = data.get("choices")
    if not choices:
        raise RuntimeError(f"OpenAI returned no choices: {data}")
    content = choices[0]["message"]["content"]
    if not content:
        raise RuntimeError(f"OpenAI returned an empty message: {choices[0]}")
    return content.strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--prompts-json", type=pathlib.Path, default=PROMPTS_JSON)
    ap.add_argument("--out", default=str(ROOT / "image-prompts" / "rewrite" / "ideogram_magicprompt_openai.json"))
    ap.add_argument("--model", default="gpt-4o-mini")
    ap.add_argument("--aspect-ratio", default="1:1")
    ap.add_argument("--sleep", type=float, default=1.0)
    args = ap.parse_args()

    load_env_file(str(ROOT / ".env"))
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise SystemExit("OPENAI_API_KEY not set (.env or environment)")

    from ideogram4.magic_prompt import (
        build_messages,
        reorder_caption_keys,
        strip_aspect_ratio_and_bboxes,
    )

    categories = json.loads(args.prompts_json.read_text(encoding="utf-8"))
    out_items = []
    total = sum(1 for cat in categories for s in SOURCES if cat.get(s))
    done = 0
    for cat in categories:
        entry = {"type": cat["type"]}
        for source in SOURCES:
            src_entry = cat.get(source)
            if not src_entry:
                continue
            messages = build_messages("v1.txt", src_entry["prompt"], args.aspect_ratio)
            raw = openai_expand(messages, api_key, args.model)
            caption_obj = reorder_caption_keys(json.loads(raw))
            caption = strip_aspect_ratio_and_bboxes(
                json.dumps(caption_obj, ensure_ascii=False, separators=(",", ":"))
            )
            entry[source] = {"prompt": caption}
            done += 1
            print(f"[{done}/{total}] {cat['type']} ({source}) -> {len(caption)} chars")
            time.sleep(args.sleep)
        out_items.append(entry)

    out_path = pathlib.Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out_items, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"wrote {len(out_items)} categories -> {out_path}")


if __name__ == "__main__":
    main()
