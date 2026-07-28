"""TASK-G: Ideogram-4(셀프호스팅 nf4, ideogram4 패키지)의 block/caption-issue 재현율을 잰다.

배경 정정: TASK-G 원안은 API의 magic-prompt(자동 프롬프트 확장)가 원인이라고 가정했지만,
configs/models/ideogram-4.yaml 기준 이 프로젝트의 ideogram-4는 API가 아니라 로컬 nf4 가중치를
직접 로드해서 쓴다 — magic-prompt 자체가 없다. src/adapters/ideogram.py는 이미 모든 프롬프트를
JSON caption schema(high_level_description + compositional_deconstruction)로 감싸서 넣고
raise_on_caption_issues=False로 예외를 억제하는 상태다. 이 스크립트가 검증하는 것은
"plain text vs JSON caption format이 실제로 caption-issue(=block) 발생률에 차이를 만드는가"
(TASK-G 3번 항목이 만들어놓기만 하고 측정한 적은 없음)와 "같은 프롬프트가 여러 번 호출해도
결정적으로 같은 결과를 내는가"(원안의 검증 기준을 로컬 버전에 맞게 재적용) 두 가지다.

    conda run -n t2i-ideogram python -m scripts.ideogram_probe \
        --config configs/models/ideogram-4.yaml \
        --prompts-json configs/benchmarks/vlm-prompts.json \
        --trials 3 \
        --out bench/ideogram_probe/block_rate.csv
"""
import argparse
import csv
import json
import pathlib
import sys
import time

import torch
import yaml
from ideogram4 import PRESETS, Ideogram4Pipeline, Ideogram4PipelineConfig

ROOT = pathlib.Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "src"))
from adapters.ideogram import _to_caption_json  # noqa: E402

PROMPTS_JSON = ROOT / "configs" / "benchmarks" / "vlm-prompts.json"
CSV_FIELDS = [
    "prompt_id", "type", "source", "caption_format", "trial",
    "blocked", "error_message", "latency_s",
]


def load_items(prompts_json):
    categories = json.loads(pathlib.Path(prompts_json).read_text(encoding="utf-8"))
    items = []
    for cat in categories:
        for source in ("claude", "chatgpt", "qwen2.5-vl-7b-instruct"):
            entry = cat.get(source)
            if entry:
                items.append({"type": cat["type"], "source": source, "prompt": entry["prompt"]})
    return items


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=str(ROOT / "configs" / "models" / "ideogram-4.yaml"))
    ap.add_argument("--prompts-json", type=pathlib.Path, default=PROMPTS_JSON)
    ap.add_argument("--trials", type=int, default=3)
    ap.add_argument("--out", default=str(ROOT / "bench" / "ideogram_probe" / "block_rate.csv"))
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()

    cfg = yaml.safe_load(pathlib.Path(args.config).read_text(encoding="utf-8"))
    items = load_items(args.prompts_json)

    pipe = Ideogram4Pipeline.from_pretrained(
        config=Ideogram4PipelineConfig(weights_repo=cfg["repo"]),
        device="cuda",
        dtype=getattr(torch, cfg["dtype"]),
    )
    preset = PRESETS[cfg.get("sampler_preset", "V4_QUALITY_48")]

    out_path = pathlib.Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    write_header = not out_path.exists()
    f = out_path.open("a", newline="", encoding="utf-8")
    writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
    if write_header:
        writer.writeheader()

    total = len(items) * 2 * args.trials
    done = 0
    for i, it in enumerate(items):
        for caption_format in ("plain", "json"):
            caption = it["prompt"] if caption_format == "plain" else _to_caption_json(it["prompt"])
            for trial in range(args.trials):
                blocked, error_message = False, ""
                t0 = time.time()
                try:
                    pipe(
                        caption,
                        height=cfg.get("height", 1024),
                        width=cfg.get("width", 1024),
                        num_steps=preset.num_steps,
                        guidance_schedule=preset.guidance_schedule,
                        mu=preset.mu,
                        std=preset.std,
                        seed=args.seed,
                        raise_on_caption_issues=True,
                    )
                except Exception as e:  # noqa: BLE001 — caption-issue 예외 타입이 패키지마다 다를 수 있어 광범위하게 잡는다
                    blocked = True
                    error_message = str(e)[:300]
                latency_s = round(time.time() - t0, 2)

                writer.writerow({
                    "prompt_id": i,
                    "type": it["type"],
                    "source": it["source"],
                    "caption_format": caption_format,
                    "trial": trial,
                    "blocked": blocked,
                    "error_message": error_message,
                    "latency_s": latency_s,
                })
                f.flush()
                done += 1
                print(f"[{done}/{total}] prompt={i} format={caption_format} trial={trial} "
                      f"blocked={blocked} ({latency_s}s)")

    f.close()
    print(f"done. csv: {out_path}")


if __name__ == "__main__":
    main()
