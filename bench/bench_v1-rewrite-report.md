# bench_v1 rewriter 변환 리포트

총 40개, 재시도 발생 1개.

본 실험 전 육안 스팟체크: 카테고리별 몇 개씩 골라 원문 의도가 유지됐는지,
출력이 비지 않았는지 확인할 것 (D 검증에서 발견된 빈 출력 버그와 동일 클래스).

| # | id | 과목 | 카테고리 | 입력(ko) | 출력(en) | 재시도 |
|---|-----|------|---------|----------|----------|--------|
| 1 | bench_v1_001 | 국어 | 사물단독 | 국어 낱말 카드에 쓸 사과 그림 하나 그려줘 | exactly one red apple with one green leaf and one brown stem, large and centered | - |
| 2 | bench_v1_002 | 수학 | 사물단독 | 수학 시간에 쓸 주사위 하나 그려줘 | exactly one white six-sided die with black circular pips, slightly rotated to show three faces displaying one pip, two pips, and three pips | - |
| 3 | bench_v1_003 | 영어 | 사물단독 | 영어 단어 학습용으로 우산 그림 하나 필요해 | exactly one yellow umbrella centered, canopy open and curved handle visible | - |
| 4 | bench_v1_004 | 사회 | 사물단독 | 옛날 물건 소개 자료에 쓸 갓(조선시대 전통 모자) 그림 하나 | exactly one black Joseon-era gat with a tall translucent crown, a wide circular brim, and two thin tied chin strings, single centered arrangement | - |
| 5 | bench_v1_005 | 음악 | 사물단독 | 음악 시간에 배울 리코더 그림 하나 그려줘 | exactly one cream soprano recorder with clearly visible finger holes and mouthpiece, single centered arrangement | - |
| 6 | bench_v1_006 | 국어 | 사물단독 | 노란 리본이 달린 파란 선물 상자를 그려줘 | a blue gift box with a yellow ribbon tied in a neat bow on top, single centered arrangement | - |
| 7 | bench_v1_007 | 사회 | 역사문학 | 한복을 입은 조선시대 선비 한 명을 그려줘 | exactly one Joseon-era scholar wearing traditional white hanbok and a black gat hat, standing centered, calm posture with hands gently clasped in front | - |
| 8 | bench_v1_008 | 국어 | 역사문학 | 흥부전 수업에 쓸 제비 한 마리 그려줘 | exactly one black and white swallow with a long forked tail, perched on a thin branch, centered | - |
| 9 | bench_v1_009 | 사회 | 역사문학 | 빨간 곤룡포를 입은 왕과 파란 치마를 입은 왕비가 나란히 서 있는 그림 | exactly one king in a red gonryongpo robe and exactly one queen in a blue chima skirt standing side by side, the king on the left and the queen on the right, both facing forward with calm expressions | - |
| 10 | bench_v1_010 | 사회 | 역사문학 | 거북선 한 척이 바다 위에 떠 있는 장면을 그려줘 | exactly one traditional Korean turtle ship floating on calm sea waves, the ship centered, showing a wooden hull, a spiked roof deck, and a dragon-headed prow | - |
| 11 | bench_v1_011 | 사회 | 역사문학 | 초가집 앞에 서 있는 농부의 모습을 그려줘 | a friendly farmer standing centered in front of a thatched-roof house, wearing a wide straw hat and plain overalls, holding a wooden hoe at their side | - |
| 12 | bench_v1_012 | 사회 | 역사문학 | 노란 저고리를 입은 아이 세 명이 강강술래를 하는 장면 | exactly three children wearing yellow jeogori jackets performing the Ganggangsullae circle dance, each child holding the next child's hands, evenly spaced to form a ring, feet mid-step, cheerful expressions | - |
| 13 | bench_v1_013 | 국어 | 역사문학 | 기와집 왼쪽에는 붉은 단풍나무, 오른쪽에는 소나무가 있는 가을 풍경 | a traditional Korean tile-roofed house centered, exactly one red maple tree on the left with autumn foliage, exactly one green pine tree on the right, scattered fallen leaves below | - |
| 14 | bench_v1_014 | 과학 | 자연과학 | 개구리 한 마리를 그려줘 | exactly one green frog sitting facing forward, centered | - |
| 15 | bench_v1_015 | 과학 | 자연과학 | 해바라기 한 송이 그림이 필요해 | exactly one yellow-petaled sunflower with a brown center, a green stem, and exactly two green leaves, single centered arrangement | - |
| 16 | bench_v1_016 | 과학 | 자연과학 | 보름달을 그려줘 | a large bright full moon centered, with visible surface craters and dark maria | - |
| 17 | bench_v1_017 | 과학 | 자연과학 | 비 오는 날 하늘의 먹구름을 그려줘 | exactly three dark gray clouds with steady rain falling downward from each, arranged in a horizontal row near the top | - |
| 18 | bench_v1_018 | 과학 | 자연과학 | 나뭇가지에 참새 네 마리가 앉아 있는 그림 | exactly four brown sparrows perched on a single tree branch in a horizontal row, evenly spaced | - |
| 19 | bench_v1_019 | 과학 | 자연과학 | 주황색 몸에 흰 줄무늬가 있는 흰동가리 물고기를 그려줘 | exactly one orange clownfish with white stripes, side view, fins spread, single centered arrangement | - |
| 20 | bench_v1_020 | 과학 | 자연과학 | 태양 왼쪽에 지구, 오른쪽에 달이 나란히 있는 그림을 그려줘 | the Sun centered with exactly one Earth on the left and exactly one Moon on the right, all in a horizontal row, each body shown as a simple sphere with distinct colors and craters visible on the Moon | - |
| 21 | bench_v1_021 | 과학 | 자연과학 | 연못 위에 연잎 다섯 장이 떠 있고 그중 하나에 개구리가 앉아 있는 그림 | exactly five green lotus leaves floating on calm water, arranged in a gentle cluster, the rightmost leaf supporting exactly one small green frog sitting facing forward | - |
| 22 | bench_v1_022 | 과학 | 자연과학 | 빨간 튤립 두 송이와 노란 튤립 세 송이가 함께 핀 화단 | exactly two red tulips and exactly three yellow tulips growing together in a rectangular flower bed, green stems and leaves visible, arranged in one horizontal row with the red tulips on the left and the yellow tulips on the right | - |
| 23 | bench_v1_023 | 사회 | 생활사회 | 횡단보도 앞에 서 있는 초등학생을 그려줘 | exactly one elementary school student standing in front of a zebra crosswalk, facing forward, a small backpack on their shoulders | - |
| 24 | bench_v1_024 | 사회 | 생활사회 | 지진 대피 훈련 자료로, 책상 아래에 들어가 몸을 웅크린 학생 그림 | exactly one student crouching under exactly one sturdy desk, knees tucked and head covered with both hands, earthquake drill posture, centered single arrangement | - |
| 25 | bench_v1_025 | 사회 | 생활사회 | 버스 정류장에서 차례로 줄을 선 사람 세 명을 그려줘 | exactly three people standing in a single file line at a bus stop, arranged from left to right, beside a round bus stop sign on the left | - |
| 26 | bench_v1_026 | 사회 | 생활사회 | 소방관이 호스로 불을 끄는 모습을 그려줘 | exactly one firefighter in a bright protective helmet and suit on the left spraying a stream of water from a hose toward tall orange flames on the right, clear action pose | - |
| 27 | bench_v1_027 | 실과 | 생활사회 | 밥그릇 오른쪽에 국그릇이 놓인 올바른 상차림 그림 | a Korean table setting showing exactly one white rice bowl on the left, exactly one soup bowl on the right, exactly one metal spoon and exactly one pair of chopsticks placed parallel in a horizontal row on the far right | - |
| 28 | bench_v1_028 | 국어 | 생활사회 | 교실에서 두 명은 앉아서 책을 읽고 한 명은 창가에 서서 밖을 보는 장면 | three students in a classroom, exactly two seated students on the left reading open books at two separate desks, exactly one standing student on the right by a tall window looking outside, friendly expressions | - |
| 29 | bench_v1_029 | 사회 | 생활사회 | 빨간 앞치마를 입은 요리사가 접시 세 개를 들고 있고 뒤에 오븐이 보이는 주방 | a friendly chef wearing a red apron holding exactly three white plates, two plates in the left hand and one plate in the right hand, a silver oven on the right side | - |
| 30 | bench_v1_030 | 국어 | 생활사회 | 노란 우비를 입은 아이가 파란 우산을 쓰고 물웅덩이 옆을 걷는 모습 | a smiling child in a yellow raincoat holding exactly one blue umbrella above their head, walking on the left beside exactly one shallow puddle on the right | - |
| 31 | bench_v1_031 | 도덕 | 감정관계 | 활짝 웃는 아이의 얼굴을 그려줘 | a friendly child's face showing a wide smile with visible teeth, big bright eyes, rosy cheeks, head slightly tilted, centered close-up | - |
| 32 | bench_v1_032 | 국어 | 감정관계 | 슬퍼서 눈물을 흘리는 아이를 그려줘 | a young child with teary eyes and visible tears running down both cheeks, head slightly bowed, shoulders slumped, hands loosely at sides, single centered arrangement | - |
| 33 | bench_v1_033 | 도덕 | 감정관계 | 한 명은 기뻐하고 다른 한 명은 화가 난 두 아이를 그려줘 | exactly two children standing side by side, on the left a happy smiling child raising one hand, on the right an angry frowning child with crossed arms, both wearing simple shirts | - |
| 34 | bench_v1_034 | 도덕 | 감정관계 | 넘어진 친구에게 손을 내밀어 일으켜 주는 아이의 모습 | exactly two children, the left child extending a helping hand, the right child sitting on the ground reaching up, their hands meeting at the center, both with friendly expressions | - |
| 35 | bench_v1_035 | 도덕 | 감정관계 | 발표하는 친구를 부러운 표정으로 바라보는 학생의 모습 | exactly two students, the observer on the right seated at a desk with an admiring, slightly envious expression, watching a presenting classmate on the left standing and gesturing toward a blank board | - |
| 36 | bench_v1_036 | 도덕 | 감정관계 | 세 명의 아이 중 가운데 아이만 시무룩하고 양옆 아이들은 웃고 있는 모습 | exactly three children in a horizontal row, the middle child showing a sad frown, the left child smiling, the right child smiling, all facing forward | - |
| 37 | bench_v1_037 | 도덕 | 개념은유 | 흙에서 새싹이 돋아나는 모습을 그려줘 (성장을 상징하는 그림) | exactly one small green sprout emerging from a dark brown soil layer, centered, a large upward arrow above the sprout pointing up, a bright yellow sun on the upper right | - |
| 38 | bench_v1_038 | 도덕 | 개념은유 | 여러 색깔의 퍼즐 조각들이 하나로 맞춰지는 모습 (협동을 상징) | exactly four puzzle pieces forming one square, one red piece on the left, one blue piece on the right, one yellow piece on the top, one green piece on the bottom, curved arrows pointing inward as the pieces slide together | OK |
| 39 | bench_v1_039 | 과학 | 개념은유 | 바다에서 물이 증발해 구름이 되고 비로 내리는 물의 순환을 한 장면에 담은 그림 | the water cycle showing one ocean on the left with exactly three upward vapor arrows, above them two clouds forming, on the right exactly three downward blue arrows of rain falling from the clouds onto a small green land | - |
| 40 | bench_v1_040 | 도덕 | 개념은유 | 큰 나무가 그늘을 만들어 작은 새싹을 지켜 주는 모습 (배려를 상징) | exactly one large leafy tree on the left casting broad shade with its canopy over exactly one small green sprout on the right, the sprout standing upright under the shade, two gentle curved arrows from tree to sprout suggesting protection | - |
