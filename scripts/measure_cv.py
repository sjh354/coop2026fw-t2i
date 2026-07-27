"""VLM 대신 OpenCV로 count/attribute spec item을 결정론적으로 측정한다.
spec item에 "measurer": "cv"가 있고 type이 count 또는 attribute인 것만 처리한다.
대상은 배경이 흰 단색인 구조·기하 카테고리(Structured Worksheet Template 등)로 한정 —
YOLO/SAM 같은 객체 검출 모델은 쓰지 않는다.

    conda run -n t2i-score python -m scripts.measure_cv \
        --images image-prompts/v243_pixart-sigma-lecture24/images \
        --spec configs/benchmarks/vlm-prompts-spec.json \
        --out bench/scores/v243_pixart-sigma-lecture24/measure_cv.csv
"""
import argparse
import csv
import json
import pathlib
import re
import sys

import cv2
import numpy as np

ROOT = pathlib.Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
from scripts.judge_spec import FILENAME_RE  # noqa: E402

NAMED_COLORS = {
    "red": (0, 100, 100), "orange": (15, 100, 100), "yellow": (30, 100, 100),
    "green": (60, 100, 100), "cyan": (90, 100, 100), "blue": (115, 100, 100),
    "magenta": (150, 100, 100), "brown": (15, 60, 45), "black": (0, 0, 5),
    "white": (0, 0, 95), "gray": (0, 0, 50),
}


def count_regions(img, min_area, aspect_range, mode="blobs"):
    """mode='blobs': 채도 있는 덩어리(핀 등)를 연결요소로 분리해 센다.
    mode='holes': 흰/밝은 내부 영역(박스 등)을 연결요소로 분리해 센다 —
    이미지 테두리에 닿는 가장 큰 연결요소(그림 바깥 배경)는 제외한다."""
    h_img, w_img = img.shape[:2]
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    sat, val = hsv[:, :, 1], hsv[:, :, 2]

    if mode == "blobs":
        mask = ((sat > 60) & (val > 60)).astype(np.uint8) * 255
    else:
        mask = ((sat < 30) & (val > 200)).astype(np.uint8) * 255

    n_labels, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    border_labels = set(labels[0, :]) | set(labels[-1, :]) | set(labels[:, 0]) | set(labels[:, -1])

    count = 0
    for label in range(1, n_labels):
        if mode == "holes" and label in border_labels:
            continue
        area = stats[label, cv2.CC_STAT_AREA]
        if area < min_area or area > 0.5 * h_img * w_img:
            continue
        w, h = stats[label, cv2.CC_STAT_WIDTH], stats[label, cv2.CC_STAT_HEIGHT]
        aspect = h / w if w else 0
        if aspect_range[0] <= aspect <= aspect_range[1]:
            count += 1
    return count


def _nearest_color_name(hsv_pixel):
    h, s, v = hsv_pixel
    if v < 40:
        return "black"
    if s < 40:
        return "white" if v > 80 else "gray"
    best_name, best_dist = None, float("inf")
    for name, (nh, ns, nv) in NAMED_COLORS.items():
        if name in ("black", "white", "gray"):
            continue
        dist = min(abs(h - nh), 180 - abs(h - nh))
        if dist < best_dist:
            best_name, best_dist = name, dist
    return best_name


def region_colors(img, min_area=200):
    """흰 배경 위 색이 있는 덩어리들을 좌->우 순서로 색이름 리스트로 반환한다."""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    _, binary = cv2.threshold(gray, 245, 255, cv2.THRESH_BINARY_INV)
    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

    blobs = []
    for c in contours:
        if cv2.contourArea(c) < min_area:
            continue
        mask = np.zeros(gray.shape, dtype=np.uint8)
        cv2.drawContours(mask, [c], -1, 255, -1)
        median_hsv = np.median(hsv[mask == 255], axis=0)
        x, _, _, _ = cv2.boundingRect(c)
        blobs.append((x, _nearest_color_name(median_hsv)))
    blobs.sort(key=lambda b: b[0])
    return [name for _, name in blobs]


def polygon_sides(contour, circle_vertex_threshold=8):
    epsilon = 0.02 * cv2.arcLength(contour, True)
    approx = cv2.approxPolyDP(contour, epsilon, True)
    n = len(approx)
    return "circle" if n >= circle_vertex_threshold else n


