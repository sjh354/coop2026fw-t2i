# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Research harness for comparing text-to-image model candidates (PixArt-Sigma, SDXL, Flux2-Klein, Z-Image, SD3.5, Sana, Lumina2, Qwen-Image, Ideogram) under the same prompts, to see which fits a 16GB VRAM budget. Pre-production research phase — licensing/quantization concerns are deliberately deferred; the goal right now is just "does it run, and how much VRAM/time does it take."

## Commands

Each model runs in its own conda env (diffusers version pins conflict across models — see `envs/README.md`):

```bash
conda activate t2i-<name>          # e.g. t2i-pixart, t2i-sdxl, t2i-flux2
python -m src.generate --model <model> --exp <experiment>
# e.g. python -m src.generate --model pixart-sigma --exp coloring-book
```

Review/compare results:

```bash
streamlit run src/review_app.py
```

There is no build/lint/test step — this is a script-driven experiment harness, not a library.

## Architecture: three orthogonal axes

Every run is a combination of **model × experiment (style) × keyword set**, each living in its own YAML file under `configs/`:

- `configs/models/<name>.yaml` — repo id, adapter name, conda env, dtype, steps, guidance, `supports_negative`, quantization
- `configs/experiments/<name>.yaml` — style/negative prompt text, seed, and which keyword set to use
- `configs/keywords/<name>.yaml` — a fixed benchmark keyword list (e.g. `basic30`) — this is the comparison baseline across models, so don't edit it casually
- `configs/benchmarks/vlm-prompts.json` — 24 complete prompts (8 categories × 3 VLM sources) extracted from real textbook images. As of 2026-07-24 this is the project's fixed **Baseline** test ("lecture24" runs, see `bench/results.md`) — don't edit casually, same rule as keyword sets above

`src/generate.py` combines them as `f"{keyword}, {exp['style']}"` and writes one image per keyword. **Prompts are never passed via CLI or hardcoded** — that's the point of this structure. To try a new style, copy the experiment file to a new name (don't overwrite — overwriting breaks traceability of what a past version's prompt was) and change `--exp`:

```bash
cp configs/experiments/coloring-book.yaml configs/experiments/flat-illust.yaml
# edit name: and style: in the new file
python -m src.generate --model pixart-sigma --exp flat-illust
```

Swapping just `--model` reruns the same experiment prompts against a different model.

## Adapters (`src/adapters/`)

`adapters/__init__.py::load(model_cfg)` does a **lazy import** of `adapters.<model_cfg['adapter']>` and calls its `build(cfg)`, which returns a `(prompt, negative, seed) -> PIL.Image` closure. Lazy import is required: each model's env has a different diffusers version, and importing all adapters eagerly would fail outside the exact matching env.

- `generic.py` — covers any model `AutoPipelineForText2Image` handles (sd35, sana, lumina2, qwen-image, ideogram-4). Handles nf4/fp8 quantization + cpu offload. **Don't add a dedicated adapter for a new model until `generic.py` is actually tried and fails** — the repo intentionally avoids pre-splitting adapters.
- `pixart.py`, `sdxl.py`, `flux2.py`, `zimage.py` — dedicated adapters for models that needed one.
- Models with `supports_negative: false` (e.g. flux2-klein, no CFG) silently ignore the negative prompt; `generate.py` prints a `[warn]` if an experiment sets one anyway.

## Output structure: `image-prompts/`

`src/generate.py` auto-allocates a globally incrementing version (`v001`, `v002`, ...) and creates `image-prompts/v00N_<model-name>/`:

