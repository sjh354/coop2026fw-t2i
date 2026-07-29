"""프롬프트 리라이팅 backend 비교 harness (TASK-E).

기존 rewriter(src/rewriter)는 한국어 교사 입력 -> 영어 콘텐츠 프롬프트를 만드는
API(OpenAI) 기반 리라이터다. 이 스크립트는 그 자리를 대체할 수 있는 로컬 LLM
backend 두 개를 configs/benchmarks/vlm-prompts.json의 완성된 영어 프롬프트에
적용해, 더 정교한 리라이팅이 이미지 품질(TASK-B spec 통과율)을 올리는지 본다.

backend:
  passthrough    - 대조군, 아무것도 하지 않음
  wan_style      - Wan2.2 wan/utils/prompt_extend.py의 로컬 Qwen 확장 인터페이스
                   구조를 차용. 원본 시스템 프롬프트는 영상 생성용(카메라워크/
                   움직임 어휘를 강제)이라 내용은 새로 쓴 system_prompt로 교체.
  promptenhancer - Tencent PromptEnhancer-7B (HunyuanImage-2.1/reprompt, CVPR
                   2026). trust_remote_code=True 필요. 기본 시스템 프롬프트가
                   중국어라 반드시 --system-prompt로 교체해야 한다. 공식
                   추론 코드의 enable_thinking 기본값은 False.

    python -m scripts.rewrite --in configs/benchmarks/vlm-prompts.json \
        --backend passthrough --out image-prompts/rewrite/passthrough.json
    python -m scripts.rewrite --in configs/benchmarks/vlm-prompts.json \
        --backend wan_style --system-prompt configs/rewrite/wan_style.txt \
        --out image-prompts/rewrite/wan_style.json
    python -m scripts.rewrite --in configs/benchmarks/vlm-prompts.json \
        --backend promptenhancer --system-prompt configs/rewrite/promptenhancer.txt \
        --out image-prompts/rewrite/promptenhancer.json --enable-thinking
"""
import argparse
import json
import pathlib

SOURCES = ("claude", "chatgpt", "qwen2.5-vl-7b-instruct")

PHOTO_WORDS = [
    "photorealistic", "photo-realistic", "cinematic", "8k", "4k", "artstation",
    "hyperrealistic", "hyper-realistic", "octane render", "unreal engine",
    "dslr", "bokeh", "studio lighting", "ray tracing", "raytraced", "photo",
]

NEGATION_CUES = ["no ", "not ", "non-", "avoid", "free of", "lack of",
                  "without", "devoid"]
NEGATION_WINDOW = 40


def count_photo_words(text):
    """리라이팅 출력에 섞인 사진/영상 계열 어휘를 찾아 리스트로 반환한다.

    "avoiding photorealistic qualities"처럼 금지 문맥에서 나온 매칭은
    실질 leak이 아니므로, 매칭 앞 NEGATION_WINDOW자 안에 부정 표현이 있으면 제외한다.
    """
    lowered = text.lower()
    hits = []
    for w in PHOTO_WORDS:
        idx = lowered.find(w)
        if idx == -1:
            continue
        context = lowered[max(0, idx - NEGATION_WINDOW):idx]
        if any(cue in context for cue in NEGATION_CUES):
            continue
        hits.append(w)
    return hits


