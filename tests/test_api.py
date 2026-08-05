import io
import shutil
import time
import uuid
import zipfile

import pytest
from fastapi.testclient import TestClient

from app.backend.main import app
from app.backend.services import store, overlay
from app.backend.services.store import PRODUCTS, JOBS, HISTORY
from app.backend.schemas.generation import GenerationRequest
from app.backend.api.generations import build_generation_plan

client = TestClient(app)


@pytest.fixture(autouse=True)
def _clear_store(tmp_path, monkeypatch):
    """
    실제 개발용 데이터(data/store.json, data/outputs/의 기존 파일)를 절대 건드리지 않도록 격리한다.
    - store.STORE_PATH: pytest의 tmp_path(테스트 종료 시 자동 정리되는 임시 디렉터리)로 리다이렉트.
      완전히 별도 파일이라 실제 data/store.json은 읽지도 쓰지도 않는다.
    - overlay.OUTPUT_DIR: data/outputs/ 자체가 아니라 그 "하위"의 테스트 전용 서브폴더로 리다이렉트.
      정적 파일 서빙(/files/...)은 data/ 디렉터리 마운트에 묶여있어 완전히 밖으로 뺄 수 없기 때문에,
      최소한 기존 데모 파일이 있는 data/outputs/ 최상위는 안 건드리고 서브폴더만 만들고 지운다.
    """
    monkeypatch.setattr(store, "STORE_PATH", tmp_path / "store.json")

    test_output_dir = overlay.OUTPUT_DIR / f"_pytest_{uuid.uuid4().hex[:8]}"
    monkeypatch.setattr(overlay, "OUTPUT_DIR", test_output_dir)

    PRODUCTS.clear()
    JOBS.clear()
    HISTORY.clear()
    yield
    if test_output_dir.exists():
        shutil.rmtree(test_output_dir)  # 테스트가 만든 서브폴더만 삭제 - 형제 파일은 안 건드림
    PRODUCTS.clear()
    JOBS.clear()
    HISTORY.clear()


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
    """
    PATCH /copy는 아직 실제로 구현되지 않았음을 솔직하게 501로 알린다
    (문구가 이미 PNG에 구워져 있어서, 지금 200을 주면 프론트가 잘못 믿고 붙을 수 있음).
    job_id 자체는 일관되게 처리되는지(존재하는 job은 501, 없는 job은 404)만 확인한다.
    """
    pid = _upload_product()
    r = client.post("/api/v1/generations", json={"product_id": pid, "time_slots": ["morning"]})
    job_id = r.json()["job_id"]

    patch = client.patch(f"/api/v1/generations/{job_id}/copy",
                          json={"headline": "새 헤드라인", "subcopy": "새 서브카피"})
    assert patch.status_code == 501

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


def test_generate_rejects_duplicate_while_job_in_progress():
    """중복 생성 요청 방지 — 같은 상품에 진행 중(queued/processing)인 job이 있으면 409."""
    pid = _upload_product()
    JOBS["job_fake_inprogress"] = {
        "status": "processing",
        "progress": 10,
        "current_step": None,
        "completed_count": 0,
        "total_count": 4,
        "estimated_seconds": 60,
        "product_id": pid,
        "request": {},
        "result": None,
        "error_message": None,
    }

    r = client.post("/api/v1/generations", json={"product_id": pid, "time_slots": ["morning"]})
    assert r.status_code == 409


def test_generate_allows_new_request_after_previous_completed():
    """이전 job이 completed/failed면 중복 방지에 안 걸리고 새로 생성 가능해야 한다."""
    pid = _upload_product()
    JOBS["job_fake_done"] = {
        "status": "completed",
        "progress": 100,
        "current_step": None,
        "completed_count": 4,
        "total_count": 4,
        "estimated_seconds": 60,
        "product_id": pid,
        "request": {},
        "result": [],
        "error_message": None,
    }

    r = client.post("/api/v1/generations", json={"product_id": pid, "time_slots": ["morning"]})
    assert r.status_code == 202


def test_download_one_returns_png_file():
    pid = _upload_product()
    r = client.post("/api/v1/generations", json={"product_id": pid, "time_slots": ["morning"]})
    job_id = r.json()["job_id"]
    time.sleep(0.5)

    result = client.get(f"/api/v1/generations/{job_id}").json()
    tone = result["results"][0]["tone"]

    resp = client.get(f"/api/v1/download/{job_id}", params={"tone": tone, "output_format": "thumbnail"})
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "image/png"


def test_download_one_404_for_unknown_job():
    resp = client.get("/api/v1/download/job_nope", params={"tone": "emotional", "output_format": "thumbnail"})
    assert resp.status_code == 404


