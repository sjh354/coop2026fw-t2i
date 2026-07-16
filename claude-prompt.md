<user>
T2I 모델의 프롬프트 작성법에 관한 최신의 신뢰할만한 연구나 발견이 있는지 논문이나 공식 블로그 같은곳을 통해서 찾아봐줘
</user>
<claude>
T2I 모델 프롬프트 작성법에 대한 최신 연구를 찾아볼게. 여러 각도로 검색해보겠습니다.좋은 논문들이 나오고 있네. 공식 블로그/모델 제공자 가이드와 최신 방법론도 추가로 찾아보겠습니다.PromptEnhancer는 CVPR 2026 채택 논문이네. 이제 공식 모델 제공자 가이드(FLUX, Qwen-Image 등)와 프롬프트 실패 모드 관련 내용을 찾아보겠습니다.공식 1차 자료로 Black Forest Labs의 FLUX 프롬프트 가이드를 직접 확인하겠습니다.찾아본 결과를 학술 연구와 공식 제공자 가이드 두 축으로 정리했어. 흥미롭게도 서로 다른 출처들이 상당히 비슷한 원칙으로 수렴하고 있습니다.

## 1. 학술 연구 (최신)

가장 주목할 만한 건 **PromptEnhancer** (Tencent Hunyuan, arXiv 2509.04545, **CVPR 2026 채택**)입니다. T2I diffusion 모델이 attribute binding(속성 결합), negation(부정), compositional relationship(구성 관계) 같은 복잡한 프롬프트를 충실히 렌더링하지 못하는 문제를 다루는데, 핵심 접근은 이거예요:

- 모델 가중치를 수정하지 않고 rewriter를 generator와 분리(decouple)하는 범용 프롬프트 재작성 프레임워크. 즉 어떤 사전학습 T2I 모델에도 plug-and-play로 붙일 수 있음.
- AlignEvaluator라는 보상 모델의 지도하에 강화학습으로 Chain-of-Thought(CoT) rewriter를 학습. 이 AlignEvaluator는 흔한 T2I 실패 모드를 분석해 도출한 24개 핵심 항목(key points) taxonomy에 기반해 명시적이고 세밀한 피드백을 제공합니다.
- 학습은 2단계로, 먼저 SFT로 CoT 스타일 응답 능력을 초기화하고, 이후 GRPO로 정책을 정렬합니다. SFT 데이터는 Gemini-2.5-Pro(영어)/DeepSeek-V3(중국어)를 teacher로 삼아 (짧은 프롬프트 → 요소 분해·모호성 분석 → 풍부한 프롬프트) 쌍을 distillation해서 구성했어.

