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

from __future__ import annotations

import base64
import datetime
import hashlib
import html as htmllib
import json
import mimetypes
import pathlib
import re
import shutil
import sys

from PIL import Image

ROOT = pathlib.Path(__file__).parent
SRC = ROOT / "src"
CORE_SRC = SRC / "core"             # G Pen Core: shared CSS, behavior, fonts, icons
I18N_DIR = ROOT / "i18n"
CONTENT_DIR = ROOT / "content"
CACHE_DIR = ROOT / ".cache"         # resized images, so a rebuild doesn't re-encode them
YEAR = str(datetime.date.today().year)

# The public address of the site. Canonical links, share previews (og:), the sitemap and
# the offline copies' links all hang off this one value. When help.gpen.com goes live:
# set it to "https://help.gpen.com/", add a CNAME file containing help.gpen.com, rebuild.
BASE_URL = "https://help.gpen.com/"

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
        "name": "G Pen 3-Piece Slim Grinder",
        "category": "Dry Herb Grinder",
        "card_image": "grinder-card.png",
        "images": {},
        "text": {},
        "shop_button": ("Shop dry herb vaporizers", "https://www.gpen.com/collections/dry-herb-vaporizers"),
        "register": False,  # no warranty, so nothing to register (Tim, 2026-09-30)
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
        <span class="thumb"><img src="{card_img}"{srcset} alt=""{dims}{loading}></span>
        <div>
          <h2>{name}</h2>
          <span class="eyebrow" data-i18n="cat_{slug}">{category}</span>
        </div>
      </a>"""

# Card shown inside the product-switcher sheet on each guide page. The product name is
# right under the picture, so the picture itself is decorative (alt="").
SWITCHER_CARD = """      <a class="guide-card" href="{href}" {extattr} {current}>
        <div class="gc-img"><img src="{card_img}"{srcset} alt=""{dims} loading="lazy"></div>
        <div class="gc-body">
          <span class="gc-name">{name}</span>
          <span class="gc-cat" data-i18n="cat_{slug}">{category}</span>
        </div>
      </a>"""


def card_srcset(slug: str, spec: dict, root_prefix: str, sizes: str) -> tuple[str, str]:
    """(srcset/sizes attributes, width/height attributes) for a product's card image.
    The WebP renditions are written by build_product() into <slug>/img/; names are
    deterministic, so any page can reference them."""
    ci = spec["card_image"]
    if ci.startswith("http"):
        return "", ""
    with Image.open(SRC / ci) as im:
        W, H = im.size
    stem = pathlib.PurePosixPath(ci).stem
    parts = dict.fromkeys(f"{root_prefix}{slug}/img/{stem}-{w}.webp {min(w, W)}w" for w in WIDTHS_CARD)
    return f' srcset="{", ".join(parts)}" sizes="{sizes}"', f' width="{W}" height="{H}"'


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


# ─────────────────────────────────────────────────────────────────────────────────────
# G Pen Core — shared layer injected into every page (guides, index, 404)
# ─────────────────────────────────────────────────────────────────────────────────────
FONT_IMPORT_RE = re.compile(r"@import url\('https://fonts\.googleapis\.com/[^']*'\);\s*")
TITLE_RE = re.compile(r"<title>(.*?)</title>", re.S)
DESC_RE = re.compile(r'<meta name="description" content="([^"]*)">')


def load_core_translations() -> dict:
    data = json.loads((I18N_DIR / "_core.json").read_text())
    return {k: v for k, v in data.items() if not k.startswith("_")}


def merge_translations(page: dict | None) -> dict:
    """Shared strings under each page's own (the page wins on a key both define)."""
    core = load_core_translations()
    page = page or {}
    return {lang: {**core.get(lang, {}), **page.get(lang, {})} for lang in core}


