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
import uuid
from datetime import datetime, timezone
from pathlib import Path

from transformers import data

from app.backend.services.auth import CUSTOMERS, SESSIONS

STORE_PATH = Path("var/store.json")
# ⚠️ 중요: "data/" 하위에 두면 안 된다 - main.py가 app.mount("/files", StaticFiles(directory="data"))로
# data/ 전체를 정적 서빙하기 때문에, data/store.json으로 두면 GET /files/store.json 한 번으로
# 상품명·가격·전체 History가 인증 없이 그대로 공개된다. var/는 정적 마운트 대상이 아니라 안전하다.

PRODUCTS: dict[str, dict] = {}
JOBS: dict[str, dict] = {}
HISTORY: list[dict] = []
VIDEO_JOBS: dict[str, dict] = {}
COMMUNITY_POSTS: list[dict] = []
INQUIRIES: list[dict] = []

def save() -> None:
    STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = STORE_PATH.with_suffix(".tmp")
    tmp.write_text(
        json.dumps(
            {
                "products": PRODUCTS,
                "jobs": JOBS,
                "history": HISTORY,
                "video_jobs": VIDEO_JOBS,
                "customers": CUSTOMERS,
                "community_posts": COMMUNITY_POSTS,
                "inquiries": INQUIRIES,
            },
            ensure_ascii=False,
        ),
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
    VIDEO_JOBS.clear()
    VIDEO_JOBS.update(data.get("video_jobs", {}))
    CUSTOMERS.clear()
    CUSTOMERS.update(data.get("customers", {}))
    COMMUNITY_POSTS.clear()
    COMMUNITY_POSTS.extend(data.get("community_posts", []))
    INQUIRIES.clear()
    INQUIRIES.extend(data.get("inquiries", []))



    # 인증 도입 전(customer_id 개념이 없던 시절) 만들어진 상품/작업/이력은 그대로 두면
    # 배포 즉시 "어느 고객사 것도 아닌" 상태가 되어 영구 404가 된다 - LEGACY라는
    # 특수 고객사로 일괄 배정해서, 최소한 관리자가 LEGACY 계정으로 로그인하면
    # 예전 데이터를 계속 볼 수 있게 한다 (PR 리뷰에서 지적됨). LEGACY 계정 자체는
    # main.py의 lifespan에서 서버 시작 시 자동 생성된다.

    for post in COMMUNITY_POSTS:
        post.setdefault("comments", [])
        post["comment_count"] = len(post["comments"])

    for product in PRODUCTS.values():
        product.setdefault("customer_id", "LEGACY")
    for job in JOBS.values():
        job.setdefault("customer_id", "LEGACY")
    for entry in HISTORY:
        entry.setdefault("customer_id", "LEGACY")

    # 좀비 job 정리: 서버가 죽기 전 queued/processing 상태였던 job은, 그걸 돌리던
    # BackgroundTask가 재시작으로 같이 사라졌으므로 다시는 완료되지 않는다.
    # 이 상태를 그대로 두면 (중복 생성 방지 로직과 맞물려) 해당 상품이 영구적으로
    # "이미 진행 중" 409를 받게 되어 사용자가 빠져나올 방법이 없어진다 - failed로 정리한다.
    for job in JOBS.values():
        if job.get("status") in ("queued", "processing"):
            job["status"] = "failed"
            job["error_message"] = "서버 재시작으로 생성이 중단되었습니다. 다시 시도해주세요."
            job["current_step"] = None

    _migrate_missing_result_ids()
    _recover_video_jobs()


def _migrate_missing_result_ids() -> None:
    """
    ToneResult.result_id가 필수 필드로 추가되기 전(쇼츠 기능 이전)에 저장된
    var/store.json이 남아있으면, result_id 없는 결과를 GET /generations/{id}가
    pydantic 검증에서 500으로 떨어뜨릴 수 있다. 로드 시점에 없는 것만 채워서
    이전 데이터도 그대로 계속 쓸 수 있게 한다 (Sprint0~1 수준의 가벼운 마이그레이션).
    """
    for job in JOBS.values():
        for r in (job.get("result") or []):
            if isinstance(r, dict) and not r.get("result_id"):
                r["result_id"] = f"res_migrated_{uuid.uuid4().hex[:8]}"
    for entry in HISTORY:
        for r in entry.get("results", []):
            if isinstance(r, dict) and not r.get("result_id"):
                r["result_id"] = f"res_migrated_{uuid.uuid4().hex[:8]}"


def _recover_video_jobs(*, recovered_at: datetime | None = None) -> None:
    """재시작으로 중단된 영상 작업을 중복 실행되지 않는 안전한 상태로 바꾼다."""
    recovery_time = recovered_at or datetime.now(timezone.utc)
    if recovery_time.tzinfo is None or recovery_time.utcoffset() is None:
        raise ValueError("video job recovery time must be timezone-aware")
    for job in VIDEO_JOBS.values():
        recovered = False
        for removed_field in (
            "music_key",
            "music_warning",
            "silent_publish_confirmed",
        ):
            job.pop(removed_field, None)
        if job.get("render_status") in {"queued", "processing"}:
            job["render_status"] = "failed"
            job["error_message"] = (
                "서버 재시작으로 영상 생성이 중단되었습니다. 다시 시도해주세요."
            )
            recovered = True
        if (
            job.get("publish_status") == "pending"
            and not job.get("youtube_video_id")
        ):
            job["publish_status"] = "needs_review"
            job["youtube_error"] = "게시 성공 여부를 확인한 뒤 다시 시도해주세요."
            recovered = True
        if recovered:
            job["updated_at"] = recovery_time.isoformat()


def reset_for_tests() -> None:
    """테스트 전용 - 메모리와 디스크 파일 둘 다 초기화."""
    PRODUCTS.clear()
    JOBS.clear()
    HISTORY.clear()
    VIDEO_JOBS.clear()
    COMMUNITY_POSTS.clear()
    INQUIRIES.clear()
    CUSTOMERS.clear()
    SESSIONS.clear()
    if STORE_PATH.exists():
        STORE_PATH.unlink()
