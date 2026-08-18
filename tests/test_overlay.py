import shutil
import uuid
from pathlib import Path

import pytest
from PIL import Image

from app.backend.services import overlay
from app.image_presets import IMAGE_PRESETS, get_image_preset


@pytest.fixture(autouse=True)
def _isolate_output_dir(monkeypatch):
    """
    실제 data/outputs/ 최상위(데모 파일이 있을 수 있는 곳)는 안 건드리고,
    그 하위의 테스트 전용 서브폴더만 만들고 지운다.
    """
    test_output_dir = overlay.OUTPUT_DIR / f"_pytest_{uuid.uuid4().hex[:8]}"
    monkeypatch.setattr(overlay, "OUTPUT_DIR", test_output_dir)
    yield
    if test_output_dir.exists():
        shutil.rmtree(test_output_dir)


def test_create_placeholder_background_matches_requested_size():
    img = overlay.create_placeholder_background("emotional", (300, 200))
    assert img.size == (300, 200)


def test_save_source_image_preserves_unbranded_model_output():
    source = Image.new("RGB", (73, 41), (12, 34, 56))

    url = overlay.save_source_image(
        job_id="job_source",
        tone="premium",
        time_slot="commute_pm",
        image=source,
    )

    assert url.startswith("/files/outputs/")
    saved_path = Path("data") / url.removeprefix("/files/")
    with Image.open(saved_path) as saved:
        assert saved.mode == "RGB"
        assert saved.size == source.size
        assert saved.tobytes() == source.tobytes()


def test_overlay_copy_resizes_to_format_spec():
    bg = overlay.create_placeholder_background("modern", (1024, 1024))
    result = overlay.overlay_copy(bg, "헤드라인", "서브카피", "thumbnail", tone="modern")
    assert result.size == (1080, 1080)


def test_generate_and_save_creates_one_file_per_format():
    urls = overlay.generate_and_save(
        job_id="job_test1", tone="premium", time_slot="evening",
        headline="헤드라인", subcopy="서브카피",
        output_formats=["thumbnail", "sns_card"],
    )
    assert set(urls.keys()) == {"thumbnail", "sns_card"}
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


def test_generate_and_save_uses_provided_background_when_given():
    """model_server 연동 경로 - 실제 배경 이미지를 주면 placeholder 대신 그걸 써야 한다."""
    from PIL import Image
    real_bg = Image.new("RGB", (1024, 1024), (10, 20, 30))

    urls = overlay.generate_and_save(
        job_id="job_bgtest", tone="modern", time_slot="morning",
        headline="헤드라인", subcopy="서브카피",
        output_formats=["thumbnail"],
        background_image=real_bg,
    )
    file_path = Path("data") / urls["thumbnail"].removeprefix("/files/")
    saved = Image.open(file_path)
    assert saved.size == (1080, 1080)


def test_generate_and_save_falls_back_to_placeholder_without_background():
    """background_image를 안 주면 기존처럼 톤별 placeholder를 쓴다 (Mock 경로, 하위호환)."""
    urls = overlay.generate_and_save(
        job_id="job_nobg", tone="premium", time_slot="morning",
        headline="헤드라인", subcopy="서브카피",
        output_formats=["thumbnail"],
    )
    assert urls["thumbnail"].startswith("/files/outputs/")


def test_overlay_copy_rejects_a_source_with_the_wrong_aspect_ratio():
    square_bg = Image.new("RGB", (1024, 1024), (50, 100, 150))

    with pytest.raises(ValueError, match="aspect ratio"):
        overlay.overlay_copy(
            square_bg,
            "헤드라인",
            "서브카피",
            "sns_card",
            tone="modern",
        )


@pytest.mark.parametrize("output_format", list(IMAGE_PRESETS))
def test_overlay_copy_exports_native_ratio_without_white_letterbox(
    output_format: str,
):
    preset = get_image_preset(output_format)
    source_color = (12, 34, 56)
    background = Image.new("RGB", preset.composite_size, source_color)

    result = overlay.overlay_copy(
        background,
        "",
        "",
        output_format,
        tone="modern",
    )

    assert result.size == preset.export_size
    assert result.getpixel((0, 0)) == source_color
    assert result.getpixel((result.width - 1, result.height - 1)) == source_color
