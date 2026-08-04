"""
model_server/(R2·R3)를 호출하는 래퍼. R3가 이 스펙대로 Mock 서버부터 띄우면
UI 완성 전에도 통합 테스트가 가능하다. 계약 상세는 docs/api_contract.md 참고.
"""
import os
import httpx

MODEL_SERVER_URL = os.getenv("MODEL_SERVER_URL", "http://localhost:8001")


async def request_generation(product_id: str, product_image_url: str, tone: str,
                              image_prompt: str, negative_prompt: str | None,
                              time_slot: str | None) -> dict:
    payload = {
        "product_id": product_id,
        "product_image_url": product_image_url,
        "tone": tone,
        "image_prompt": image_prompt,
        "negative_prompt": negative_prompt,
        "time_slot": time_slot,
    }
    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(f"{MODEL_SERVER_URL}/infer", json=payload)
        resp.raise_for_status()
        return resp.json()
