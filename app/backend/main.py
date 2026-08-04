from pathlib import Path
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.backend.api import products, generations, jobs, history, usage

app = FastAPI(title="소형가전 광고 생성 서비스")

app.include_router(products.router)
app.include_router(generations.router)
app.include_router(jobs.router)
app.include_router(history.router)
app.include_router(usage.router)

Path("data/uploads").mkdir(parents=True, exist_ok=True)
Path("data/outputs").mkdir(parents=True, exist_ok=True)
app.mount("/files", StaticFiles(directory="data"), name="files")


@app.get("/health")
async def health():
    return {"status": "ok"}
