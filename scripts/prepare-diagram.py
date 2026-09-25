#!/usr/bin/env python3
"""Trim, resize and optimise a hand-drawn diagram for the site.

Diagrams are exported with generous transparent margins and at a far higher
resolution than the page needs. This trims to the drawn content, scales to a
sensible display width, and palette-quantises (these drawings use few colours,
so this is typically a 5-7x saving with no visible loss).

When both a light and a dark variant are given they are cropped to the *same*
box, so the two images stay pixel-aligned when the browser swaps them under
prefers-color-scheme. Re-run with both variants whenever either is re-exported.

Usage:
    pixi run --manifest-path ~/ap-stats/pixi.toml \
        python scripts/prepare-diagram.py NAME LIGHT.png [DARK.png]

Writes public/images/NAME.png and, when given, public/images/NAME-dark.png.
"""

import argparse
from pathlib import Path

import numpy as np
from PIL import Image

OUT_DIR = Path(__file__).resolve().parent.parent / "public" / "images"
BLEED = 24
COLOURS = 128


def content_box(path: Path) -> tuple[int, int, int, int]:
    alpha = np.array(Image.open(path).convert("RGBA"))[:, :, 3] > 10
    rows = np.where(alpha.any(axis=1))[0]
    cols = np.where(alpha.any(axis=0))[0]
    if not len(rows) or not len(cols):
        raise SystemExit(f"{path} is fully transparent")
    return int(cols.min()), int(rows.min()), int(cols.max()), int(rows.max())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("name", help="Output basename, e.g. grid-babysitting")
    parser.add_argument("light", type=Path)
    parser.add_argument("dark", type=Path, nargs="?")
    parser.add_argument("--width", type=int, default=2600)
    args = parser.parse_args()

    sources = [("", args.light)] + ([("-dark", args.dark)] if args.dark else [])

    sizes = {Image.open(p).size for _, p in sources}
    if len(sizes) > 1:
        raise SystemExit(f"variants differ in canvas size: {sizes}")

    # One box covering the content of every variant keeps them aligned.
    boxes = [content_box(p) for _, p in sources]
    x0 = min(b[0] for b in boxes) - BLEED
    y0 = min(b[1] for b in boxes) - BLEED
    x1 = max(b[2] for b in boxes) + 1 + BLEED
    y1 = max(b[3] for b in boxes) + 1 + BLEED
    w, h = Image.open(args.light).size
    box = (max(0, x0), max(0, y0), min(w, x1), min(h, y1))
    print(f"shared crop box {box}")

    for suffix, path in sources:
        im = Image.open(path).convert("RGBA").crop(box)
        height = round(im.height * args.width / im.width)
        resized = im.resize((args.width, height), Image.LANCZOS)
        out = OUT_DIR / f"{args.name}{suffix}.png"
        resized.quantize(colors=COLOURS, method=Image.Quantize.FASTOCTREE).save(
            out, optimize=True
        )
        kb = out.stat().st_size / 1024
        print(f"wrote {out.name}  {args.width}x{height}  {kb:.0f} KB")
    print(f"\nUse in a page: <Diagram name=\"{args.name}\" "
          f'width={{{args.width}}} height={{{height}}} alt="..." caption="..." />')


if __name__ == "__main__":
    main()
