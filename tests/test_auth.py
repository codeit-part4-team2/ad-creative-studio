import io
import os

import pytest
from fastapi.testclient import TestClient

from app.backend.main import app
from app.backend.services import auth

client = TestClient(app)


@pytest.fixture(autouse=True)
def _clear_auth():
    auth.CUSTOMERS.clear()
    auth.SESSIONS.clear()
    auth.reset_rate_limit_for_tests()
    yield
    auth.CUSTOMERS.clear()
    auth.SESSIONS.clear()
    auth.reset_rate_limit_for_tests()


def _upload_product_as(token: str, name="테스트상품"):
    files = {"image": ("p.png", io.BytesIO(b"fakebytes"), "image/png")}
    data = {"product_name": name, "price": 10000}
    r = client.post(
        "/api/v1/products", files=files, data=data,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    return r.json()["product_id"]


# ── 관리자 고객사 생성 ──────────────────────────────────────

def test_admin_create_customer_requires_admin_key(monkeypatch):
    monkeypatch.setenv("ADMIN_API_KEY", "secret123")
    r = client.post("/api/v1/admin/customers", json={
        "customer_id": "CUS-0001", "company_name": "ABC전자", "pin": "123456",
    })
    assert r.status_code == 403


def test_admin_create_customer_succeeds_with_correct_key(monkeypatch):
    monkeypatch.setenv("ADMIN_API_KEY", "secret123")
    r = client.post(
        "/api/v1/admin/customers",
        json={"customer_id": "CUS-0001", "company_name": "ABC전자", "pin": "123456"},
        headers={"X-Admin-Key": "secret123"},
    )
    assert r.status_code == 201
    assert r.json()["customer_id"] == "CUS-0001"


def test_admin_create_customer_blocked_when_no_admin_key_configured(monkeypatch):
    monkeypatch.delenv("ADMIN_API_KEY", raising=False)
    r = client.post(
        "/api/v1/admin/customers",
        json={"customer_id": "CUS-0001", "company_name": "ABC전자", "pin": "123456"},
        headers={"X-Admin-Key": "anything"},
    )
    assert r.status_code == 403


def test_admin_create_customer_rejects_duplicate_id(monkeypatch):
    monkeypatch.setenv("ADMIN_API_KEY", "secret123")
    body = {"customer_id": "CUS-0001", "company_name": "ABC전자", "pin": "123456"}
    client.post("/api/v1/admin/customers", json=body, headers={"X-Admin-Key": "secret123"})
    r = client.post("/api/v1/admin/customers", json=body, headers={"X-Admin-Key": "secret123"})
    assert r.status_code == 409


# ── 로그인 ──────────────────────────────────────────────

def test_login_succeeds_with_correct_pin():
    auth.create_customer("CUS-0001", "ABC전자", "123456")
    r = client.post("/api/v1/auth/login", json={"customer_id": "CUS-0001", "pin": "123456"})
    assert r.status_code == 200
    assert r.json()["customer"]["company_name"] == "ABC전자"
    assert r.json()["token"]


def test_login_fails_with_wrong_pin():
    auth.create_customer("CUS-0001", "ABC전자", "123456")
    r = client.post("/api/v1/auth/login", json={"customer_id": "CUS-0001", "pin": "000000"})
    assert r.status_code == 401


def test_login_fails_for_unknown_customer():
    r = client.post("/api/v1/auth/login", json={"customer_id": "CUS-9999", "pin": "123456"})
    assert r.status_code == 401


def test_login_fails_for_inactive_customer():
    auth.create_customer("CUS-0001", "ABC전자", "123456")
    auth.CUSTOMERS["CUS-0001"]["status"] = "suspended"
    r = client.post("/api/v1/auth/login", json={"customer_id": "CUS-0001", "pin": "123456"})
    assert r.status_code == 401


def test_pin_is_never_stored_in_plaintext():
    customer = auth.create_customer("CUS-0001", "ABC전자", "123456")
    assert "123456" not in customer["pin_hash"]
    assert customer["pin_hash"] != "123456"


# ── 인증 필요 endpoint 보호 ──────────────────────────────

def test_create_product_requires_login():
    files = {"image": ("p.png", io.BytesIO(b"fakebytes"), "image/png")}
    r = client.post("/api/v1/products", files=files, data={"product_name": "x", "price": 1000})
    assert r.status_code == 401


def test_create_product_rejects_invalid_token():
    files = {"image": ("p.png", io.BytesIO(b"fakebytes"), "image/png")}
    r = client.post(
        "/api/v1/products", files=files, data={"product_name": "x", "price": 1000},
        headers={"Authorization": "Bearer not-a-real-token"},
    )
    assert r.status_code == 401


def test_me_returns_logged_in_customer():
    auth.create_customer("CUS-0001", "ABC전자", "123456")
    token = auth.verify_login("CUS-0001", "123456")
    r = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["customer_id"] == "CUS-0001"


def test_logout_invalidates_token():
    auth.create_customer("CUS-0001", "ABC전자", "123456")
    token = auth.verify_login("CUS-0001", "123456")
    client.post("/api/v1/auth/logout", headers={"Authorization": f"Bearer {token}"})
    r = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401


# ── multi-tenant 데이터 격리 (핵심) ──────────────────────────

def test_customer_cannot_see_another_customers_products_via_generation():
    auth.create_customer("CUS-A", "A사", "111111")
    auth.create_customer("CUS-B", "B사", "222222")
    token_a = auth.verify_login("CUS-A", "111111")
    token_b = auth.verify_login("CUS-B", "222222")

    product_id = _upload_product_as(token_a)

    # B사 토큰으로 A사 상품에 대해 생성 요청 -> 404 (있는지 없는지도 안 알려줌)
    r = client.post(
        "/api/v1/generations",
        json={"product_id": product_id, "time_slots": ["morning"]},
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert r.status_code == 404


def test_customer_history_only_shows_own_entries(monkeypatch):
    from app.backend.services.store import HISTORY

    auth.create_customer("CUS-A", "A사", "111111")
    auth.create_customer("CUS-B", "B사", "222222")
    token_a = auth.verify_login("CUS-A", "111111")
    token_b = auth.verify_login("CUS-B", "222222")

    HISTORY.append({"customer_id": "CUS-A", "job_id": "job_a", "results": [], "favorite": False})
    HISTORY.append({"customer_id": "CUS-B", "job_id": "job_b", "results": [], "favorite": False})

    r_a = client.get("/api/v1/history", headers={"Authorization": f"Bearer {token_a}"})
    r_b = client.get("/api/v1/history", headers={"Authorization": f"Bearer {token_b}"})

    assert [h["job_id"] for h in r_a.json()] == ["job_a"]
    assert [h["job_id"] for h in r_b.json()] == ["job_b"]

    HISTORY.clear()


def test_customer_cannot_toggle_favorite_on_another_customers_entry():
    from app.backend.services.store import HISTORY

    auth.create_customer("CUS-A", "A사", "111111")
    auth.create_customer("CUS-B", "B사", "222222")
    token_b = auth.verify_login("CUS-B", "222222")

    HISTORY.append({"customer_id": "CUS-A", "job_id": "job_a", "results": [], "favorite": False})

    r = client.patch("/api/v1/history/job_a/favorite", headers={"Authorization": f"Bearer {token_b}"})
    assert r.status_code == 404

    HISTORY.clear()


# ── PR 리뷰 반영: 세션 재확인, rate limit, timing-safe login ──────────

def test_session_becomes_invalid_after_customer_suspended():
    """로그인 당시엔 active였어도, 관리자가 나중에 정지시키면 이미 있던 세션도 즉시 무효화돼야 한다."""
    auth.create_customer("CUS-0001", "ABC전자", "123456")
    token = auth.verify_login("CUS-0001", "123456")
    assert auth.resolve_session(token) is not None  # 정지 전엔 유효

    auth.CUSTOMERS["CUS-0001"]["status"] = "suspended"
    assert auth.resolve_session(token) is None  # 정지 후 같은 토큰이 즉시 무효


def test_login_is_rate_limited_after_repeated_failures():
    auth.create_customer("CUS-0001", "ABC전자", "123456")
    for _ in range(5):
        r = client.post("/api/v1/auth/login", json={"customer_id": "CUS-0001", "pin": "000000"})
        assert r.status_code == 401

    # 6번째부터는 PIN이 맞아도 rate limit에 걸려야 한다
    r = client.post("/api/v1/auth/login", json={"customer_id": "CUS-0001", "pin": "123456"})
    assert r.status_code == 429


def test_nonexistent_and_existing_customer_login_take_similar_time():
    """
    존재하지 않는 customer_id는 즉시 실패하고 존재하는 ID는 PBKDF2를 다 돌리면,
    응답시간 차이로 유효한 ID를 추측할 수 있다 - 둘 다 비슷한 시간이 걸려야 한다.
    절대 시간이 아니라 "존재 여부에 따른 뚜렷한 차이가 없는지"만 느슨하게 확인한다
    (CI 환경마다 절대 시간이 다르므로 배수 기준으로 비교).
    """
    import time as _time

    auth.create_customer("CUS-EXISTS", "ABC전자", "123456")

    start = _time.perf_counter()
    auth.verify_login("CUS-EXISTS", "wrong-pin")
    existing_duration = _time.perf_counter() - start

    start = _time.perf_counter()
    auth.verify_login("CUS-DOES-NOT-EXIST", "wrong-pin")
    missing_duration = _time.perf_counter() - start

    # PBKDF2 26만회가 압도적으로 오래 걸리는 연산이라, 존재 유무에 따른 분기가
    # 없다면 둘 다 비슷해야 한다 (5배 이상 차이 나면 timing attack에 다시 취약해진 것).
    assert missing_duration > existing_duration / 5
