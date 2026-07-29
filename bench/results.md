# 모델 실측 기록

generate.py가 노트에 vram/latency를 자동 기록하므로, 여기엔 **결론과 삽질만** 적는다.
(숫자를 손으로 옮겨적지 말 것 — Streamlit Compare 탭이 표로 보여줌)

## Baseline: lecture24 (`configs/benchmarks/vlm-prompts.json`)

**2026-07-24부터 이 테스트를 프로젝트 Baseline으로 고정한다.** 실제 교과서 이미지를 VLM(Claude/ChatGPT/Qwen2.5-VL)에 넣어 뽑아낸 8개 카테고리 × 3개 VLM 소스 = 24개 완성 프롬프트(`configs/benchmarks/vlm-prompts.json`, 소스: `MEMO.md` 로드맵의 Task 1 방법)를 모델에 그대로 흘려 생성 → 채점한 결과다. `bench_v1`(키워드+스타일 조합, 수량/공간/속성 축)과는 별도 트랙이며 서로 대체하지 않는다 — bench_v1은 축별 실패모드 진단용, lecture24는 실제 교육 콘텐츠에 가까운 완성 프롬프트 기준 종합 비교용.

- 대상 run: `v243_pixart-sigma-lecture24`, `v244_flux2-klein-4b-nf4-lecture24`, `v245_qwen-image-lecture24` (`scripts/lecture_generate.py`로 생성).
- 채점: pass1(vqascore+cv) + `scripts/score_csd_target.py`(카테고리당 참조 1장, provisional) + `scripts/judge_lecture24.py`(content_present/text_legibility/layout_structure/educational_fit 4축).
- 종합 리포트: `reports/lecture24-v243-v244-v245/index.html`.
- **앞으로 프롬프트/모델/채점 방식을 바꿀 때는 이 baseline 대비 개선 여부로 판단한다** — `configs/benchmarks/vlm-prompts.json`은 `configs/keywords/*`처럼 비교 기준이므로 함부로 편집하지 않는다(내용을 바꾸려면 새 파일로 분리).
- **알려진 한계**: csd_target은 카테고리당 참조 이미지 1장(원본 교과서 이미지)만 쓰는 provisional 신호다 — 정식 golden set(카테고리당 15~25장) 수집 전까지는 "그 한 장과 얼마나 닮았는가"에 가까운 약한 신호로만 참고할 것.
- **⚠️ 2026-07-27 발견 — v243/v244/v245는 프롬프트 드리프트로 무효화됨**: 커밋 `778d5dd`("backup", 07-27 10:41)가 `vlm-prompts.json`의 24개 중 15개(카테고리×소스) 프롬프트를 고정 baseline 규칙을 어기고 재작성했다. 그런데 `v243/v244/v245` 이미지는 그 전날(07-21)에 **옛 프롬프트**로 이미 생성돼 있었고, `vlm-prompts-spec.json`(TASK-B2 spec item 채점 체계)은 그 뒤(07-27 12:30)에 **새 프롬프트** 기준으로 작성됐다 — 즉 지금 채점 중이던 spec item 문구와 실제 이미지가 15개 카테고리에서 서로 다른 프롬프트를 가리키고 있었다. 새 프롬프트가 더 낫다고 판단해 **새 프롬프트를 baseline으로 확정**하고, `v243/v244/v245`는 `scripts/lecture_generate.sh` + `--model qwen-image`로 재생성하기로 함(새 버전 번호로 생성됨, v243~v245는 그대로 두고 새 버전이 baseline을 대체). TASK-B2 STAGE 0~3에서 만든 라벨(파일럿 29건 + `bench/scores/stage3_manual.csv` 96건)은 옛 이미지 기준이라 재생성 후 다시 라벨링해야 한다.
- **✅ 2026-07-27 — 재생성 완료, baseline이 v246/v247/v249로 교체됨**: 서버 157에서 새 프롬프트 기준으로
  재생성 완료 — `v246_pixart-sigma-lecture24`, `v247_flux2-klein-4b-nf4-lecture24`,
  `v249_qwen-image-lecture24` (전부 status: done, 24장씩). 커밋 `552e478`로 3개 노트를 로컬·23서버에
  동기화 완료(이미지 자체는 gitignored라 scp로 로컬에 별도 복사). qwen-image는 중간에 `v248`로
  한 번 실패했었는데(status: running, 0장 — GGUF/디스크 공간 이슈로 죽은 시도) `.trash/`로
  옮겨두고 커밋에서는 제외했다.
  - v243/v244/v245는 지우지 않고 그대로 둔다 — "옛 프롬프트 기준 기록"으로만 참고, 최종 비교에는 쓰지 않는다.
  - 새 STAGE 3 표본 `bench/scores/stage3_worklist_v2.csv` (125건, 축당 25건)를 v246/v247/v249
    이미지 기준으로 새로 뽑아뒀다. 기존 `stage3_worklist.csv`/`stage3_manual.csv`(96건)는
    v243/v244/v245 기준 기록이므로 건드리지 않았고, 최종 신뢰도 지표 계산에서는 제외한다.
  - **남은 순서(순서를 지킬 것 — 자세한 내용은 `NextJob-TaskB2.md` STAGE 3 참고)**: `sample_stage3.py`가
    `check` 문구를 그 시점 spec.json 값으로 worklist CSV에 얼려 넣고, `judge_spec_manual.py`는
    spec.json이 아니라 그 worklist를 읽으므로, "문구 정리"와 "라벨링"을 동시에 할 수 없다. ①
    부정문 spec 문구(19개 item 후보) 정리 → ② `sample_stage3.py` 재실행(seed 고정이라 표본은 그대로,
    check만 갱신) → ③ 그제서야 `judge_spec_manual.py --worklist ... --out stage3_manual_v2.csv`로
    125건 손 채점(대화형 터미널 도구, 자동화 대상 아님).
  - **서버 23 — STAGE 3 κ 계산의 실제 블로커**: κ는 두 채점자(사람+VLM)가 있어야 나오는데 지금은
    사람 쪽 준비만 진행 중이고 자동 쪽은 v246/v247/v249용으로 아예 없다 — 새 이미지 72장이 23에
    없고, `t2i-judge` env도 23에서 지워져 있다(freeze는 `envs/t2i-judge.txt`에 보존, TASK-E 디스크
    확보 중 지워진 것으로 추정). 디스크는 91% 사용(9.1GB 여유)이라 env를 바로 재생성하기도 빠듯한데,
    그 대부분을 차지하는 `~/.cache/huggingface/hub/models--tencent--HunyuanImage-2.1`(18G)이 채점
    전용 서버 역할과 안 맞는 **T2I 생성 모델 캐시**로 확인됨(역할 분리 규칙 위반 소지, 다른 작업 중
    받았을 수도 있어 임의 삭제는 하지 않음) — 지우면 여유가 27GB로 늘어 env 재생성이 가능해진다.
    사용자 확인 후 (a) 이미지 rsync → (b) `t2i-judge` 재생성 → (c) `judge_spec.py` 실행 → (d)
    `judge_agreement.py`로 κ 계산, 4단계가 남아야 STAGE 3가 끝난다.
  - **참고**: `measure_cv.py`의 상수(box row_band 0.3~0.7, 핀 aspect_range/min_area)는 v243의 옛
    structured_worksheet_template 이미지에 맞춰 튜닝된 값이다. 새 프롬프트로 레이아웃이 달라졌을
    수 있으니, v246 이미지로 CV 카운팅을 다시 돌릴 때 6/6 일치가 그대로 재현되는지 먼저 확인할 것 —
    안 되면 상수를 새로 맞춰야 한다.
  - **✅ 2026-07-27 — STAGE 3 완료(자동 채점 + κ 계산)**: HunyuanImage-2.1 캐시(18G) 삭제로 서버 23
    디스크를 확보하고 `t2i-judge` env(`envs/t2i-judge.txt`)를 재생성, 새 이미지 72장을 rsync한 뒤
    `scripts/sweeps/stage3_auto_judge.sh`(신규, `alert.py` 연동)로 v246/v247/v249 세 모델을
    Qwen2.5-VL-7B(mode=yesno, 사람 손 채점과 동일 기준)로 자동 채점하고 `judge_agreement.py`로
    `stage3_manual_v2.csv`(125건) 대비 κ를 계산했다. 결과: `bench/scores/stage3_auto_v2.csv`,
    `bench/scores/stage3_disagreement_v2.csv`(불일치 32건).

    | 구분 | n | 일치율 | κ |
    |---|---|---|---|
    | 전체 | 125 | 0.74 | 0.37 |
    | claude 소스 | 49 | 0.78 | 0.41 |
    | chatgpt 소스 | 40 | 0.78 | 0.39 |
    | qwen 소스 | 36 | 0.67 | 0.33 |

    전부 κ<0.6 — **Qwen2.5-VL-7B judge는 125건 규모에서도 여전히 신뢰할 수 없다.** 이전 3장짜리
    파일럿(κ=0.55)보다도 낮아졌다. 소스별로도 자기 계열 선호(self-enhancement bias) 가설과 반대
    방향으로, qwen 소스에서 오히려 가장 낮은 일치율(κ=0.33)을 보였다 — spec item 채점 결과를 모델
    비교의 최종 근거로 쓰지 말 것. 다음 단계는 judge 자체를 재검토(TASK-C의 다른 judge 후보 재시도,
    또는 probe 모드로 count류 항목만 분리)하거나, spec item 채점 대신 CV/VQAScore 등 다른 지표
    비중을 높이는 방향을 검토하는 것.

