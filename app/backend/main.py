import os
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.backend.logging_config import configure_application_logging
from app.backend.api import (
    auth,
    download,
    exposure,
    generations,
    history,
    jobs,
    products,
    usage,
    videos,
    youtube,
)
from app.backend.services import auth as auth_service, store
from app.backend.services.video_workflow import build_default_video_workflow


configure_application_logging()


# .env 로딩은 코드(load_dotenv())가 아니라 실행 명령(uvicorn --env-file .env)에서
# 한다. 파일은 있는데 값이 프로세스에 하나도 없으면 플래그 누락을 바로 알린다.
def _warn_if_env_file_not_actually_loaded() -> None:
    env_path = Path(".env")
    if not env_path.exists():
        return
    try:
        keys = [
            line.split("=", 1)[0].strip()
            for line in env_path.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.strip().startswith("#") and "=" in line
        ]
    except OSError:
        return
    if keys and not any(key in os.environ for key in keys):
        print(
            "[WARNING] .env 파일이 있지만 그 안의 값이 프로세스 환경변수에 하나도 "
            "반영되지 않았습니다 - uvicorn 실행 시 --env-file .env 플래그를 "
            "빠뜨리지 않았는지 확인하세요."
        )


_warn_if_env_file_not_actually_loaded()


@asynccontextmanager
async def lifespan(app: FastAPI):
    store.load()
    # 인증 도입 전(customer_id 없던 시절) 데이터는 store.load()가 LEGACY로 배정한다 -
    # 그 데이터를 실제로 볼 수 있는 계정이 있어야 하므로 서버 시작 시 자동 생성한다.
    if "LEGACY" not in auth_service.CUSTOMERS:
        auth_service.create_customer(
            "LEGACY", "레거시 데이터(인증 도입 전)", os.getenv("LEGACY_PIN", "000000")
        )
    app.state.video_workflow = build_default_video_workflow()
    yield


app = FastAPI(title="소형가전 광고 생성 서비스", lifespan=lifespan)

# web/(Next.js)는 브라우저에서 직접 호출하므로 배포 origin을 명시적으로 제한한다.
_allowed_origins = os.getenv(
    "WEB_ALLOWED_ORIGINS",
    "http://localhost:3000,http://127.0.0.1:3000",
).split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in _allowed_origins if origin.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(products.router)
app.include_router(generations.router)
app.include_router(jobs.router)
app.include_router(history.router)
app.include_router(usage.router)
app.include_router(exposure.router)
app.include_router(download.router)
app.include_router(videos.router)
app.include_router(youtube.router)
app.include_router(auth.router)
app.include_router(auth.admin_router)

Path("data/uploads").mkdir(parents=True, exist_ok=True)
Path("data/outputs").mkdir(parents=True, exist_ok=True)
Path("data/videos").mkdir(parents=True, exist_ok=True)
app.mount("/files", StaticFiles(directory="data"), name="files")


@app.get("/")
async def root():
    return {"message": "소형가전 광고 생성 서비스 API"}


@app.get("/health")
async def health():
    return {"status": "ok"}
