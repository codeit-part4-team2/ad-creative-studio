from __future__ import annotations

from PIL import Image

from model_server.compositing import composite_product, fit_product_rgba


def test_fit_product_preserves_aspect_ratio_and_bottom_center_anchor() -> None:
    source = Image.new("RGBA", (20, 10), (220, 10, 20, 255))

    fitted = fit_product_rgba(
        source,
        canvas_size=(100, 100),
        fill_ratio=0.5,
        bottom_ratio=0.9,
    )

    assert fitted.size == (100, 100)
    assert fitted.getbbox() == (25, 65, 75, 90)


def test_composite_product_keeps_opaque_source_color_exactly() -> None:
    background = Image.new("RGB", (20, 20), (0, 0, 255))
    product = Image.new("RGBA", (20, 20), (0, 0, 0, 0))
    product.putpixel((10, 10), (220, 10, 20, 255))

    result = composite_product(background, product, add_shadow=False)

    assert result.mode == "RGB"
    assert result.getpixel((10, 10)) == (220, 10, 20)
    assert result.getpixel((0, 0)) == (0, 0, 255)


def test_composite_product_rejects_mismatched_canvas_size() -> None:
    background = Image.new("RGB", (20, 20), "white")
    product = Image.new("RGBA", (10, 10), (0, 0, 0, 0))

    try:
        composite_product(background, product)
    except ValueError as exc:
        assert "same size" in str(exc)
    else:
        raise AssertionError("mismatched canvases must be rejected")
