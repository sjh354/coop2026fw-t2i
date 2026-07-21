"""수업용 벤치마크: configs/benchmarks/vlm-prompts.json의 24개(8 카테고리 x 3 VLM 소스)
완성 프롬프트를 모델 1개에 그대로 흘려 이미지를 생성한다.

기존 src/generate.py는 keyword + style을 조합해 프롬프트를 만들지만, 이 24개는 VLM이
이미 완성해서 낸 프롬프트라 조합이 필요 없다 — 그래서 별도 스크립트로 분리했다.
노트(frontmatter)/PngInfo/VRAM·sec 기록 관례는 src/generate.py와 동일하게 맞춰
review_app.py, src/scoring.py가 그대로 읽을 수 있게 한다.

    python -m scripts.lecture_generate --model pixart-sigma
    python -m scripts.lecture_generate --model flux2-klein-4b-nf4
"""
import argparse
import datetime
import json
import pathlib
import re
import sys
import time

import torch
import yaml
import frontmatter
from PIL import PngImagePlugin

ROOT = pathlib.Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "src"))
import adapters  # noqa: E402

PROMPTS_JSON = ROOT / "configs" / "benchmarks" / "vlm-prompts.json"
OUT = ROOT / "image-prompts"
SEED = 0
SOURCE_SLUG = {"claude": "claude", "chatgpt": "chatgpt", "qwen2.5-vl-7b-instruct": "qwen"}


def slug(text):
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def load_items():
    """vlm-prompts.json을 (type, source, prompt) 24개 리스트로 편다."""
    categories = json.loads(PROMPTS_JSON.read_text(encoding="utf-8"))
    items = []
    for cat in categories:
        for source in ("claude", "chatgpt", "qwen2.5-vl-7b-instruct"):
            entry = cat.get(source)
            if entry:
                items.append({"type": cat["type"], "source": source, "prompt": entry["prompt"]})
    return items


def next_version():
    OUT.mkdir(exist_ok=True)
    used = [int(m.group(1)) for d in OUT.iterdir()
            if d.is_dir() and (m := re.match(r"v(\d+)_", d.name))]
    return f"v{max(used, default=0) + 1:03d}"


def write_note(vdir, model, items, image_names):
    gallery = "\n".join(f"![[{n}]]" for n in image_names)
    meta = {
        "version": vdir.name.split("_", 1)[0],
        "model": model["name"],
        "model_repo": model["repo"],
        "experiment": "lecture-vlm24",
        "keyword_set": "lecture_vlm24",
        "keywords": [f"{it['type']} ({it['source']})" for it in items],
        "prompts": [it["prompt"] for it in items],
        "style": "",
        "negative_prompt": "",
        "seed": SEED,
        "dtype": model["dtype"],
        "quantization": model.get("quantization"),
        "guidance_scale": model["guidance"],
        "steps": model["steps"],
        "num_images": len(items),
        "created": datetime.date.today().isoformat(),
        "vram_peak_gb": None,
        "sec_per_image": None,
        "status": "running",
        "rating": None,
        "tags": [],
        "issues": "",
        "best": [],
    }
    note_path = vdir / f"{vdir.name}.md"
    note_path.write_text(
        frontmatter.dumps(frontmatter.Post(f"## Images\n\n{gallery}\n", **meta)),
        encoding="utf-8",
    )
    return note_path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True, help="configs/models/<name>.yaml")
    args = ap.parse_args()

    model = yaml.safe_load((ROOT / "configs" / "models" / f"{args.model}.yaml")
                            .read_text(encoding="utf-8"))
    items = load_items()

    version = next_version()
    vdir = OUT / f"{version}_{model['name']}-lecture24"
    img_dir = vdir / "images"
    img_dir.mkdir(parents=True)

    image_names = [f"{version}_{i:02d}_{slug(it['type'])}_{SOURCE_SLUG[it['source']]}.png"
                   for i, it in enumerate(items)]
    note_path = write_note(vdir, model, items, image_names)
    print(f"note: {note_path}")

    torch.cuda.reset_peak_memory_stats()
    generate = adapters.load(model)

    t0 = time.time()
    for i, it in enumerate(items):
        image = generate(it["prompt"], "", SEED)

        info = PngImagePlugin.PngInfo()
        for k, v in [("prompt", it["prompt"]), ("type", it["type"]), ("source", it["source"]),
                     ("seed", SEED), ("model", model["repo"]),
                     ("guidance_scale", model["guidance"]), ("steps", model["steps"])]:
            info.add_text(k, str(v))
        image.save(img_dir / image_names[i], pnginfo=info)
        print(f"[{i + 1}/{len(items)}] {it['type']} ({it['source']}) -> {image_names[i]}")

    elapsed = time.time() - t0
    post = frontmatter.load(str(note_path))
    post["vram_peak_gb"] = round(torch.cuda.max_memory_allocated() / 1024**3, 2)
    post["sec_per_image"] = round(elapsed / len(items), 2)
    post["status"] = "done"
    note_path.write_text(frontmatter.dumps(post), encoding="utf-8")

    print(f"done. vram_peak={post['vram_peak_gb']}GB  sec/img={post['sec_per_image']}")


if __name__ == "__main__":
    main()
