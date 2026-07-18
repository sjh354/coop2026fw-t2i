# 스타일 프리셋 v2 설계 문서

t2i-lab · K-12 교사용 삽화 파이프라인 · 2026-07-17

전제:
- diagram30/formula30은 raster T2I 트랙에서 이관 완료 → 해당 프리셋 4개는 본 체계에서 제외.
- 스타일은 콘텐츠와 직교한다. "역사적 분위기" 같은 내용 요소는 rewriter 출력(content prompt)이 담당하고, 프리셋은 시각 언어만 기술한다.
- 모든 v2 문안은 §3 authoring rules를 통과해야 한다.

---

## 1. 통합안 (승인됨)

12개 → **4개 + 보류 1개**.

| # | v2 프리셋 | 목적 | 학년군 | 대상 카테고리 | 흡수·폐기 |
|---|---|---|---|---|---|
| 1 | `edu-flat-v2` | 개념 전달용 플랫 벡터. 단일 피사체·개념 은유. 슬라이드 기본값 | 전 학년 | 사물 단독, 개념 은유, 자연 관찰(단순) | `educational-flat`(fork), `history-flat` 흡수 |
| 2 | `playful-soft` | 저학년 친근함. 무외곽선·뮤트 파스텔·둥근 형태 | 초저·초고 | 사물 단독, 감정/사회 상황(저학년) | `flat-illust` 기반 승격, `coloring-book` 폐기 |
| 3 | `storybook-scene` | 다객체 장면 묘사. 인물·배경 포함 | 초고·중 | 인물/장면(역사·문학), 감정/사회 상황 | `history-storybook` 흡수 |
| 4 | `observational` | 고학년 과학 관찰용 준사실 묘사 | 중·고 | 자연/과학 관찰(동식물, 천체, 구조) | 신설 (realistic 계열 기존 프리셋 있으면 여기로) |
| 보류 | `mono-minimal` | 비수식 개념도의 raster 잔여 수요 확인 후 추가 | 중·고 | 개념 은유, 단순 구조도 | `diagram-clean` 잔여분 |
| 폐기/이관 | — | — | — | — | `diagram-whiteboard`, `formula-print`, `formula-chalkboard` → LaTeX/matplotlib 트랙 |

`coloring-book` 폐기 근거: #1이 얇은 외곽선·crisp 방향을 점유하므로 #2는 반대 방향(무외곽선·소프트)일 때 커버리지가 넓다. 굵은 균일 외곽선은 SDXL 파일럿에서 style collapse에 취약했다. 벤치마크 대조군으로서의 가치는 archive에 YAML만 남겨 보존한다(운영 대상 아님).

---

## 2. 시각 언어 정의

### 2.1 edu-flat-v2

| 축 | 정의 |
|---|---|
| 선 | 얇고 균일한 외곽선(닫힌 윤곽). 선 두께 변화 없음 |
| 색 | 제한된 플랫 팔레트 4~6색. 중채도, 원색 지양 |
| 형태 | 강한 기하학적 단순화. 실루엣 판독성 최우선 |
| 음영 | 완전 플랫. 그라데이션·음영 일절 없음 |
| 배경 | 무배경(단색 밝은 배경), 피사체 중앙 배치 |
| 금지 | 그라데이션, 소프트 셰이딩, 드롭 섀도, 질감, 사실적 묘사, 화면 내 텍스트 |

### 2.2 playful-soft

| 축 | 정의 |
|---|---|
| 선 | 무외곽선 또는 극세선. 색 경계로 형태 구분 |
| 색 | 뮤트 파스텔. 저~중채도, 따뜻한 톤 우세 |
| 형태 | 둥근 유기적 단순화. 뾰족한 모서리 없음 |
| 음영 | 2톤 컬러 블로킹까지만 허용(같은 색상의 명도 2단계). 연속 그라데이션 금지 |
| 배경 | 단색 밝은 배경 + 넉넉한 여백 |
| 금지 | 굵은 검은 외곽선, 고채도·네온, 강한 대비, 복잡한 배경, 질감, 화면 내 텍스트 |

