"""image-prompts/*의 노트를 스캔해서 overview1.html이 읽을 manifest.json을 만든다.

status: done인 노트라도 images/ 가 비어있거나 개수가 안 맞으면 실패로 간주하고 제외한다
(로컬 체크아웃엔 images/가 gitignore되어 없을 수 있음 — 이 스크립트는 실제 이미지가
있는 서버/머신에서 실행해야 의미가 있다).

    python -m http.server 80  # repo root에서
    -> http://<host>/overview1.html
"""
import pathlib
import sys

import frontmatter
import yaml

ROOT = pathlib.Path(__file__).parent.parent
OUT = ROOT / "image-prompts"


def slug(text):
    import re
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def main():
    entries = []
    skipped = []

    for vdir in sorted(OUT.iterdir()):
        if not vdir.is_dir():
            continue
        note_path = vdir / f"{vdir.name}.md"
        if not note_path.exists():
            continue

        try:
            post = frontmatter.load(str(note_path))
        except Exception as e:
            skipped.append(f"{vdir.name}: frontmatter parse error ({e})")
            continue

        meta = post.metadata
        if meta.get("status") != "done":
            skipped.append(f"{vdir.name}: status={meta.get('status')}")
            continue
        if meta.get("vram_peak_gb") is None or meta.get("sec_per_image") is None:
            skipped.append(f"{vdir.name}: missing vram/sec metrics")
            continue

        keywords = meta.get("keywords", [])
        img_dir = vdir / "images"
        images = []
        for i, kw in enumerate(keywords):
            fname = f"{vdir.name.split('_', 1)[0]}_{i:02d}_{slug(kw)}.png"
            fpath = img_dir / fname
            if fpath.exists():
                images.append({
                    "keyword": kw,
                    "path": str(fpath.relative_to(ROOT)),
                })

        if not images or len(images) != len(keywords):
            skipped.append(
                f"{vdir.name}: {len(images)}/{len(keywords)} images found on disk"
            )
            continue

        entries.append({
            "version": meta.get("version"),
            "model": meta.get("model"),
            "experiment": meta.get("experiment"),
            "keyword_set": meta.get("keyword_set"),
            "vram_peak_gb": meta.get("vram_peak_gb"),
            "sec_per_image": meta.get("sec_per_image"),
            "num_images": len(images),
            "rating": meta.get("rating"),
            "images": images,
        })

    manifest_path = ROOT / "manifest.json"
    import json
    manifest_path.write_text(
        json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(f"manifest: {manifest_path} ({len(entries)} successful runs)")
    if skipped:
        print(f"skipped {len(skipped)} runs:", file=sys.stderr)
        for s in skipped:
            print(f"  - {s}", file=sys.stderr)


if __name__ == "__main__":
    main()
