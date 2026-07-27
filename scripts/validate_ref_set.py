"""CSD ref_set(스타일 골든셋) 검증 — 프리셋별 레퍼런스 이미지 디렉토리를 받아
pairwise CSD 유사도 통계를 내고 manifest를 만든다.

수집 기준: bench/style-presets-v2.md의 "5. CSD ref_set 수집 기준" 절 참고
(프리셋별 15~25장, 피사체 다양·스타일 균일).

    python -m scripts.validate_ref_set --preset edu-flat-v2 --dir refs/golden-set/edu-flat-v2

출력:
    configs/ref_sets/{preset}.yaml   — manifest (경로/sha256/통계/status)
    reports/ref_set_validation.md    — 프리셋별 통계표 + outlier 목록 (프리셋 섹션만 갱신)

status:
    validated     — outlier 없음
    needs-review  — outlier 있음 (실패로 죽지 않고 기록만 남김)
    provisional   — --provisional로 강제 지정. 정식 ref_set이 아직 없어 임시
                     (파일럿 등) 이미지로 코드 경로만 검증할 때 씀. src/scoring.py의
                     --components csd는 validated/provisional manifest만 받아들인다.

3090의 t2i-score env에서 실행할 것 (CSD 모델 로드 필요).
"""
import argparse
import hashlib
import pathlib
import re

import yaml

import sys
ROOT = pathlib.Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
from src.scoring import load_csd_model, csd_style_embedding  # noqa: E402

REF_SETS_DIR = ROOT / "configs" / "ref_sets"
REPORT_PATH = ROOT / "reports" / "ref_set_validation.md"
IMAGE_EXTS = (".png", ".jpg", ".jpeg")


def _sha256(path):
    return hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest()


def _pairwise_stats(embeddings):
    """embeddings: 이미 정규화된 (1, D) 텐서 리스트. 자기 자신 제외 pairwise cosine."""
    n = len(embeddings)
    per_image_mean = []
    all_sims = []
    for i in range(n):
        sims = []
        for j in range(n):
            if i == j:
                continue
            sim = float((embeddings[i] @ embeddings[j].T).item())
            sims.append(sim)
            if j > i:
                all_sims.append(sim)
        per_image_mean.append(sum(sims) / len(sims) if sims else 0.0)

    mean = sum(all_sims) / len(all_sims) if all_sims else 0.0
    std = (sum((s - mean) ** 2 for s in all_sims) / len(all_sims)) ** 0.5 if all_sims else 0.0
    min_sim = min(all_sims) if all_sims else 0.0
    return per_image_mean, {"mean": round(mean, 4), "min": round(min_sim, 4), "std": round(std, 4)}


def validate_ref_set(preset, image_dir, provisional=False):
    image_dir = pathlib.Path(image_dir)
    paths = sorted(p for p in image_dir.iterdir() if p.suffix.lower() in IMAGE_EXTS)
    if len(paths) < 2:
        raise ValueError(f"{image_dir}: 이미지가 {len(paths)}장뿐 — pairwise 유사도를 낼 수 없음(최소 2장).")

    model = load_csd_model()
    embeddings = [csd_style_embedding(model, p) for p in paths]
    per_image_mean, stats = _pairwise_stats(embeddings)

    outlier_threshold = stats["mean"] - 2 * stats["std"]
    outliers = [str(p) for p, m in zip(paths, per_image_mean) if m < outlier_threshold]

    if provisional:
        status = "provisional"
    else:
        status = "needs-review" if outliers else "validated"

    images = [
        {"path": str(p), "sha256": _sha256(p), "mean_similarity": round(m, 4)}
        for p, m in zip(paths, per_image_mean)
    ]

    manifest = {
        "preset": preset,
        "status": status,
        "count": len(paths),
        "stats": stats,
        "outliers": outliers,
        "images": images,
    }
    return manifest


def write_manifest(manifest):
    REF_SETS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = REF_SETS_DIR / f"{manifest['preset']}.yaml"
    out_path.write_text(yaml.safe_dump(manifest, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return out_path


def _render_section(manifest):
    lines = [
        f"## {manifest['preset']}",
        "",
        f"status: `{manifest['status']}` · count: {manifest['count']} · "
        f"mean={manifest['stats']['mean']} min={manifest['stats']['min']} std={manifest['stats']['std']}",
        "",
    ]
    if manifest["outliers"]:
        lines.append("outlier(mean − 2σ 미만):")
        for o in manifest["outliers"]:
            lines.append(f"- {o}")
    else:
        lines.append("outlier 없음.")
    lines.append("")
    return "\n".join(lines)


def update_report(manifest):
    """reports/ref_set_validation.md에서 이 프리셋의 섹션만 교체/추가한다."""
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    header = "# CSD ref_set 검증 리포트\n\n프리셋별 통계는 `scripts/validate_ref_set.py` 재실행 시 해당 섹션만 갱신됨.\n\n"
    section = _render_section(manifest)
    section_marker = f"## {manifest['preset']}"

    if not REPORT_PATH.exists():
        REPORT_PATH.write_text(header + section, encoding="utf-8")
        return

    text = REPORT_PATH.read_text(encoding="utf-8")
    pattern = re.compile(rf"^## {re.escape(manifest['preset'])}\n.*?(?=^## |\Z)", re.MULTILINE | re.DOTALL)
    if pattern.search(text):
        text = pattern.sub(section, text)
    else:
        text = text.rstrip("\n") + "\n\n" + section
    REPORT_PATH.write_text(text, encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--preset", required=True, help="프리셋 이름 (edu-flat-v2 등)")
    ap.add_argument("--dir", required=True, help="레퍼런스 이미지 디렉토리")
    ap.add_argument("--provisional", action="store_true",
                    help="정식 ref_set이 아직 없을 때(파일럿 등) status를 강제로 provisional 표기")
    args = ap.parse_args()

    manifest = validate_ref_set(args.preset, args.dir, provisional=args.provisional)
    out_path = write_manifest(manifest)
    update_report(manifest)

    print(f"{manifest['count']}장 검증 완료 -> {out_path}")
    print(f"status={manifest['status']} mean={manifest['stats']['mean']} "
          f"min={manifest['stats']['min']} std={manifest['stats']['std']}")
    if manifest["outliers"]:
        print(f"[warn] outlier {len(manifest['outliers'])}장 — {REPORT_PATH} 확인")
    print(f"리포트 -> {REPORT_PATH}")


if __name__ == "__main__":
    main()
