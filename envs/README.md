# conda env 규칙

모델 하나(또는 같은 아키텍처 계열)당 env 하나. `configs/models/*.yaml`의 `env` 필드와
이름을 맞춘다.

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

## 채점 전용 env: t2i-score

`src/scoring.py`(VQAScore/CSD 실제 모델)는 T2I 생성 env와 별도 env에서 돌린다 —
diffusers 스택과 무관하고, 생성 모델과 동시에 VRAM에 올리지 않는다는 전제(별도 패스로 실행)라서
분리하는 게 자연스럽다.

    conda create -n t2i-score python=3.11 -y
    conda activate t2i-score
    pip install torch --index-url https://download.pytorch.org/whl/cu121
    pip install -r ./requirements-common.txt
    pip install opencv-python-headless "t2v-metrics==3.0" anthropic
    # t2v-metrics v3.1부터 clip-flant5 계열이 legacy 취급되어 빠졌음(README:
    # "reproduce results from the original VQAScore paper → v3.0 release 사용").
    # ==3.0으로 고정해야 model='clip-flant5-xl'이 존재한다.
    # CSD는 pip 패키지가 없음 — https://github.com/learn2phoenix/CSD 를 vendor하거나
    # PYTHONPATH에 추가할 것. 체크포인트 다운로드 경로는 README.md "채점 모듈" 절 참고.

**미완료**: 이 저장소 개발 샌드박스(macOS, GPU 없음)에서는 t2v_metrics/CSD를 실제로
설치·검증할 수 없었다. 3090 서버에서 위 명령으로 env를 만든 뒤 동작 확인되면
`pip freeze > envs/t2i-score.txt`로 스냅샷을 남길 것.
