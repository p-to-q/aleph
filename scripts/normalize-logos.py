#!/usr/bin/env python3
"""Normalize logo PNGs without clipping the horns artwork."""

from __future__ import annotations

from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "web" / "public"
ALEPH_LOGO = "aleph-logo.png"
HORNS_LOGO = "horns.png"


def scale_to_max_edge(im: Image.Image, target_max: int) -> Image.Image:
    w, h = im.size
    scale = target_max / max(w, h)
    return im.resize(
        (max(1, round(w * scale)), max(1, round(h * scale))),
        Image.Resampling.LANCZOS,
    )


def main() -> None:
    with Image.open(PUBLIC / ALEPH_LOGO) as source:
        aleph = scale_to_max_edge(source.convert("RGBA"), 713).copy()
    with Image.open(PUBLIC / HORNS_LOGO) as source:
        horns = source.convert("RGBA").copy()

    aleph.save(PUBLIC / ALEPH_LOGO, optimize=True)
    horns.save(PUBLIC / HORNS_LOGO, optimize=True)
    print(f"{ALEPH_LOGO}: normalized to {aleph.size}")
    print(f"{HORNS_LOGO}: preserved at {horns.size}")


if __name__ == "__main__":
    main()
