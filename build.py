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
import datetime
import html as htmllib
import json
import mimetypes
import pathlib
import shutil

ROOT = pathlib.Path(__file__).parent
SRC = ROOT / "src"
I18N_DIR = ROOT / "i18n"
YEAR = str(datetime.date.today().year)

MANUAL_PDF = ("https://cdn.shopify.com/s/files/1/0185/1576/files/"
              "20250528_GPen_Hydout_Manual.pdf?v=1749240232")

# Shopify CDN images for products that don't have local guide pages yet.
# Pulled live from gpen.com/products.json (September 2026).
_CDN = "https://cdn.shopify.com/s/files/1/0185/1576/files/"

PRODUCTS = {
    # ── Products with completed local guide pages ─────────────────────────────
    "hydout": {
        "template": "hydout.template.html",
        "name": "G Pen Hydout",
        "category": "510 Cartridge Battery",
        "card_image": "hero.png",           # local file in src/
        "images": {
            "HERO":  "hero.png",
            "STEP1": "step-01-charge.jpg",
            "STEP2": "step-02-load.jpg",
            "STEP3": "step-03-activate.jpg",
            "STEP4": "step-04-clean.jpg",
            "STEP4B": "step-04b-clean.jpg",
            "VID1":  "video-how-to-use.jpg",
            "VID2":  "video-how-to-clean.jpg",
        },
        "text": {"MANUAL_PDF": MANUAL_PDF},
        "shop_button": ("Shop the Hydout collection", "https://www.gpen.com/collections/g-pen-hydout-collection"),
    },
    "dash-ii": {
        "template": "dash-ii.template.html",
        "name": "G Pen Dash II",
        "category": "Dry Herb Vaporizer",
        "card_image": "dash-ii-card.png",   # local file in src/
        "images": {
            "HERO":  "dash-ii-hero.png",
            "CARD":  "dash-ii-card.png",    # card img must be in images so build copies it
            "STEP1": "dash-ii-step-01-charge.jpg",
            "STEP2": "dash-ii-step-02-load.jpg",
            "STEP3": "dash-ii-step-03-activate.jpg",
            "STEP4": "dash-ii-step-04-clean.jpg",
            "VID1":  "dash-ii-video-how-to-use.jpg",
            "VID2":  "dash-ii-video-cleaning.jpg",
        },
        "text": {},
    },
    "510-original": {
        "template": "510-original.template.html",
        "name": "G Pen 510 Original",
        "category": "510 Cartridge Battery",
        "card_image": "510-original-card.png",
        "images": {
            "HERO":  "510-original-hero.png",
            "CARD":  "510-original-card.png",
            "STEP1": "510-original-step-01-charge.jpg",
            "STEP2": "510-original-step-02-load.jpg",
            "STEP3": "510-original-step-03-activate.jpg",
            "STEP4": "510-original-step-04-clean.jpg",
            "VID1":  "510-original-video-how-to-use.jpg",
            "VID2":  "510-original-video-cleaning.jpg",
        },
        "text": {},
        "shop_button": ("Shop the Retro collection", "https://www.gpen.com/collections/g-pen-510-original-retro-collection"),
    },
    "micro-ii": {
        "template": "micro-ii.template.html",
        "name": "G Pen Micro II",
        "category": "Concentrate Vaporizer",
        "card_image": "micro-ii-card.png",
        "images": {
            "HERO":  "micro-ii-hero.jpg",
            "CARD":  "micro-ii-card.png",
            "STEP1": "micro-ii-step-01-charge.jpg",
            "STEP2": "micro-ii-step-02-load.jpg",
            "STEP3": "micro-ii-step-03-activate.jpg",
            "STEP4": "micro-ii-step-04-clean.jpg",
            "STEP5": "micro-ii-step-05-alerts.jpg",
            "ATTACH_SIDECAR": "micro-ii-attach-sidecar.jpg",
            "ATTACH_ADAPTER": "micro-ii-attach-rig-adapter.jpg",
            "VID1":  "micro-ii-video-how-to-use.jpg",
            "VID2":  "micro-ii-video-cleaning.jpg",
        },
        "text": {},
    },
    "melt": {
        "template": "melt.template.html",
        "name": "G Pen Melt",
        "category": "Hot Knife / Dab Tool",
        "card_image": "melt-card.png",
        "images": {
            "HERO":  "melt-hero.png",
            "CARD":  "melt-card.png",
            "STEP1": "melt-step-01-charge.jpg",
            "STEP2": "melt-step-02-activate.jpg",
            "STEP3": "melt-step-03-scoop.jpg",
            "STEP4": "melt-step-04-clean.jpg",
            "UPG_MICRO_II": "melt-upgrade-micro-ii.png",
            "UPG_MICRO_PLUS": "melt-upgrade-micro-plus.png",
            "VID1":  "melt-video-in-action.jpg",
        },
        "text": {},
        "shop_button": ("Shop all vaporizers", "https://www.gpen.com/collections/vaporizers"),
    },

    "dash-plus": {
        "template": "dash-plus.template.html",
        "name": "G Pen Dash+",
        "category": "Dry Herb Vaporizer",
        "card_image": "dash-plus-card.png",
        "images": {
            "STEP1": "dash-plus-step-01-charge.jpg",
            "STEP2": "dash-plus-step-02-load.jpg",
            "STEP3": "dash-plus-step-03-heat.jpg",
            "STEP4": "dash-plus-step-04-draw.jpg",
            "VID1":  "dash-plus-video-how-to-use.jpg",
            "VID2":  "dash-plus-video-cleaning.jpg",
        },
        "text": {},
    },
    "elite-ii": {
        "template": "elite-ii.template.html",
        "legacy": True,
        "name": "G Pen Elite II",
        "category": "Dry Herb Vaporizer",
        "card_image": "elite-ii-card.png",
        "images": {
            "STEP1": "elite-ii-card.png",
            "STEP2": "elite-ii-card.png",
            "STEP3": "elite-ii-card.png",
            "STEP4": "elite-ii-card.png",
            "VID1":  "elite-ii-video-how-to-use.jpg",
            "VID2":  "elite-ii-video-cleaning.jpg",
        },
        "text": {},
    },
    "micro-plus": {
        "template": "micro-plus.template.html",
        "legacy": True,
        "name": "G Pen Micro+",
        "category": "Concentrate Vaporizer",
        "card_image": "micro-plus-card.png",
        "images": {
            "STEP1": "microplus-step-01-charge.jpg",
            "STEP2": "microplus-step-02-load.jpg",
            "STEP3": "microplus-step-03-heat.jpg",
            "STEP4": "microplus-step-04-draw.jpg",
            "VID1":  "micro-plus-video-how-to-use.jpg",
            "VID2":  "micro-plus-video-cleaning.jpg",
        },
        "text": {},
    },
    "hyer": {
        "template": "hyer.template.html",
        "legacy": True,
        "name": "G Pen Hyer",
        "category": "Concentrate Vaporizer",
        "card_image": "hyer-card.png",
        "images": {
            "STEP1": "hyer-step-01-charge.jpg",
            "STEP2": "hyer-step-02-setup.jpg",
            "STEP3": "hyer-step-03-heat.jpg",
            "STEP4": "hyer-step-04-draw.jpg",
            "VID1":  "hyer-video-how-to-use.jpg",
            "VID2":  "hyer-video-cleaning.jpg",
        },
        "text": {},
    },
    "connect": {
        "template": "connect.template.html",
        "legacy": True,
        "name": "G Pen Connect",
        "category": "Concentrate Vaporizer",
        "card_image": "connect-card.png",
        "images": {
            "STEP1": "connect-step-01-charge.jpg",
            "STEP2": "connect-step-02-setup.jpg",
            "STEP3": "connect-step-03-load.jpg",
            "STEP4": "connect-step-04-draw.jpg",
            "VID1":  "connect-video-how-to-use.jpg",
            "VID2":  "connect-video-cleaning.jpg",
        },
        "text": {},
    },

    # ── Upcoming guide pages — show in switcher, link to gpen.com for now ─────
    # card_image may be a full CDN URL or a local filename in src/.
    "roam": {
        "template": None,
        "legacy": True,
        "name": "G Pen Roam",
        "category": "Portable E-Rig",
        "card_image": _CDN + "Roam_thumb_01.png?v=1768241512",
        "href": "https://www.gpen.com/products/g-pen-roam",
    },
}


