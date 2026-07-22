# t2i-lab

교육용(K-12 수업 프레젠테이션 삽화) T2I 모델 후보들을 같은 조건에서 비교하기 위한 실험 환경.
연구개발 단계 — 결과만 좋으면 되므로 라이선스/양자화/파인튜닝은 지금 당장은 신경 쓰지 않는다.

## 연구 방향

**핵심 구조: 프롬프트 구축 → T2I 이미지 생성 → 메트릭 채점, 3단계 파이프라인을 계속 돌리면서 프롬프트 작성기 / T2I 모델 / 채점 방식 세 가지를 동시에 발전시킨다.**

- 파인튜닝(LoRA)이나 DMD 계열 one-step 증류는 지금 하지 않는다. teacher 모델 그대로 e2e 파이프라인이 잘 돌고 결과가 충분히 좋으면 그걸로 충분하고, 나중에 필요해지면(서빙 속도/일관성 문제 등) 그때 시작한다.
- 이미지 안에 텍스트를 넣을지 말지는 더 이상 정책적으로 막지 않는다. 텍스트 렌더링이 잘 되는 모델이면 오히려 좋은 것이고, 안 되면 그냥 텍스트 없는 삽화로 취급한다. 별도 트랙으로 다루지 않는다.
- 세 요소(프롬프트/모델/채점) 중 무엇을 먼저 개선할지는 감이 아니라 **채점 결과가 가리키는 병목**으로 판단한다(예: 프롬프트 충실도는 낮은데 스타일은 괜찮다 → 프롬프트/모델 쪽 문제, 채점 자체가 사람 판단과 안 맞는다 → 채점 방식 문제).

## 파이프라인

```
① 프롬프트 구축          ② T2I 이미지 생성           ③ 메트릭 채점
(rewriter + style preset) → (configs/models 후보군)  → (충실도 + 스타일 + 종합)
        ↑____________________________________________________|
                    채점 결과가 다음 라운드 개선 방향을 정함
```

### ① 프롬프트 구축

목적: 오브젝트 설명(한국어 가능) + 개발자가 미리 정한 스타일 프리셋을 합쳐 모델에 넣을 최종 프롬프트를 만든다.

- **구조 원칙**: rewriter(콘텐츠만 담당) + style preset(상수, 코드에서 뒤에 붙임)을 분리한다. rewriter가 스타일 어휘까지 건드리면 매 호출마다 스타일이 미세하게 흔들려 일관성이 깨진다.
- **스타일 프리셋**: 길이 3버전(S/M/L, 모델별 토큰 예산에 맞춤) × 목적별 프리셋(플랫 컬러 벡터, 흑백 라인아트 등 필요한 만큼). 우선순위: 스타일 앵커 → 플랫/음영 제약 → 배경 → 구도 → 금지 요소. 뒤가 잘려도 앞이 살아남게 배열.
- **한국어 입력 → 영어 확장 rewriter**: 부정문("~가 아닌")은 반드시 긍정 서술로 치환(diffusion 모델은 "no X"를 넣으면 오히려 X를 그리는 경향), counting/entity layout처럼 T2I가 약한 부분은 few-shot으로 명시 유도.
- **참고 자료**: PromptEnhancer(CVPR 2026, 24개 실패 모드 taxonomy — attribute binding/negation/counting/compositional relation 등), FLUX/Qwen-Image 공식 가이드(구조화 서술, 어순=가중치, 가중치 문법 지양). 자세한 조사 내용은 git 히스토리의 `claude-prompt.md` 참고(README 통합 후 삭제됨).
- **검증 루프**: (한국어 입력, rewriter 출력, 최종 프롬프트, 채점 결과)를 계속 기록해두면 이후 rewriter 자체를 파인튜닝하고 싶을 때 데이터로 그대로 쓸 수 있다.

### ② T2I 모델

지금까지 실측해본 모델 후보군(`configs/models/`) 중에서 프롬프트/채점 결과가 가장 좋은 조합을 고른다.
새 모델을 굳이 더 찾아다니지 않고, 이미 돌려본 것들의 실측 비교부터 채운다.

