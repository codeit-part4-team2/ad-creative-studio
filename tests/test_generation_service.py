import asyncio
import shutil
import threading
import uuid
from pathlib import Path

import pytest
from PIL import Image

from app.backend.schemas.generation import GenerationRequest
from app.backend.services import copy_generator, generation_service, overlay
from app.backend.services.store import JOBS


@pytest.fixture(autouse=True)
def _isolate_generation(monkeypatch):
    output_dir = overlay.OUTPUT_DIR / f"_pytest_{uuid.uuid4().hex[:8]}"
    monkeypatch.setattr(overlay, "OUTPUT_DIR", output_dir)
    monkeypatch.setattr(
        copy_generator,
        "build_ad_copy",
        lambda _item: ("테스트 헤드라인", "테스트 서브카피"),
    )
    JOBS.clear()
    yield
    JOBS.clear()
    if output_dir.exists():
        shutil.rmtree(output_dir)


def _request(*, time_slot: str) -> GenerationRequest:
    return GenerationRequest(
        product_id="prd_test",
        tones=["modern"],
        time_slots=[time_slot],
        output_formats=["detail_banner", "sns_card"],
    )


def _prepare_job() -> None:
    JOBS["job_test"] = {
        "status": "processing",
        "progress": 0,
        "completed_count": 0,
        "total_count": 1,
        "current_step": None,
    }


def test_mock_formatted_exports_keep_tone_color_at_non_square_edges():
    _prepare_job()
    service = generation_service.LocalOverlayGenerationService()

    [result] = asyncio.run(
        service.generate(
            "job_test",
            _request(time_slot="morning"),
            {"product_name": "테스트 상품", "selling_points": []},
        )
    )

    expected_color = overlay.TONE_PLACEHOLDER_COLOR["modern"]
    for image_url in result.images.values():
        image_path = Path("data") / image_url.removeprefix("/files/")
        with Image.open(image_path) as image:
            assert image.getpixel((2, 2)) == expected_color


def test_mock_clean_source_is_saved_only_for_rush_hour():
    _prepare_job()
    JOBS["job_test"]["total_count"] = 2
    request = GenerationRequest(
        product_id="prd_test",
        tones=["modern"],
        time_slots=["morning", "commute_am"],
        output_formats=["thumbnail"],
    )

    results = asyncio.run(
        generation_service.LocalOverlayGenerationService().generate(
            "job_test",
            request,
            {"product_name": "테스트 상품", "selling_points": []},
        )
    )

    by_slot = {result.time_slot: result for result in results}
    assert by_slot["morning"].source_image_url is None
    assert by_slot["commute_am"].source_image_url is not None
    assert len(list(overlay.OUTPUT_DIR.glob("*_source_*.png"))) == 1


def test_rush_hour_source_save_and_copy_generation_overlap(monkeypatch):
    _prepare_job()
    source_started = threading.Event()
    copy_started = threading.Event()
    overlapped: dict[str, bool] = {}

    def save_source_image(**_kwargs) -> str:
        source_started.set()
        overlapped["source"] = copy_started.wait(timeout=0.5)
        return "/files/outputs/source.png"

    def build_ad_copy(_item) -> tuple[str, str]:
        copy_started.set()
        overlapped["copy"] = source_started.wait(timeout=0.5)
        return "테스트 헤드라인", "테스트 서브카피"

    monkeypatch.setattr(overlay, "save_source_image", save_source_image)
    monkeypatch.setattr(copy_generator, "build_ad_copy", build_ad_copy)
    monkeypatch.setattr(
        overlay,
        "generate_and_save",
        lambda **_kwargs: {"thumbnail": "/files/outputs/card.png"},
    )

    asyncio.run(
        generation_service.LocalOverlayGenerationService().generate(
            "job_test",
            GenerationRequest(
                product_id="prd_test",
                tones=["modern"],
                time_slots=["commute_pm"],
                output_formats=["thumbnail"],
            ),
            {"product_name": "테스트 상품", "selling_points": []},
        )
    )

    assert overlapped == {"source": True, "copy": True}
