from __future__ import annotations

import io

import pytest
from PIL import Image

from model_server.cache import TTLCache
from model_server.preprocessing import (
    derive_product_artifacts,
    HttpImageDownloader,
    ProductPreprocessor,
    RembgSegmenter,
)


class _FakeResponse:
    def __init__(
        self,
        payload: bytes,
        content_type: str = "image/png",
        status_code: int = 200,
    ) -> None:
        self._payload = payload
        self.status_code = status_code
        self.headers = {
            "content-type": content_type,
            "content-length": str(len(payload)),
        }

    def raise_for_status(self) -> None:
        return None

    def iter_content(self, chunk_size: int) -> list[bytes]:
        return [
            self._payload[index : index + chunk_size]
            for index in range(0, len(self._payload), chunk_size)
        ]


def _png_bytes(size: tuple[int, int] = (10, 5)) -> bytes:
    image = Image.new("RGB", size, (10, 20, 30))
    output = io.BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def test_preprocessor_reuses_download_segmentation_and_canny_for_same_key() -> None:
    calls = {"download": 0, "segment": 0, "canny": 0}

    def download(_: str) -> Image.Image:
        calls["download"] += 1
        return Image.new("RGB", (20, 10), (100, 100, 100))

    def segment(_: Image.Image) -> Image.Image:
        calls["segment"] += 1
        return Image.new("RGBA", (20, 10), (200, 10, 20, 255))

    def canny(image: Image.Image) -> Image.Image:
        calls["canny"] += 1
        return Image.new("RGB", image.size, (255, 255, 255))

    preprocessor = ProductPreprocessor(
        cache=TTLCache(max_entries=2, ttl_seconds=60.0),
        downloader=download,
        segmenter=segment,
        canny_builder=canny,
        image_size=100,
        product_fill_ratio=0.5,
    )

    first = preprocessor.prepare("product:1", "https://images.example/one.png")
    second = preprocessor.prepare("product:1", "https://images.example/one.png")

    assert first.cache_hit is False
    assert second.cache_hit is True
    assert first.artifacts is second.artifacts
    assert calls == {"download": 1, "segment": 1, "canny": 1}
    assert first.artifacts.product_rgba.size == (100, 100)
    assert first.artifacts.product_on_white.mode == "RGB"
    assert first.artifacts.alpha_mask.mode == "L"


def test_cached_segmentation_derives_two_native_ratio_artifact_sets() -> None:
    calls = {"download": 0, "segment": 0}

    def download(_: str) -> Image.Image:
        calls["download"] += 1
        return Image.new("RGB", (80, 40), "white")

    def segment(_: Image.Image) -> Image.Image:
        calls["segment"] += 1
        return Image.new("RGBA", (80, 40), (200, 10, 20, 255))

    preprocessor = ProductPreprocessor(
        cache=TTLCache(max_entries=2, ttl_seconds=60.0),
        downloader=download,
        segmenter=segment,
        image_size=100,
        product_fill_ratio=0.5,
        include_canny=False,
    )

    first = preprocessor.prepare("product:1", "https://images.example/one.png")
    second = preprocessor.prepare("product:1", "https://images.example/one.png")
    square = derive_product_artifacts(
        first.artifacts,
        canvas_size=(100, 100),
        fill_ratio=0.5,
        include_canny=False,
    )
    vertical = derive_product_artifacts(
        second.artifacts,
        canvas_size=(72, 128),
        fill_ratio=0.5,
        include_canny=True,
        canny_builder=lambda image: Image.new("RGB", image.size, "black"),
    )

    assert calls == {"download": 1, "segment": 1}
    assert square.product_rgba.size == (100, 100)
    assert vertical.product_rgba.size == (72, 128)
    assert vertical.product_on_white.size == (72, 128)
    assert vertical.alpha_mask.size == (72, 128)
    assert vertical.canny_image is not None
    assert vertical.canny_image.size == (72, 128)


def test_fast_preprocessor_skips_unused_canny_work() -> None:
    def unexpected_canny(_: Image.Image) -> Image.Image:
        raise AssertionError("fast composite profile must not build Canny input")

    preprocessor = ProductPreprocessor(
        cache=TTLCache(max_entries=2, ttl_seconds=60.0),
        downloader=lambda _: Image.new("RGB", (20, 10), "white"),
        segmenter=lambda image: image.convert("RGBA"),
        canny_builder=unexpected_canny,
        image_size=100,
        product_fill_ratio=0.5,
        include_canny=False,
    )

    result = preprocessor.prepare(
        "product:fast",
        "https://images.example/product.png",
    )

    assert result.artifacts.canny_image is None


