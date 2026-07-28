# 채점 파이프라인 실행 순서 (본 실험 생성 완료 후)

`bash scripts/run_main_experiment.sh`(`SKIP_SCORE=1`로 생성만 먼저 돌린 경우 포함)로
`image-prompts/vNNN_<model>/` 런들이 다 생기고 나면, 아래 순서대로 실행한다. 모든
스크립트는 run 디렉토리 경로를 인자로 받는 단순 배치 실행이라 어느 GPU에서 돌려도 된다
(`CUDA_VISIBLE_DEVICES=0` 등으로 지정).

## 0. 사전 조건

- `configs/keywords/bench_v1.yaml` 존재 (`python -m scripts.build_bench_v1_keywords`로 생성)
- 각 run의 note(`vNNN_<model>/vNNN_<model>.md`)에 `keyword_set: bench_v1`이 기록돼 있을 것
  (`--exp <preset>-benchv1`로 생성된 run만 해당 — `scripts/run_main_experiment.sh`가 이렇게 만든다)
- **서버 역할 분리(2026-07-19)**: 생성은 `root@172.10.5.157`(env `t2i`만), 채점은
  `ubuntu@172.10.5.23`(env `t2i-score`/`t2i-judge`만) — CLAUDE.md 참고. 두 서버가 물리적으로
  분리돼 있고 `image-prompts/*/images/`는 gitignored라, **아래 1~4번을 돌리기 전에 157에서
  생성된 run 디렉토리(`vNNN_<model>/` 전체, note+images)를 23으로 옮겨야 한다**:
  `scp -r root@172.10.5.157:~/t2i/image-prompts/vNNN_<model> ~/t2i/image-prompts/` (또는 로컬 경유).

## 1. 채점 패스1 (vqascore + custom_cv) — run별

```bash
conda activate t2i-score
for vdir in image-prompts/v2*_lumina2 image-prompts/v2*_pixart-sigma image-prompts/v2*_flux2-klein-4b-nf4; do
  run=$(basename "$vdir")
  python -m src.scoring --dir "$vdir/images" \
    --out "bench/scores/${run}/pass1.csv" --components vqascore,cv
done
```

소요: 이미지당 VQAScore 추론 ~수초 (3090 기준) × 480장 → 전체 30분 내외 예상(미측정).
GPU: `t2i-score` env, 단독 사용 권장(생성 프로세스와 동시 로드 안 함).

## 2. 정식 ref_set 수집 후 validate_ref_set 재실행

`bench/style-presets-v2.md`의 "5. CSD ref_set 수집 기준"에 따라 프리셋별
`refs/golden-set/<preset>/`에 15~25장 수집(gitignored — 원본은 여기 두고 수동 관리).

```bash
for preset in edu-flat-v2 observational playful-soft storybook-scene; do
  PYTHONPATH=vendor python -m scripts.validate_ref_set --preset "$preset" --dir "refs/golden-set/$preset"
done
```

(`PYTHONPATH=vendor` 필요 — CSD 공개 구현이 `vendor/CSD`로 vendoring돼 있음. 체크포인트는
`weights/scoring/csd_vit-l.pth`에 미리 받아둘 것, README.md "채점 모듈" 절 참고.)

`configs/ref_sets/<preset>.yaml`이 `status: validated`면 3번으로, `needs-review`면
`reports/ref_set_validation.md`의 outlier 목록을 보고 이미지 재수집 후 재실행.

**이 단계가 늦어지면 3번만 미루고 1·4·5는 먼저 진행 가능** — csd 없이도 merge는 동작한다.

## 3. csd 패스 — validated/provisional manifest가 있는 run만

run 디렉토리 이름(`vNNN_<model>`)에는 preset이 안 들어있다 — note frontmatter의
`experiment:` 필드로 매핑해야 한다(디렉토리명 glob으로는 절대 못 찾음, 2026-07-20
확인). 예:

