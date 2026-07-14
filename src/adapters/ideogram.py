"""ideogram-oss/ideogram4 전용 adapter.

diffusers 호환 모델이 아니라 자체 패키지(ideogram4)를 쓴다 -> generic.py(AutoPipelineForText2Image)로는
체크포인트 키가 하나도 안 맞아 로드 불가. 우리 프롬프트는 이미 완성된 키워드+스타일 문장이라
magic-prompt(LLM으로 구조화 JSON 캡션 확장, API 키 필요) 단계는 건너뛰고 원문을 그대로 넣는다.
"""
import torch
from ideogram4 import PRESETS, Ideogram4Pipeline, Ideogram4PipelineConfig


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
            prompt,
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
