# conda env 규칙

모델 하나(또는 같은 아키텍처 계열)당 env 하나. `configs/models/*.yaml`의 `env` 필드와
이름을 맞춘다.

**서버 역할 통합 (2026-07-31, 157 반납)**: 원래는 생성 env(`t2i`, `t2i-qwen`, `t2i-ideogram`)와
채점 env(`t2i-score`, `t2i-judge`)를 서버별로 분리해서 97GB 디스크가 금방 차는 걸 피했지만,
`root@172.10.5.157`이 반납되면서 지금은 `ubuntu@172.10.5.23` 하나가 생성+채점+리라이팅을
전부 담당한다. 디스크가 여유 없으니(2026-08-02 기준 7.6GB) 새 env를 만들기 전에 반드시
`df -h /`로 먼저 확인하고, 안 쓰는 env는 `pip freeze`로 백업 후 지울 것. 자세한 건 CLAUDE.md의
"GPU 서버 & keeping everything in sync" 절 참고.

공통 베이스:

    conda create -n t2i-<name> python=3.11 -y
    conda activate t2i-<name>
    pip install torch --index-url https://download.pytorch.org/whl/cu121
    pip install -r ./requirements-common.txt

그 다음 모델별로 diffusers 버전만 다르게 박는다. 여기가 충돌 지점이므로
**성공한 조합은 envs/<name>.txt 로 `pip freeze` 해서 남길 것.**

    pip freeze > envs/<name>.txt

대부분의 모델은 env 하나(`t2i`)를 공유해서 돌아간다. 확인 결과 qwen-image와
ideogram-4만 별도 env가 필요했다(둘 다 요구하는 torch/transformers/bitsandbytes
버전이 서로, 그리고 나머지 모델들과 충돌).

| 모델 | env | 비고 |
|---|---|---|
| pixart-sigma | t2i | 이미 동작 확인됨 |
| sdxl | t2i | |
| flux2-klein-4b / -base / -9b | t2i | Flux2KleinPipeline 필요 → diffusers 최신 |
| zimage-turbo | t2i | diffusers 미지원이면 공식 레포 코드 사용 |
| sd35-medium | t2i | |
| sana-1600m | t2i | |
| lumina2 | t2i | |
| qwen-image | t2i-qwen | bitsandbytes 필요 (nf4 GGUF), t2i-ideogram과 버전 충돌해서 분리 |
| ideogram-4 | t2i-ideogram | ideogram4 패키지 자체 의존성 때문에 분리 |
| flux2-klein-4b-svdquant | t2i-flux2-svdquant | nunchaku(SVDQuant) 요구 torch 2.11+cu13.0 이 t2i env의 torch 2.5.1+cu121과 충돌해서 분리. 공식 업스트림 미지원이라 community wheel(tonera/vitoom-nunchaku) 사용 |

## 채점 전용 env: t2i-score

`src/scoring.py`(VQAScore/CSD 실제 모델)는 T2I 생성 env와 별도 env에서 돌린다 —
diffusers 스택과 무관하고, 생성 모델과 동시에 VRAM에 올리지 않는다는 전제(별도 패스로 실행)라서
분리하는 게 자연스럽다.

    conda create -n t2i-score python=3.11 -y
    conda activate t2i-score
    pip install torch --index-url https://download.pytorch.org/whl/cu121
    pip install -r ./requirements-common.txt
    pip install opencv-python-headless "t2v-metrics==3.0"
    # t2v-metrics v3.1부터 clip-flant5 계열이 legacy 취급되어 빠졌음(README:
    # "reproduce results from the original VQAScore paper → v3.0 release 사용").
    # ==3.0으로 고정해야 model='clip-flant5-xl'이 존재한다.
    conda install ffmpeg=6.1.2 -c conda-forge -y   # t2v_metrics가 import 시점에 요구
    bash envs/fix_t2v_metrics.sh                   # 아래 "t2v-metrics 3.0 패키징 문제" 참고
    # CSD는 pip 패키지가 없음 — vendor/CSD로 이미 vendoring됨(리포에 커밋됨).
    # 실행 시 PYTHONPATH=vendor 필요. 체크포인트 다운로드 경로는 README.md "채점 모듈" 절 참고.