재훈 씨가 PixArt 파이프라인에 곧바로 참고할 수 있는 부분: 이 24개 실패 모드 분류(T2I-KeyPoints)와 rewriter 코드/모델(7B·32B)이 [GitHub](https://github.com/Hunyuan-PromptEnhancer/PromptEnhancer)에 공개돼 있고, T2I-Keypoints-Eval 평가 스크립트도 함께 나와 있습니다. Streamlit 리뷰 워크플로우에 정렬 평가 축으로 붙이기 좋아 보임.

그 외 관련 계열 연구들:
- **PRISM** (arXiv 2403.19103, v4 2025.08): 블랙박스 접근만으로 사람이 읽을 수 있고 모델 간 전이 가능한 프롬프트를 자동 생성. LLM jailbreaking에서 착안해, 참조 이미지 기반으로 후보 프롬프트 분포를 반복적으로 정제합니다.
- **VisualPrompter** (arXiv 2506.23138): 시각 피드백을 활용한 semantic-aware 프롬프트 최적화.
- RePrompt(RL 기반), LayerCraft(CoT + 레이어드 오브젝트), MInT(멀티모달 CoT) 등 "LLM으로 프롬프트를 rewrite한다"는 방향이 현재 SOTA 흐름입니다.

## 2. 공식 제공자 가이드

**Black Forest Labs (FLUX 공식)** — docs.bfl.ml에 정식 가이드가 있고, 특히 재훈 씨한테 유용할 건 [black-forest-labs/skills GitHub](https://github.com/black-forest-labs/skills)의 `flux-best-practices` 스킬입니다. Core Principles(보편 원칙), 모델별 가이드, T2I/I2I 프롬프팅, JSON 구조화 프롬프팅, Hex 컬러 지정(#RRGGBB)을 포함하고 Claude Code 플러그인으로도 설치 가능해. 핵심 원칙은 주제를 먼저 놓고, 정확한 색은 HEX 코드로, 복잡한 장면은 JSON으로, 계층적 정보 구조를 따르라는 것. 또 FLUX.2에서는 (((개념:1.5))) 같은 복잡한 가중치 문법이 대체로 눈에 띄는 차이를 만들지 못하는데, 어텐션이 자연어 구조와 위치에 따라 가중치를 내부적으로 처리하기 때문이라 공식 지침은 문법보다 자연어 구조를 신뢰하라고 권합니다.

**Qwen-Image (Alibaba 공식 리포트 arXiv 2508.02324)** + 커뮤니티 검증 가이드에서 나온 실전 규칙:
- 서사보다 구조 — Subject/Environment/Lighting처럼 범주화된 서술이 정밀도를 높인다. 주제를 먼저, 그다음 환경, 그다음 세부를 서술.
- 1~3문장이 sweet spot이고 장황함보다 간결함이 낫다.
- 넣고 싶은 텍스트는 항상 큰따옴표로 감싸면 렌더링 정확도가 크게 오른다 (여러 소스가 공통으로 강조).

## 여러 출처가 수렴하는 공통 원칙

논문·공식문서를 관통하는 실무 원칙을 정리하면:

1. **구조화 > 서사**: 주제 → 환경 → 조명/스타일 → 기술 파라미터 순의 계층적 서술
2. **어순이 곧 가중치**: 중요한 요소를 앞쪽에 배치 (FLUX·Qwen 공통)
3. **간결성**: 1~3문장
4. **가중치 문법 지양**: 최신 flow-matching 계열 모델에선 자연어 구조가 더 잘 먹힘
5. **LLM 기반 CoT rewriting**: 짧은 사용자 프롬프트를 요소 분해 → 모호성 해소 → 풍부화하는 파이프라인이 현재 SOTA 방향
6. **실패 모드 인식**: attribute binding / negation / compositional relationship이 반복되는 취약 지점

PixArt-Sigma 자체 공식 프롬프트 가이드나, coloring-book처럼 특정 스타일(굵은 균일선·플랫 컬러) 제약에 초점을 둔 연구를 더 파볼까? 아니면 위 PromptEnhancer의 24개 key-point taxonomy 전체 목록을 구체적으로 뽑아줄까?
</claude>
<user>
일단 PixArt-Siama공식 가이드랑 교육용 이미지 생성에 알맞른 특정 스타일 제약에 초점을 둔 연구도 더 찾아보고 정리해줘. 
PromptEnhancer의 24개 key-point taxonomy 전체 목록도 정리해줘

그리고 최종적으로 텍스트 인코더까지 포함해서 모델이 쓰는 총 VRAM은 16GB환경에서 원활하게 돌아가야 한대. 이런 환경에서 쓸 수 있는 가장 적합한 모델이 뭐가 있는지 굳이 pixart나 flux가 아니어도 돼. 모델에 대한 전반적인 탐색을 통해 추천 모델 상위 5개를 그 이유와 함께 말해주고, 각 모델에 대응하는 프롬프팅에 관한 특이사항이 있으면 그것도 같이 정리해줘
</user>
<claude>
세 가지를 나눠서 조사할게. PixArt-Sigma 공식 자료, 24개 key-point 전체 목록, 그리고 16GB VRAM 환경 모델 탐색. 순서대로 검색하겠습니다.PixArt-Sigma 자료 확보. 이제 PromptEnhancer의 24개 key-point 전체 목록을 논문 본문에서 확인하겠습니다.24개 taxonomy 전체 확보. 이제 교육용/컬러링북 스타일 제약 연구를 찾아보겠습니다.컬러링북/라인아트 연구 확보. 마지막으로 16GB VRAM 환경에 적합한 최신 모델들을 폭넓게 조사하겠습니다.세 주제 모두 자료가 모였어. 순서대로 정리할게.

---

## 1. PixArt-Sigma 공식 자료 + 교육용 스타일 제약 연구

### PixArt-Sigma 공식 정보 (HF/GitHub)

핵심은 재훈 씨도 이미 쓰고 있겠지만 VRAM 관점에서 짚으면:

- 아키텍처는 UNet이 아닌 **Transformer 백본(DiT 계열)**이고, T5 텍스트 인코더와 VAE를 쓰는 Transformer Latent Diffusion Model입니다. T5 기반 학습 덕분에 세밀한 디테일이 있는 복잡한 프롬프트를 더 잘 따라간다는 게 공식 설명.
- 메모리: 텍스트 인코더를 8-bit로 로드하면 8GB 미만 VRAM에서 PixArtSigmaPipeline을 돌릴 수 있고, load_in_4bit로 내리면 7GB 미만까지 가능합니다. 단 8-bit로 계산한 텍스트 임베딩은 정밀도 손실로 이미지 품질에 영향을 줄 수 있어 켜고 끈 결과를 비교하도록 권장해요.
- 실전 팁: 공식 diffusers 워크플로우는 **텍스트 인코더로 임베딩만 뽑고 → 메모리에서 내린 뒤(flush) → transformer로 latent 생성**하는 2단계 분리를 권장합니다. 큰따옴표로 넣을 프롬프트는 max_sequence_length 기본값 300이고, guidance_scale은 4.5가 기본. clean_caption 옵션으로 캡션 전처리도 가능.
- ComfyUI 쪽에선 T5를 bnb 4bit로 로드하면 약 6GB VRAM만 차지해 12GB 카드에서도 동작하지만, BitsAndBytes가 가중치를 시스템 RAM으로 임시 이동시키지 못해 계속 VRAM에 상주한다는 특성이 있습니다.

즉 PixArt-Sigma는 T5-XXL(약 4.7B)이 메모리의 대부분을 차지하고, transformer 자체는 0.6B로 매우 가벼운 구조예요.

### 교육용/컬러링북 스타일 제약 연구

재훈 씨 목표(굵고 균일한 선, 플랫 컬러)에 직접 맞닿은 연구들:

- **LineArt** (arXiv 2412.11519): 학습 없이(training-free) 디자인 드로잉에 외형을 입히는 프레임워크인데, ablation에서 패턴 두께를 제어하는 double-line(이중선)의 역할, 텍스처 생성을 강화하는 고주파 제약으로서의 soft edge를 핵심 설계로 검증했어요. 다만 그림자가 과하거나 텍스처가 복잡한 라인 드로잉에서는 어려움을 겪는다고 명시 — 이게 컬러링북엔 오히려 시사점입니다. 컬러링 페이지는 그림자·그라데이션이 **없어야** 하는데, diffusion 모델은 기본적으로 음영을 넣으려는 경향이 있어요.

- **Flow-Guided Controllable Line Drawing** (arXiv 2307.07540): Image-to-Flow 네트워크, Double Flow Generator, Line Controllable Regressor 세 모듈로 선의 스타일과 제어 가능성을 확보. 선 두께/스타일을 명시적으로 제어하는 접근.

- 반대 방향(선→채색) 연구도 계열이 활발합니다. Diffusart(CVPRW 2023, 스크리블 기반 조건부 채색), MangaDiT(arXiv 2508.09709, 계층적 어텐션으로 레퍼런스 기반 채색), Offset Prior 기반 채색(WACV) 등. 이건 재훈 씨가 라인아트를 생성한 뒤 플랫 컬러를 자동으로 채우고 싶을 때 참고할 방향이에요.

**실무적 결론**: "굵고 균일한 선 + 플랫 컬러 + 닫힌 영역"은 프롬프트 텍스트만으로 강제하기 어렵습니다(모델이 음영을 넣으려 함). 커뮤니티에서 검증된 패턴은 (1) 전용 coloring-book LoRA + `black and white, line art, thick outlines, white background` 류 프롬프트, (2) **ControlNet(lineart/canny)로 구조를 강제**, (3) 래스터 생성 후 **SVG 벡터화로 후처리**하는 방식입니다. (3)은 재훈 씨가 이미 탐색 중인 벡터 이미지 방향과 정확히 맞물려요 — 벡터화 단계에서 선 두께 균일화와 색 평탄화를 결정론적으로 강제할 수 있으니까요.

---

## 2. PromptEnhancer의 24개 Key-Point Taxonomy (T2I-KeyPoints) 전체 목록

논문 Table 1 기준 전체입니다. 6개 상위 카테고리로 조직된 24개 세부 key point로, 각 항목은 TIC(Text-Image Consistency, 텍스트-이미지 일치) 또는 SI(Structural Integrity, 구조 무결성) 기준으로 평가돼요.

**① Linguistic Comprehension (언어 이해)**
1. Negation — 부정 해석 ("파 없는 소고기국수")
2. Attribute Consistency — 하나의 속성을 여러 대상에 결합 ("모두 빨간 옷 입은 다섯 명")
3. Pronoun Resolution — 대명사 지시 모호성 해소 ("it"이 공을 가리킴)

**② Visual Attributes (시각 속성)**
4. Counting — 수 세기, n≥3 ("강아지 네 마리")
5. Size — 상대적 크기 비교
6. Material — 재질 렌더링 ("독수리 얼음 조각")
7. Expression — 얼굴 표정/감정
8. Artistic Style — 화풍 준수 ("수묵화의 여덟 준마")

**③ Action & Interaction (동작·상호작용)**
9. Full-body Action — 전신 복합 동작 (TIC&SI)
10. Hand Action — 손/손가락 구조 (TIC&SI)
11. Animal Action — 동물의 동작 (TIC&SI)
12. Contact Interaction — 물리적 접촉 상호작용 (TIC&SI)
13. Interaction w/o Contact — 비접촉 상호작용 ("아인슈타인이 호킹을 바라봄")
14. State — 연속적 상태 ("바람에 흩날리는 벚꽃")

**④ Relations & Structure (관계·구조)**
15. Comparative Relation — 속성 비교 ("A가 B보다 키가 큼")
16. Compositional Relation — 다른 것으로 구성된 개체 ("오렌지 조각으로 만든 고양이")
17. Containment Relation — 용기가 개체를 담음 ("소다수 가득한 컵")
18. Similarity Relation — 형태 유사성 ("기타 모양 호수")
19. Cross-Entity Binding — 서로 다른 개체에 다른 속성 결합
20. Entity Layout — 특정 배치 ("좌상단 미니맵")

**⑤ World Knowledge & Reasoning (세계 지식·추론)**
21. Knowledge Application — 유명 개체 ("만리장성 / 마리 퀴리")
22. Counterfactual — 초현실·불가능 장면

**⑥ Scene Text & Typography (장면 텍스트)**
23. Text Rendering — 텍스트 내용 정확 렌더링
24. Text Layout — 지시대로 텍스트 위치 배치

**정량 결과 요약**(HunyuanImage 2.1 기준): 24개 차원 평균 정확도가 65.9% → 71.0%로 5.1pp 상승, 24개 중 21개 개선. 가장 큰 향상은 Similarity Relation(+17.3pp), Counterfactual(+17.2pp), Counting(+15.0pp), Pronoun Resolution(+13.9pp), Expression(+12.9pp), Cross-Entity Binding(+11.3pp). 반대로 비접촉 상호작용(-4.9pp), Size(-0.7pp), Text Layout(-0.7pp)에서는 소폭 하락 — 단순 개념에서는 rewrite가 오히려 모호성/과잉 명세를 유발할 수 있다는 뜻이에요.

참고로 이들이 rewrite에 쓴 teacher 시스템 프롬프트는 거시→미시 4단계 서술 계층, 객관성·정밀성을 위한 7개 문법 규칙, 9개 핵심 제약으로 구성됩니다. 재훈 씨 프롬프트 템플릿 설계에 그대로 벤치마킹할 수 있는 구조예요.

---

## 3. 16GB VRAM(텍스트 인코더 포함)에서 원활한 모델 Top 5

"원활하게"를 기준(= 풀 프리시전에 가깝게, 잦은 반복 생성에 여유 있게)으로 잡고, 효율↔품질 스펙트럼을 넓게 커버하도록 골랐습니다.

**1. SANA-1.6B (NVIDIA/MIT)** — 효율·여유 1위
0.6B 버전이 Flux-12B 대비 20배 작고 100배 이상 빠르며, 16GB 노트북 GPU에서 1024×1024를 1초 미만에 생성합니다. 핵심은 32배 압축 Deep Compression Autoencoder(DC-AE), 선형 어텐션 Linear DiT, 그리고 T5 대신 decoder-only 소형 LLM(Gemma) 텍스트 인코더. 16GB에 ControlNet·LoRA까지 얹을 헤드룸이 가장 큽니다. **프롬프팅 특이사항**: T5류가 아니라 Gemma 기반이라 Complex Human Instruction(CHI)이라는, in-context learning과 instruction-following을 활용하는 상세 자연어 지시가 잘 먹혀요. "이런 스타일로 그려줘" 식의 설명형 지시에 강합니다.

**2. Z-Image Turbo (Alibaba, 6B)** — 품질/VRAM 가성비 + 최신
6B 단일 스트림 DiT로, Turbo가 8-step 서브초 추론을 16GB 미만 VRAM에서 달성하며 훨씬 큰 모델들을 능가. GenEval·DPG-Bench 등에서 photorealism, 이중언어 텍스트 렌더링, attribute binding, prompt following 상위권이고, Apache 2.0라 상업적 사용 가능. 텍스트 인코더는 수정된 Qwen3-4B. **프롬프팅 특이사항**: LLM 인코더라 자연어 지시가 유연하고, 영·중 텍스트 렌더링이 강하니 교육 자료의 라벨/제목을 이미지 안에 넣을 때 유리. 단 풀 BF16 상주는 16GB에 빠듯할 수 있어 인코더 fp8/Q8 또는 CPU offload를 곁들이는 게 안전합니다.

**3. FLUX.1 Dev (GGUF Q8)** — 프롬프트 준수·LoRA 생태계 1위
12B DiT + 4.5B T5-XXL 인코더로, GGUF Q8 양자화 시 FP16과 거의 구분 안 되는 품질을 절반 VRAM으로 내며, ControlNet/IP-Adapter 헤드룸이 필요하면 Q4로도 가능. 컬러링북/라인아트 LoRA가 가장 풍부한 축에 속해 스타일 강제에 유리해요. **주의**: 비상업 라이선스라 생성물 판매엔 별도 라이선스 필요 — 교내 연구/교육용이면 무방. **프롬프팅 특이사항**: 주제를 앞에 놓는 계층적 자연어, HEX 색 지정, 복잡 장면은 JSON, 가중치 문법((()))은 지양(자연어 구조 신뢰). guidance-distilled라 negative prompt 의존이 낮습니다.

**4. SDXL** — 스타일 제어(ControlNet+LoRA) 실용성 1위
동적 메모리 관리로 6GB에서도 돌아갈 만큼 가볍고, 특정 스타일·LoRA가 필요한 작업에 실용적 추천. 재훈 씨의 "굵고 균일한 선 + 플랫 컬러" 제약에는 SDXL의 성숙한 ControlNet(lineart/canny/scribble) + coloring-book LoRA 조합이 현재 가장 검증된 파이프라인입니다. **프롬프팅 특이사항**: CLIP 기반이라 자연어 문장보다 **키워드/태그 나열 + negative prompt**가 효과적. 컬러링북 LoRA의 전형적 패턴은 `black and white, line art, thick outlines, white background` 형태예요.

**5. PixArt-Sigma (0.6B)** — 초경량 베이스라인 (현재 사용 모델)
8GB 미만에서 돌면서 크기 대비 놀라운 품질, 최대 4K 출력, 오픈소스. 16GB에선 텍스트 인코더까지 올려도 여유가 커서 배치 생성·리뷰 반복에 좋습니다. T5 기반이라 **긴 서술형 프롬프트에 강하고**(max_seq 300), guidance 4.5가 기본. 재훈 씨의 현재 스택과 연속성이 있으니 새 모델들의 A/B 비교 기준선으로도 계속 쓸 만해요.

**요약 매핑**:
- 최대 속도·헤드룸 → SANA
- 최신·상업 가능·텍스트 렌더링 → Z-Image Turbo
- 최고 프롬프트 준수·LoRA 다양성 → FLUX.1 Dev (Q8)
- 컬러링북 스타일 강제(ControlNet) → SDXL
- 초경량 T5 서술형 베이스라인 → PixArt-Sigma

대안으로 Qwen-Image(20B, 텍스트 렌더링 강하나 16GB엔 강한 양자화 필요), FLUX.2 Klein(증류로 소비자 GPU 실시간급), Kolors(Apache 2.0, ~8GB INT8), Hunyuan-DiT(중국어 텍스트 강점)도 있는데, 위 5개가 "16GB 원활 + 교육용 일러스트"라는 두 조건을 가장 균형 있게 만족합니다.

교육용 컬러링북이라는 목적을 감안하면 개인적으로는 **SDXL(스타일 강제) + SANA 또는 Z-Image(빠른 다량 생성)** 조합이 실전에서 가장 강할 걸로 보여요. 혹시 이 중 특정 모델의 실제 VRAM 내역(인코더/VAE/트랜스포머별)이나 컬러링북 LoRA·ControlNet 파이프라인을 더 구체적으로 파볼까?
</claude>
<user>
모델은 프레젠테이션 교육 자료에 들어갈 삽화를 생성하는 목적이 강하고, 특히 초등~고등학교 정규 교육 과정의 수업 시간에 사용할 자료라서 프롬프트 정합도와 적절한 이미지의 스타일을 갖는게 중요해.

이런 프롬프트를 작성할 때 어떤 오브젝트를 만들지 입력할 창과, 내가(개발자가) 미리 넣어줄 시스템 프롬프트 느낌의 스타일 프롬프트를 합친 만큼이 최대 토큰 길이보다 짧아야 하니까 스타일 프롬프트를 마음껏 늘리지는 못할 것 같아.
저런 스타일의 이미지를 생성하기 위한 우선순위를 반영해서 프롬프트를 몇 개 길이 버전으로 각각 작성해줘. 작성 언어는 상관없이 결과만 잘 나오면 되고, 필요하다면 미리 파인튜닝도 염두에 두고 있어.
더 필요한 사용자 결정이 있다면 일단 물어봐줘
</user>
<claude>
프롬프트를 쓰기 전에 결정이 필요한 게 몇 개 있어. 특히 **어떤 모델을 쓰느냐가 프롬프트의 "방언"과 토큰 예산을 완전히 바꿔**: SDXL은 CLIP 77토큰이라 키워드 나열이 필수고, PixArt/SANA는 ~300토큰 서술형, FLUX는 512토큰까지 자연어가 먹혀. 그리고 앞서 컬러링북 스타일 작업을 하고 있었는데, 이번 프레젠테이션 삽화도 같은 라인아트 계열인지 아니면 플랫 벡터 일러스트 같은 다른 스타일인지에 따라 스타일 프롬프트의 핵심 키워드가 달라져.
</claude>
<user>
질문: 타겟 모델은 어떤 걸로 갈 예정이야? (토큰 예산과 프롬프트 문체가 여기에 따라 달라짐)
답: 아직 미정 — 공용 버전으로

질문: 삽화의 목표 스타일은?
답: 플랫벡터, 교과서 삽화풍 등 상황에 적합한 교육용 이미지

질문: 색상 방향은?
답: 풀컬러 플랫 (그라데이션 없음), 흑백 라인만 및 수업 주제별로 다름
</user>
<claude>
좋아, 그 조건이면 **스타일 프리셋 2개(풀컬러 플랫 / 흑백 라인) × 길이 3버전**으로 만드는 게 맞아. 수업 주제별로 개발자가 프리셋만 갈아끼우는 구조.

우선순위부터 정하면 (뒤가 잘려도 앞이 살아남게 배열):

1. **스타일 앵커** (flat vector illustration / line art) — 이게 빠지면 전부 무너짐
2. **플랫 제약** (no gradients, no shadows) — diffusion 모델은 기본적으로 음영을 넣으려 해서 명시 필수
3. **배경** (white background) — 슬라이드 삽입용이라 배경 분리가 중요
4. **구도** (centered, single subject, minimal)
5. **금지 요소** (no text, no watermark) — CLIP 77토큰에선 잘리기 쉬우니 SDXL에선 negative prompt로 이동

---

## 프리셋 A: 풀컬러 플랫 벡터

**L — 서술형 (~100토큰, PixArt/SANA/FLUX용)**
```
flat vector illustration of {OBJECT}, designed for a school textbook and classroom presentation slides. Simple geometric shapes with clean uniform dark outlines, solid flat colors with no gradients, no shadows and no textures, bright friendly limited color palette, plain white background, single centered subject with generous margins, minimal detail, easily recognizable even at small size, no text, no labels, no watermark
```

**M — 중간 (~40토큰, 공용 안전판)**
```
{OBJECT}, flat vector illustration, educational textbook style, clean uniform outlines, solid flat colors, no gradients, no shadows, plain white background, centered, minimal detail, no text
```

**S — 초단 (~18토큰, SDXL 77토큰 대비)**
```
{OBJECT}, flat vector illustration, flat colors, clean outlines, white background, minimal, educational
```

## 프리셋 B: 흑백 라인 (워크시트/컬러링 겸용)

**L — 서술형**
```
black and white line art illustration of {OBJECT} for a school worksheet, thick uniform black outlines, closed clean shapes, pure white background, no shading, no gray tones, no hatching, no color fill, simple clear forms, single centered subject, no text, no watermark
```

**M — 중간**
```
{OBJECT}, black and white line art, thick uniform black outlines, closed lines, pure white background, no shading, no gray, simple, no text
```

**S — 초단**
```
{OBJECT}, line art, thick black outlines, white background, no shading, simple
```

**SDXL 전용 negative prompt** (S/M 버전과 함께, positive에서 뺀 금지 요소를 여기로):
```
photo, photorealistic, 3d render, gradient, shadow, texture, busy background, text, watermark, signature, complex details
```
FLUX Dev나 Z-Image Turbo 같은 guidance-distilled 모델은 negative prompt를 안 쓰니, 이 경우 M/L 버전처럼 positive 안에 "no ..."로 유지해야 해.

---

몇 가지 설계 판단 근거:

**{OBJECT}를 앞에 둔 이유** — FLUX·Qwen 공통으로 앞쪽 토큰이 더 큰 가중치를 받아서, 프롬프트 정합도(수업 내용이 정확히 나오는 것)가 최우선인 재훈 씨 요구에는 오브젝트 선행이 맞아. 스타일 일관성이 흔들리면 그때 스타일 앵커 한 단어(`flat vector illustration of`)만 앞으로 빼는 L 구조로 전환하면 돼.

**영어로 쓴 이유** — 후보 모델 전부 학습 데이터가 영어 중심이라 정합도가 가장 안정적. 사용자 입력({OBJECT})이 한국어로 들어온다면 rewriter 단계에서 영어로 번역·확장하는 걸 권장해 (아래 파인튜닝과 연결됨).

**파인튜닝 염두 시** — 이게 토큰 예산 문제의 근본 해결책이야. 스타일 LoRA를 학습하면서 트리거 토큰(예: `eduflat style`, `edulinework style`)을 심으면 스타일 프롬프트가 2~3토큰으로 줄고 남는 예산 전부를 {OBJECT} 서술에 쓸 수 있어. 이때 중요한 건 **지금부터 생성·선별하는 데이터의 캡션을 위 프리셋 어휘와 동일하게 유지**하는 것 — 나중에 그 이미지들이 그대로 LoRA 학습 데이터가 되니까. 재훈 씨의 파일시스템 버저닝 + Streamlit 리뷰 워크플로우가 이미 있으니, 리뷰에서 통과한 이미지에 프리셋 ID를 메타데이터로 남겨두면 학습 세트 구축이 공짜로 따라와.

**운영 팁** — 초등 저학년용엔 프리셋 A에 `cute, rounded shapes, friendly` 3토큰을 추가하고, 고등 과학용엔 `accurate proportions, diagram-like` 같은 소폭 변형 슬롯을 두는 식으로, 프리셋을 통째로 늘리기보다 3~5토큰짜리 modifier 슬롯을 얹는 구조가 토큰 예산 관리에 유리해.

원하면 이 프리셋들을 PixArt-Sigma에서 바로 테스트할 수 있게 {OBJECT} 샘플 10개(과목별)를 채운 배치 스크립트 형태로 만들어줄게. 아니면 한국어 입력 → 영어 프롬프트 확장용 rewriter 시스템 프롬프트를 먼저 잡아볼까?
</claude>
<user>
한국어 입력 → 영어 프롬프트 확장용 rewriter 시스템 프롬프트
</user>
<claude>
구조 결정부터 하나 짚을게: **rewriter는 내용(오브젝트 서술)만 출력하고, 스타일 프리셋은 코드에서 문자열로 뒤에 붙이는 걸 권장**해. rewriter한테 스타일까지 맡기면 매 호출마다 스타일 어휘가 미세하게 흔들려서 일관성이 깨지고, 토큰 예산 관리도 비결정적이 되거든. PromptEnhancer도 rewriter와 generator를 분리한 것처럼, 여기선 content(LLM 담당)와 style(상수) 분리가 같은 원리야.

```
You are a prompt rewriter for a text-to-image model that generates
illustrations for K-12 classroom presentation slides.

INPUT: a short description in Korean (occasionally English) of what
to draw, optionally with a grade level.

OUTPUT: exactly one line of English text describing the CONTENT of
the image. No quotes, no explanations, no line breaks. A separate
style preset will be appended by the system — NEVER include style
words (flat, vector, line art, outline, color palette, background,
illustration, cartoon, watercolor, 3d, photo, etc.).

PROCESS (do this silently, output only the final line):
1. Extract: main subject(s), exact counts, per-object attributes,
   actions/states, spatial arrangement.
2. Resolve ambiguity with classroom-appropriate defaults: neutral
   and friendly, culturally generic, safe for children.
3. Translate everything into concrete visual language.

REWRITE RULES:
- Put the main subject in the first 5 words.
- Counts: state numbers explicitly ("exactly three apples") and
  keep each count next to its noun.
- Attribute binding: place each attribute immediately before its
  own noun ("a red circle and a blue square", never "red and blue
  shapes").
- Negation: NEVER use "no/without/not" for content. Convert to a
  positive alternative (e.g. "우산이 파란색이 아님" → pick another
  concrete color: "a yellow umbrella").
- Spatial layout: make positions explicit ("on the left", "above",
  "in a horizontal row") whenever more than one object appears.
- Abstract concepts: convert to a depictable scene (e.g. "광합성" →
  a leaf, sun, and arrows), but keep it simple enough for one image.
- Do not request any text, letters, numbers as glyphs, labels, or
  captions inside the image.
- People: default to a generic, friendly student or teacher unless
  specified; avoid real or famous persons.
- Length: at most {MAX_WORDS} words. Prefer fewer. Cut minor
  details first; never cut the subject, counts, or bindings.

EXAMPLES:
입력: 사과 세 개가 담긴 바구니
출력: a woven basket holding exactly three red apples, the apples
clearly visible above the basket rim, single centered arrangement

입력: 달의 위상 변화 (중학교 과학)
출력: exactly eight moons in one horizontal row showing lunar phases,
starting with a fully dark new moon on the far left, waxing crescent
and half moon in between, a bright full moon at the center, then
waning back to a dark moon on the far right

입력: 파란색이 아닌 우산을 쓴 아이
출력: a smiling child holding a large yellow umbrella above their
head, standing centered, light rain falling around the child
```

운영 노트 몇 개: 

**{MAX_WORDS} 값** — SDXL이면 15, PixArt/SANA면 45, FLUX면 80 정도로 코드에서 주입해. 프리셋 S/M/L과 짝을 맞추면 됨.

**부정 변환 규칙이 제일 중요해.** PromptEnhancer의 24개 실패 모드 중 Negation은 rewrite로 개선되는 대표 항목인데, T2I 모델은 "no X"를 넣으면 오히려 X를 그리는 경향이 있어서 rewriter 단계에서 긍정 서술로 치환하는 게 가장 확실한 해법이야. 스타일 프리셋의 "no gradients" 같은 건 괜찮아 — 그건 학습된 스타일 어휘라 다르게 동작하고, 어차피 상수라 통제 가능해.

**세 번째 예시(달의 위상)는 의도적으로 counting + layout을 동시에 시연**하는 few-shot이야. 교육 자료엔 "n개를 순서대로" 패턴이 자주 나올 텐데, 이게 T2I 최약점(Counting, Entity Layout)이라 예시로 박아두면 rewriter가 그 패턴을 따라해.

**검증 루프** — 이 rewriter 출력을 Streamlit 리뷰 앱에 원본 한국어 입력과 나란히 저장해두면, 나중에 (한국어 입력, 영어 출력) 쌍이 그대로 rewriter 파인튜닝 데이터가 돼. PromptEnhancer의 SFT 데이터 구축과 동일한 구조를 공짜로 얻는 셈이야.

바로 테스트해보고 싶으면, 이 시스템 프롬프트를 로컬 LLM(Qwen 계열이 한국어에 강함)이나 API에 물려서 과목별 한국어 입력 20개짜리 테스트 세트를 돌려보는 걸 추천해. 테스트 입력 세트가 필요하면 만들어줄게.
</claude>