import asyncio
import io
import shutil
import uuid

import pytest
from PIL import Image

from app.backend.services import generation_service as gs
from app.backend.services import model_server_client
from app.backend.services import overlay
from app.backend.schemas.generation import GenerationRequest
from app.backend.services.store import JOBS, PRODUCTS


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
        "total_count": len(time_slots) * 4,
        "current_step": None,
    }
    req = GenerationRequest(product_id=product_id, time_slots=list(time_slots))
    return req, PRODUCTS[product_id]


def test_model_server_generation_success(monkeypatch):
    async def fake_request_generation(**kwargs):
        return {
            "status": "done",
            "generated_image_url": "http://fake-model-server/bg.png",
            "product_preserved": True,
            "gen_time_sec": 1.2,
        }

    monkeypatch.setattr(model_server_client, "request_generation", fake_request_generation)
    monkeypatch.setattr(model_server_client, "httpx", type("M", (), {"AsyncClient": _FakeAsyncClient}))
    monkeypatch.setattr(model_server_client, "MODEL_SERVER_URL", "http://fake-model-server")

    req, product = _setup_job_and_product(time_slots=("morning",))
    service = gs.ModelServerGenerationService()

    results = asyncio.run(service.generate("job_test", req, product))

    assert len(results) == 4  # 톤 4종
    for r in results:
        assert r.result_id.startswith("res_")
        assert len(r.images) == len(req.output_formats)
    assert JOBS["job_test"]["completed_count"] == 4
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
