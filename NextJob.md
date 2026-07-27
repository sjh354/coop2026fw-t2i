# t2i-lab — 코드작업 / 공부 분리 정리

작성일 기준 baseline: **lecture24 트랙** (`configs/benchmarks/vlm-prompts.json`)

---

## 0. 현재 상태 (baseline 확정)

| 항목 | 내용 |
|---|---|
| 프롬프트셋 | `configs/benchmarks/vlm-prompts.json` — 8 카테고리 × 3 VLM 소스(Claude / ChatGPT / Qwen2.5-VL-7B) = 24 완성 프롬프트, 각 항목에 채점용 metric 힌트 포함 |
| 카테고리 | C1 활동지 템플릿, C2 막대그래프, C3 역사 인물 초상, C4 다인물 교실 협업, C5 세대 간 실내 장면, C6 단일 인물 컷아웃, C7 라벨 과학 도표, C8 기하 도형 세트 |
| 생성 스크립트 | `scripts/lecture_generate.py` / `.sh` (키워드+스타일 조합 없이 완성 프롬프트를 그대로 흘림) |
| 생성 완료 | `v243_pixart-sigma-lecture24`, `v244_flux2-klein-4b-nf4-lecture24`, Qwen-Image(GGUF Q5_K_M) |
| 채점 | ① `pass1.csv` = vqascore + custom_cv ② `scripts/score_csd_target.py` = csd_target(카테고리당 원본 1장 대비) ③ `scripts/judge_lecture24.py` = content_present / text_legibility / layout_structure / educational_fit (pass·fail·n/a) |
| 보류 트랙 | bench_v1 (40 프롬프트 × 키워드+스타일 조합) — 별개 트랙, 지금 baseline 아님 |

### 이미 확인된 결함 (발표자료 약점 분석에서 도출)

1. **통계적 근거 없음** — n=24, 시드 1개, 오차막대 없음. 88% vs 100%는 이미지 3장 차이이고 Wilson CI가 완전히 겹침.
2. **비교 교란** — 파라미터 수(0.6B / 4B / 20B), 양자화(fp16 / NF4 / Q5_K_M), 스텝(20 / 4 / 50)이 동시에 다름. bf16 baseline이 하나도 없음.
3. **Qwen 삼중 얽힘** — Qwen2.5-VL이 프롬프트를 쓰고, judge도 하고, Qwen-Image가 평가 대상. 게다가 Qwen-Image가 100/100/100.
4. **rubric 천장 효과** — pass/fail 이진 3축으로 상위권 변별 불가.
5. **csd_target 순환성** — 프롬프트가 바로 그 소스 이미지에서 나왔으므로, 재고 있는 건 모델 품질이 아니라 "VLM 캡션의 round-trip 정도".
6. **custom_cv 미검증** — 판별력 없음이 이미 확인됨. flat이 아닌 스타일을 구조적으로 불리하게 만듦.
7. **VRAM / latency 미측정** — 프로젝트 프레이밍이 "16GB 서빙 제약"인데 정작 그 숫자가 없음.
8. **사람 평가 0건**.

---

## 1. 코드작업 / 실험 — 코딩 에이전트 핸드오프 프롬프트

> 아래 각 블록은 **컨텍스트 없는 에이전트에게 그대로 붙여넣는 용도**입니다.
> 경로 중 `‹확인›` 표시된 것은 넘기기 전에 실제 레포에서 확인하세요.

### 우선순위

```
P0  TASK-A (통계)          — 기존 데이터만으로 반나절. 가장 값싸고 방어력 상승 최대
P0  TASK-B (rubric 재설계)  — 이후 모든 실험의 자가 되므로 먼저 고쳐야 함
P1  TASK-C (judge 검증)
P1  TASK-D (VRAM/latency)
P2  TASK-E (프롬프트 리라이팅 harness)
P2  TASK-F (속도: Lightning / distilled 체크포인트)
P3  TASK-G (Ideogram block + 텍스트 렌더링)
P3  TASK-H (텍스트/수식 오버레이 파이프라인) — B가 끝나기 전엔 시작 금지
```

---

### TASK-A · 기존 점수에 통계 검정 붙이기

```
[배경]
t2i-lab이라는 text-to-image 벤치마킹 프로젝트다. 교육용 일러스트 생성 품질을
3개 모델(PixArt-Sigma, FLUX.2-klein-4b NF4, Qwen-Image)에서 비교했다.
24개 프롬프트를 세 모델 모두에 동일하게 넣은 paired 설계다.

[입력]
- bench/scores/v243_*/pass1.csv, bench/scores/v244_*/pass1.csv, (Qwen-Image 해당 디렉토리) ‹확인›
  컬럼: prompt_id, vqascore, custom_cv 등
- csd_target 결과 CSV ‹확인›
- judge 결과 (pass/fail/n/a 4축) ‹확인›
각 CSV는 prompt_id로 조인 가능하다. prompt_id는 8개 카테고리 × 3개 VLM 소스 구조를
문자열에 포함하고 있으니 파싱해서 category, prompt_source 컬럼을 만들어라.

[해야 할 일]
scripts/stats_report.py 하나만 새로 만든다. 인자는 --in (CSV 디렉토리), --out (출력 디렉토리).
다음을 계산해서 CSV + PNG로 떨군다.

1. 모델 쌍별 Wilcoxon signed-rank test
   - 대상: vqascore, csd_target (연속형 지표)
   - prompt_id로 페어링. p-value와 effect size(r = Z/sqrt(N))를 함께 출력.
2. judge pass rate에 Wilson score 95% 신뢰구간
   - 축별 / 모델별. n/a는 분모에서 제외하고, 제외된 n을 반드시 같이 기록.
   - text_legibility는 pass rate가 아니라 "n/a가 아닌 비율"(= 글자 비슷한 걸 그리려 시도한 비율)을
     별도 컬럼 emission_rate로 함께 출력.
3. 모델 쌍별 Fisher's exact test — judge 축별 2x2 pass/fail
4. per-prompt 차이 분포 박스플롯 (모델 쌍 × 지표)
5. 층화 집계 표 3종:
   - category × model
   - prompt_source × model  ← 자기 계열 편향 확인용, 이게 제일 중요
   - track(structural = C1,C2,C7,C8 / illustration = C3,C4,C5,C6) × model

[검증 기준]
- 24개 프롬프트가 세 모델 전부에서 매칭되는지 assert. 매칭 실패 시 어떤 id가 빠졌는지 출력하고 중단.
- Wilcoxon 결과를 scipy.stats.wilcoxon로 계산하되, 동일값(tie)이 많으면 경고를 출력.
- 손으로 검산할 수 있게 요약 표를 stdout에도 출력.

[하지 말 것]
- 기존 채점 스크립트를 건드리지 마라. 읽기 전용이다.
- 시각화 라이브러리를 새로 도입하지 마라. matplotlib만.
- 결과 해석을 코드에 하드코딩하지 마라. 숫자만 뱉으면 된다.
- 200줄 넘으면 과설계다.
```

