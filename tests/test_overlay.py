import shutil
import uuid
from pathlib import Path

import pytest
from PIL import Image

from app.backend.services import overlay
from app.prompt.templates import OUTPUT_FORMATS


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


def test_generate_and_save_uses_provided_background_when_given():
    """model_server 연동 경로 - 실제 배경 이미지를 주면 placeholder 대신 그걸 써야 한다."""
    from PIL import Image
    real_bg = Image.new("RGB", (500, 500), (10, 20, 30))

    urls = overlay.generate_and_save(
        job_id="job_bgtest", tone="modern", time_slot="morning",
        headline="헤드라인", subcopy="서브카피",
        output_formats=["thumbnail"],
        background_image=real_bg,
    )
    file_path = Path("data") / urls["thumbnail"].removeprefix("/files/")
    saved = Image.open(file_path)
    assert saved.size == (1000, 1000)  # OUTPUT_FORMATS["thumbnail"]["size"]로 리사이즈됐는지


def test_generate_and_save_falls_back_to_placeholder_without_background():
    """background_image를 안 주면 기존처럼 톤별 placeholder를 쓴다 (Mock 경로, 하위호환)."""
    urls = overlay.generate_and_save(
        job_id="job_nobg", tone="premium", time_slot="morning",
        headline="헤드라인", subcopy="서브카피",
        output_formats=["thumbnail"],
    )
    assert urls["thumbnail"].startswith("/files/outputs/")


def test_overlay_copy_preserves_aspect_ratio_no_stretch():
    """
    실제 모델이 반환하는 정사각형(예: 1024x1024) 배경을 가로형(detail_banner)
    규격으로 뽑을 때, 단순 resize면 제품이 가로로 눌린다 - 지금은 비율 유지
    + 흰색 레터박스 패딩이어야 한다.
    """
    square_bg = Image.new("RGB", (1024, 1024), (50, 100, 150))
    detail_spec = OUTPUT_FORMATS["detail_banner"]["size"]  # 가로형, 정사각형 아님

    result = overlay.overlay_copy(square_bg, "헤드라인", "서브카피", "detail_banner", tone="modern")
    assert result.size == detail_spec

    # detail_banner(860×400)는 가로로 넓은 캔버스라, 정사각형 배경을 비율 유지로
    # 넣으면 세로(400)에 맞춰 축소되고 좌우에 여백이 생긴다 - 그 여백이 흰색인지 확인.
    left_edge_pixel = result.getpixel((2, detail_spec[1] // 2))
    assert left_edge_pixel[0] > 240 and left_edge_pixel[1] > 240 and left_edge_pixel[2] > 240


def test_overlay_copy_output_matches_spec_size_regardless_of_background_shape():
    """배경이 어떤 비율이든, 최종 출력은 항상 요청한 규격 크기와 정확히 같아야 한다."""
    tall_bg = Image.new("RGB", (300, 900), (10, 10, 10))  # 세로로 긴 배경
    for fmt, spec in OUTPUT_FORMATS.items():
        result = overlay.overlay_copy(tall_bg, "h", "s", fmt, tone="modern")
        assert result.size == spec["size"]
