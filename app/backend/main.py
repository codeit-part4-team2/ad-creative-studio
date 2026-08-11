import os
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
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

# Streamlit은 서버 쪽(Python)에서 requests로 호출해서 CORS가 필요 없었지만,
# web/(Next.js)는 브라우저에서 직접 fetch하므로 CORS 허용이 없으면 "Failed to fetch"로
# 조용히 막힌다 (에러 메시지에 이유가 안 나와서 원인 파악이 까다로움 - 실제로 겪은 문제).
# WEB_ALLOWED_ORIGINS(쉼표 구분)로 배포 시 도메인을 지정할 수 있게 하고, 기본값은
# 로컬 개발 서버(Next.js dev :3000, 혹시 모를 3001)로 좁혀둔다.
_allowed_origins = os.getenv("WEB_ALLOWED_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _allowed_origins if o.strip()],
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

Path("data/uploads").mkdir(parents=True, exist_ok=True)
Path("data/outputs").mkdir(parents=True, exist_ok=True)
Path("data/videos").mkdir(parents=True, exist_ok=True)
app.mount("/files", StaticFiles(directory="data"), name="files")


@app.get("/health")
async def health():
    return {"status": "ok"}
