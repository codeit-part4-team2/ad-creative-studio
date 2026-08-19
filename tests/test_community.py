from fastapi.testclient import TestClient

from app.backend.main import app
from app.backend.services import auth, store


client = TestClient(app)


def setup_function():
    store.reset_for_tests()
    auth.create_customer("CUS-0001", "테스트 회사", "1234")


def _login_headers():
    response = client.post(
        "/api/v1/auth/login",
        json={
            "customer_id": "CUS-0001",
            "pin": "1234",
        },
    )
    assert response.status_code == 200

    token = response.json()["token"]
    return {"Authorization": f"Bearer {token}"}


def test_create_community_post():
    headers = _login_headers()

    response = client.post(
        "/api/v1/community/posts",
        headers=headers,
        json={
            "category": "광고 팁",
            "title": "SNS 광고 질문",
            "content": "4:5와 1:1 중 어떤 비율을 많이 사용하시나요?",
        },
    )

    assert response.status_code == 201

    data = response.json()

    assert data["customer_id"] == "CUS-0001"
    assert data["company_name"] == "테스트 회사"
    assert data["category"] == "광고 팁"
    assert data["title"] == "SNS 광고 질문"
    assert data["comment_count"] == 0
    assert data["post_id"].startswith("post_")


def test_get_community_posts():
    headers = _login_headers()

    client.post(
        "/api/v1/community/posts",
        headers=headers,
        json={
            "category": "자유",
            "title": "첫 번째 글",
            "content": "첫 번째 내용",
        },
    )

    client.post(
        "/api/v1/community/posts",
        headers=headers,
        json={
            "category": "사용 후기",
            "title": "두 번째 글",
            "content": "두 번째 내용",
        },
    )

    response = client.get(
        "/api/v1/community/posts",
        headers=headers,
    )

    assert response.status_code == 200

    posts = response.json()

    assert len(posts) == 2
    assert posts[0]["title"] == "두 번째 글"
    assert posts[1]["title"] == "첫 번째 글"


def test_get_community_post_detail():
    headers = _login_headers()

    create_response = client.post(
        "/api/v1/community/posts",
        headers=headers,
        json={
            "category": "광고 팁",
            "title": "상세 조회 테스트",
            "content": "상세 내용",
        },
    )

    post_id = create_response.json()["post_id"]

    response = client.get(
        f"/api/v1/community/posts/{post_id}",
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json()["title"] == "상세 조회 테스트"


def test_community_requires_auth():
    response = client.get("/api/v1/community/posts")

    assert response.status_code == 401

def test_create_community_comment():
    headers = _login_headers()

    create_response = client.post(
        "/api/v1/community/posts",
        headers=headers,
        json={
            "category": "자유",
            "title": "댓글 테스트",
            "content": "게시글 내용",
        },
    )
    post_id = create_response.json()["post_id"]

    comment_response = client.post(
        f"/api/v1/community/posts/{post_id}/comments",
        headers=headers,
        json={
            "content": "첫 번째 댓글입니다.",
        },
    )

    assert comment_response.status_code == 201

    comment = comment_response.json()
    assert comment["customer_id"] == "CUS-0001"
    assert comment["company_name"] == "테스트 회사"
    assert comment["content"] == "첫 번째 댓글입니다."


def test_post_detail_contains_comments():
    headers = _login_headers()

    create_response = client.post(
        "/api/v1/community/posts",
        headers=headers,
        json={
            "category": "자유",
            "title": "댓글 상세 테스트",
            "content": "게시글 내용",
        },
    )
    post_id = create_response.json()["post_id"]

    client.post(
        f"/api/v1/community/posts/{post_id}/comments",
        headers=headers,
        json={"content": "댓글입니다."},
    )

    response = client.get(
        f"/api/v1/community/posts/{post_id}",
        headers=headers,
    )

    assert response.status_code == 200

    data = response.json()
    assert data["comment_count"] == 1
    assert len(data["comments"]) == 1
    assert data["comments"][0]["content"] == "댓글입니다."
