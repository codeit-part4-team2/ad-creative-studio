from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

# 반드시 app.backend.api/services를 import하기 전에 .env를 읽어야 한다 - 아래 라우터들이
# import되는 순간(모듈 로드 시점) generation_service.py/model_server_client.py 등이
# 이미 os.getenv(...)로 MODEL_SERVER_URL·USE_MOCK_GENERATION·BACKEND_PUBLIC_URL 등을
# 읽어버리기 때문이다. load_dotenv()가 없으면 .env 파일 내용이 전혀 반영 안 되고
# os.getenv()의 기본값(fallback)만 항상 쓰이는데, 지금까지 그 기본값이 우연히 원하는
# 값(USE_MOCK_GENERATION=true 등)과 같아서 안 걸렸을 뿐이다 (재헌님이 model_server 쪽
# 동일 버그를 먼저 발견해서 우리 쪽도 확인함).
from dotenv import load_dotenv
load_dotenv()

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