def _card_img(s: str, spec: dict, is_switcher: bool = False) -> str:
    """Return the correct image src — CDN URL if absolute, local path otherwise."""
    ci = spec["card_image"]
    if ci.startswith("https://") or ci.startswith("http://"):
        return ci
    prefix = f"../{s}/img/" if is_switcher else f"{s}/img/"
    return prefix + ci


def _card_href(s: str, spec: dict) -> tuple[str, str]:
    """Return (href, extra_attrs) for a product card."""
    if spec.get("template"):
        return f"{s}/", ""
    return spec.get("href", f"https://www.gpen.com/products/{s}"), \
           'target="_blank" rel="noopener noreferrer"'


CARD = """      <a class="card" href="{href}" {extattr}>
        <span class="thumb"><img src="{card_img}" alt="" loading="lazy"></span>
        <span>
          <h2>{name}</h2>
          <span class="eyebrow">{category}</span>
        </span>
      </a>"""

# Card shown inside the product-switcher sheet on each guide page.
SWITCHER_CARD = """      <a class="guide-card" href="{href}" {extattr} {current}>
        <div class="gc-img"><img src="{card_img}" alt="{name}" loading="lazy"></div>
        <div class="gc-body">
          <span class="gc-name">{name}</span>
          <span class="gc-cat">{category}</span>
        </div>
      </a>"""


