from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

# .env 로딩은 코드(load_dotenv())가 아니라 실행 명령(uvicorn --env-file .env)에서
# 한다 - model_server(R3)와 같은 방식으로 팀 컨벤션을 통일했다(치용님/재헌님 협의).
# 실행 시 반드시 --env-file .env를 붙여야 MODEL_SERVER_URL·USE_MOCK_GENERATION 등
# .env 값이 실제로 반영된다. SETUP.md 실행 명령 참고.
from app.backend.api import products, generations, jobs, history, usage, exposure, download, videos
from app.backend.services import store


@asynccontextmanager
async def lifespan(app: FastAPI):
    store.load()  # 서버 재시작 시 var/store.json에서 이전 상태 복구 (통합 체크리스트 갭)
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

Path("data/uploads").mkdir(parents=True, exist_ok=True)
Path("data/outputs").mkdir(parents=True, exist_ok=True)
Path("data/videos").mkdir(parents=True, exist_ok=True)
app.mount("/files", StaticFiles(directory="data"), name="files")


@app.get("/health")
async def health():
    return {"status": "ok"}
