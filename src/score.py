"""이미지가 프롬프트/스타일에 얼마나 맞는지 CLIP 기반 근사치로 채점한다.

    python -m src.score --version v001_pixart-sigma --refs educational-flat

vqascore/csd는 진짜 VQAScore/CSD 모델이 아니라 CLIP(openai/clip-vit-base-patch32)로
근사한 프록시다. 인터페이스(score_image의 반환 딕셔너리)는 나중에 진짜 모델로
교체해도 그대로 유지되도록 맞춰뒀다.

주의 (content leakage): refs/<name>/ 은 보통 같은 keyword set으로 생성된 이미지
중에서 고른 것이라, "apple" 후보를 apple 참조 이미지들과 비교하면 csd가 스타일이
아니라 콘텐츠 일치 때문에 높게 나올 수 있다. CLIP 이미지 임베딩 코사인은 이 leakage에
특히 취약하다 — 참조 셋의 콘텐츠를 최대한 다양하게 유지해서 완화할 것.

주의 (스페인어 vqascore): openai/clip-vit-base-patch32는 스페인어 텍스트 인코더가
약하므로, spanish30 키워드셋으로 생성된 이미지는 노트의 keyword_set을 보고 같은
인덱스의 basic30 영어 키워드로 vqascore를 채점한다. 그래야 vqascore가 "이미지가
영어로 뭘 보여주는가"를 계속 측정하고, educational-flat vs -es의 vqascore 격차가
스페인어 프롬프팅으로 인한 페널티를 보여준다.
"""
import argparse
import pathlib

import frontmatter
import numpy as np
import torch
import yaml
from PIL import Image
from transformers import CLIPModel, CLIPProcessor

ROOT = pathlib.Path(__file__).parent.parent
CONFIGS = ROOT / "configs"
IMAGE_PROMPTS = ROOT / "image-prompts"
REFS = ROOT / "refs"

CLIP_NAME = "openai/clip-vit-base-patch32"

_clip_cache = {}


def load_clip():
    """CLIP 모델/프로세서를 로드한다 (모듈 레벨 캐시, 프로세스당 1회만 다운로드/로드)."""
    if "model" not in _clip_cache:
        _clip_cache["model"] = CLIPModel.from_pretrained(CLIP_NAME).eval()
        _clip_cache["processor"] = CLIPProcessor.from_pretrained(CLIP_NAME)
    return _clip_cache["model"], _clip_cache["processor"]


def _normalize(emb):
    return emb / emb.norm(dim=-1, keepdim=True)


def embed_images(paths, clip=None):
    """이미지 파일 경로 리스트 -> (N, D) L2-정규화 임베딩 텐서."""
    model, processor = clip or load_clip()
    images = [Image.open(p).convert("RGB") for p in paths]
    inputs = processor(images=images, return_tensors="pt")
    with torch.no_grad():
        emb = model.get_image_features(**inputs)
    return _normalize(emb)


def embed_text(text, clip=None):
    """텍스트 하나 -> (1, D) L2-정규화 임베딩 텐서."""
    model, processor = clip or load_clip()
    inputs = processor(text=[text], return_tensors="pt", padding=True)
    with torch.no_grad():
        emb = model.get_text_features(**inputs)
    return _normalize(emb)


def load_refs(ref_dir, clip=None, exclude_name=None):
    """refs/<name>/ 의 PNG들을 임베딩한다. 비어있거나 없으면 None.

    exclude_name: 채점 대상 이미지 자신이 참조 셋에도 들어있을 때(golden set에
    추가된 이미지를 다시 채점하는 경우) csd가 자기 자신과의 코사인(≈1)으로
    부풀지 않도록 같은 파일명을 제외한다.
    """
    if not ref_dir.exists():
        return None
    paths = [p for p in sorted(ref_dir.glob("*.png")) if p.name != exclude_name]
    if not paths:
        return None
    return embed_images(paths, clip)