---

### TASK-B · rubric 재설계 (천장 효과 제거)

```
[배경]
교육용 T2I 생성 결과를 VLM judge로 채점하는데, 현재 rubric이
content_present / text_legibility / layout_structure / educational_fit 4축 pass·fail 이진이고
한 모델이 3축 전부 100%가 나와서 변별력이 없다. 이걸 고쳐야 한다.

[입력]
- configs/benchmarks/vlm-prompts.json ‹확인›
  각 항목에 프롬프트 텍스트와 "metric 힌트"(정답 조건 서술)가 들어 있다.
- scripts/judge_lecture24.py ‹확인› — 현재 judge 구현. Qwen2.5-VL-7B-Instruct 사용.

[해야 할 일]
1. vlm-prompts.json의 metric 힌트를 **원자적 spec item 리스트**로 확장한 파일을 만든다.
   경로: configs/benchmarks/vlm-prompts-spec.json
   형식:
   {
     "id": "C2_claude",
     "spec_items": [
       {"id": "s1", "type": "count",     "check": "exactly 3 bars are present"},
       {"id": "s2", "type": "attribute", "check": "each bar has a distinct fill color"},
       {"id": "s3", "type": "spatial",   "check": "bars sit above a horizontal baseline"},
       {"id": "s4", "type": "text",      "check": "an axis label region exists"}
     ]
   }
   항목당 6~12개. type은 count / attribute / spatial / text / style 중 하나.
   초안은 자동 생성하되, **사람이 검토할 수 있도록 원본 프롬프트 문장을 함께 남겨라.**

2. scripts/judge_spec.py 신규 작성. 인자 --images, --spec, --out.
   - spec item 하나당 VLM에 yes/no 질문 1개씩 독립 호출.
   - 출력: prompt_id, item_id, type, verdict(yes/no/unclear)
   - 이미지당 종합 점수 = 통과 item 수 / 전체 item 수 (연속값이 되므로 천장 효과가 사라진다)
   - 호출 순서를 랜덤화하고, 질문에 "정답이 yes일 것 같다"는 유도 표현을 넣지 마라.

3. scripts/judge_spec_manual.py — 같은 spec에 대해 사람이 터미널에서 y/n을 입력해
   손 채점 CSV를 만드는 최소 도구. 30장 정도 채점할 수 있으면 된다.

[검증 기준]
- 파일럿 3장에 대해 judge_spec.py 결과와 judge_spec_manual.py 손 채점을 비교해
  일치율을 출력. 일치율이 0.8 미만이면 그 사실을 명시적으로 경고 출력.
- spec item이 하나도 없는 프롬프트가 있으면 중단.

[하지 말 것]
- 기존 judge_lecture24.py를 수정하거나 삭제하지 마라. 둘 다 남긴다.
- Likert 1~5 척도로 바꾸지 마라. yes/no 원자 질문의 개수로 연속값을 만드는 게 요점이다.
- 자동 재시도/자기 검증 루프를 만들지 마라.
```

---

### TASK-B2 · VLM judge 관대성 편향 제거 ✅ STAGE 0~3 완료 (2026-07-27)

```
[배경]
TASK-B의 spec item judge(Qwen2.5-VL-7B-Instruct) 검증 중 사람 손 채점 27건 대비 일치율
0.67, 불일치 9건이 전부 VLM이 더 관대한 방향으로 나타남. count/attribute 축에 집중된
축 특이적 체계 편향으로 판단, "judge를 더 똑똑하게" 대신 "측정 가능한 축은 결정론적으로
잰다"는 전략으로 STAGE 0~4를 설계해 진행함.
```

**STAGE 0 — 불일치 9건 triage**: `scripts/triage_disagreement.py`로 9건 분류(A 지각오류 5,
B 문구모호 4, C 사람오류 0). B≥3 게이트 발동 → spec 문구 재작성(주관적 형용사 제거, s8/s10
분리) 후 재채점, 일치율 0.67→0.76(22/29)로 개선. 남은 불일치(chatgpt s8/s9)는 문구가 아니라
chatgpt 소스 이미지의 생성 실패 자체가 원인으로 확인.

**STAGE 1 — yes/no → 추출형 질문(probe) 전환**: count 항목에 `probe`/`expect`(int_eq) 필드
추가, `judge_spec.py --mode probe` 구현. 결과: yesno와 probe 모드 일치율·κ가 **완전히 동일**
(22/29, κ=0.55) — 원인이 yes/no 형식의 acquiescence bias가 아니라 7B VLM의 순수 시각적
개수 세기 지각 한계임을 확인. STAGE 2로 진행.

**STAGE 2 — count/attribute 축 CV 라우팅 (파일럿)**: `scripts/measure_cv.py` 신규
(`count_regions`, `region_colors`). structured_worksheet_template의 박스/핀 개수(s1/s3)만
파일럿 라우팅 — CV가 사람 라벨과 **6/6 완전 일치**, 같은 6건에서 VLM은 4/6만 일치. n=6이라
정식 κ는 못 냄, STAGE 3에서 재검증 필요. Data Viz/과학 다이어그램/도형 카테고리와
polygon_sides는 이번 세션 범위 밖으로 남김.

