import torch
from diffusers import StableDiffusionXLPipeline


def build(cfg):
    pipe = StableDiffusionXLPipeline.from_pretrained(
        cfg["repo"], torch_dtype=getattr(torch, cfg["dtype"]), variant="fp16"
    ).to("cuda")

    def generate(prompt, negative, seed):
        return pipe(
            prompt=prompt,
            negative_prompt=negative,
            num_inference_steps=cfg["steps"],
            guidance_scale=cfg["guidance"],
            generator=torch.Generator("cuda").manual_seed(seed),
        ).images[0]

    return generate
