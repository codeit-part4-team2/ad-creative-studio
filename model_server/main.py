from __future__ import annotations

import asyncio
import uuid
from contextlib import asynccontextmanager
from collections.abc import Mapping
import logging
import os
from pathlib import Path
from threading import Lock
from typing import Annotated

from fastapi import Depends, FastAPI, Response
from fastapi.staticfiles import StaticFiles

from deploy.monitoring import start_gpu_watcher
from deploy.queue_manager import QueueManager
from model_server.cache import TTLCache
from model_server.config import InferenceConfig
from model_server.inference import FileOutputStore, InferenceEngine
from model_server.pipelines import DiffusersGenerationPipeline
from model_server.preprocessing import (
    HttpImageDownloader,
    ProductArtifacts,
    ProductPreprocessor,
    RembgSegmenter,
)
from model_server.schemas import (
    HealthResponse,
    InferRequest,
    InferResponse,
    WarmupResponse,
)


LOGGER = logging.getLogger(__name__)


def _resolve_output_dir(
    environ: Mapping[str, str],
    *,
    base_dir: Path,
) -> Path:
    raw_path = environ.get(
        "MODEL_OUTPUT_DIR",
        environ.get("OUTPUT_DIR", "data/outputs"),
    )
    output_dir = Path(raw_path).expanduser()
    if not output_dir.is_absolute():
        output_dir = base_dir / output_dir
    return output_dir.resolve()


OUTPUT_DIR = _resolve_output_dir(os.environ, base_dir=Path.cwd())
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 서버 시작 시 GPU 감시 스레드 시작
    start_gpu_watcher()
    yield
    # 서버 종료 시 할 일 없음 (daemon 스레드라 자동 정리됨)

app = FastAPI(title="Team 2 Advertisement Model Server", version="0.2.0", lifespan=lifespan)
app.mount("/files/outputs", StaticFiles(directory=OUTPUT_DIR), name="model-outputs")
_engine: InferenceEngine | None = None
_engine_lock = Lock()
queue_manager = QueueManager()


def _build_engine() -> InferenceEngine:
    config = InferenceConfig.from_env(os.environ)
    cache: TTLCache[str, ProductArtifacts] = TTLCache(
        max_entries=config.cache_max_entries,
        ttl_seconds=config.cache_ttl_seconds,
    )
    preprocessor = ProductPreprocessor(
        cache=cache,
        downloader=HttpImageDownloader(
            allowed_origins=config.image_allowed_origins,
        ),
        segmenter=RembgSegmenter(),
        image_size=config.image_size,
        product_fill_ratio=config.product_fill_ratio,
        # 비율별 Canny는 cache hit 뒤 InferenceEngine에서 정확한 캔버스에 맞춰 만든다.
        include_canny=False,
    )
    pipeline = DiffusersGenerationPipeline(config)
    output_store = FileOutputStore(
        OUTPUT_DIR,
        url_prefix="/files/outputs",
    )
    return InferenceEngine(
        config=config,
        preprocessor=preprocessor,
        pipeline=pipeline,
        output_store=output_store,
    )


def get_engine() -> InferenceEngine:
    global _engine
    if _engine is not None:
        return _engine
    with _engine_lock:
        if _engine is None:
            _engine = _build_engine()
        return _engine


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(
        model_loaded=_engine.model_loaded if _engine is not None else False
    )


@app.post(
    "/warmup",
    response_model=WarmupResponse,
    response_model_exclude_none=True,
)
def warmup(
    engine: Annotated[InferenceEngine, Depends(get_engine)],
) -> WarmupResponse:
    try:
        engine.load_model()
    except Exception:
        LOGGER.exception("model warmup failed")
        return WarmupResponse(
            status="failed",
            model_loaded=False,
            error_message="model_load_failed",
        )
    return WarmupResponse(status="ok", model_loaded=engine.model_loaded)


@app.post("/infer", response_model=InferResponse)
async def infer(
    request: InferRequest,
    response: Response,
    engine: Annotated[InferenceEngine, Depends(get_engine)],
) -> InferResponse:
    request_id = str(uuid.uuid4())
    response.headers["X-Queue-Position"] = str(queue_manager.queue_position(request_id))
    response.headers["X-Estimated-Wait-Sec"] = str(queue_manager.estimated_wait_sec(request_id))

    try:
        async with queue_manager.slot(request_id) as ctx:
            result = await asyncio.to_thread(
                engine.run,
                product_id=request.product_id,
                product_image_url=request.product_image_url,
                tone=request.tone,
                image_prompt=request.image_prompt,
                negative_prompt=request.negative_prompt,
                time_slot=request.time_slot,
                output_format=request.output_format,
                scene_purpose=request.scene_purpose,
            )
        queue_manager.record_gpu_duration(result.stage_times_sec["generate"])
        response.headers["X-Gen-Time-Sec"] = str(ctx.duration_sec)
    except Exception:
        LOGGER.exception("inference failed for product_id=%s", request.product_id)
        return InferResponse(status="failed", error_message="inference_failed")

    return InferResponse.model_validate(result)
