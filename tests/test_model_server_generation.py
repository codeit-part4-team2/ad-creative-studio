import asyncio
import io
import shutil
import uuid
from pathlib import Path

import pytest
from PIL import Image

from app.backend.services import generation_service as gs
from app.backend.services import model_server_client
from app.backend.services import overlay
from app.backend.schemas.generation import GenerationRequest
from app.backend.services.store import JOBS, PRODUCTS
from app.image_presets import get_image_preset


def _tiny_png_bytes() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (64, 64), (200, 100, 50)).save(buf, format="PNG")
    return buf.getvalue()


class _FakeResponse:
    def __init__(self, content: bytes):
        self.content = content

    def raise_for_status(self):
        pass


class _FakeAsyncClient:
    """httpx.AsyncClient(timeout=...) as client: await client.get(url) 를 흉내."""
    def __init__(self, *a, **k):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def get(self, url):
        return _FakeResponse(_tiny_png_bytes())


@pytest.fixture(autouse=True)
def _clear(monkeypatch):
    # generate_and_save는 OUTPUT_DIR이 data/outputs/ 하위여야 하므로(정적 서빙 경계),
    # tmp_path가 아니라 실제 OUTPUT_DIR 밑의 격리된 서브폴더를 쓴다 (기존 테스트들과 동일 패턴).
    test_output_dir = overlay.OUTPUT_DIR / f"_pytest_{uuid.uuid4().hex[:8]}"
    monkeypatch.setattr(overlay, "OUTPUT_DIR", test_output_dir)

    JOBS.clear()
    PRODUCTS.clear()
    yield
    if test_output_dir.exists():
        shutil.rmtree(test_output_dir)
    JOBS.clear()
    PRODUCTS.clear()


def _setup_job_and_product(job_id="job_test", product_id="prd_test", time_slots=("morning",)):
    req = GenerationRequest(product_id=product_id, time_slots=list(time_slots))
    PRODUCTS[product_id] = {
        "product_name": "테스트 상품",
        "selling_points": [],
        "image_url": "/files/uploads/prd_test.png",
        "image_path": "data/uploads/prd_test.png",
    }
    JOBS[job_id] = {
        "status": "processing",
        "progress": 0,
        "completed_count": 0,
        "total_count": len(time_slots) * len(req.tones) * len(req.output_formats),
        "current_step": None,
    }
    return req, PRODUCTS[product_id]


def test_generation_payload_includes_the_selected_native_ratio(monkeypatch):
    monkeypatch.setattr(
        model_server_client,
        "BACKEND_PUBLIC_URL",
        "http://backend.internal:8000",
    )

    payload = model_server_client._generation_payload(
        "p-1",
        "/files/uploads/p-1.png",
        "modern",
        "clean studio",
        None,
        "morning",
        "sns_card",
    )

    assert payload["output_format"] == "sns_card"


def test_model_server_generation_success(monkeypatch):
    async def fake_request_generation(**kwargs):
        output_format = str(kwargs["output_format"])
        return {
            "status": "done",
            "generated_image_url": f"http://fake-model-server/{output_format}.png",
            "product_preserved": True,
            "gen_time_sec": 1.2,
        }

    async def fake_fetch_generated_image(url: str) -> Image.Image:
        output_format = Path(url).stem
        return Image.new("RGB", get_image_preset(output_format).composite_size, "green")

    monkeypatch.setattr(model_server_client, "request_generation", fake_request_generation)
    monkeypatch.setattr(
        model_server_client,
        "fetch_generated_image",
        fake_fetch_generated_image,
    )
    monkeypatch.setattr(model_server_client, "MODEL_SERVER_URL", "http://fake-model-server")

    req, product = _setup_job_and_product(time_slots=("morning", "commute_pm"))
    service = gs.ModelServerGenerationService()

    results = asyncio.run(service.generate("job_test", req, product))

    assert len(results) == 8  # 시간대 2종 x 톤 4종
    for r in results:
        assert r.result_id.startswith("res_")
        assert len(r.images) == len(req.output_formats)
        if r.time_slot == "morning":
            assert r.source_image_url is None
            continue
        assert r.time_slot == "commute_pm"
        assert r.source_image_url is not None
    assert JOBS["job_test"]["completed_count"] == 16
    assert JOBS["job_test"]["progress"] == 100


