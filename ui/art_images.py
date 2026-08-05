"""Album-art image helpers (crop / rounded thumbnail)."""

from __future__ import annotations

from PIL import Image, ImageDraw


def _centre_crop_square(image: Image.Image) -> Image.Image:
    """Centre-crop to square so later square resizes do not squash the art."""
    width, height = image.size
    if width <= 0 or height <= 0:
        return image
    if width == height:
        return image
    side = min(width, height)
    left = (width - side) // 2
    top = (height - side) // 2
    return image.crop((left, top, left + side, top + side))


def _rounded_thumbnail(image: Image.Image, size: int, radius: int) -> Image.Image:
    """Square thumbnail with rounded corners.

    The art label's corner_radius is invisible on its own because the image
    covers it, so the rounding has to live in the image itself.
    """
    square = _centre_crop_square(image)
    thumb = square.resize((size, size), Image.Resampling.LANCZOS)
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        (0, 0, size - 1, size - 1),
        radius=radius,
        fill=255,
    )
    thumb.putalpha(mask)
    return thumb