- 후보: PixArt-Sigma, SDXL, Flux2-Klein, Z-Image, SD3.5, Sana, Lumina2, Qwen-Image, Ideogram-4
- 모델마다 프롬프트 "방언"이 다르다는 점만 유의: CLIP 기반(SDXL)은 키워드 나열 + negative prompt, T5/LLM 기반(PixArt/Sana/Qwen/Z-Image)은 서술형 자연어, guidance-distilled(Flux2-Klein 등)는 negative prompt 자체가 안 먹히므로 금지 요소를 positive 문장 안에 "no ..."로 유지.
- 모델별 VRAM/latency는 각 run의 note frontmatter(`vram_peak_gb`, `sec_per_image`)에 자동 기록되므로 bench 문서에 손으로 옮기지 않는다.
- **방언(dialect) 효과 파일럿 결론** (`bench/results.md` 상세): 단순 프롬프트("an apple" 수준)에서는 모델별 방언 재표현이 출력을 거의 바꾸지 않는다 — 어려운 출력은 대부분 프롬프트 문제가 아니라 모델 능력 한계. 수량/공간/속성 결합 같은 복합 프롬프트에서도 방언으로 실제 개선된 사례는 flux2-klein-4b의 수량 정확도 하나뿐이었고, 나머지 실패(sd35-medium의 좌우 반전 고정, zimage-turbo의 개수 오류, pixart-sigma의 속성 색 전이)는 조건과 무관하게 동일하게 재현돼 능력 한계로 판단. **lumina2가 복합 프롬프트 전 축(수량/공간/속성)에서 가장 안정적** — ②에서 후보 압축 시 우선 고려.
- **스타일 프리셋 작성 규칙**: LLM/T5 인코더 모델은 스타일 프롬프트 속 구체 명사(그릴 수 있는 사물, 예: "textbook")를 오브젝트로 그대로 렌더링할 수 있다("textbook infographic style" → 책이 그림에 등장). 배경/매체로 의도한 게 아니면 스타일 프롬프트에 구체 명사를 넣지 않는다. 상세 감사 결과는 `bench/results.md` 참고.
- **flux2-klein-4b 16GB 진입 결론**: 기본 조건(양자화·offload 없음)은 실측 peak이 16GB를 넘어 탈락 대상이었으나, **transformer NF4 양자화 + `enable_model_cpu_offload()`**(`configs/models/flux2-klein-4b-nf4.yaml`) 조합으로 16GB 진입에 성공(전체 offload만 쓰는 것보다 VRAM/속도 둘 다 더 나음). 품질 저하는 경미(음영 그라디언트 다소 밋밋, 윤곽선 살짝 거칠어짐 — 구조적 결함 없음). "text encoder만 offload" 방식은 이 파이프라인 구조에서 실질적 절감 효과가 없어 폐기. **결과적으로 lumina2+pixart-sigma 2모델 체제로의 축소는 발동하지 않음** — flux2-klein-4b는 NF4 양자화 조건으로 후보 유지. 상세는 `bench/results.md` 참고.

### ③ 메트릭 채점

두 축만 본다: **프롬프트 충실도**, **스타일 반영도**. (화질/미감/지식 계열 메트릭은 지금 우선순위 아님.)

- **프롬프트 충실도**: VQAScore(이미지-텍스트가 맞는지 VLM에게 물어 "Yes" 확률을 점수화 — 분해 불필요, 세팅 제일 간단)로 시작. 더 세밀한 원인 분석이 필요해지면 Soft-TIFA(Qwen-VL 백본)로 확장.
- **스타일 반영도**: 참조 셋(golden set) 대비 CSD(스타일 전용 학습 지표, DINO보다 content leakage에 덜 휘둘림) + 콜링북/플랫 일러스트 특유 속성(선 두께 균일도, 색 플랫니스)은 결정론적 커스텀 CV 지표로 직접 측정. 참조 셋은 스윕 결과 중 스타일 합격작을 골라 쌓는 자체 golden set을 우선한다(라이선스 이슈 없고 타깃이 정확함).
- **VLM-as-judge**: CV/CSD로 못 잡는 미묘한 기준(예: "아이 친화적 단순함")이 필요할 때 rubric 기반으로 보조 채점. 아직 최적 방식이 정해지지 않았으므로 여러 방식(zero-shot closed VLM, 전용 evaluator, rubric 기반)을 실제로 시도해보고 사람 판단과 가장 잘 맞는 걸 고른다.
- **종합 랭킹**: 두 축을 합치지 않고 개발 중엔 2D 산점도로 트레이드오프를 보되(스타일은 좋은데 프롬프트 무시 vs 프롬프트는 맞는데 밋밋함), 버전 랭킹용 단일 숫자가 필요하면 조화평균 사용.
- 자세한 조사 내용은 git 히스토리의 `claude-metric.md` 참고(README 통합 후 삭제됨).

