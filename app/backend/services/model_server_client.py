"""
model_server/(R2·R3)를 호출하는 래퍼. R3가 이 스펙대로 Mock 서버부터 띄우면
UI 완성 전에도 통합 테스트가 가능하다. 계약 상세는 docs/api_contract.md 참고.
"""
import os
import io
import httpx
from PIL import Image

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


async def fetch_generated_image(generated_image_url: str) -> Image.Image:
    """
    /infer 응답의 generated_image_url(배경 이미지, 제품 보존 처리는 R2/R3가 완료한 상태)을
    실제로 내려받아 PIL Image로 반환한다. 절대 URL("https://...")이면 그대로,
    model_server가 자기 자신 기준 상대경로("/outputs/...")로 주면 MODEL_SERVER_URL을 붙인다.
    """
    url = generated_image_url
    if not url.startswith("http"):
        url = f"{MODEL_SERVER_URL.rstrip('/')}/{url.lstrip('/')}"

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        return Image.open(io.BytesIO(resp.content)).convert("RGB")