def core_head(prefix: str, offline: bool, canonical: str, title: str, desc: str,
              image: str | None, noindex: bool = False) -> str:
    """Everything G Pen Core adds to <head>: fonts, the shared stylesheet, icons, share tags.
    prefix: path from the page to the site root ("" for the index, "../" for a guide)."""
    asset = (BASE_URL if offline else prefix) + "core/"
    fonts = (CORE_SRC / "fonts.css").read_text().replace("{{FONT_BASE}}", asset + "fonts/")
    css = (CORE_SRC / "core.css").read_text()
    esc = lambda s: htmllib.escape(s, quote=True)
    out = []
    if not offline:
        for f in ("lato-400-latin", "kanit-800i-latin"):
            out.append(f'<link rel="preload" href="{asset}fonts/{f}.woff2" as="font" type="font/woff2" crossorigin>')
    out += [
        f'<link rel="icon" href="{asset}favicon.svg" type="image/svg+xml">',
        f'<link rel="apple-touch-icon" href="{asset}apple-touch-icon.png">',
        f'<link rel="canonical" href="{canonical}">',
    ]
    if noindex:
        out.append('<meta name="robots" content="noindex">')
    out += [
        '<meta property="og:type" content="website">',
        '<meta property="og:site_name" content="G Pen">',
        f'<meta property="og:title" content="{esc(title)}">',
        f'<meta property="og:description" content="{esc(desc)}">',
        f'<meta property="og:url" content="{canonical}">',
    ]
    if image:
        out.append(f'<meta property="og:image" content="{image}">')
    out.append(f'<meta name="twitter:card" content="{"summary" if image else "summary"}">')
    out.append(f"<style>\n{fonts}\n{css}</style>")
    return "\n".join(out) + "\n"


def inject_core(html: str, head: str) -> str:
    """Swap the render-blocking Google Fonts @import for the self-hosted faces, add the
    core <head> block after the page's own <style> (so core rules win ties), and inline
    the shared behavior script last, after the i18n runtime it talks to."""
    html = FONT_IMPORT_RE.sub("", html)
    html = html.replace("</head>", head + "</head>", 1)
    js = (CORE_SRC / "guide.js").read_text()
    return html.replace("</body>", f"<script>\n{js}</script>\n</body>", 1)


def page_meta(html: str) -> tuple[str, str]:
    t = TITLE_RE.search(html)
    d = DESC_RE.search(html)
    return (htmllib.unescape(t.group(1).strip()) if t else "G Pen",
            htmllib.unescape(d.group(1)) if d else "")


def publish_core() -> None:
    """Copy the shared static assets to /core/ (fonts + icons)."""
    out = ROOT / "core"
    if out.exists():
        shutil.rmtree(out, ignore_errors=True)
    (out / "fonts").mkdir(parents=True)
    for f in sorted((CORE_SRC / "fonts").glob("*.woff2")):
        shutil.copy(f, out / "fonts" / f.name)
    for f in ("favicon.svg", "apple-touch-icon.png"):
        shutil.copy(CORE_SRC / f, out / f)


# ─────────────────────────────────────────────────────────────────────────────────────
# Responsive images: WebP renditions + srcset/sizes, width/height to stop layout shift
# ─────────────────────────────────────────────────────────────────────────────────────
# How wide each kind of image is DRAWN (CSS px). Step/attachment circles are 150px from
# 480px up, 130px below, 100px under 375px; video stills fill a card; card thumbnails
# are ~80px on the index and ~150-190px in the All-guides sheet.
SIZES_CIRCLE = "(min-width:480px) 150px, (min-width:375px) 130px, 100px"
SIZES_VIDEO = "(min-width:680px) 322px, (min-width:560px) 46vw, calc(100vw - 36px)"
SIZES_VIDEO_SINGLE = "(min-width:680px) 644px, calc(100vw - 36px)"   # a lone video spans the column
SIZES_INDEX_CARD = "80px"
SIZES_SWITCHER_CARD = "(min-width:480px) 190px, 44vw"
WIDTHS_CIRCLE = (300, 450)     # 150px x DPR 2 / DPR 3
WIDTHS_VIDEO = (480, 960)
WIDTHS_CARD = (160, 320, 640)