### 2.3 storybook-scene

| 축 | 정의 |
|---|---|
| 선 | 부드러운 세선 또는 무외곽선 혼용. 손그림 느낌의 약간의 선 강약 허용 |
| 색 | 따뜻한 확장 팔레트(8~12색). 중채도, 장면 전체의 색 조화 우선 |
| 형태 | 중간 단순화. 인물은 단순한 이목구비, 배경은 형태 암시 수준 |
| 음영 | 약한 소프트 셰이딩·은은한 색 워시 허용. 강한 명암 대비 금지 |
| 배경 | 배경 포함이 기본. 전경-배경 위계 명확, 배경은 채도·디테일을 낮춤 |
| 금지 | 사실적 인물 묘사, 강한 그림자, 어두운 분위기, 화면 내 텍스트, 과밀 구성 |

### 2.4 observational

| 축 | 정의 |
|---|---|
| 선 | 가늘고 정밀한 선. 구조 경계 명확, 스케치풍 러프선 금지 |
| 색 | 자연색 기반 뮤트 팔레트. 대상 고유색 충실, 저~중채도 |
| 형태 | 단순화 최소. 비례·구조·부위 형태 정확성 우선 |
| 음영 | 절제된 소프트 셰이딩으로 입체감만 부여. 드라마틱한 조명 금지 |
| 배경 | 무배경(밝은 중성색). 대상 단독, 필요시 부위 확대 병치 가능 |
| 금지 | 만화적 과장, 의인화, 데포르메, 강한 스타일화, 화면 내 텍스트, 배경 장면 |

---

## 3. Style→Object Leakage 방지 Authoring Rules

배경: LLM 기반 텍스트 인코더(qwen-image, lumina2 등)는 스타일 서술 내 구체 명사를 장면 객체로 해석한다. 확인 사례: "textbook infographic style" → 책 객체 렌더링.

### 체크리스트 (모든 style 문안이 통과해야 함)

- [ ] **R1. 등장 가능 명사 금지** — 화면에 물체로 그릴 수 있는 가산명사를 쓰지 않는다. (금지 예: book, textbook, crayon, chalkboard, sticker, poster, paper, canvas, slide, card, magazine, toy)
- [ ] **R2. 매체·도구 → 시각 결과 치환** — 재료/도구 명사는 그것이 만드는 시각적 결과를 형용사구로 서술한다. (crayon texture → soft grainy strokes / watercolor → translucent soft color washes / chalk → dusty matte strokes)
- [ ] **R3. 장르명 내장 명사 검사** — 장르 관용구에 숨은 객체 명사를 찾는다. (storybook illustration → 'book' 내장, 위험 / infographic → 차트 포스터로 객체화 가능 / picture-book, field guide, encyclopedia 동일)
- [ ] **R4. 단독 렌더링 자문** — 각 명사에 대해 "이 단어 하나만 프롬프트로 넣으면 무엇이 그려지는가?"를 자문한다. 물체가 그려지면 교체한다.
- [ ] **R5. 메타 명사 화이트리스트** — 허용 명사는 화면 요소를 지시하는 메타 어휘로 한정: illustration, style, rendering, palette, color, outline, line, shape, form, silhouette, composition, background, subject, shading, contrast, space, strokes.
- [ ] **R6. 본문은 긍정 서술 우선** — "no X" 부정 구문은 X 토큰을 본문에 노출시킨다. 배제 대상은 negative 필드로 옮기고, 본문에는 원하는 상태를 긍정형으로 쓴다. (no gradient → completely flat color)
- [ ] **R7. negative 미지원 모델 가정** — 일부 모델(FLUX 계열 등)은 negative를 무시한다. style 본문 단독으로 스타일이 성립하는지 확인한다.
- [ ] **R8. 복합어 분해 검사** — 하이픈·복합 표현을 분해해 각 요소에 R1~R4를 적용한다. (infographic-style → infographic 검출)
- [ ] **R9. 스모크 테스트** — 신규/수정 문안은 LLM-인코더 모델 1개(lumina2 권장)로 basic30 중 3키워드 생성 후, 스타일 명사가 객체로 등장하는지 육안 확인. PNG metadata로 문안 버전 대조.