**완료 (2026-07-18, 3090 서버)**: `python scripts/smoke_test_scoring.py` PASS
(success_mean=0.9133 > failure_mean=0.6767). 스냅샷: `envs/t2i-score.txt`.
VRAM 실측(2026-07-19 추가): vram_peak=6.06GB (clip-flant5-xl 로드 기준, T2I 생성
모델과 동시 로드하지 않는 별도 패스 전제이므로 생성 모델 VRAM과 합산하지 않음).

### t2v-metrics 3.0 패키징 문제 (`envs/fix_t2v_metrics.sh`)

`t2v_metrics/__init__.py`가 import 시점에 자기가 지원하는 VLM 백엔드를 전부
끌어온다 — 우리는 `VQAScore(model="clip-flant5-xl")` 하나만 쓰는데도 LLaVA-OneVision,
LLaVA-Video, InternVideo2-CLIP 등 무관한 백엔드가 없는 의존성(`llava` 패키지,
`flash_attn`) 때문에 import 자체가 죽는다. 추가로 pip가 설치하는 `torchaudio`가
`torch`(cu121)와 다른 CUDA 빌드(cu124)로 잡혀서 그것도 따로 크래시.

`envs/fix_t2v_metrics.sh`가 하는 일 (env 하나 새로 만들 때마다 1회 실행):

1. `torchaudio`를 torch와 같은 cu121 인덱스로 강제 재설치
2. `llava` 최소 stub 생성 — `LLaVAOneVisionModel`/`LLaVAVideoModel` 클래스 정의가
   import는 되게 하되 실제로 호출하면 `NotImplementedError` (우리가 안 쓰는 모델이라
   진짜 LLaVA-NeXT를 설치할 필요는 없음)
3. site-packages의 `t2v_metrics/__init__.py`를 패치해서 `CLIPScore`/`ITMScore`
   import를 `try/except ImportError`로 감쌈 — 이 두 클래스(InternVideo2-CLIP,
   BLIP2-ITM)는 안 쓰고, InternVideo2-CLIP 쪽은 `flash_attn`(컴파일 필요한 CUDA
   확장)까지 요구해서 스텁으로 우회하기보다 통째로 건너뛰는 게 맞음

이 스크립트는 `pip freeze`로는 재현 안 되는 site-packages 직접 수정이라
`envs/t2i-score.txt`만 보고 env를 새로 만들면 이 문제가 그대로 재발한다 —
**반드시 `fix_t2v_metrics.sh`를 같이 실행할 것.**

추가로: 서버에 캐시돼 있던 만료된 HF OAuth 토큰(`hf_oauth_...`) 때문에
`google/flan-t5-xl` 다운로드가 401로 막혔던 적이 있음 — 이런 401이 뜨면
`huggingface-cli logout`으로 만료 토큰부터 지울 것 (flan-t5-xl은 공개 모델이라
토큰 자체가 필요 없음).

## VLM-judge 보조 env: t2i-judge (Qwen2.5-VL, 교차검증용)

2026-07-28부터 기본 judge는 InternVL3-8B(아래 `t2i-judge2` 절 참고)로 바뀌었다 —
TASK-C 삼각검증에서 사람 채점과의 κ가 세 judge 중 최고(0.61)였기 때문. 이 env는
**Qwen2.5-VL-7B-Instruct로 교차검증할 때만** 쓴다. `scripts/judge.py`(bench_v1
축별 pass/fail 판정)가 예전에는 Anthropic API(`score_image_vlm`, `t2i-score` env에
`anthropic` 패키지)로 했었지만, API 키가 서버에 없어서 로컬 추론으로 전환한 env다.
`t2i-qwen`(Qwen-Image T2I 생성 모델용)과 이름이 비슷하지만 완전히 다른 모델·용도라
env를 분리한다.

    conda create -n t2i-judge python=3.11 -y
    conda activate t2i-judge
    pip install torch --index-url https://download.pytorch.org/whl/cu121
    pip install -r ./requirements-common.txt
    pip install "transformers>=4.49.0" qwen-vl-utils[decord] accelerate
    pip install torchvision --index-url https://download.pytorch.org/whl/cu121
    # transformers 4.49 미만은 Qwen2_5_VLForConditionalGeneration이 없음.
    # torchvision은 qwen_vl_utils가 import 시점에 요구하는데 위 pip install 목록에는
    # 안 딸려옴 — torch와 반드시 같은 cu121 인덱스로 설치할 것(2026-07-20 확인).

