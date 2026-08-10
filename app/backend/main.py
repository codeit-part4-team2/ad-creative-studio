from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.backend.api import products, generations, jobs, history, usage, exposure, download, videos, youtube
from app.backend.services import store
from app.backend.services.video_workflow import build_default_video_workflow


@asynccontextmanager
async def lifespan(app: FastAPI):
    store.load()  # 서버 재시작 시 var/store.json에서 이전 상태 복구 (통합 체크리스트 갭)
    app.state.video_workflow = build_default_video_workflow()
    yield


app = FastAPI(title="소형가전 광고 생성 서비스", lifespan=lifespan)

app.include_router(products.router)
app.include_router(generations.router)
app.include_router(jobs.router)
app.include_router(history.router)
app.include_router(usage.router)
app.include_router(exposure.router)
app.include_router(download.router)
app.include_router(videos.router)
app.include_router(youtube.router)

Path("data/uploads").mkdir(parents=True, exist_ok=True)
Path("data/outputs").mkdir(parents=True, exist_ok=True)
Path("data/videos").mkdir(parents=True, exist_ok=True)
app.mount("/files", StaticFiles(directory="data"), name="files")


@app.get("/health")
async def health():
    return {"status": "ok"}
