"""Bing 이미지 검색 HTML을 직접 파싱해 CSD golden set 후보 이미지를 카테고리별로 내려받는다.

download_ref_images.py(Google Custom Search API)가 Google Cloud 백엔드 키 검증 지연 문제로
당장 동작하지 않아 만든 대체 경로 — API 키 없이 requests+정규식 파싱만으로 동작한다.
검색은 Google PSE에 등록했던 것과 같은 클립아트/벡터 스톡 도메인들을 하나씩 순회하며
site:도메인 필터로 검색한다(Bing은 OR로 묶은 site: 여러 개는 강제 필터가 아니라 약한
힌트로만 취급해서 관련 없는 도메인이 섞이므로, 도메인당 개별 쿼리로 확실히 강제).
카테고리/검색어(CATEGORIES)를 download_ref_images.py와 그대로 공유한다.

사용:
    python -m scripts.scrape_ref_images --category structured-worksheet --num 15
    python -m scripts.scrape_ref_images --all --num 15

출력:
    refs/lecture24/<category-slug>/<slug>_NN.<ext>  (download_ref_images.py와 동일 경로)

주의:
    Bing HTML 구조 의존적 스크레이핑이라 언제든 깨질 수 있음. robots.txt/이용약관상
    개인 연구용 소량 수집 목적으로만 쓸 것 — 대량/상시 크롤링 용도 아님.
"""
import argparse
import hashlib
import html
import json
import pathlib
import re
import time

import requests

from scripts.download_ref_images import CATEGORIES, OUT_ROOT

BING_URL = "https://www.bing.com/images/search"
DOMAINS = [
    "flaticon.com", "freepik.com", "vecteezy.com", "pixabay.com",
    "shutterstock.com", "istockphoto.com", "stock.adobe.com",
    "123rf.com", "dreamstime.com", "vectorstock.com",
]
HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}

RESULT_RE = re.compile(r'\sm="({.*?})"')


def _search_images(query, domain=None, offset=0):
    """domain이 주어지면 단일 site: 필터로 검색(Bing은 OR로 묶은 site: 여러 개는 약한
    힌트로만 취급하고 단일 site:도메인 필터만 확실히 강제하므로 도메인별로 따로 검색).
    domain=None이면 필터 없는 일반 웹 이미지 검색."""
    q = f"site:{domain} {query}" if domain else query
    params = {"q": q, "first": offset, "count": 35}
    resp = requests.get(BING_URL, params=params, headers=HEADERS, timeout=15)
    resp.raise_for_status()

    seen = set()
    urls = []
    for raw in RESULT_RE.findall(resp.text):
        try:
            item = json.loads(html.unescape(raw))
        except json.JSONDecodeError:
            continue
        murl, purl = item.get("murl"), item.get("purl", "")
        if not murl or murl in seen:
            continue
        if domain and domain not in purl:
            continue
        seen.add(murl)
        urls.append(murl)
    return urls


def _drain(query, domain, out_dir, slug, num, seen_hashes, saved):
    offset = 0
    while saved < num and offset < 70:
        urls = _search_images(query, domain, offset=offset)
        if not urls:
            break
        for url in urls:
            if saved >= num:
                break
            try:
                img_resp = requests.get(url, headers=HEADERS, timeout=10)
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
            print(f"  [{saved}/{num}] {out_path} ({domain or 'general web'})")

        offset += 35
        time.sleep(1.0)
    return saved


def download_category(slug, query, num):
    out_dir = OUT_ROOT / slug
    out_dir.mkdir(parents=True, exist_ok=True)

    seen_hashes = set()
    saved = 0
    for domain in DOMAINS:
        if saved >= num:
            break
        saved = _drain(query, domain, out_dir, slug, num, seen_hashes, saved)

    if saved < num:
        print(f"  [fallback] 스톡 도메인에서 {saved}장뿐 — 일반 웹 검색으로 나머지 채움")
        saved = _drain(query, None, out_dir, slug, num, seen_hashes, saved)

    print(f"{slug}: {saved}장 저장 -> {out_dir}")
    return saved


def main():
    ap = argparse.ArgumentParser()
    group = ap.add_mutually_exclusive_group(required=True)
    group.add_argument("--category", choices=sorted(CATEGORIES), help="카테고리 하나만 수집")
    group.add_argument("--all", action="store_true", help="8개 카테고리 전부 수집")
    ap.add_argument("--num", type=int, default=15, help="카테고리당 다운로드할 장수 (기본 15)")
    args = ap.parse_args()

    targets = CATEGORIES.items() if args.all else [(args.category, CATEGORIES[args.category])]
    for slug, query in targets:
        print(f"=== {slug} ({query}) ===")
        download_category(slug, query, args.num)


if __name__ == "__main__":
    main()