**STAGE 3 — 라벨 확대(125건) + 정식 κ 계산**: 도중 프롬프트 드리프트(커밋 778d5dd)로
v243/v244/v245가 무효화되어 v246/v247/v249로 재생성(→ baseline 문서는 `bench/results.md`
참고), STAGE 0~2 라벨은 전부 재작업 대상이 됨. 부정문 spec 19개 item 긍정문으로 정리 →
`sample_stage3.py` 재실행(worklist_v2, 125건, 축당 25건) → 사람 손 채점(`stage3_manual_v2.csv`)
→ 서버 23 디스크 확보(HunyuanImage-2.1 캐시 18G 삭제, 사용자 확인 후) → `t2i-judge` env
재생성 + 이미지 72장 rsync → `scripts/sweeps/stage3_auto_judge.sh`(신규, alert.py 연동)로
v246/v247/v249 자동 채점 → `judge_agreement.py`로 κ 계산.

**최종 결과**:

| 구분 | n | 일치율 | κ |
|---|---|---|---|
| 전체 | 125 | 0.74 | 0.37 |
| claude 소스 | 49 | 0.78 | 0.41 |
| chatgpt 소스 | 40 | 0.78 | 0.39 |
| qwen 소스 | 36 | 0.67 | 0.33 |

전부 κ<0.6 — **Qwen2.5-VL-7B judge는 이 규모에서도 신뢰할 수 없음**(unvalidated,
`bench/results.md`에 명시). 자기 계열 선호 가설은 지지되지 않음(오히려 qwen 소스에서
가장 낮은 κ). 불일치 32건은 `bench/scores/stage3_disagreement_v2.csv`.

**STAGE 4 (조건부, 미실행)**: STAGE 1~3 이후에도 κ<0.6이고 그 축이 결론에 필수적일 때만
실행 — 비-Qwen judge(InternVL3-8B/Gemma-3-12B 4bit 등)와 삼각 비교. spec item 채점이
최종 모델 비교에 꼭 필요한지부터 판단 후 착수할 것.

전체 신규 코드: `triage_disagreement.py` / `measure_cv.py` / `judge_agreement.py` /
`sample_stage3.py` / `stage3_auto_judge.sh`.

---

### TASK-C · judge 신뢰성 검증 (교차 judge + Cohen's κ)

```
[배경]
현재 VLM judge는 Qwen2.5-VL-7B-Instruct다. 그런데 평가 대상 중 하나가 Qwen-Image이고,
프롬프트 일부도 Qwen2.5-VL이 작성했다. 자기 계열 선호(self-enhancement bias) 의심을
해소해야 한다. GPU는 RTX 3090(24GB) 1장, 16GB 예산 제약이 있다.

[해야 할 일]
1. scripts/judge_spec.py(TASK-B 산출물)에 --judge-model 인자를 추가해
   판정 모델을 교체 가능하게 한다. 기본값은 기존 Qwen2.5-VL-7B.
2. 비-Qwen 계열 judge를 최소 1개 붙인다. 후보: InternVL3-8B 또는 Gemma-3-12B 4bit.
   VRAM에 안 들어가면 그 사실과 실측 peak VRAM을 기록하고 더 작은 모델로 내려가라.
3. scripts/judge_agreement.py 신규. 인자 --a, --b, --out.
   두 채점 CSV(사람 vs VLM, 또는 VLM A vs VLM B)를 받아
   Cohen's κ, 단순 일치율, 불일치 항목 목록을 출력.

[검증 기준]
- 사람 손 채점 30장 이상 확보된 상태에서 (사람 vs Qwen judge) κ를 먼저 보고한다.
- κ 0.6 미만이면 그 judge의 결과는 신뢰할 수 없다고 리포트에 명시.
- prompt_source별로 κ를 쪼개서 출력할 것. Qwen 소스 프롬프트에서만 판정이 후한지가 핵심 질문이다.

[하지 말 것]
- judge 여러 개를 앙상블해서 하나의 점수로 합치지 마라. 각각 따로 보고한다.
- 새 모델을 받기 위해 기존 환경의 transformers 버전을 올리지 마라. 환경은 conda env로 관리하라.
```

**진행 상황 (2026-07-27, 파일럿 규모 완료)**

- `scripts/judge_spec.py`에 `--judge-model`/`--judge-quant4bit` 추가, `scripts/judge.py`를
  Qwen 전용 백엔드 + 범용(`AutoModelForImageTextToText`) 백엔드로 일반화.
- `scripts/judge_agreement.py` 신규 — `--a/--b/--out`, 전체 + prompt_source(claude/chatgpt/qwen)별
  Cohen's κ·일치율·불일치 목록 출력. 로컬에서 기존 pilot CSV로 검증 완료.
- 2차 judge로 `unsloth/gemma-3-12b-it-bnb-4bit`(사전 4bit, ~7.3GB, ungated) 채택 —
  `google/gemma-3-12b-it` 원본(bf16 22.7GB, gated)은 서버 여유 디스크에 안 들어감.
- **인프라 이슈**: 이 체크포인트가 transformers 내부적으로 `torch>=2.6`을 요구하는데
  `t2i-judge`(Qwen2.5-VL 작동 버전)는 torch 2.5.1 고정 — 건드리지 않고 `t2i-judge2`
  (torch 2.6.0+cu124, transformers 5.14.1) 신규 env로 분리. 설치 중 서버 디스크가
  92%까지 참 → pip/conda 캐시 정리로 확보(`envs/README.md` 참고).
- 실행 스크립트 `scripts/sweeps/pilot_judge_gemma3.sh` 신규, `alert.py` 연동으로
  Discord 알림 확인됨.

**핵심 결과** (v243 파일럿 3장, spec item 29건, `bench/results.md`에 상세):

