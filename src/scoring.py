"""이미지 채점 모듈 — vqascore/custom_cv/csd 패스 분리 실행.

    score_image(image, prompt, components, ref_set=None) -> {vqascore?, custom_cv?, csd?}

VLM-as-judge는 이 모듈에서 분리됐다 — 로컬 Qwen2.5-VL-7B-Instruct 기반
`scripts/judge.py` 참고 (예전 Anthropic API 기반 score_image_vlm은 제거됨).

무거운 모델(VQAScore, CSD)은 함수 인자로 받지 않고 모듈 레벨 캐시로 lazy-load한다.
가중치 다운로드 경로 / VRAM은 README.md의 "채점 모듈" 절 참고. T2I 생성 모델과
동시 로드하지 않는다는 전제 — 채점은 생성이 끝난 뒤 별도 패스로 돌린다.

패스를 분리하는 이유: csd는 정식 ref_set(골든셋) 수집 전까지 provisional 상태이므로,
vqascore/cv는 먼저 채점하고 csd는 ref_set 확정 후(scripts/validate_ref_set.py) 별도로
재실행할 수 있어야 한다. run/model/item_id 컬럼은 scripts/merge_results.py의 조인 키.

    python -m src.scoring --dir image-prompts/v211_lumina2/images \\
        --out bench/scores/v211_lumina2/pass1.csv --components vqascore,cv

    python -m src.scoring --dir image-prompts/v211_lumina2/images \\
        --out bench/scores/v211_lumina2/csd.csv --components csd \\
        --ref-manifest configs/ref_sets/edu-flat-v2.yaml
"""
import argparse
import csv
import pathlib

import cv2
import frontmatter
import numpy as np
import yaml
from PIL import Image

ROOT = pathlib.Path(__file__).parent.parent
WEIGHTS = ROOT / "weights" / "scoring"
BENCH_V1 = ROOT / "configs" / "benchmarks" / "bench_v1.yaml"

VQASCORE_MODEL = "clip-flant5-xl"
CSD_CHECKPOINT = WEIGHTS / "csd_vit-l.pth"

_vqascore_cache = {}
_csd_cache = {}


def _load_vqascore():
    """t2v_metrics.VQAScore를 lazy-load한다 (프로세스당 1회).

    t2v-metrics v3.1부터 clip-flant5 계열이 legacy 취급되어 모델 목록에서
    빠졌다 — `pip install t2v-metrics==3.0`으로 고정해야 이 모델명이 동작한다
    (envs/README.md 참고).
    """
    if "model" not in _vqascore_cache:
        import t2v_metrics
        _vqascore_cache["model"] = t2v_metrics.VQAScore(model=VQASCORE_MODEL)
    return _vqascore_cache["model"]


def load_csd_model():
    """CSD(Contrastive Style Descriptors) ViT-L 체크포인트를 lazy-load한다.

    공개 구현: https://github.com/learn2phoenix/CSD (vendor/CSD, MIT 라이선스로 vendoring).
    체크포인트는 저자 공식 HF 미러 https://huggingface.co/tomg-group-umd/CSD-ViT-L 에서
    받아 WEIGHTS/csd_vit-l.pth 에 둔다 (README 참고). scripts/validate_ref_set.py도
    이 함수를 그대로 재사용한다.

    2026-07-20 ubuntu@172.10.5.23 t2i-score env에서 실제 체크포인트로 로드+forward
    검증 완료 (load_state_dict strict 매치, style embedding shape [N, 768]).
    체크포인트의 state dict 키는 "module." 접두사가 붙어 있어 convert_state_dict로
    벗겨내야 한다 — 벗기지 않으면 strict=False가 조용히 0개 키 매치로 통과해
    랜덤 초기화 상태로 채점하게 된다.
    """
    if "model" not in _csd_cache:
        if not CSD_CHECKPOINT.exists():
            raise FileNotFoundError(
                f"CSD 체크포인트가 없습니다: {CSD_CHECKPOINT}. README.md의 "
                "'채점 모듈' 절에 안내된 URL에서 받아 이 경로에 둘 것."
            )
        import torch
        from CSD.model import CSD_CLIP  # vendor/CSD
        from CSD.utils import convert_state_dict

        model = CSD_CLIP("vit_large", "default")
        checkpoint = torch.load(CSD_CHECKPOINT, map_location="cpu", weights_only=False)
        state = convert_state_dict(checkpoint["model_state_dict"])
        msg = model.load_state_dict(state, strict=False)
        if msg.missing_keys or msg.unexpected_keys:
            raise RuntimeError(f"CSD 체크포인트 로드 불일치: {msg}")
        model.eval()
        if torch.cuda.is_available():
            model = model.cuda()
        _csd_cache["model"] = model
    return _csd_cache["model"]


