from __future__ import annotations

from fastapi.testclient import TestClient

from model_server.inference import InferenceResult
from model_server.main import app, get_engine


class _SuccessfulEngine:
    def run(self, **_: object) -> InferenceResult:
        return InferenceResult(
            status="done",
            generated_image_url="/files/outputs/premium.png",
            product_preserved=True,
            preservation_method="source_alpha_composite",
            gen_time_sec=0.5,
            stage_times_sec={"generate": 0.4, "composite": 0.1},
            cache_hit=False,
            model_profile="fast_composite",
            num_inference_steps=4,
            peak_vram_gb=3.0,
        )


class _FailingEngine:
    def run(self, **_: object) -> InferenceResult:
        raise RuntimeError("secret internal path and token")


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
    app.dependency_overrides[get_engine] = lambda: _SuccessfulEngine()
    try:
        response = TestClient(app).post("/infer", json=_payload())
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "done"
    assert body["generated_image_url"] == "/files/outputs/premium.png"
    assert body["gen_time_sec"] == 0.5
    assert body["stage_times_sec"] == {"generate": 0.4, "composite": 0.1}
    assert body["num_inference_steps"] == 4


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
