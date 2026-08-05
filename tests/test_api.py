import io
import shutil
import time

import pytest
from fastapi.testclient import TestClient

from app.backend.main import app
from app.backend.services.store import PRODUCTS, JOBS, HISTORY
from app.backend.services.overlay import OUTPUT_DIR
from app.backend.schemas.generation import GenerationRequest
from app.backend.api.generations import build_generation_plan

client = TestClient(app)


@pytest.fixture(autouse=True)
def _clear_store():
    PRODUCTS.clear()
    JOBS.clear()
    HISTORY.clear()
    yield
    if OUTPUT_DIR.exists():
        shutil.rmtree(OUTPUT_DIR)


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


def test_favorite_toggle_flow():
    """S3 — 생성 이력 즐겨찾기 토글."""
    pid = _upload_product()
    r = client.post("/api/v1/generations", json={"product_id": pid, "time_slots": ["morning"]})
    job_id = r.json()["job_id"]
    time.sleep(0.5)

    history = client.get("/api/v1/history").json()
    entry = next(h for h in history if h["job_id"] == job_id)
    assert entry["favorite"] is False  # 기본값

    toggled = client.patch(f"/api/v1/history/{job_id}/favorite")
    assert toggled.status_code == 200
    assert toggled.json()["favorite"] is True

    favorites_only = client.get("/api/v1/history", params={"favorite_only": True}).json()
    assert any(h["job_id"] == job_id for h in favorites_only)

    # 다시 토글하면 꺼짐
    toggled_again = client.patch(f"/api/v1/history/{job_id}/favorite")
    assert toggled_again.json()["favorite"] is False

    favorites_only_after = client.get("/api/v1/history", params={"favorite_only": True}).json()
    assert not any(h["job_id"] == job_id for h in favorites_only_after)


def test_favorite_toggle_404_for_unknown_job():
    resp = client.patch("/api/v1/history/job_doesnotexist/favorite")
    assert resp.status_code == 404


def test_generation_result_images_are_real_files_not_mock_url():
    """M3+S2 — 규격별로 실제 오버레이 이미지가 생성되는지 (더 이상 placehold.co mock 아님)."""
    pid = _upload_product()
    r = client.post("/api/v1/generations", json={"product_id": pid, "time_slots": ["evening"]})
    job_id = r.json()["job_id"]
    time.sleep(0.5)

    result = client.get(f"/api/v1/generations/{job_id}").json()
    first_tone = result["results"][0]
    assert "placehold.co" not in str(first_tone["images"])
    for fmt, url in first_tone["images"].items():
        assert url.startswith("/files/outputs/")
        served = client.get(url)
        assert served.status_code == 200  # 정적 서빙으로 실제 열림
