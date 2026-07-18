# 모델 실측 기록

generate.py가 노트에 vram/latency를 자동 기록하므로, 여기엔 **결론과 삽질만** 적는다.
(숫자를 손으로 옮겨적지 말 것 — Streamlit Compare 탭이 표로 보여줌)

| 모델 | 3090에서 동작 | 16GB 가능? | 결론 | 삽질 메모 |
|---|---|---|---|---|
| pixart-sigma | ✅ | | | |
| sdxl | | | | |
| flux2-klein-4b | | | | |
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