| 비교 | 일치율 | 전체 κ | claude κ | chatgpt κ | qwen κ |
|---|---|---|---|---|---|
| 사람 vs Qwen2.5-VL-7B (기존) | 0.76 | 0.55 | 0.55 | 0.29 | 0.55 |
| 사람 vs Gemma-3-12B-4bit (신규) | 0.66 | 0.31 | 0.17 | 0.40 | 0.17 |

- 두 judge 모두 κ<0.6 — **이 규모에서는 둘 다 신뢰할 수 없음.** 사람 손 채점 30장 이상
  확보 기준에 이제 막 도달한 수준이라, 표본을 늘려 재검증하기 전까지 spec item 채점
  결과를 모델 비교의 최종 근거로 쓰지 말 것.
- **자기 계열 선호(self-enhancement bias) 가설은 이 파일럿에서 지지되지 않음**: Qwen
  judge가 qwen 소스에 유독 후하지 않고(claude와 동일 κ=0.55), Gemma-3도 qwen 소스에
  유독 박하지 않음(claude와 동일 κ=0.17). 대신 두 judge 모두 **chatgpt 소스에서 서로
  반대 방향으로 튐**(Qwen: chatgpt 최저 0.29 / Gemma-3: chatgpt 최고 0.40) — 계열 편향보다
  chatgpt 소스 spec item 문구의 모호성 문제일 가능성.

**다음 단계**: 사람 손 채점 규모를 30장 이상으로 늘려 재검증 필요.

---

### TASK-D · VRAM / latency 실측 테이블

```
[배경]
프로젝트의 핵심 제약이 "16GB VRAM 서빙"인데 정작 그 숫자가 리포트에 없다.
서버: Linux, RTX 3090 24GB (호스트명 camp-16).

[해야 할 일]
scripts/bench_cost.py 신규. 인자 --config (모델 YAML), --prompts, --out.
모델별로 다음을 측정해 CSV 한 줄씩 기록:
  model, dtype/quant, num_inference_steps, resolution,
  peak_vram_gb, model_load_s, latency_p50_s, latency_p90_s, images_measured

- peak VRAM은 torch.cuda.max_memory_allocated() + nvidia-smi 실측 둘 다 기록
  (allocator 밖의 CUDA context / cuDNN workspace 때문에 값이 다르다)
- warmup 2장 버리고 그 다음 10장으로 측정
- 측정 중 다른 프로세스가 같은 GPU를 쓰고 있으면 경고 출력

[추가 실험 — 교란 제거용]
FLUX.2-klein-4b에 대해 세 조건을 각각 측정:
  (a) 현재 쓰는 NF4 체크포인트
  (b) 같은 모델 bf16
  (c) distilled 체크포인트 여부 확인 — 레포명이 FLUX.2-klein-base-4B인지 FLUX.2-klein-4B인지 확인하고
      distilled라면 guidance_scale=1.0, num_inference_steps=4로 재측정
이유: 현재 11.39s/img가 base 체크포인트를 쓰고 있거나 NF4 dequant 오버헤드일 가능성이 있다.
bnb NF4는 Ampere(sm_86)에 fused kernel이 없어 오히려 느려지는 경우가 많다.
distilled bf16이 8.4GB면 16GB 예산에 이미 들어오므로 NF4를 쓸 이유가 없어질 수도 있다.

[검증 기준]
- 세 조건의 출력 이미지를 같은 시드로 뽑아 나란히 저장. 육안 비교 가능해야 한다.
- (a)와 (b)의 품질 차이가 없는데 (a)가 더 느리면 그 사실을 리포트 맨 위에 쓸 것.

[하지 말 것]
- 속도를 위해 모델 코드에 패치를 넣지 마라. 체크포인트/설정 교체만 한다.
```

---

### TASK-E · 프롬프트 리라이팅 harness (2 백엔드 비교)

```
[배경]
한국어 교사 입력 → 영어 T2I 프롬프트로 바꾸는 리라이터가 이미 있다.
이걸 더 정교한 리라이터로 교체하면 이미지 품질이 올라가는지 검증하려 한다.
비교 대상 두 백엔드:
  (1) Wan2.2 계열 prompt_extend.py 구조 (인터페이스만 차용, 시스템 프롬프트는 교체)
  (2) PromptEnhancer-7B (Tencent HunyuanImage, CVPR 2026)
GPU: RTX 3090 24GB.(ubuntu@172.10.5.23 사용)

[중요한 사전 지식 — 그대로 반영할 것]
- Wan2.2의 원본 시스템 프롬프트는 영상 생성용이라 움직임/카메라워크 어휘를 강제로 붙인다.
  교육용 flat 일러스트에는 해롭다. 인터페이스 구조만 쓰고 내용은 새로 쓴다.
- PromptEnhancer-7B는 bf16에서 실측 약 15GB (README의 13GB는 부정확).
  trust_remote_code=True 필요, transformers >= 4.56 필요.
  기본 시스템 프롬프트가 중국어라 반드시 교체해야 한다.
  공식 추론 코드에서 enable_thinking=False가 기본값이다 (CoT가 대표 기능인데도 그렇다) — 두 설정 다 실험할 것.
- AlignEvaluator는 공개되지 않았다. 공식 평가 스크립트는 Gemini API를 judge로 쓴다.
  따라서 보상/평가는 기존 파이프라인(TASK-B의 spec 채점 + CSD)으로 대체한다.

[해야 할 일]
scripts/rewrite.py 신규. 인자 --in (프롬프트 JSON), --backend {passthrough,wan_style,promptenhancer},
--system-prompt (txt 경로), --out (JSON).
- passthrough = 아무것도 안 하는 대조군. 반드시 포함할 것.
- 출력 JSON은 원본 프롬프트와 리라이팅된 프롬프트를 둘 다 보존한다.
- 시스템 프롬프트는 코드가 아니라 configs/rewrite/*.txt 파일로 분리.

그다음 기존 생성 스크립트(scripts/lecture_generate.py ‹확인›)에 리라이팅된 JSON을
그대로 흘려 3개 조건 × 24 프롬프트를 생성한다.

[검증 기준]
- 백엔드별 출력 프롬프트 3개씩을 stdout에 찍어 육안 확인 후 전체 실행.
- 리라이터가 "photorealistic", "cinematic", "8k", "ArtStation" 같은 사진 계열 어휘를 넣는지
  단순 키워드 매칭으로 세어서 리포트. 이게 flat 교육 일러스트를 망치는 주 경로다.
- 최종 판정은 TASK-B의 spec 통과율로 한다. VQAScore 단독으로 판정하지 마라.

[하지 말 것]
- 파인튜닝(QLoRA)을 지금 하지 마라. 시스템 프롬프트 제약만으로 먼저 측정한다.
- 백엔드를 추상 클래스로 감싸지 마라. if/elif 3개면 충분하다.
- 리라이터 출력을 자동으로 검증/재시도하는 루프를 만들지 마라.
```

