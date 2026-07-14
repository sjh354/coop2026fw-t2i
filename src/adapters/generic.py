"""AutoPipeline로 커버되는 모델들 (sd35, sana, lumina, qwen, ideogram).

돌려보고 안 되는 모델만 전용 adapter로 분리한다. 미리 쪼개지 말 것.
"""
import torch
from diffusers import AutoPipelineForText2Image

QUANT = {"nf4", "fp8"}


def build(cfg):
    kwargs = {"torch_dtype": getattr(torch, cfg["dtype"])}
    q = cfg.get("quantization")
    if q in QUANT and not cfg.get("prequantized"):
        from diffusers import BitsAndBytesConfig
        kwargs["quantization_config"] = BitsAndBytesConfig(
            load_in_4bit=True, bnb_4bit_quant_type="nf4",
            bnb_4bit_compute_dtype=kwargs["torch_dtype"],
        )

    pipe = AutoPipelineForText2Image.from_pretrained(cfg["repo"], **kwargs)
    if q:
        pipe.enable_model_cpu_offload()   # 양자화해도 안 들어가면 오프로드
    else:
        pipe = pipe.to("cuda")

    def generate(prompt, negative, seed):
        call = dict(
            prompt=prompt,
            num_inference_steps=cfg["steps"],
            guidance_scale=cfg["guidance"],
            generator=torch.Generator("cuda").manual_seed(seed),
        )
        if cfg.get("supports_negative"):
            call["negative_prompt"] = negative
        return pipe(**call).images[0]

    return generate
