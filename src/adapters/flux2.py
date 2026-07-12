import torch
from diffusers import Flux2KleinPipeline


def build(cfg):
    pipe = Flux2KleinPipeline.from_pretrained(
        cfg["repo"], torch_dtype=getattr(torch, cfg["dtype"])
    ).to("cuda")

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
