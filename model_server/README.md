# Model Server (R2 · R3 담당)

담당: 성치용, 유수빈, 김재헌

<!-- 실제 모델 선정 이유, 파이프라인 구조, 실행 방법 등은 담당자가 채워주세요 -->

여기가 로컬 GPU 추론 서버(SDXL/SD1.5 + 톤 LoRA×4 + ControlNet/IP-Adapter) 자리입니다.
R4+R5(app/backend)는 이 서버의 `/infer` 엔드포인트를 호출만 합니다 — 계약은
[docs/api_contract.md](../docs/api_contract.md) 참고.

## 빠른 시작 (제안)
- 이 폴더 아래에 별도 FastAPI 앱으로 구성하는 걸 추천합니다 (`model_server/main.py`)
- Mock 서버부터 먼저 띄워주시면 R4+R5가 UI 완성 전에 통합 테스트를 시작할 수 있습니다:
  ```python
  # 예시 - 실제 모델 없이 더미 이미지 반환
  @app.post("/infer")
  async def infer(payload: dict):
      return {
          "status": "done",
          "generated_image_url": "https://placehold.co/1000x1000",
          "product_preserved": True,
          "gen_time_sec": 1.0,
      }
  ```
- 포트는 `.env.example`의 `MODEL_SERVER_URL`(기본 8001)에 맞춰주세요.
