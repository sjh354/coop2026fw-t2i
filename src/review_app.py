"""버전을 훑어보고, 평가하고, 비교한다.

기존 streamlit.py에서 바뀐 것:
  - 모델별 필터 (사이드바)
  - vram_peak_gb / sec_per_image 표시 — 지금 단계에선 이게 평가의 절반
  - Compare 모드에서 같은 키워드를 모델별로 가로 정렬 (모델 비교가 주 목적이므로)

Run:
    streamlit run src/review_app.py
"""
import pathlib
import shutil

import frontmatter
import streamlit as st

ROOT = pathlib.Path(__file__).parent.parent / "image-prompts"
REFS_ROOT = pathlib.Path(__file__).parent.parent / "refs"


def list_versions():
    return sorted(d for d in ROOT.iterdir()
                  if d.is_dir() and (d / f"{d.name}.md").exists())


@st.cache_data(show_spinner=False)
def _load_cached(note_path_str, mtime):
    return frontmatter.load(note_path_str)


def load(vdir):
    note_path = vdir / f"{vdir.name}.md"
    return _load_cached(str(note_path), note_path.stat().st_mtime)


def images(vdir):
    return sorted((vdir / "images").glob("*.png"))


def save(vdir, post):
    (vdir / f"{vdir.name}.md").write_text(frontmatter.dumps(post), encoding="utf-8")


def labels_for(post, imgs):
    kw = post.get("keywords", [])
    return {p.name: (kw[i] if i < len(kw) else p.name) for i, p in enumerate(imgs)}


def stat_line(post):
    return (f"model={post.get('model')} · vram={post.get('vram_peak_gb')}GB · "
            f"{post.get('sec_per_image')}s/img · steps={post.get('steps')} · "
            f"guidance={post.get('guidance_scale')} · seed={post.get('seed')} · "
            f"quant={post.get('quantization')} · {post.get('created')}")


st.set_page_config(layout="wide", page_title="T2I Lab")

if not ROOT.exists() or not list_versions():
    st.error("image-prompts/ 가 비어있다. 먼저 src/generate.py 를 돌릴 것.")
    st.stop()

versions = list_versions()
posts = {v.name: load(v) for v in versions}
vmap = {v.name: v for v in versions}

models = sorted({p.get("model", "?") for p in posts.values()})
picked_models = st.sidebar.multiselect("Model filter", models, default=models)
names = [n for n in vmap if posts[n].get("model") in picked_models]

mode = st.sidebar.radio("Mode", ["Browse / Rate", "Compare"])

if mode == "Browse / Rate":
    name = st.sidebar.selectbox("Version", names)
    vdir, post = vmap[name], posts[name]
    imgs = images(vdir)
    labels = labels_for(post, imgs)

    st.title(name)
    if post.get("status") != "done":
        st.warning(f"status={post.get('status')} — 생성이 끝나지 않았을 수 있음 (OOM?)")
    st.markdown("**Style prompt**")
    st.code(post.get("style", ""), language=None, wrap_lines=True)
    if post.get("negative_prompt"):
        st.markdown("**Negative prompt**")
        st.code(post["negative_prompt"], language=None, wrap_lines=True)
    st.caption(stat_line(post))

    st.subheader("Evaluation")
    c1, c2 = st.columns([1, 3])
    rating = c1.slider("Rating (0 = unrated)", 0, 5, int(post.get("rating") or 0))
    tags = c2.text_input("Tags (comma-separated)", ", ".join(post.get("tags", [])))
    issues = st.text_area("Issues / notes", post.get("issues", ""), height=80)
    best = st.multiselect("Best picks", [p.name for p in imgs],
                          default=post.get("best", []),
                          format_func=lambda n: labels.get(n, n))

    if st.button("Save", type="primary"):
        post["rating"] = rating or None
        post["tags"] = [t.strip() for t in tags.split(",") if t.strip()]
        post["issues"] = issues
        post["best"] = best
        save(vdir, post)
        st.success("Saved to note.")

    st.subheader("Scoring")
    ref_name = st.text_input("Ref set (refs/<name>/) — 비워두면 golden set 없이 채점",
                              post.get("experiment", ""))
    sc1, sc2 = st.columns(2)
    if sc1.button("➕ Add best picks to golden set"):
        if not best:
            st.warning("먼저 Best picks를 골라야 golden set에 추가할 수 있다.")
        elif not ref_name:
            st.warning("Ref set 이름을 입력해야 golden set에 추가할 수 있다.")
        else:
            ref_dir = REFS_ROOT / ref_name
            ref_dir.mkdir(parents=True, exist_ok=True)
            for n in best:
                shutil.copy(vdir / "images" / n, ref_dir / n)
            st.success(f"{len(best)}장을 refs/{ref_name}/ 에 추가했다.")
    if sc2.button("Compute scores"):
        import score  # heavy (torch/CLIP) — 버튼을 눌렀을 때만 로드
        with st.spinner("CLIP으로 채점 중..."):
            post = score.score_version(vdir, ref_name or None)
        posts[name] = post
        csd_note = "" if post.get("csd_mean") is not None else " (csd 없음 — golden set 미지정)"
        st.success(f"harmonic_mean={post.get('harmonic_mean')}{csd_note}")
    if post.get("harmonic_mean") is not None:
        st.caption(f"vqascore={post.get('vqascore_mean')} · csd={post.get('csd_mean')} · "
                   f"flatness={post.get('flatness_mean')} · harmonic={post.get('harmonic_mean')}")

    golden_files = {p.name for p in (REFS_ROOT / ref_name).glob("*.png")} if ref_name else set()

    st.subheader("Images")
    cols = st.columns(5)
    for i, p in enumerate(imgs):
        with cols[i % 5]:
            star = "⭐ " if p.name in best else ""
            golden = "🏆 " if p.name in golden_files else ""
            st.image(str(p), caption=f"{golden}{star}{labels[p.name]}", width="stretch")