def _flatness(img_path):
    """그라디언트가 적고(평평한 색면) 색상 수가 적을수록 1에 가깝다. 모델 없이 계산."""
    arr = np.asarray(Image.open(img_path).convert("RGB"), dtype=np.float32)
    grad = np.abs(np.diff(arr, axis=0)).mean() + np.abs(np.diff(arr, axis=1)).mean()
    low_gradient = 1.0 - min(grad / 40.0, 1.0)

    quantized = (arr // 32).astype(np.int32)
    n_unique = len(np.unique(quantized.reshape(-1, 3), axis=0))
    few_colors = 1.0 - min(n_unique / 256.0, 1.0)

    return round(float((low_gradient + few_colors) / 2), 4)


def _harmonic(values):
    """0이 아닌 값들만 모아 조화평균. 값이 없으면 None."""
    vals = [v for v in values if v is not None and v > 0]
    if not vals:
        return None
    return round(len(vals) / sum(1 / v for v in vals), 4)


def score_image(img_path, keyword, ref_embeds, clip=None):
    """이미지 하나를 채점한다.

    keyword: vqascore에 쓸 영어 콘텐츠 키워드 (스타일 문구 제외, 스페인어면
        basic30의 같은 인덱스 영어 키워드로 매핑해서 넘길 것 - CLI가 처리).
    ref_embeds: load_refs()의 결과, 없으면 None (csd는 None으로 남는다).
    """
    model, processor = clip or load_clip()
    img_emb = embed_images([img_path], (model, processor))
    text_emb = embed_text(keyword, (model, processor))

    vqascore = round(max(float((img_emb @ text_emb.T).item()), 0.0), 4)

    csd = None
    if ref_embeds is not None:
        csd = round(max(float((img_emb @ ref_embeds.T).mean().item()), 0.0), 4)

    flatness = _flatness(img_path)
    harmonic = _harmonic([vqascore, csd, flatness])

    return {"vqascore": vqascore, "csd": csd, "flatness": flatness, "harmonic": harmonic}


def _english_keyword_for(post, index):
    """post의 keyword_set이 spanish30이면 basic30의 같은 인덱스 영어 키워드를 반환."""
    keyword_set = post.get("keyword_set")
    if keyword_set == "spanish30":
        basic = yaml.safe_load((CONFIGS / "keywords" / "basic30.yaml").read_text())
        return basic["keywords"][index]
    return post["keywords"][index]


def _mean(values):
    vals = [v for v in values if v is not None]
    return round(sum(vals) / len(vals), 4) if vals else None


def score_version(vdir, ref_name=None, clip=None):
    """버전 하나(image-prompts/v00N_<model>/)의 모든 이미지를 채점해 노트에 기록.

    ref_name이 None이면 golden set 없이 vqascore/flatness/harmonic만 계산한다
    (csd는 None으로 남는다) — golden set을 아직 안 만들었어도 바로 쓸 수 있다.
    """
    note_path = vdir / f"{vdir.name}.md"
    post = frontmatter.load(str(note_path))
    img_dir = vdir / "images"
    img_paths = sorted(img_dir.glob("*.png"))

    clip = clip or load_clip()
    ref_embeds = load_refs(REFS / ref_name, clip) if ref_name else None

    scores = {}
    for i, img_path in enumerate(img_paths):
        keyword = _english_keyword_for(post, i)
        scores[img_path.name] = score_image(img_path, keyword, ref_embeds, clip)

    post["scores"] = scores
    post["vqascore_mean"] = _mean([s["vqascore"] for s in scores.values()])
    post["csd_mean"] = _mean([s["csd"] for s in scores.values()])
    post["flatness_mean"] = _mean([s["flatness"] for s in scores.values()])
    post["harmonic_mean"] = _mean([s["harmonic"] for s in scores.values()])
    note_path.write_text(frontmatter.dumps(post), encoding="utf-8")
    return post


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", required=True, help="image-prompts/<version>/")
    ap.add_argument("--refs", default=None,
                     help="refs/<name>/ (생략하면 csd 없이 vqascore/flatness/harmonic만 계산)")
    args = ap.parse_args()

    vdir = IMAGE_PROMPTS / args.version
    post = score_version(vdir, args.refs)
    print(f"vqascore_mean={post['vqascore_mean']} csd_mean={post['csd_mean']} "
          f"flatness_mean={post['flatness_mean']} harmonic_mean={post['harmonic_mean']}")


if __name__ == "__main__":
    main()
