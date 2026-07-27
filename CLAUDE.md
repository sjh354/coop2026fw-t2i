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

## GPU servers & keeping everything in sync

Two remote GPU servers are available for running experiments (each a single RTX 3090, 24GB VRAM),
**each with a fixed, separate role** (2026-07-19 split, after both disks filled up from mixing
generation + scoring model caches on the same 97GB disk):

- `root@172.10.5.157` — repo at `/root/t2i` — **이미지 생성(T2I 추론) 전용.**
  env는 `t2i` 하나만 유지 — 지금 확정된 3개 후보(lumina2, pixart-sigma, flux2-klein-4b-nf4)가
  전부 이 env를 씀. `t2i-score`/`t2i-judge`/`t2i-qwen`/`t2i-ideogram` 같은 채점·비후보 모델 env는
  여기 만들지 않는다 — 디스크(97GB)가 금방 찬다.
- `ubuntu@172.10.5.23` — repo at `/home/ubuntu/t2i` — **채점(scoring) + 프롬프트 리라이팅(rewrite) 전용.**
  env는 `t2i-score`(VQAScore/CSD/custom_cv, `src/scoring.py`), `t2i-judge`(로컬 Qwen2.5-VL-7B-Instruct
  VLM-judge, `scripts/judge.py`), `t2i-rewrite`(로컬 LLM 기반 프롬프트 리라이터 backend,
  `scripts/rewrite.py` — 2026-07-27 TASK-E 추가) 이렇게 유지. T2I 생성 모델 env(`t2i` 등)나
  그 가중치 캐시를 여기 두지 않는다.
  **디스크 여유가 30GB 이상 필요한 큰 모델(예: PromptEnhancer-7B, 대체 judge 모델)을 새로
  받기 전에는 반드시 `df -h /`로 먼저 확인** — 채점/리라이팅 env가 여러 개 쌓이면 97GB가
  금방 찬다. 안 쓰는 env는 지우기 전에 `pip freeze > envs/<name>.txt`로 먼저 백업하고
  커밋한 뒤 지울 것 (재현 가능하게).

**두 서버 다 새 역할과 맞지 않는 env/모델 캐시를 발견하면 바로 지운다** (예: 157에 `t2i-score` env가
생겼거나, 23에 T2I 생성 모델 가중치가 캐시돼 있으면) — 역할이 섞이기 시작하면 다시 디스크가 찬다.
`df -h /`로 여유 공간을 수시로 확인할 것.

본 실험 워크플로우상 생성은 157에서, 채점은 23에서 도니 **생성된 PNG를 23으로 옮기는 단계가
필요하다** (`image-prompts/*/images/`는 gitignored라 git으로는 안 넘어감) — `scp`/`rsync`로 직접
옮기거나, 로컬을 경유지로 쓸 것. `docs/eval_runbook.md`가 채점 실행 순서를 다룬다.

Both accept `ssh -i /Users/sjh354/.ssh/id_ed25519 <user>@<host>`. Note the repo directory is named `t2i` on both servers, not `t2i-lab`.

This repo lives in three places (local + two servers) and must never drift. Follow these sync rules:

**After local code changes** (editing configs, adapters, scripts — anything not a model run):
1. Commit and push from local.
2. SSH into both servers and `git pull` so they pick up the change before any run uses it.

**After a server-side run** (a model generation, sweep, or any long-running experiment executed via SSH on one of the two servers):
1. On that server: commit the results (e.g. updated `image-prompts/*.md` notes, `bench/results.md`, frozen env files) and push.
2. Pull the update back to local, and `git pull` it on the *other* server too, so all three checkouts stay current.

The goal: local and both servers should always be pullable to the same latest commit before starting new work. Don't leave a server ahead of origin (uncommitted/unpushed run results) or behind origin (stale config) when handing off between machines.

## Bench notes (`bench/results.md`)

Holds conclusions and troubleshooting notes only — vram/latency numbers are auto-recorded in note frontmatter and shown in the Streamlit Compare tab, so don't hand-copy numbers into this file.

## Generated reports (`reports/`)

All generated report files (md/html) live under top-level `reports/`, not `bench/`. `bench/` stays reserved for hand-written conclusion/troubleshooting notes. When adding a new report generator, write its output to `reports/`.

## Archived one-off scripts (`scripts/archive/`, `logs/archive/`)

Completed one-off sweep scripts (`sweep.sh` ~ `sweep9_2.sh` and `renumber_versions_sweep8_2.sh`) and their corresponding run logs live under `scripts/archive/` and `logs/archive/` — kept for historical reference, not meant to be rerun or extended. `scripts/sweeps/` holds scripts still in active use (keyword/grid builders, pilot sweeps).

## Keep README.md current

`README.md` is the living research plan (pipeline stages, model/prompt/metric status, the ordered checklist). Whenever you do research or work that changes the plan — a decision made, a checklist item resolved, a new finding about prompting/models/metrics, a change in what to try next — update the relevant section of `README.md` in the same session, not just this CLAUDE.md or bench notes.
