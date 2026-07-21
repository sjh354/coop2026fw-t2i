"""수업용 lecture24 벤치 전용 VLM-judge — bench_v1의 counting/spatial/attribute
축·expected 문장이 없는 자유형 프롬프트(24개, keyword_set=lecture_vlm24)용으로
scripts/judge.py와 별도 축 4개를 쓴다. 모델 로딩(_load_judge_model)과
호출부(_call_judge_vlm, system 파라미터 추가됨)는 judge.py 걸 그대로 재사용한다.

축: content_present, text_legibility(텍스트 없는 프롬프트면 n/a), layout_structure,
educational_fit — 상세 정의는 JUDGE_SYSTEM 참고. bench_v1과 달리 verdict에 n/a를
모델이 직접 골라도 되므로 judge.py의 _parse_judge_response(pass/fail만 허용)는
재사용하지 않고 이 파일에서 따로 파싱한다.

    conda run -n t2i-judge python -m scripts.judge_lecture24 \
        --runs image-prompts/v243_pixart-sigma-lecture24 image-prompts/v244_flux2-klein-4b-nf4-lecture24
"""
import argparse
import csv
import json
import pathlib
import re
import sys

from PIL import Image

ROOT = pathlib.Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
from scripts.judge import _load_judge_model, _call_judge_vlm  # noqa: E402

SCORES_DIR = ROOT / "bench" / "scores"

AXES = ("content_present", "text_legibility", "layout_structure", "educational_fit")

JUDGE_SYSTEM = (
    "너는 초등 교육용 삽화 T2I 생성 이미지를 채점하는 심사위원이다. "
    "주어진 프롬프트를 이미지가 얼마나 충족하는지 아래 4개 축 각각에 대해 "
    "pass, fail, 또는 해당사항 없으면 n/a로 판정해라.\n"
    "- content_present: 프롬프트가 명시한 주요 대상/개수가 이미지에 실제로 있는가\n"
    "- text_legibility: 제목/축라벨/워크시트 문구가 읽을 수 있는 실제 단어로 렌더됐는가 "
    "(프롬프트가 텍스트를 요구하지 않으면 n/a)\n"
    "- layout_structure: 그리드/축/라벨 위치/도형 배열이 프롬프트 설명과 일치하는가\n"
    "- educational_fit: 깔끔한 flat 스타일, 나이대에 맞는 톤, 왜곡·잡음이 없는가\n"
    "각 축마다 근거를 한국어 한 문장으로 설명해라. 다른 설명 없이 JSON 배열만 출력해라: "
    '[{"axis": "<축이름>", "verdict": "pass"|"fail"|"n/a", "rationale": "<한 문장>"}, ...]'
)


def _prompt_from_png(image_path):
    info = Image.open(image_path).info
    if "prompt" not in info:
        raise ValueError(f"{image_path}에 PngInfo prompt 메타데이터가 없습니다.")
    return info["prompt"]


def _parse_judge_response(raw):
    start, end = raw.find("["), raw.rfind("]")
    if start == -1 or end == -1:
        raise ValueError(f"JSON 배열을 찾을 수 없음: {raw[:200]!r}")
    parsed = json.loads(raw[start:end + 1])
    by_axis = {item["axis"]: item for item in parsed}
    missing = set(AXES) - set(by_axis)
    if missing:
        raise ValueError(f"응답에 축 누락: {missing}")
    result = {}
    for axis in AXES:
        item = by_axis[axis]
        if item["verdict"] not in ("pass", "fail", "n/a"):
            raise ValueError(f"verdict 값이 pass/fail/n/a가 아님: {item}")
        result[axis] = {"verdict": item["verdict"], "rationale": str(item.get("rationale", ""))}
    return result


def _judge_item(image_path, prompt):
    user_text = f"프롬프트: {prompt}"
    raw = _call_judge_vlm(image_path, user_text, system=JUDGE_SYSTEM)
    try:
        return _parse_judge_response(raw), False
    except (ValueError, json.JSONDecodeError, KeyError) as e:
        feedback = user_text + f"\n[이전 출력 파싱 실패: {e}] 반드시 JSON 배열만, 지정된 형식으로 다시 출력해라."
        raw2 = _call_judge_vlm(image_path, feedback, system=JUDGE_SYSTEM)
        try:
            return _parse_judge_response(raw2), True
        except (ValueError, json.JSONDecodeError, KeyError):
            return {axis: {"verdict": "parse_error", "rationale": "파싱 실패(재시도 후에도)"}
                    for axis in AXES}, True


def judge_run(run_dir):
    run_dir = pathlib.Path(run_dir)
    import frontmatter
    note_path = run_dir / f"{run_dir.name}.md"
    post = frontmatter.load(str(note_path))
    if post.get("keyword_set") != "lecture_vlm24":
        print(f"[skip] {run_dir.name}: keyword_set={post.get('keyword_set')!r} (lecture_vlm24 아님)")
        return []

    images = sorted((run_dir / "images").glob("*.png"))
    rows = []
    for i, img_path in enumerate(images):
        m = re.match(r"v\d+_\d+_(.+)_(claude|chatgpt|qwen)\.png", img_path.name)
        cat_slug, source = m.group(1), m.group(2)
        prompt = _prompt_from_png(img_path)
        judged, retried = _judge_item(img_path, prompt)
        for axis in AXES:
            rows.append({
                "run": run_dir.name, "model": post.get("model"), "type": cat_slug, "source": source,
                "axis": axis, "verdict": judged[axis]["verdict"], "rationale": judged[axis]["rationale"],
                "retried": retried,
            })
        print(f"[{i + 1}/{len(images)}] {cat_slug} ({source}) -> "
              f"{[judged[a]['verdict'] for a in AXES]}")
    return rows


def write_csv(rows, out_path):
    out_path = pathlib.Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["run", "model", "type", "source", "axis", "verdict", "rationale", "retried"]
    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", nargs="+", required=True, help="image-prompts/vNNN_model 디렉토리들")
    ap.add_argument("--force", action="store_true", help="이미 결과가 있어도 재실행")
    args = ap.parse_args()

    import torch
    if torch.cuda.is_available():
        torch.cuda.reset_peak_memory_stats()

    for run_dir in args.runs:
        run_name = pathlib.Path(run_dir).name
        out_path = SCORES_DIR / run_name / "judge_lecture24.csv"
        if out_path.exists() and not args.force:
            print(f"[skip] {out_path} 이미 존재 (--force로 재실행)")
            continue
        rows = judge_run(run_dir)
        if rows:
            write_csv(rows, out_path)
            print(f"{len(rows)}행 -> {out_path}")

    if torch.cuda.is_available():
        vram_peak_gb = round(torch.cuda.max_memory_allocated() / 1024**3, 2)
        print(f"vram_peak={vram_peak_gb}GB")


if __name__ == "__main__":
    main()
