"""VLM-as-judge — 로컬 VLM(기본 InternVL3-8B-hf, 2026-07-28부터)으로 bench_v1 축
(counting/spatial/attribute)별 pass/fail을 판정한다. 예전 scoring.py의 Anthropic API
기반 score_image_vlm을 대체한다 (API 키 불필요, 3090에서 로컬 추론).

기본 judge를 Qwen2.5-VL-7B-Instruct에서 InternVL3-8B-hf로 변경(TASK-C 삼각검증에서
사람 채점과의 κ가 세 judge 중 최고인 0.61) — 전용 conda env도 t2i-judge2로 바뀐다
(envs/README.md 참고, transformers 버전 핀 필수). Qwen2.5-VL로 교차검증하려면
model_repo="Qwen/Qwen2.5-VL-7B-Instruct"를 명시하고 env도 t2i-judge로 바꿀 것.

    python -m scripts.judge --runs image-prompts/v223_lumina2 image-prompts/v224_lumina2
    python -m scripts.judge --runs image-prompts/v223_lumina2 --force   # 기존 결과 있어도 재실행

동작:
    1. run의 note frontmatter에서 keyword_set을 확인한다 — 'bench_v1'이 아니면 스킵
       (item_id 역산이 build_bench_v1_keywords.py가 만든 순서 보존을 전제하기 때문).
    2. 이미지 파일명 인덱스로 configs/benchmarks/bench_v1.yaml의 prompts[i]를 찾아
       item_id/axes/expected를 얻는다 (PNG/note 어디에도 item_id 자체는 없음 — 인덱스
       기반 역산. src/scoring.py의 _run_context와 동일한 가정).
    3. counting/spatial/attribute 3축 모두에 대해 행을 만든다 — item의 axes에 없는
       축은 verdict=n/a로 채우고 VLM을 부르지 않는다. axes에 있는 축만 한 번의 VLM
       호출로 같이 판정한다.
    4. 구조화 JSON 파싱 실패 시 피드백을 붙여 1회 재생성, 그래도 실패하면
       verdict=parse_error (meta로 retried 기록).

출력: bench/scores/{run}/judge.csv (item_id, axis, verdict, rationale, retried) +
run/model 컬럼(scripts/merge_results.py 조인 키).

스모크 테스트(--smoke-map)는 bench_v1 이전 파일럿 PNG용 — 아래 참고.
"""
import argparse
import csv
import json
import pathlib
import re
import sys

import frontmatter
import yaml

ROOT = pathlib.Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

BENCH_V1 = ROOT / "configs" / "benchmarks" / "bench_v1.yaml"
SCORES_DIR = ROOT / "bench" / "scores"
IMAGE_PROMPTS = ROOT / "image-prompts"

JUDGE_MODEL_REPO = "OpenGVLab/InternVL3-8B-hf"
AXES = ("counting", "spatial", "attribute")

JUDGE_SYSTEM = (
    "너는 K-12 교육 삽화용 T2I 생성 이미지를 채점하는 심사위원이다. "
    "주어진 '통과 기준' 문장을 이미지가 충족하는지, 지정된 축들에 대해서만 각각 "
    "pass 또는 fail로 판정해라. 각 축마다 근거를 한국어 한 문장으로 설명해라. "
    "다른 설명 없이 JSON 배열만 출력해라: "
    '[{"axis": "<축이름>", "verdict": "pass"|"fail", "rationale": "<한 문장>"}, ...]'
)

_model_cache = {}