- `v00N_<model-name>.md` — an Obsidian-style note with YAML frontmatter that is the **single source of truth** for that run: full model/experiment/keyword params, plus `vram_peak_gb` and `sec_per_image` (auto-recorded after generation — this is currently half the point of each experiment, since the driving question is "what fits in 16GB"). The note is written *before* generation starts so a crash/OOM mid-run still leaves a record (`status: running` until it completes).
- `images/` — the generated PNGs (gitignored; regenerate from the note's params instead of committing images). Each PNG also embeds prompt/seed/model metadata via `PngInfo`.

`rating`, `tags`, `issues`, `best` fields in the frontmatter are filled in later via `review_app.py`, not by `generate.py`.

## Review app (`src/review_app.py`)

Streamlit app with two modes: **Browse/Rate** (single version, rate/tag/annotate, saved back into the note's frontmatter) and **Compare** (same keyword shown side-by-side across chosen versions/models, plus a resource table of vram/sec-per-image/rating). Reads/writes directly against the `image-prompts/*/*.md` frontmatter — there is no separate database.

## Shell scripts: Discord notifications

Any shell script that performs **model inference, training, benchmarking, evaluation, or long-running batch experiments** must integrate the Discord notification helper at `scripts/alert.py`.

Notification policy:

- **Always** use `scripts/alert.py`; do not implement separate Discord webhook logic.
- Send a notification **once per model × task (or model × experiment) completion**, whether it succeeds or fails. This is the preferred granularity—avoid spamming notifications for every image, batch, or intermediate step.
- Send a final summary notification when the entire script finishes.
- Failure notifications should include a short excerpt from the log when possible.
- Success notifications should include useful metrics when available (e.g. VRAM usage, seconds per image, training loss, elapsed time, etc.).
- Long-running scripts should continue running after an individual model/task failure whenever practical, while still notifying the failure.

Preferred usage pattern:

```bash
python "$(dirname "$0")/alert.py" \
  --task "$TASK" \
  --status ok|fail \
  --message "MODEL/TASK ..."

# Final summary
python "$(dirname "$0")/alert.py" \
  --task "$TASK" \
  --status ok|fail \
  --log "$SUMMARY"
```

The notification frequency used in `pilot_dialect.sh` (one notification per completed model × task combination, plus one final summary) is considered the project standard and should be followed unless there is a strong reason to do otherwise.

## Conda envs (`envs/`)

One env per model or model family, matching the `env:` field in `configs/models/*.yaml`. `requirements-common.txt` holds only cross-model deps (pyyaml, frontmatter, pillow, streamlit, accelerate, safetensors, sentencepiece, protobuf) — `diffusers`/`torch` are installed per-env since versions conflict across models. **After getting a model working, freeze the env** (`pip freeze > envs/<name>.txt`) — these snapshots are tracked in git specifically to preserve known-good combinations, since diffusers version pinning is the main source of breakage here.

First PixArt run downloads ~12GB (T5-XXL text encoder) — point `HF_HOME` at a large partition before running.

## GPU server & keeping everything in sync

`root@172.10.5.157` (기존 이미지 생성 전용 서버, RTX 3090)는 2026-07-31 반납되었다. 반납 전
산출물(`image-prompts/*/images/` — gitignored라 git으로는 안 넘어가는 부분 포함),
`logs/`의 gitignored 런 로그, conda env(`t2i`, `t2i-ideogram`, `t2i-qwen`)의 `pip freeze`
스냅샷(`envs/*.txt`)을 모두 `ubuntu@172.10.5.23`으로 백업/병합 완료. HF 캐시(모델 가중치, 58GB)는
재다운로드 가능하므로 백업하지 않고 폐기했다.

이제 **`ubuntu@172.10.5.23` (repo at `/home/ubuntu/t2i`, RTX 3090) 하나가 생성(T2I 추론) +
채점(scoring) + 프롬프트 리라이팅(rewrite)을 전부 담당**한다. 기존 채점/리라이팅 env
(`t2i-score`, `t2i-judge2`, `t2i-judge`, `t2i-rewrite`)에 더해, 생성용 env(`t2i`, `t2i-ideogram`,
`t2i-qwen` 등, 필요시 `envs/*.txt`에서 재현)도 여기서 운용한다.

디스크가 97GB로 여러 역할을 겸하니 여유 공간에 특히 주의할 것 — **큰 모델을 새로 받거나 새 env를
만들기 전에는 반드시 `df -h /`로 먼저 확인**. 안 쓰는 env는 지우기 전에
`pip freeze > envs/<name>.txt`로 먼저 백업하고 커밋한 뒤 지울 것 (재현 가능하게).

`ssh -i /Users/sjh354/.ssh/id_ed25519 ubuntu@172.10.5.23`. Note the repo directory is named `t2i` on the server, not `t2i-lab`.

This repo lives in two places (local + the server) and must never drift. Follow these sync rules:

**After local code changes** (editing configs, adapters, scripts — anything not a model run):
1. Commit and push from local.
2. SSH into the server and `git pull` so it picks up the change before any run uses it.

**After a server-side run** (a model generation, sweep, or any long-running experiment executed via SSH on the server):
1. On the server: commit the results (e.g. updated `image-prompts/*.md` notes, `bench/results.md`, frozen env files) and push.
2. Pull the update back to local, so both checkouts stay current.

The goal: local and the server should always be pullable to the same latest commit before starting new work. Don't leave the server ahead of origin (uncommitted/unpushed run results) or behind origin (stale config) when handing off between machines.

## Bench notes (`bench/results.md`)

Holds conclusions and troubleshooting notes only — vram/latency numbers are auto-recorded in note frontmatter and shown in the Streamlit Compare tab, so don't hand-copy numbers into this file.

## Generated reports (`reports/`)

All generated report files (md/html) live under top-level `reports/`, not `bench/`. `bench/` stays reserved for hand-written conclusion/troubleshooting notes. When adding a new report generator, write its output to `reports/`.

## Archived one-off scripts (`scripts/archive/`, `logs/archive/`)

Completed one-off sweep scripts (`sweep.sh` ~ `sweep9_2.sh` and `renumber_versions_sweep8_2.sh`) and their corresponding run logs live under `scripts/archive/` and `logs/archive/` — kept for historical reference, not meant to be rerun or extended. `scripts/sweeps/` holds scripts still in active use (keyword/grid builders, pilot sweeps).

## Keep README.md current

`README.md` is the living research plan (pipeline stages, model/prompt/metric status, the ordered checklist). Whenever you do research or work that changes the plan — a decision made, a checklist item resolved, a new finding about prompting/models/metrics, a change in what to try next — update the relevant section of `README.md` in the same session, not just this CLAUDE.md or bench notes.
