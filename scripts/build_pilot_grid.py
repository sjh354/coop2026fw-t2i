"""방언(dialect) 파일럿 결과(experiment=educational-flat-pilot)를 스캔해서
image-prompts/pilot-dialect-report.md 를 생성한다.

키워드별 행 × 모델별 shared|dialect 열로 이미지를 나란히 배치하고,
리소스 표(vram/sec/block rate)를 붙인다. review_app.py는 건드리지 않는
독립 산출물 — Obsidian ![[...]] 임베드 관례를 그대로 따른다
(build_manifest.py의 이미지 파일명 규칙과 동일: {version}_{i:02d}_{slug(kw)}.png).

모델별 판정(방언으로 개선됨/개선 안 됨/block)은 육안 비교가 필요해 이 스크립트가
자동 채우지 않는다 — "## 판정" 섹션에 빈 표만 만들어두고 리뷰 후 수동 기입.
"""
import pathlib
import re
import sys

import frontmatter

ROOT = pathlib.Path(__file__).parent.parent
OUT = ROOT / "image-prompts"
EXP = "educational-flat-pilot"


def slug(text):
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def load_pilot_notes():
    notes = []
    for vdir in sorted(OUT.iterdir()):
        if not vdir.is_dir():
            continue
        note_path = vdir / f"{vdir.name}.md"
        if not note_path.exists():
            continue
        post = frontmatter.load(str(note_path))
        meta = post.metadata
        if meta.get("experiment") != EXP:
            continue
        notes.append((vdir, meta))
    return notes


def image_path(vdir, meta, i, kw):
    version = vdir.name.split("_", 1)[0]
    fname = f"{version}_{i:02d}_{slug(kw)}.png"
    fpath = vdir / "images" / fname
    return fname if fpath.exists() else None


def build_grid_section(notes, models, keywords):
    by_model_cond = {(m["model"], m["condition"]): (v, m) for v, m in notes}
    lines = ["## 키워드 × 모델(shared|dialect) 그리드\n"]
    for i, kw in enumerate(keywords):
        lines.append(f"### {kw}\n")
        header = "| 조건 | " + " | ".join(models) + " |"
        sep = "|---|" + "---|" * len(models)
        lines.append(header)
        lines.append(sep)
        for cond in ("shared", "dialect"):
            row = [cond]
            for m in models:
                entry = by_model_cond.get((m, cond))
                if not entry:
                    row.append("—")
                    continue
                vdir, meta = entry
                fname = image_path(vdir, meta, i, kw)
                row.append(f"![[{fname}]]" if fname else "(missing)")
            lines.append("| " + " | ".join(row) + " |")
        lines.append("")
    return "\n".join(lines)


def build_resource_table(notes):
    lines = ["## 리소스 표\n", "| 모델 | 조건 | vram_peak_gb | sec_per_image | status |", "|---|---|---|---|---|"]
    for vdir, meta in notes:
        lines.append(
            f"| {meta.get('model')} | {meta.get('condition')} | "
            f"{meta.get('vram_peak_gb')} | {meta.get('sec_per_image')} | {meta.get('status')} |"
        )
    return "\n".join(lines)


def build_block_rate(notes, models):
    lines = [
        "## Block rate (모델별)\n",
        "> ⚠ ideogram-4는 `raise_on_caption_issues=False`라 safety filter block이 "
        "exit 0으로 끝날 수 있다. 아래 status는 pilot_dialect.sh의 exit code/로그 매칭 "
        "기반이라 block을 놓칠 수 있음 — ideogram-4 결과 이미지는 육안으로 빈/차단된 "
        "프레임이 있는지 확인할 것.\n",
        "| 모델 | shared | dialect |", "|---|---|---|"]
    by_model_cond = {(m["model"], m["condition"]): m for _, m in notes}
    for m in models:
        s = by_model_cond.get((m, "shared"))
        d = by_model_cond.get((m, "dialect"))
        s_status = s.get("status") if s else "no-run"
        d_status = d.get("status") if d else "no-run"
        lines.append(f"| {m} | {s_status} | {d_status} |")
    return "\n".join(lines)


def build_verdict_table(models):
    lines = [
        "## 판정 (육안 비교 후 수동 기입)\n",
        "| 모델 | 판정 (개선됨 / 능력 한계 / block 등) | 다음 단계 권고 |",
        "|---|---|---|",
    ]
    for m in models:
        lines.append(f"| {m} | TODO | TODO |")
    return "\n".join(lines)


KEYWORD_RATIONALE = {
    "an apple": "단순 단일 사물 (대조군)",
    "a cat": "얼굴 있는 생물 (눈/얼굴 붕괴 판별력)",
    "a house": "구조물/약한 복합 (파트 구성 스트레스)",
    "a butterfly": "대칭+미세 패턴 (좌우대칭/디테일 스트레스)",
    "a car": "다부품 인공물 (수량/구조 스트레스)",
}


def build_keyword_rationale_section(keywords):
    lines = ["## 선정 키워드 + 사유\n", "| 키워드 | 사유 |", "|---|---|"]
    for kw in keywords:
        lines.append(f"| {kw} | {KEYWORD_RATIONALE.get(kw, '(rationale not recorded)')} |")
    return "\n".join(lines)


def main():
    notes = load_pilot_notes()
    if not notes:
        print(f"'{EXP}' 실험 노트가 없다. pilot_dialect.sh를 먼저 실행할 것.", file=sys.stderr)
        sys.exit(1)

    models = sorted({m["model"] for _, m in notes})
    keywords = notes[0][1].get("keywords", [])

    sections = [
        f"# 방언 파일럿 결과 ({EXP})\n",
        f"모델 {len(models)}개, 키워드 {len(keywords)}개, run {len(notes)}개.\n",
        build_keyword_rationale_section(keywords),
        build_grid_section(notes, models, keywords),
        build_resource_table(notes),
        build_block_rate(notes, models),
        build_verdict_table(models),
    ]

    report_path = OUT / "pilot-dialect-report.md"
    report_path.write_text("\n\n".join(sections) + "\n", encoding="utf-8")
    print(f"report: {report_path}")


if __name__ == "__main__":
    main()
