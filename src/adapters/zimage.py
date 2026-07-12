import torch
from diffusers import AutoPipelineForText2Image


def build(cfg):
    # Z-Image는 diffusers 지원 상태가 유동적. 실패하면 공식 레포
    # (github.com/Tongyi-MAI/Z-Image) 인퍼런스 코드로 갈아끼울 것.
    pipe = AutoPipelineForText2Image.from_pretrained(
        cfg["repo"], torch_dtype=getattr(torch, cfg["dtype"]), trust_remote_code=True
    ).to("cuda")

    def generate(prompt, negative, seed):
        return pipe(
            prompt=prompt,
            num_inference_steps=cfg["steps"],
            guidance_scale=cfg["guidance"],
            generator=torch.Generator("cuda").manual_seed(seed),
        ).images[0]

    return generate
