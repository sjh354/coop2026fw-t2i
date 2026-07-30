"""TASK-G 마지막 조건: 24개(8카테고리 x 3 VLM 소스) 원본 프롬프트(passthrough.json과 동일)를
ideogram4의 공식 magic-prompt API(docs/prompting.md#magic-prompt, 기본값 ideogram-4-v1 —
Ideogram 자체 호스티드 서비스)로 실제 변환해 image-prompts/rewrite/ideogram_magicprompt.json에
쓴다. scripts/ideogram_guide_captions.py(손으로 스키마를 따라 작성한 버전)와 달리 이번엔 진짜
magic-prompt 호출 결과를 그대로 쓴다 — v257(passthrough)/v258(wan_style)/v259(promptenhancer)/
v260(ideogram_guide)과 같은 실험 설계에서 프롬프트 변환 방식만 다섯 번째로 추가하는 것.

IDEOGRAM_API_KEY는 <repo_root>/.env 또는 환경변수로 공급한다(하드코딩 금지).

    conda run -n t2i-ideogram python -m scripts.ideogram_magic_prompt_captions \
        --out image-prompts/rewrite/ideogram_magicprompt.json
"""
import argparse
import json
import os
import pathlib
import time

ROOT = pathlib.Path(__file__).parent.parent
PROMPTS_JSON = ROOT / "configs" / "benchmarks" / "vlm-prompts.json"
SOURCES = ("claude", "chatgpt", "qwen2.5-vl-7b-instruct")


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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--prompts-json", type=pathlib.Path, default=PROMPTS_JSON)
    ap.add_argument("--out", default=str(ROOT / "image-prompts" / "rewrite" / "ideogram_magicprompt.json"))
    ap.add_argument("--aspect-ratio", default="1:1")
    ap.add_argument("--sleep", type=float, default=1.0, help="호출 사이 대기(초), API rate limit 대비")
    args = ap.parse_args()

    load_env_file(str(ROOT / ".env"))
    api_key = os.environ.get("IDEOGRAM_API_KEY")
    if not api_key:
        raise SystemExit("IDEOGRAM_API_KEY not set (.env or environment)")

    from ideogram4.magic_prompt import Ideogram4MagicPromptV1

    magic = Ideogram4MagicPromptV1(api_key=api_key)

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
            caption = magic.expand(src_entry["prompt"], aspect_ratio=args.aspect_ratio)
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