def csd_style_embedding(model, image_path):
    import torch
    from torchvision import transforms

    preprocess = transforms.Compose([
        transforms.Resize(224),
        transforms.CenterCrop(224),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.48145466, 0.4578275, 0.40821073],
                              std=[0.26862954, 0.26130258, 0.27577711]),
    ])
    img = preprocess(Image.open(image_path).convert("RGB")).unsqueeze(0)
    img = img.to(next(model.parameters()).device)
    with torch.no_grad():
        _, _, style_emb = model(img)
    return torch.nn.functional.normalize(style_emb, dim=-1)


def _vqascore(image_path, prompt):
    model = _load_vqascore()
    score = model(images=[str(image_path)], texts=[prompt])
    return round(float(score[0][0]), 4)


def _csd(image_path, ref_set):
    if not ref_set:
        return None
    model = load_csd_model()
    img_emb = csd_style_embedding(model, image_path)
    ref_embs = [csd_style_embedding(model, r) for r in ref_set]
    sims = [float((img_emb @ r.T).item()) for r in ref_embs]
    return round(max(sum(sims) / len(sims), 0.0), 4)


def _line_flatness(bgr):
    """색 영역의 균일성(플랫 셰이딩 정도). 영역 내부 채널별 분산(픽셀 수 가중 평균)이
    작을수록 1에 가깝다. LAB 세 채널을 합쳐 분산을 내면 채널 간 스케일 차이(L~250 vs
    a/b~130)가 분산처럼 잡히므로 채널별로 따로 낸다."""
    lab = cv2.cvtColor(bgr, cv2.COLOR_BGR2LAB).astype(np.float32)
    quantized = (bgr // 24).astype(np.int32)
    flat_ids = quantized[:, :, 0] * 32 * 32 + quantized[:, :, 1] * 32 + quantized[:, :, 2]
    region_ids, counts = np.unique(flat_ids, return_counts=True)
    total_var, weight_sum = 0.0, 0
    for region_id, count in zip(region_ids, counts):
        if count < 50:
            continue
        mask = flat_ids == region_id
        per_channel_var = lab[mask].reshape(-1, 3).var(axis=0).mean()
        total_var += per_channel_var * count
        weight_sum += count
    if weight_sum == 0:
        return 0.0
    mean_var = float(total_var / weight_sum)
    return round(1.0 - min(mean_var / 80.0, 1.0), 4)


def _edge_uniformity(bgr):
    """윤곽선 두께 일관성. Canny 엣지를 살짝 dilate해 두께가 있는 마스크로 만든 뒤,
    거리변환값(선 내부 각 픽셀에서 배경까지 거리 ≈ 국소 반두께)의 변동계수가
    작을수록(두께가 일정할수록) 1에 가깝다."""
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 80, 160)
    line_mask = cv2.dilate(edges, np.ones((3, 3), np.uint8), iterations=1)
    if line_mask.sum() == 0:
        return 0.0
    dist = cv2.distanceTransform(line_mask, cv2.DIST_L2, 5)
    widths = dist[line_mask > 0]
    if widths.size < 2:
        return 1.0
    coeff_var = float(widths.std() / (widths.mean() + 1e-6))
    return round(1.0 - min(coeff_var, 1.0), 4)


def _custom_cv(image_path):
    bgr = cv2.imread(str(image_path))
    flat = _line_flatness(bgr)
    edge = _edge_uniformity(bgr)
    return round((flat + edge) / 2, 4)


def score_image(image, prompt, components, ref_set=None):
    """이미지 하나를 채점한다. components에 담긴 것만 계산해서 돌려준다.

    image: 채점할 PNG 경로.
    prompt: 이미지 생성에 쓰인 전체 프롬프트(스타일 문구 포함).
    components: {"vqascore", "cv", "csd"} 부분집합.
    ref_set: csd용 스타일 레퍼런스 이미지 경로 리스트.
    """
    result = {}
    if "vqascore" in components:
        result["vqascore"] = _vqascore(image, prompt)
    if "cv" in components:
        result["custom_cv"] = _custom_cv(image)
    if "csd" in components:
        result["csd"] = _csd(image, ref_set or [])
    return result


