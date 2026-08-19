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
import time

CUSTOMERS: dict[str, dict] = {}  # customer_id -> {company_name, pin_hash, pin_salt, status, plan, created_at}
SESSIONS: dict[str, str] = {}  # session_token -> customer_id (인메모리 전용, 서버 재시작 시 초기화)
FAILED_LOGIN_ATTEMPTS: dict[str, list[float]] = {}  # customer_id -> 최근 실패 타임스탬프들
ADMIN_FAILED_ATTEMPTS: list[float] = []
ADMIN_RATE_LIMIT_MAX_ATTEMPTS = 5
ADMIN_RATE_LIMIT_WINDOW_SECONDS = 60

PBKDF2_ITERATIONS = 260_000  # OWASP 2023 권장 최소치 근사
RATE_LIMIT_MAX_ATTEMPTS = 5
RATE_LIMIT_WINDOW_SECONDS = 60

# 존재하지 않는 customer_id로 로그인해도 항상 이 salt로 PBKDF2를 한 번 돌려서,
# "존재하는 ID는 느리고 존재 안 하는 ID는 빠르다"는 응답시간 차이(timing attack)로
# 유효한 customer_id를 추측당하지 않게 한다 (PR 리뷰에서 지적됨).
_DUMMY_SALT = secrets.token_bytes(16)


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


def is_rate_limited(customer_id: str) -> bool:
    """
    같은 customer_id로 짧은 시간에 너무 많이 실패하면 잠깐 막는다. 실제 고객을
    노린 무차별 대입(brute force) 방지가 목적이다 - 다만 이 방식 자체가 "누군가
    일부러 틀린 PIN을 계속 넣어서 진짜 고객을 잠깐 못 들어오게 lockout시키는" 부작용도
    있을 수 있는 절충이라, 프로젝트 규모에 맞는 가벼운 수준으로만 넣는다.
    """
    now = time.time()
    attempts = [t for t in FAILED_LOGIN_ATTEMPTS.get(customer_id, []) if now - t < RATE_LIMIT_WINDOW_SECONDS]
    FAILED_LOGIN_ATTEMPTS[customer_id] = attempts
    return len(attempts) >= RATE_LIMIT_MAX_ATTEMPTS


def _record_failed_attempt(customer_id: str) -> None:
    FAILED_LOGIN_ATTEMPTS.setdefault(customer_id, []).append(time.time())


def verify_login(customer_id: str, pin: str) -> str | None:
    """
    성공하면 세션 토큰 반환, 실패(고객 없음/PIN 불일치/비활성)하면 None.
    CPU를 쓰는 PBKDF2 계산이라 async 라우트에서 직접 호출하지 말고 asyncio.to_thread로
    돌릴 것 (안 그러면 로그인 동시 요청이 많을 때 이벤트 루프 자체가 막힌다).
    """
    customer = CUSTOMERS.get(customer_id)
    if customer and customer.get("status") == "active":
        salt = bytes.fromhex(customer["pin_salt"])
        expected_hash = customer["pin_hash"]
    else:
        # 존재하지 않거나 비활성 고객이어도 동일하게 PBKDF2를 한 번 돌린다(timing attack 방지) -
        # expected_hash를 None으로 둬서 아래 compare_digest가 무조건 실패하게 한다.
        salt = _DUMMY_SALT
        expected_hash = None

    computed = _hash_pin(pin, salt)
    if expected_hash is None or not secrets.compare_digest(computed, expected_hash):
        _record_failed_attempt(customer_id)
        return None

    token = secrets.token_urlsafe(32)
    SESSIONS[token] = customer_id
    return token


def resolve_session(token: str) -> dict | None:
    """
    세션이 있다고 바로 통과시키지 않고, 매번 고객사 status를 다시 확인한다 -
    관리자가 나중에 고객사를 정지시켜도 이미 로그인된 세션이 계속 살아있으면
    정지가 무의미해지기 때문이다 (PR 리뷰에서 지적됨).
    """
    customer_id = SESSIONS.get(token)
    if not customer_id:
        return None
    customer = CUSTOMERS.get(customer_id)
    if not customer or customer.get("status") != "active":
        return None
    return customer


def logout(token: str) -> None:
    SESSIONS.pop(token, None)


def verify_admin_key(provided_key: str | None) -> bool:
    """고객사 생성(admin)은 로그인 사용자가 아니라 팀 내부 관리 도구가 호출하는 것을
    전제로, 별도 ADMIN_API_KEY 하나로만 막는다 - 이 프로젝트 규모에서 별도 관리자
    로그인 시스템까지 만드는 건 과함."""
    expected = os.getenv("ADMIN_API_KEY")
    if not expected:
        _record_admin_failed_attempt()
        return False  # 키를 설정 안 했으면 기본적으로 막는다 (열어두는 쪽으로 fail하지 않음)

    valid = secrets.compare_digest(provided_key or "", expected)
    if not valid:
        _record_admin_failed_attempt()
    return valid

def is_admin_rate_limited() -> bool:
    now = time.time()

    recent_attempts = [
        attempt
        for attempt in ADMIN_FAILED_ATTEMPTS
        if now - attempt < ADMIN_RATE_LIMIT_WINDOW_SECONDS
    ]

    ADMIN_FAILED_ATTEMPTS.clear()
    ADMIN_FAILED_ATTEMPTS.extend(recent_attempts)

    return len(recent_attempts) >= ADMIN_RATE_LIMIT_MAX_ATTEMPTS


def _record_admin_failed_attempt() -> None:
    ADMIN_FAILED_ATTEMPTS.append(time.time())


def reset_rate_limit_for_tests() -> None:
    FAILED_LOGIN_ATTEMPTS.clear()
    ADMIN_FAILED_ATTEMPTS.clear()
