# -*- coding: utf-8 -*-
"""
Generate extension icons.

Priority:
  1. source_logo.jpg in this folder  (the icon image chosen by the user)
  2. kmutt_logo.png at the project root
  3. Fallback: pure-stdlib geometric icon (no Pillow needed)

All sources are center-cropped to a square and resized to 128/48/16
(high-quality LANCZOS).

Usage:
    python generate_icons.py
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SOURCE_CANDIDATES = [
    os.path.join(HERE, "source_logo.jpg"),
    os.path.abspath(os.path.join(HERE, "..", "..", "..", "kmutt_logo.png")),
]
SIZES = (128, 48, 16)


def _from_image(path: str) -> bool:
    try:
        from PIL import Image
    except ImportError:
        return False
    try:
        im = Image.open(path).convert("RGBA")
    except Exception:
        return False

    # Center-crop to a square if the source is not square
    w, h = im.size
    side = min(w, h)
    left = (w - side) // 2
    top = (h - side) // 2
    im = im.crop((left, top, left + side, top + side))

    for size in SIZES:
        out = im.resize((size, size), Image.LANCZOS)
        out.save(os.path.join(HERE, f"icon{size}.png"))
        print(f"icon{size}.png written (from {os.path.basename(path)}, {size}x{size})")
    return True


def _from_geometry() -> None:
    """Pure-stdlib fallback: blue rounded square + white document glyph."""
    import struct
    import zlib

    BG = (30, 58, 95)
    DOC = (255, 255, 255)
    LINE = (37, 99, 235)

    def make_png(size, pixels):
        def chunk(tag, data):
            c = struct.pack(">I", len(data)) + tag + data
            c += struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
            return c

        raw = b""
        for row in pixels:
            raw += b"\x00" + b"".join(struct.pack("BBB", *px) for px in row)
        return (b"\x89PNG\r\n\x1a\n"
                + chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0))
                + chunk(b"IDAT", zlib.compress(raw, 9))
                + chunk(b"IEND", b""))

    def rounded_rect(canvas, x0, y0, x1, y1, radius, fill):
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                cx = min(x - x0, x1 - x)
                cy = min(y - y0, y1 - y)
                if cx < radius and cy < radius:
                    dx, dy = radius - cx - 1, radius - cy - 1
                    if dx * dx + dy * dy > radius * radius:
                        continue
                canvas[y][x] = fill

    for size in SIZES:
        canvas = [[BG for _ in range(size)] for _ in range(size)]
        m = max(1, int(size * 0.04))
        rounded_rect(canvas, m, m, size - 1 - m, size - 1 - m, max(2, int(size * 0.16)), BG)
        dx0, dy0 = int(size * 0.24), int(size * 0.20)
        dx1, dy1 = int(size * 0.76), int(size * 0.82)
        rounded_rect(canvas, dx0, dy0, dx1, dy1, max(1, int(size * 0.05)), DOC)
        fold = int(size * 0.18)
        for i in range(fold):
            for j in range(fold - i):
                x, y = dx1 - j, dy0 + i
                if 0 <= x < size and 0 <= y < size:
                    canvas[y][x] = BG
        lx0, lx1 = int(size * 0.32), int(size * 0.68)
        widths = [0.36, 0.52, 0.42]
        lh = max(1, int(size * 0.07))
        for k, w in enumerate(widths):
            y = int(size * 0.36) + k * int(size * 0.16)
            x1 = int(lx0 + (lx1 - lx0) * w)
            for y2 in range(y, y + lh):
                for x in range(lx0, x1 + 1):
                    canvas[y2][x] = LINE
        with open(os.path.join(HERE, f"icon{size}.png"), "wb") as f:
            f.write(make_png(size, canvas))
        print(f"icon{size}.png written (geometric fallback)")


if __name__ == "__main__":
    for cand in SOURCE_CANDIDATES:
        if os.path.exists(cand) and _from_image(cand):
            sys.exit(0)
    print("logo source not found — using geometric fallback")
    _from_geometry()
