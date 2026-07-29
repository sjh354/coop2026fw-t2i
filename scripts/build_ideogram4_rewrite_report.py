"""TASK-G 후속: ideogram-4 리라이팅 4조건(passthrough/wan_style/promptenhancer/ideogram_guide,
v257/v258/v259/v260) 비교 리포트를 reports/rewrite-ideogram4-comparison/index.html로 생성한다.
scripts/rewrite_compare_ideogram4.sh가 만든 bench/scores/rewrite_ideogram4_{pass1,csd_target,
judge_lecture24}.csv를 읽는다. bench/scores/rewrite_v250_252 리포트와 같은 레이아웃(카테고리별
행, 조건별 열 그리드 + 지표 요약 테이블)이지만 열이 3개가 아니라 4개다.

    python -m scripts.build_ideogram4_rewrite_report
"""
import csv
import html
from collections import defaultdict
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
RUNS = ["v257", "v258", "v259", "v260"]
LABEL = {
    "v257": "passthrough",
    "v258": "wan_style",
    "v259": "promptenhancer",
    "v260": "ideogram_guide",
}
CLS = {"v257": "pt", "v258": "ws", "v259": "pe", "v260": "gd"}
RUN_DIR = {v: f"{v}_ideogram-4-lecture24" for v in RUNS}
AXES = ["content_present", "text_legibility", "layout_structure", "educational_fit"]


def load_notes():
    notes = {}
    for v in RUNS:
        p = ROOT / "image-prompts" / RUN_DIR[v] / f"{RUN_DIR[v]}.md"
        fm = p.read_text().split("---")[1]
        notes[v] = yaml.safe_load(fm)
    return notes


def load_pass1():
    d = defaultdict(dict)
    with open(ROOT / "bench/scores/rewrite_ideogram4_pass1.csv") as f:
        for row in csv.DictReader(f):
            v = row["run"].split("_")[0]
            d[v][row["image"]] = {
                "vqascore": float(row["vqascore"]),
                "custom_cv": float(row["custom_cv"]),
            }
    return d


def load_csd():
    d = defaultdict(dict)
    with open(ROOT / "bench/scores/rewrite_ideogram4_csd_target.csv") as f:
        for row in csv.DictReader(f):
            v = row["image"].split("_")[0]
            d[v][row["image"]] = float(row["csd_target"])
    return d


def load_judge():
    d = defaultdict(lambda: defaultdict(dict))
    with open(ROOT / "bench/scores/rewrite_ideogram4_judge_lecture24.csv") as f:
        for row in csv.DictReader(f):
            v = row["run"].split("_")[0]
            d[v][row["source"]][row["axis"]] = row["verdict"].strip().lower()
    return d


