"""TASK-G: ideogram-oss/ideogram4 공식 prompting guide(docs/prompting.md, CaptionVerifier)를
그대로 따르는 JSON 캡션 24개(8 카테고리 x 3 VLM 소스)를 손으로 작성해 image-prompts/rewrite/
ideogram_guide.json에 쓴다. scripts/rewrite.py의 3개 backend(passthrough/wan_style/promptenhancer)와
같은 출력 위치·구조를 따라 scripts/lecture_generate.py --prompts-json / scripts/ideogram_probe.py로
그대로 흘릴 수 있게 한다.

현재 프로덕션 어댑터(src/adapters/ideogram.py)의 _to_caption_json은 프롬프트 전체를 obj 요소 하나에
욱여넣는 naive wrap이라 style_description이 없고 type:"text" 요소도 전혀 안 쓴다 -> 학습 분포와
어긋난 캡션을 매번 넣고 있었던 셈이다. 이 스크립트는 원본 24개 프롬프트가 실제로 명시한 내용만 가지고
(없는 문구를 지어내지 않고) style_description + background + elements(obj/text)로 분해한다.
type:"text" 요소는 원본 프롬프트가 실제로 인용부호로 준 문자열이 있는 경우에만 추가한다
(예: qwen 소스의 'bar graphs', 'Animal Cell', 'UNIT 17 test' 제목) — "no text" 라고 명시한
프롬프트(claude 소스 대부분)에는 절대 text 요소를 넣지 않는다.

    python -m scripts.ideogram_guide_captions --out image-prompts/rewrite/ideogram_guide.json
"""
import argparse
import json
import pathlib

ROOT = pathlib.Path(__file__).parent.parent
SOURCES = ("claude", "chatgpt", "qwen2.5-vl-7b-instruct")

FLAT_STYLE = dict(
    aesthetics="simple, cheerful, classroom-friendly",
    lighting="even flat lighting, no dramatic shadows",
    medium="illustration",
    art_style="flat vector children's educational illustration, thick clean black outlines, minimal shading",
)


def _style(color_palette=None, **overrides):
    style = dict(FLAT_STYLE, **overrides)
    ordered = {k: style[k] for k in ("aesthetics", "lighting", "medium", "art_style")}
    if color_palette:
        ordered["color_palette"] = color_palette
    return ordered


def _obj(desc, color_palette=None):
    el = {"type": "obj", "desc": desc}
    if color_palette:
        el["color_palette"] = color_palette
    return el


def _text(text, desc, color_palette=None):
    el = {"type": "text", "text": text, "desc": desc}
    if color_palette:
        el["color_palette"] = color_palette
    return el


def _caption(hld, background, elements, color_palette=None):
    return {
        "high_level_description": hld,
        "style_description": _style(color_palette=color_palette),
        "compositional_deconstruction": {"background": background, "elements": elements},
    }