def _load_judge_model(model_repo=JUDGE_MODEL_REPO, quant4bit=False):
    """model_repo에 'qwen'이 들어있으면 Qwen2.5-VL 전용 클래스로, 아니면
    transformers의 범용 AutoModelForImageTextToText로 로드한다(Gemma-3 등).
    두 백엔드가 서로 다른 채팅 템플릿/입력 처리 방식을 쓰므로 _call_judge_vlm에서
    같은 model_repo 기준으로 분기한다."""
    key = (model_repo, quant4bit)
    if key not in _model_cache:
        import torch
        from transformers import AutoProcessor

        if "qwen" in model_repo.lower():
            from transformers import Qwen2_5_VLForConditionalGeneration
            model = Qwen2_5_VLForConditionalGeneration.from_pretrained(
                model_repo, torch_dtype=torch.bfloat16, device_map="cuda"
            )
        else:
            from transformers import AutoModelForImageTextToText
            kwargs = {"torch_dtype": torch.bfloat16, "device_map": "cuda"}
            if quant4bit:
                from transformers import BitsAndBytesConfig
                kwargs = {
                    "quantization_config": BitsAndBytesConfig(
                        load_in_4bit=True, bnb_4bit_compute_dtype=torch.bfloat16
                    ),
                    "device_map": "cuda",
                }
            model = AutoModelForImageTextToText.from_pretrained(model_repo, **kwargs)
        processor = AutoProcessor.from_pretrained(model_repo)
        _model_cache[key] = (model, processor)
    return _model_cache[key]


def _call_judge_vlm(image_path, user_text, system=JUDGE_SYSTEM, model_repo=JUDGE_MODEL_REPO, quant4bit=False):
    model, processor = _load_judge_model(model_repo, quant4bit)
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": [
            {"type": "image", "image": str(image_path)},
            {"type": "text", "text": user_text},
        ]},
    ]
    if "qwen" in model_repo.lower():
        from qwen_vl_utils import process_vision_info
        text = processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        image_inputs, video_inputs = process_vision_info(messages)
        inputs = processor(text=[text], images=image_inputs, videos=video_inputs,
                            padding=True, return_tensors="pt").to(model.device)
    else:
        inputs = processor.apply_chat_template(
            messages, tokenize=True, add_generation_prompt=True,
            return_dict=True, return_tensors="pt",
        ).to(model.device)
    generated = model.generate(**inputs, max_new_tokens=400)
    trimmed = [out[len(inp):] for inp, out in zip(inputs.input_ids, generated)]
    return processor.batch_decode(trimmed, skip_special_tokens=True,
                                   clean_up_tokenization_spaces=False)[0]


def _parse_judge_response(raw, covered_axes):
    start, end = raw.find("["), raw.rfind("]")
    if start == -1 or end == -1:
        raise ValueError(f"JSON 배열을 찾을 수 없음: {raw[:200]!r}")
    parsed = json.loads(raw[start:end + 1])
    by_axis = {item["axis"]: item for item in parsed}
    missing = set(covered_axes) - set(by_axis)
    if missing:
        raise ValueError(f"응답에 축 누락: {missing}")
    result = {}
    for axis in covered_axes:
        item = by_axis[axis]
        if item["verdict"] not in ("pass", "fail"):
            raise ValueError(f"verdict 값이 pass/fail이 아님: {item}")
        result[axis] = {"verdict": item["verdict"], "rationale": str(item.get("rationale", ""))}
    return result


def _judge_item(image_path, expected, covered_axes, content_prompt=None):
    """covered_axes에 대해서만 VLM을 부르고, 실패 시 피드백 붙여 1회 재시도."""
    if not covered_axes:
        return {}, False

    user_text = (
        f"통과 기준: {expected}\n"
        f"판정할 축: {', '.join(covered_axes)}\n"
        + (f"프롬프트(참고용): {content_prompt}\n" if content_prompt else "")
    )
    raw = _call_judge_vlm(image_path, user_text)
    try:
        return _parse_judge_response(raw, covered_axes), False
    except (ValueError, json.JSONDecodeError, KeyError) as e:
        feedback = user_text + f"\n[이전 출력 파싱 실패: {e}] 반드시 JSON 배열만, 지정된 형식으로 다시 출력해라."
        raw2 = _call_judge_vlm(image_path, feedback)
        try:
            return _parse_judge_response(raw2, covered_axes), True
        except (ValueError, json.JSONDecodeError, KeyError):
            return {axis: {"verdict": "parse_error", "rationale": "파싱 실패(재시도 후에도)"}
                    for axis in covered_axes}, True


def _bench_v1_prompts():
    return yaml.safe_load(BENCH_V1.read_text(encoding="utf-8"))["prompts"]


