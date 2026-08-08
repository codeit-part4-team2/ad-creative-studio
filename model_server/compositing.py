from __future__ import annotations

from PIL import Image, ImageFilter


def fit_product_rgba(
    image: Image.Image,
    *,
    canvas_size: tuple[int, int],
    fill_ratio: float = 0.5,
    bottom_ratio: float = 0.9,
) -> Image.Image:
    if not 0 < fill_ratio <= 1:
        raise ValueError("fill_ratio must be in the interval (0, 1]")
    if not 0 < bottom_ratio <= 1:
        raise ValueError("bottom_ratio must be in the interval (0, 1]")

    rgba = image.convert("RGBA")
    alpha_bbox = rgba.getchannel("A").getbbox()
    if alpha_bbox is None:
        raise ValueError("product image has no visible pixels")
    product = rgba.crop(alpha_bbox)

    canvas_width, canvas_height = canvas_size
    max_width = max(1, round(canvas_width * fill_ratio))
    max_height = max(1, round(canvas_height * fill_ratio))
    scale = min(max_width / product.width, max_height / product.height)
    target_size = (
        max(1, round(product.width * scale)),
        max(1, round(product.height * scale)),
    )
    product = product.resize(target_size, Image.Resampling.LANCZOS)

    x = (canvas_width - product.width) // 2
    desired_bottom = round(canvas_height * bottom_ratio)
    y = min(canvas_height - product.height, max(0, desired_bottom - product.height))
    canvas = Image.new("RGBA", canvas_size, (0, 0, 0, 0))
    canvas.alpha_composite(product, (x, y))
    return canvas


def composite_product(
    background: Image.Image,
    product_rgba: Image.Image,
    *,
    add_shadow: bool = True,
) -> Image.Image:
    if background.size != product_rgba.size:
        raise ValueError("background and product canvas must have the same size")

    result = background.convert("RGBA")
    product = product_rgba.convert("RGBA")
    if add_shadow:
        alpha = product.getchannel("A")
        radius = max(2, round(max(product.size) * 0.012))
        shadow_alpha = alpha.filter(ImageFilter.GaussianBlur(radius=radius))
        shadow = Image.new("RGBA", product.size, (0, 0, 0, 0))
        shadow.putalpha(shadow_alpha.point(lambda value: round(value * 0.35)))
        offset = max(2, round(product.height * 0.012))
        shifted_shadow = Image.new("RGBA", product.size, (0, 0, 0, 0))
        shifted_shadow.alpha_composite(shadow, (0, offset))
        result = Image.alpha_composite(result, shifted_shadow)

    result = Image.alpha_composite(result, product)
    return result.convert("RGB")
