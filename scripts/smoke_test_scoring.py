"""채점 모듈 스모크 테스트: 정합 성공 3장 vs 실패 3장에서 vqascore가 성공군 > 실패군
순위를 내는지 확인한다. 3090 GPU 서버, t2i-score env에서 실행할 것 (VQAScore가 실제
CLIP-FlanT5 모델을 로드하므로 이 저장소의 macOS 개발 샌드박스에서는 돌지 않는다).

샘플 6장은 image-prompts/pilot-complex3-report.md의 축별 판정(수량/공간/속성, 육안
비교로 기입됨)에서 그대로 가져왔다 — 전부 저장소에 실제 존재하는 PNG.

    conda activate t2i-score
    python scripts/smoke_test_scoring.py
"""
import pathlib
import sys

ROOT = pathlib.Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from PIL import Image  # noqa: E402

from src.scoring import score_image  # noqa: E402

IMAGE_PROMPTS = ROOT / "image-prompts"

# (버전, 파일명, 판정 근거) — pilot-complex3-report.md 축별 판정표 그대로.
SUCCESS = [
    ("v211_lumina2", "v211_00_three_apples_in_a_basket.png", "수량: 정확히 3개"),
    ("v211_lumina2", "v211_01_a_tree_to_the_left_of_a_house.png", "공간: 나무가 집 왼쪽"),
    ("v211_lumina2", "v211_02_a_cat_wearing_a_blue_hat.png", "속성: 파란 모자, 색 전이 없음"),
]
FAILURE = [
    ("v207_sd35-medium", "v207_01_a_tree_to_the_left_of_a_house.png", "공간: 좌우 항상 반전"),
    ("v214_zimage-turbo", "v214_00_three_apples_in_a_basket.png", "수량: 항상 2개만 생성"),
    ("v205_pixart-sigma", "v205_02_a_cat_wearing_a_blue_hat.png", "속성: 파란색이 다리/꼬리로 번짐"),
]


def _score_group(entries):
    scores = []
    for version_dir, filename, reason in entries:
        path = IMAGE_PROMPTS / version_dir / "images" / filename
        # PngInfo의 "keyword"(콘텐츠만)를 쓴다 — "prompt"는 6장이 거의 같은 스타일
        # 접미사를 공유해서 vqascore가 콘텐츠보다 그 공통 접미사를 채점하게 된다.
        keyword = Image.open(path).info["keyword"]
        result = score_image(path, keyword, ref_set=[])
        print(f"  {filename} ({reason}) -> vqascore={result['vqascore']}")
        scores.append(result["vqascore"])
    return scores


def main():
    import torch
    if torch.cuda.is_available():
        torch.cuda.reset_peak_memory_stats()

    print("성공군 (수량/공간/속성 모두 정확):")
    success_scores = _score_group(SUCCESS)
    print("실패군 (해당 축에서 오판정):")
    failure_scores = _score_group(FAILURE)

    success_mean = sum(success_scores) / len(success_scores)
    failure_mean = sum(failure_scores) / len(failure_scores)
    print(f"\nsuccess_mean={success_mean:.4f} failure_mean={failure_mean:.4f}")

    if torch.cuda.is_available():
        vram_peak_gb = round(torch.cuda.max_memory_allocated() / 1024**3, 2)
        print(f"vram_peak={vram_peak_gb}GB")

    assert success_mean > failure_mean, (
        "vqascore가 성공군을 실패군보다 높게 채점하지 못했다. 코드 버그일 수도 있지만, "
        "실패군 3장이 하필 VQAScore가 원래 약한 축(정확한 개수/좌우공간/속성귀속)이라 "
        "모델 자체의 한계일 가능성도 있다 — 실패하면 개별 이미지 점수를 먼저 보고 "
        "코드 문제(프롬프트/이미지 로딩)인지 metric 한계인지부터 구분할 것."
    )
    print("PASS: vqascore(성공군) > vqascore(실패군)")


if __name__ == "__main__":
    main()