def judge_run(run_dir, bench_v1_prompts):
    run_dir = pathlib.Path(run_dir)
    note_path = run_dir / f"{run_dir.name}.md"
    post = frontmatter.load(str(note_path))
    if post.get("keyword_set") != "bench_v1":
        print(f"[skip] {run_dir.name}: keyword_set={post.get('keyword_set')!r} (bench_v1 아님)")
        return []

    images = sorted((run_dir / "images").glob("*.png"))
    rows = []
    for i, img_path in enumerate(images):
        item = bench_v1_prompts[i]
        covered = [a for a in AXES if a in item.get("axes", [])]
        judged, retried = _judge_item(img_path, item["expected"], covered)
        for axis in AXES:
            if axis in judged:
                verdict, rationale = judged[axis]["verdict"], judged[axis]["rationale"]
            else:
                verdict, rationale = "n/a", ""
            rows.append({
                "run": run_dir.name, "model": post.get("model"), "item_id": item["id"],
                "axis": axis, "verdict": verdict, "rationale": rationale,
                "retried": retried if axis in covered else False,
            })
        print(f"[{i + 1}/{len(images)}] {item['id']} -> {[judged[a]['verdict'] for a in covered] or 'n/a'}")
    return rows


def judge_smoke_map(map_path):
    """bench_v1 이전 파일럿 PNG 등, note에 item_id 역산 근거가 없는 이미지용 스모크 경로.
    map_path: 이미지 경로 -> {axes, expected} 임시 매핑 (예: tests/judge_smoke_map.yaml)."""
    data = yaml.safe_load(pathlib.Path(map_path).read_text(encoding="utf-8"))
    rows = []
    for entry in data["images"]:
        img_path = ROOT / entry["path"]
        covered = list(entry["axes"])
        judged, retried = _judge_item(img_path, entry["expected"], covered)
        item_id = pathlib.Path(entry["path"]).stem
        for axis in AXES:
            if axis in judged:
                verdict, rationale = judged[axis]["verdict"], judged[axis]["rationale"]
            else:
                verdict, rationale = "n/a", ""
            rows.append({
                "run": "smoke", "model": None, "item_id": item_id,
                "axis": axis, "verdict": verdict, "rationale": rationale,
                "retried": retried if axis in covered else False,
            })
        print(f"{item_id} -> {[judged[a]['verdict'] for a in covered] or 'n/a'}")
    return rows


def write_csv(rows, out_path):
    out_path = pathlib.Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["run", "model", "item_id", "axis", "verdict", "rationale", "retried"]
    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", nargs="*", default=[], help="image-prompts/vNNN_model 디렉토리들")
    ap.add_argument("--smoke-map", help="tests/judge_smoke_map.yaml 같은 스모크 전용 매핑 파일")
    ap.add_argument("--force", action="store_true", help="이미 judge 결과가 있어도 재실행")
    args = ap.parse_args()

    if not args.runs and not args.smoke_map:
        sys.exit("--runs 또는 --smoke-map 중 하나는 필요합니다.")

    import torch
    if torch.cuda.is_available():
        torch.cuda.reset_peak_memory_stats()

    if args.smoke_map:
        out_path = SCORES_DIR / "judge_smoke.csv"
        if out_path.exists() and not args.force:
            print(f"[skip] {out_path} 이미 존재 (--force로 재실행)")
        else:
            rows = judge_smoke_map(args.smoke_map)
            write_csv(rows, out_path)
            print(f"{len(rows)}행 -> {out_path}")

    if args.runs:
        bench_v1_prompts = _bench_v1_prompts()
        for run_dir in args.runs:
            run_name = pathlib.Path(run_dir).name
            out_path = SCORES_DIR / run_name / "judge.csv"
            if out_path.exists() and not args.force:
                print(f"[skip] {out_path} 이미 존재 (--force로 재실행)")
                continue
            rows = judge_run(run_dir, bench_v1_prompts)
            if rows:
                write_csv(rows, out_path)
                print(f"{len(rows)}행 -> {out_path}")

    if torch.cuda.is_available():
        vram_peak_gb = round(torch.cuda.max_memory_allocated() / 1024**3, 2)
        print(f"vram_peak={vram_peak_gb}GB")


if __name__ == "__main__":
    main()