def test_model_server_generation_runs_two_ratios_in_order_and_saves_vertical_source(
    monkeypatch,
):
    requested_formats: list[str] = []

    async def fake_request_generation(**kwargs):
        output_format = str(kwargs["output_format"])
        requested_formats.append(output_format)
        return {
            "status": "done",
            "generated_image_url": f"/files/outputs/{output_format}.png",
            "product_preserved": True,
            "gen_time_sec": 1.2,
        }

    async def fake_fetch_generated_image(url: str) -> Image.Image:
        if "story_vertical" in url:
            return Image.new("RGB", (720, 1280), (10, 20, 30))
        return Image.new("RGB", (896, 1120), (40, 50, 60))

    monkeypatch.setattr(
        model_server_client,
        "request_generation",
        fake_request_generation,
    )
    monkeypatch.setattr(
        model_server_client,
        "fetch_generated_image",
        fake_fetch_generated_image,
    )

    req, product = _setup_job_and_product(time_slots=("commute_pm",))
    req = req.model_copy(
        update={
            "tones": ["modern"],
            "output_formats": ["sns_card", "story_vertical"],
        }
    )
    JOBS["job_test"]["total_count"] = 2

    [result] = asyncio.run(
        gs.ModelServerGenerationService().generate("job_test", req, product)
    )

    assert requested_formats == ["sns_card", "story_vertical"]
    assert list(result.images) == ["sns_card", "story_vertical"]
    assert result.source_image_url is not None
    source_path = Path("data") / result.source_image_url.removeprefix("/files/")
    with Image.open(source_path) as source:
        assert source.size == (720, 1280)
        assert source.getpixel((0, 0)) == (10, 20, 30)
    assert JOBS["job_test"]["completed_count"] == 2
    assert JOBS["job_test"]["progress"] == 100


def test_model_server_generation_raises_on_failed_status(monkeypatch):
    async def fake_request_generation(**kwargs):
        return {"status": "failed", "error_message": "CUDA OOM", "generated_image_url": None}

    monkeypatch.setattr(model_server_client, "request_generation", fake_request_generation)

    req, product = _setup_job_and_product(time_slots=("morning",))
    service = gs.ModelServerGenerationService()

    with pytest.raises(RuntimeError, match="CUDA OOM"):
        asyncio.run(service.generate("job_test", req, product))


def test_fetch_generated_image_returns_pil_image(monkeypatch):
    monkeypatch.setattr(model_server_client, "httpx", type("M", (), {"AsyncClient": _FakeAsyncClient}))
    monkeypatch.setattr(model_server_client, "MODEL_SERVER_URL", "http://fake")
    image = asyncio.run(model_server_client.fetch_generated_image("http://fake/bg.png"))
    assert isinstance(image, Image.Image)
    assert image.mode == "RGB"


def test_fetch_generated_image_rejects_another_origin(monkeypatch):
    monkeypatch.setattr(model_server_client, "MODEL_SERVER_URL", "http://model.internal:8001")

    with pytest.raises(ValueError, match="MODEL_SERVER_URL origin"):
        asyncio.run(
            model_server_client.fetch_generated_image(
                "http://169.254.169.254/latest/meta-data/"
            )
        )


def test_fetch_generated_image_joins_relative_url_with_model_server_base(monkeypatch):
    captured_urls = []

    class _CapturingClient(_FakeAsyncClient):
        async def get(self, url):
            captured_urls.append(url)
            return _FakeResponse(_tiny_png_bytes())

    monkeypatch.setattr(model_server_client, "httpx", type("M", (), {"AsyncClient": _CapturingClient}))
    monkeypatch.setattr(model_server_client, "MODEL_SERVER_URL", "http://localhost:8001")

    asyncio.run(model_server_client.fetch_generated_image("/outputs/bg.png"))
    assert captured_urls == ["http://localhost:8001/outputs/bg.png"]
