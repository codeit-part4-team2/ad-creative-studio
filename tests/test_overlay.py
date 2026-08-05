import shutil
from pathlib import Path

import pytest

from app.backend.services import overlay


@pytest.fixture(autouse=True)
def _clean_outputs():
    yield
    if overlay.OUTPUT_DIR.exists():
        shutil.rmtree(overlay.OUTPUT_DIR)


def test_create_placeholder_background_matches_requested_size():
    img = overlay.create_placeholder_background("emotional", (300, 200))
    assert img.size == (300, 200)


def test_overlay_copy_resizes_to_format_spec():
    bg = overlay.create_placeholder_background("modern", (100, 100))
    result = overlay.overlay_copy(bg, "헤드라인", "서브카피", "thumbnail", tone="modern")
    assert result.size == (1000, 1000)  # OUTPUT_FORMATS["thumbnail"]["size"]


def test_generate_and_save_creates_one_file_per_format():
    urls = overlay.generate_and_save(
        job_id="job_test1", tone="premium", time_slot="evening",
        headline="헤드라인", subcopy="서브카피",
        output_formats=["thumbnail", "detail_banner", "sns_card"],
    )
    assert set(urls.keys()) == {"thumbnail", "detail_banner", "sns_card"}
    for fmt, url in urls.items():
        assert url.startswith("/files/outputs/")
        file_path = Path("data") / url.removeprefix("/files/")
        assert file_path.exists()


def test_generate_and_save_urls_are_unique_across_calls():
    urls1 = overlay.generate_and_save(
        job_id="job_test2", tone="modern", time_slot="morning",
        headline="A", subcopy="B", output_formats=["thumbnail"],
    )
    urls2 = overlay.generate_and_save(
        job_id="job_test2", tone="modern", time_slot="morning",
        headline="A", subcopy="B", output_formats=["thumbnail"],
    )
    assert urls1["thumbnail"] != urls2["thumbnail"]