def _prompt_from_png(image_path):
    info = Image.open(image_path).info
    if "prompt" not in info:
        raise ValueError(f"{image_path}에 PngInfo prompt 메타데이터가 없습니다.")
    return info["prompt"]


def _bench_v1_item_ids():
    prompts = yaml.safe_load(BENCH_V1.read_text(encoding="utf-8"))["prompts"]
    return [p["id"] for p in prompts]


def _run_context(image_dir):
    """image_dir(= .../vNNN_model/images)의 상위 note frontmatter에서 run 식별자,
    모델명, item_id 리스트(순서 기반)를 얻는다.

    item_id 매핑은 note의 keyword_set이 'bench_v1'일 때만 채워진다 — PNG/note
    어디에도 bench_v1 item id 자체가 기록돼 있지 않아서, build_bench_v1_keywords.py가
    configs/benchmarks/bench_v1.yaml의 prompts 순서를 그대로 보존해 keywords 리스트를
    만든다는 사실에 기대어 '이미지 파일명 인덱스 == bench_v1 프롬프트 인덱스'로 역산한다.
    """
    image_dir = pathlib.Path(image_dir)
    vdir = image_dir.parent
    note_path = vdir / f"{vdir.name}.md"
    post = frontmatter.load(str(note_path))
    item_ids = _bench_v1_item_ids() if post.get("keyword_set") == "bench_v1" else None
    return {"run": vdir.name, "model": post.get("model"), "item_ids": item_ids}


def _load_ref_manifest(path):
    manifest = yaml.safe_load(pathlib.Path(path).read_text(encoding="utf-8"))
    if manifest["status"] not in ("validated", "provisional"):
        raise ValueError(
            f"{path}: status={manifest['status']} — validated 또는 provisional인 "
            "manifest만 채점에 쓸 수 있습니다. scripts/validate_ref_set.py로 먼저 검증할 것."
        )
    return manifest


def score_batch(image_dir, out_csv, components, ref_manifest_path=None):
    """디렉토리의 모든 PNG를 채점해 CSV + 마크다운 요약을 쓴다."""
    components = set(components)
    ctx = _run_context(image_dir)

    ref_set, provisional = [], False
    if "csd" in components:
        if not ref_manifest_path:
            raise ValueError("--components csd는 --ref-manifest가 필요합니다.")
        manifest = _load_ref_manifest(ref_manifest_path)
        ref_set = [img["path"] for img in manifest["images"]]
        provisional = manifest["status"] == "provisional"

    paths = sorted(pathlib.Path(image_dir).glob("*.png"))
    fieldnames = ["run", "model", "item_id", "image"]
    fieldnames += [c for c in ("vqascore", "custom_cv", "csd") if
                   (c if c != "custom_cv" else "cv") in components]
    if "csd" in components:
        fieldnames.append("csd_provisional")

    rows = []
    for i, p in enumerate(paths):
        prompt = _prompt_from_png(p)
        item_id = ctx["item_ids"][i] if ctx["item_ids"] else None
        row = {"run": ctx["run"], "model": ctx["model"], "item_id": item_id, "image": p.name,
               **score_image(p, prompt, components, ref_set)}
        if "csd" in components:
            row["csd_provisional"] = provisional
        rows.append(row)

    out_csv = pathlib.Path(out_csv)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with out_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    summary_path = out_csv.with_suffix(".md")
    _write_summary(summary_path, rows, fieldnames)
    return rows


def _write_summary(summary_path, rows, fieldnames):
    lines = [f"# 채점 요약 ({len(rows)}장)", "", "| " + " | ".join(fieldnames) + " |",
              "|" + "---|" * len(fieldnames)]
    for row in rows:
        lines.append("| " + " | ".join(str(row[k]) for k in fieldnames) + " |")
    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True, help="채점할 PNG 디렉토리 (image-prompts/vNNN_model/images)")
    ap.add_argument("--out", required=True, help="출력 CSV 경로 (같은 이름의 .md 요약도 생성)")
    ap.add_argument("--components", required=True,
                    help="콤마구분: vqascore,cv,csd 중 조합 (예: vqascore,cv 또는 csd)")
    ap.add_argument("--ref-manifest", help="--components csd 사용 시 configs/ref_sets/<preset>.yaml 경로")
    args = ap.parse_args()

    components = {c.strip() for c in args.components.split(",") if c.strip()}
    rows = score_batch(args.dir, args.out, components, ref_manifest_path=args.ref_manifest)
    print(f"{len(rows)}장 채점 완료 ({','.join(sorted(components))}) -> {args.out}")


if __name__ == "__main__":
    main()