# 각 항목: type(카테고리) -> {source: caption dict}. 원본 프롬프트 문구(NextJob.md TASK-G 조사 시
# configs/benchmarks/vlm-prompts.json에서 읽은 전문)에 없는 내용은 추가하지 않는다.
CATEGORIES = {
    "Structured Worksheet Template": {
        "claude": _caption(
            "A blank children's worksheet with six empty boxes above a row of colored location pins.",
            "A plain white page.",
            [
                _obj("Six empty rectangular boxes with thick black outlines and white interiors, "
                     "arranged in two staggered rows, completely blank inside."),
                _obj("A single horizontal black baseline near the bottom of the page."),
                _obj("Six small teardrop-shaped location pins in different colors placed along the "
                     "baseline, each connected to one box above by a thin vertical black stroke."),
            ],
        ),
        "chatgpt": _caption(
            "A printable elementary school worksheet template with six large empty boxes and colored "
            "location pins, ready for handwriting.",
            "A plain white page with balanced spacing and a clean vector layout.",
            [
                _obj("Six large empty rectangular boxes with thick black outlines, arranged in two "
                     "staggered rows, writing areas completely blank."),
                _obj("Six small colored teardrop-shaped location pins along a horizontal baseline, "
                     "each connected to one box by a thin vertical stroke."),
            ],
        ),
        "qwen2.5-vl-7b-instruct": None,  # 원문이 claude 소스와 동일 (baseline과 동일하게 재사용)
    },
    "Data Visualization Chart": {
        "claude": _caption(
            "A simple vertical bar chart with six bars of different colors and heights on a white "
            "background, no numbers or labels.",
            "A plain white worksheet background with thin horizontal gridlines behind the bars.",
            [
                _obj("A plain vertical axis line on the left edge of the chart."),
                _obj("Six vertical bars of equal width standing on a horizontal baseline, left to "
                     "right colored yellow, blue, orange, red, brown and green, the blue bar tallest "
                     "and the orange bar shortest, a small toy icon centered below each bar."),
            ],
            color_palette=["#F2C230", "#2E5AAC", "#F2871E", "#D62828", "#8B5E3C", "#3C9F45", "#FFFFFF"],
        ),
        "chatgpt": _caption(
            "A printable worksheet with a colorful bar graph comparing six favorite-toy categories.",
            "A clean white page with balanced classroom-friendly layout.",
            [
                _obj("A bar graph with six differently colored bars and a small toy icon below each "
                     "category."),
                _obj("Labeled axes, numbered comprehension questions, and blank answer lines below the "
                     "chart, left completely blank of any specific wording."),
            ],
        ),
        "qwen2.5-vl-7b-instruct": _caption(
            "A bar graph worksheet titled 'bar graphs' showing the favorite toys of Grade 1 learners.",
            "A white worksheet background with a beige header section.",
            [
                _text("bar graphs", "Small bold black title text at the top of the worksheet."),
                _obj("Six bars colored yellow, blue, orange, red, brown and green in that order, each "
                     "with a toy icon below it: a doll, a robot, a basketball, a dinosaur, a truck, "
                     "and a teddy bear."),
                _text("1\n2\n3\n4\n5\n6\n7\n8\n9\n10\n11\n12",
                      "Small black numeric y-axis scale running vertically from 1 to 12."),
            ],
            color_palette=["#F2C230", "#2E5AAC", "#F2871E", "#D62828", "#8B5E3C", "#3C9F45", "#F5E6C8"],
        ),
    },
    "Historical Figure Portrait": {
        "claude": _caption(
            "A friendly cartoon portrait of a nineteenth-century American statesman, upper body only.",
            "A plain white background.",
            [
                _obj("A man with a dark beard along the jawline and no mustache, wearing a black formal "
                     "coat and bow tie, calm smiling expression, facing slightly left, tall dark hat "
                     "removed."),
                _obj("A striped and starred flag hanging behind his right shoulder."),
                _obj("A rolled parchment scroll placed near his left side."),
            ],
        ),
        "chatgpt": _caption(
            "An educational cartoon illustration of a single historical political figure, upper body "
            "only.",
            "A plain white background with balanced composition.",
            [
                _obj("A historical figure in formal period clothing with distinctive facial hair and "
                     "hairstyle, calm expression."),
                _obj("A national flag on one side and a rolled parchment scroll on the other as "
                     "symbolic props."),
            ],
        ),
        "qwen2.5-vl-7b-instruct": _caption(
            "A cartoon-style portrait of Abraham Lincoln, upper body only, facing slightly left.",
            "A plain white background, simple and colorful style with soft edges.",
            [
                _obj("Abraham Lincoln with a dark beard along the jawline and no mustache, black "
                     "formal coat, white shirt and dark bow tie, tall hat removed, calm smiling "
                     "expression."),
                _obj("An American flag with red and white stripes and white stars on a blue field "
                     "hanging behind his right shoulder."),
                _obj("A rolled parchment scroll in a pale cream tone resting near his left side."),
            ],
        ),
    },
    "Multi-Character Classroom Collaboration": {
        "claude": _caption(
            "Four elementary school students sitting around a shared classroom table sharing their "
            "projects.",
            "A simple plain classroom background.",
            [
                _obj("Two girls on the left and a boy and a girl on the right sitting around a table, "
                     "bright cheerful expressions; the girl at front left holds up a folded paper "
                     "booklet with both hands, the boy holds a marker pen."),
                _obj("Colored drawings of a park and pencils scattered on the table surface."),
                _obj("The girl on the right seated in a wheelchair."),
            ],
        ),
        "chatgpt": _caption(
            "A Korean elementary school textbook illustration of four students sharing their creative "
            "projects around a table.",
            "A simple classroom background with soft pastel colors.",
            [
                _obj("Four students each presenting a different work such as a park drawing, booklet, "
                     "or poster while smiling and talking; the student on the right uses a wheelchair."),
                _obj("A speech bubble shape above each student's head, left free of specific wording."),
            ],
        ),
        "qwen2.5-vl-7b-instruct": _caption(
            "A group of four children at a shared classroom table, each engaged with a drawing of a "
            "park.",
            "A classroom with a simple wooden table and chairs, cartoonish and colorful style.",
            [
                _obj("The girl on the front left holds an open folded booklet showing a drawing of a "
                     "park; the other three children are focused on their own drawings; the girl in a "
                     "wheelchair on the right has a completed park drawing."),
                _obj("A speech bubble shape above each child's head, left free of specific wording."),
            ],
        ),
    },
    "Intergenerational Indoor Scene": {
        "claude": _caption(
            "An elderly couple sitting on a sofa while a child kneels nearby writing notes in a cozy "
            "living room.",
            "A living room with a soft green rug.",
            [
                _obj("An elderly woman in a magenta cardigan and yellow scarf gesturing with one hand, "
                     "and an elderly man in a light blue shirt smiling, both with gray hair, sitting "
                     "side by side on a beige fabric sofa."),
                _obj("A young child in a red hoodie kneeling on the floor in the foreground with their "
                     "back to the viewer, writing on a small notepad with a pencil."),
                _obj("A floor lamp with a green shade behind the sofa, and a wooden side table with a "
                     "small potted plant."),
            ],
        ),
        "chatgpt": _caption(
            "An elementary school textbook illustration of a child interviewing two grandparents in a "
            "cozy living room.",
            "A living room with minimal background details and warm family atmosphere.",
            [
                _obj("A child kneeling on the floor in the foreground with their back to the viewer, "
                     "writing notes on a small notepad."),
                _obj("Two grandparents sitting side by side on a beige sofa answering questions with "
                     "friendly expressions."),
                _obj("A green-shaded floor lamp, a wooden side table, and a small potted plant."),
            ],
        ),
        "qwen2.5-vl-7b-instruct": _caption(
            "A cozy living room scene with an elderly couple on a sofa and a child taking notes on the "
            "floor.",
            "A living room with a soft green rug, warm-toned and cartoonish style.",
            [
                _obj("An elderly woman in a magenta cardigan, gray pants and yellow scarf with glasses, "
                     "smiling, seated beside an elderly man in a light blue shirt and dark pants on a "
                     "beige fabric sofa."),
                _obj("A child in a red hoodie kneeling on the floor in the foreground with their back "
                     "to the viewer, holding a small notepad and pencil."),
                _obj("A green floor lamp with a light shade, a wooden side table with a small potted "
                     "plant."),
            ],
        ),
    },
    "Single-Character Cutout": {
        "claude": _caption(
            "An elderly woman sewing fabric at a treadle sewing machine, upper body cutout.",
            "A flat pale blue rounded background shape, nothing shown below the table.",
            [
                _obj("An elderly woman with gray hair tied in a bun and round glasses, wearing a white "
                     "long-sleeve blouse and green vest, gentle focused smile."),
                _obj("An old black treadle sewing machine mounted on a wooden table, both her hands "
                     "guiding a folded pink and white checkered cloth under the needle."),
            ],
        ),
        "chatgpt": _caption(
            "An educational cutout illustration of a single character using a sewing machine at a work "
            "table.",
            "A simple flat solid-color background shape without additional scenery.",
            [
                _obj("A character seated at a work table using a hands-on tool such as a sewing "
                     "machine, upper body and work surface only, everything below the table cropped "
                     "out."),
            ],
        ),
        "qwen2.5-vl-7b-instruct": _caption(
            "A cartoon-style elderly woman sewing a piece of fabric at a treadle sewing machine.",
            "A flat pale blue rounded shape, nothing shown below the table, simple and colorful style.",
            [
                _obj("An elderly woman with gray hair tied in a bun, round glasses, white long-sleeve "
                     "blouse and green vest, guiding pink and white checkered fabric under the needle "
                     "with both hands."),
                _obj("A black treadle sewing machine with silver accents mounted on a wooden table."),
            ],
        ),
    },
    "Labeled Science Diagram": {
        "claude": _caption(
            "A black and white line drawing of an animal cell for a science worksheet, no text.",
            "A white background.",
            [
                _obj("One large oval cell outlined with a thin double membrane line."),
                _obj("A single large circle in the center representing the nucleus, four oval "
                     "organelles with internal wavy stripes distributed around it, a cluster of short "
                     "curved ribbon shapes on the left side, two plain empty ovals on the right and "
                     "lower left, thin black outlines with light gray fill only inside the organelles."),
            ],
        ),
        "chatgpt": _caption(
            "A printable elementary science worksheet with a simplified animal cell diagram with "
            "labeled organelles.",
            "A white background with black vector outlines and grayscale fills.",
            [
                _obj("A cell membrane, cytoplasm, nucleus, mitochondria, and vacuole, each connected to "
                     "a label with a straight leader line."),
                _obj("A color key at the bottom of the worksheet."),
            ],
        ),
        "qwen2.5-vl-7b-instruct": _caption(
            "A diagram of an animal cell titled 'Animal Cell', labeled with its cellular components.",
            "A white background, thin black line drawing with light gray fills.",
            [
                _text("Animal Cell", "Bold black title text at the top of the worksheet."),
                _obj("A cell membrane drawn as a thin double outline, a large circle nucleus at the "
                     "center, and mitochondria, vacuole and cytoplasm distinguished by different gray "
                     "tones and internal stripe patterns."),
                _text("cell membrane\ncytoplasm\nnucleus\nmitochondria\nvacuole",
                      "Small black labels next to straight leader lines pointing to each part of the "
                      "cell."),
            ],
        ),
    },
    "Geometric Shape Set": {
        "claude": _caption(
            "A set of eight separate geometric outline shapes evenly spaced on a white background, no "
            "text.",
            "A plain white background.",
            [
                _obj("Eight shapes arranged in two rows of four with thin black outlines and no fill: "
                     "a regular hexagon, a square, a rhombus standing on one corner, an equilateral "
                     "triangle, a trapezoid with the shorter side on top, a wide rectangle, a circle, "
                     "and a regular pentagon, each isolated with clear white space around it."),
            ],
        ),
        "chatgpt": _caption(
            "A printable elementary mathematics worksheet introducing eight basic geometric shapes.",
            "A white background with clean typography and printable worksheet layout.",
            [
                _obj("Eight shapes with black vector outlines, each with a blank answer line beneath "
                     "it: regular hexagon, square, rhombus, equilateral triangle, trapezoid, "
                     "rectangle, circle, and regular pentagon."),
                _obj("A section asking students to count sides and corners and identify real-world "
                     "objects matching each shape, left free of specific wording."),
            ],
        ),
        "qwen2.5-vl-7b-instruct": _caption(
            "A black and white worksheet titled 'UNIT 17 test' with eight geometric shapes in two "
            "rows.",
            "A white background, black and white worksheet style.",
            [
                _text("UNIT 17 test", "Bold black title text at the top of the worksheet."),
                _obj("A space for the student's name below the title."),
                _obj("Eight shapes in two rows of four with a blank line underneath each for the "
                     "student's answer: a hexagon, a square, a rhombus, a triangle, a trapezoid, a "
                     "rectangle, a circle, and a pentagon."),
                _obj("A bottom section with images of a house, donut, sailboat, and playing card for "
                     "students to identify by shape."),
            ],
        ),
    },
}


def build_items():
    items = []
    for cat_type, sources in CATEGORIES.items():
        entry = {"type": cat_type}
        reused = sources["claude"] if sources.get("qwen2.5-vl-7b-instruct") is None else None
        for source in SOURCES:
            caption = sources.get(source) if sources.get(source) is not None else reused
            entry[source] = {"prompt": json.dumps(caption, separators=(",", ":"), ensure_ascii=False)}
        items.append(entry)
    return items


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "image-prompts" / "rewrite" / "ideogram_guide.json"))
    args = ap.parse_args()

    items = build_items()
    out_path = pathlib.Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(items, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"wrote {len(items)} categories -> {out_path}")


if __name__ == "__main__":
    main()