**진행 상황 (2026-07-27, 3개 조건 리라이팅 완료 / 이미지 생성 전)**

- `scripts/rewrite.py` 신규 — `--in/--backend/--system-prompt/--out`, backend 3개
  (`passthrough`/`wan_style`/`promptenhancer`)를 if/elif로 구현. 미리보기 3개 stdout 출력,
  photo-word 키워드 리포트 포함. 시스템 프롬프트는 `configs/rewrite/wan_style.txt`,
  `configs/rewrite/promptenhancer.txt`로 분리.
- `wan_style`은 Qwen2.5-7B-Instruct에 Wan2.2 `prompt_extend.py` 인터페이스 구조만 차용
  (내용은 새 시스템 프롬프트로 교체). `promptenhancer`는 `tencent/HunyuanImage-2.1`의
  `reprompt` 서브폴더(실측 bf16 ~18GB) — `trust_remote_code=True`인데 커스텀 코드
  (`tokenization_hy.py`)가 리포 루트에서만 조회돼 `subfolder=`가 안 먹어서
  `snapshot_download`로 로컬에 받은 뒤 그 경로로 로드하도록 우회. `tiktoken` 의존성 누락도
  발견해 설치.
- `scripts/lecture_generate.py`에 `--prompts-json` 옵션 한 줄 추가(기본값 불변, surgical) —
  `scripts/rewrite.py` 출력을 그대로 흘려보낼 수 있게 함.
- `ubuntu@172.10.5.23`을 채점 겸 리라이팅 서버로 확장(CLAUDE.md 갱신) — 디스크가 95%
  차 있어서 `t2i-judge`/`t2i-judge2`/`t2i-score` env와 채점용 모델 캐시(Qwen2.5-VL-7B,
  Gemma-3-12B-4bit, CLIP)를 **freeze 커밋 후 삭제**해서 50GB 확보, 그 위에 `t2i-rewrite`
  env를 새로 만듦. PromptEnhancer-7B 첫 다운로드는 shard 2/3이 죽어서(dead connection)
  `hf download` + Xet 고성능 전송으로 재시도해 해결.
- 채점 파이프라인을 다시 쓰려면 `envs/t2i-judge.txt`/`t2i-judge2.txt`/`t2i-score.txt`로
  env 재생성 + 모델 재다운로드 필요 (지금 23번엔 채점 모델 캐시가 없음).

**핵심 결과** (`image-prompts/rewrite/{passthrough,wan_style,promptenhancer}.json`, 24개
벤치마크 프롬프트 × 3조건, photo-word 키워드 단순 매칭):

| backend | photo-word 검출 | 비고 |
|---|---|---|
| passthrough (대조군) | 0 | |
| wan_style | 0 | 수량/공간관계 보존 양호 |
| promptenhancer (enable_thinking=False) | `cinematic`×4, `photorealistic`×3 (나머지 `photo` 히트는 "no photographic qualities" 부정문이라 오탐) | 명시적으로 금지한 시스템 프롬프트를 줬는데도 새어나옴 |

- **핵심 발견**: PromptEnhancer-7B는 "사진/영상 어휘 금지"를 시스템 프롬프트에 명시해도
  24개 중 최소 7개에서 사실적 어휘가 샌다. wan_style(Qwen2.5-7B, 인터페이스만 차용)은
  0건 — 같은 제약을 줬을 때 base 모델 자체의 "사진처럼 보정하려는" 편향이 더 강한 걸로 보임.
  단, 이건 단순 키워드 매칭 기준이라 오탐(부정문)이 섞여 있고, 최종 판정 기준(TASK-B spec
  통과율)으로는 아직 검증 안 됨.

**다음 단계**: `enable_thinking=True` 조건은 아직 안 돌림(사전지식에 "두 설정 다 실험"
명시돼 있었음 — False만 완료). 157번(생성 전용) 서버에서
`python -m scripts.lecture_generate --model <candidate> --prompts-json image-prompts/rewrite/<backend>.json`
로 3조건×24개 실제 이미지 생성 → TASK-B spec 채점 파이프라인으로 최종 판정, 아직 미실행.

---

### TASK-F · 속도 실험 (Qwen-Image-Lightning 등)

```
[배경]
Qwen-Image(약 20B, GGUF Q5_K_M, ~50 steps)가 품질은 가장 좋은데 너무 느리다.
few-step distilled 변종인 Qwen-Image-Lightning으로 대체 가능한지 본다.
GPU: RTX 3090 24GB, 서빙 예산 16GB.

[해야 할 일]
1. Qwen-Image-Lightning 체크포인트를 받아 기존 모델 YAML 규약(configs/models/*.yaml ‹확인›)에 맞춰
   설정 파일 하나를 추가한다. 기존 파일들의 필드 구조를 그대로 따를 것.
2. TASK-D의 scripts/bench_cost.py로 Qwen-Image(full) vs Lightning의
   peak VRAM / latency를 같은 조건에서 측정.
3. 동일 시드·동일 24 프롬프트로 생성하고 TASK-B의 spec 채점 + CSD를 돌린다.
4. 리포트: quality(spec 통과율) vs latency vs VRAM 3열 표.

[검증 기준]
- full과 Lightning의 출력이 같은 시드에서 명백히 다른 이미지여야 한다.
  거의 동일하다면 체크포인트 로딩이 잘못된 것이니 중단하고 보고.
- step 수를 임의로 조정하지 말고 각 체크포인트의 공식 권장값을 쓰고, 그 값을 CSV에 기록.

[하지 말 것]
- 속도 최적화를 위해 다른 모델(PixArt, FLUX)의 step 수를 같이 건드리지 마라.
  step 수는 이미 모델 간 비교의 교란변수다. 여기서는 Qwen 계열 내부 비교만 한다.
```

