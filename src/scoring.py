"""이미지 채점 모듈 1차 구현 (진짜 모델). `src/score.py`(CLIP 프록시)를 대체하지 않고
별도로 둔다 — review_app.py는 아직 프록시를 쓰고, 이 모듈은 3090에서 검증 후 교체한다.

    score_image(image, prompt, ref_set) -> {vqascore, csd, custom_cv, harmonic}
    score_image_vlm(image, prompt) -> {faithfulness, style, overall}

무거운 모델(VQAScore, CSD)은 함수 인자로 받지 않고 모듈 레벨 캐시로 lazy-load한다
(인터페이스를 3개 파라미터로 고정하기 위해).

가중치 다운로드 경로 / VRAM은 README.md의 "채점 모듈" 절 참고. T2I 생성 모델과
동시 로드하지 않는다는 전제 — 채점은 생성이 끝난 뒤 별도 패스로 돌린다.

    python -m src.scoring --dir image-prompts/v211_lumina2/images --out bench/scores.csv
"""
import argparse
import base64
import csv
import json
import pathlib

import cv2
import numpy as np
from PIL import Image

ROOT = pathlib.Path(__file__).parent.parent
WEIGHTS = ROOT / "weights" / "scoring"

VQASCORE_MODEL = "clip-flant5-xl"
CSD_CHECKPOINT = WEIGHTS / "csd_vit-l.pth"
VLM_JUDGE_MODEL = "claude-sonnet-5"

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


def _load_csd():
    """CSD(Contrastive Style Descriptors) ViT-L 체크포인트를 lazy-load한다.

    공개 구현: https://github.com/learn2phoenix/CSD
    체크포인트를 WEIGHTS/csd_vit-l.pth 에 미리 받아둘 것 (README 참고).

    주의: 아래 CSD_CLIP 생성자 인자/forward 반환 형태(3-tuple)/state dict 키는
    공개 구현 문서 기준으로 작성했고 GPU 서버에서 직접 돌려 확인하지 못했다.
    3090에서 첫 실행 시 CSD 리포와 대조해 맞을 것.
    """
    if "model" not in _csd_cache:
        if not CSD_CHECKPOINT.exists():
            raise FileNotFoundError(
                f"CSD 체크포인트가 없습니다: {CSD_CHECKPOINT}. README.md의 "
                "'채점 모듈' 절에 안내된 URL에서 받아 이 경로에 둘 것."
            )
        import torch
        from CSD.model import CSD_CLIP  # 공개 구현 vendored 또는 pip 설치 전제

        model = CSD_CLIP("vit_large", "default")
        state = torch.load(CSD_CHECKPOINT, map_location="cpu")
        model.load_state_dict(state["model_state_dict"], strict=False)
        model.eval()
        _csd_cache["model"] = model
    return _csd_cache["model"]


def _csd_style_embedding(model, image_path):
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
    model = _load_csd()
    img_emb = _csd_style_embedding(model, image_path)
    ref_embs = [_csd_style_embedding(model, r) for r in ref_set]
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


def _harmonic_mean(values):
    vals = [v for v in values if v is not None]
    if not vals:
        return None
    if any(v <= 0 for v in vals):
        return 0.0
    return round(len(vals) / sum(1 / v for v in vals), 4)


def score_image(image, prompt, ref_set):
    """이미지 하나를 채점한다.

    image: 채점할 PNG 경로.
    prompt: 이미지 생성에 쓰인 전체 프롬프트(스타일 문구 포함).
    ref_set: 스타일 레퍼런스 이미지 경로 리스트. 비어있으면 csd는 None.
    """
    vqascore = _vqascore(image, prompt)
    csd = _csd(image, ref_set)
    custom_cv = _custom_cv(image)
    harmonic = _harmonic_mean([vqascore, csd, custom_cv])
    return {"vqascore": vqascore, "csd": csd, "custom_cv": custom_cv, "harmonic": harmonic}


