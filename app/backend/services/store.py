"""
인메모리 저장소 + 파일 기반 영속화 (통합 체크리스트 갭: 서버 재시작 시 데이터 유지).

매 요청마다 디스크에 쓰는 게 아니라, 상태가 실제로 바뀌는 지점(상품 등록/생성 시작·완료·
실패/즐겨찾기 토글)에서 명시적으로 save()를 호출한다. Sprint0~1 수준의 가벼운 영속화이고,
동시 다중 프로세스 환경까지 보장하진 않는다 - 진짜 DB는 Sprint1 이후 필요해지면 전환.

⚠️ 운영 조건: 이 방식은 uvicorn worker 1개(--workers 1, 기본값) 기준으로만 안전하다.
여러 worker 프로세스가 동시에 이 파일에 쓰면 경쟁 상태로 데이터가 유실될 수 있다.
다중 사용자를 실제로 받게 되면 SQLite/PostgreSQL 또는 Redis로 교체 예정.
"""
import json
from pathlib import Path

STORE_PATH = Path("data/store.json")

PRODUCTS: dict[str, dict] = {}
JOBS: dict[str, dict] = {}
HISTORY: list[dict] = []


def save() -> None:
    STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = STORE_PATH.with_suffix(".tmp")
    tmp.write_text(
        json.dumps({"products": PRODUCTS, "jobs": JOBS, "history": HISTORY}, ensure_ascii=False),
        encoding="utf-8",
    )
    tmp.replace(STORE_PATH)  # 원자적 교체 - 쓰기 도중 죽어도 기존 파일 안 깨짐


def load() -> None:
    """앱 시작 시 1회 호출. 파일이 없거나 깨져있으면 빈 상태로 조용히 시작한다."""
    if not STORE_PATH.exists():
        return
    try:
        data = json.loads(STORE_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError, UnicodeDecodeError):
        return

    PRODUCTS.clear()
    PRODUCTS.update(data.get("products", {}))
    JOBS.clear()
    JOBS.update(data.get("jobs", {}))
    HISTORY.clear()
    HISTORY.extend(data.get("history", []))


def reset_for_tests() -> None:
    """테스트 전용 - 메모리와 디스크 파일 둘 다 초기화."""
    PRODUCTS.clear()
    JOBS.clear()
    HISTORY.clear()
    if STORE_PATH.exists():
        STORE_PATH.unlink()