def webp_variant(src: pathlib.Path, width: int, out_dir: pathlib.Path) -> tuple[str, int, int]:
    """Write <stem>-<width>.webp into out_dir (from a content-hash cache) and return
    (filename, width, height). Never upscales: a request wider than the source yields a
    rendition at the source's own width."""
    data = src.read_bytes()
    with Image.open(src) as im:
        W, H = im.size
        w = min(width, W)
        h = round(H * w / W)
        name = f"{src.stem}-{width}.webp"
        key = hashlib.sha1(data + f"|{w}|q80m6".encode()).hexdigest()[:16]
        cached = CACHE_DIR / "img" / f"{key}.webp"
        if not cached.exists():
            cached.parent.mkdir(parents=True, exist_ok=True)
            mode = "RGBA" if im.mode in ("RGBA", "LA", "P") else "RGB"
            im.convert(mode).resize((w, h), Image.LANCZOS).save(cached, "WEBP", quality=80, method=6)
    shutil.copy(cached, out_dir / name)
    return name, w, h


def srcset_for(src: pathlib.Path, widths, out_dir: pathlib.Path, base: str = "img/") -> tuple[str, int, int]:
    """Generate renditions and return (srcset, natural_w, natural_h)."""
    with Image.open(src) as im:
        W, H = im.size
    parts = []
    for width in widths:
        name, w, _ = webp_variant(src, width, out_dir)
        parts.append(f"{base}{name} {w}w")
    return ", ".join(dict.fromkeys(parts)), W, H


IMG_TAG_RE = re.compile(r'<img src="img/([^"]+)"([^>]*)>')


def responsive_images(html: str, plans: dict) -> str:
    """Add srcset/sizes/width/height to every <img src="img/NAME"> that has a plan."""
    def sub(m):
        name, rest = m.group(1), m.group(2)
        plan = plans.get(name)
        if not plan or "srcset=" in rest:
            return m.group(0)
        srcset, sizes, w, h = plan
        return f'<img src="img/{name}" srcset="{srcset}" sizes="{sizes}" width="{w}" height="{h}"{rest}>'
    return IMG_TAG_RE.sub(sub, html)


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