---

## 4. S/M/L 티어 문안 (v2)

티어 규격: S ≈ 10~15 토큰(핵심 정체성만), M ≈ 30~40(운영 기본값), L ≈ 60~75(속성 완전 기술). 모든 문안 R1~R8 통과. negative는 티어 공통.

```yaml
name: edu-flat-v2
keywords: basic30
seed: 0
tiers:
  S: >-
    flat vector illustration, limited flat colors, thin clean outline,
    plain light background
  M: >-
    flat educational vector illustration, limited flat color palette,
    crisp geometric shapes, thin clean outline of even width,
    clear readable silhouette, completely flat color fill,
    centered single subject on plain light background
  L: >-
    flat educational vector illustration, clean and simple visual language,
    limited flat color palette of four to six muted colors,
    crisp geometric shapes with strong simplification,
    thin clean outline of perfectly even width, closed contours,
    clear readable silhouette, completely flat color fill with no depth,
    generous empty space around the subject,
    centered single subject on plain light background
negative: >-
  photorealistic, 3d render, photograph, gradient, soft shading, drop shadow,
  heavy black outline, painterly, textured, busy background, cluttered,
  text, letters, watermark, signature, grainy, noisy
```

```yaml
name: playful-soft
keywords: basic30
seed: 0
tiers:
  S: >-
    soft flat illustration, muted pastel colors, rounded friendly forms,
    no outline
  M: >-
    soft flat vector illustration, muted pastel color palette,
    rounded organic forms with no sharp corners, no outline,
    gentle two-tone color blocking, warm and friendly mood,
    centered single subject on plain light background
  L: >-
    soft flat vector illustration in a modern editorial manner,
    muted pastel color palette with warm tones, low saturation,
    rounded organic forms with no sharp corners, no outline,
    shapes defined purely by color boundaries,
    gentle depth through two-tone color blocking only,
    plenty of negative space, warm friendly and approachable mood,
    centered single subject on plain light background
negative: >-
  photorealistic, 3d render, photograph, heavy black outline, thick ink lines,
  harsh contrast, neon colors, saturated, continuous gradient, busy background,
  cluttered, text, letters, watermark, signature, grainy, noisy, sketchy
```

```yaml
name: storybook-scene
keywords: basic30
seed: 0
tiers:
  S: >-
    warm narrative illustration, soft colors, gentle scene with background
  M: >-
    warm narrative illustration, soft harmonious color palette,
    simplified characters with friendly features, full scene composition
    with a softly rendered background, gentle color washes,
    delicate thin linework, cozy and inviting mood
  L: >-
    warm narrative illustration with a gentle hand-drawn feel,
    soft harmonious palette of eight to twelve medium-saturation colors,
    simplified characters with small friendly facial features,
    full scene composition with clear foreground and background separation,
    background rendered softer and less detailed than the subject,
    translucent soft color washes, subtle soft shading, no harsh shadows,
    delicate thin linework with slight natural variation,
    cozy inviting and light-hearted mood
negative: >-
  photorealistic, 3d render, photograph, harsh shadows, dark moody lighting,
  high contrast, realistic human faces, cluttered composition,
  text, letters, watermark, signature, grainy, noisy
```

```yaml
name: observational
keywords: basic30
seed: 0
tiers:
  S: >-
    accurate naturalistic illustration, precise fine linework,
    natural muted colors, plain background
  M: >-
    accurate naturalistic illustration for science learning,
    anatomically correct proportions and structure,
    precise fine linework with clear structural boundaries,
    natural muted color palette true to the subject,
    subtle soft shading for gentle volume,
    single subject on a plain light neutral background
  L: >-
    accurate naturalistic illustration for science learning,
    anatomically correct proportions, faithful structure and surface detail,
    precise fine controlled linework with clear structural boundaries,
    natural muted color palette true to the real subject, low saturation,
    subtle soft shading giving gentle volume without dramatic lighting,
    no stylization, no exaggeration, no anthropomorphism,
    single centered subject on a plain light neutral background,
    calm neutral scientific presentation
negative: >-
  cartoon, anime, cute, chibi, anthropomorphic, exaggerated features,
  heavy outline, flat sticker look, dramatic lighting, dark background,
  scene, landscape, text, letters, watermark, signature, grainy, noisy
```

