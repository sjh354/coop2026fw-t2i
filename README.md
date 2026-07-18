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
쓰는 1차 구현. `python -m src.scoring --dir <PNG 디렉토리> --out <csv 경로>`로 배치 채점 →
`<csv 경로>` + 같은 이름의 `.md` 요약 생성. `--refs`로 스타일 레퍼런스 이미지 경로들을,
`--vlm`으로 VLM-as-judge 열을 추가할 수 있다.

- **env**: `t2i-score` (T2I 생성 env와 분리, 동시 로드 안 함 — `envs/README.md` 참고).
- **VQAScore**: `t2v_metrics` 패키지, `clip-flant5-xl`. 가중치는 `HF_HOME`(기본 `~/.cache/huggingface`)에
  자동 다운로드됨. VRAM: **3090에서 측정 필요, 아직 미측정**.
- **CSD**: 공개 구현([github.com/learn2phoenix/CSD](https://github.com/learn2phoenix/CSD))의
  ViT-L 체크포인트를 `weights/scoring/csd_vit-l.pth`에 받아둘 것(`weights/`는 `.gitignore`의
  `*.pth` 규칙으로 자동 제외됨). `ref_set`이 비어있으면(golden set 미확보) `csd`는 `None`.
  VRAM: **3090에서 측정 필요, 아직 미측정**.
- **custom_cv**: OpenCV만 사용, 모델 불필요. line flatness(색 영역 내부 LAB 채널별 분산,
  픽셀 수 가중 평균) + edge uniformity(Canny 엣지 dilate 후 거리변환 폭의 변동계수)를 각각
  0~1로 정규화해 평균. 저장소의 실제 파일럿 PNG 6장(v205/v207/v211/v214, `pilot-complex3-report.md`
  축별 판정표 기준)으로 로컬 검증함 — 값이 0.77~0.82 범위에서 이미지별로 갈리는 것 확인.
- **VLM-as-judge**: `score_image_vlm`, provider는 `provider_fn` 인자로 교체 가능(기본
  Anthropic vision, `rewriter/providers.py`의 텍스트 전용 함수와 별도). 프롬프트에 수량/공간/속성
  3축을 명시적으로 판단하도록 지시.
- **스모크 테스트**: `scripts/smoke_test_scoring.py` — 정합 성공 3장(lumina2, `pilot-complex3-report.md`
  판정상 3축 모두 성공) vs 실패 3장(sd35-medium 공간 반전 / zimage-turbo 수량 오류 / pixart-sigma
  속성 색 전이)에서 `vqascore(성공군) > vqascore(실패군)`을 assert. **3090의 `t2i-score` env에서
  실행해야 함 — GPU 없는 개발 샌드박스에서는 미실행.**

## 앞으로 확인해야 할 것 (순서대로)

- [x] **삽화 유형 + 벤치마크 프롬프트셋 정의**: 6개 카테고리(사물단독/역사문학/자연과학/생활사회/감정관계/개념은유) × 난이도(easy16/medium16/hard8) × 축(counting/spatial/attribute)으로 40개 벤치마크 프롬프트셋(v1) 확정 → `configs/benchmarks/bench_v1.yaml`. 이후 모든 비교는 이 셋 기준으로 고정.
- [x] **스타일 프리셋 확정**: 12개 → 4개(`edu-flat-v2`/`playful-soft`/`storybook-scene`/`observational`) + 보류 1개(`mono-minimal`)로 통합. 설계 근거·시각 언어·leakage 방지 authoring rules(R1~R9): `bench/style-presets-v2.md`. 신규 4개 프리셋은 `configs/experiments/*.yaml`에 `status: pending-validation`으로 반영, R9 스모크 테스트 통과 후 validated 전환 예정. 구 12개 프리셋 yaml은 `configs/experiments/archive/presets-v1/`로 보존(과거 실험 노트가 참조).
- [x] **rewriter 1차 구현 + 검증 하네스**: `src/rewriter`(`rewrite(prompt_ko, opts) -> {prompt_en, meta}`, provider는 `opts.llm_fn`으로 교체 가능, lang="es"는 인터페이스만 두고 `NotImplementedError`), `scripts/verify_rewriter.py`(과목별 한국어 샘플 20개 → 수량/스타일오염/길이 자동 체크 → `bench/rewriter-verification-report.md`). 자동 체크 실패 시 위반 사유를 피드백으로 넣어 최대 1회 재생성(`meta["retried"]`에 기록). 기본 provider/모델은 OpenAI `gpt-5`(`src/rewriter/providers.py::call_openai`, `.env`의 `OPENAI_API_KEY` 사용). `tests/`에 유닛 테스트 21개 통과. **실행 완료(2026-07-19 재검증)**: `python -m scripts.verify_rewriter` 결과 20/20 실제 통과 — 빈 출력을 PASS로 잘못 기록하던 버그(#18) 수정 후 리포트 재생성 확인. 스페인어는 다음 단계.
- [x] **채점 모듈 1차 구현**: `src/scoring.py`(`score_image(image, prompt, ref_set) → {vqascore, csd, custom_cv, harmonic}`, `score_image_vlm(image, prompt) → {faithfulness, style, overall}`). 상세는 아래 "채점 모듈" 절. `custom_cv`(OpenCV, 모델 불필요)와 배치 CSV/마크다운 생성은 저장소의 실제 파일럿 PNG로 로컬 검증 완료. **VQAScore 스모크테스트 완료(2026-07-19, 3090 서버)**: `python scripts/smoke_test_scoring.py` PASS — success_mean=0.9133 > failure_mean=0.6767, vram_peak=6.06GB(clip-flant5-xl 로드 기준, T2I 생성 모델과 동시 로드 안 함). `t2i-score` env 구성 시 `t2v-metrics==3.0` 자체 패키징 문제(무관한 VLM 백엔드를 import 시점에 전부 끌어옴) 우회가 필요했음 — `envs/README.md`의 "t2v-metrics 3.0 패키징 문제" 절과 `envs/fix_t2v_metrics.sh` 참고. CSD는 여전히 미검증(체크포인트 미다운로드, ref_set 없이는 스킵됨).
- [ ] **golden set 시드 확보**: 스타일 합격작 20장 이상 모으기 시작(초기엔 unDraw/Storyset 등 라이선스 깨끗한 소스로 부트스트랩 가능, 평가 전용).
- [ ] **기존 모델 후보군 실측 비교**: 벤치마크 프롬프트셋 + 확정된 스타일 프리셋 + 채점 모듈로 지금까지 써본 모델들을 동일 조건에서 채점 → 1차 순위표.
- [ ] **3단계 병행 개선 루프 진입**: 채점 결과가 가리키는 병목에 따라 프롬프트/모델/채점 중 우선순위를 정해 반복 개선. (파인튜닝·증류는 이 루프에서 결과가 계속 부족할 때만 후순위로 검토.)

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

## 축이 3개다

    모델(configs/models) × 스타일(configs/experiments) × 키워드셋(configs/keywords)

버전 번호(v001...)는 전역 증가하고, 디렉토리명에 모델명이 붙는다.
어떤 조합이었는지는 노트 frontmatter의 model/experiment/keyword_set에 남는다.
