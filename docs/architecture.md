# Architecture

```
사용자
  ↓
app/frontend (Streamlit)  ── R4+R5 소유
  ↓ REST (api_contract.md §1)
app/backend (FastAPI)     ── R4+R5 소유
  │
  ├─ app/prompt          ── R4+R5 소유 (Prompt Builder)
  │
  ↓ REST (api_contract.md §2)
model_server (SDXL/SD1.5 + LoRA×4 + ControlNet/IP-Adapter)  ── R2+R3 소유
```

## 담당 경계
| 레이어 | 담당 | 비고 |
|---|---|---|
| app/frontend | R4+R5 | Streamlit, Wizard(Product→Generate→History) |
| app/backend | R4+R5 | FastAPI, 상태관리, History, 다운로드 |
| app/prompt | R4+R5 | 톤×시간대 템플릿, image_prompt(영어)/ad_copy(한국어) 생성 |
| app/backend/services/overlay.py | R4+R5 | PIL 한글 오버레이 (결정 7) |
| app/backend/services/openai_client.py | R4+R5 | 텍스트 전용 공용 래퍼, 비용 로깅 (결정 8) |
| model_server/ | R2+R3 | 로컬 GPU 이미지 생성, 제품 보존 마스킹 |

## 데이터 흐름
사진 업로드 → 상품 등록 → 생성 요청(톤×시간대 조합) → model_server 호출(마스킹→톤별 배경 생성)
→ 문구 생성(OpenAI, 텍스트) → PIL 오버레이 → 규격별(썸네일/배너/SNS카드) 결과 반환 → History 저장

## 왜 이렇게 나눴나
- 이미지 생성(model_server)과 서비스 로직(app/backend)을 분리해서, R2/R3가 모델을 바꾸거나
  튜닝해도 `docs/api_contract.md`의 계약만 지키면 프론트/백엔드는 영향받지 않는다.
- Prompt Builder를 backend 안이 아니라 `app/prompt`로 독립시킨 이유: 순수 함수라 테스트하기 쉽고
  (tests/test_prompt_builder.py), 나중에 model_server 쪽에서도 재사용할 여지를 남겨둔다.
