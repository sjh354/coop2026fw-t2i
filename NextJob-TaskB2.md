# TASK-B2 · VLM judge 관대성 편향 제거 (컨텍스트 없는 코딩 에이전트용)

> 선행: TASK-B (spec item 채점 체계, `judge_spec.py` / `judge_spec_manual.py` / `compare_judge_spec.py`)
> 이 문서 전체를 그대로 에이전트에 붙여넣는다. `‹확인›` 경로만 미리 채울 것.

---

```
[배경]
t2i-lab은 교육용 일러스트를 생성하는 text-to-image 모델들을 비교 평가하는 프로젝트다.
생성 이미지를 spec item(원자적 yes/no 조건) 단위로 채점하는 VLM judge가 이미 있다.
judge 모델은 Qwen2.5-VL-7B-Instruct다.

직전 검증 결과:
- 사람 손 채점 27건 대비 VLM judge 일치율 0.67 (18/27)
- 불일치 9건이 **전부** VLM이 더 관대한 방향 (auto=yes / manual=no)
- 불일치는 count(개수 세기)·attribute(색상/속성 구분) 축에 집중
- spatial·text 축은 27건 전부 일치

즉 무작위 오차가 아니라 **축 특이적 체계 편향**이다. 프롬프트를 다듬어 고칠 문제가 아니라,
7B VLM이 정확한 개수 세기와 색상 구분을 못 하는 지각 한계로 보는 게 맞다.

[전략]
"judge를 더 똑똑하게 만든다"가 아니라 "측정 가능한 축은 judge에서 빼고 결정론적으로 잰다"로 간다.
  count / attribute (기하·구조 카테고리)  → OpenCV로 직접 측정
  count (인물 수, CV 불가)                → VLM 유지하되 yes/no를 추출형 질문으로 교체
  spatial / text / style                  → VLM 유지 (이미 일치하고 있음)

[GPU/환경]
Linux, RTX 3090 24GB. OpenCV, PaddleOCR 사용 가능. 새 대형 모델 도입 금지.
```

---

## STAGE 0 — 불일치 9건 triage (코드 최소, 반드시 먼저) ✅ 완료 (2026-07-27)

