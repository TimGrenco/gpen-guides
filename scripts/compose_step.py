#!/usr/bin/env python3
"""Place a white-background product render on the site's gray plate as a square step image.

The circular mask is applied in CSS (.step-circle), so only a centred square is needed.
Usage: compose_step.py SRC OUT [--crop x0,y0,x1,y1]   (crop drops stray studio props first)
       compose_step.py SRC OUT --as-is                 (already-framed square image: only flatten onto the plate)
Needs: pip3 install pillow numpy scipy
"""

import sys

import numpy as np
from PIL import Image, ImageFilter
from scipy import ndimage

PLATE = (228, 229, 231)  # matches --plate (#E4E5E7) in the templates
PLATE_F = np.array(PLATE, dtype=np.float32)
CANVAS = 900
PAD_FRAC = 0.09


def foreground_mask(arr, hard_thresh=244, connect_thresh=120, sat_thresh=0.10, bright_thresh=130):
    """True where a pixel is product/subject, False where it's studio background.

    A plain "near-white" flood fill misses soft shadow gradients on the sweep (they dip
    below the pure-white threshold but are still background), leaving a visible gray smear
    around the product once composited onto the flat plate. So background here is the union
    of two things, both restricted to the region reachable from the image border through
    at-least-dim-gray pixels (so we never touch anything enclosed by the product itself):
      - pure white/near-white (hard_thresh)
      - low-saturation ("gray"), moderately bright pixels (shadow reads as neutral gray;
        black plastic and skin don't, regardless of how dark or bright they are)
    """
    mx = arr.max(axis=2)
    mn = arr.min(axis=2)
    sat = np.where(mx > 0, (mx - mn) / np.maximum(mx, 1), 0)
    brightness = arr.mean(axis=2)

    labeled, _ = ndimage.label(brightness >= connect_thresh)
    border_labels = set(labeled[0, :]) | set(labeled[-1, :]) | set(labeled[:, 0]) | set(labeled[:, -1])
    border_labels.discard(0)
    reachable = np.isin(labeled, list(border_labels))

    shadow_like = reachable & (sat <= sat_thresh) & (brightness >= bright_thresh)
    pure_white = reachable & np.all(arr >= hard_thresh, axis=2)
    return ~(shadow_like | pure_white)


def bbox_of_mask(mask):
    ys, xs = np.where(mask)
    return xs.min(), ys.min(), xs.max(), ys.max()


def compose(src_path, out_path, crop=None, feather=10, canvas=CANVAS, pad_frac=PAD_FRAC):
    img = Image.open(src_path).convert("RGB")
    if crop:
        img = img.crop(crop)
    arr = np.array(img).astype(np.float32)

    fg_mask = foreground_mask(arr)
    # feather the fg/bg boundary so a soft blend to plate replaces any hard cutoff line
    alpha = (fg_mask.astype(np.float32) * 255).astype(np.uint8)
    alpha_soft = np.array(Image.fromarray(alpha).filter(ImageFilter.GaussianBlur(feather))).astype(np.float32) / 255.0
    blended = (arr * alpha_soft[..., None] + PLATE_F[None, None, :] * (1 - alpha_soft[..., None])).clip(0, 255).astype(np.uint8)

    x0, y0, x1, y1 = bbox_of_mask(fg_mask)
    fg_w, fg_h = x1 - x0, y1 - y0
    side = max(fg_w, fg_h)
    pad = int(side * pad_frac)
    square_side = side + pad * 2

    square = np.full((square_side, square_side, 3), PLATE, dtype=np.uint8)
    crop_arr = blended[y0:y1 + 1, x0:x1 + 1]
    oy, ox = (square_side - fg_h) // 2, (square_side - fg_w) // 2
    square[oy:oy + crop_arr.shape[0], ox:ox + crop_arr.shape[1]] = crop_arr

    Image.fromarray(square).resize((canvas, canvas), Image.LANCZOS).save(out_path, quality=92)
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
