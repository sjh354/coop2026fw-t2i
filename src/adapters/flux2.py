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
    offload = cfg.get("offload")
    if q or offload == "full":
        pipe.enable_model_cpu_offload()
    elif offload == "text_encoder":
        pipe.transformer.to("cuda")
        pipe.vae.to("cuda")
        pipe.text_encoder.to("cpu")
        # self.device는 컴포넌트를 알파벳순(text_encoder가 transformer/vae보다 먼저)으로
        # 훑어 첫 nn.Module의 device를 반환한다. text_encoder를 cpu에 두면 diffusion 중
        # 실행 디바이스가 cpu로 오판되므로 cuda로 고정한다.
        type(pipe).device = property(lambda self: torch.device("cuda"))
    else:
        pipe = pipe.to("cuda")

    def generate(prompt, negative, seed):
        # klein은 CFG를 안 쓴다 -> negative는 무시됨 (generate.py가 경고 출력)
        gen_kwargs = dict(
            height=1024,
            width=1024,
            num_inference_steps=cfg["steps"],
            guidance_scale=cfg["guidance"],
            generator=torch.Generator("cuda").manual_seed(seed),
        )
        if offload == "text_encoder":
            pipe.text_encoder.to("cuda")
            prompt_embeds = pipe.encode_prompt(prompt=prompt, device="cuda")[0]
            pipe.text_encoder.to("cpu")
            torch.cuda.empty_cache()
            return pipe(prompt_embeds=prompt_embeds, **gen_kwargs).images[0]
        return pipe(prompt=prompt, **gen_kwargs).images[0]

    return generate
