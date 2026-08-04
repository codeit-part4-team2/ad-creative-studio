import io
import time

import pytest
from fastapi.testclient import TestClient

from app.backend.main import app
from app.backend.services.store import PRODUCTS, JOBS, HISTORY
from app.backend.schemas.generation import GenerationRequest
from app.backend.api.generations import build_generation_plan

client = TestClient(app)


@pytest.fixture(autouse=True)
def _clear_store():
    PRODUCTS.clear()
    JOBS.clear()
    HISTORY.clear()
    yield


def _upload_product(name="스팀 에어프라이어 5L"):
    files = {"image": ("p.png", io.BytesIO(b"fakebytes"), "image/png")}
    data = {"product_name": name, "price": 89000, "selling_points": "기름 없이,1인가구"}
    r = client.post("/api/v1/products", files=files, data=data)
    assert r.status_code == 200
    return r.json()["product_id"]


def test_generate_returns_404_for_unknown_product():
    r = client.post("/api/v1/generations", json={"product_id": "prd_nope", "time_slots": ["morning"]})
    assert r.status_code == 404


def test_generate_rejects_empty_time_slots():
    pid = _upload_product()
    r = client.post("/api/v1/generations", json={"product_id": pid, "time_slots": []})
    assert r.status_code == 400


def test_generate_rejects_more_than_max_time_slots():
    pid = _upload_product()
    r = client.post("/api/v1/generations", json={
        "product_id": pid,
        "time_slots": ["morning", "commute_am", "afternoon", "commute_pm"],
    })
    assert r.status_code == 400


def test_generate_returns_202_and_expected_total_count():
    pid = _upload_product()
    r = client.post("/api/v1/generations", json={"product_id": pid, "time_slots": ["morning", "evening"]})
    assert r.status_code == 202
    job_id = r.json()["job_id"]

    # 톤 4종(기본값) x 시간대 2개 = 8 이어야 한다 (규격 곱하지 않음)
    time.sleep(0.5)  # BackgroundTasks 완료 대기
    status = client.get(f"/api/v1/jobs/{job_id}").json()
    assert status["total_count"] == 8


def test_output_formats_do_not_increase_model_generation_count():
    """출력 규격은 후처리 조건이라, 몇 개를 요청하든 실제 생성 계획(plan) 개수는 시간대x톤 그대로여야 한다."""
    product = {"product_name": "커피메이커", "price": 50000, "selling_points": []}

    req_one_format = GenerationRequest(
        product_id="x", time_slots=["morning", "evening"], output_formats=["thumbnail"]
    )
    req_three_formats = GenerationRequest(
        product_id="x", time_slots=["morning", "evening"],
        output_formats=["thumbnail", "detail_banner", "sns_card"],
    )

    plan_one = build_generation_plan(req_one_format, product)
    plan_three = build_generation_plan(req_three_formats, product)

    # 시간대 2 x 톤 4(기본값) = 8 로 동일해야 함
    assert len(plan_one) == 8
    assert len(plan_three) == 8
    assert len(plan_one) == len(plan_three)


def test_full_flow_populates_history():
    pid = _upload_product()
    r = client.post("/api/v1/generations", json={"product_id": pid, "time_slots": ["commute_am"]})
    job_id = r.json()["job_id"]

    time.sleep(0.5)
    result = client.get(f"/api/v1/generations/{job_id}")
    assert result.status_code == 200
    assert len(result.json()["results"]) == 4  # 톤 4종

    history = client.get("/api/v1/history").json()
    assert any(h["job_id"] == job_id for h in history)


def test_copy_patch_uses_job_id_consistently():
    pid = _upload_product()
    r = client.post("/api/v1/generations", json={"product_id": pid, "time_slots": ["morning"]})
    job_id = r.json()["job_id"]

    patch = client.patch(f"/api/v1/generations/{job_id}/copy",
                          json={"headline": "새 헤드라인", "subcopy": "새 서브카피"})
    assert patch.status_code == 200

    patch_missing = client.patch("/api/v1/generations/job_doesnotexist/copy",
                                  json={"headline": "x", "subcopy": "y"})
    assert patch_missing.status_code == 404
