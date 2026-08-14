#!/usr/bin/env python3
"""Build the G Pen product-guide site from src/.

Output layout (this is what GitHub Pages serves from the repo root):

    index.html              portal index, one card per product
    <product>/index.html    the guide         -> /<product>/
    <product>/offline.html  single-file copy, images inlined as data URIs
    <product>/img/*         image assets

The clean /<product>/ URL is the one that ends up inside a printed QR code,
so it should stay stable once a code has shipped.

Run:  python3 build.py
"""

import base64
import mimetypes
import pathlib
import shutil

ROOT = pathlib.Path(__file__).parent
SRC = ROOT / "src"

MANUAL_PDF = ("https://cdn.shopify.com/s/files/1/0185/1576/files/"
              "20250528_GPen_Hydout_Manual.pdf?v=1749240232")

PRODUCTS = {
    "hydout": {
        "template": "hydout.template.html",
        "name": "G Pen Hydout",
        "category": "510 Cartridge Battery",
        "meta": "4 steps · 2 videos",
        "card_image": "hero.png",
        "images": {
            "HERO":  "hero.png",
            "STEP1": "step-01-charge.jpg",
            "STEP2": "step-02-load.jpg",
            "STEP3": "step-03-activate.jpg",
            "STEP4": "step-04-clean.jpg",
            "VID1":  "video-how-to-use.jpg",
            "VID2":  "video-how-to-clean.jpg",
        },
        "text": {"MANUAL_PDF": MANUAL_PDF},
    },
}

CARD = """      <a class="card" href="{slug}/">
        <span class="thumb"><img src="{slug}/img/{card_image}" alt="" loading="lazy"></span>
        <span>
          <span class="eyebrow">{category}</span>
          <h2>{name}</h2>
          <p class="meta">{meta}</p>
        </span>
      </a>"""


def data_uri(path: pathlib.Path) -> str:
    mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    return f"data:{mime};base64," + base64.b64encode(path.read_bytes()).decode()


def write(path: pathlib.Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    rel = path.relative_to(ROOT)
    print(f"  {str(rel):34} {path.stat().st_size / 1024:8.1f} KB")


def build_product(slug: str, spec: dict) -> None:
    template = (SRC / spec["template"]).read_text()
    out_dir = ROOT / slug
    img_dir = out_dir / "img"

    # Rebuild the image folder so removed assets don't linger.
    if img_dir.exists():
        shutil.rmtree(img_dir)
    img_dir.mkdir(parents=True)

    hosted, offline = template, template
    for key, filename in spec["images"].items():
        src = SRC / filename
        shutil.copy(src, img_dir / filename)
        hosted = hosted.replace("{{%s}}" % key, f"img/{filename}")
        offline = offline.replace("{{%s}}" % key, data_uri(src))

    # The brand mark links back to the index when hosted; the single-file copy
    # has no index to return to, so it points at the public site instead.
    hosted = hosted.replace("{{HOME}}", "../")
    offline = offline.replace("{{HOME}}", "https://www.gpen.com")

    for key, value in spec["text"].items():
        hosted = hosted.replace("{{%s}}" % key, value)
        offline = offline.replace("{{%s}}" % key, value)

    write(out_dir / "index.html", hosted)
    write(out_dir / "offline.html", offline)


def build_index() -> None:
    template = (SRC / "index.template.html").read_text()
    cards = "\n".join(
        CARD.format(slug=slug, card_image=spec["card_image"], category=spec["category"],
                    name=spec["name"], meta=spec["meta"])
        for slug, spec in PRODUCTS.items()
    )
    write(ROOT / "index.html", template.replace("{{CARDS}}", cards))


if __name__ == "__main__":
    print("Building G Pen product guides\n")
    for slug, spec in PRODUCTS.items():
        build_product(slug, spec)
    build_index()

    stale = [p for p in ("hydout.html", "hydout-standalone.html") if (ROOT / p).exists()]
    if stale:
        print("\nRemoving files from the old flat layout:")
        for name in stale:
            (ROOT / name).unlink()
            print(f"  {name}")
    if (ROOT / "img").exists():
        shutil.rmtree(ROOT / "img")
        print("  img/")

    print(f"\nDone. Preview with: python3 serve.py")
