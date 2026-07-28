"""TASK-G: Ideogram-4(셀프호스팅 nf4, ideogram4 패키지)의 block/caption-issue 재현율을 잰다.

배경 정정(2차): 설치된 패키지 소스(ideogram4/pipeline_ideogram4.py, ideogram4/safety.py) 확인 결과
Hive 기반 실제 safety filter는 self-host 경로에 연결돼 있지 않다 — moderate_prompt/moderate_image는
API 키가 필요한 독립 함수이고 파이프라인이 호출하지 않는다. 과거 관찰된 "block"은 CaptionVerifier가
non-JSON/스키마 위반 캡션을 감지해 raise_on_caption_issues=True 기본값에서 ValueError를 던진 것으로
설명된다(src/adapters/ideogram.py는 이미 raise_on_caption_issues=False로 이걸 억제 중). 공식 문서는
또한 실제 NSFW 차단 시 예외가 아니라 "Image blocked by safety filter" 텍스트가 박힌 회색 이미지를
반환한다고 명시하므로, 예외 발생 여부만으로는 이 케이스를 못 잡는다 — 그래서 이미지의 픽셀 분산도
같이 본다.

이 스크립트가 실제로 재는 것 두 가지:
1. 캡션 포맷(plain / naive-json(현재 프로덕션 방식) / guide(공식 스키마 완전 준수, TASK-G
   scripts/ideogram_guide_captions.py 산출물))별로 (a) CaptionVerifier 경고 개수(GPU 불필요,
   정적 체크) (b) 실제 pipe() 호출의 예외 여부 (c) 반환 이미지가 근사 단색(회색 차단 화면 의심)인지.
2. 같은 프롬프트를 여러 번 호출해도 결정적으로 같은 결과를 내는가(원안의 검증 기준).

48-step V4_QUALITY_48 프리셋 기준 24개 x 3 포맷 x N trial은 비용이 크므로 --limit/--trials로
파일럿 규모부터 돌릴 것.

    conda run -n t2i-ideogram python -m scripts.ideogram_probe \
        --config configs/models/ideogram-4.yaml \
        --guide-prompts-json image-prompts/rewrite/ideogram_guide.json \
        --limit 6 --trials 2 \
        --out bench/ideogram_probe/block_rate_pilot.csv
"""
import argparse
import csv
import json
import pathlib
import sys
import time

import numpy as np
import torch
import yaml
from ideogram4 import PRESETS, Ideogram4Pipeline, Ideogram4PipelineConfig
from ideogram4.caption_verifier import CaptionVerifier

ROOT = pathlib.Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "src"))
from adapters.ideogram import _to_caption_json  # noqa: E402

PROMPTS_JSON = ROOT / "configs" / "benchmarks" / "vlm-prompts.json"
GUIDE_JSON = ROOT / "image-prompts" / "rewrite" / "ideogram_guide.json"
SOURCES = ("claude", "chatgpt", "qwen2.5-vl-7b-instruct")
CSV_FIELDS = [
    "prompt_id", "type", "source", "caption_format", "trial",
    "verifier_warnings", "exception", "error_message",
    "blank_image", "image_std", "latency_s",
]
BLANK_STD_THRESHOLD = 8.0  # 8-bit grayscale std; 회색 단색 차단 화면 의심 기준(경험적, 사람 확인 필요)


def load_items(prompts_json):
    categories = json.loads(pathlib.Path(prompts_json).read_text(encoding="utf-8"))
    items = []
    for cat in categories:
        for source in SOURCES:
            entry = cat.get(source)
            if entry:
                items.append({"type": cat["type"], "source": source, "prompt": entry["prompt"]})
    return items


def load_guide_captions(guide_json):
    categories = json.loads(pathlib.Path(guide_json).read_text(encoding="utf-8"))
    by_key = {}
    for cat in categories:
        for source in SOURCES:
            entry = cat.get(source)
            if entry:
                by_key[(cat["type"], source)] = entry["prompt"]
    return by_key


def build_caption(fmt, item, guide_captions, verifier):
    if fmt == "plain":
        caption = item["prompt"]
    elif fmt == "json":
        caption = _to_caption_json(item["prompt"])
    else:
        caption = guide_captions[(item["type"], item["source"])]
    warnings = verifier.verify_raw(caption)
    return caption, len(warnings)


def image_stats(image):
    arr = np.array(image.convert("L"), dtype=np.float32)
    std = float(arr.std())
    return std, std < BLANK_STD_THRESHOLD


def run_trial(pipe, cfg, preset, caption, seed):
    t0 = time.time()
    exception, error_message = False, ""
    blank_image, image_std = None, None
    try:
        images = pipe(
            caption,
            height=cfg.get("height", 1024),
            width=cfg.get("width", 1024),
            num_steps=preset.num_steps,
            guidance_schedule=preset.guidance_schedule,
            mu=preset.mu,
            std=preset.std,
            seed=seed,
            raise_on_caption_issues=True,
        )
        image_std, blank_image = image_stats(images[0])
    except Exception as e:  # noqa: BLE001 — caption-issue 예외 타입이 패키지마다 다를 수 있어 광범위하게 잡는다
        exception = True
        error_message = str(e)[:300]
    latency_s = round(time.time() - t0, 2)
    return exception, error_message, blank_image, image_std, latency_s


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=str(ROOT / "configs" / "models" / "ideogram-4.yaml"))
    ap.add_argument("--prompts-json", type=pathlib.Path, default=PROMPTS_JSON)
    ap.add_argument("--guide-prompts-json", type=pathlib.Path, default=GUIDE_JSON)
    ap.add_argument("--formats", nargs="+", default=["plain", "json", "guide"])
    ap.add_argument("--trials", type=int, default=3)
    ap.add_argument("--limit", type=int, default=None, help="처음 N개 프롬프트만 사용 (파일럿용)")
    ap.add_argument("--out", default=str(ROOT / "bench" / "ideogram_probe" / "block_rate.csv"))
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()

    cfg = yaml.safe_load(pathlib.Path(args.config).read_text(encoding="utf-8"))
    items = load_items(args.prompts_json)
    if args.limit:
        items = items[:args.limit]
    guide_captions = load_guide_captions(args.guide_prompts_json) if "guide" in args.formats else {}
    verifier = CaptionVerifier()

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

    total = len(items) * len(args.formats) * args.trials
    done = 0
    for i, it in enumerate(items):
        for fmt in args.formats:
            caption, n_warnings = build_caption(fmt, it, guide_captions, verifier)
            for trial in range(args.trials):
                exception, error_message, blank_image, image_std, latency_s = run_trial(
                    pipe, cfg, preset, caption, args.seed)
                writer.writerow({
                    "prompt_id": i, "type": it["type"], "source": it["source"],
                    "caption_format": fmt, "trial": trial,
                    "verifier_warnings": n_warnings, "exception": exception,
                    "error_message": error_message, "blank_image": blank_image,
                    "image_std": image_std, "latency_s": latency_s,
                })
                f.flush()
                done += 1
                print(f"[{done}/{total}] prompt={i} format={fmt} trial={trial} "
                      f"warnings={n_warnings} exception={exception} blank={blank_image} "
                      f"({latency_s}s)")

    f.close()
    print(f"done. csv: {out_path}")


if __name__ == "__main__":
    main()