| 모델 | 3090에서 동작 | 16GB 가능? | 결론 | 삽질 메모 |
|---|---|---|---|---|
| pixart-sigma | ✅ | | | |
| sdxl | | | | |
| flux2-klein-4b | ✅ | ✅ (NF4+offload 조건만) | 기본(양자화 없음, cpu offload 없음)은 16GB 초과 — NF4 양자화 + `enable_model_cpu_offload()` 조합으로 진입 성공, 품질 저하는 경미 | 아래 "flux2-klein-4b 16GB 진입 시도" 참고 |
| flux2-klein-4b-base | | | | |
| flux2-klein-9b | | | | |
| zimage-turbo | | | | |
| sd35-medium | | | | |
| sana-1600m | | | | |
| lumina2 | | | | |
| qwen-image | | | | |
| ideogram-4 | | | | |

## 스타일 프리셋 명사 누출(style→object leakage)

**규칙:** LLM/T5 계열 텍스트 인코더 모델(qwen-image, lumina2, sd35-medium, pixart-sigma 등 자연어 서술형 인코더)은 스타일 프롬프트 속 구체 명사(그릴 수 있는 사물)를 오브젝트로 렌더링할 수 있다. 배경/매체로 의도한 것이 아니면 스타일 프롬프트에 구체 명사를 넣지 않는다.

**발견 경위:** 방언(dialect) 1라운드 파일럿(v182~v198)에서 qwen-image/lumina2가 `educational-flat`의 "textbook infographic style" 문구를 문자 그대로 책 오브젝트로 렌더링하는 것을 PNG 메타데이터 대조로 확인. dialect 변환이 만든 confound가 아니라 원본 스타일 프리셋 자체에 내재한 문제.

### 감사 결과 (configs/experiments/ 전체)

