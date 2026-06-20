"""Image normalization for mixed-format claim uploads."""

from __future__ import annotations

import io
from pathlib import Path

from PIL import Image

try:
    from pillow_heif import register_heif_opener

    register_heif_opener()
except ImportError:
    pass

try:
    import pillow_avif  # noqa: F401
except ImportError:
    pass


def normalize_image_bytes(path: Path) -> tuple[bytes, str]:
    raw = path.read_bytes()
    if raw[:2] == b"\xff\xd8":
        return raw, "image/jpeg"

    with Image.open(path) as img:
        rgb = img.convert("RGB")
        buffer = io.BytesIO()
        rgb.save(buffer, format="JPEG", quality=90)
        return buffer.getvalue(), "image/jpeg"
