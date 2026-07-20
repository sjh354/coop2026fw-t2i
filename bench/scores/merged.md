# 채점 결과 병합 리포트

## 모델별 컴포넌트 평균

| model | vqascore | custom_cv | csd | judge_pass_rate | harmonic |
|---|---|---|---|---|---|
| flux2-klein-4b-nf4 | 0.8368 | 0.7561 | 0.4797 | 0.925 | 0.653 |
| lumina2 | 0.8396 | 0.7393 | 0.4425 | 0.9437 | 0.6303 |
| pixart-sigma | 0.8045 | 0.7396 | 0.4286 | 0.8104 | 0.5804 |

## 모델×축 pass율 (judge)

| model | counting | spatial | attribute |
|---|---|---|---|
| flux2-klein-4b-nf4 | 26/32 (81%) | 50/52 (96%) | 40/40 (100%) |
| lumina2 | 30/32 (94%) | 49/52 (94%) | 40/40 (100%) |
| pixart-sigma | 21/32 (66%) | 43/52 (83%) | 39/40 (98%) |