문안 메모:
- edu-flat-v2에서 기존 v2의 "infographic-style rendering"을 제거했다(R3·R8 위반: infographic은 차트 포스터로 객체화 가능). "clean and simple visual language"로 대체.
- playful-soft에서 flat-illust 원문의 "presentation slide artwork" 제거(R1: slide는 등장 가능 객체).
- storybook-scene은 'storybook/book' 어휘를 전면 배제하고 "narrative illustration"으로 정체성을 표현.
- observational의 L 티어 "no stylization…" 3연속 부정은 R6 예외로 남겼다. 대응하는 긍정 표현("faithful", "true to the real subject")이 이미 본문에 있고, 부정 대상(stylization 등)이 객체 명사가 아니라 leakage 위험이 낮다. negative 미지원 모델 대비 이중 안전장치.

---

## 5. CSD ref_set 수집 기준

프리셋별 15~25장 권장. 공통 원칙: **피사체는 최대한 다양하게, 스타일은 균일하게** — CSD가 콘텐츠가 아닌 스타일을 채점하도록 피사체 분포를 벤치마크 키워드와 겹치지 않게 섞는다. 화면 내 텍스트 포함 이미지 제외.

### edu-flat-v2
- 플랫 벡터 아이콘/스팟 일러스트 계열. 얇은 균일 외곽선 + 완전 플랫 채색 + 무배경 3조건을 모두 만족하는 것만.
- 그라데이션·긴 그림자(long shadow)·질감이 조금이라도 있으면 제외.
- 피사체: 사물·동물·자연물 고르게. 아이콘 세트에서 가져올 경우 한 세트에서 5장 이상 가져오지 않기(세트 편향 방지).

### playful-soft
- 무외곽선 파스텔 플랫 일러스트. 모던 에디토리얼/앱 온보딩 일러스트 계열이 근접.
- 채도 높은 것, 검은 외곽선 있는 것, 연속 그라데이션 쓰는 것 제외. 2톤 컬러 블로킹까지만 허용.
- 둥근 형태 언어가 유지되는지 확인. 배경은 단색·여백 위주만.

### storybook-scene
- 그림책풍 장면 일러스트. 반드시 배경 포함 다객체 장면으로만 수집(단일 피사체 컷 제외 — edu-flat과의 스타일 거리 확보).
- 수채/구아슈풍 부드러운 워시 질감, 따뜻한 조화 팔레트. 어둡거나 고대비 극화풍 제외.
- 인물 포함 장면과 비인물 장면을 섞되 인물 비중 절반 이하로(CSD가 인물 존재 여부를 스타일로 오학습하는 것 방지).

### observational
- 과학 도감풍 자연물 세밀화(botanical/zoological illustration 계열). 무배경 단독 피사체.
- 라벨·지시선·텍스트가 인쇄된 도판 제외(텍스트 없는 원화만). 사진 제외.
- 동물·식물·광물·천체 등 분류군을 고르게. 판화풍 흑백 선화는 제외(채색 세밀화만 — 팔레트도 스타일 정의의 일부).

---

## 부록: 폐기 프리셋 처리

- `coloring-book`, `history-flat`, `history-storybook`, `educational-flat`(v1), `flat-illust`: `configs/experiments/archive/`로 이동. 기존 실험 노트 frontmatter가 참조하므로 삭제 금지.
- `diagram-*`, `formula-*`: LaTeX/matplotlib 트랙 리포 영역으로 이관. raster 프리셋 목록에서 제거.
- 미확인 잔여 프리셋(12개 중 목록 미제출분)이 있으면 위 매핑 규칙(목적 기준)으로 4개 중 하나에 흡수 또는 archive.