VLM_JUDGE_SYSTEM = (
    "너는 K-12 교육 삽화용 T2I 생성 이미지를 채점하는 심사위원이다. "
    "아래 3축을 각각 독립적으로 판단해라: "
    "(1) 수량 — 요청된 개수의 사물이 정확히 그려졌는가, "
    "(2) 공간 관계 — 요청된 좌우/상하 배치가 맞는가, "
    "(3) 속성 결합 — 색/재질 등 속성이 의도한 대상에만 붙었고 다른 대상으로 번지지 않았는가. "
    "이 3축을 종합해 faithfulness(프롬프트 충실도)를 매기고, style(플랫 교육 삽화 스타일 준수도)을 "
    "별도로 매긴 뒤, overall은 두 값의 단순 평균으로 계산해라. "
    "각 항목은 0.0~1.0 사이 실수. 다른 설명 없이 JSON만 출력해라: "
    '{"faithfulness": <float>, "style": <float>, "overall": <float>}'
)


def _call_anthropic_vision(image_path, prompt, *, model):
    import anthropic

    media_type = "image/png"
    data = base64.standard_b64encode(pathlib.Path(image_path).read_bytes()).decode("utf-8")
    client = anthropic.Anthropic()
    response = client.messages.create(
        model=model,
        max_tokens=300,
        system=VLM_JUDGE_SYSTEM,
        messages=[{
            "role": "user",
            "content": [
                {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": data}},
                {"type": "text", "text": f"프롬프트: {prompt}"},
            ],
        }],
    )
    return response.content[0].text


def _parse_judge_json(raw):
    start, end = raw.find("{"), raw.rfind("}")
    parsed = json.loads(raw[start:end + 1])
    return {k: round(float(parsed[k]), 4) for k in ("faithfulness", "style", "overall")}


def score_image_vlm(image, prompt, provider_fn=None):
    """VLM-as-judge 채점. provider_fn(image_path, prompt, *, model) -> raw text로 교체 가능."""
    provider_fn = provider_fn or _call_anthropic_vision
    raw = provider_fn(image, prompt, model=VLM_JUDGE_MODEL)
    return _parse_judge_json(raw)


def _prompt_from_png(image_path):
    info = Image.open(image_path).info
    if "prompt" not in info:
        raise ValueError(f"{image_path}에 PngInfo prompt 메타데이터가 없습니다.")
    return info["prompt"]


def score_batch(image_dir, ref_set, out_csv, with_vlm=False):
    """디렉토리의 모든 PNG를 채점해 CSV + 마크다운 요약을 쓴다."""
    paths = sorted(pathlib.Path(image_dir).glob("*.png"))
    fieldnames = ["image", "vqascore", "csd", "custom_cv", "harmonic"]
    if with_vlm:
        fieldnames += ["vlm_faithfulness", "vlm_style", "vlm_overall"]

    rows = []
    for p in paths:
        prompt = _prompt_from_png(p)
        row = {"image": p.name, **score_image(p, prompt, ref_set)}
        if with_vlm:
            vlm = score_image_vlm(p, prompt)
            row.update({"vlm_faithfulness": vlm["faithfulness"], "vlm_style": vlm["style"],
                        "vlm_overall": vlm["overall"]})
        rows.append(row)

    out_csv = pathlib.Path(out_csv)
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
    ap.add_argument("--dir", required=True, help="채점할 PNG 디렉토리")
    ap.add_argument("--refs", nargs="*", default=[], help="스타일 레퍼런스 이미지 경로들")
    ap.add_argument("--out", required=True, help="출력 CSV 경로 (같은 이름의 .md 요약도 생성)")
    ap.add_argument("--vlm", action="store_true", help="VLM-as-judge도 같이 채점")
    args = ap.parse_args()

    rows = score_batch(args.dir, args.refs, args.out, with_vlm=args.vlm)
    print(f"{len(rows)}장 채점 완료 -> {args.out}")


if __name__ == "__main__":
    main()
