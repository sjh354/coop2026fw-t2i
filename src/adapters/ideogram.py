"""ideogram-oss/ideogram4 전용 adapter.

diffusers 호환 모델이 아니라 자체 패키지(ideogram4)를 쓴다 -> generic.py(AutoPipelineForText2Image)로는
체크포인트 키가 하나도 안 맞아 로드 불가. 이 모델은 구조화 JSON 캡션으로만 학습되어 있어서
plain text를 그대로 넣으면 safety filter 오탐(false positive)이 뜬다 (공식 prompting guide 확인).
magic-prompt(LLM 캡션 확장, API 키 필요)는 안 쓰고, 우리 keyword+style 문장을 최소 스키마
(high_level_description + compositional_deconstruction)에 담아 JSON으로 직렬화해서 넣는다.
"""
import json

import torch
from ideogram4 import PRESETS, Ideogram4Pipeline, Ideogram4PipelineConfig


def _to_caption_json(prompt):
    caption = {
        "high_level_description": prompt,
        "compositional_deconstruction": {
            "background": prompt,
            "elements": [{"type": "obj", "desc": prompt}],
        },
    }
    return json.dumps(caption, separators=(",", ":"), ensure_ascii=False)


def build(cfg):
    pipe = Ideogram4Pipeline.from_pretrained(
        config=Ideogram4PipelineConfig(weights_repo=cfg["repo"]),
        device="cuda",
        dtype=getattr(torch, cfg["dtype"]),
    )
    preset = PRESETS[cfg.get("sampler_preset", "V4_QUALITY_48")]

    def generate(prompt, negative, seed):
        # negative_prompt 미지원 (CFG schedule은 preset에 내장)
        images = pipe(
            _to_caption_json(prompt),
            height=cfg.get("height", 1024),
            width=cfg.get("width", 1024),
            num_steps=preset.num_steps,
            guidance_schedule=preset.guidance_schedule,
            mu=preset.mu,
            std=preset.std,
            seed=seed,
            raise_on_caption_issues=False,
        )
        return images[0]

    return generate
