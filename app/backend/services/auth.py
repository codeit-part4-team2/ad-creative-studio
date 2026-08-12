"""
B2B multi-tenant 인증 - 사업자번호 진위확인 API 대신, 관리자가 계약된 고객사에
customer_id + PIN을 발급하고 사용자는 그걸로 로그인하는 방식 (2026-08-12 팀 결정).
불특정 다수가 즉시 가입하는 SaaS가 아니라 계약 단계에서 이미 고객 확인이 끝나는
B2B 서비스라, 매 요청마다 "실제 사업자인가"보다 "우리와 계약된 고객인가"만 확인하면
충분하다는 판단.

PIN은 절대 평문 저장하지 않는다 - pbkdf2_hmac(표준 라이브러리만으로 충분, 이 규모
프로젝트에 bcrypt 등 새 의존성을 추가할 필요는 없음) + 고객마다 다른 salt.
세션은 로그인마다 새로 발급되는 랜덤 토큰 - store.py의 PRODUCTS/JOBS와 같은 패턴으로
인메모리 + 파일 영속화한다(단, 세션 자체는 재로그인이 가벼우니 영속화 대상에서 뺀다 -
서버 재시작하면 다시 로그인하면 됨. CUSTOMERS만 영속화 대상).
"""
import hashlib
import os
import secrets

CUSTOMERS: dict[str, dict] = {}  # customer_id -> {company_name, pin_hash, pin_salt, status, plan, created_at}
SESSIONS: dict[str, str] = {}  # session_token -> customer_id (인메모리 전용, 서버 재시작 시 초기화)

PBKDF2_ITERATIONS = 260_000  # OWASP 2023 권장 최소치 근사


def _hash_pin(pin: str, salt: bytes) -> str:
    return hashlib.pbkdf2_hmac("sha256", pin.encode("utf-8"), salt, PBKDF2_ITERATIONS).hex()


def create_customer(customer_id: str, company_name: str, pin: str, plan: str = "basic") -> dict:
    if customer_id in CUSTOMERS:
        raise ValueError(f"customer_id 중복: {customer_id}")
    salt = secrets.token_bytes(16)
    CUSTOMERS[customer_id] = {
        "customer_id": customer_id,
        "company_name": company_name,
        "pin_hash": _hash_pin(pin, salt),
        "pin_salt": salt.hex(),
        "status": "active",
        "plan": plan,
    }
    return CUSTOMERS[customer_id]


def verify_login(customer_id: str, pin: str) -> str | None:
    """성공하면 세션 토큰 반환, 실패(고객 없음/PIN 불일치/비활성)하면 None."""
    customer = CUSTOMERS.get(customer_id)
    if not customer or customer.get("status") != "active":
        return None
    salt = bytes.fromhex(customer["pin_salt"])
    if not secrets.compare_digest(_hash_pin(pin, salt), customer["pin_hash"]):
        return None
    token = secrets.token_urlsafe(32)
    SESSIONS[token] = customer_id
    return token


def resolve_session(token: str) -> dict | None:
    customer_id = SESSIONS.get(token)
    if not customer_id:
        return None
    return CUSTOMERS.get(customer_id)


def logout(token: str) -> None:
    SESSIONS.pop(token, None)


def verify_admin_key(provided_key: str | None) -> bool:
    """고객사 생성(admin)은 로그인 사용자가 아니라 팀 내부 관리 도구가 호출하는 것을
    전제로, 별도 ADMIN_API_KEY 하나로만 막는다 - 이 프로젝트 규모에서 별도 관리자
    로그인 시스템까지 만드는 건 과함."""
    expected = os.getenv("ADMIN_API_KEY")
    if not expected:
        return False  # 키를 설정 안 했으면 기본적으로 막는다 (열어두는 쪽으로 fail하지 않음)
    return secrets.compare_digest(provided_key or "", expected)
