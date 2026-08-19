import os

from fastapi.testclient import TestClient

from app.backend.main import app
from app.backend.services import auth, store


client = TestClient(app)


def setup_function():
    store.reset_for_tests()

    auth.create_customer(
        "CUS-0001",
        "테스트 회사 A",
        "1234",
    )
    auth.create_customer(
        "CUS-0002",
        "테스트 회사 B",
        "5678",
    )

    os.environ["ADMIN_API_KEY"] = "test-admin-key"


def _login_headers(customer_id: str, pin: str) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/login",
        json={
            "customer_id": customer_id,
            "pin": pin,
        },
    )

    assert response.status_code == 200

    token = response.json()["token"]

    return {
        "Authorization": f"Bearer {token}",
    }


def test_create_inquiry():
    headers = _login_headers("CUS-0001", "1234")

    response = client.post(
        "/api/v1/inquiries",
        headers=headers,
        json={
            "title": "이미지 생성 문의",
            "content": "이미지 비율 관련 문의입니다.",
        },
    )

    assert response.status_code == 201

    data = response.json()

    assert data["customer_id"] == "CUS-0001"
    assert data["company_name"] == "테스트 회사 A"
    assert data["status"] == "waiting"
    assert data["answer"] is None
    assert data["inquiry_id"].startswith("inq_")


def test_customer_sees_only_own_inquiries():
    headers_a = _login_headers("CUS-0001", "1234")
    headers_b = _login_headers("CUS-0002", "5678")

    client.post(
        "/api/v1/inquiries",
        headers=headers_a,
        json={
            "title": "A 문의",
            "content": "A 내용",
        },
    )

    client.post(
        "/api/v1/inquiries",
        headers=headers_b,
        json={
            "title": "B 문의",
            "content": "B 내용",
        },
    )

    response = client.get(
        "/api/v1/inquiries",
        headers=headers_a,
    )

    assert response.status_code == 200

    inquiries = response.json()

    assert len(inquiries) == 1
    assert inquiries[0]["title"] == "A 문의"


def test_other_customer_cannot_read_inquiry():
    headers_a = _login_headers("CUS-0001", "1234")
    headers_b = _login_headers("CUS-0002", "5678")

    create_response = client.post(
        "/api/v1/inquiries",
        headers=headers_a,
        json={
            "title": "비공개 문의",
            "content": "A의 문의입니다.",
        },
    )

    inquiry_id = create_response.json()["inquiry_id"]

    response = client.get(
        f"/api/v1/inquiries/{inquiry_id}",
        headers=headers_b,
    )

    assert response.status_code == 404


def test_admin_key_required_to_list_all_inquiries():
    response = client.get(
        "/api/v1/admin/inquiries",
    )

    assert response.status_code == 403


def test_admin_can_answer_inquiry():
    headers = _login_headers("CUS-0001", "1234")

    create_response = client.post(
        "/api/v1/inquiries",
        headers=headers,
        json={
            "title": "답변 테스트",
            "content": "운영자 답변이 필요합니다.",
        },
    )

    inquiry_id = create_response.json()["inquiry_id"]

    answer_response = client.post(
        f"/api/v1/admin/inquiries/{inquiry_id}/answer",
        headers={
            "X-Admin-Key": "test-admin-key",
        },
        json={
            "answer": "운영자 답변입니다.",
        },
    )

    assert answer_response.status_code == 200

    data = answer_response.json()

    assert data["status"] == "answered"
    assert data["answer"] == "운영자 답변입니다."
    assert data["answered_at"] is not None


def test_customer_can_read_answer_after_admin_reply():
    headers = _login_headers("CUS-0001", "1234")

    create_response = client.post(
        "/api/v1/inquiries",
        headers=headers,
        json={
            "title": "답변 확인 테스트",
            "content": "답변 확인용 문의입니다.",
        },
    )

    inquiry_id = create_response.json()["inquiry_id"]

    client.post(
        f"/api/v1/admin/inquiries/{inquiry_id}/answer",
        headers={
            "X-Admin-Key": "test-admin-key",
        },
        json={
            "answer": "답변 완료",
        },
    )

    response = client.get(
        f"/api/v1/inquiries/{inquiry_id}",
        headers=headers,
    )

    assert response.status_code == 200

    data = response.json()

    assert data["status"] == "answered"
    assert data["answer"] == "답변 완료"