---

### TASK-G · Ideogram-4 block 문제 + 텍스트 렌더링 평가

```
[배경]
Ideogram-4로 생성하면 간헐적으로 "blocked" 응답이 오고 이미지가 안 나온다.
동일 프롬프트가 어떤 때는 되고 어떤 때는 막힌다.

[가장 유력한 원인 — 먼저 이것부터 확인]
Ideogram의 Magic Prompt(자동 프롬프트 확장)가 호출마다 다르게 리라이팅하고,
확장된 결과가 안전 필터에 걸리는 것이다. 원본이 아니라 확장본이 걸리므로 비결정적으로 보인다.
→ API 호출에서 magic prompt 옵션을 OFF로 두고 재현성을 먼저 확보한다.
   (v4에서 필드명이 바뀌었을 수 있으니 developer.ideogram.ai 문서 확인)

[해야 할 일]
1. scripts/ideogram_probe.py 신규. 24개 프롬프트를 magic prompt ON/OFF 두 조건으로
   각 3회씩 호출하고 block 여부를 CSV로 기록한다.
   컬럼: prompt_id, magic_prompt, trial, blocked(bool), error_message, latency_s
   → OFF에서 결정론적(같은 프롬프트는 항상 같은 결과)이 되는지가 첫 검증 기준.
2. block이 남는 프롬프트가 있으면 그 프롬프트들의 공통 어휘를 뽑아 리포트.
   (인체, 역사적 사건, 국가명 등 패턴이 있는지)
3. 프롬프트를 JSON caption schema로 변환하는 옵션을 추가.
   필드: high_level_description / style_description / compositional_deconstruction(background + elements)
   Ideogram 공식 문서가 plain-text 프롬프트의 오탐률이 높음을 인정하고 JSON 경로를 권장한다.
   변환 전/후 block rate를 비교.
4. 별도로 — Ideogram-4가 오픈 웨이트로 공개되었는지 확인하라(2026년 6월경 릴리스 정보 있음,
   레포 후보: ideogram-ai/ideogram-4-nf4 / -fp8, 라이선스 게이트 있음).
   사실이면 셀프호스팅 시 API-side 필터가 아예 사라지므로 이게 근본 해결이다.
   1024px에서 peak VRAM 실측이 필요하다(9.3B, 16GB 예산 초과 가능성 있음).

[텍스트 렌더링 평가 — 위와 분리된 작업]
5. 먼저 파일럿을 돌린다. 현재 후보 3종(FLUX.2-klein-4b, Lumina2, PixArt-Sigma)에
   짧은 영어 단어 렌더링을 요구하는 프롬프트 10개를 넣고 PaddleOCR로 word-F1을 잰다.
   **세 모델 모두 0에 가까우면 OCR 기반 평가 자체가 무의미하므로 그 사실을 보고하고 중단한다.**
   floor effect 위에 평가 인프라를 짓지 않기 위한 게이트다.
6. 게이트를 통과한 모델에 대해서만 Ideogram과의 비교 실험을 설계한다.

[검증 기준]
- 1번의 OFF 조건이 결정론적이지 않으면 원인 가설이 틀린 것이니 즉시 보고하고 멈춰라.
- OCR 결과는 반드시 이미지 3장을 사람이 직접 보고 OCR 출력과 대조해 검증한 뒤 전체 실행.

[하지 말 것]
- 안전 필터를 우회하는 프롬프트 트릭을 시도하지 마라. 포맷 문제와 우회는 다르다.
- 한국어 텍스트 렌더링부터 시작하지 마라. 영어에서 0이면 한국어는 볼 것도 없다.
```

---

### TASK-H · 텍스트/수식 오버레이 파이프라인 (labeled illustration 트랙)

> **TASK-B가 끝나기 전에는 시작하지 말 것.** 오버레이가 나은지 판정할 자가 아직 없다.

