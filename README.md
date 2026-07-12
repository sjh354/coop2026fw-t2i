# t2i-lab

교육용 T2I 모델 후보들을 같은 조건에서 비교하기 위한 실험 환경.
연구개발 단계 — 라이선스/양자화는 일단 무시하고 돌아가는지부터 본다.

## 실행

    conda activate t2i-pixart
    python -m src.generate --model pixart-sigma --exp coloring-book

    streamlit run src/review_app.py

## 구조

    configs/
      models/       모델 1개 = 파일 1개 (repo, adapter, env, dtype, steps, quant)
      experiments/  스타일 1개 = 파일 1개 (style/negative prompt, seed, 참조할 키워드셋)
      keywords/     고정 벤치마크 키워드셋 — 모델 비교의 기준이므로 함부로 안 바꾼다
    src/
      generate.py   모델 × 실험 조합 하나를 생성. 공통 엔트리포인트.
      adapters/     모델별 pipeline 로딩. lazy import (env가 다르므로 필수).
      review_app.py 브라우징/평가/비교
    image-prompts/
      v001_pixart-sigma/
        v001_pixart-sigma.md    frontmatter = single source of truth
        images/
    envs/           conda env 규칙 + 성공한 pip freeze 스냅샷
    bench/          결론과 삽질 메모

## 축이 3개다

    모델(configs/models) × 스타일(configs/experiments) × 키워드셋(configs/keywords)

버전 번호(v001...)는 전역 증가하고, 디렉토리명에 모델명이 붙는다.
어떤 조합이었는지는 노트 frontmatter의 model/experiment/keyword_set에 남는다.
