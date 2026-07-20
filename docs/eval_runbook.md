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
    --out "bench/scores/${run}_pass1.csv" --components vqascore,cv
done
```

소요: 이미지당 VQAScore 추론 ~수초 (3090 기준) × 480장 → 전체 30분 내외 예상(미측정).
GPU: `t2i-score` env, 단독 사용 권장(생성 프로세스와 동시 로드 안 함).

## 2. 정식 ref_set 수집 후 validate_ref_set 재실행

`bench/style-presets-v2.md`의 "5. CSD ref_set 수집 기준"에 따라 프리셋별
`refs/<preset>/`에 15~25장 수집(gitignored — 원본은 여기 두고 수동 관리).

```bash
for preset in edu-flat-v2 observational playful-soft storybook-scene; do
  PYTHONPATH=vendor python -m scripts.validate_ref_set --preset "$preset" --dir "refs/$preset"
done
```

(`PYTHONPATH=vendor` 필요 — CSD 공개 구현이 `vendor/CSD`로 vendoring돼 있음. 체크포인트는
`weights/scoring/csd_vit-l.pth`에 미리 받아둘 것, README.md "채점 모듈" 절 참고.)

`configs/ref_sets/<preset>.yaml`이 `status: validated`면 3번으로, `needs-review`면
`reports/ref_set_validation.md`의 outlier 목록을 보고 이미지 재수집 후 재실행.

**이 단계가 늦어지면 3번만 미루고 1·4·5는 먼저 진행 가능** — csd 없이도 merge는 동작한다.

## 3. csd 패스 — validated/provisional manifest가 있는 run만

```bash
for preset in edu-flat-v2 observational playful-soft storybook-scene; do
  for vdir in image-prompts/v2*_${preset##*-}*; do  # 실제로는 run과 preset 매핑을 note에서 확인할 것
    run=$(basename "$vdir")
    PYTHONPATH=vendor python -m src.scoring --dir "$vdir/images" \
      --out "bench/scores/${run}_csd.csv" --components csd \
      --ref-manifest "configs/ref_sets/${preset}.yaml"
  done
done
```

## 4. judge (VLM-as-judge, 로컬 Qwen2.5-VL-7B-Instruct)

```bash
conda activate t2i-judge
python -m scripts.judge --runs image-prompts/v2*_lumina2 image-prompts/v2*_pixart-sigma \
  image-prompts/v2*_flux2-klein-4b-nf4
```

이미 결과가 있는 run은 스킵된다(`--force`로 재실행). 소요: item당 VLM 1~2회 호출
(재시도 포함), 3090 기준 실측치는 `scripts/judge.py` 스모크 결과 참고.

## 5. 최종 병합

```bash
python -m scripts.merge_results \
  --pass1 bench/scores/*_pass1.csv \
  --csd bench/scores/*_csd.csv \
  --judge bench/scores/judge_*.csv \
  --out bench/scores/merged.csv
```

`bench/scores/merged.csv` + `bench/scores/merged.md`(모델별 컴포넌트 평균, 모델×축
pass율 표)가 최종 산출물. csd 결측이면 `missing_components` 컬럼에 표시되고 harmonic은
나머지 값들로만 계산된다 — 3번을 건너뛰고 먼저 실행해도 문제없다.
