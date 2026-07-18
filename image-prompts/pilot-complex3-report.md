# 방언 파일럿 결과 (educational-flat-v2-complex)


모델 5개, 키워드 3개, run 13개.


## 선정 키워드 + 사유

| 키워드 | 사유 |
|---|---|
| three apples in a basket | 수량(counting) 축 — 사과 정확히 3개 / 바구니 안에 위치 |
| a tree to the left of a house | 공간 관계(spatial) 축 — 나무가 집의 왼쪽에 위치 / 둘 다 온전한 형태 |
| a cat wearing a blue hat | 속성 결합(attribute binding) 축 — 모자가 파란색 / 고양이에게만 씌워짐(색 전이 없음) |

## 키워드 × 모델(shared|dialect) 그리드

### three apples in a basket

| 조건 | flux2-klein-4b | lumina2 | pixart-sigma | sd35-medium | zimage-turbo |
|---|---|---|---|---|---|
| shared | ![[v203_00_three_apples_in_a_basket.png]] | ![[v211_00_three_apples_in_a_basket.png]] | ![[v205_00_three_apples_in_a_basket.png]] | ![[v207_00_three_apples_in_a_basket.png]] | ![[v214_00_three_apples_in_a_basket.png]] |
| dialect | ![[v204_00_three_apples_in_a_basket.png]] | ![[v212_00_three_apples_in_a_basket.png]] | ![[v206_00_three_apples_in_a_basket.png]] | ![[v208_00_three_apples_in_a_basket.png]] | ![[v215_00_three_apples_in_a_basket.png]] |

### a tree to the left of a house

| 조건 | flux2-klein-4b | lumina2 | pixart-sigma | sd35-medium | zimage-turbo |
|---|---|---|---|---|---|
| shared | ![[v203_01_a_tree_to_the_left_of_a_house.png]] | ![[v211_01_a_tree_to_the_left_of_a_house.png]] | ![[v205_01_a_tree_to_the_left_of_a_house.png]] | ![[v207_01_a_tree_to_the_left_of_a_house.png]] | ![[v214_01_a_tree_to_the_left_of_a_house.png]] |
| dialect | ![[v204_01_a_tree_to_the_left_of_a_house.png]] | ![[v212_01_a_tree_to_the_left_of_a_house.png]] | ![[v206_01_a_tree_to_the_left_of_a_house.png]] | ![[v208_01_a_tree_to_the_left_of_a_house.png]] | ![[v215_01_a_tree_to_the_left_of_a_house.png]] |

### a cat wearing a blue hat

| 조건 | flux2-klein-4b | lumina2 | pixart-sigma | sd35-medium | zimage-turbo |
|---|---|---|---|---|---|
| shared | ![[v203_02_a_cat_wearing_a_blue_hat.png]] | ![[v211_02_a_cat_wearing_a_blue_hat.png]] | ![[v205_02_a_cat_wearing_a_blue_hat.png]] | ![[v207_02_a_cat_wearing_a_blue_hat.png]] | ![[v214_02_a_cat_wearing_a_blue_hat.png]] |
| dialect | ![[v204_02_a_cat_wearing_a_blue_hat.png]] | ![[v212_02_a_cat_wearing_a_blue_hat.png]] | ![[v206_02_a_cat_wearing_a_blue_hat.png]] | ![[v208_02_a_cat_wearing_a_blue_hat.png]] | ![[v215_02_a_cat_wearing_a_blue_hat.png]] |


## 리소스 표

| 모델 | 조건 | vram_peak_gb | sec_per_image | status |
|---|---|---|---|---|
| flux2-klein-4b | dialect | 17.32 | 3.1 | done |
| flux2-klein-4b | shared | 17.32 | 3.07 | done |
| lumina2 | dialect | 12.28 | 28.9 | done |
| lumina2 | shared | 12.28 | 28.34 | done |
| pixart-sigma | dialect | 14.46 | 6.0 | done |
| pixart-sigma | shared | 14.46 | 6.19 | done |
| sd35-medium | dialect | 17.59 | 13.29 | done |
| sd35-medium | shared | 17.59 | 13.17 | done |
| zimage-turbo | dialect | 21.67 | 17.63 | done |
| zimage-turbo | shared | 21.67 | 17.2 | done |

## Block rate (모델별)

| 모델 | shared | dialect |
|---|---|---|
| flux2-klein-4b | done | done |
| lumina2 | done | done |
| pixart-sigma | done | done |
| sd35-medium | done | done |
| zimage-turbo | done | done |

## 축별 판정 (수량/공간/속성 — 육안 비교 후 수동 기입)

판정값: 방언으로 개선 / 차이 없음 / 둘 다 실패

| 모델 | 수량 | 공간 | 속성 | 종합 소견 |
|---|---|---|---|---|
| flux2-klein-4b | 방언으로 개선 (shared 4개→dialect 정확히 3개) | 차이 없음 (둘 다 성공) | 차이 없음 (둘 다 성공) | 방언이 수량 정확도를 실제로 개선한 유일한 사례. 공간/속성은 이미 baseline에서 잘 됨 |
| pixart-sigma | 차이 없음 (둘 다 대략 3개, 육안상 근사) | 차이 없음 (둘 다 성공) | 둘 다 실패 (파란색이 모자 밖 다리/꼬리/수염까지 번짐) | 방언 효과 거의 없음. 속성 결합(색 전이 방지)은 모델 능력 한계로 판단 |
| sd35-medium | 둘 다 실패 (항상 4개 생성) | 둘 다 실패 (나무·집 좌우가 항상 반대로 뒤바뀜) | 차이 없음 (둘 다 성공) | 수량/공간 모두 조건과 무관하게 동일한 방식으로 실패 — 방언으로 못 고치는 모델 능력 한계 |
| zimage-turbo | 둘 다 실패 (항상 2개만 생성) | 차이 없음 (둘 다 성공) | 차이 없음 (둘 다 성공) | 수량은 능력 한계. 별도로 1라운드와 동일하게 무채색/저채도로 수렴하는 스타일 준수 문제가 더 큼 |
| lumina2 | 차이 없음 (둘 다 정확히 3개) | 차이 없음 (둘 다 성공) | 차이 없음 (둘 다 성공) | 3축 모두 baseline(shared)에서 이미 완벽 — 방언이 필요 없는 모델. 5개 중 복합 프롬프트 최고 성능 |
