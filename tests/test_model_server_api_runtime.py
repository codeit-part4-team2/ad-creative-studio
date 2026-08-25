from __future__ import annotations

from fastapi.testclient import TestClient

from model_server.inference import InferenceResult
from model_server.main import app, get_engine


class _SuccessfulEngine:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def run(self, **kwargs: object) -> InferenceResult:
        self.calls.append(kwargs)
        return InferenceResult(
            status="done",
            generated_image_url="/files/outputs/premium.png",
            product_preserved=True,
            preservation_method="source_alpha_composite",
            gen_time_sec=0.5,
            gpu_queue_wait_sec=0.05,
            stage_times_sec={
                "gpu_queue_wait": 0.05,
                "generate": 0.4,
                "composite": 0.1,
            },
            cache_hit=False,
            model_profile="fast_composite",
            num_inference_steps=4,
            background_size=768,
            output_size=1024,
            output_format="thumbnail",
            background_width=768,
            background_height=768,
            output_width=1024,
            output_height=1024,
            peak_vram_gb=3.0,
        )


class _FailingEngine:
    def run(self, **_: object) -> InferenceResult:
        raise RuntimeError("secret internal path and token")


class _FailingWarmupEngine:
    model_loaded = False

    def load_model(self) -> None:
        raise RuntimeError("secret model repository and access token")


def _payload() -> dict[str, str]:
    return {
        "product_id": "p-1",
        "product_image_url": "https://images.example/product.png",
        "tone": "premium",
        "image_prompt": "premium marble studio",
        "negative_prompt": "blurry",
        "time_slot": "evening",
    }


def test_infer_returns_backward_compatible_fields_and_per_stage_timings() -> None:
    engine = _SuccessfulEngine()
    app.dependency_overrides[get_engine] = lambda: engine
    try:
        response = TestClient(app).post("/infer", json=_payload())
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "done"
    assert body["generated_image_url"] == "/files/outputs/premium.png"
    assert body["gen_time_sec"] == 0.5
    assert body["gpu_queue_wait_sec"] == 0.05
    assert body["stage_times_sec"] == {
        "gpu_queue_wait": 0.05,
        "generate": 0.4,
        "composite": 0.1,
    }
    assert body["num_inference_steps"] == 4
    assert body["background_size"] == 768
    assert body["output_size"] == 1024
    assert body["output_format"] == "thumbnail"
    assert body["background_width"] == 768
    assert body["background_height"] == 768
    assert body["output_width"] == 1024
    assert body["output_height"] == 1024
    assert engine.calls[0]["output_format"] == "thumbnail"
    assert engine.calls[0]["time_slot"] == "evening"
    assert engine.calls[0]["scene_purpose"] == "standard"


def test_infer_forwards_an_explicit_native_ratio() -> None:
    engine = _SuccessfulEngine()
    app.dependency_overrides[get_engine] = lambda: engine
    payload = {**_payload(), "output_format": "story_vertical"}
    try:
        response = TestClient(app).post("/infer", json=payload)
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert engine.calls[0]["output_format"] == "story_vertical"


def test_infer_forwards_an_explicit_shorts_scene_purpose() -> None:
    engine = _SuccessfulEngine()
    app.dependency_overrides[get_engine] = lambda: engine
    payload = {**_payload(), "scene_purpose": "self_aware"}
    try:
        response = TestClient(app).post("/infer", json=payload)
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert engine.calls[0]["scene_purpose"] == "self_aware"


def test_infer_rejects_unknown_scene_purpose() -> None:
    engine = _SuccessfulEngine()
    app.dependency_overrides[get_engine] = lambda: engine
    payload = {**_payload(), "scene_purpose": "hero"}
    try:
        response = TestClient(app).post("/infer", json=payload)
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422
    assert engine.calls == []


def test_infer_rejects_legacy_detail_banner_for_new_generation() -> None:
    engine = _SuccessfulEngine()
    app.dependency_overrides[get_engine] = lambda: engine
    payload = {**_payload(), "output_format": "detail_banner"}
    try:
        response = TestClient(app).post("/infer", json=payload)
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422
    assert engine.calls == []


def test_infer_failure_does_not_expose_internal_exception_text() -> None:
    app.dependency_overrides[get_engine] = lambda: _FailingEngine()
    try:
        response = TestClient(app).post("/infer", json=_payload())
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "failed"
    assert body["error_message"] == "inference_failed"
    assert "secret" not in response.text


def test_health_is_available_without_loading_model_weights() -> None:
    response = TestClient(app).get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "model_loaded": False}


def test_warmup_failure_returns_structured_error_without_internal_details() -> None:
    app.dependency_overrides[get_engine] = lambda: _FailingWarmupEngine()
    try:
        response = TestClient(app, raise_server_exceptions=False).post("/warmup")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {
        "status": "failed",
        "model_loaded": False,
        "error_message": "model_load_failed",
    }
    assert "secret" not in response.text