> **결과**: `scripts/triage_disagreement.py` 작성, 불일치 9건 전부 분류 완료 —
> `bench/scores/v243_pixart-sigma-lecture24/triage.csv` 참조.
>
> - A (judge 지각 오류) 5건 — s1 박스 개수 오세기(실제 7개인데 6개로 판정, claude/qwen 2건),
>   s4 핀 색상 구분 실패(갈색 핀 2개가 같은 색인데 "전부 다르다"고 판정, claude/chatgpt/qwen 3건)
> - B (spec 문구 모호) **4건** — s8 "outlines are thick and black" (claude/qwen, "thick" 기준 불명),
>   s8 "the background is white" (chatgpt, 안쪽 캔버스 vs 전체 이미지 배경 중 무엇을 볼지 불명),
>   s9 "spacing between elements looks balanced/even" (chatgpt, 본질적으로 주관적 미적 판단이라
>   객관적 정오 기준 자체가 없음)
> - C (사람 채점 오류) 0건
>
> **문서 전제와 다른 발견**: 원래 전략은 spatial/text/style 축은 "이미 일치하고 있으니 VLM 유지"였으나,
> 이번 9건 중 style 축(s8)이 attribute 축(s4)과 동률로 가장 많이 틀렸다(3건). spatial 축도 1건
> 걸렸다(chatgpt s9, 다만 이 항목은 원래 spatial이 아니라 사실상 주관적 미적 판단 문항). 즉
> "style은 이미 잘 맞는다"는 전제가 이 표본에서는 틀렸다 — style 문항 중 "thick"/"balanced" 같은
> 상대적·주관적 표현이 낀 항목만 틀렸고, 나머지 spatial/text 문항은 그대로 100% 일치했다. 축
> 자체의 문제가 아니라 **문항 문구가 상대적/주관적 형용사를 쓰는지**가 원인으로 보인다.
>
> **B≥3 게이트 발동 → 해소 완료.** 문서 규칙에 따라 B로 분류된 4개 항목
> (`structured_worksheet_template_claude/qwen`의 s8 "thick and black", `..._chatgpt`의 s8
> "background is white", s9 "balanced/even")의 spec 문구를 `configs/benchmarks/vlm-prompts-spec.json`에서
> 더 객관적으로 재작성(주관적 형용사 제거, 구체적 기준 명시)하고, server 23(`t2i-judge` env)에서
> `judge_spec.py` 재실행 + 사용자가 새 문구로 4건 재채점.
>
> - claude s8, qwen s8: auto=yes / manual=yes로 **일치** (재작성으로 해소됨)
> - chatgpt s8, s9: 여전히 **불일치** (auto=yes 또는 unclear / manual=no) — 원인은 문구 모호성이
>   아니라 chatgpt 소스 이미지 자체가 의도한 worksheet 구조(박스 6개 + 핀 6개)를 거의 그리지 못한
>   생성 실패작이라는 점. spec 문구를 더 고쳐도 해소되지 않는 별개 문제로 판단, 더 이상 문구를
>   건드리지 않음.
> - 재계산된 일치율: **18/27(0.67) → 20/27(0.74)**. 여전히 0.8 미만이나, B 게이트 조건("문구 고치고
>   재실행")은 충족했으므로 STAGE 1로 진행. 최신 CSV는 `bench/scores/v243_pixart-sigma-lecture24/
>   judge_spec_pilot.csv`, `judge_spec_manual.csv`에 반영됨.

```
[해야 할 일]
compare_judge_spec.py의 불일치 9건을 CSV로 뽑고, 각 건에 대해 원본 이미지 + spec item 문구 +
VLM 응답 + 사람 판정을 한 화면에 나란히 보여주는 최소 스크립트를 만든다.
  scripts/triage_disagreement.py  (인자 --compare, --images, --out)

각 건을 사람이 다음 3가지 중 하나로 분류해 CSV에 기록할 수 있게 한다:
  A. judge 지각 오류    — spec 문구는 명확한데 VLM이 잘못 봄
  B. spec 문구 모호      — 사람과 VLM이 서로 다른 기준을 적용 (예: "각 막대는 서로 다른 색"에서
                          비슷한 두 색조를 다르다고 볼지)
  C. 사람 채점 오류      — 사람이 틀림

[왜 필요한가]
B가 섞여 있으면 judge를 고쳐도 일치율이 안 오른다. spec 문구를 고쳐야 한다.
전체 설계를 바꾸기 전에 이 분포부터 확인한다.

[검증 기준]
9건 전부 분류될 것. B가 3건 이상이면 STAGE 1로 가기 전에 해당 spec item 문구를 먼저 고치고
judge_spec.py를 재실행해 일치율을 다시 잰다.

[하지 말 것]
- 분류를 자동화하지 마라. 사람이 9건 보는 데 10분이면 된다.
```

---

## STAGE 1 — yes/no를 추출형 질문으로 교체

```
[근거]
VLM-as-judge의 관대함은 상당 부분 yes/no 형식 자체의 acquiescence bias다.
정답을 문장 안에 노출한 채 동의를 구하면 모델은 동의하는 쪽으로 기운다.
질문에서 정답을 빼고 값을 추출하게 한 뒤 코드에서 비교하면 이 경로가 닫힌다.
오차가 남더라도 체계적 관대함이 무작위 오차로 바뀌는 것이 핵심이다.

[해야 할 일]
configs/benchmarks/vlm-prompts-spec.json ‹확인› 의 spec item 스키마에 필드 2개를 추가한다.

  {
    "id": "s1",
    "type": "count",
    "check": "exactly 6 bars are present",        // 기존, 사람 채점용으로 유지
    "probe": "How many separate vertical bars are in this image? Answer with a single integer only.",
    "expect": {"mode": "int_eq", "value": 6}
  }

  mode 종류는 4개만 만든다:
    int_eq        — 정수 일치
    set_eq        — 쉼표 구분 목록이 집합으로 일치 (색상 목록 등)
    contains      — 응답에 특정 문자열 포함
    yesno         — 기존 방식 (spatial/style 축 전용)

judge_spec.py에 --mode {yesno,probe} 인자를 추가한다.
  probe 모드: probe 질문을 던지고 응답 문자열을 파싱해 expect와 대조.
  파싱 실패 시 verdict=unparseable로 기록하고 절대 yes로 처리하지 마라.

[질문 작성 규칙 — 반드시 지킬 것]
- probe 문구에 정답 값을 넣지 마라. "6개가 맞나?"가 아니라 "몇 개인가?"다.
- 선택지를 제시하지 마라.
- "Answer with a single integer only" 같은 출력 형식 지시는 넣어라. 파싱을 위해 필요하다.
- 유도 표현("clearly", "obviously", "should be") 금지.

[검증 기준]
- 사람 손 채점 27건과 동일한 이미지·item에 대해 probe 모드를 돌려 일치율과 Cohen's κ를 둘 다 출력.
- 불일치의 방향 분포를 출력할 것. 관대 방향 비율이 여전히 0.8을 넘으면 편향이 안 잡힌 것이므로
  그 사실을 명시적으로 보고하고 STAGE 2로 넘어가라.
- unparseable 비율을 반드시 리포트에 포함. 10%를 넘으면 probe 문구를 고쳐야 한다.

[하지 말 것]
- 기존 yesno 경로를 삭제하지 마라. 두 모드를 나란히 비교해야 이 변경의 효과를 주장할 수 있다.
- 응답을 재질문하는 자동 재시도 루프를 만들지 마라. unparseable은 unparseable로 남긴다.
```

---

## STAGE 2 — count / attribute 축을 CV로 라우팅

```
[대상 범위]
구조·기하 카테고리에만 적용한다:
  Structured Worksheet Template (박스·핀 개수)
  Data Visualization Chart      (막대 개수, 막대 색상)
  Labeled Science Diagram       (내부 구조물 개수)
  Geometric Shape Set           (도형 개수, 도형별 변 개수)
인물 장면 카테고리(Historical Figure Portrait, Multi-Character Classroom Collaboration,
Intergenerational Indoor Scene, Single-Character Cutout)의 인물 수는 CV로 세지 마라.
STAGE 1의 probe 방식을 그대로 쓴다.

[해야 할 일]
scripts/measure_cv.py 신규. 인자 --images, --spec, --out.
spec item의 type이 count 또는 attribute이고 measurer 필드가 "cv"인 것만 처리한다.
(spec 스키마에 "measurer": "cv" | "vlm" 필드를 추가하고, 기본값은 "vlm")

구현은 다음 3개 측정기만 만든다. 그 이상 만들지 마라.

1. count_regions(img, min_area, aspect_range)
   이진화 → cv2.findContours → 면적·종횡비로 필터 → 개수 반환
   막대, 박스, 도형, 핀 개수에 공통으로 쓴다.

2. region_colors(img, contours)
   각 컨투어 내부의 중앙값 색을 HSV로 변환 → 고정 색이름 테이블에서 최근접 매핑
   → 좌→우 순서로 색이름 리스트 반환. attribute 축의 색상 목록 대조에 쓴다.

3. polygon_sides(contour)
   cv2.approxPolyDP(epsilon = 0.02 * arcLength) → 꼭짓점 수 반환
   원은 꼭짓점 수가 임계 이상이면 "circle"로 처리.

출력 CSV: prompt_id, item_id, type, measurer, measured_value, expected_value, verdict

[검증 기준 — 이게 가장 중요하다]
- CV 측정기도 사람 라벨 대비 검증해야 한다. 결정론적이라고 옳은 게 아니다.
  STAGE 0에서 쓴 것과 같은 이미지 집합에 대해 (CV vs 사람) 일치율과 κ를 출력하라.
- CV 일치율이 VLM 일치율보다 낮으면 그 축은 CV 라우팅을 취소하고 VLM으로 되돌린다.
  그 판정 결과를 리포트에 남길 것.
- 파일럿 3장은 컨투어를 원본 위에 그려 PNG로 저장하고 사람이 육안 확인한 뒤 전체 실행.

[하지 말 것]
- 객체 검출 모델(YOLO, SAM 등)을 도입하지 마라. 이 4개 카테고리는 배경이 흰색 단색이라
  단순 이진화로 충분하다.
- 임계값을 이미지마다 자동 튜닝하는 로직을 만들지 마라. 카테고리별 상수 하나면 된다.
- CV 결과와 VLM 결과를 하나의 점수로 합치지 마라. measurer 컬럼을 남겨 끝까지 구분한다.
```

---

## STAGE 3 — 라벨 확대 + 정식 신뢰도 지표

```
[근거]
n=27은 일치율 0.67의 95% 신뢰구간이 대략 [0.48, 0.82]다. 축별로 쪼개면 축당 6~8건이라
축별 결론은 아직 주장할 수 없다. 반면 불일치 9건이 전부 한 방향인 것은
무작위 가정 하에 확률 2 x 0.5^9 ≈ 0.004이므로 편향의 **존재**는 이미 확립됐다.
"편향은 확실하고 크기는 미추정"이 현재 정확한 상태다.

[해야 할 일]
1. judge_spec_manual.py로 손 채점을 축당 최소 25건, 총 100~150건으로 확대한다.
   샘플링은 축(type)별 층화 무작위. 모델별로도 고르게 섞을 것.
   같은 이미지를 두 번 채점하지 않도록 이미 채점된 id를 제외하는 기능을 추가하라.

2. scripts/judge_agreement.py 확장 (없으면 신규). 출력 항목:
   - 단순 일치율 + Wilson 95% CI
   - Cohen's κ  ← 불균형 분포에서 단순 일치율은 과대평가되므로 이게 주 지표
   - 불일치 방향 분포 + 부호검정 p값
   - type(count/attribute/spatial/text/style) x measurer(cv/vlm) 교차표로 위 전부를 쪼개서 출력
   - model별로도 쪼갤 것 ← judge가 특정 모델 출력에만 관대한지 확인

[검증 기준]
- κ < 0.6인 (type, measurer) 조합은 리포트에 "unvalidated"로 명시 표기하고,
  그 조합의 점수는 최종 모델 비교에서 제외하거나 별도 표로 분리한다.
- 확대 후에도 관대 편향이 남으면, 그 축의 pass rate는 상한(upper bound)으로만 해석한다고
  리포트에 명시할 것.

[하지 말 것]
- 라벨링 자체를 VLM으로 대체하지 마라. 앵커가 사람이어야 하는 이유가 이거다.
- κ가 낮다고 spec item을 사후에 삭제하지 마라. 낮은 채로 보고한다.
```

---

## STAGE 4 — (조건부) 외부 앵커 교차검증

```
[실행 조건]
STAGE 1~3을 마친 뒤에도 특정 축에서 κ < 0.6이고, 그 축이 결론에 필수적인 경우에만 한다.
그렇지 않으면 이 스테이지는 건너뛴다.

[해야 할 일]
judge_spec.py의 --judge-model 인자로 비-Qwen 계열 judge를 하나 붙인다.
  후보: InternVL3-8B, Gemma-3-12B 4bit. 16GB에 안 들어가면 실측 peak VRAM을 기록하고
  더 작은 모델로 내려가라.
같은 spec, 같은 이미지에 대해 세 채점자(사람 / Qwen judge / 대체 judge)의 κ를 삼각 비교한다.

[반드시 함께 볼 것]
prompt_source별로 쪼개서 κ를 출력하라. 프롬프트 일부를 Qwen2.5-VL이 작성했고
평가 대상 중 하나가 Qwen-Image이므로, Qwen 소스 프롬프트에서만 판정이 후한지가 핵심 질문이다.

[하지 말 것]
- 두 judge를 앙상블해 하나의 점수로 만들지 마라. 각각 따로 보고한다.
- 새 judge를 위해 기존 환경의 transformers 버전을 올리지 마라. 별도 venv를 쓴다.
- 이 스테이지를 STAGE 1~3보다 먼저 하지 마라. 형식 문제를 안 고친 채 judge만 바꾸면
  같은 편향이 새 모델에서 반복된다.
```

---

## 전체 완료 조건

```
1. STAGE 0의 9건 분류표가 존재한다.
2. yesno 모드와 probe 모드의 일치율·κ가 나란히 비교된 표가 있다.
3. CV 라우팅된 축 각각에 대해 (CV vs 사람) κ가 보고되어 있고,
   VLM보다 나쁜 축은 되돌려졌다.
4. 최종 채점 CSV에 measurer 컬럼이 남아 있어 어느 축이 무엇으로 측정됐는지 추적 가능하다.
5. κ < 0.6인 조합이 리포트에 unvalidated로 표기되어 있다.

전체 신규 코드는 triage_disagreement.py / measure_cv.py / judge_agreement.py 확장
세 개, 400줄 안쪽이다. 이보다 커지면 설계가 과하다.
```