ACCESSORIES_URL = "https://www.gpen.com/collections/accessories"
ARROW_SVG = ('<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" '
             'stroke-linejoin="round" aria-hidden="true"><line x1="4" y1="10" x2="16" y2="10"/>'
             '<polyline points="11,5 16,10 11,15"/></svg>')


def accessories_html(slug: str) -> str:
    """The body of a guide's Upgrade section: product cards (from src/accessories.json) and a shop button.

    Products the store has no dedicated accessories for get just the button.
    """
    path = SRC / "accessories.json"
    cards = json.loads(path.read_text()).get(slug, []) if path.exists() else []
    out = []
    if cards:
        out.append('    <div class="acc-grid">')
        for i, c in enumerate(cards, start=1):
            img = c["image"]
            if img.startswith("http"):  # store CDN: ask for a card-sized rendition
                img += ("&" if "?" in img else "?") + "width=480"
            href = c.get("url") or f"https://www.gpen.com/products/{c['handle']}"
            # alt attribute needs full escaping; the visible text is set via data-i18n's
            # textContent (not innerHTML), so it must stay UNescaped or entities like
            # &amp;/&#x27; would show up literally once a translation is applied.
            alt = htmllib.escape(c["name"])
            name, note, price = c["name"], c["note"], c["price"]
            out.append(
                f'      <a class="acc-card" href="{href}" target="_blank" rel="noopener noreferrer">\n'
                f'        <img src="{img}" alt="{alt}" loading="lazy">\n'
                '        <div class="acc-card-body">\n'
                f'          <span class="acc-card-name" data-i18n="acc{i}_name">{name}</span>\n'
                f'          <span class="acc-card-price">{price}</span>\n'
                f'          <span class="acc-card-note" data-i18n="acc{i}_note">{note}</span>\n'
                '          <span class="acc-shop" data-i18n="acc_shop">Shop →</span>\n'
                '        </div>\n'
                '      </a>'
            )
        out.append('    </div>')
    label, url = PRODUCTS[slug].get("shop_button") or ("Shop all accessories" if cards else "Shop accessories", ACCESSORIES_URL)
    cls = "upgrade-btn alt" if cards else "upgrade-btn"
    out.append('    <div class="upgrade-cta">')
    out.append(f'      <a class="{cls}" href="{url}" target="_blank" rel="noopener noreferrer" data-i18n="upgrade_btn">')
    out.append(f'        {label}\n        {ARROW_SVG}')
    out.append('      </a>')
    out.append('    </div>')
    return "\n".join(out)


def load_i18n(slug: str):
    """Load translations from i18n/<slug>.json if it exists."""
    path = I18N_DIR / f"{slug}.json"
    if path.exists():
        return json.loads(path.read_text())
    return None


def inject_i18n(html: str, translations: dict) -> str:
    """Inject window._T data block + i18n runtime JS before </body>."""
    runtime = (SRC / "i18n-runtime.js").read_text()
    t_json = json.dumps(translations, ensure_ascii=False)
    injection = (
        f"\n<script>window._T={t_json};</script>\n"
        f"<script>{runtime}</script>\n"
    )
    return html.replace("</body>", injection + "</body>", 1)


def data_uri(path: pathlib.Path) -> str:
    mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    return f"data:{mime};base64," + base64.b64encode(path.read_bytes()).decode()


