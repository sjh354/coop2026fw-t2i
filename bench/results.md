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