### 채점 모듈 (`src/scoring.py`)

`src/score.py`(CLIP 프록시, `review_app.py`가 아직 씀)와 별도로, 실제 VQAScore/CSD 모델을
쓰는 1차 구현. `python -m src.scoring --dir <PNG 디렉토리> --out <csv 경로> --components <조합>`으로
배치 채점 → `<csv 경로>` + 같은 이름의 `.md` 요약 생성. `--components`는 `vqascore,cv,csd` 중
조합(csd는 `--ref-manifest`로 `configs/ref_sets/<preset>.yaml` 필요) — vqascore/cv 패스와 csd
패스를 분리해서, csd는 정식 ref_set 수집 전엔 건너뛰고 나중에 그 패스만 재실행할 수 있다.

- **env**: `t2i-score` (T2I 생성 env와 분리, 동시 로드 안 함 — `envs/README.md` 참고).
- **VQAScore**: `t2v_metrics` 패키지, `clip-flant5-xl`. 가중치는 `HF_HOME`(기본 `~/.cache/huggingface`)에
  자동 다운로드됨. VRAM: **3090에서 측정 필요, 아직 미측정**.
- **CSD**: 공개 구현([github.com/learn2phoenix/CSD](https://github.com/learn2phoenix/CSD), MIT)의
  `CSD/` 서브패키지를 `vendor/CSD`로 vendoring함(pip 패키지 없음) — 실행 시 `PYTHONPATH=vendor`
  필요. 체크포인트(ViT-L)는 저자 공식 HF 미러 [tomg-group-umd/CSD-ViT-L](https://huggingface.co/tomg-group-umd/CSD-ViT-L)에서
  받아 `weights/scoring/csd_vit-l.pth`에 둘 것(`weights/`는 `.gitignore`의 `*.pth` 규칙으로
  자동 제외됨). 저자가 리포 상단에 논문 수치와의 미세한 불일치 가능성을 disclaimer로 밝혀뒀지만
  provisional 용도로는 문제없음. **2026-07-20 ubuntu@172.10.5.23 `t2i-score` env에서 실제
  체크포인트 로드+forward 검증 완료** — state dict 키에 `module.` 접두사가 있어
  `CSD.utils.convert_state_dict`로 벗겨야 함(벗기지 않으면 `strict=False`가 조용히 0개 키
  매치로 통과해 랜덤 초기화 상태로 채점하는 버그였음, `src/scoring.py::load_csd_model`에서 수정).
  `validate_ref_set.py --provisional`도 파일럿 이미지 3장으로 실측 검증(mean=0.6175,
  std=0.0481, `configs/ref_sets/_smoke_pilot.yaml`). ref_set 정식 검증/수집은
  `scripts/validate_ref_set.py` + `bench/style-presets-v2.md`의 "5. CSD ref_set 수집 기준"
  참고. VRAM: 실측 ~1.6GB(단일 이미지 forward 기준).
- **custom_cv**: OpenCV만 사용, 모델 불필요. line flatness(색 영역 내부 LAB 채널별 분산,
  픽셀 수 가중 평균) + edge uniformity(Canny 엣지 dilate 후 거리변환 폭의 변동계수)를 각각
  0~1로 정규화해 평균. 저장소의 실제 파일럿 PNG 6장(v205/v207/v211/v214, `pilot-complex3-report.md`
  축별 판정표 기준)으로 로컬 검증함 — 값이 0.77~0.82 범위에서 이미지별로 갈리는 것 확인.
- **VLM-as-judge**: `scoring.py`에서 완전히 분리된 별도 스크립트 `scripts/judge.py` —
  **로컬 Qwen2.5-VL-7B-Instruct**(전용 `t2i-judge` env, 3090에서 직접 추론)로 API 키 없이
  판정한다. 예전에 있던 Anthropic API 기반 `score_image_vlm`은 제거됨. bench_v1의
  counting/spatial/attribute 축별로 pass/fail을 구조화 JSON으로 받는다. 실행 순서는
  `docs/eval_runbook.md` 참고. `t2i-judge` env 구성 시 `qwen-vl-utils`가 import 시점에
  요구하는 `torchvision`이 설치 목록에서 빠져 있었음 — `envs/README.md` 참고해 추가로 설치할 것.
  **스모크 테스트 완료(2026-07-20, 3090 서버)**: `--smoke-map tests/judge_smoke_map.yaml` PASS
  없이 실행 완료, vram_peak=15.78GB. 단, 결과는 **정확도 이슈를 드러냄** — 알려진 실패 파일럿
  3장 중 2장(v207 spatial 좌우반전, v205 attribute 색 전이)에서 judge가 `pass`를 냄(false
  positive). v205는 rationale 자체가 "다리도 파란색"이라고 결함을 인지하고도 verdict는
  pass로 낸 경우 — 판정 로직(프롬프트/파싱)이 아니라 모델의 spatial-reasoning/fine-grained
  attribute 판단 자체가 약한 것으로 보임. counting 축은 성공/실패 양쪽 다 정확히 잡음.
  본 실험 결과 해석 시 judge의 spatial/attribute 축 판정은 액면 그대로 신뢰하지 말고
  이미지 직접 확인으로 교차검증할 것 — 별도 개선 트랙 필요(프롬프트 튜닝 또는 더 큰 모델).
- **최종 병합**: `scripts/merge_results.py` — pass1(vqascore/cv) + csd + judge CSV를
  run×item_id 기준으로 합쳐 harmonic 집계 최종 CSV + 모델별 컴포넌트 평균/모델×축 pass율
  리포트를 만든다. csd가 없어도(정식 ref_set 미수집) 나머지 컴포넌트만으로 동작한다.
- **스모크 테스트**: `scripts/smoke_test_scoring.py` — 정합 성공 3장(lumina2, `pilot-complex3-report.md`
  판정상 3축 모두 성공) vs 실패 3장(sd35-medium 공간 반전 / zimage-turbo 수량 오류 / pixart-sigma
  속성 색 전이)에서 `vqascore(성공군) > vqascore(실패군)`을 assert. **3090의 `t2i-score` env에서
  실행해야 함 — GPU 없는 개발 샌드박스에서는 미실행.**

## 앞으로 확인해야 할 것 (순서대로)

- [x] **삽화 유형 + 벤치마크 프롬프트셋 정의**: 6개 카테고리(사물단독/역사문학/자연과학/생활사회/감정관계/개념은유) × 난이도(easy16/medium16/hard8) × 축(counting/spatial/attribute)으로 40개 벤치마크 프롬프트셋(v1) 확정 → `configs/benchmarks/bench_v1.yaml`. 이후 모든 비교는 이 셋 기준으로 고정.
- [x] **스타일 프리셋 확정**: 12개 → 4개(`edu-flat-v2`/`playful-soft`/`storybook-scene`/`observational`) + 보류 1개(`mono-minimal`)로 통합. 설계 근거·시각 언어·leakage 방지 authoring rules(R1~R9): `bench/style-presets-v2.md`. 구 12개 프리셋 yaml은 `configs/experiments/archive/presets-v1/`로 보존(과거 실험 노트가 참조). **R9 스모크 테스트 완료(2026-07-19)**: lumina2 + r9-smoke3(apple/cat/book)로 4개 전부 생성·육안 확인 — leakage 없음 확인되어 4개 전부 `status: validated`로 전환. `observational`/`storybook-scene`은 교육용치고 스타일이 과하게 고퀄리티/복잡하다는 별도 지적이 있었으나 leakage와 무관한 이슈라 일단 본 실험에 포함하고 채점 결과로 판단하기로 함 — 상세는 `bench/results.md`.
- [x] **rewriter 1차 구현 + 검증 하네스**: `src/rewriter`(`rewrite(prompt_ko, opts) -> {prompt_en, meta}`, provider는 `opts.llm_fn`으로 교체 가능, lang="es"는 인터페이스만 두고 `NotImplementedError`), `scripts/verify_rewriter.py`(과목별 한국어 샘플 20개 → 수량/스타일오염/길이 자동 체크 → `bench/rewriter-verification-report.md`). 자동 체크 실패 시 위반 사유를 피드백으로 넣어 최대 1회 재생성(`meta["retried"]`에 기록). 기본 provider/모델은 OpenAI `gpt-5`(`src/rewriter/providers.py::call_openai`, `.env`의 `OPENAI_API_KEY` 사용). `tests/`에 유닛 테스트 21개 통과. **실행 완료(2026-07-19 재검증)**: `python -m scripts.verify_rewriter` 결과 20/20 실제 통과 — 빈 출력을 PASS로 잘못 기록하던 버그(#18) 수정 후 리포트 재생성 확인. 스페인어는 다음 단계.
- [x] **채점 모듈 1차 구현**: `src/scoring.py`(`score_image(image, prompt, components, ref_set=None) → {vqascore?, custom_cv?, csd?}`). VLM-as-judge는 `scripts/judge.py`로 분리(로컬 Qwen2.5-VL). 상세는 아래 "채점 모듈" 절. `custom_cv`(OpenCV, 모델 불필요)와 배치 CSV/마크다운 생성은 저장소의 실제 파일럿 PNG로 로컬 검증 완료. **VQAScore 스모크테스트 완료(2026-07-19, 3090 서버)**: `python scripts/smoke_test_scoring.py` PASS — success_mean=0.9133 > failure_mean=0.6767, vram_peak=6.06GB(clip-flant5-xl 로드 기준, T2I 생성 모델과 동시 로드 안 함). `t2i-score` env 구성 시 `t2v-metrics==3.0` 자체 패키징 문제(무관한 VLM 백엔드를 import 시점에 전부 끌어옴) 우회가 필요했음 — `envs/README.md`의 "t2v-metrics 3.0 패키징 문제" 절과 `envs/fix_t2v_metrics.sh` 참고. **CSD도 2026-07-20 실측 검증 완료**(체크포인트 로드+forward+`validate_ref_set.py --provisional` 전체 경로, 위 "채점 모듈" 절 참고).
- [x] **golden set 확보**: 최초 수집분은 벤치마크 대상 12개 run(v231~v242) 이미지에서 골라 자체 참조(self-reference) 오염 발견 → 폐기(`refs/_old_self_ref_backup/`에 보존, 스코어링엔 미사용). 프론티어 모델(Imagen-4)로 4개 프리셋 독립 재생성(edu-flat-v2 15장/observational 10장/playful-soft 10장/storybook-scene 10장, bench_v1 40개 키워드와 주제 미중복) 후 전량 교체. `validate_ref_set.py` 4개 프리셋 전부 `status: validated`(2026-07-20). storybook-scene은 세이프티 필터로 아동 피사체가 전혀 생성되지 않아 성인/비인물 장면 위주로 구성됨 — 아동 대상 스타일 정합성은 추후 재검증 필요.
- [x] **기존 모델 후보군 실측 비교**: 벤치마크 프롬프트셋(bench_v1, 40개) × 확정 스타일 프리셋 4개(`edu-flat-v2`/`observational`/`playful-soft`/`storybook-scene`) × 3개 후보 모델(lumina2/pixart-sigma/flux2-klein-4b-nf4) = 12개 run(480장) 생성 후 채점 완료(2026-07-20, `bench/scores/merged.md`). csd 포함 4개 컴포넌트(vqascore/custom_cv/csd/judge_pass_rate) 전부로 harmonic 계산 완료 — flux2-klein-4b-nf4(0.653) > lumina2(0.6303) > pixart-sigma(0.5804).

  | model | vqascore | custom_cv | csd | judge_pass_rate | harmonic |
  |---|---|---|---|---|---|
  | flux2-klein-4b-nf4 | 0.837 | 0.756 | 0.480 | 0.925 | 0.653 |
  | lumina2 | 0.840 | 0.739 | 0.443 | 0.944 | 0.630 |
  | pixart-sigma | 0.805 | 0.740 | 0.429 | 0.810 | 0.580 |

  judge 축별 pass율: pixart-sigma가 counting에서 66%(21/32)로 세 모델 중 유독 낮음(lumina2 94%, flux2-klein 81%) — 방언 파일럿에서 이미 나온 "lumina2가 복합 프롬프트 전 축에서 가장 안정적" 결론과 일치. spatial/attribute는 세 모델 다 80~100%대지만, judge 자체의 spatial/attribute 판정 정확도가 파일럿에서 낮게 나온 바 있어(위 "채점 모듈" 절) 액면 그대로 신뢰하지 않고 이미지 직접 확인이 필요.
- [ ] **3단계 병행 개선 루프 진입**: 채점 결과가 가리키는 병목에 따라 프롬프트/모델/채점 중 우선순위를 정해 반복 개선. (파인튜닝·증류는 이 루프에서 결과가 계속 부족할 때만 후순위로 검토.) 위 1차 비교 결과대로면 pixart-sigma의 counting 약점이 우선 조사 대상 — judge 오탐인지 실제 모델 한계인지 이미지 직접 확인 필요.

## 실행

    conda activate t2i-pixart
    python -m src.generate --model pixart-sigma --exp coloring-book

    streamlit run src/review_app.py

## 구조

    configs/
      models/       모델 1개 = 파일 1개 (repo, adapter, env, dtype, steps, quant)
      experiments/  스타일 1개 = 파일 1개 (style/negative prompt, seed, 참조할 키워드셋)
                    archive/presets-v1/ 폐기된 구 프리셋 — 과거 실험 노트가 참조하므로 보존만
      keywords/     고정 벤치마크 키워드셋 — 모델 비교의 기준이므로 함부로 안 바꾼다
      benchmarks/   3단계 파이프라인 전체용 rubric 프롬프트셋(v1, 40개) — bench_v1.yaml
    src/
      generate.py   모델 × 실험 조합 하나를 생성. 공통 엔트리포인트.
      adapters/     모델별 pipeline 로딩. lazy import (env가 다르므로 필수).
      review_app.py 브라우징/평가/비교
    image-prompts/
      v001_pixart-sigma/
        v001_pixart-sigma.md    frontmatter = single source of truth
        images/
    envs/           conda env 규칙 + 성공한 pip freeze 스냅샷
    bench/          결론과 삽질 메모
    reports/        생성된 리포트(md/html) — bench/reports/였던 것도 여기로 통합
    scripts/
      sweeps/       현재 쓰는 스윕/빌드 스크립트
      archive/      끝난 스윕(sweep.sh~9_2.sh) — 과거 기록 보존용, 재실행 대상 아님
    logs/           현재 실행 로그
      archive/      끝난 스윕(sweep*)의 summary.tsv — 과거 기록 보존용

## 축이 3개다

    모델(configs/models) × 스타일(configs/experiments) × 키워드셋(configs/keywords)

버전 번호(v001...)는 전역 증가하고, 디렉토리명에 모델명이 붙는다.
어떤 조합이었는지는 노트 frontmatter의 model/experiment/keyword_set에 남는다.


## 랩미팅 코멘트 백업

> https://docs.google.com/presentation/d/1CKLPUB_i5icXxrAOilvpawpoHU1EJnlE9ZzILbHZjQ8

### 7.1 사전미팅
```text
15분 발표 준비 + Q&A 디스커션 별도 진행
경량화 + 영상 생ㅇ성하는 기존 모델들을 교육 컨텐츠 용으로 쓸만한 영상 (스타일, 품질 동시에 잡기)
기존 모델로 유아용 컨텐츠로 만들어서 한번 보고? 안될거같으면 파인튜닝으로 ㄱㄱ

이거를 경량화 하는게 주요 목적

서베이를 잘 하자

컴프레션?

영상 스타일? 
프롬프트 vs 파인튜닝 

Few shot adaptation 기반으로 해야할 것.
우선 기존에 걍 모델이 어떻게 다른지 비교? 어디까지 되는지?

컴프레션? 디퓨전에서 quantazation / 일반 뉴럴넷이랑 또 다름
여러 방향으로 접근 가능
파라미터 프루닝이나 distill, … 등등

다음주까진 컴프레션 논문살펴보기
```

---

### 7.8 미팅 코멘트

```text
T2I 결과 나오는거 확인하는거 위주로
컴프레션도 적당히 공부해보기

논문을 보는거 보다
교육용 컨텐츠 -> output 가져와야 함

어떻게 비교 평가 할 것인지?
특히 교육용 컨텐츠 T2I라서 

일단 제네릭한 이미지 생성에서도 메트릭 찾아보고
비교를 해야함
어떻게 평가할 지 고민

아키텍쳐는 가볍게, 논문이나 프로젝트 페이지 생성 결과를 가져와서 비교

PixArt랑 FLUX만 보면 되는지? 
일단 다른거도 비교 추가

7/22 : Task 1: 수업용 프롬프트 20~30개 제작 + 2~3개 모델 결과 분석 + Prompt Rewriting 논문 1~2개
```

---

### 7.22 미팅 코멘트

```text
Ideogram이 텍스트 잘 만듬
- json형식으로 되게 explicit하게 넘겨주던데 이런 방법론

텍스트 어떻게 잘 넣음?
그래프 그리기는 또 다른데 어떻게 함?

일단 계획대로 ㄱㄱ

```
