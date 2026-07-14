"""AutoPipeline로 커버되는 모델들 (sd35, sana, lumina, qwen, ideogram).

돌려보고 안 되는 모델만 전용 adapter로 분리한다. 미리 쪼개지 말 것.
"""
import torch
from diffusers import AutoPipelineForText2Image

QUANT = {"nf4", "fp8"}


def _load_gguf_transformer(cfg, dtype):
    """gguf_repo/gguf_file이 지정된 경우, 원본 bf16 transformer 대신 GGUF 양자화본을 받는다.
    (transformer만 GGUF로 교체 -> text_encoder/vae는 원본 repo에서 그대로, 전체 다운로드량 절감)
    """
    import diffusers
    from diffusers import GGUFQuantizationConfig
    from huggingface_hub import hf_hub_download

    transformer_cls = getattr(diffusers, cfg["gguf_transformer_class"])
    gguf_path = hf_hub_download(repo_id=cfg["gguf_repo"], filename=cfg["gguf_file"])
    return transformer_cls.from_single_file(
        gguf_path,
        quantization_config=GGUFQuantizationConfig(compute_dtype=dtype),
        torch_dtype=dtype,
    )


def build(cfg):
    dtype = getattr(torch, cfg["dtype"])
    kwargs = {"torch_dtype": dtype}
    q = cfg.get("quantization")
    if cfg.get("gguf_repo"):
        kwargs["transformer"] = _load_gguf_transformer(cfg, dtype)
    elif q in QUANT and not cfg.get("prequantized"):
        from diffusers import PipelineQuantizationConfig
        kwargs["quantization_config"] = PipelineQuantizationConfig(
            quant_backend="bitsandbytes_4bit",
            quant_kwargs={
                "load_in_4bit": True, "bnb_4bit_quant_type": "nf4",
                "bnb_4bit_compute_dtype": dtype,
            },
            components_to_quantize=["transformer"],
        )

    pipe = AutoPipelineForText2Image.from_pretrained(cfg["repo"], **kwargs)
    if q or cfg.get("gguf_repo"):
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