| 프리셋 | 위험 명사 | 판정 | 조치 |
|---|---|---|---|
| coloring-book / -es | "kids coloring book" | (c) 의도치 않은 누출 위험 — textbook과 동일 패턴 | v2 파생 권장(미실행, 이번 라운드 범위 밖) |
| diagram-clean | "textbook figure style" | (c) | v2 파생 권장(미실행, 범위 밖) |
| diagram-whiteboard | "whiteboard", "board" | (b) 의도된 배경/매체 — 스타일 자체가 "칠판에 그려진 도표" | 조치 불필요 |
| educational-flat | "textbook infographic style" | (c) round1에서 실증된 원인 | **v2 파생 완료** (educational-flat-v2, Step1) |
| educational-flat-es | "textbook infographic style" | (c) 동일 | 조치 보류 — spanish30 트랙, 이번 라운드 범위 밖 |
| educational-flat-pilot | "textbook infographic style" | (c) 동일 | 조치 안 함 — 1라운드 산출물, 수정 금지(원인 규명용으로 그대로 보존) |
| educational-flat-v2 | 없음 | (a) | - |
| flat-illust / -es | "presentation slide artwork" | (a)~(b) 경계 — "slide"는 발표자료 형식을 가리키는 매체어에 가까워 누출 가능성 낮음, 직접 실증 사례 없음 | 조치 불필요(관찰만) |
| formula-chalkboard | "chalkboard" | (b) 의도된 배경 — 수식이 "칠판에 적힌" 장면을 의도적으로 요구 | 조치 불필요 |
| formula-print | "textbook print style" | (c) — chalkboard와 달리 책 자체가 장면 의도가 아니라 활자체만 묘사하려는 의도인데 "textbook" 단어가 그대로 남아있음 | v2 파생 권장(미실행, formula30 트랙은 범위 밖) |
| history-flat | "history textbook infographic style" | (c) | v2 파생 권장(미실행, 범위 밖) |
| history-storybook | "storybook illustration", "history book artwork" | (c) — 이름과 의도는 화풍(수채 그림책 화풍)이지만 "책" 오브젝트로 새는 동일 위험 | v2 파생 권장(미실행, 범위 밖) |

**결론:** "textbook"/"storybook"/"coloring book" 계열 표현이 있는 프리셋은 전부 동일 위험군. `chalkboard`/`whiteboard`처럼 장면의 배경으로 명시적으로 의도된 명사는 위험군에서 제외. 이번 라운드는 `educational-flat`만 v2로 조치(2라운드 파일럿 대상 5모델이 이 스타일을 쓰기 때문); 나머지는 각 트랙(spanish30/diagram30/formula30/history30) 작업 시 동일 규칙으로 v2 파생 필요.

**v2 재검증(Step3):** lumina2 + flux2-klein-4b를 apple/cat 2키워드로 v2 스타일 재생성 — 책 오브젝트 완전 소멸, 스타일(플랫/선/색감)은 v1과 동등하게 유지됨. 수정 확인 완료.

## 방언(dialect) 2라운드 — 복합 프롬프트(수량/공간/속성) 파일럿

`image-prompts/pilot-complex3-report.md` 참고(그리드/리소스 표/축별 판정 전체). 5모델(flux2-klein-4b, pixart-sigma, sd35-medium, zimage-turbo, lumina2) × 복합 키워드 3개(수량/공간/속성 축) × shared/dialect, v2 스타일 사용.

**핵심 발견 — 1라운드 가설("단순 프롬프트로는 방언 효과가 분리 안 됨")이 맞았다:**

| 모델 | 수량 | 공간 | 속성 | 종합 |
|---|---|---|---|---|
| flux2-klein-4b | **방언으로 개선**(4개→3개) | 차이 없음 | 차이 없음 | 복합 프롬프트에서 방언 효과가 실제로 관측된 유일한 사례 |
| pixart-sigma | 차이 없음 | 차이 없음 | 둘 다 실패(색 전이) | 방언 효과 없음, 속성 결합은 능력 한계 |
| sd35-medium | 둘 다 실패(항상 4개) | 둘 다 실패(좌우 반전 고정) | 차이 없음 | 방언과 무관하게 동일한 방식으로 실패 — 능력 한계 |
| zimage-turbo | 둘 다 실패(항상 2개) | 차이 없음 | 차이 없음 | 수량은 능력 한계, 1라운드와 동일하게 저채도/무채색 스타일 준수 문제도 동반 |
| lumina2 | 차이 없음(둘 다 성공) | 차이 없음 | 차이 없음 | 3축 모두 baseline에서 이미 완벽 — 5개 중 복합 프롬프트 최고 성능, 방언 불필요 |

**결론:** 방언(프롬프트 재표현)으로 실제로 고쳐진 사례는 flux2-klein-4b의 수량 축 하나뿐. 나머지 실패는 조건과 무관하게 동일하게 재현되므로 프롬프트 문제가 아니라 모델 자체의 능력 한계로 판단. lumina2가 복합 프롬프트 전 축에서 가장 안정적.

## flux2-klein-4b 16GB 진입 시도

기본 조건(양자화 없음, `pipe.to("cuda")`만)은 24GB 3090에서도 실측 peak(nvidia-smi 기준, torch `max_memory_allocated()`보다 2~3GB 더 높게 나옴)이 16GB를 넘어 그대로는 탈락. 세 가지 완화책을 순서대로 실측(`educational-flat-pilot`, pilot5 5키워드):

1. **`enable_model_cpu_offload()`만 (양자화 없음)** — 16GB 진입 성공. 다만 이미지당 시간이 기본 대비 약 5.6배로 증가. 출력은 기본 조건과 바이트 단위로 동일(가중치/연산 자체는 안 바뀌므로 당연).
2. **text encoder만 offload (transformer/vae는 GPU 상주, text_encoder만 인코딩 시점에 GPU⇄CPU 왕복)** — **실패.** `encode_prompt()` 호출 시점에 text_encoder+transformer+vae가 동시에 GPU에 올라가 있어 peak이 기본 조건보다 오히려 더 높게 나옴(왕복에 따른 할당 파편화까지 겹침). 속도도 기본 대비 약 3.4배 느려짐. "텍스트 인코더만 내리면 된다"는 가정 자체가 이 파이프라인 구조(단일 컴포넌트만 왕복시켜도 인코딩 순간엔 전부 상주)에서는 성립하지 않음 — 진짜로 절감하려면 인코딩 중엔 transformer도 같이 내려야 하는데, 그러면 결국 ①(전체 offload)과 같아짐. 구현은 `src/adapters/flux2.py`에 남겨뒀지만(`offload: text_encoder`) 채택하지 않음.
3. **transformer NF4 양자화(bitsandbytes) + `enable_model_cpu_offload()`** — 16GB 진입 성공, **①보다 VRAM/속도 둘 다 더 좋음**(양자화로 스왑 대상 자체가 작아졌기 때문). 품질 스팟체크(pilot5 중 "a cat", "a butterfly"): 구조/구도/색상 유지, 다만 그라디언트 음영이 다소 밋밋해지고 윤곽선이 살짝 거칠어지는 경미한 저하 관찰. 리키지·붕괴 등 치명적 결함 없음.