def test_download_one_404_for_unfinished_job():
    pid = _upload_product()
    r = client.post("/api/v1/generations", json={"product_id": pid, "time_slots": ["morning"]})
    job_id = r.json()["job_id"]
    # 완료 기다리지 않고 바로 다운로드 시도
    JOBS[job_id]["status"] = "processing"  # 확실하게 미완료 상태로 고정
    resp = client.get(f"/api/v1/download/{job_id}", params={"tone": "emotional", "output_format": "thumbnail"})
    assert resp.status_code == 409


def test_download_all_returns_zip_with_all_images():
    pid = _upload_product()
    r = client.post("/api/v1/generations", json={"product_id": pid, "time_slots": ["morning"]})
    job_id = r.json()["job_id"]
    time.sleep(0.5)

    resp = client.get(f"/api/v1/download/{job_id}/all")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/zip"

    zf = zipfile.ZipFile(io.BytesIO(resp.content))
    names = zf.namelist()
    # 톤 4종 x 규격 3종 = 12개 파일
    assert len(names) == 12


def test_download_rejects_path_traversal_attempt():
    """_url_to_path가 data/outputs/ 밖으로 나가는 경로를 거부하는지 (방어적 검증)."""
    from app.backend.api.download import _url_to_path
    from fastapi import HTTPException

    try:
        _url_to_path("/files/../../etc/passwd")
        assert False, "예외가 발생했어야 함"
    except HTTPException as e:
        assert e.status_code == 400


def test_exposure_returns_404_for_unknown_product():
    resp = client.get("/api/v1/exposure/prd_doesnotexist")
    assert resp.status_code == 404


def test_exposure_returns_unavailable_when_no_matching_generation():
    """상품은 있는데 해당 시간대로 생성된 게 없으면 available=False."""
    pid = _upload_product()
    resp = client.get(f"/api/v1/exposure/{pid}", params={"at": "2026-08-05T07:00:00+09:00"})
    assert resp.status_code == 200
    assert resp.json()["available"] is False
    assert resp.json()["time_slot"] == "morning"


def test_exposure_accepts_at_query_param_for_demo():
    """?at= 파라미터로 임의 시각 기준 조회 가능 (발표 데모용)."""
    pid = _upload_product()
    r = client.post("/api/v1/generations", json={"product_id": pid, "time_slots": ["evening"]})
    time.sleep(0.5)

    resp = client.get(f"/api/v1/exposure/{pid}", params={"at": "2026-08-05T20:30:00+09:00"})
    assert resp.status_code == 200
    assert resp.json()["time_slot"] == "evening"
    assert resp.json()["available"] is True


def test_download_all_returns_404_when_no_files_exist_on_disk():
    """디스크에서 파일이 사라진 경우 빈 ZIP을 200으로 조용히 주면 안 되고 404여야 한다."""
    pid = _upload_product()
    r = client.post("/api/v1/generations", json={"product_id": pid, "time_slots": ["morning"]})
    job_id = r.json()["job_id"]
    time.sleep(0.5)

    # 결과는 completed인데, 디스크 파일을 강제로 지워서 "파일 없음" 상황을 재현
    result = client.get(f"/api/v1/generations/{job_id}").json()
    for tone_result in result["results"]:
        for url in tone_result["images"].values():
            from app.backend.api.download import _url_to_path
            path = _url_to_path(url)
            if path.exists():
                path.unlink()

    resp = client.get(f"/api/v1/download/{job_id}/all")
    assert resp.status_code == 404


def test_download_all_zip_does_not_collide_across_multiple_time_slots():
    """시간대 2개 이상인 job에서 ZIP arcname이 tone_format만 쓰면 서로 다른 시간대
    파일이 같은 이름으로 겹쳐써져서 절반이 유실된다 - time_slot을 arcname에 포함해야 한다."""
    pid = _upload_product()
    r = client.post("/api/v1/generations", json={"product_id": pid, "time_slots": ["morning", "evening"]})
    job_id = r.json()["job_id"]
    time.sleep(0.5)

    resp = client.get(f"/api/v1/download/{job_id}/all")
    assert resp.status_code == 200
    zf = zipfile.ZipFile(io.BytesIO(resp.content))
    names = zf.namelist()
    # 시간대 2 x 톤 4 x 규격 3 = 24개 파일이 전부 유니크한 이름으로 있어야 함
    assert len(names) == 24
    assert len(set(names)) == 24  # 중복 없음


def test_download_one_with_time_slot_returns_correct_slot():
    """time_slot을 지정하면 그 시간대의 이미지를 정확히 받아야 한다 (여러 시간대가 섞인 job)."""
    pid = _upload_product()
    r = client.post("/api/v1/generations", json={"product_id": pid, "time_slots": ["morning", "evening"]})
    job_id = r.json()["job_id"]
    time.sleep(0.5)

    result = client.get(f"/api/v1/generations/{job_id}").json()
    tone = result["results"][0]["tone"]

    resp = client.get(f"/api/v1/download/{job_id}", params={
        "tone": tone, "output_format": "thumbnail", "time_slot": "evening",
    })
    assert resp.status_code == 200
    assert "evening" in resp.headers["content-disposition"]