else:  # Compare — 같은 키워드를 모델별로 가로 비교
    picks = st.sidebar.multiselect("Versions", names, default=names[:3])
    n_rows = st.sidebar.slider("Keywords to show", 1, 30, 6)
    if not picks:
        st.info("비교할 버전을 고를 것.")
        st.stop()

    st.subheader("Resources")
    st.table([{"version": n, "model": posts[n].get("model"),
               "vram_gb": posts[n].get("vram_peak_gb"),
               "sec/img": posts[n].get("sec_per_image"),
               "rating": posts[n].get("rating"),
               "harmonic": posts[n].get("harmonic_mean")} for n in picks])

    default_ref = posts[picks[0]].get("experiment", "")
    ref_name = st.sidebar.text_input("Ref set (refs/<name>/)", default_ref)
    ref_dir = REFS_ROOT / ref_name if ref_name else None

    st.markdown(
        "<style>.st-key-golden-grid button[kind='primary']"
        "{background-color:#21c55d;border-color:#21c55d;color:white;}</style>",
        unsafe_allow_html=True,
    )

    grids = {n: images(vmap[n]) for n in picks}
    kws = posts[picks[0]].get("keywords", [])

    if "golden_pending" not in st.session_state:
        st.session_state.golden_pending = {}
    pending = st.session_state.golden_pending

    def on_disk(img_path):
        return bool(ref_dir and (ref_dir / img_path.name).exists())

    with st.container(key="golden-grid"):
        for row in range(min(n_rows, len(kws))):
            st.markdown(f"**{kws[row]}**")
            cols = st.columns(len(picks))
            for col, n in zip(cols, picks):
                with col:
                    st.caption(posts[n].get("model", n))
                    if row < len(grids[n]):
                        img_path = grids[n][row]
                        st.image(str(img_path), width="stretch")
                        key = f"{n}/{img_path.name}"
                        is_golden = pending.get(key, on_disk(img_path))
                        label = "✅ Golden" if is_golden else "➕ Golden"
                        if st.button(label, key=f"golden_{n}_{row}",
                                     type="primary" if is_golden else "secondary",
                                     disabled=not ref_name):
                            pending[key] = not is_golden
                    else:
                        st.write("—")

    changes = {k: v for k, v in pending.items()
               if v != on_disk(next(p for p in grids[k.split("/", 1)[0]]
                                     if p.name == k.split("/", 1)[1]))}
    if st.button(f"Submit golden set changes ({len(changes)})",
                 type="primary", disabled=not changes):
        for key, want_golden in changes.items():
            n, fname = key.split("/", 1)
            img_path = next(p for p in grids[n] if p.name == fname)
            if want_golden:
                ref_dir.mkdir(parents=True, exist_ok=True)
                shutil.copy(img_path, ref_dir / fname)
            else:
                (ref_dir / fname).unlink()
        st.session_state.golden_pending = {}
        st.rerun()
