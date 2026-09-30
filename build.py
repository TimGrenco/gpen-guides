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
import sys

ROOT = pathlib.Path(__file__).parent
SRC = ROOT / "src"
I18N_DIR = ROOT / "i18n"
CONTENT_DIR = ROOT / "content"
YEAR = str(datetime.date.today().year)

sys.path.insert(0, str(ROOT))
from sections.render import render_product_body, compose_translations, IMG_REF_RE  # noqa: E402
from sections.normalize import load_normalized  # noqa: E402
from sections.schema import validate_content  # noqa: E402

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
            "UPG_MICRO_II": "melt-upgrade-micro-ii.png",
            "UPG_MICRO_PLUS": "melt-upgrade-micro-plus.png",
        },
        "text": {},
        "shop_button": ("Shop all vaporizers", "https://www.gpen.com/collections/vaporizers"),
    },

    "dash-plus": {
        "template": "dash-plus.template.html",
        "name": "G Pen Dash+",
        "category": "Dry Herb Vaporizer",
        "card_image": "dash-plus-card.png",
        "images": {},
        "text": {},
    },
    "grinder": {
        "template": "grinder.template.html",
        "name": "G Pen Grinder",
        "category": "3-Piece Dry Herb Grinder",
        "card_image": "grinder-card.png",
        "images": {},
        "text": {},
        "shop_button": ("Shop dry herb vaporizers", "https://www.gpen.com/collections/dry-herb-vaporizers"),
    },
    "elite-ii": {
        "template": "elite-ii.template.html",
        "legacy": True,
        "hidden": True,     # off the site for now; flip to False to bring it back
        "name": "G Pen Elite II",
        "category": "Dry Herb Vaporizer",
        "card_image": "elite-ii-card.png",
        "images": {},
        "text": {},
    },
    "micro-plus": {
        "template": "micro-plus.template.html",
        "legacy": True,
        "hidden": True,     # off the site for now; flip to False to bring it back
        "name": "G Pen Micro+",
        "category": "Concentrate Vaporizer",
        "card_image": "micro-plus-card.png",
        "images": {},
        "text": {},
    },
    "hyer": {
        "template": "hyer.template.html",
        "legacy": True,
        "hidden": True,     # off the site for now; flip to False to bring it back
        "name": "G Pen Hyer",
        "category": "Concentrate Vaporizer",
        "card_image": "hyer-card.png",
        "images": {},
        "text": {},
    },
    "connect": {
        "template": "connect.template.html",
        "legacy": True,
        "hidden": True,     # off the site for now; flip to False to bring it back
        "name": "G Pen Connect",
        "category": "Concentrate Vaporizer",
        "card_image": "connect-card.png",
        "images": {},
        "text": {},
    },

    # ── Upcoming guide pages — show in switcher, link to gpen.com for now ─────
    # card_image may be a full CDN URL or a local filename in src/.
    "roam": {
        "template": None,
        "legacy": True,
        "hidden": True,     # off the site for now; flip to False to bring it back
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
ARROW_SVG = ('<svg viewBox="0 0 20 20" aria-hidden="true">'
             '<path d="M7 4.5 15.5 10 7 15.5Z" fill="currentColor"/></svg>')


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
                '          <span class="acc-shop" data-i18n="acc_shop">Shop</span>\n'
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


class ContentError(Exception):
    pass


def content_images(content: dict) -> list[str]:
    refs = []
    for s in content.get("steps", []):
        refs += [s["image"]] + ([s["image2"]] if s.get("image2") else [])
    refs += [a["image"] for a in content.get("attachments", [])]
    refs += [v["thumb"] for v in content.get("videos", [])]
    return refs


def load_content(slug: str):
    """Load, normalize and validate content/<slug>.json (steps/attachments/specs/faq/videos).

    Normalizing writes back any freshly minted IDs (e.g. a bullet just added by hand),
    so they stay stable from then on. Bad content fails the build loudly rather than
    publishing a half-broken guide.
    """
    path = CONTENT_DIR / f"{slug}.json"
    if not path.exists():
        return None
    content = load_normalized(path)
    errors = validate_content(slug, content)
    errors += [f"{slug}: image not found: src/{f}" for f in content_images(content) if not (SRC / f).is_file()]
    if errors:
        raise ContentError("\n  ".join([f"content/{slug}.json is invalid:"] + errors))
    return content


def load_i18n(slug: str):
    """Load the translation cache from i18n/<slug>.json if it exists."""
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


def visible_products() -> dict:
    """PRODUCTS minus anything flagged hidden. Hidden products keep their source
    (template, content, translations, images) but aren't built, listed or linked."""
    return {s: spec for s, spec in PRODUCTS.items() if not spec.get("hidden")}


def build_switcher(current_slug: str) -> str:
    """Generate the product-switcher card HTML for a given guide page.

    Current products come first; legacy products sit in a collapsed fold that
    opens by default when the visitor is already on a legacy guide.
    """
    featured, legacy = [], []
    for s, spec in visible_products().items():
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
    content = load_content(slug)  # validate before touching the output folder
    out_dir = ROOT / slug
    img_dir = out_dir / "img"

    # Rebuild the image folder so removed assets don't linger.
    if img_dir.exists():
        shutil.rmtree(img_dir, ignore_errors=True)
    img_dir.mkdir(parents=True)

    register_button = (ROOT / "sections" / "partials" / "register-button.html").read_text().rstrip("\n")
    hosted = offline = (template.replace("{{ACCESSORIES}}", accessories_html(slug))
                                .replace("{{REGISTER_BUTTON}}", register_button))

    # Structured content (steps/attachments/specs/faq/videos) — still contains unresolved
    # {{STEP1}}-style image tokens, resolved by the per-image loop right below.
    if content:
        body = render_product_body(slug, content)
        for key in ("STEPS", "ATTACHMENTS", "SPECS_ROWS", "FAQ_ITEMS", "VIDEOS"):
            hosted = hosted.replace("{{%s}}" % key, body[key])
            offline = offline.replace("{{%s}}" % key, body[key])

    for key, filename in spec["images"].items():
        src = SRC / filename
        shutil.copy(src, img_dir / filename)
        hosted = hosted.replace("{{%s}}" % key, f"img/{filename}")
        offline = offline.replace("{{%s}}" % key, data_uri(src))

    # Images referenced from content/<slug>.json by filename (relative to src/, e.g. a
    # guide image under src/images/) — published flat into <product>/img/.
    for ref in sorted(set(IMG_REF_RE.findall(hosted))):
        src = SRC / ref
        name = pathlib.PurePosixPath(ref).name
        shutil.copy(src, img_dir / name)
        hosted = hosted.replace("{{img:%s}}" % ref, f"img/{name}")
        offline = offline.replace("{{img:%s}}" % ref, data_uri(src))

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
    cache = load_i18n(slug)
    if cache:
        translations = compose_translations(slug, content, cache) if content else cache
        hosted = inject_i18n(hosted, translations)
        offline = inject_i18n(offline, translations)

    write(out_dir / "index.html", hosted)
    write(out_dir / "offline.html", offline)


def build_index() -> None:
    template = (SRC / "index.template.html").read_text()
    cards_html, legacy_html = [], []
    for slug, spec in visible_products().items():
        href, extattr = _card_href(slug, spec)
        (legacy_html if spec.get("legacy") else cards_html).append(CARD.format(
            slug=slug,
            card_img=_card_img(slug, spec, is_switcher=False),
            category=spec["category"],
            name=spec["name"],
            href=href,
            extattr=extattr,
        ))
    legacy_section = ""
    if legacy_html:
        legacy_section = (
            '\n    <details class="legacy">\n'
            f'      <summary>{LEGACY_LABEL}</summary>\n'
            '      <div class="grid">\n' + "\n".join(legacy_html) + "\n      </div>\n"
            "    </details>"
        )
    page = (template.replace("{{CARDS}}", "\n".join(cards_html))
                    .replace("{{LEGACY_SECTION}}", legacy_section)
                    .replace("{{YEAR}}", YEAR))
    write(ROOT / "index.html", page)


if __name__ == "__main__":
    print("Building G Pen product guides\n")
    failed = []
    for slug, spec in visible_products().items():
        if spec.get("template"):          # only build products with a local template
            try:
                build_product(slug, spec)
            except ContentError as e:
                # leave that product's previously built pages untouched; build the rest
                failed.append(slug)
                print(f"\n  ✗ {e}\n")
    build_index()

    for slug, spec in PRODUCTS.items():
        if spec.get("hidden") and spec.get("template") and (ROOT / slug).is_dir():
            # ignore_errors: macOS ._ sidecars on network volumes vanish mid-walk
            shutil.rmtree(ROOT / slug, ignore_errors=True)
            print(f"  removed {slug}/ (hidden — source kept in src/, content/, i18n/)")

    stale = [p for p in ("hydout.html", "hydout-standalone.html") if (ROOT / p).exists()]
    if stale:
        print("\nRemoving files from the old flat layout:")
        for name in stale:
            (ROOT / name).unlink()
            print(f"  {name}")
    if (ROOT / "img").exists():
        shutil.rmtree(ROOT / "img")
        print("  img/")

    if failed:
        print(f"\nFAILED: {', '.join(failed)} — fix the content errors above; their pages were not rebuilt.")
        sys.exit(1)
    print(f"\nDone. Preview with: python3 serve.py")
