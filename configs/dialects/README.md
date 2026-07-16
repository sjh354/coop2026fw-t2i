# configs/dialects/

모델별 프롬프트 방언(dialect) 템플릿. `src/generate.py --dialect edu-<model>`로 적용.
이 디렉토리는 `image-prompts` 방언 파일럿 실험(`.claude/plans/task-snoopy-star.md`)을 위해
신설되었고, 결과에 따라 나중에 모델별 프롬프트 어댑터 레이어의 초안이 된다.

## 파일 스키마

```yaml
base_experiment: educational-flat   # 재표현 대상이 된 shared 실험
model: <model config name>
template: >-
  ... {keyword} ...                 # 플레이스홀더는 {keyword} 하나뿐. .format(keyword=...)
negative: "..."                     # 실제로 모델에 전달될 negative (무시 모델은 "")
transform_notes: >-
  이 dialect가 적용한 구체적 변환 규칙
```

## 핵심 원칙: per-model baseline 대비 의미 동일성

shared 조건에서 모델이 **실제로 받는 내용**은 어댑터의 `supports_negative`에 따라 다르다
(`src/generate.py`가 `exp.get("negative", "")`를 넘기지만, 각 어댑터가 이를 쓰는지는 다름 —
`src/adapters/*.py` 참조). dialect의 의미 동일성은 이 실제 baseline 기준으로 판단해야 한다.

### negative 반영 모델 — baseline = positive 스타일 ∪ negative 필드
`sdxl`, `pixart-sigma`, `sana-1600m`, `sd35-medium`, `lumina2`, `qwen-image`.
이 모델들은 `negative_prompt`가 실제로 CFG에 쓰인다. dialect는 positive/negative 두 채널
사이에서 내용을 재분배할 수 있다(예: SDXL dialect가 금지어를 태그째로 negative 필드로
몰아넣는 것). 단, **positive ∪ negative의 합집합은 shared와 동일해야 한다** — 요소를
추가하거나 완전히 빼면 안 된다.

### negative 무시 모델 — baseline = positive 스타일만
`flux2-klein-4b`(및 klein 계열 전체, CFG 없음), `zimage-turbo`(guidance=1.0),
`ideogram-4`(CFG schedule이 preset에 내장, negative_prompt 파라미터 자체가 없음).
이 모델들은 shared 조건에서도 `negative_prompt` 필드가 **통째로 드롭**되고, 모델은 positive
스타일 문자열만 받는다(단, 그 안에 내장된 부정어 "no gradient, no shading, no
photorealism"은 positive 문자열의 일부이므로 그대로 전달됨).

**따라서 이 세 모델의 dialect는 positive 스타일 내용만으로 구성해야 하며, negative 필드의
태그(예: "heavy black outline", "busy background", "text, letters, watermark")를 positive
문장으로 접어 넣으면 안 된다.** 접으면 dialect가 shared보다 더 많은 내용을 모델에 전달하게
되어, "방언 효과"와 "프롬프트 내용 효과"가 분리되지 않는 confound가 재도입된다 — 정확히
이 세 모델에서 dialect가 "개선됐다"고 잘못 판정될 위험이 가장 크므로 특히 주의.
이 세 파일의 `negative:` 필드는 항상 `""`로 둔다.

## 모델별 형식 요지

| 모델 | 형식 | negative baseline |
|---|---|---|
| sdxl | 태그 나열(bag-of-words), 77토큰 예산 | 반영 (합집합 보존, 태그 그대로) |
| flux2-klein-4b | 주제 선행 계층적 자연어, 가중치 문법(`((...))`) 지양 | 무시 → positive-only |
| sana-1600m | 지시문형(명령문 시퀀스) | 반영 |
| pixart-sigma | 긴 서술형 prose (T5, max_seq 300) | 반영 |
| sd35-medium | 중간 길이 자연어 서술 | 반영 |
| zimage-turbo | 유연한 자연어 서술 | 무시 → positive-only |
| lumina2 | 유연한 자연어 서술 | 반영 |
| qwen-image | 유연한 자연어 서술 | 반영 |
| ideogram-4 | 자연어 description (어댑터가 JSON 캡션으로 감쌈) | 무시(파라미터 없음) → positive-only |

## `src/generate.py`와의 연동

`--dialect edu-<model>`을 주면:
- `prompt = dialect["template"].format(keyword=keyword)` (base_experiment의 `exp['style']`은
  전달용 fallback으로 안 쓰이고, 대신 template 전체가 완성된 프롬프트)
- `negative = dialect.get("negative", "")`
- 출력 폴더 접미사에 `-dialect`가 붙어 shared 조건과 폴더가 겹치지 않음
- 노트 frontmatter에 `condition: dialect`, `dialect: edu-<model>` 기록
