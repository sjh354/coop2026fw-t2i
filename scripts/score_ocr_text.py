"""TASK-G 5번: 텍스트 렌더링 파일럿 채점. configs/keywords/text-render-pilot10.yaml의
키워드에 박힌 큰따옴표 단어(target word)를 PaddleOCR로 읽어낸 텍스트와 비교한다.

floor effect 게이트: 세 후보(FLUX.2-klein-4b, Lumina2, PixArt-Sigma) 모두 match_rate가
0에 가까우면(설계 기준 <10%) OCR 기반 평가 자체가 무의미하므로 보고만 하고 중단한다
(TASK-G 검증 기준).

GPU 불필요 — PaddleOCR CPU 추론으로 로컬에서 돌리는 것을 전제로 한다(157/23 역할 분리와
무관, scoring 모델 env를 GPU 생성 서버에 새로 안 얹기 위함).

    python -m scripts.score_ocr_text --note image-prompts/vNNN_pixart-sigma-text-render-pilot/vNNN_pixart-sigma-text-render-pilot.md \
        --out bench/ocr_pilot/results.csv
"""
import argparse
import csv
import pathlib
import re

import frontmatter

ROOT = pathlib.Path(__file__).parent.parent
CSV_FIELDS = ["model", "prompt_id", "keyword", "target_word", "ocr_text", "matched", "precision", "recall", "f1"]


def target_word(keyword):
    m = re.search(r'"([A-Za-z]+)"', keyword)
    return m.group(1).upper() if m else None


def normalize_tokens(text):
    return [t.upper() for t in re.findall(r"[A-Za-z]+", text)]


def score_one(ocr, image_path, target):
    result = ocr.predict(str(image_path))
    predicted_tokens = []
    for page in result:
        for text in page.get("rec_texts", []):
            predicted_tokens.extend(normalize_tokens(text))

    matched = target in predicted_tokens
    tp = predicted_tokens.count(target) if matched else 0
    tp = min(tp, 1)  # target은 이미지당 1회 등장 기대
    precision = tp / len(predicted_tokens) if predicted_tokens else 0.0
    recall = 1.0 if matched else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return matched, precision, recall, f1, " ".join(predicted_tokens)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--note", required=True, help="image-prompts/vNNN_.../vNNN_....md")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    from paddleocr import PaddleOCR
    ocr = PaddleOCR(lang="en")

    post = frontmatter.load(args.note)
    note_path = pathlib.Path(args.note)
    img_dir = note_path.parent / "images"
    model = post["model"]
    keywords = post["keywords"]
    version = post["version"]

    out_path = pathlib.Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    write_header = not out_path.exists()
    rows = []
    with out_path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        if write_header:
            writer.writeheader()

        for i, keyword in enumerate(keywords):
            target = target_word(keyword)
            if target is None:
                print(f"[warn] 큰따옴표 단어 없음, 스킵: {keyword}")
                continue
            image_path = next(img_dir.glob(f"{version}_{i:02d}_*.png"))
            matched, precision, recall, f1, ocr_text = score_one(ocr, image_path, target)
            row = {
                "model": model, "prompt_id": i, "keyword": keyword, "target_word": target,
                "ocr_text": ocr_text, "matched": matched,
                "precision": round(precision, 3), "recall": round(recall, 3), "f1": round(f1, 3),
            }
            writer.writerow(row)
            rows.append(row)
            print(f"[{i + 1}/{len(keywords)}] target={target} matched={matched} ocr='{ocr_text}'")

    match_rate = sum(r["matched"] for r in rows) / len(rows) if rows else 0.0
    print(f"done. model={model} match_rate={match_rate:.2f} ({sum(r['matched'] for r in rows)}/{len(rows)})")
    if match_rate < 0.1:
        print(f"[floor-effect] {model}: match_rate < 10% — OCR 기반 평가가 이 모델엔 무의미할 수 있음")


if __name__ == "__main__":
    main()
