"""Google Custom Search Image API로 CSD golden set 후보 이미지를 카테고리별 폴더에 내려받는다.

카테고리/검색어는 bench/style-presets-v2.md 논의에서 정한 8개 lecture24 카테고리 기준
(scripts/validate_ref_set.py로 검증하기 전 원본 수집 단계).

사전 준비:
    https://console.cloud.google.com 에서 Custom Search API 활성화 + API 키 발급.
    https://programmablesearchengine.google.com 에서 검색엔진 생성 후 CX(cse id) 확보.
    (신규 계정은 "전체 웹 검색" 토글이 막혀있는 경우가 있음 — 이 경우 "검색할 사이트"에
    클립아트/벡터 스톡 도메인을 여러 개 등록해서 우회: flaticon.com, freepik.com,
    vecteezy.com, pixabay.com, shutterstock.com, istockphoto.com, stock.adobe.com,
    123rf.com, dreamstime.com, vectorstock.com 등. 설정(Setup) 화면에서 이미지 검색도 켜둘 것.
    .env 또는 환경변수에 아래 두 값 설정:
        GOOGLE_API_KEY=...
        GOOGLE_CSE_ID=...

사용:
    python -m scripts.download_ref_images --category structured-worksheet --num 15
    python -m scripts.download_ref_images --all --num 15   # 8개 카테고리 전부

출력:
    refs/lecture24/<category-slug>/<slug>_NN.<ext>
    (validate_ref_set.py --preset lecture24-<slug> --dir refs/lecture24/<slug> 로 이어서 검증)
"""
import argparse
import hashlib
import os
import pathlib
import time

import requests

ROOT = pathlib.Path(__file__).parent.parent
OUT_ROOT = ROOT / "refs" / "lecture24"
ENV_PATH = ROOT / "scripts" / ".env"


def _load_env_file(path):
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())

SEARCH_API_URL = "https://www.googleapis.com/customsearch/v1"

CATEGORIES = {
    "structured-worksheet": "blank kids worksheet template vector flat icon",
    "data-viz-chart": "flat chart icon vector",
    "historical-figure-portrait": "historical figure cartoon avatar",
    "multi-character-collab": "kids group activity flat icon",
    "intergenerational-indoor": "family living room cartoon flat",
    "single-character-cutout": "profession character flat icon",
    "labeled-science-diagram": "science diagram line art",
    "geometric-shape-set": "geometric shapes outline set vector no fill",
}


def _search_images(query, api_key, cse_id, num, start=1):
    params = {
        "key": api_key,
        "cx": cse_id,
        "q": query,
        "searchType": "image",
        "num": min(num, 10),
        "start": start,
        "safe": "active",
    }
    resp = requests.get(SEARCH_API_URL, params=params, timeout=15)
    resp.raise_for_status()
    return resp.json().get("items", [])


def download_category(slug, query, api_key, cse_id, num):
    out_dir = OUT_ROOT / slug
    out_dir.mkdir(parents=True, exist_ok=True)

    seen_hashes = set()
    saved = 0
    start = 1
    while saved < num and start < 100:
        items = _search_images(query, api_key, cse_id, num - saved, start=start)
        if not items:
            break
        for item in items:
            url = item.get("link")
            if not url:
                continue
            try:
                img_resp = requests.get(url, timeout=10)
                img_resp.raise_for_status()
                content = img_resp.content
            except requests.RequestException as e:
                print(f"  [skip] {url} ({e})")
                continue

            digest = hashlib.sha256(content).hexdigest()
            if digest in seen_hashes:
                continue
            seen_hashes.add(digest)

            ext = pathlib.Path(url.split("?")[0]).suffix.lower()
            if ext not in (".png", ".jpg", ".jpeg", ".webp"):
                ext = ".jpg"

            saved += 1
            out_path = out_dir / f"{slug}_{saved:02d}{ext}"
            out_path.write_bytes(content)
            print(f"  [{saved}/{num}] {out_path}")

            if saved >= num:
                break
        start += len(items)
        time.sleep(0.5)

    print(f"{slug}: {saved}장 저장 -> {out_dir}")
    return saved


def main():
    ap = argparse.ArgumentParser()
    group = ap.add_mutually_exclusive_group(required=True)
    group.add_argument("--category", choices=sorted(CATEGORIES), help="카테고리 하나만 수집")
    group.add_argument("--all", action="store_true", help="8개 카테고리 전부 수집")
    ap.add_argument("--num", type=int, default=15, help="카테고리당 다운로드할 장수 (기본 15)")
    args = ap.parse_args()

    _load_env_file(ENV_PATH)
    api_key = os.environ.get("GOOGLE_API_KEY")
    cse_id = os.environ.get("GOOGLE_CSE_ID")
    if not api_key or not cse_id:
        raise SystemExit("환경변수 GOOGLE_API_KEY, GOOGLE_CSE_ID를 설정하세요 (스크립트 상단 docstring 참고).")

    targets = CATEGORIES.items() if args.all else [(args.category, CATEGORIES[args.category])]
    for slug, query in targets:
        print(f"=== {slug} ({query}) ===")
        download_category(slug, query, api_key, cse_id, args.num)


if __name__ == "__main__":
    main()
