# Prompt Spec

## 입력/출력 스키마
`app/prompt/schemas.py`의 `PromptRequest` / `PromptResult` 그대로.

```python
class PromptRequest(BaseModel):
    product_name: str
    category: str | None = None
    price: int | None = None
    selling_points: list[str] = []
    tone: Literal["emotional", "modern", "practical", "premium"]
    time_slot: Literal["morning", "commute_am", "afternoon",
                        "commute_pm", "evening", "late_night"] | None = None

class PromptResult(BaseModel):
    image_prompt: str
    headline: str
    subcopy: str
    negative_prompt: str | None = None
```

출력 비율은 문구 프롬프트 조건이 아니므로 `PromptRequest`에 넣지 않는다.
`GenerationRequest.output_formats`가 1~2개의 프리셋을 받고, 백엔드가 같은
`PromptResult`를 비율별 네이티브 `/infer` 요청에 재사용한다.

## Builder 흐름
```
사용자 입력
  → 톤 템플릿 결합 (app/prompt/templates.py TONE_TEMPLATES)
  → 시간대 템플릿 결합 (TIME_SLOT_TEMPLATES, 선택 시)
  → 제품 보존 지시 추가 (PRODUCT_PRESERVATION_INSTRUCTION)
  → 이미지 프롬프트 생성 (영어)
  → 한국어 광고 문구 생성 (headline/subcopy)
```

- 이미지 프롬프트: 영어 (모델 성능 최적화, model_server가 영어 기반 SDXL/SD1.5 사용)
- 광고 문구: 한국어 (사용자가 실제로 보는 결과물)
- 이미지 내 한글 텍스트는 여기서 만들지 않음 → `app/backend/services/overlay.py`가 PIL로 별도 처리 (결정 7)

## 오늘 준비된 템플릿
- 톤 4종 (감성/모던/실용/프리미엄)
- 시간대 6종 (아침/출근러시아워/오후/퇴근러시아워/저녁/심야) — PM 승인, 러시아워 세분화 반영
- 출력 프리셋 4종 (정사각형 1:1 / SNS 피드 4:5 / 쇼츠·스토리 9:16 / 웹 배너 16:9)
- 한 요청당 서로 다른 프리셋 최대 2개, 생략 시 1:1

## 아직 안 한 것 (의도적으로 보류)
- 톤별 카피 톤앤매너 실제 문구 — 유수빈님이 정의해서 전달 예정, `build_ad_copy()`는 지금 더미
- OpenAI 실제 SDK 연동 — key 수령 후 `openai_client.call_text_model()` TODO 부분 채우기
- 시간대별 세부 하이퍼파라미터(조명 수치 등)는 R2/R3 LoRA 학습 결과 나오면 조정
