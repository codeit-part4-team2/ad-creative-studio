"""
model_server/(R2·R3)를 호출하는 래퍼. R3가 이 스펙대로 Mock 서버부터 띄우면
UI 완성 전에도 통합 테스트가 가능하다. 계약 상세는 docs/api_contract.md 참고.
"""
import os
import io
from urllib.parse import urljoin, urlparse

import httpx
from PIL import Image

MODEL_SERVER_URL = os.getenv("MODEL_SERVER_URL", "http://localhost:8001")
BACKEND_PUBLIC_URL = os.getenv("BACKEND_PUBLIC_URL", "http://localhost:8000")
MAX_GENERATED_IMAGE_BYTES = 25 * 1024 * 1024
MAX_GENERATED_IMAGE_PIXELS = 20_000_000


def _http_origin(url: str) -> tuple[str, str, int]:
    parsed = urlparse(url)
    if (
        parsed.scheme not in {"http", "https"}
        or parsed.hostname is None
        or parsed.username is not None
        or parsed.password is not None
    ):
        raise ValueError("URL must have an HTTP(S) origin without credentials")
    default_port = 443 if parsed.scheme == "https" else 80
    return parsed.scheme, parsed.hostname.lower(), parsed.port or default_port


def _resolve_product_image_url(product_image_url: str) -> str:
    parsed = urlparse(product_image_url)
    if parsed.scheme in {"http", "https"} and parsed.netloc:
        if _http_origin(product_image_url) != _http_origin(BACKEND_PUBLIC_URL):
            raise ValueError(
                "product_image_url must use the BACKEND_PUBLIC_URL origin"
            )
        return product_image_url
    if parsed.scheme or parsed.netloc or not product_image_url.startswith("/"):
        raise ValueError("product_image_url must be an HTTP(S) URL or an absolute API path")
    return urljoin(f"{BACKEND_PUBLIC_URL.rstrip('/')}/", product_image_url.lstrip("/"))


def _generation_payload(
    product_id: str,
    product_image_url: str,
    tone: str,
    image_prompt: str,
    negative_prompt: str | None,
    time_slot: str | None,
) -> dict[str, object]:
    return {
        "product_id": product_id,
        "product_image_url": _resolve_product_image_url(product_image_url),
        "tone": tone,
        "image_prompt": image_prompt,
        "negative_prompt": negative_prompt or "",
        "time_slot": time_slot,
    }


async def request_generation(product_id: str, product_image_url: str, tone: str,
                              image_prompt: str, negative_prompt: str | None,
                              time_slot: str | None) -> dict:
    payload = _generation_payload(
        product_id,
        product_image_url,
        tone,
        image_prompt,
        negative_prompt,
        time_slot,
    )
    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(f"{MODEL_SERVER_URL}/infer", json=payload)
        resp.raise_for_status()
        return resp.json()


def request_generation_sync(product_id: str, product_image_url: str, tone: str,
                            image_prompt: str, negative_prompt: str | None,
                            time_slot: str | None) -> dict:
    payload = _generation_payload(
        product_id,
        product_image_url,
        tone,
        image_prompt,
        negative_prompt,
        time_slot,
    )
    with httpx.Client(timeout=120) as client:
        response = client.post(f"{MODEL_SERVER_URL}/infer", json=payload)
        response.raise_for_status()
        return response.json()


def _resolve_generated_image_url(generated_image_url: str) -> str:
    parsed = urlparse(generated_image_url)
    if parsed.scheme in {"http", "https"} and parsed.netloc:
        if _http_origin(generated_image_url) != _http_origin(MODEL_SERVER_URL):
            raise ValueError("generated_image_url must use the MODEL_SERVER_URL origin")
        return generated_image_url
    if parsed.scheme or parsed.netloc or not generated_image_url.startswith("/"):
        raise ValueError("generated_image_url must be a model-server URL or absolute API path")
    return urljoin(
        f"{MODEL_SERVER_URL.rstrip('/')}/",
        generated_image_url.lstrip("/"),
    )


def _decode_generated_image(content: bytes) -> Image.Image:
    if not content or len(content) > MAX_GENERATED_IMAGE_BYTES:
        raise ValueError("generated image byte size is outside the allowed range")
    with Image.open(io.BytesIO(content)) as source_image:
        width, height = source_image.size
        if width <= 0 or height <= 0 or width * height > MAX_GENERATED_IMAGE_PIXELS:
            raise ValueError("generated image pixel size is outside the allowed range")
        return source_image.convert("RGB")


async def fetch_generated_image(generated_image_url: str) -> Image.Image:
    """
    /infer 응답의 generated_image_url(배경 이미지, 제품 보존 처리는 R2/R3가 완료한 상태)을
    실제로 내려받아 PIL Image로 반환한다. 절대 URL("https://...")이면 그대로,
    model_server가 자기 자신 기준 상대경로("/outputs/...")로 주면 MODEL_SERVER_URL을 붙인다.
    """
    url = _resolve_generated_image_url(generated_image_url)

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        return _decode_generated_image(resp.content)


def fetch_generated_image_sync(generated_image_url: str) -> Image.Image:
    url = _resolve_generated_image_url(generated_image_url)
    with httpx.Client(timeout=30) as client:
        response = client.get(url)
        response.raise_for_status()
        return _decode_generated_image(response.content)