def build():
    notes = load_notes()
    pass1 = load_pass1()
    csd = load_csd()
    judge = load_judge()

    keywords = notes["v257"]["keywords"]
    prompts = notes["v257"]["prompts"]
    n = len(keywords)

    filenames = {}
    for v in RUNS:
        img_dir = ROOT / "image-prompts" / RUN_DIR[v] / "images"
        files = sorted(img_dir.glob("*.png"))
        assert len(files) == n, f"{v}: {len(files)} images, expected {n}"
        filenames[v] = [f.name for f in files]

    categories = []
    cur_cat = None
    for i, kw in enumerate(keywords):
        cat, src = kw.rsplit(" (", 1)
        src = src.rstrip(")")
        if cat != cur_cat:
            categories.append({"name": cat, "rows": []})
            cur_cat = cat
        categories[-1]["rows"].append({"idx": i, "src": src, "prompt": prompts[i]})

    avg = {}
    for v in RUNS:
        vq = [pass1[v][fn]["vqascore"] for fn in filenames[v]]
        cv = [pass1[v][fn]["custom_cv"] for fn in filenames[v]]
        cs = [csd[v][fn] for fn in filenames[v]]
        avg[v] = {
            "vqascore": sum(vq) / len(vq),
            "custom_cv": sum(cv) / len(cv),
            "csd_target": sum(cs) / len(cs),
        }

    judge_summary = {}
    for v in RUNS:
        judge_summary[v] = {}
        for axis in AXES:
            p = f = na = 0
            for src_key, axes in judge[v].items():
                verdict = axes.get(axis, "")
                if verdict == "pass":
                    p += 1
                elif verdict == "fail":
                    f += 1
                else:
                    na += 1
            denom = p + f
            judge_summary[v][axis] = (p, denom, na)

    def pct(x):
        return f"{x * 100:.1f}%"

    def bar(val, vmin, vmax, cls):
        frac = 0 if vmax == vmin else (val - vmin) / (vmax - vmin)
        frac = max(0.05, min(1, frac))
        return (
            f'<span class="scorebar {cls}"><span class="scorebar-fill" '
            f'style="width:{frac*100:.0f}%"></span></span>'
        )

    vq_all = [avg[v]["vqascore"] for v in RUNS]
    cv_all = [avg[v]["custom_cv"] for v in RUNS]
    cs_all = [avg[v]["csd_target"] for v in RUNS]

    out = []
    out.append("<!DOCTYPE html><html><head><meta charset='UTF-8'>")
    out.append("<meta name='viewport' content='width=device-width,initial-scale=1'>")
    out.append(
        "<title>ideogram-4 리라이팅 4조건 비교 — passthrough / wan_style / "
        "promptenhancer / ideogram_guide (v257-v260)</title>"
    )
    out.append("""<style>
:root { --paper:#f4f5f7; --ink:#1c2028; --ink-soft:#565f6d; --line:#dadfe6; --panel:#fff;
  --pt:#57606f; --ws:#b5651d; --pe:#7a4fb5; --gd:#1f7a5c;
  --code-bg:#eceef2; --pass:#2f8f5b; --fail:#c0392b;
  --shadow:0 1px 2px rgba(28,32,40,.06),0 6px 20px -8px rgba(28,32,40,.12); }
@media (prefers-color-scheme: dark) {
  :root { --paper:#14171d; --ink:#e7e9ee; --ink-soft:#9aa3b2; --line:#2b303a; --panel:#1b1f27;
    --pt:#9aa3b2; --ws:#d98a42; --pe:#b294e0; --gd:#4fbf95; --code-bg:#20242d;
    --pass:#5cbf8a; --fail:#e2685a; --shadow:0 1px 2px rgba(0,0,0,.3),0 10px 30px -10px rgba(0,0,0,.5); } }
:root[data-theme="dark"] { --paper:#14171d; --ink:#e7e9ee; --ink-soft:#9aa3b2; --line:#2b303a; --panel:#1b1f27;
  --pt:#9aa3b2; --ws:#d98a42; --pe:#b294e0; --gd:#4fbf95; --code-bg:#20242d;
  --pass:#5cbf8a; --fail:#e2685a; --shadow:0 1px 2px rgba(0,0,0,.3),0 10px 30px -10px rgba(0,0,0,.5); }
:root[data-theme="light"] { --paper:#f4f5f7; --ink:#1c2028; --ink-soft:#565f6d; --line:#dadfe6; --panel:#fff;
  --pt:#57606f; --ws:#b5651d; --pe:#7a4fb5; --gd:#1f7a5c; --code-bg:#eceef2; --pass:#2f8f5b; --fail:#c0392b;
  --shadow:0 1px 2px rgba(28,32,40,.06),0 6px 20px -8px rgba(28,32,40,.12); }
* { box-sizing:border-box; }
html { background:var(--paper); }
body { margin:0; background:var(--paper); color:var(--ink); font-family:ui-sans-serif,-apple-system,"Segoe UI",Roboto,sans-serif; font-size:15.5px; line-height:1.55; }
h1,h2,h3 { font-family:ui-serif,Georgia,"Noto Serif KR",serif; font-weight:600; margin:0; }
.mono,.num { font-variant-numeric:tabular-nums; font-family:ui-monospace,"SF Mono",Menlo,monospace; }
a { color:inherit; }
.wrap { max-width:1500px; margin:0 auto; padding:0 28px 96px; }
header.masthead { border-bottom:1px solid var(--line); padding:56px 0 32px; margin-bottom:40px; }
.eyebrow { text-transform:uppercase; letter-spacing:.12em; font-size:12px; color:var(--ink-soft); font-weight:600; margin-bottom:14px; }
h1.title { font-size:30px; line-height:1.2; max-width:70ch; }
.subtitle { margin-top:12px; color:var(--ink-soft); font-size:15.5px; max-width:95ch; }
section.exec { margin-bottom:48px; }
section.exec h2 { font-size:22px; margin-bottom:16px; }
section.exec ul { padding-left:22px; margin:0; }
section.exec li { margin-bottom:10px; }
.callout { background:var(--panel); border:1px solid var(--line); border-radius:10px; padding:18px 20px; margin:24px 0; font-size:13.5px; color:var(--ink-soft); }
.callout b { color:var(--ink); }
.callout.warn { border-left:3px solid var(--fail); }
.callout.note { border-left:3px solid var(--ink-soft); }
.tablewrap { overflow-x:auto; margin:20px 0 8px; }
table.avgtable { border-collapse:collapse; width:100%; min-width:760px; font-size:13.5px; }
table.avgtable th, table.avgtable td { padding:9px 12px; border-bottom:1px solid var(--line); text-align:left; }
table.avgtable th { font-size:11px; text-transform:uppercase; letter-spacing:.05em; color:var(--ink-soft); font-weight:600; }
table.avgtable td.num { text-align:right; font-family:ui-monospace,monospace; }
table.avgtable td.rowlabel { font-weight:600; border-left:3px solid var(--stripe); padding-left:9px; }
table.avgtable td.winner { font-weight:700; color:var(--stripe); }
section.category { margin-bottom:56px; }
.category-head { display:flex; align-items:baseline; gap:14px; margin-bottom:22px; padding-bottom:12px; border-bottom:1px solid var(--line); }
.category-head h2 { font-size:22px; }
.srcrow { padding:18px 0; border-bottom:1px dashed var(--line); }
.srcrow:last-child { border-bottom:none; }
.srcname { font-weight:600; font-size:13.5px; display:block; margin-bottom:6px; }
.srcprompt { margin:4px 0 14px; font-size:11.5px; color:var(--ink-soft); line-height:1.4; }
.cellpair4 { display:grid; grid-template-columns:repeat(4,1fr); gap:14px; }
@media (max-width:1100px) { .cellpair4 { grid-template-columns:repeat(2,1fr); } }
figure.cell { margin:0; background:var(--panel); border:1px solid var(--line); border-radius:8px; overflow:hidden; }
figure.cell.pt { box-shadow:inset 3px 0 0 var(--pt); }
figure.cell.ws { box-shadow:inset 3px 0 0 var(--ws); }
figure.cell.pe { box-shadow:inset 3px 0 0 var(--pe); }
figure.cell.gd { box-shadow:inset 3px 0 0 var(--gd); }
figure.cell img { width:100%; display:block; aspect-ratio:1/1; object-fit:cover; background:var(--code-bg); }
figcaption { padding:8px 10px 10px; display:flex; flex-direction:column; gap:5px; }
.condname { font-size:10px; text-transform:uppercase; letter-spacing:.04em; color:var(--ink-soft); }
.metric { display:flex; align-items:baseline; gap:5px; font-size:11.5px; }
.metric-k { color:var(--ink-soft); text-transform:uppercase; letter-spacing:.04em; font-size:10px; width:22px; flex-shrink:0; }
.metric-v { font-weight:600; min-width:3.4ch; }
.scorebar { flex:1; height:4px; border-radius:2px; background:var(--code-bg); overflow:hidden; display:inline-block; }
.scorebar-fill { display:block; height:100%; background:var(--line); }
.scorebar.pt .scorebar-fill { background:var(--pt); }
.scorebar.ws .scorebar-fill { background:var(--ws); }
.scorebar.pe .scorebar-fill { background:var(--pe); }
.scorebar.gd .scorebar-fill { background:var(--gd); }
.pillrow { display:flex; gap:4px; margin-top:4px; flex-wrap:wrap; }
.pill { display:inline-flex; align-items:center; gap:3px; font-size:10px; padding:2px 5px; border-radius:4px; background:var(--code-bg); }
.pill-k { text-transform:uppercase; letter-spacing:.02em; color:var(--ink-soft); font-size:8.5px; }
.pill.v-pass { color:var(--pass); }
.pill.v-fail { color:var(--fail); font-weight:700; }
.pill.v-na { color:var(--ink-soft); opacity:.55; }
footer { margin-top:64px; padding-top:24px; border-top:1px solid var(--line); font-size:12px; color:var(--ink-soft); }
footer code { background:var(--code-bg); padding:1px 5px; border-radius:4px; }
</style></head><body><div class="wrap">""")

    out.append('<header class="masthead">')
    out.append('<div class="eyebrow">t2i-lab · TASK-G Ideogram-4 리라이팅/캡션포맷 비교</div>')
    out.append(
        '<h1 class="title">ideogram-4 리라이팅 4조건 비교 — passthrough vs wan_style vs '
        "promptenhancer vs ideogram_guide (v257-v260)</h1>"
    )
    out.append(
        '<p class="subtitle">[Fact] 앞 3조건(passthrough/wan_style/promptenhancer)은 순수 '
        "텍스트 프롬프트를 어댑터가 naive JSON 하나의 obj 요소로 감싸 넣은 것이고, "
        "ideogram_guide는 공식 스키마(style_description + type:\"text\" 요소 포함)를 사람이 "
        "직접 작성한 캡션이다. 따라서 이 비교는 순수 4-way 리라이터 비교가 아니라 "
        "<b>\"리라이팅 품질\"과 \"캡션 포맷\"이 뒤섞인 confound</b>다 — 순위표가 아니라 "
        "참고 수치로 읽을 것.</p>"
    )
    out.append("</header>")

    out.append('<section class="exec"><h2>Executive Summary</h2><ul>')
    out.append(
        f"<li><b>[Fact]</b> vqascore·custom_cv는 <b>ideogram_guide</b>가 최고"
        f"(vq {avg['v260']['vqascore']:.3f}, cv {avg['v260']['custom_cv']:.3f}), "
        f"csd_target(스타일 유사도)은 <b>promptenhancer</b>가 최고"
        f"({avg['v259']['csd_target']:.3f})이고 <b>ideogram_guide는 csd_target에서 뚜렷하게 "
        f"최저</b>({avg['v260']['csd_target']:.3f}, 나머지 세 조건은 0.42~0.50).</li>"
    )
    out.append(
        "<li><b>[Fact]</b> VLM-judge(InternVL3-8B, 참고용 — TASK-B2/TASK-C에서 이미 "
        "κ&lt;0.6로 신뢰도 낮음이 확정된 경로)에서 ideogram_guide는 content_present pass율이 "
        f"{pct(judge_summary['v260']['content_present'][0]/max(1,judge_summary['v260']['content_present'][1]))}"
        "로 나머지 세 조건(80~100%)보다 뚜렷이 낮고, n/a(판정불가) 비율도 24개 중 13개로 가장 "
        "높다.</li>"
    )
    out.append(
        "<li><b>[Fact]</b> text_legibility 축은 ideogram_guide에서 24개 전부 n/a — 명시적으로 "
        'type:"text" 스키마 요소를 추가했음에도 judge가 텍스트 관련 판정을 시도한 이미지가 '
        "0건이다. 이 축 자체가 원본에서도 대부분 n/a(다른 조건도 3~6/24만 유효 판정)라 "
        "판단력이 약한 축이라는 점을 감안해야 한다.</li>"
    )
    out.append(
        "<li><b>[Inference]</b> csd_target 저하와 judge content_present 저하가 같은 조건"
        "(ideogram_guide)에서 함께 나타난다는 건, 손으로 작성한 구조화 캡션이 원본 VLM 캡션 "
        "소스 이미지와의 스타일 유사도·내용 일치도 양쪽에서 다른 세 조건과 다른 이미지를 "
        "만들어내고 있다는 뜻이다. 다만 표본 24개, 시드 1개라 통계 검정 없이는 '악화'라고 "
        "단정할 수 없다.</li>"
    )
    out.append(
        "<li><b>[Fact]</b> 그레이스케일 표준편차 스크리닝(사전 채점 전) 결과 96장 전부 "
        "std&gt;8로 완전 단색/차단화면은 없었다. 다만 ideogram_guide의 평균 std(17.5)가 나머지 "
        "세 조건(36~44)보다 뚜렷이 낮다 — 시각적으로 더 단조로운(flat) 이미지 경향으로, "
        "csd_target/judge 저하와 방향이 일치한다.</li>"
    )
    out.append(
        "<li><b>[Recommendation]</b> 텍스트 렌더링 성공 여부(TASK-G의 원래 목적)는 육안 판정만 "
        "유효하다고 이미 결론난 사항이므로, 아래 이미지 그리드에서 라벨/글자가 필요한 카테고리"
        "(Structured Worksheet Template, Data Visualization Chart, Labeled Science Diagram)의 "
        "ideogram_guide 열을 직접 확인해달라. VLM-judge와 자동 지표만으로는 이 질문에 답할 수 "
        "없다.</li>"
    )
    out.append("</ul></section>")

    # summary table
    out.append('<div class="tablewrap"><table class="avgtable"><thead><tr>')
    out.append("<th>조건</th><th>avg vqascore</th><th>avg custom_cv</th><th>avg csd_target</th>")
    out.append(
        "<th>judge content_present</th><th>judge text_legibility</th>"
        "<th>judge layout_structure</th><th>judge educational_fit</th></tr></thead><tbody>"
    )
    winners = {
        "vqascore": max(RUNS, key=lambda v: avg[v]["vqascore"]),
        "custom_cv": max(RUNS, key=lambda v: avg[v]["custom_cv"]),
        "csd_target": max(RUNS, key=lambda v: avg[v]["csd_target"]),
    }
    for v in RUNS:
        cls = CLS[v]
        row = f'<tr style="--stripe:var(--{cls})"><td class="rowlabel">{LABEL[v]}</td>'
        for key in ("vqascore", "custom_cv", "csd_target"):
            val = avg[v][key]
            wcls = " winner" if winners[key] == v else ""
            row += f'<td class="num{wcls}">{val:.4f}</td>'
        for axis in AXES:
            p, denom, na = judge_summary[v][axis]
            rate = f"{p}/{denom}" if denom else "n/a"
            row += f'<td class="num">{rate} <span class="mono" style="color:var(--ink-soft);font-size:10px">(na={na})</span></td>'
        row += "</tr>"
        out.append(row)
    out.append("</tbody></table></div>")

    for cat in categories:
        out.append('<section class="category"><div class="category-head"><h2>%s</h2></div>' % html.escape(cat["name"]))
        for row in cat["rows"]:
            i = row["idx"]
            out.append('<div class="srcrow"><span class="srcname">%s</span>' % html.escape(row["src"]))
            out.append('<p class="srcprompt">%s</p>' % html.escape(row["prompt"][:280]))
            out.append('<div class="cellpair4">')
            for v in RUNS:
                fn = filenames[v][i]
                cls = CLS[v]
                vq = pass1[v][fn]["vqascore"]
                cv = pass1[v][fn]["custom_cv"]
                cs = csd[v][fn]
                out.append(f'<figure class="cell {cls}">')
                out.append(f'<img src="../../image-prompts/{RUN_DIR[v]}/images/{fn}" loading="lazy" alt="{html.escape(fn)}">')
                out.append("<figcaption>")
                out.append(f'<span class="condname">{LABEL[v]}</span>')
                out.append(
                    f'<div class="metric"><span class="metric-k">VQ</span>'
                    f'{bar(vq, min(vq_all), max(vq_all), cls)}<span class="metric-v">{vq:.3f}</span></div>'
                )
                out.append(
                    f'<div class="metric"><span class="metric-k">CV</span>'
                    f'{bar(cv, min(cv_all), max(cv_all), cls)}<span class="metric-v">{cv:.3f}</span></div>'
                )
                out.append(
                    f'<div class="metric"><span class="metric-k">CS</span>'
                    f'{bar(cs, min(cs_all), max(cs_all), cls)}<span class="metric-v">{cs:.3f}</span></div>'
                )
                out.append("</figcaption></figure>")
            out.append("</div></div>")
        out.append("</section>")

    out.append(
        "<footer>생성: <code>scripts/build_ideogram4_rewrite_report.py</code> · 데이터: "
        "<code>bench/scores/rewrite_ideogram4_{pass1,csd_target,judge_lecture24}.csv</code> · "
        "이미지: <code>image-prompts/v257-v260_ideogram-4-lecture24/images/</code></footer>"
    )
    out.append("</div></body></html>")

    out_dir = ROOT / "reports/rewrite-ideogram4-comparison"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "index.html").write_text("".join(out))
    print(f"-> {out_dir / 'index.html'}")


if __name__ == "__main__":
    build()