```
[배경]
교육용 일러스트 중 라벨이 필요한 것(과학 개념도, 활동지)은 T2I 모델이 글자를 못 그린다.
"텍스트만 따로 만들어 얹는" 방식과 "이미지와 함께 생성" 방식 중 어느 쪽이 나은지 검증한다.
핵심 어려움: 라벨이 그림의 특정 지점에 의미적으로 앵커되어야 한다.
GPU: RTX 3090 24GB. VLM은 Qwen2.5-VL-7B-Instruct 사용 가능.

[실험 설계 — 두 조건만 비교]
조건 A: render_prompt에 라벨 텍스트를 직접 삽입해 T2I가 통째로 그리게 함
조건 B: negative prompt로 텍스트를 억제한 무텍스트 래스터를 생성 → 라벨을 SVG로 오버레이
대상: 라벨이 필요한 프롬프트 8~10개만. 전체 24개로 확장하지 마라.

[스테이지 — 각 스크립트는 --in / --out 명시 인자만 받고 서로 모른다]
1. plan.py       : 프롬프트 → plan.json
   verify        : 스키마 검증 통과, 라벨 개수 1~5
2. (기존 생성 스크립트 재사용) : plan.json → 무텍스트 PNG
   verify        : OCR로 글자 검출 시 해당 프롬프트는 시드 바꿔 재생성
3. ground.py     : PNG + 라벨 설명 → 앵커 bbox (Qwen2.5-VL grounding)
   verify        : 파일럿 3장에서 bbox를 이미지 위에 그려 육안 확인
4. overlay.py    : PNG + anchors.json → SVG → 최종 PNG + placement.json
   verify        : 라벨 박스 간 IoU 0, leader line 끝점이 앵커 bbox 내부
5. label_eval.py : 최종 PNG → OCR 정확도 + 앵커 정확도 + 가림 정도

**스테이지 3(grounding)부터 짜서 파일럿 PNG 한 장에 붙여봐라.**
여기가 가장 불확실하고, Qwen2.5-VL의 bbox 품질이 안 나오면 나머지 설계가 전부 바뀐다.

[plan.json 최소 스키마]
{
  "id": "bio_cell_01",
  "prompt_ko": "식물 세포의 구조",
  "render_prompt": "flat educational illustration, plant cell cross-section, ...",
  "style_preset": "edu-flat-v2",
  "negative": "text, letters, labels, captions, watermark",
  "labels": [
    {"id": "L1", "ko": "세포벽", "ground": "the outermost rigid boundary of the cell"},
    {"id": "L2", "ko": "엽록체", "ground": "green oval organelle inside the cell"}
  ]
}
negative는 조건 B에서만 적용. 조건 A는 render_prompt에 라벨 텍스트를 명시적으로 삽입.

[라벨 배치 알고리즘 — 멍청하게 유지]
각 라벨에 대해:
  앵커 bbox 중심에서 8방향 후보 위치 생성 (거리 = 이미지 폭의 12%)
  후보 점수 = w1*(다른 라벨과 겹침) + w2*(엣지 밀도맵과 겹침) + w3*(중심 이탈도)
  최소 점수 채택, leader line은 앵커 bbox 경계까지
엣지 밀도맵은 기존 scoring.py의 line uniformity 계산에 쓰이는 Canny 결과를 재사용.
힘 기반 최적화나 반복 정제를 만들지 마라. 라벨 5개 이하에서 그리디로 충분하다. 50줄 넘으면 과설계.

[메트릭 4개]
  ocr_exact   : PaddleOCR-ko 라벨별 완전일치 비율 (B는 합성 텍스트이므로 1.0에 가까워야 정상)
  ocr_cer     : 문자 오류율 — A의 실질 판독률
  anchor_acc  : VLM에 "'엽록체' 라벨은 어느 부분을 가리키나?" 물어 정답 여부  ← 핵심 지표
  occlusion   : 라벨 박스와 엣지맵 겹침 비율
anchor_acc를 grounding과 같은 모델로 재면 순환이다. 완화책 둘:
  (i) 질문 방향을 뒤집어 라벨→객체로 묻기
  (ii) 30장은 손으로 채점해 VLM 채점과의 일치율을 먼저 확인. 낮으면 이 지표는 버린다.

[함정]
- 한글 폰트: cairosvg/resvg는 시스템 폰트를 참조한다. 서버에 Pretendard 또는 Noto Sans KR를
  설치하고 fc-cache -fv 하지 않으면 라벨이 두부(□□□)로 나온다.
  스테이지 4의 첫 verify에 폰트 렌더 확인을 넣어라.
- 좌표계: 앵커는 정규화 [0,1]로만 저장. 모델마다 해상도가 달라 픽셀 저장은 깨진다.
- PixArt-Sigma는 negative prompt를 넣어도 글자 비슷한 형태를 그리는 경우가 있다.
  스테이지 2의 OCR verify가 이걸 잡는다.

[하지 말 것]
- SAM3 세그멘테이션 + 전체 SVG 벡터화(AutoFigure-Edit 풀 파이프라인)를 구현하지 마라.
  그건 사후 편집 가능성을 위한 것이고 이 가설과 무관하다. 오버레이만으로 검증된다.
- Qwen-Image 계열의 네이티브 텍스트 렌더링을 조건 C로 추가하지 마라. 별개 가설이다.
- plan 단계에 LLM 반복 정제(auditor) 루프를 만들지 마라.

전체 작업량은 plan.py / ground.py / overlay.py / label_eval.py 네 파일, 400줄 안쪽이다.
```

---

## 2. 공부해야 할 것

### 2-1. 통계 — 최우선

발표 방어력이 가장 크게 오르는 영역이고, TASK-A를 해석하려면 필수.

| 개념 | 왜 필요한가 |
|---|---|
| **Wilcoxon signed-rank test** | 같은 프롬프트에 대한 paired 비교. 정규성 가정 불필요. 지금 설계에 가장 잘 맞고 unpaired 대비 검정력이 훨씬 높다 |
| **Wilson score interval** | 비율의 신뢰구간. 작은 n과 극단값(24/24)에서 정규근사보다 정확 |
| **Fisher's exact test** | 2×2 pass/fail, n이 작을 때 카이제곱 대신 |
| **paired bootstrap** | 평균 차이의 신뢰구간을 리샘플링으로 |
| **Cohen's κ** | judge-사람 일치도. 0.6 이상이면 substantial agreement로 통용 |
| **effect size (r = Z/√N)** | p값만으로는 "차이가 얼마나 큰가"에 답 못 함 |

**예상 질문 대비:** "왜 FID를 안 썼나?" → FID는 수천 장 규모의 분포 간 거리이고 n=24에서는 추정 편향이 극심하다. 게다가 비교 대상 실제 분포(교과서 도판 대량 코퍼스)가 없다. 정당한 답변이다.

### 2-2. 평가 메트릭의 내부 동작