가중치는 `HF_HOME`에 자동 다운로드(`Qwen/Qwen2.5-VL-7B-Instruct`, ~16GB). VRAM 실측치는
`scripts/judge.py` 스모크 테스트 결과 참고(README.md "채점 모듈" 절).

## 기본 judge env: t2i-judge2 (InternVL3-8B, 2026-07-28부터 기본값)

원래는 TASK-C 자기 계열 선호(self-enhancement bias) 검증용으로 Qwen2.5-VL이 아닌
judge(Gemma-3-12B 4bit)를 붙이려고 `t2i-judge`(torch 2.5.1 고정, Qwen2.5-VL 작동 버전)를
건드리지 않고 분리한 env였다 — Gemma-3 계열 체크포인트가 transformers 내부적으로
`torch>=2.6`을 요구해서 같은 env에 못 들어갔기 때문(2026-07-27 확인, `create_causal_mask`가
`ValueError: ... require torch>=2.6`로 죽음). InternVL3-8B(`OpenGVLab/InternVL3-8B-hf`)도
같은 이유로 이 env를 쓴다 — TASK-C 삼각검증 결과 InternVL3가 사람 채점과 κ=0.61로 세
judge 중 가장 높게 나와 `scripts/judge.py`/`scripts/judge_spec.py`의 **기본 judge**가
됐다. `scripts/judge_spec.py --judge-model unsloth/gemma-3-12b-it-bnb-4bit`(Gemma-3)도
이 env에서 그대로 동작한다.

    conda create -n t2i-judge2 python=3.11 -y
    conda activate t2i-judge2
    pip install torch --index-url https://download.pytorch.org/whl/cu124
    pip install pyyaml python-frontmatter safetensors sentencepiece protobuf \
        "transformers>=4.55.0" accelerate bitsandbytes
    pip install torchvision --index-url https://download.pytorch.org/whl/cu124
    # cu121 인덱스는 torch 2.5.1이 최신이라 torch>=2.6 요구를 못 채운다 — cu124 필수.
    # streamlit 등 나머지 requirements-common.txt 패키지는 이 env에서 안 쓰여서 뺐다.

**기본 judge 가중치**는 `OpenGVLab/InternVL3-8B-hf`(bf16, 15.9GB, transformers 네이티브
`InternVLForConditionalGeneration`, `trust_remote_code` 불필요 — 원본 `OpenGVLab/InternVL3-8B`는
커스텀 `InternVLChatModel` 클래스라 호환 안 됨, 반드시 `-hf` 접미사 붙은 리포를 쓸 것).
VRAM 실측: 파일럿 3장 기준 vram_peak=15.35GB(16GB 예산 대비 여유 ~0.65GB,
`scripts/sweeps/pilot_judge_internvl3.sh`, 2026-07-28).

Gemma-3 가중치(교차검증용)는 `unsloth/gemma-3-12b-it-bnb-4bit`(사전 4bit 양자화, ~7.3GB,
ungated) 사용 — `google/gemma-3-12b-it` 원본(bf16, ~22.7GB, gated)은 서버 여유 디스크에
안 들어간다. VRAM 실측: 파일럿 3장 기준 vram_peak=7.57GB
(`scripts/sweeps/pilot_judge_gemma3.sh`, 2026-07-27).

스냅샷: `envs/t2i-judge2.txt`.
