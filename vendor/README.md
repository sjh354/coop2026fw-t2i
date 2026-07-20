# vendor/CSD

`CSD/`는 [learn2phoenix/CSD](https://github.com/learn2phoenix/CSD) (MIT License,
`CSD_LICENSE` 참고)에서 `CSD/` 서브패키지만 그대로 vendor했다 — pip 패키지가 없어서
직접 가져왔다 (2026-07-20, 커밋 시점 origin HEAD 기준).

체크포인트(`weights/scoring/csd_vit-l.pth`, gitignored)는 저자 공식 HF 미러
https://huggingface.co/tomg-group-umd/CSD-ViT-L 에서 받는다. 원본 리포의
Google Drive 링크와 동일 가중치이며, 저자는 논문 수치와의 미세한 불일치
가능성을 리포 상단 disclaimer로 밝혀뒀다 — provisional 용도로는 문제없음.

로드 시 주의: 체크포인트 state dict 키에 `module.` 접두사가 붙어 있어
`CSD.utils.convert_state_dict`로 벗겨내야 한다(`src/scoring.py::load_csd_model`
참고) — 2026-07-20 ubuntu@172.10.5.23에서 실제 체크포인트로 로드+forward
검증 완료(strict 매치, style embedding shape 확인).

사용처: `src/scoring.py`(csd 컴포넌트), `scripts/validate_ref_set.py`.
PYTHONPATH에 리포 루트의 `vendor/`를 추가해야 `from CSD.model import CSD_CLIP`가
동작한다 (예: `PYTHONPATH=vendor python -m scripts.validate_ref_set ...`).