- **VQAScore** (ECCV 2024) — VQA 모델의 P("Yes") 단일 forward pass. 긴 프롬프트에서 한계. 지금 데이터에서 과학 개념도 카테고리에 명백한 역전 결과가 나왔으므로 이건 "애매한 불일치"가 아니라 **문서화된 metric failure case**로 쓸 수 있다.
- **CSD** — LAION-Styles로 파인튜닝한 ViT, content-invariant 스타일 유사도. flat 교육 일러스트 도메인에서의 한계.
- **custom_cv** (flatness, line uniformity) — 정의를 스스로 완전히 설명할 수 있어야 한다. 현재 판별력이 없다는 게 확인된 상태.
- **VLM-as-judge 실패 모드** — self-enhancement bias, position bias, verbosity bias. 완화 표준: κ 보고, 순서 랜덤화, multi-judge.
- **DiagramEval** (EMNLP 2025) — diagram을 그래프로 보고 텍스트 요소=노드, 연결=방향 엣지로 두고 node/path alignment를 P/R/F1로 정량화. TASK-H를 하게 되면 이게 맞는 자다.
- **OCR 기반 평가** — LongCat-Image가 희귀 문자에서 VLM judge가 실패한다는 관찰에 근거해 평가자를 MLLM judging에서 PPOCRv5로 교체했다. 한글 라벨 정확도는 VLM judge가 아니라 OCR word accuracy + edit distance로 빼는 게 안전하다.

### 2-3. 프롬프트 리라이팅 계보 (태스크 2의 이론 배경)

```
Promptist (2022)  →  APE (ICLR'23)  →  OPT2I  →  PromptEnhancer (CVPR'26)
```

- **APE** — LLM이 프롬프트를 스스로 탐색·생성. 발표에서 이미 다룬 논문. 비용 가정이 이미지 생성 워크로드에는 성립하지 않는다는 점이 약점으로 지적됨.
- **Promptist / OPT2I** — 발표 자료의 APE 섹션에 빠져 있는 선행연구. 채워 넣어야 한다.
- **PromptEnhancer** — CoT 리라이팅 + AlignEvaluator 보상(T2I-KeyPoints 24축) + GRPO. AlignEvaluator는 미공개, 공식 평가 스크립트는 Gemini API를 judge로 씀. **24 keypoints에 glyph accuracy가 없을 가능성이 높다** → 텍스트 렌더링은 이 보상 신호로 절대 개선되지 않는다.
- **FormatSpread** (Sclar et al., ICLR 2024) — LLM에서 포맷이 유발하는 성능 분산을 측정하는 방법론. T2I에는 아직 대응물이 없다.

**여기가 지금 프로젝트의 논리적 긴장 지점입니다.** dialect pilot에서 "모델별 프롬프트 적응은 효과 없다(Promptist-era 가설 실패)"고 결론냈는데, 이제 프롬프트 리라이팅을 추진하려 합니다. 그대로 두면 발표에서 정면으로 찔립니다. 조화시킬 프레이밍 두 가지:

1. **"모델 dialect 적응은 무효, 도메인/스타일 적응은 유효"** — 적응의 대상이 다르다는 구분.
2. **FormatSpread의 T2I판** — 리라이팅으로 얻는 이득이 포맷 내 분산보다 작다는 걸 보이는 방향. 기존 음성 결과의 두 번째 증거축이 된다.

둘 중 어느 쪽으로 갈지는 TASK-E 결과를 보고 정하되, **미리 정해두지 말고 어느 쪽이 나와도 논문이 되는 설계**로 두는 게 안전합니다.

### 2-4. Labeled diagram 생성 (태스크 2-1의 이론 배경)

- **DiagrammerGPT** (COLM'24) — LLM이 diagram plan(엔티티 + 관계 + 2D bbox)을 먼저 만들고 planner-auditor 루프로 정제 → DiagramGLIGEN 생성 → Pillow로 라벨 렌더. 의미 연결이 **plan 단계에서 확정된 채로** 얹힌다는 게 핵심.
- **AutomaTikZ (ICLR'24) → DeTikZify (NeurIPS'24) → TikZero (ICCV'25)** — 코드 중간표현 계보.
- **ScImage** (ICLR'25) — **Python 코드 생성이 TikZ 출력보다 Correctness/Relevance/Scientific style 전부에서 앞섰다**(컴파일 에러율도 0.17 vs 0.19). formula30/diagram30을 matplotlib으로 뺀 판단이 문헌과 일치한다는 근거로 인용 가능.
- **AutoFigure-Edit (ICLR'26) / SciDiagramEdit / SciFig** — raster→vector 하이브리드. "그림은 확산모델, 라벨은 프로그램"으로 모달리티를 분리하되 레이아웃 계획을 공유.
- **Glyph-ByT5 / TextDiffuser / AnyText** — 네이티브 텍스트 렌더링 계열. AnyText가 중/일/한에서 매우 미미한 결과만 보인 이유로 고품질 데이터 수집 난이도를 지적했던 지점.

### 2-5. 속도 / 양자화 (태스크 3의 배경)

- **NF4** — QLoRA의 quantile 기반 4-bit, double quantization, 실효 ~4.1 bit. **Ampere(sm_86)에 fused kernel이 없어 오히려 느려질 수 있다**는 게 지금 11.39s/img 미스터리의 유력 후보.
- **GGUF k-quants** — Q5_K_M의 의미(5-bit nominal, 계층적 superblock scaling, mixed-precision M 정책, 실효 ~5.5 bit).
- **Step distillation** — LCM / DMD / Lightning 계열의 차이. PixArt-Σ의 공개 LCM 체크포인트는 α 기반이지 Σ가 아니다.
- **TeaCache** — training-free 캐싱. Lumina-Image-2.0에서 ~25s → 16.7s(1.5x) ~ 11.9s(2.1x).

---

## 3. 한 줄 요약

- **지금 당장 값싸게 얻을 것:** TASK-A(통계) + TASK-D(VRAM/latency). 기존 데이터만으로 하루 안에 가능하고, 발표/논문 방어력이 가장 크게 오른다.
- **가장 중요한 구조적 수정:** TASK-B(rubric 재설계). 이게 없으면 이후 모든 실험의 결론이 천장 효과에 묻힌다.
- **가장 미루기 쉬운 함정:** TASK-H(오버레이). 재미있지만 자가 없는 상태에서 400줄을 짓게 된다.
- **논문 프레이밍에서 반드시 정리할 것:** dialect pilot 음성 결과와 프롬프트 리라이팅 추진 사이의 논리적 긴장.