def test_preprocessor_bounds_the_cached_raw_segmentation_size() -> None:
    preprocessor = ProductPreprocessor(
        cache=TTLCache(max_entries=2, ttl_seconds=60.0),
        downloader=lambda _: Image.new("RGB", (2000, 1000), "white"),
        segmenter=lambda image: image.convert("RGBA"),
        image_size=100,
        product_fill_ratio=0.5,
        include_canny=False,
    )

    result = preprocessor.prepare(
        "product:large",
        "https://images.example/large.png",
    )

    assert result.artifacts.segmented_product is not None
    assert result.artifacts.segmented_product.size == (1280, 640)


def test_rembg_segmenter_initializes_one_session_for_multiple_images() -> None:
    sessions: list[object] = []
    received_sessions: list[object] = []

    def session_factory() -> object:
        session = object()
        sessions.append(session)
        return session

    def remove_func(image: Image.Image, *, session: object) -> Image.Image:
        received_sessions.append(session)
        return image.convert("RGBA")

    segmenter = RembgSegmenter(
        session_factory=session_factory,
        remove_func=remove_func,
    )

    segmenter(Image.new("RGB", (2, 2), "white"))
    segmenter(Image.new("RGB", (2, 2), "black"))

    assert len(sessions) == 1
    assert received_sessions == [sessions[0], sessions[0]]


def test_http_downloader_rejects_non_http_scheme_without_requesting() -> None:
    requested: list[str] = []
    downloader = HttpImageDownloader(
        allowed_origins={"https://images.example"},
        request_get=lambda url, **_: requested.append(url),
        max_bytes=1024,
        max_pixels=10_000,
    )

    with pytest.raises(ValueError, match="HTTP"):
        downloader("file:///etc/passwd")

    assert requested == []


def test_http_downloader_stops_response_larger_than_limit() -> None:
    payload = _png_bytes()
    response = _FakeResponse(payload)
    response.headers["content-length"] = "2048"
    downloader = HttpImageDownloader(
        allowed_origins={"https://images.example"},
        request_get=lambda *_args, **_kwargs: response,
        max_bytes=1024,
        max_pixels=10_000,
    )

    with pytest.raises(ValueError, match="maximum size"):
        downloader("https://images.example/product.png")


def test_http_downloader_decodes_valid_image_and_normalizes_rgb() -> None:
    response = _FakeResponse(_png_bytes((10, 5)))
    downloader = HttpImageDownloader(
        allowed_origins={"https://images.example"},
        request_get=lambda *_args, **_kwargs: response,
        max_bytes=1024,
        max_pixels=100,
    )

    image = downloader("https://images.example/product.png")

    assert image.mode == "RGB"
    assert image.size == (10, 5)


def test_http_downloader_rejects_pixel_limit_before_decoding(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    response = _FakeResponse(_png_bytes((11, 10)))
    downloader = HttpImageDownloader(
        allowed_origins={"https://images.example"},
        request_get=lambda *_args, **_kwargs: response,
        max_bytes=1024,
        max_pixels=100,
    )
    decode_calls: list[Image.Image] = []

    def unexpected_decode(image: Image.Image, *_args: object, **_kwargs: object) -> None:
        decode_calls.append(image)
        raise AssertionError("pixel limit must be checked before image decoding")

    monkeypatch.setattr(Image.Image, "load", unexpected_decode)

    with pytest.raises(ValueError, match="maximum pixel count"):
        downloader("https://images.example/product.png")

    assert decode_calls == []


def test_http_downloader_rejects_origin_outside_allowlist_before_request() -> None:
    requested: list[str] = []
    downloader = HttpImageDownloader(
        request_get=lambda url, **_: requested.append(url),
        allowed_origins={"https://images.example"},
        max_bytes=1024,
        max_pixels=100,
    )

    with pytest.raises(ValueError, match="allowed origin"):
        downloader("http://169.254.169.254/latest/meta-data/")

    assert requested == []


def test_http_downloader_rejects_redirects_from_allowed_origin() -> None:
    response = _FakeResponse(_png_bytes(), status_code=302)
    request_options: list[dict[str, object]] = []
    downloader = HttpImageDownloader(
        request_get=lambda *_args, **kwargs: (
            request_options.append(kwargs) or response
        ),
        allowed_origins={"https://images.example"},
        max_bytes=1024,
        max_pixels=100,
    )

    with pytest.raises(ValueError, match="redirect"):
        downloader("https://images.example/product.png")

    assert request_options[0]["allow_redirects"] is False
