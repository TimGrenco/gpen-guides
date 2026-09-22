#!/usr/bin/env python3
"""Place a white-background product render on the site's gray plate as a square step image.

The circular mask is applied in CSS (.step-circle), so only a centred square is needed.
Usage: compose_step.py SRC OUT [--crop x0,y0,x1,y1]   (crop drops stray studio props first)
       compose_step.py SRC OUT --as-is                 (already-framed square image: only flatten onto the plate)
Needs: pip3 install pillow numpy scipy
"""

import sys

import numpy as np
from PIL import Image
from scipy import ndimage

PLATE = (228, 229, 231)  # matches --plate (#E4E5E7) in the templates
CANVAS = 900
PAD_FRAC = 0.09


def remove_background(img, white_thresh=244):
    arr = np.array(img.convert("RGB"))
    near_white = np.all(arr >= white_thresh, axis=2)
    labeled, _ = ndimage.label(near_white)
    border = set(labeled[0, :]) | set(labeled[-1, :]) | set(labeled[:, 0]) | set(labeled[:, -1])
    border.discard(0)
    bg_mask = np.isin(labeled, list(border))
    out = arr.copy()
    out[bg_mask] = PLATE
    alpha = np.where(bg_mask, 0, 255).astype(np.uint8)
    return Image.fromarray(np.dstack([out, alpha])), ~bg_mask


def bbox_of_mask(mask):
    ys, xs = np.where(mask)
    return xs.min(), ys.min(), xs.max(), ys.max()


def compose(src_path, out_path, crop=None, canvas=CANVAS, pad_frac=PAD_FRAC):
    img = Image.open(src_path).convert("RGB")
    if crop:
        img = img.crop(crop)
    rgba, fg_mask = remove_background(img)
    x0, y0, x1, y1 = bbox_of_mask(fg_mask)
    fg_w, fg_h = x1 - x0, y1 - y0
    cropped = rgba.crop((x0, y0, x1 + 1, y1 + 1))

    side = max(fg_w, fg_h)
    pad = int(side * pad_frac)
    square_side = side + pad * 2

    square = Image.new("RGBA", (square_side, square_side), PLATE + (255,))
    square.alpha_composite(cropped, ((square_side - fg_w) // 2, (square_side - fg_h) // 2))
    square.resize((canvas, canvas), Image.LANCZOS).convert("RGB").save(out_path, quality=92)
    print(f"{src_path} -> {out_path}")


def flatten(src_path, out_path, canvas=CANVAS):
    img = Image.open(src_path).convert("RGBA")
    if img.width != img.height:
        raise SystemExit(f"{src_path}: --as-is needs a square image, got {img.size}")
    flat = Image.new("RGBA", img.size, PLATE + (255,))
    flat.alpha_composite(img)
    flat = flat.convert("RGB")
    if flat.width != canvas:
        flat = flat.resize((canvas, canvas), Image.LANCZOS)
    flat.save(out_path, quality=92)
    print(f"{src_path} -> {out_path}")


if __name__ == "__main__":
    args = sys.argv[1:]
    if "--as-is" in args:
        args.remove("--as-is")
        flatten(args[0], args[1])
        raise SystemExit
    crop = None
    if "--crop" in args:
        i = args.index("--crop")
        crop = tuple(int(v) for v in args[i + 1].split(","))
        del args[i:i + 2]
    compose(args[0], args[1], crop=crop)
