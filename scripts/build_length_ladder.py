"""TASK-I 파트 2: 순수 길이 효과를 보기 위한 3단 사다리 중 "medium" 조건만 새로 만든다.

short(=passthrough, 이미 v250에 있음)과 long(=promptenhancer_cn 전체, 이미 v262에 있음)
사이에 낄 "medium" 조건이 없어서, promptenhancer_cn의 리라이팅 결과를 문장 단위로 앞에서부터
살리고 뒤를 잘라 원본과 전체 리라이팅의 중간 지점 단어 수로 만든다. structural 카테고리
4개(counting/attribute-binding 실패축)만 대상으로 한다 — TASK-I 파트 1이 이미 이 4개에서
신호를 봤으므로 사다리도 여기만 좁혀서 본다.

    python -m scripts.build_length_ladder \
        --in image-prompts/rewrite/promptenhancer_cn.json \
        --out image-prompts/rewrite/promptenhancer_cn_medium.json
"""
import argparse
import json
import pathlib
import re

STRUCTURAL = {"Structured Worksheet Template", "Data Visualization Chart",
              "Labeled Science Diagram", "Geometric Shape Set"}

SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")


def truncate_to_words(text, target_words):
    """문장 단위로 앞에서부터 누적, target_words를 처음 넘기는 문장까지 포함."""
    sentences = SENTENCE_RE.split(text.strip())
    kept, word_count = [], 0
    for sent in sentences:
        kept.append(sent)
        word_count += len(sent.split())
        if word_count >= target_words:
            break
    return " ".join(kept)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="in_path", required=True, type=pathlib.Path)
    ap.add_argument("--out", dest="out_path", required=True, type=pathlib.Path)
    args = ap.parse_args()

    categories = json.loads(args.in_path.read_text(encoding="utf-8"))
    kept_categories = []
    for cat in categories:
        if cat["type"] not in STRUCTURAL:
            continue
        for source, entry in cat.items():
            if source == "type" or not isinstance(entry, dict):
                continue
            orig_words = len(entry["prompt_original"].split())
            long_words = len(entry["prompt"].split())
            target = orig_words + round(0.5 * (long_words - orig_words))
            medium = truncate_to_words(entry["prompt"], target)
            print(f"{cat['type']} ({source}): orig={orig_words}w long={long_words}w "
                  f"target={target}w -> medium={len(medium.split())}w")
            entry["prompt_full_rewrite"] = entry["prompt"]
            entry["prompt"] = medium
            entry["backend"] = "promptenhancer_cn_medium"
        kept_categories.append(cat)

    args.out_path.parent.mkdir(parents=True, exist_ok=True)
    args.out_path.write_text(json.dumps(kept_categories, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"저장: {args.out_path} ({len(kept_categories)}개 카테고리 x 3소스 = "
          f"{sum(len(c) - 1 for c in kept_categories)}개 프롬프트)")


if __name__ == "__main__":
    main()
