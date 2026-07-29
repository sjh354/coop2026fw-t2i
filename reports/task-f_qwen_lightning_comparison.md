# TASK-F · qwen-image vs qwen-image-lightning quality/latency/VRAM 비교

생성: 서버 157 (`scripts/sweeps/task_f_qwen_pipeline.sh`). quality(vqascore/csd_target)는 서버 23 채점 완료 후 --score-dir-full/--score-dir-lightning 인자로 재실행해야 채워진다.

| 항목 | qwen-image (full) | qwen-image-lightning |
|---|---|---|
| dtype/quantization | bfloat16/gguf-q5_k_m | bfloat16/gguf-q4_k_s |
| steps | 30 | 8 |
| peak VRAM (torch) GB | 15.53 | 15.53 |
| peak VRAM (nvidia-smi) GB | 16.04 | 16.05 |
| latency p50 (s) | 152.15 | 50.44 |
| latency p90 (s) | 153.62 | 51.27 |
| vqascore (mean, 24 prompts) | 0.8701 | 0.8784 |
| csd_target (mean, 24 prompts) | 0.6319 | 0.6421 |
