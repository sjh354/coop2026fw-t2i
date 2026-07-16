"""모델 × 실험 조합 하나를 생성한다.

    python -m src.generate --model pixart-sigma --exp coloring-book

버전 디렉토리는 image-prompts/v001_pixart-sigma/ 형태로 자동 채번.
Obsidian 노트(frontmatter)가 여전히 single source of truth이고,
rating/tags/issues/best는 Streamlit에서 채운다.

VRAM peak와 img당 시간을 자동으로 노트에 기록한다 — 지금 단계의 목표가
"어느 모델이 16GB에 들어가는가"이므로 이게 실험 결과의 절반이다.
"""
import argparse
import datetime
import pathlib
import re
import sys
import time

import torch
import yaml
import frontmatter
from PIL import PngImagePlugin

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import adapters  # noqa: E402

ROOT = pathlib.Path(__file__).parent.parent
CONFIGS = ROOT / "configs"
OUT = ROOT / "image-prompts"


def load_yaml(path):
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def slug(text):
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def next_version():
    OUT.mkdir(exist_ok=True)
    used = [int(m.group(1)) for d in OUT.iterdir()
            if d.is_dir() and (m := re.match(r"v(\d+)_", d.name))]
    return f"v{max(used, default=0) + 1:03d}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True, help="configs/models/<name>.yaml")
    ap.add_argument("--exp", required=True, help="configs/experiments/<name>.yaml")
    ap.add_argument("--dialect", default=None, help="configs/dialects/<name>.yaml")
    args = ap.parse_args()

    model = load_yaml(CONFIGS / "models" / f"{args.model}.yaml")
    exp = load_yaml(CONFIGS / "experiments" / f"{args.exp}.yaml")
    keywords = load_yaml(CONFIGS / "keywords" / f"{exp['keywords']}.yaml")["keywords"]
    dialect = (load_yaml(CONFIGS / "dialects" / f"{args.dialect}.yaml")
               if args.dialect else None)

    active_negative = dialect.get("negative", "") if dialect else exp.get("negative", "")
    if not model.get("supports_negative") and active_negative:
        print(f"[warn] {model['name']}는 CFG를 안 써서 negative prompt가 무시된다.")

    version = next_version()
    suffix = model["name"] + ("-dialect" if dialect else "")
    vdir = OUT / f"{version}_{suffix}"
    img_dir = vdir / "images"
    img_dir.mkdir(parents=True)

    # 노트를 먼저 쓴다: 파일명이 결정적이므로 생성이 중간에 죽어도(OOM 등) 기록은 남는다.
    image_names = [f"{version}_{i:02d}_{slug(k)}.png" for i, k in enumerate(keywords)]
    meta = {
        "version": version,
        "model": model["name"],
        "model_repo": model["repo"],
        "experiment": exp["name"],
        "style": exp["style"],
        "negative_prompt": active_negative,
        "condition": "dialect" if dialect else "shared",
        "dialect": args.dialect,
        "keyword_set": exp["keywords"],
        "keywords": keywords,
        "seed": exp["seed"],
        "dtype": model["dtype"],
        "quantization": model.get("quantization"),
        "guidance_scale": model["guidance"],
        "steps": model["steps"],
        "num_images": len(keywords),
        "created": datetime.date.today().isoformat(),
        # 아래 3개는 생성 후 갱신
        "vram_peak_gb": None,
        "sec_per_image": None,
        "status": "running",
        # 아래 4개는 Streamlit에서 채움
        "rating": None,
        "tags": [],
        "issues": "",
        "best": [],
    }
    gallery = "\n".join(f"![[{n}]]" for n in image_names)
    note_path = vdir / f"{vdir.name}.md"
    note_path.write_text(
        frontmatter.dumps(frontmatter.Post(f"## Images\n\n{gallery}\n", **meta)),
        encoding="utf-8",
    )
    print(f"note: {note_path}")

    torch.cuda.reset_peak_memory_stats()
    generate = adapters.load(model)

    t0 = time.time()
    for i, keyword in enumerate(keywords):
        if dialect:
            prompt = dialect["template"].format(keyword=keyword)
        else:
            prompt = f"{keyword}, {exp['style']}"
        image = generate(prompt, active_negative, exp["seed"])

        info = PngImagePlugin.PngInfo()
        for k, v in [("prompt", prompt), ("keyword", keyword),
                     ("negative_prompt", active_negative),
                     ("seed", exp["seed"]), ("model", model["repo"]),
                     ("guidance_scale", model["guidance"]), ("steps", model["steps"])]:
            info.add_text(k, str(v))
        image.save(img_dir / image_names[i], pnginfo=info)
        print(f"[{i + 1}/{len(keywords)}] {keyword} -> {image_names[i]}")

    elapsed = time.time() - t0
    post = frontmatter.load(str(note_path))
    post["vram_peak_gb"] = round(torch.cuda.max_memory_allocated() / 1024**3, 2)
    post["sec_per_image"] = round(elapsed / len(keywords), 2)
    post["status"] = "done"
    note_path.write_text(frontmatter.dumps(post), encoding="utf-8")

    print(f"done. vram_peak={post['vram_peak_gb']}GB  "
          f"sec/img={post['sec_per_image']}")


if __name__ == "__main__":
    main()