**결론: flux2-klein-4b는 탈락하지 않는다.** NF4 양자화 + cpu offload 조합(`configs/models/flux2-klein-4b-nf4.yaml`)으로 16GB 예산에 안정적으로 진입, 품질 저하도 실사용 가능한 수준. lumina2(품질)+pixart-sigma(속도) 2모델 체제로의 축소는 **발동하지 않음** — flux2-klein-4b는 "NF4 양자화 조건"으로 후보 목록에 유지.

**남은 삽질:** `flux2.py`의 fp8 분기(`quantization: fp8`)는 실제로는 `quant_backend="bitsandbytes_4bit"` + `bnb_4bit_quant_type: "nf4"`를 그대로 재사용하는 스텁이라 값과 무관하게 NF4가 적용됨 — 이번 라운드는 NF4가 더 강한 압축이라 fp8을 별도 구현하지 않고 보류. fp8이 필요해지면 torchao 설치 + `PipelineQuantizationConfig(quant_backend="torchao", ...)` 경로를 새로 붙여야 함.

## TASK-D · VRAM/latency 실측 테이블 (2026-07-27, 서버 157)

`scripts/bench_cost.py`로 확정 후보 3개(pixart-sigma, lumina2, flux2-klein-4b-nf4) +
FLUX.2-klein-4b 교란 제거용 2개 조건(distilled bf16, non-distilled/50-step bf16, 둘 다
양자화 없음)을 같은 방식(warmup 2장 버리고 10장 측정)으로 실측. 원본: `bench/cost/vram_latency.csv`.

| model | vram(torch/smi) GB | steps | p50_s | p90_s |
|---|---|---|---|---|
| flux2-klein-4b-nf4 | 7.8 / 8.16 | 4 | 11.35 | 12.11 |
| flux2-klein-4b (bf16) | 17.32 / 19.67 | 4 | 2.77 | 2.78 |
| flux2-klein-4b-base (bf16) | 17.33 / 19.67 | 50 | 63.0 | 63.32 |
| lumina2 | 12.28 / 14.9 | 30 | 29.48 | 29.54 |
| pixart-sigma | 14.46 / 16.54 | 20 | 5.8 | 5.85 |

- **위 "flux2-klein-4b 16GB 진입 시도" 절의 미해결 질문에 답함 — NF4 dequant 오버헤드가 실제 원인.**
  같은 distilled 체크포인트·같은 4-step에서 NF4가 bf16보다 **4.1배 느림**(11.35s vs 2.77s). 시드
  고정 육안 비교(`bench/cost_images/`, `a_cat` 예시) 결과 두 출력이 사실상 동일 — 품질 손해 없이
  순전히 속도만 손해. 다만 bf16은 VRAM 19.67GB로 위 절에서 이미 확인한 대로 16GB 예산을 넘으므로,
  **지금 예산에서는 NF4 유지가 맞다.** 예산이 ~20GB로 늘어나는 결정이 나오면 bf16으로 전환 검토.
- **pixart-sigma가 16GB 예산에 거의 다 참**: nvidia-smi 실측 16.54GB(torch 할당 14.46GB보다
  2GB 더 높음). 다른 프로세스가 같은 GPU를 쓰면 OOM 위험 — 실서빙 시 여유를 두고 잡을 것.
- **model_load_s는 이번 측정에서 신뢰 불가**: lumina2(1244s)/flux2-klein-4b-base(824s)/
  pixart-sigma(409s)는 첫 다운로드 포함으로 보이고 캐시돼 있던 나머지 두 조건(61.6s/12.14s)과
  조건이 다르다. warm-cache 로드 시간을 별도 재측정하기 전까지 모델 간 비교에 쓰지 말 것.

## v2 스타일 프리셋 R9 스모크 테스트 (2026-07-19)

`scripts/preset_smoke_test.sh`로 4개 프리셋(edu-flat-v2/observational/playful-soft/storybook-scene)을
lumina2 + r9-smoke3(apple/cat/book)로 생성, 육안 확인(`v223~v226_lumina2`).

- **leakage**: 4개 전부 없음 — "a book" 케이스 포함, 스타일 문구 명사가 객체로 새어나오는 현상 미관찰. R9 통과로 4개 전부 `status: validated` 처리.
- **별도 발견(R9 스코프 밖)**: `observational`, `storybook-scene` 두 프리셋은 교육용 프레젠테이션에 쓰기엔 스타일이 지나치게 고퀄리티/복잡하다는 지적. leakage 문제가 아니라 문구의 디테일/톤 설계 문제라 이번 스모크 테스트로는 막지 않고, 본 실험(VQAScore 등 채점)에 그대로 포함해서 결과로 판단하기로 함. 필요시 추후 문구 단순화 후 R9 재실행.

## TASK-C · judge 신뢰성 검증 — 2차 judge(Gemma-3-12B 4bit) 파일럿 (2026-07-27)

Qwen2.5-VL-7B(현재 judge)이 Qwen 계열 소스 프롬프트(qwen2.5-vl이 작성)나 Qwen-Image 평가 대상에
자기 계열 선호(self-enhancement bias)를 보이는지 확인하려고, 비-Qwen judge를 붙여 사람 손 채점
(v243 파일럿 3장, spec item 29건)과 각각 비교했다. `scripts/judge_agreement.py`로 전체 및
prompt_source(claude/chatgpt/qwen)별 Cohen's κ 계산.

| 비교 | 전체 n | 전체 일치율 | 전체 κ | claude κ | chatgpt κ | qwen κ |
|---|---|---|---|---|---|---|
| 사람 vs Qwen2.5-VL-7B (기존 judge) | 29 | 0.76 | 0.55 | 0.55 | 0.29 | 0.55 |
| 사람 vs Gemma-3-12B-4bit (신규 judge) | 29 | 0.66 | 0.31 | 0.17 | 0.40 | 0.17 |