def build_rewrite_fn(backend, system_prompt, enable_thinking):
    """backend별로 모델을 한 번만 로드하고, prompt -> rewritten prompt 함수를 반환한다."""
    if backend == "passthrough":
        return lambda prompt: prompt

    if backend == "wan_style":
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        model_id = "Qwen/Qwen2.5-7B-Instruct"
        tok = AutoTokenizer.from_pretrained(model_id)
        model = AutoModelForCausalLM.from_pretrained(
            model_id, torch_dtype=torch.bfloat16, device_map="cuda")

        def rewrite_fn(prompt):
            messages = [{"role": "system", "content": system_prompt},
                        {"role": "user", "content": prompt}]
            text = tok.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
            inputs = tok(text, return_tensors="pt").to(model.device)
            out = model.generate(**inputs, max_new_tokens=200, do_sample=False)
            return tok.decode(out[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True).strip()

        return rewrite_fn

    if backend == "promptenhancer":
        import torch
        from huggingface_hub import snapshot_download
        from transformers import AutoModelForCausalLM, AutoTokenizer

        # trust_remote_code 커스텀 코드(tokenization_hy.py)는 리포 루트에서만 찾으므로
        # subfolder= 인자로는 안 되고, reprompt/ 하위를 로컬로 통째로 받아 그 경로에서 로드해야 한다.
        local_dir = snapshot_download(
            "tencent/HunyuanImage-2.1", allow_patterns=["reprompt/*"])
        model_path = f"{local_dir}/reprompt"
        tok = AutoTokenizer.from_pretrained(model_path, trust_remote_code=True)
        model = AutoModelForCausalLM.from_pretrained(
            model_path, trust_remote_code=True,
            torch_dtype=torch.bfloat16, device_map="cuda")

        def rewrite_fn(prompt):
            messages = [{"role": "system", "content": system_prompt},
                        {"role": "user", "content": prompt}]
            text = tok.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=True,
                enable_thinking=enable_thinking)
            inputs = tok(text, return_tensors="pt").to(model.device)
            max_new_tokens = 1024 if enable_thinking else 512
            out = model.generate(**inputs, max_new_tokens=max_new_tokens, do_sample=False)
            raw = tok.decode(out[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True).strip()
            if "<answer>" in raw and "</answer>" in raw:
                return raw.split("<answer>", 1)[1].split("</answer>", 1)[0].strip()
            if "</think>" in raw:
                return raw.split("</think>", 1)[1].strip()
            return prompt

        return rewrite_fn

    raise ValueError(f"unknown backend: {backend}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="in_path", required=True, help="입력 프롬프트 JSON (vlm-prompts.json 형식)")
    ap.add_argument("--backend", required=True, choices=["passthrough", "wan_style", "promptenhancer"])
    ap.add_argument("--system-prompt", help="passthrough 외 backend는 필수 (configs/rewrite/*.txt)")
    ap.add_argument("--out", required=True)
    ap.add_argument("--enable-thinking", action="store_true",
                     help="promptenhancer 전용. 공식 기본값은 False, 두 설정 비교용")
    args = ap.parse_args()

    if args.backend != "passthrough" and not args.system_prompt:
        ap.error("--backend wan_style/promptenhancer는 --system-prompt가 필요합니다")

    system_prompt = (pathlib.Path(args.system_prompt).read_text(encoding="utf-8")
                      if args.system_prompt else "")
    categories = json.loads(pathlib.Path(args.in_path).read_text(encoding="utf-8"))
    rewrite_fn = build_rewrite_fn(args.backend, system_prompt, args.enable_thinking)

    photo_hits_total = 0
    preview_count = 0
    for cat in categories:
        for source in SOURCES:
            entry = cat.get(source)
            if not entry:
                continue
            original = entry["prompt"]
            rewritten = rewrite_fn(original)
            entry["prompt_original"] = original
            entry["prompt"] = rewritten
            entry["backend"] = args.backend

            hits = count_photo_words(rewritten)
            photo_hits_total += len(hits)
            if preview_count < 3:
                print(f"--- {cat['type']} ({source}) ---")
                print(f"[원본] {original}")
                print(f"[{args.backend}] {rewritten}")
                if hits:
                    print(f"[photo-word 검출] {hits}")
                print()
                preview_count += 1

    out_path = pathlib.Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(categories, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"backend={args.backend}  photo-word 검출 총합={photo_hits_total} (24개 프롬프트 중)")
    print(f"저장: {out_path}")


if __name__ == "__main__":
    main()