def write(path: pathlib.Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    rel = path.relative_to(ROOT)
    print(f"  {str(rel):34} {path.stat().st_size / 1024:8.1f} KB")


LEGACY_LABEL = "Legacy products"


def build_switcher(current_slug: str) -> str:
    """Generate the product-switcher card HTML for a given guide page.

    Current products come first; legacy products sit in a collapsed fold that
    opens by default when the visitor is already on a legacy guide.
    """
    featured, legacy = [], []
    for s, spec in PRODUCTS.items():
        current_attr = 'aria-current="true"' if s == current_slug else ""
        href, extattr = _card_href(s, spec)
        # Switcher links are relative to the guide subfolder; adjust local guides.
        if spec.get("template") and s != current_slug:
            href = f"../{s}/"
        elif spec.get("template") and s == current_slug:
            href = "./"
        card = SWITCHER_CARD.format(
            slug=s,
            card_img=_card_img(s, spec, is_switcher=True),
            category=spec["category"],
            name=spec["name"],
            href=href,
            extattr=extattr,
            current=current_attr,
        )
        (legacy if spec.get("legacy") else featured).append(card)

    html = "\n".join(featured)
    if legacy:
        open_attr = " open" if PRODUCTS.get(current_slug, {}).get("legacy") else ""
        html += (
            f'\n      <details class="legacy"{open_attr}>\n'
            f'        <summary data-i18n="legacy_title">{LEGACY_LABEL}</summary>\n'
            '        <div class="legacy-grid">\n' + "\n".join(legacy) + "\n        </div>\n"
            "      </details>"
        )
    return html


def build_product(slug: str, spec: dict) -> None:
    template = (SRC / spec["template"]).read_text()
    out_dir = ROOT / slug
    img_dir = out_dir / "img"

    # Rebuild the image folder so removed assets don't linger.
    if img_dir.exists():
        shutil.rmtree(img_dir, ignore_errors=True)
    img_dir.mkdir(parents=True)

    hosted = offline = template.replace("{{ACCESSORIES}}", accessories_html(slug))
    for key, filename in spec["images"].items():
        src = SRC / filename
        shutil.copy(src, img_dir / filename)
        hosted = hosted.replace("{{%s}}" % key, f"img/{filename}")
        offline = offline.replace("{{%s}}" % key, data_uri(src))

    # The card image (used by the portal index + product switcher) isn't always
    # one of the template's {{KEY}} images — copy it too if it's a local file.
    card_image = spec.get("card_image", "")
    if card_image and not card_image.startswith("http") and card_image not in spec["images"].values():
        shutil.copy(SRC / card_image, img_dir / card_image)

    # Brand mark links to the guides home page (relative, so it survives a domain change).
    # The store is reached through each guide's "Upgrade" section instead.
    hosted  = hosted.replace("{{HOME}}", "../")
    offline = offline.replace("{{HOME}}", "../")
    hosted  = hosted.replace("{{YEAR}}", YEAR)
    offline = offline.replace("{{YEAR}}", YEAR)

    for key, value in spec["text"].items():
        hosted = hosted.replace("{{%s}}" % key, value)
        offline = offline.replace("{{%s}}" % key, value)

    # Inject the product-switcher cards.
    switcher = build_switcher(slug)
    hosted  = hosted.replace("{{PRODUCT_SWITCHER}}", switcher)
    offline = offline.replace("{{PRODUCT_SWITCHER}}", switcher)

    # Inject translations if available.
    translations = load_i18n(slug)
    if translations:
        hosted = inject_i18n(hosted, translations)
        offline = inject_i18n(offline, translations)

    write(out_dir / "index.html", hosted)
    write(out_dir / "offline.html", offline)


def build_index() -> None:
    template = (SRC / "index.template.html").read_text()
    cards_html, legacy_html = [], []
    for slug, spec in PRODUCTS.items():
        href, extattr = _card_href(slug, spec)
        (legacy_html if spec.get("legacy") else cards_html).append(CARD.format(
            slug=slug,
            card_img=_card_img(slug, spec, is_switcher=False),
            category=spec["category"],
            name=spec["name"],
            href=href,
            extattr=extattr,
        ))
    page = (template.replace("{{CARDS}}", "\n".join(cards_html))
                    .replace("{{LEGACY_CARDS}}", "\n".join(legacy_html))
                    .replace("{{LEGACY_LABEL}}", LEGACY_LABEL)
                    .replace("{{YEAR}}", YEAR))
    write(ROOT / "index.html", page)


if __name__ == "__main__":
    print("Building G Pen product guides\n")
    for slug, spec in PRODUCTS.items():
        if spec.get("template"):          # only build products with a local template
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