**핵심 발견:**
- 두 judge 모두 κ<0.6 — TASK-C 검증 기준상 **둘 다 이 규모(파일럿 29건)에서는 신뢰할 수 없다.**
  spec item 채점 체계 자체(문구 애매함, yes/no 경계 판단) 또는 파일럿 표본 크기 문제일 수 있어,
  이 결론을 "어느 judge를 쓸지"의 근거로 쓰기 전에 표본을 늘려 재검증 필요(TASK-C의 "사람 손 채점
  30장 이상 확보" 기준에 이제 막 도달한 수준).
- **자기 계열 선호 가설은 이 파일럿에서 지지되지 않음**: Qwen judge가 qwen 소스에서 특별히 후한
  것도 아니고(claude와 동일 κ=0.55), Gemma-3도 qwen 소스에서 특별히 나쁜 것도 아님(claude와
  동일 κ=0.17). 오히려 두 judge 모두 **chatgpt 소스에서 claude/qwen 소스와 다른 방향으로
  치우침**(Qwen judge: chatgpt가 가장 낮음/0.29, Gemma-3: chatgpt가 가장 높음/0.40) — 이는
  계열 편향보다 chatgpt 소스 spec item 문구의 모호성 문제일 가능성을 시사(`bench/results.md`
  위쪽 "ChatGPT 소스 spec item은 기준이 모호할 수 있음" 계열 관찰과 연결지어 재확인 필요).
- Gemma-3-12B-4bit(`unsloth/gemma-3-12b-it-bnb-4bit`) VRAM 실측: 7.57GB peak(3장 기준) — 16GB
  예산에 충분히 들어간다.

**인프라 메모**: Gemma-3 계열 체크포인트가 transformers 내부적으로 `torch>=2.6`을 요구해서
기존 `t2i-judge`(torch 2.5.1 고정, Qwen2.5-VL 작동 버전) env를 건드리지 않고 `t2i-judge2`
(torch 2.6.0+cu124)를 새로 만들어 분리했다 — 자세한 내용/설치 명령은 `envs/README.md` 참고.

**다음 단계**: 사람 손 채점을 30장 이상으로 늘려 재검증하기 전까지는 두 judge 결과 모두
"참고용"으로만 쓰고, spec item 채점 결과를 모델 비교의 최종 근거로 확정하지 말 것.

## TASK-C · judge 신뢰성 검증 — STAGE 3 규모 재검증 (2026-07-27, 서버 23, 125건)

위 파일럿(29건)의 "사람 손 채점을 30장 이상으로 늘려 재검증" 지시에 따라, TASK-B2 STAGE 3
손 라벨링(v246/v247/v249, 125건)과 같은 표본으로 Gemma-3-12B-4bit를 재실행.
`scripts/sweeps/stage3_gemma3_judge.sh`.

| 비교 | n | 일치율 | 전체 κ | claude κ | chatgpt κ | qwen κ |
|---|---|---|---|---|---|---|
| 사람 vs Qwen2.5-VL-7B (TASK-B2 STAGE 3) | 125 | 0.74 | 0.37 | 0.41 | 0.39 | 0.33 |
| 사람 vs Gemma-3-12B-4bit | 125 | 0.67 | **0.19** | 0.34 | -0.04 | 0.22 |
| Qwen2.5-VL-7B vs Gemma-3-12B-4bit | 588 | 0.83 | **0.35** | 0.35 | 0.20 | 0.47 |

**핵심 발견:**
- 표본을 29건→125건으로 4배 이상 늘려도 **세 비교 전부 κ<0.6** — 파일럿의 "신뢰 불가" 결론이
  표본 크기 문제가 아니었음이 확정됨. spec item VLM 채점은 judge 모델을 바꿔도, 표본을
  늘려도 사람 라벨과 충분히 일치하지 않는다.
- **자기 계열 선호 가설, STAGE 3 규모에서도 지지되지 않음**: qwen 소스 프롬프트에서 Qwen judge가
  더 후하거나 Gemma-3가 더 박한 패턴이 없고, 오히려 Qwen vs Gemma-3 교차비교에서 qwen 소스가
  가장 일치율이 높음(κ=0.47, 세 소스 중 최고). 두 judge가 서로 잘 맞는 소스가 자기 계열
  소스라는 게 아니라 — 그냥 chatgpt 소스가 유독 안 맞는다.
- **chatgpt 소스 문제가 표본 확대 후 더 뚜렷해짐**: 사람 vs Gemma-3 비교에서 chatgpt 소스
  κ=-0.04(무작위보다 나쁨). 파일럿 때부터 있던 패턴(위 파일럿 표에서도 chatgpt가 유독 갈림)이
  표본이 커지자 방향이 뒤집히지 않고 더 악화됨 — judge 문제가 아니라 **chatgpt 소스 spec item
  문구 자체의 모호성**이 원인일 가능성이 높다는 쪽으로 결론이 기움.
- 결과: `bench/scores/stage3_auto_gemma3_v2.csv`,
  `bench/scores/stage3_disagreement_manual_vs_gemma3_v2.csv`(사람 vs Gemma-3 불일치 41건),
  `bench/scores/stage3_disagreement_qwen_vs_gemma3_v2.csv`(Qwen vs Gemma-3 불일치 102건).

**다음 단계**: judge 모델 교체로는 해결되지 않는 문제로 결론. spec item 채점을 모델 비교의
주 근거로 계속 쓸지, VQAScore/CSD 등 다른 지표로 무게중심을 옮길지 프로젝트 차원의 결정
필요(`NextJob.md` TASK-C/TASK-E 섹션 참고, 아직 미결정).

## TASK-E · 리라이팅 3조건 실제 생성 (2026-07-27, 서버 157, flux2-klein-4b-nf4)

`scripts/sweeps/rewrite_generate_flux2klein.sh`로 리라이팅 3백엔드(passthrough/wan_style/
promptenhancer) × 24프롬프트를 bench_v1 종합 1위 후보 flux2-klein-4b-nf4로 실제 생성.

| backend | 버전 | vram_peak | sec/img |
|---|---|---|---|
| passthrough (대조군) | v250 | 7.8GB | 10.92 |
| wan_style | v251 | 7.8GB | 10.72 |
| promptenhancer | v252 | 7.8GB | 10.10 |

- 72장(3조건×24) 생성 완료, VRAM/속도 조건 간 차이는 미미(±1s/img 이내).
- 원래 계획한 최종 판정 기준(spec 통과율)이 같은 세션의 TASK-B2/TASK-C 결과(κ<0.6 확정)로
  근거가 흔들림 — 채점 방법론 결정 전까지는 이 3조건 이미지에 대한 spec 채점을 최종 판정으로
  쓰지 말 것.

## TASK-A · 통계 검정 — 새 baseline(v246/v247/v249) 재실행 (2026-07-28, 서버 23)

프롬프트 드리프트로 v243/v244/v245가 무효화되고 v246(pixart-sigma)/v247(flux2-klein-4b-nf4)/
v249(qwen-image)로 재생성된 뒤, 이 baseline에 대해 vqascore/custom_cv/csd_target 채점이
한 번도 실행되지 않은 상태였음(spec item 채점만 있었음) — 이번에 처음부터 재실행.

**서버 인프라 이슈(재현 시 참고)**:
- `t2i-score` env가 서버 23에서 지워져 있었음 — `envs/t2i-score.txt`로 재생성 필요.
  디스크가 1.8GB만 남아있어 t2i-rewrite 백엔드용 `Qwen2.5-7B-Instruct` HF 캐시(15G, 이미 삭제된
  env 소속이라 재사용 안 됨)를 삭제해 공간 확보(사용자 승인 후 진행).
- `torch==2.5.1+cu121` 같은 로컬 버전 지정은 PyPI가 아니라 `--index-url
  https://download.pytorch.org/whl/cu121`로 따로 설치해야 함 — freeze 파일 그대로 `pip install -r`
  하면 실패.
- `t2v_metrics==3.0`은 import 시점에 안 쓰는 백엔드(InternVideo2 등)까지 전부 끌어와 `flash_attn`
  미설치로 깨짐 — `envs/README.md`/`envs/fix_t2v_metrics.sh`에 있던 우회가 이번에도 필요했음
  (site-packages의 `clipscore_models`/`itmscore_models` `__init__.py`에서 해당 import를
  try/except로 감쌈). ffmpeg 시스템 패키지, `llava`(pip 미공개, `pip install
  git+https://github.com/LLaVA-VL/LLaVA-NeXT.git`)도 새로 설치 필요.
- CSD 채점은 `PYTHONPATH=vendor` 필수(README "채점 모듈" 절에 명시돼 있었으나 처음에 누락해 1회
  실패) + `refs/lecture24/vlm-target/*.png`가 `.gitignore`로 제외돼 있어 로컬→서버 직접 scp 필요.

**결과** (`reports/stats_lecture24_v2/`, n=24 paired):

| metric | mean: pixart-sigma | mean: flux2-klein-4b-nf4 | mean: qwen-image |
|---|---|---|---|
| vqascore | 0.7692 | 0.8323 | 0.8701 |
| custom_cv | 0.7089 | 0.7335 | 0.7692 |
| csd_target | 0.5307 | 0.6302 | 0.6319 |

Wilcoxon signed-rank (모든 쌍 유의):
- vqascore: 세 쌍 전부 p<0.01 (pixart-sigma가 가장 낮고, qwen-image가 가장 높음 — effect r=0.57~0.81로 큰 편)
- csd_target: pixart-sigma가 flux2-klein-4b-nf4/qwen-image보다 유의하게 낮음(p<0.01, r≈0.53~0.56).
  flux2-klein-4b-nf4 vs qwen-image는 유의하지 않음(p=0.73, r=0.07) — 둘은 csd_target 기준 사실상 동급.

judge_lecture24.csv(4축 pass/fail) 기반 통계(pass rate/Fisher)는 이번 baseline에 대해 한 번도
생성된 적이 없어(스펙아이템 judge로 대체된 뒤 폐기된 경로로 보임) 스킵 — `scripts/stats_report.py`가
해당 파일 부재 시 경고만 찍고 넘어가도록 수정함. 필요하면 TASK-C에서 이미 신뢰성 낮다고 결론난
judge 시스템을 다시 붙이는 것보다, vqascore/csd_target 같은 연속형 지표를 주 근거로 쓰는 쪽이
합리적.

## TASK-F · Qwen-Image-Lightning 파일럿 (2026-07-28, 서버 157)

`configs/models/qwen-image-lightning.yaml` 신규 — `OzzyGT/qwen-image-lighting-gguf`(8-step
Lightning LoRA가 이미 fuse된 비공식 GGUF, Q4_K_S 11.5GB)를 기존 `generic.py`의 `gguf_repo`
경로 그대로 사용(어댑터 코드 변경 없음 — LoRA를 diffusers `load_lora_weights`로 GGUF 양자화
transformer 위에 얹는 공식 경로는 호환성 문제가 보고돼 있어, 대신 LoRA가 이미 병합된 GGUF를 선택).

동일 시드(0)·동일 프롬프트(apple/cat, `educational-flat-v2-check` exp) 파일럿 비교(v253 vs v254):

| | Lightning (8-step) | full qwen-image (30-step) |
|---|---|---|
| vram_peak | 15.56GB | 15.56GB |
| sec/img | 97.05 | 207.18 |

- 체크포인트 검증 기준 통과: 같은 시드에서 Lightning은 회갈색 톤의 다른 구도, full은 표준 빨간
  사과로 육안상 명백히 다른 이미지 — 랜덤 초기화나 잘못된 로드가 아니라 체크포인트가 실제로 적용됨.
  다만 색감이 원본과 크게 다른 점은 8-step distillation의 대가일 수 있어 24프롬프트 전체 스펙
  채점 시 확인 필요.
- 속도는 약 2.1배 향상(step 수는 30→8, 3.75배 감소했지만 텍스트 인코딩 등 고정 오버헤드가
  전체의 상당 부분이라 배수만큼 안 줄어듦). VRAM은 동일(같은 아키텍처 계열, 양자화 레벨만 다름).
- 다음 단계(TASK-F 본문 2~4번, 아직 미실행): `bench_cost.py`로 정식 VRAM/latency 측정, 동일 24
  프롬프트 생성 후 spec+CSD 채점, quality/latency/VRAM 3열 비교표.

## TASK-F · qwen-image vs qwen-image-lightning 정식 24프롬프트 비교 (2026-07-28~29, 서버 157/23)

`scripts/sweeps/task_f_qwen_pipeline.sh`로 동일 24프롬프트(lecture24)·동일 시드 정식 생성
(v255=full 30-step Q5_K_M, v256=lightning 8-step Q4_K_S, 서버 157) → VQAScore/csd_target 채점
(서버 23) → `reports/task-f_qwen_lightning_comparison.md`.

| 항목 | qwen-image (full, 30-step, Q5_K_M) | qwen-image-lightning (8-step, Q4_K_S) |
|---|---|---|
| peak VRAM (torch/smi) | 15.53 / 16.04 GB | 15.53 / 16.05 GB |
| latency p50 / p90 | 152.15s / 153.62s | 50.44s / 51.27s |
| vqascore (mean, 24) | 0.8701 | **0.8784** |
| csd_target (mean, 24) | 0.6319 | **0.6421** |

- **품질 저하 없음** — vqascore·csd_target 둘 다 lightning이 오히려 근소하게 높다(둘 다
  n=24, 시드 1개라 유의차 검정은 안 했지만 최소한 "distillation으로 품질이 깎였다"는 우려는
  기각). VRAM은 사실상 동일(양쪽 다 nvidia-smi 기준 16GB 예산을 근소 초과), 속도는 약 3배 —
  파일럿(2.1배, apple/cat 2장)보다 정식 측정에서 격차가 더 벌어졌는데, 24프롬프트 규모에서
  텍스트 인코딩 등 고정 오버헤드 비중이 상대적으로 줄어든 것으로 보임.
- **결론**: qwen-image 계열을 후보로 유지한다면 lightning으로 교체하는 데 품질상의 이유로
  막을 근거가 없다. VRAM이 16GB를 근소 초과하는 문제는 full/lightning 공통이라 이 비교와는
  별개 이슈.

## TASK-E · 리라이팅 3백엔드 4지표 채점 (2026-07-28, 서버 23)

`scripts/rewrite_compare_v250_252.sh`로 v250(passthrough)/v251(wan_style)/v252(promptenhancer)
72장(flux2-klein-4b-nf4, 동일 시드)에 VQAScore/custom_cv/csd_target/VLM-judge(InternVL3-8B,
lecture24 4축) 전부 채점. 결과 리포트: `reports/rewrite-v250-v251-v252-comparison/index.html`.

| backend | 버전 | VQAScore | custom_cv | csd_target |
|---|---|---|---|---|
| passthrough (대조군) | v250 | 0.832 | 0.733 | 0.630 |
| wan_style | v251 | **0.902** | 0.734 | 0.620 |
| promptenhancer | v252 | 0.829 | **0.750** | **0.659** |

- 네 지표를 동시에 1등 하는 백엔드 없음 — wan_style은 VQAScore·judge(content/layout/edu 축)에서,
  promptenhancer는 csd_target·custom_cv에서 각각 우세. passthrough(리라이팅 없음)도 큰 격차 없이
  따라붙음.
- judge_lecture24 결과는 참고용(TASK-C에서 이미 κ<0.6 확정) — 이 비교의 최종 판정 근거로 쓰지
  않음. 리포트에 사람 눈 채점 대기용 72행 표를 미리 마련해둠(로컬 이미지 준비 완료,
  `image-prompts/v25{0,1,2}_flux2-klein-4b-nf4-lecture24/images/`).
- **채점 중 발견한 문제**: 서버 23의 disk 여유 확보를 위한 것으로 보이는 외부 프로세스가 v250/v251
  이미지 디렉토리를 스코어링 도중 삭제해, 첫 pass1/csd_target 실행이 조용히 0건으로 기록됨(에러 없이
  통과) — 생성 서버(157)에서 이미지를 재복사해 재채점으로 수정. 앞으로 이런 스크립트에는 0건 결과를
  실패로 간주하는 가드를 추가하는 게 안전.

**다음 단계**: 사람 눈 채점(리포트의 72행 표) 완료 후 VLM-judge와 비교, 최종 백엔드 채택 여부 결정.

## TASK-E · 리라이팅 시스템 프롬프트 개량(공식 레포 구조 정합) 4지표 채점 (2026-07-29, 서버 157/23)

`configs/rewrite/wan_style_cn.txt`/`promptenhancer_cn.txt` — 기존 `wan_style.txt`/`promptenhancer.txt`보다
공식 레포(Wan2.2 `prompt_extend.py`, Tencent PromptEnhancer-7B) 원본 시스템 프롬프트 구조에 더 가깝게
개량한 버전. v251(wan_style)/v252(promptenhancer)를 대체하는 새 baseline 후보로 동일 파이프라인 재실행:

1. `scripts/rewrite.py --backend {wan_style,promptenhancer} --system-prompt configs/rewrite/{wan_style_cn,promptenhancer_cn}.txt` →
   `image-prompts/rewrite/{wan_style_cn,promptenhancer_cn}.json` (서버 23, `t2i-rewrite`)
2. `scripts/sweeps/rewrite_generate_flux2klein_cn.sh` → flux2-klein-4b-nf4, 24프롬프트×2조건 생성
   (서버 157) → v261(wan_style_cn)/v262(promptenhancer_cn)
3. `scripts/rewrite_compare_v261_262.sh` → VQAScore/custom_cv/csd_target/VLM-judge 채점 (서버 23)

| backend | 버전 | VQAScore | custom_cv | csd_target | photo-word 검출 |
|---|---|---|---|---|---|
| wan_style (기존) | v251 | **0.902** | 0.734 | 0.620 | 0 |
| wan_style_cn (신규) | v261 | 0.887 | **0.750** | **0.639** | 0 |
| promptenhancer (기존) | v252 | 0.829 | 0.750 | **0.659** | 7 |
| promptenhancer_cn (신규) | v262 | **0.876** | 0.751 | 0.654 | **0** |

judge_lecture24(InternVL3-8B, 참고용 — κ<0.6, 최종 판정 근거 아님) overall pass율(96문항=24×4축):
passthrough(v250) 62/96, wan_style(v251) 66/96, **wan_style_cn(v261) 68/96**,
promptenhancer(v252) 65/96, promptenhancer_cn(v262) 64/96. 축별로는 네 조건 모두 `text_legibility`가
2~3/24로 압도적으로 낮음(공통 약점, 조건 간 차이 아님).

- **promptenhancer_cn이 가장 뚜렷한 개선**: VQAScore 0.829→0.876, photo-word 누출 7건→0건. 시스템
  프롬프트를 공식 구조에 맞게 재작성한 것만으로 기존 promptenhancer의 핵심 실패 모드(사진/영상 어휘
  누출)가 해소됨.
- wan_style_cn은 VQAScore가 기존보다 소폭 낮아졌지만(0.902→0.887) custom_cv/csd_target/judge
  pass율은 전부 개선 — 두 시스템 프롬프트 모두 새 baseline 후보로 볼 근거 있음.
- 서버 23 디스크 90%(9.8GB 여유) 상태에서 wan_style_cn용 Qwen2.5-7B-Instruct(~15GB) 신규 다운로드가
  필요해, 대응 env가 없는 orphan 캐시 `gemma-3-12b-it-bnb-4bit`(7.3GB)를 사용자 승인 하에 삭제해
  공간 확보. 이후 채점 중 디스크가 다시 98%(2.9GB)까지 참 — 이 Qwen 캐시는 wan_style(_cn) 리라이팅에
  계속 필요하므로 유지, 대신 앞으로 서버 23에서 큰 모델을 추가할 때는 이 캐시까지 감안해 여유를
  더 타이트하게 관리해야 함.

**다음 단계**: v250~v252/v261/v262를 한 리포트에서 나란히 비교(passthrough 대조군 포함), 사람 눈 채점
완료 후 최종 baseline(_cn 버전 채택 여부) 확정.

## TASK-G · ideogram-4 리라이팅/캡션포맷 4조건 생성 + 채점 (2026-07-28~29, 서버 157/23)

`scripts/sweeps/rewrite_generate_ideogram4.sh`로 passthrough(v257)/wan_style(v258)/
promptenhancer(v259)/ideogram_guide(v260) 4조건 × 24프롬프트를 ideogram-4-nf4(48-step)로 생성
완료(서버 157, sec/img 160~173, vram_peak 19.1~19.2GB). `scripts/rewrite_compare_ideogram4.sh`로
VQAScore/custom_cv/csd_target/VLM-judge(InternVL3-8B, lecture24 4축) 채점 완료(서버 23). 결과
리포트: `reports/rewrite-ideogram4-comparison/index.html`.

**중요한 confound**: 앞 3조건은 순수 텍스트를 `_to_caption_json`이 naive JSON 하나의 `obj`
요소로 감싼 것이고, ideogram_guide는 공식 스키마(`style_description` + `type:"text"` 요소 포함)를
사람이 직접 작성한 캡션이다(TASK-G 설계 §696). 즉 이 비교는 "리라이팅 품질"과 "캡션 포맷"이
뒤섞여 있어 4-way 순위표가 아니라 참고 수치로 읽어야 한다.

| backend | 버전 | VQAScore | custom_cv | csd_target |
|---|---|---|---|---|
| passthrough (대조군) | v257 | 0.8241 | 0.7735 | 0.4212 |
| wan_style | v258 | 0.8699 | 0.7691 | 0.4212 |
| promptenhancer | v259 | 0.8461 | 0.7529 | **0.4974** |
| ideogram_guide | v260 | **0.8706** | **0.8110** | 0.2201 |

- VQAScore·custom_cv는 ideogram_guide가 최고, csd_target(스타일 유사도)은 promptenhancer가
  최고이고 **ideogram_guide가 csd_target에서 뚜렷하게 최저**(0.22 vs 나머지 0.42~0.50) — 앞의
  TASK-E(flux2-klein) 결과와 달리 여기서는 한 조건이 지표 간 방향이 완전히 갈린다.
- judge_lecture24(참고용, TASK-B2/TASK-C에서 이미 κ<0.6 확정): ideogram_guide는
  content_present pass율 45.5%(n=11/24, na=13)로 나머지 세 조건(80~100%)보다 뚜렷이 낮고,
  text_legibility는 24개 전부 n/a — `type:"text"` 요소를 명시적으로 추가했음에도 judge가 텍스트
  관련 판정을 시도한 이미지가 0건.
- 채점 전 그레이스케일 표준편차 스크리닝: 96장 전부 std>8로 완전 단색/차단화면(block)은 없음.
  다만 ideogram_guide 평균 std(17.5)가 나머지 세 조건(36.4~43.6)보다 뚜렷이 낮아 — 시각적으로
  더 단조로운(flat) 이미지 경향이며, csd_target·judge content_present 저하와 방향이 일치한다.
- **[Inference]** 세 신호(csd_target 저하, judge content_present 저하, std 저하)가 전부
  ideogram_guide에서 동시에 나타나므로, 손으로 쓴 구조화 캡션이 원본 VLM 캡션 소스 이미지와의
  스타일/내용 일치도 양쪽에서 다른 세 조건과 다른(더 단순화된) 이미지를 만들고 있을 가능성이
  높다. 다만 n=24, 시드 1개라 통계 검정 없이 "악화"라고 단정할 수 없다.
- 텍스트 렌더링 성공 여부(TASK-G 원래 목적)는 자동 지표로 답할 수 없는 질문 — 리포트의
  Structured Worksheet Template / Data Visualization Chart / Labeled Science Diagram 카테고리에서
  ideogram_guide 열을 육안으로 확인 필요(OCR 자동화는 이미 폐기 결정, 재도입 안 함).

**다음 단계**: 리포트를 열어 텍스트/라벨이 필요한 카테고리의 ideogram_guide 열을 육안 판정 —
공식 스키마 캡션이 실제로 글자를 더 잘 그리는지가 TASK-G의 핵심 질문이었고, 자동 지표만으로는
결론이 나지 않음(오히려 스타일 유사도·judge 판정은 guide가 불리하게 나옴).
