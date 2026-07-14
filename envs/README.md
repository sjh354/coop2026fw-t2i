# conda env 규칙

모델 하나(또는 같은 아키텍처 계열)당 env 하나. `configs/models/*.yaml`의 `env` 필드와
이름을 맞춘다.

공통 베이스:

    conda create -n t2i-<name> python=3.11 -y
    conda activate t2i-<name>
    pip install torch --index-url https://download.pytorch.org/whl/cu121
    pip install -r ../requirements-common.txt

그 다음 모델별로 diffusers 버전만 다르게 박는다. 여기가 충돌 지점이므로
**성공한 조합은 envs/<name>.txt 로 `pip freeze` 해서 남길 것.**

    pip freeze > envs/<name>.txt

| env | 모델 | 비고 |
|---|---|---|
| t2i-pixart  | pixart-sigma | 이미 동작 확인됨 |
| t2i-sdxl    | sdxl | diffusers 안정 버전이면 대부분 됨 |
| t2i-flux2   | flux2-klein-4b / -base / -9b | Flux2KleinPipeline 필요 → diffusers 최신 |
| t2i-zimage  | zimage-turbo | diffusers 미지원이면 공식 레포 코드 사용 |
| t2i-sd35    | sd35-medium | |
| t2i-sana    | sana-1600m | |
| t2i-lumina  | lumina2 | |
| t2i-qwen    | qwen-image | bitsandbytes 필요 (nf4) |
| t2i-ideogram| ideogram-4 | repo id / 파이프라인 클래스 확인 필요 |
