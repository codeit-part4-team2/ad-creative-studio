from __future__ import annotations

import asyncio
from typing import get_args

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.backend.services import model_server_client
from app.prompt.schemas import (
    TimeSlotLiteral as AppTimeSlotLiteral,
    ToneLiteral as AppToneLiteral,
)
from model_server.main import OUTPUT_DIR, _resolve_output_dir, app, get_engine
from model_server.schemas import (
    TimeSlotLiteral as ModelTimeSlotLiteral,
    ToneLiteral as ModelToneLiteral,
)


class _JsonResponse:
    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, object]:
        return {"status": "done", "generated_image_url": "/files/outputs/result.png"}


def test_backend_resolves_relative_product_image_for_remote_model_server(monkeypatch) -> None:
    posted: list[tuple[str, dict[str, object]]] = []

    class _Client:
        def __init__(self, *args: object, **kwargs: object) -> None:
            pass

        async def __aenter__(self) -> "_Client":
            return self

        async def __aexit__(self, *args: object) -> bool:
            return False

        async def post(self, url: str, *, json: dict[str, object]) -> _JsonResponse:
            posted.append((url, json))
            return _JsonResponse()

    monkeypatch.setattr(model_server_client.httpx, "AsyncClient", _Client)
    monkeypatch.setattr(model_server_client, "MODEL_SERVER_URL", "http://model.internal:8001")
    monkeypatch.setattr(model_server_client, "BACKEND_PUBLIC_URL", "http://backend.internal:8000")

    asyncio.run(model_server_client.request_generation(
        product_id="prd_1",
        product_image_url="/files/uploads/prd_1.png",
        tone="premium",
        image_prompt="premium studio",
        negative_prompt="blurry",
        time_slot="commute_am",
    ))

    assert posted[0][0] == "http://model.internal:8001/infer"
    assert posted[0][1]["product_image_url"] == "http://backend.internal:8000/files/uploads/prd_1.png"


def test_backend_rejects_absolute_product_url_from_another_origin(monkeypatch) -> None:
    monkeypatch.setattr(
        model_server_client,
        "BACKEND_PUBLIC_URL",
        "http://backend.internal:8000",
    )

    with pytest.raises(ValueError, match="BACKEND_PUBLIC_URL origin"):
        model_server_client._resolve_product_image_url(
            "http://169.254.169.254/latest/meta-data/"
        )


def test_backend_accepts_absolute_product_url_from_its_own_origin(monkeypatch) -> None:
    monkeypatch.setattr(
        model_server_client,
        "BACKEND_PUBLIC_URL",
        "http://backend.internal:8000",
    )

    resolved = model_server_client._resolve_product_image_url(
        "http://backend.internal:8000/files/uploads/prd_1.png"
    )

    assert resolved == "http://backend.internal:8000/files/uploads/prd_1.png"


def test_model_server_time_slots_match_backend_contract() -> None:
    assert set(get_args(ModelTimeSlotLiteral)) == set(get_args(AppTimeSlotLiteral))


def test_model_server_tones_match_backend_contract() -> None:
    assert set(get_args(ModelToneLiteral)) == set(get_args(AppToneLiteral))


def test_relative_model_output_dir_is_resolved_from_service_workdir(tmp_path) -> None:
    resolved = _resolve_output_dir(
        {"MODEL_OUTPUT_DIR": "runtime/model-outputs"},
        base_dir=tmp_path,
    )

    assert resolved == (tmp_path / "runtime" / "model-outputs").resolve()


def test_model_server_serves_generated_output_file() -> None:
    filename = "_pytest_model_server_static.png"
    output = OUTPUT_DIR / filename
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (2, 2), "red").save(output)
    try:
        response = TestClient(app).get(f"/files/outputs/{filename}")
    finally:
        output.unlink(missing_ok=True)

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"


def test_warmup_loads_pipeline_before_first_inference() -> None:
    class _WarmableEngine:
        model_loaded = False

        def load_model(self) -> None:
            self.model_loaded = True

    engine = _WarmableEngine()
    app.dependency_overrides[get_engine] = lambda: engine
    try:
        response = TestClient(app).post("/warmup")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "model_loaded": True}