def _measure_item(img, item):
    if item["type"] == "count":
        mode = "holes" if "box" in item["check"].lower() else "blobs"
        aspect_range = (1.5, 10.0) if mode == "holes" else (0.5, 2.0)
        measured = count_regions(img, min_area=300, aspect_range=aspect_range, mode=mode)
        expected = item["expect"]["value"]
        verdict = "yes" if measured == expected else "no"
        return measured, expected, verdict
    if item["type"] == "attribute" and "color" in item["check"].lower():
        colors = region_colors(img)
        verdict = "yes" if len(colors) == len(set(colors)) and colors else "no"
        return ",".join(colors), "all_distinct", verdict
    raise ValueError(f"CV로 측정할 수 없는 item type: {item['type']}")


def measure_images(images_dir, spec_by_id, out_dir=None):
    images_dir = pathlib.Path(images_dir)
    rows = []
    for img_path in sorted(images_dir.glob("*.png")):
        m = FILENAME_RE.match(img_path.name)
        if not m:
            continue
        spec_id = f"{m.group(1)}_{m.group(2)}"
        entry = spec_by_id.get(spec_id)
        if entry is None:
            continue
        img = cv2.imread(str(img_path))
        for item in entry["spec_items"]:
            if item.get("measurer") != "cv":
                continue
            measured, expected, verdict = _measure_item(img, item)
            rows.append({
                "prompt_id": spec_id, "item_id": item["id"], "type": item["type"],
                "measurer": "cv", "measured_value": measured, "expected_value": expected,
                "verdict": verdict,
            })
            if out_dir:
                _save_debug_overlay(img, item, out_dir / f"{img_path.stem}_{item['id']}.png")
    return rows


def _save_debug_overlay(img, item, out_path):
    mode = "holes" if item["type"] == "count" and "box" in item["check"].lower() else "blobs"
    aspect_range = (1.5, 10.0) if mode == "holes" else (0.5, 2.0)
    h_img, w_img = img.shape[:2]
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    sat, val = hsv[:, :, 1], hsv[:, :, 2]
    mask = (((sat > 60) & (val > 60)) if mode == "blobs" else ((sat < 30) & (val > 200))).astype(np.uint8) * 255
    n_labels, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    border_labels = set(labels[0, :]) | set(labels[-1, :]) | set(labels[:, 0]) | set(labels[:, -1])

    overlay = img.copy()
    for label in range(1, n_labels):
        if mode == "holes" and label in border_labels:
            continue
        area = stats[label, cv2.CC_STAT_AREA]
        if area < 300 or area > 0.5 * h_img * w_img:
            continue
        x, y, w, h = stats[label, cv2.CC_STAT_LEFT], stats[label, cv2.CC_STAT_TOP], \
            stats[label, cv2.CC_STAT_WIDTH], stats[label, cv2.CC_STAT_HEIGHT]
        aspect = h / w if w else 0
        color = (0, 0, 255) if aspect_range[0] <= aspect <= aspect_range[1] else (255, 0, 0)
        cv2.rectangle(overlay, (x, y), (x + w, y + h), color, 2)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(out_path), overlay)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--images", required=True)
    ap.add_argument("--spec", default=str(ROOT / "configs" / "benchmarks" / "vlm-prompts-spec.json"))
    ap.add_argument("--out", required=True)
    ap.add_argument("--debug-overlay-dir", help="컨투어를 그린 PNG를 저장할 디렉토리 (파일럿 육안 확인용)")
    args = ap.parse_args()

    entries = json.loads(pathlib.Path(args.spec).read_text(encoding="utf-8"))
    spec_by_id = {e["id"]: e for e in entries}
    out_dir = pathlib.Path(args.debug_overlay_dir) if args.debug_overlay_dir else None

    rows = measure_images(args.images, spec_by_id, out_dir=out_dir)
    out_path = pathlib.Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "prompt_id", "item_id", "type", "measurer", "measured_value", "expected_value", "verdict",
        ])
        writer.writeheader()
        writer.writerows(rows)
    print(f"{len(rows)}행 -> {out_path}")


if __name__ == "__main__":
    main()
