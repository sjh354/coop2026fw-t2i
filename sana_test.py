import torch
from diffusers import SanaPipeline

pipe = SanaPipeline.from_pretrained('Efficient-Large-Model/Sana_1600M_1024px_diffusers', torch_dtype=torch.bfloat16).to('cuda')

prompt = 'an apple, flat educational vector illustration, textbook infographic style, limited flat color palette, crisp geometric shapes, thin clean outline, clear readable silhouette, centered single subject on plain light background, no gradient, no shading, no photorealism'
neg = 'photorealistic, 3d render, photograph, gradient, soft shading, drop shadow, heavy black outline, painterly, textured, busy background, cluttered, text, letters, watermark, signature, grainy, noisy'

img = pipe(prompt=prompt, negative_prompt=neg, num_inference_steps=20, guidance_scale=4.5,
           complex_human_instruction=[], generator=torch.Generator('cuda').manual_seed(0)).images[0]
img.save('/tmp/sana_no_chi_apple.png')
print('SAVED_OK')
