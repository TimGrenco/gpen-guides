#!/usr/bin/env python3
"""Build the stacked two-circle step image (used for a Clean step with two close-ups).

Geometry was measured from the original Hydout step-04-clean.jpg (582x760 at 1x).
Usage: compose_step_pair.py TOP_SRC BOTTOM_SRC OUT [--as-is]
  --as-is  the two sources are already-framed square images: keep their framing and
           just flatten them onto the plate (otherwise each render is cut out and centred).
"""

import sys

from PIL import Image, ImageDraw

from compose_step import PLATE, bbox_of_mask, remove_background

BASE_W, BASE_H = 582, 760
TOP_CENTER, BOT_CENTER = (270, 199), (270, 542)
RADIUS = 190
SCALE = 2


def circular_patch(src_path, diameter, pad_frac=0.08, as_is=False):
    if as_is:
        framed = Image.open(src_path).convert("RGBA")
        if framed.width != framed.height:
            raise SystemExit(f"{src_path}: --as-is needs a square image, got {framed.size}")
        square = Image.new("RGBA", framed.size, PLATE + (255,))
        square.alpha_composite(framed)
    else:
        rgba, fg_mask = remove_background(Image.open(src_path).convert("RGB"))
        x0, y0, x1, y1 = bbox_of_mask(fg_mask)
        cropped = rgba.crop((x0, y0, x1 + 1, y1 + 1))
        fg_w, fg_h = cropped.size
        side = max(fg_w, fg_h)
        square_side = side + int(side * pad_frac) * 2
        square = Image.new("RGBA", (square_side, square_side), PLATE + (255,))
        square.alpha_composite(cropped, ((square_side - fg_w) // 2, (square_side - fg_h) // 2))
    square = square.resize((diameter, diameter), Image.LANCZOS)

    mask = Image.new("L", (diameter, diameter), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, diameter - 1, diameter - 1), fill=255)
    circular = Image.new("RGBA", (diameter, diameter), (0, 0, 0, 0))
    circular.paste(square, (0, 0), mask)
    return circular


def build(top_src, bot_src, out_path, as_is=False):
    canvas = Image.new("RGBA", (BASE_W * SCALE, BASE_H * SCALE), (255, 255, 255, 255))
    diameter = RADIUS * 2 * SCALE
    for src, (cx, cy) in ((top_src, TOP_CENTER), (bot_src, BOT_CENTER)):
        canvas.alpha_composite(
            circular_patch(src, diameter, as_is=as_is),
            ((cx - RADIUS) * SCALE, (cy - RADIUS) * SCALE),
        )
    canvas.convert("RGB").save(out_path, quality=92)
    print(f"saved {out_path} size={canvas.size}")


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a != "--as-is"]
    build(*args[:3], as_is="--as-is" in sys.argv[1:])