def build_switcher(current_slug: str, offline: bool = False) -> str:
    """Generate the product-switcher card HTML for a given guide page.

    Current products come first; legacy products sit in a collapsed fold that
    opens by default when the visitor is already on a legacy guide. The offline copy
    links (and loads card pictures) from the live site, since its siblings aren't on disk.
    """
    featured, legacy = [], []
    root = BASE_URL if offline else "../"
    for s, spec in visible_products().items():
        current_attr = 'aria-current="true"' if s == current_slug else ""
        href, extattr = _card_href(s, spec)
        # Switcher links are relative to the guide subfolder; adjust local guides.
        if spec.get("template") and s != current_slug:
            href = f"{root}{s}/"
        elif spec.get("template") and s == current_slug:
            href = f"{BASE_URL}{s}/" if offline else "./"
        card_img = _card_img(s, spec, is_switcher=True)
        srcset, dims = ("", "") if offline else card_srcset(s, spec, "../", SIZES_SWITCHER_CARD)
        if offline and not card_img.startswith("http"):
            card_img = BASE_URL + card_img[len("../"):]
        card = SWITCHER_CARD.format(
            slug=s,
            card_img=card_img,
            srcset=srcset,
            dims=dims,
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

    register_button = ("" if spec.get("register") is False else
                       (ROOT / "sections" / "partials" / "register-button.html").read_text().rstrip("\n"))
    hosted = offline = (template.replace("{{ACCESSORIES}}", accessories_html(slug))
                                .replace("{{REGISTER_BUTTON}}", register_button))

    # Structured content (steps/attachments/specs/faq/videos) — still contains unresolved
    # {{STEP1}}-style image tokens, resolved by the per-image loop right below.
    if content:
        body = render_product_body(slug, content)
        for key in ("STEPS", "ATTACHMENTS", "SPECS_ROWS", "FAQ_ITEMS", "VIDEOS"):
            hosted = hosted.replace("{{%s}}" % key, body[key])
            offline = offline.replace("{{%s}}" % key, body[key])

    # Template-level images ({{HERO}} etc.): published only if the template uses them.
    # (Several products list a hero that no page shows — the Dash II one is 3 MB.)
    for key, filename in spec["images"].items():
        if "{{%s}}" % key not in hosted:
            continue
        src = SRC / filename
        shutil.copy(src, img_dir / filename)
        hosted = hosted.replace("{{%s}}" % key, f"img/{filename}")
        offline = offline.replace("{{%s}}" % key, data_uri(src))

    # Images referenced from content/<slug>.json by filename (relative to src/, e.g. a
    # guide image under src/images/) — published flat into <product>/img/, each with WebP
    # renditions sized for how it is drawn. The offline copy inlines one mid-size rendition
    # instead of the 900px original, which roughly halves its size.
    video_refs = {v["thumb"] for v in (content or {}).get("videos", [])}
    plans = {}
    for ref in sorted(set(IMG_REF_RE.findall(hosted))):
        src = SRC / ref
        name = pathlib.PurePosixPath(ref).name
        shutil.copy(src, img_dir / name)
        is_video = ref in video_refs
        video_sizes = SIZES_VIDEO_SINGLE if len(video_refs) == 1 else SIZES_VIDEO
        widths, sizes = (WIDTHS_VIDEO, video_sizes) if is_video else (WIDTHS_CIRCLE, SIZES_CIRCLE)
        srcset, w, h = srcset_for(src, widths, img_dir)
        plans[name] = (srcset, sizes, w, h)
        inline_name, _, _ = webp_variant(src, widths[-1] if is_video else 450, img_dir)
        hosted = hosted.replace("{{img:%s}}" % ref, f"img/{name}")
        offline = offline.replace("{{img:%s}}" % ref, data_uri(img_dir / inline_name))
    hosted = responsive_images(hosted, plans)

    # The card image (used by the portal index + product switcher) isn't always
    # one of the template's {{KEY}} images — copy it too if it's a local file, plus the
    # small WebP renditions the index and switchers actually load.
    card_image = spec.get("card_image", "")
    if card_image and not card_image.startswith("http"):
        if not (img_dir / card_image).exists():
            shutil.copy(SRC / card_image, img_dir / card_image)
        for w in WIDTHS_CARD:
            webp_variant(SRC / card_image, w, img_dir)

    # Brand mark links to the guides home page (relative, so it survives a domain change).
    # The store is reached through each guide's "Upgrade" section instead.
    hosted  = hosted.replace("{{HOME}}", "../")
    offline = offline.replace("{{HOME}}", BASE_URL)
    hosted  = hosted.replace("{{YEAR}}", YEAR)
    offline = offline.replace("{{YEAR}}", YEAR)

    for key, value in spec["text"].items():
        hosted = hosted.replace("{{%s}}" % key, value)
        offline = offline.replace("{{%s}}" % key, value)

    # Inject the product-switcher cards.
    hosted  = hosted.replace("{{PRODUCT_SWITCHER}}", build_switcher(slug))
    offline = offline.replace("{{PRODUCT_SWITCHER}}", build_switcher(slug, offline=True))

    # Inject translations (the page's own, over the shared G Pen Core strings).
    cache = load_i18n(slug)
    page_t = (compose_translations(slug, content, cache) if content else cache) if cache else None
    translations = merge_translations(page_t)
    hosted = inject_i18n(hosted, translations)
    offline = inject_i18n(offline, translations)

    # G Pen Core: fonts, shared CSS + behavior, icons, canonical + share tags.
    title, desc = page_meta(hosted)
    canonical = f"{BASE_URL}{slug}/"
    og_image = f"{BASE_URL}{slug}/img/{card_image}" if card_image and not card_image.startswith("http") else None
    hosted = inject_core(hosted, core_head("../", False, canonical, title, desc, og_image))
    offline = inject_core(offline, core_head("../", True, canonical, title, desc, og_image, noindex=True))

    write(out_dir / "index.html", hosted)
    write(out_dir / "offline.html", offline)


def build_index() -> None:
    template = (SRC / "index.template.html").read_text()
    cards_html, legacy_html = [], []
    for n, (slug, spec) in enumerate(visible_products().items()):
        href, extattr = _card_href(slug, spec)
        srcset, dims = card_srcset(slug, spec, "", SIZES_INDEX_CARD)
        (legacy_html if spec.get("legacy") else cards_html).append(CARD.format(
            slug=slug,
            card_img=_card_img(slug, spec, is_switcher=False),
            srcset=srcset,
            dims=dims,
            # the first cards are on screen at load: let the browser fetch them right away
            loading="" if n < 4 else ' loading="lazy"',
            category=spec["category"],
            name=spec["name"],
            href=href,
            extattr=extattr,
        ))
    legacy_section = ""
    if legacy_html:
        legacy_section = (
            '\n    <details class="legacy">\n'
            f'      <summary data-i18n="legacy_title">{LEGACY_LABEL}</summary>\n'
            '      <div class="grid">\n' + "\n".join(legacy_html) + "\n      </div>\n"
            "    </details>"
        )
    page = (template.replace("{{CARDS}}", "\n".join(cards_html))
                    .replace("{{LEGACY_SECTION}}", legacy_section)
                    .replace("{{YEAR}}", YEAR))
    # The shared strings reach every page, so the index's own tab title rides under its own
    # key and is mapped to doc_title (what the runtime reads) here, for this page only.
    def titled(key):
        t = merge_translations(None)
        return {lang: {**strings, "doc_title": strings.get(key, "")} for lang, strings in t.items()}
    page_plain = page
    page = inject_i18n(page_plain, titled("doc_title_index"))
    title, desc = page_meta(page)
    first = next(iter(visible_products().items()))
    og_image = f"{BASE_URL}{first[0]}/img/{first[1]['card_image']}"
    index = inject_core(page, core_head("", False, BASE_URL, title, desc, og_image))
    write(ROOT / "index.html", index)

    # 404: GitHub Pages serves /404.html for any missing path, at any depth, so every
    # relative link on it is resolved against the site root with <base>.
    notice = ('<p class="notfound" data-i18n="nf_text">We couldn\'t find that page. '
              'Pick your device below to get to its guide.</p>\n')
    nf = inject_i18n(page_plain, titled("doc_title_404"))
    nf = nf.replace("<head>", f'<head>\n<base href="{BASE_URL}">', 1)
    nf = nf.replace("<title>", "<title>Page not found — ", 1)
    nf = nf.replace('  <div class="wrap list">', f'  <div class="wrap">{notice}  </div>\n  <div class="wrap list">', 1)
    nf = inject_core(nf, core_head("", False, BASE_URL, "Page not found — G Pen Product Guides", desc, None, noindex=True))
    write(ROOT / "404.html", nf)


def build_seo_files() -> None:
    urls = [BASE_URL] + [f"{BASE_URL}{s}/" for s, spec in visible_products().items() if spec.get("template")]
    sitemap = ['<?xml version="1.0" encoding="UTF-8"?>',
               '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    # no <lastmod>: a date that moves on every rebuild would claim every page changed daily
    sitemap += [f"  <url><loc>{u}</loc></url>" for u in urls]
    sitemap.append("</urlset>")
    (ROOT / "sitemap.xml").write_text("\n".join(sitemap) + "\n")
    # Only honored at a domain's root (i.e. once this is help.gpen.com). Keeps the build
    # inputs, which GitHub Pages also serves, out of search results.
    (ROOT / "robots.txt").write_text(
        "User-agent: *\n"
        "Disallow: /src/\nDisallow: /content/\nDisallow: /i18n/\nDisallow: /sections/\nDisallow: /scripts/\n"
        "Disallow: /*/offline.html\n\n"
        f"Sitemap: {BASE_URL}sitemap.xml\n")


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
    publish_core()
    build_seo_files()

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
