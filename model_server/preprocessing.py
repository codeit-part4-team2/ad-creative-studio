from __future__ import annotations

import io
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from threading import Lock
from typing import Any, Protocol
from urllib.parse import urlparse

from PIL import Image, ImageOps, UnidentifiedImageError

from model_server.cache import TTLCache
from model_server.compositing import fit_product_rgba


class _HttpResponse(Protocol):
    headers: dict[str, str]
    status_code: int

    def raise_for_status(self) -> None: ...

    def iter_content(self, chunk_size: int) -> Iterable[bytes]: ...


@dataclass(frozen=True, slots=True)
class ProductArtifacts:
    product_rgba: Image.Image
    product_on_white: Image.Image
    alpha_mask: Image.Image
    canny_image: Image.Image | None


@dataclass(frozen=True, slots=True)
class PreparationResult:
    artifacts: ProductArtifacts
    cache_hit: bool


def _requests_get(url: str, **kwargs: Any) -> _HttpResponse:
    import requests

    return requests.get(url, **kwargs)


class HttpImageDownloader:
    def __init__(
        self,
        *,
        allowed_origins: Iterable[str],
        request_get: Callable[..., _HttpResponse] = _requests_get,
        max_bytes: int = 15 * 1024 * 1024,
        max_pixels: int = 40_000_000,
        timeout: tuple[float, float] = (5.0, 30.0),
    ) -> None:
        if max_bytes <= 0 or max_pixels <= 0:
            raise ValueError("download limits must be greater than zero")
        normalized_origins = frozenset(
            self._http_origin(origin, origin_only=True)
            for origin in allowed_origins
        )
        if not normalized_origins:
            raise ValueError("allowed_origins must contain at least one origin")
        self._allowed_origins = normalized_origins
        self._request_get = request_get
        self._max_bytes = max_bytes
        self._max_pixels = max_pixels
        self._timeout = timeout

    @staticmethod
    def _http_origin(
        url: str,
        *,
        origin_only: bool,
    ) -> tuple[str, str, int]:
        parsed = urlparse(url)
        if (
            parsed.scheme.lower() not in {"http", "https"}
            or parsed.hostname is None
            or parsed.username is not None
            or parsed.password is not None
            or (origin_only and parsed.path not in {"", "/"})
            or (origin_only and (parsed.params or parsed.query or parsed.fragment))
        ):
            raise ValueError("product image URL must use a valid HTTP(S) origin")
        scheme = parsed.scheme.lower()
        default_port = 443 if scheme == "https" else 80
        return scheme, parsed.hostname.lower(), parsed.port or default_port

    def __call__(self, url: str) -> Image.Image:
        origin = self._http_origin(url, origin_only=False)
        if origin not in self._allowed_origins:
            raise ValueError("product image URL is outside the allowed origin list")

        response = self._request_get(
            url,
            stream=True,
            timeout=self._timeout,
            allow_redirects=False,
        )
        if 300 <= response.status_code < 400:
            raise ValueError("product image redirects are not allowed")
        response.raise_for_status()

        content_type = response.headers.get("content-type", "").split(";", 1)[0]
        if not content_type.lower().startswith("image/"):
            raise ValueError("product image response must have an image content type")
        content_length = response.headers.get("content-length")
        if content_length is not None and int(content_length) > self._max_bytes:
            raise ValueError("product image exceeds maximum size")

        chunks: list[bytes] = []
        received = 0
        for chunk in response.iter_content(chunk_size=64 * 1024):
            if not chunk:
                continue
            received += len(chunk)
            if received > self._max_bytes:
                raise ValueError("product image exceeds maximum size")
            chunks.append(chunk)

        try:
            with Image.open(io.BytesIO(b"".join(chunks))) as decoded:
                image = ImageOps.exif_transpose(decoded)
                if image.width * image.height > self._max_pixels:
                    raise ValueError("product image exceeds maximum pixel count")
                return image.convert("RGB")
        except UnidentifiedImageError as exc:
            raise ValueError("product image response is not a valid image") from exc


def _new_rembg_session() -> object:
    from rembg import new_session

    return new_session()


def _remove_background(image: Image.Image, *, session: object) -> Image.Image:
    from rembg import remove

    return remove(image, session=session)


class RembgSegmenter:
    def __init__(
        self,
        *,
        session_factory: Callable[[], object] = _new_rembg_session,
        remove_func: Callable[..., Image.Image] = _remove_background,
    ) -> None:
        self._session_factory = session_factory
        self._remove_func = remove_func
        self._session: object | None = None
        self._session_lock = Lock()

    def _get_session(self) -> object:
        if self._session is not None:
            return self._session
        with self._session_lock:
            if self._session is None:
                self._session = self._session_factory()
            return self._session

    def __call__(self, image: Image.Image) -> Image.Image:
        result = self._remove_func(image, session=self._get_session())
        return result.convert("RGBA")


def make_canny_rgb(image: Image.Image) -> Image.Image:
    import cv2
    import numpy as np

    gray = cv2.cvtColor(np.asarray(image.convert("RGB")), cv2.COLOR_RGB2GRAY)
    edges = cv2.Canny(gray, 100, 200)
    edges_rgb = np.repeat(edges[:, :, None], 3, axis=2)
    return Image.fromarray(edges_rgb, mode="RGB")


class ProductPreprocessor:
    def __init__(
        self,
        *,
        cache: TTLCache[str, ProductArtifacts],
        downloader: Callable[[str], Image.Image],
        segmenter: Callable[[Image.Image], Image.Image],
        canny_builder: Callable[[Image.Image], Image.Image] = make_canny_rgb,
        image_size: int,
        product_fill_ratio: float,
        include_canny: bool = True,
    ) -> None:
        self._cache = cache
        self._downloader = downloader
        self._segmenter = segmenter
        self._canny_builder = canny_builder
        self._image_size = image_size
        self._product_fill_ratio = product_fill_ratio
        self._include_canny = include_canny

    def prepare(self, cache_key: str, image_url: str) -> PreparationResult:
        artifacts, cache_hit = self._cache.get_or_create(
            cache_key,
            lambda: self._build_artifacts(image_url),
        )
        return PreparationResult(artifacts=artifacts, cache_hit=cache_hit)

    def _build_artifacts(self, image_url: str) -> ProductArtifacts:
        original = self._downloader(image_url)
        segmented = self._segmenter(original)
        product_rgba = fit_product_rgba(
            segmented,
            canvas_size=(self._image_size, self._image_size),
            fill_ratio=self._product_fill_ratio,
        )
        alpha_mask = product_rgba.getchannel("A")
        product_on_white = Image.new("RGB", product_rgba.size, "white")
        product_on_white.paste(product_rgba, mask=alpha_mask)
        canny_image: Image.Image | None = None
        if self._include_canny:
            canny_image = self._canny_builder(product_on_white).convert("RGB")
            if canny_image.size != product_rgba.size:
                canny_image = canny_image.resize(
                    product_rgba.size,
                    Image.Resampling.BILINEAR,
                )
        return ProductArtifacts(
            product_rgba=product_rgba,
            product_on_white=product_on_white,
            alpha_mask=alpha_mask,
            canny_image=canny_image,
        )
