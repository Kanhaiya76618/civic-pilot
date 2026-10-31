"""Document preparation: make citizen files fit each portal's format and size limits.

Images are converted to JPEG, downscaled and re-encoded until they fit.
PDFs cannot be shrunk safely here, so an oversize PDF is rejected with a
message the citizen can act on.
"""

from __future__ import annotations

import io
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageOps

from .registry import DocDef


class DocError(Exception):
    pass


@dataclass
class PreparedDoc:
    key: str
    path: Path
    size_kb: float
    note: str


def _detect(data: bytes) -> str:
    if data[:4] == b"%PDF":
        return "pdf"
    if data[:3] == b"\xff\xd8\xff":
        return "jpg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    return "unknown"


def prepare(src: Path, rule: DocDef, out_dir: Path) -> PreparedDoc:
    data = src.read_bytes()
    kind = _detect(data)
    limit = rule.max_kb * 1024
    formats = {f.lower().replace("jpeg", "jpg") for f in rule.formats}
    out_dir.mkdir(parents=True, exist_ok=True)

    if kind == "pdf":
        if "pdf" not in formats:
            raise DocError(f"{rule.key}: portal accepts {sorted(formats)}, got a PDF")
        if len(data) > limit:
            raise DocError(
                f"{rule.key}: PDF is {len(data) // 1024} KB, portal limit is {rule.max_kb} KB. "
                "Ask the citizen for a smaller scan or a photo of the page."
            )
        out = out_dir / f"{rule.key}.pdf"
        out.write_bytes(data)
        return PreparedDoc(rule.key, out, len(data) / 1024, "PDF within limit, unchanged")

    if kind == "unknown":
        raise DocError(f"{rule.key}: unsupported file type")
    if "jpg" not in formats:
        raise DocError(f"{rule.key}: portal accepts {sorted(formats)}; image conversion to those is not supported")

    img = ImageOps.exif_transpose(Image.open(io.BytesIO(data))).convert("RGB")
    too_big_px = bool(rule.max_px and max(img.size) > rule.max_px)
    if too_big_px:
        img.thumbnail((rule.max_px, rule.max_px))
    if kind == "jpg" and len(data) <= limit and not too_big_px:
        out = out_dir / f"{rule.key}.jpg"
        out.write_bytes(data)
        return PreparedDoc(rule.key, out, len(data) / 1024, "JPEG within limit, unchanged")

    for _ in range(8):
        for quality in (85, 75, 65, 55, 45, 35):
            buf = io.BytesIO()
            img.save(buf, "JPEG", quality=quality, optimize=True)
            if buf.tell() <= limit:
                out = out_dir / f"{rule.key}.jpg"
                out.write_bytes(buf.getvalue())
                return PreparedDoc(
                    rule.key, out, buf.tell() / 1024, f"re-encoded to {img.size[0]}x{img.size[1]} JPEG q{quality}"
                )
        if min(img.size) < 200:
            break
        img = img.resize((int(img.size[0] * 0.75), int(img.size[1] * 0.75)), Image.LANCZOS)
    raise DocError(f"{rule.key}: could not compress below {rule.max_kb} KB without making it unreadable")
