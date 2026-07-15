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
