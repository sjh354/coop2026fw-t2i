"""ideogram-oss/ideogram4 전용 adapter.

diffusers 호환 모델이 아니라 자체 패키지(ideogram4)를 쓴다 -> generic.py(AutoPipelineForText2Image)로는
체크포인트 키가 하나도 안 맞아 로드 불가. 이 모델은 구조화 JSON 캡션으로만 학습되어 있고,
설치된 패키지 소스(ideogram4/pipeline_ideogram4.py) 확인 결과 Hive 기반 실제 safety filter는
로컬 self-host 경로에 아예 연결돼 있지 않다(ideogram4/safety.py의 moderate_prompt/moderate_image는
API 키가 필요한 독립 함수이고 파이프라인이 호출하지 않음) — plain text를 넣었을 때 나던 "block"은
CaptionVerifier가 non-JSON을 감지해 raise_on_caption_issues=True 기본값에서 ValueError를 던진
것이었다. magic-prompt(LLM 캡션 확장, API 키 필요)는 안 쓰고, raise_on_caption_issues=False로
예외는 억제하되, 우리 keyword+style 문장을 최소 스키마(high_level_description +
compositional_deconstruction)에 담아 JSON으로 직렬화해서 넣는다.
"""
import json

import torch
from ideogram4 import PRESETS, Ideogram4Pipeline, Ideogram4PipelineConfig


def _to_caption_json(prompt):
    """plain text는 최소 스키마로 감싸고, 이미 유효한 캡션 JSON이면 그대로(재직렬화만) 통과시킨다.

    후자는 scripts/ideogram_guide_captions.py가 만든, 공식 prompting guide 스키마를 제대로
    따르는 캡션(style_description + type:"text" 요소 포함)을 이중으로 감싸지 않기 위함이다.
    """
    try:
        caption = json.loads(prompt)
        if not isinstance(caption, dict):
            raise ValueError
    except (json.JSONDecodeError, ValueError):
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
