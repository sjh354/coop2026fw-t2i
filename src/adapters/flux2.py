import torch
from diffusers import Flux2KleinPipeline

QUANT = {"nf4", "fp8"}


def build(cfg):
    kwargs = {"torch_dtype": getattr(torch, cfg["dtype"])}
    q = cfg.get("quantization")
    if q in QUANT and not cfg.get("prequantized"):
        from diffusers import PipelineQuantizationConfig
        kwargs["quantization_config"] = PipelineQuantizationConfig(
            quant_backend="bitsandbytes_4bit",
            quant_kwargs={
                "load_in_4bit": True, "bnb_4bit_quant_type": "nf4",
                "bnb_4bit_compute_dtype": kwargs["torch_dtype"],
            },
            components_to_quantize=["transformer"],
        )

    pipe = Flux2KleinPipeline.from_pretrained(cfg["repo"], **kwargs)
    if q:
        pipe.enable_model_cpu_offload()
    else:
        pipe = pipe.to("cuda")

    def generate(prompt, negative, seed):
        # klein은 CFG를 안 쓴다 -> negative는 무시됨 (generate.py가 경고 출력)
        return pipe(
            prompt=prompt,
            height=1024,
            width=1024,
            num_inference_steps=cfg["steps"],
            guidance_scale=cfg["guidance"],
            generator=torch.Generator("cuda").manual_seed(seed),
        ).images[0]

    return generate