```bash
for preset in edu-flat-v2 observational playful-soft storybook-scene; do
  for note in image-prompts/v2*/v2*.md; do
    grep -q "^experiment: $preset$" "$note" || continue
    vdir=$(dirname "$note")
    run=$(basename "$vdir")
    PYTHONPATH=vendor python -m src.scoring --dir "$vdir/images" \
      --out "bench/scores/${run}/csd.csv" --components csd \
      --ref-manifest "configs/ref_sets/${preset}.yaml"
  done
done
```

## 4. judge (VLM-as-judge, 로컬 InternVL3-8B — 2026-07-28부터 기본, envs/README.md 참고)

```bash
conda activate t2i-judge2
python -m scripts.judge --runs image-prompts/v2*_lumina2 image-prompts/v2*_pixart-sigma \
  image-prompts/v2*_flux2-klein-4b-nf4
```

Qwen2.5-VL로 교차검증하려면 `conda activate t2i-judge`로 바꾸고 `scripts.judge`의
`JUDGE_MODEL_REPO`를 `Qwen/Qwen2.5-VL-7B-Instruct`로 명시해서 돌릴 것(env가 다르면
서로 안 섞인다).

이미 결과가 있는 run은 스킵된다(`--force`로 재실행). 소요: item당 VLM 1~2회 호출
(재시도 포함), 3090 기준 실측치는 `scripts/judge.py` 스모크 결과 참고.

## 5. 최종 병합

```bash
python -m scripts.merge_results \
  --pass1 bench/scores/*/pass1.csv \
  --csd bench/scores/*/csd.csv \
  --judge bench/scores/*/judge.csv \
  --out bench/scores/merged.csv
```

`bench/scores/merged.csv` + `bench/scores/merged.md`(모델별 컴포넌트 평균, 모델×축
pass율 표)가 최종 산출물. csd 결측이면 `missing_components` 컬럼에 표시되고 harmonic은
나머지 값들로만 계산된다 — 3번을 건너뛰고 먼저 실행해도 문제없다.

## 6. lecture24 baseline (`vlm-prompts.json`) — 위와 별도 트랙

위 1~5번은 `bench_v1`(키워드+스타일 조합, 축별 rubric) 파이프라인 기준이다. **Baseline으로
고정된 lecture24**(`configs/benchmarks/vlm-prompts.json`, 상세는 `bench/results.md`의
"Baseline: lecture24" 절)는 완성 프롬프트를 그대로 흘리는 별도 스크립트 세트를 쓴다:

```bash
# 생성 (모델 1개당 24장)
python -m scripts.lecture_generate --model <model>

# 채점 — pass1은 1번과 동일한 src.scoring 사용
conda activate t2i-score
python -m src.scoring --dir image-prompts/vNNN_<model>-lecture24/images \
  --out bench/scores/vNNN_<model>-lecture24/pass1.csv --components vqascore,cv

# csd_target — 정식 ref_set(2번) 대신 카테고리당 참조 이미지 1장(refs/lecture24/vlm-target/)과 비교하는
# provisional 경로. 카테고리별 golden set 보강 후에는 --components csd로 전환 예정.
python -m scripts.score_csd_target --dir image-prompts/vNNN_<model>-lecture24/images \
  --out bench/scores/vNNN_<model>-lecture24/csd_target.csv

# judge — bench_v1의 counting/spatial/attribute 대신 lecture24 전용 4축(content_present/
# text_legibility/layout_structure/educational_fit)
conda activate t2i-judge
python -m scripts.judge_lecture24 --runs image-prompts/vNNN_<model>-lecture24
```

종합 리포트는 `reports/lecture24-v243-v244-v245/index.html`(수동/1회성 생성, `merge_results.py`
같은 고정 생성 스크립트는 아직 없음). 새 모델을 이 baseline에 추가할 때도 같은 4단계를
반복하고 리포트를 새로 만든다.
