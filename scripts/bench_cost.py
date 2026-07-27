"""TASK-D: 모델 하나의 VRAM/latency를 실측해 CSV 한 줄로 기록한다.

    conda run -n t2i python -m scripts.bench_cost \
        --config configs/models/flux2-klein-4b-nf4.yaml \
        --prompts configs/keywords/basic30.yaml \
        --out bench/cost/vram_latency.csv

워밍업 2장은 버리고 그 다음 10장으로 p50/p90 latency를 잰다.
peak VRAM은 torch.cuda.max_memory_allocated()와 nvidia-smi 실측(폴링 최대치)
둘 다 기록한다 — allocator 밖의 CUDA context/cuDNN workspace 때문에 값이 다르다.
같은 시드(--seed + 인덱스)로 생성한 이미지를 --img-out에 저장해 조건 간
육안 비교가 가능하게 한다.
"""
import argparse
import csv
import os
import pathlib
import re
import subprocess
import sys
import threading
import time

import numpy as np
import torch
import yaml
from PIL import PngImagePlugin

ROOT = pathlib.Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "src"))
import adapters  # noqa: E402

CSV_FIELDS = [
    "model", "dtype", "quantization", "num_inference_steps", "resolution",
    "peak_vram_gb_torch", "peak_vram_gb_smi", "model_load_s",
    "latency_p50_s", "latency_p90_s", "images_measured",
]


def load_yaml(path):
    return yaml.safe_load(pathlib.Path(path).read_text(encoding="utf-8"))


def slug(text):
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def check_gpu_contention(gpu_index):
    out = subprocess.run(
        ["nvidia-smi", f"--id={gpu_index}", "--query-compute-apps=pid",
         "--format=csv,noheader"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    other_pids = [p for p in out.splitlines() if p.strip() and int(p) != os.getpid()]
    if other_pids:
        print(f"[warn] GPU {gpu_index}를 다른 프로세스({', '.join(other_pids)})가 "
              f"같이 쓰고 있다 — VRAM 실측이 오염될 수 있다.")


class SmiPeakMonitor:
    """nvidia-smi memory.used를 폴링해서 최댓값을 추적한다."""

    def __init__(self, gpu_index, interval=0.5):
        self.gpu_index = gpu_index
        self.interval = interval
        self.peak_mb = 0
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def _poll_once(self):
        out = subprocess.run(
            ["nvidia-smi", f"--id={self.gpu_index}",
             "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
        self.peak_mb = max(self.peak_mb, int(out))

    def _run(self):
        while not self._stop.is_set():
            self._poll_once()
            self._stop.wait(self.interval)

    def __enter__(self):
        self._poll_once()
        self._thread.start()
        return self

    def __exit__(self, *exc):
        self._stop.set()
        self._thread.join()
        self._poll_once()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True, help="configs/models/<name>.yaml")
    ap.add_argument("--prompts", required=True, help="configs/keywords/<name>.yaml")
    ap.add_argument("--out", required=True, help="결과를 append할 CSV 경로")
    ap.add_argument("--warmup", type=int, default=2)
    ap.add_argument("--measure", type=int, default=10)
    ap.add_argument("--seed", type=int, default=42, help="prompt별 seed = --seed + 인덱스")
    ap.add_argument("--resolution", default="1024x1024")
    ap.add_argument("--gpu-index", type=int, default=0)
    ap.add_argument("--img-out", default=None,
                     help="측정한 이미지를 저장할 디렉토리 (기본: bench/cost_images/<model>)")
    args = ap.parse_args()

    cfg = load_yaml(args.config)
    prompts = load_yaml(args.prompts)["keywords"]
    needed = args.warmup + args.measure
    if len(prompts) < needed:
        sys.exit(f"[bench_cost] --prompts에 프롬프트가 {len(prompts)}개뿐인데 "
                  f"warmup+measure={needed}개 필요하다.")
    prompts = prompts[:needed]

    img_out = pathlib.Path(args.img_out) if args.img_out else ROOT / "bench" / "cost_images" / cfg["name"]
    img_out.mkdir(parents=True, exist_ok=True)

    check_gpu_contention(args.gpu_index)

    torch.cuda.reset_peak_memory_stats()
    with SmiPeakMonitor(args.gpu_index) as smi:
        t0 = time.time()
        generate = adapters.load(cfg)
        model_load_s = time.time() - t0

        for i, prompt in enumerate(prompts[:args.warmup]):
            generate(prompt, "", args.seed + i)

        latencies = []
        for i, prompt in enumerate(prompts[args.warmup:], start=args.warmup):
            t0 = time.time()
            image = generate(prompt, "", args.seed + i)
            latencies.append(time.time() - t0)

            info = PngImagePlugin.PngInfo()
            for k, v in [("prompt", prompt), ("seed", args.seed + i), ("model", cfg["name"])]:
                info.add_text(k, str(v))
            image.save(img_out / f"{i - args.warmup:02d}_{slug(prompt)}.png", pnginfo=info)

    peak_vram_gb_torch = round(torch.cuda.max_memory_allocated() / 1024**3, 2)
    peak_vram_gb_smi = round(smi.peak_mb / 1024, 2)

    row = {
        "model": cfg["name"],
        "dtype": cfg["dtype"],
        "quantization": cfg.get("quantization") or "none",
        "num_inference_steps": cfg["steps"],
        "resolution": cfg.get("resolution", args.resolution),
        "peak_vram_gb_torch": peak_vram_gb_torch,
        "peak_vram_gb_smi": peak_vram_gb_smi,
        "model_load_s": round(model_load_s, 2),
        "latency_p50_s": round(float(np.percentile(latencies, 50)), 2),
        "latency_p90_s": round(float(np.percentile(latencies, 90)), 2),
        "images_measured": len(latencies),
    }

    out_path = pathlib.Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    write_header = not out_path.exists()
    with out_path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        if write_header:
            writer.writeheader()
        writer.writerow(row)

    print(f"done. {row}")
    print(f"images: {img_out}")


if __name__ == "__main__":
    main()
