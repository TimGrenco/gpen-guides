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
import posixpath
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

# The public address of the site (live since 2026-09-30, see the CNAME file). Canonical
# links, share previews (og:), the sitemap, robots.txt and the offline copies' links all
# hang off this one value.
BASE_URL = "https://help.gpen.com/"

# IndexNow (Bing, Yandex, Seznam, Naver; Bing also feeds ChatGPT search and Copilot): the
# site proves it owns this key by serving /<key>.txt. Ping after a deploy with
# scripts/indexnow.py to have changed pages re-crawled within minutes.
INDEXNOW_KEY = "c2e3ce9201b3ccdca3b873e6e1bcbdd2"

sys.path.insert(0, str(ROOT))
from sections.render import render_product_body, compose_translations, IMG_REF_RE, keep_together, no_widow  # noqa: E402
from sections.normalize import load_normalized  # noqa: E402
from sections.schema import validate_content  # noqa: E402

# Shopify CDN images for products that don't have local guide pages yet.
# Pulled live from gpen.com/products.json (September 2026).
_CDN = "https://cdn.shopify.com/s/files/1/0185/1576/files/"

PRODUCTS = {
    # ── Products with completed local guide pages ─────────────────────────────
    "hydout": {
        "template": "hydout.template.html",
        "name": "G Pen Hydout",
        "category": "510 Cartridge Battery",
        "group": "510",
        "card_image": "hero.png",           # local file in src/
        "images": {},
        "text": {},
        "shop_button": ("Shop the Hydout collection", "https://www.gpen.com/collections/g-pen-hydout-collection"),
    },
    "dash-ii": {
        "template": "dash-ii.template.html",
        "name": "G Pen Dash II",
        "category": "Dry Herb Vaporizer",
        "group": "dryherb",
        "card_image": "dash-ii-card.png",   # local file in src/
        "images": {},
        "text": {},
    },
    "510-original": {
        "template": "510-original.template.html",
        "name": "G Pen 510 Original",
        "category": "510 Cartridge Battery",
        "group": "510",
        "card_image": "510-original-card.png",
        "images": {},
        "text": {},
        "shop_button": ("Shop the Retro collection", "https://www.gpen.com/collections/g-pen-510-original-retro-collection"),
    },
    "micro-ii": {
        "template": "micro-ii.template.html",
        "name": "G Pen Micro II",
        "category": "Concentrate Vaporizer",
        "group": "concentrate",
        "card_image": "micro-ii-card.png",
        "images": {},
        "text": {},
    },
    "melt": {
        "template": "melt.template.html",
        "name": "G Pen Melt",
        "category": "Hot Knife / Dab Tool",
        "group": "concentrate",
        "card_image": "melt-card.png",
        "images": {
            # used by the Upgrades cards in src/accessories.json ("image": "{{UPG_...}}")
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
        "group": "dryherb",
        "card_image": "dash-plus-card.png",
        "images": {},
        "text": {},
    },
    "grinder": {
        "template": "grinder.template.html",
        "name": "G Pen 3-Piece Slim Grinder",
        "category": "Dry Herb Grinder",
        "group": "dryherb",
        "card_image": "grinder-card.png",
        "images": {},
        "text": {},
        "shop_button": ("Shop dry herb vaporizers", "https://www.gpen.com/collections/dry-herb-vaporizers"),
        "register": False,  # no warranty, so nothing to register (Tim, 2026-09-30)
    },
    "elite-ii": {
        "template": "elite-ii.template.html",
        "legacy": True,
        "group": "dryherb",
        "hidden": False,
        "name": "G Pen Elite II",
        "category": "Dry Herb Vaporizer",
        "card_image": "elite-ii-card.png",
        "images": {},
        "text": {},
    },
    "micro-plus": {
        "template": "micro-plus.template.html",
        "legacy": True,
        "group": "concentrate",
        "hidden": False,
        "name": "G Pen Micro+",
        "category": "Concentrate Vaporizer",
        "card_image": "micro-plus-card.png",
        "images": {},
        "text": {},
    },
    "hyer": {
        "template": "hyer.template.html",
        "legacy": True,
        "group": "concentrate",
        "hidden": False,
        "name": "G Pen Hyer",
        "category": "Concentrate Vaporizer",
        "card_image": "hyer-card.png",
        "images": {},
        "text": {},
    },
    "connect": {
        "template": "connect.template.html",
        "legacy": True,
        "group": "concentrate",
        "hidden": False,
        "name": "G Pen Connect",
        "category": "Concentrate Vaporizer",
        "card_image": "connect-card.png",
        "images": {},
        "text": {},
    },

    # ── Guides not built yet: hidden; set hidden False to list them, linking to gpen.com
    # card_image may be a full CDN URL or a local filename in src/.
    "roam": {
        "template": "roam.template.html",
        "legacy": True,
        "group": "concentrate",
        "hidden": False,
        "name": "G Pen Roam",
        "category": "Portable E-Rig",
        "card_image": "roam-card.png",
        "images": {},
        "text": {},
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


# Home page sections, in order: (group key, i18n key, English heading).
INDEX_GROUPS = [
    ("dryherb", "grp_dryherb", "Dry Herb Devices"),
    ("concentrate", "grp_concentrate", "Concentrate Devices"),
    ("510", "grp_510", "510 Batteries"),
]

CARD = """      <a class="card" href="{href}" {extattr}>
        <span class="thumb"><img src="{card_img}"{srcset} alt=""{dims}{loading}></span>
        <div>
          <h3>{name}</h3>
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
        W, H = framed(im).size
    stem = pathlib.PurePosixPath(ci).stem
    parts = dict.fromkeys(f"{root_prefix}{slug}/img/{stem}-{w}.webp {min(w, W)}w" for w in WIDTHS_CARD)
    return f' srcset="{", ".join(parts)}" sizes="{sizes}"', f' width="{W}" height="{H}"'


ACCESSORIES_URL = "https://www.gpen.com/collections/accessories"
ARROW_SVG = ('<svg viewBox="0 0 20 20" aria-hidden="true">'
             '<path d="M7 4.5 15.5 10 7 15.5Z" fill="currentColor"/></svg>')


def share_image(name: str) -> str | None:
    """Absolute URL of a page's link-preview card (src/share/<name>.jpg, published to
    /core/share/); None if that card hasn't been rendered yet."""
    return f"{BASE_URL}core/share/{name}.jpg" if (SRC / "share" / f"{name}.jpg").exists() else None


def support_footer() -> str:
    """The "Talk to our team" band at the foot of every page (same voice as assets.gpen.com)."""
    return (ROOT / "sections" / "partials" / "support-footer.html").read_text().rstrip("\n")


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
                img += ("&" if "?" in img else "?") + "width=320"   # drawn ~104px wide, x3 screens
            href = c.get("url") or f"https://www.gpen.com/products/{c['handle']}"
            # alt attribute needs full escaping; the visible text is set via data-i18n's
            # textContent (not innerHTML), so it must stay UNescaped or entities like
            # &amp;/&#x27; would show up literally once a translation is applied.
            name, note, price = c["name"], c["note"], c["price"]
            out.append(
                f'      <a class="acc-card" href="{href}" target="_blank" rel="noopener noreferrer">\n'
                f'        <span class="acc-img"><img src="{img}" alt="" loading="lazy"></span>\n'
                '        <div class="acc-card-body">\n'
                f'          <span class="acc-card-name" data-i18n="acc{i}_name">{keep_together(name)}</span>\n'
                f'          <span class="acc-card-price">{price}</span>\n'
                f'          <span class="acc-card-note" data-i18n="acc{i}_note">{keep_together(note)}</span>\n'
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
        try:
            return json.loads(path.read_text())
        except json.JSONDecodeError as e:
            raise ContentError(f"i18n/{slug}.json is not valid JSON: {e}")
    return None


def inject_i18n(html: str, translations: dict) -> str:
    """Inject window._T data block + i18n runtime JS before </body>."""
    runtime = (SRC / "i18n-runtime.js").read_text()
    # plain strings (not zone HTML, already processed by render_inline) get the same
    # non-breaking spaces as rendered copy, so a language switch keeps units together
    translations = {lang: {k: (keep_together(v) if isinstance(v, str) and "<" not in v else v)
                           for k, v in strings.items()} for lang, strings in translations.items()}
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
              image: str | None, noindex: bool = False, jsonld: dict | None = None,
              alts: list | None = None, translated: bool = False, lang_path: str | None = None) -> str:
    """Everything G Pen Core adds to <head>: fonts, the shared stylesheet, icons, share tags.
    prefix: path from the page to the site root ("" for the index, "../" for a guide)."""
    asset = (BASE_URL if offline else prefix) + "core/"
    fonts = (CORE_SRC / "fonts.css").read_text().replace("{{FONT_BASE}}", asset + "fonts/")
    css = (CORE_SRC / "core.css").read_text()
    esc = lambda s: htmllib.escape(s, quote=True)
    out = [
        '<meta name="color-scheme" content="light dark">',
        '<meta name="format-detection" content="telephone=no">',   # UPC digits aren't phone numbers
    ]
    if lang_path is not None:
        # An English page (the address on the box): a visitor whose language is another
        # goes to that language's page before anything paints. Same rule as before:
        # ?lang= > saved choice > browser language. The English page itself carries no
        # translations, so it stays small for the visitors who read it.
        folders = json.dumps({k: f for k, f, _ in LANG_PAGES}, separators=(",", ":"))
        out.append(
            "<script>(function(){try{var F=%s,s=null,m=location.search.match(/[?&]lang=([a-z]{2})\\b/i);"
            "if(m){s=m[1].toUpperCase();if(s==='EN'||F[s]){try{localStorage.setItem('gpen-lang',s)}catch(e){}}else s=null}"
            "else{try{s=localStorage.getItem('gpen-lang')}catch(e){}}"
            "var n=(navigator.language||'').slice(0,2).toUpperCase(),L=(s==='EN'||F[s])?s:(F[n]?n:'EN');"
            "if(L!=='EN'){var q=location.search.replace(/([?&])lang=[a-z]{2}\\b&?/i,'$1').replace(/[?&]$/,'');"
            "location.replace('/'+F[L]+'/%s'+q+location.hash)}}catch(e){}})();</script>" % (folders, lang_path))
    elif not translated:   # the 404 page and the offline copies still translate in place
        out += [
        # Pick the visitor's language before first paint (same rule as i18n-runtime.js:
        # ?lang= > saved choice > browser language). A non-English visitor gets the page
        # hidden until the runtime has swapped the text, so English never flashes first.
        "<script>(function(){try{var S=['EN','ES','DE','IT','FR','PT','SV','PL','DA'],q=(location.search.match(/[?&]lang=([a-z]{2})\\b/i)||location.pathname.match(/^\\/(es|de|it|fr|pt|sv|pl|da)\\//)||[])[1],s=null;"
        "if(q&&S.indexOf(q.toUpperCase())>=0)s=q.toUpperCase();else{try{s=localStorage.getItem('gpen-lang')}catch(e){}}"
        "var n=(navigator.language||'').slice(0,2).toUpperCase(),L=(s&&S.indexOf(s)>=0)?s:(S.indexOf(n)>=0?n:'EN');"
        "if(L!=='EN')document.documentElement.classList.add('i18n-wait')}catch(e){}})();</script>",
        ]
    if not offline:
        for f in ("lato-400-latin", "lato-700-latin", "kanit-800i-latin"):
            out.append(f'<link rel="preload" href="{asset}fonts/{f}.woff2" as="font" type="font/woff2" crossorigin>')
    out += [
        f'<link rel="icon" href="{asset}favicon.svg" type="image/svg+xml">',
        f'<link rel="icon" href="{asset}apple-touch-icon.png" type="image/png" sizes="180x180">',
        f'<link rel="apple-touch-icon" href="{asset}apple-touch-icon.png">',
        f'<link rel="canonical" href="{canonical}">',
    ]
    out += [f'<link rel="alternate" hreflang="{h}" href="{u}">' for h, u in (alts or [])]
    if noindex:
        out.append('<meta name="robots" content="noindex">')
    else:
        out.append('<meta name="robots" content="index, follow, max-image-preview:large">')
    if jsonld:
        # "</" can't appear inside a <script>; JSON allows it escaped
        out.append('<script type="application/ld+json">'
                   + json.dumps(jsonld, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
                   + "</script>")
    out += [
        '<meta property="og:type" content="website">',
        '<meta property="og:site_name" content="G Pen">',
        f'<meta property="og:title" content="{esc(title)}">',
        f'<meta property="og:description" content="{esc(desc)}">',
        f'<meta property="og:url" content="{canonical}">',
    ]
    if image:
        # the share cards (scripts/make_share_cards.py) are 1200x630 JPEGs
        out += [f'<meta property="og:image" content="{image}">',
                '<meta property="og:image:type" content="image/jpeg">',
                '<meta property="og:image:width" content="1200">',
                '<meta property="og:image:height" content="630">',
                f'<meta property="og:image:alt" content="{esc(title)}">',
                f'<meta name="twitter:image" content="{image}">']
    out.append('<meta name="twitter:card" content="%s">' % ("summary_large_image" if image else "summary"))
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


# ─────────────────────────────────────────────────────────────────────────────────────
# Per-language pages: /es/hydout/, /de/hydout/ ... pre-translated at build time, so
# search engines index each language at its own address. The English pages (the ones
# the QR codes point at) keep translating themselves in place; these are additional.
# ─────────────────────────────────────────────────────────────────────────────────────
LANG_PAGES = [("ES", "es", "es"), ("DE", "de", "de"), ("IT", "it", "it"),
              ("FR", "fr", "fr"), ("PT", "pt", "pt-BR"),
              ("SV", "sv", "sv"), ("PL", "pl", "pl"), ("DA", "da", "da")]    # (key, folder, hreflang)
LANG_NAMES = {"EN": "en", **{k: h for k, _, h in LANG_PAGES}}


def load_meta_desc() -> dict:
    data = json.loads((I18N_DIR / "_meta.json").read_text())
    return {k: v for k, v in data.items() if not k.startswith("_")}


def alternates(path: str) -> list[tuple[str, str]]:
    """hreflang links for one page; path is "" for the home page or "<slug>/"."""
    out = [("en", BASE_URL + path)]
    out += [(h, f"{BASE_URL}{folder}/{path}") for _, folder, h in LANG_PAGES]
    return out + [("x-default", BASE_URL + path)]


def _element_spans(html: str, attr: str):
    """(start of inner HTML, end of inner HTML, key) for every element carrying attr="key",
    last first, so replacing one doesn't move the ones still to come."""
    found = []
    for m in re.finditer(r'<([a-zA-Z][\w-]*)\b[^>]*?\s%s="([^"]+)"[^>]*>' % attr, html):
        tag, key, depth, pos = m.group(1), m.group(2), 1, m.end()
        tok = re.compile(r"<(/?)%s\b[^>]*>" % tag)
        while depth:
            t = tok.search(html, pos)
            if not t:
                raise ContentError(f"unclosed <{tag} {attr}={key!r}>")
            depth += -1 if t.group(1) else (0 if t.group(0).endswith("/>") else 1)
            pos = t.end()
        found.append((m.end(), t.start(), key))
    return sorted(found, reverse=True)


_ATTR_RE = re.compile(r'(<[^>]*?\sdata-i18n-attr="([^"]+)"[^>]*>)')


def translate_attrs(html: str, strings: dict) -> str:
    """data-i18n-attr="aria-label:key;alt:key2" sets those attributes from the strings."""
    def tag(m):
        t = m.group(1)
        for pair in m.group(2).split(";"):
            attr, _, key = pair.partition(":")
            val = strings.get(key)
            if val:
                t = re.sub(r'(\s%s=")[^"]*(")' % re.escape(attr),
                           lambda a: a.group(1) + htmllib.escape(keep_together(val), quote=True) + a.group(2), t, count=1)
        return t
    return _ATTR_RE.sub(tag, html)


def translate_static(html: str, strings: dict) -> str:
    """What i18n-runtime.js does in the browser, done once at build time."""
    html = translate_attrs(html, strings)
    for start, end, key in _element_spans(html, "data-i18n-zone"):
        if key != "vids_block" and strings.get(key):     # the runtime leaves vids_block alone too
            html = html[:start] + strings[key] + html[end:]
    for start, end, key in _element_spans(html, "data-i18n"):
        val = strings.get(key)
        if not val:
            continue
        text = htmllib.escape(keep_together(val) if "<" not in val else val, quote=False)
        inner = html[start:end]
        if re.search(r"<(svg|button)\b", inner):
            # an icon (or button) inside: swap only the last run of text, as the runtime does
            parts = re.split(r"(<[^>]+>)", inner)
            for i in range(len(parts) - 1, -1, -1):
                if not parts[i].startswith("<") and parts[i].strip():
                    parts[i] = text
                    break
            inner = "".join(parts)
        else:
            inner = text
        html = html[:start] + inner + html[end:]
    return html


def set_lang_ui(html: str, lang: str) -> str:
    """Language pill + menu showing `lang` as the current choice."""
    html = re.sub(r'(<span class="lang-code" id="lang-code">)EN(</span>)', r"\g<1>%s\2" % lang, html)
    check = re.search(r'<svg class="lcheck".*?</svg>', html).group(0)
    def opt(m):
        li = m.group(0).replace(check, "")
        li = li.replace('aria-selected="true"', 'aria-selected="false"').replace(' class="lang-opt active"', ' class="lang-opt"')
        if f'data-lang="{lang}"' in li:
            li = (li.replace('aria-selected="false"', 'aria-selected="true"')
                    .replace(' class="lang-opt"', ' class="lang-opt active"')
                    .replace("</li>", check + "</li>"))
        return li
    return re.sub(r'<li role="option" data-lang="[A-Z]{2}".*?</li>', opt, html)


_SKIP_URL = re.compile(r"^(?:[a-z][a-z0-9+.-]*:|//|#|$)", re.I)


def relocate(html: str, from_dir: str, to_dir: str, page_paths: set, folder: str) -> str:
    """Rewrite every relative URL in a page written for from_dir ("/" or "/hydout/") so it
    works from to_dir ("/es/" or "/es/hydout/"). A link to another page goes to that page's
    version in the same language; anything else (images, fonts, the offline copy) still
    points at the one shared file."""
    def move(url: str) -> str:
        if _SKIP_URL.match(url):
            return url
        path, tail = re.match(r"([^?#]*)(.*)", url, re.S).groups()
        target = posixpath.normpath(posixpath.join(from_dir, path or "."))
        target += "/" if (path.endswith("/") or path in ("", ".")) and target != "/" else ""
        if target in page_paths:
            target = f"/{folder}{target}"
        rel = posixpath.relpath(target, to_dir)
        if target.endswith("/"):
            rel = "./" if rel == "." else rel + "/"
        return rel + tail

    def attr(m):
        name, val = m.group(1), m.group(2)
        if name == "srcset":
            val = ", ".join(" ".join([move(p.split(" ")[0])] + p.split(" ")[1:]) for p in val.split(", "))
        else:
            val = move(val)
        return f'{name}="{val}"'
    def fix(part):
        part = re.sub(r'\b(src|href|srcset|poster)="([^"]*)"', attr, part)
        return re.sub(r"url\((['\"]?)([^'\")]+)\1\)", lambda m: f"url({m.group(1)}{move(m.group(2))}{m.group(1)})", part)
    # scripts are left alone: guide.js builds selectors like a[href="' + h + '"] in strings
    parts = re.split(r"(<script\b[^>]*>.*?</script>)", html, flags=re.S)
    return "".join(x if x.startswith("<script") else fix(x) for x in parts)


def lang_switch_script(lang: str, path: str, here: str, save: bool = True) -> str:
    """On a language page the menu goes to the other language's page instead of translating
    in place, so the address always matches what's on screen. The visit also counts as a
    choice: the English pages open in this language from now on (same rule as ?lang=)."""
    urls = {"EN": posixpath.relpath("/" + path, here)}
    urls.update({k: posixpath.relpath(f"/{f}/{path}", here) for k, f, _ in LANG_PAGES})
    urls = {k: ("./" if v == "." else v + "/") for k, v in urls.items()}
    # ?lang=en on the way to English, so the choice holds even where storage is blocked
    # (the English page would otherwise send the visitor back by their browser language)
    return ("<script>(function(){var P='%s',U=%s;%s"
            "window._i18n=function(l){if(l===P||!U[l])return;try{localStorage.setItem('gpen-lang',l)}catch(e){}"
            "location.href=U[l]+(l==='EN'?'?lang=en':'')+location.hash}})();</script>\n"
            % (lang, json.dumps(urls, separators=(",", ":")),
               "try{localStorage.setItem('gpen-lang',P)}catch(e){}" if save else ""))


def localize_content(content: dict, leaf: dict) -> dict:
    """content/<slug>.json with one language's translations swapped in (for its JSON-LD)."""
    c = json.loads(json.dumps(content))
    tr = lambda key, cur: leaf.get(key, cur)
    for s in c.get("steps", []):
        p = f"step.{s['id']}"
        s["title"] = tr(f"{p}.title", s["title"])
        for b in s.get("bullets", []):
            b["text"] = tr(f"{p}.bullet.{b['id']}", b["text"])
        for x in s.get("press", []):
            x["action"] = tr(f"{p}.press.{x['id']}.action", x["action"])
            if x.get("sub"):
                x["sub"] = tr(f"{p}.press.{x['id']}.sub", x["sub"])
        if s.get("note"):
            s["note"]["text"] = tr(f"{p}.note", s["note"]["text"])
    for x in c.get("specs", []):
        x["label"], x["value"] = tr(f"specs.{x['id']}.label", x["label"]), tr(f"specs.{x['id']}.value", x["value"])
    for f in c.get("faq", []):
        f["question"], f["answer"] = tr(f"faq.{f['id']}.question", f["question"]), tr(f"faq.{f['id']}.answer", f["answer"])
    return c


EXTRA_PAGES = ["identify/"]   # site pages that aren't guides; each has /<lang>/ versions too


def missing_strings(pre: str, translations: dict) -> list[str]:
    """Every data-i18n / data-i18n-zone key on the page, per language, that has no string.
    A missing one would leave that bit of the page in English (silently, on every visit)."""
    keys = set(re.findall(r'\sdata-i18n(?:-zone)?="([^"]+)"', pre)) - {"vids_block"}
    keys |= {pair.partition(":")[2] for attrs in re.findall(r'\sdata-i18n-attr="([^"]+)"', pre)
             for pair in attrs.split(";")}
    out = []
    for key, _, _ in LANG_PAGES:
        gone = sorted(k for k in keys if not translations.get(key, {}).get(k))
        if gone:
            out.append(f"{key}: {', '.join(gone)}")
    return out


def write_lang_pages(pre: str, path: str, translations: dict, meta_key: str, title_for, head_for,
                     dry: bool = False) -> list:
    """Render /<folder>/<path>index.html for every language and return [(file, html)]; written
    unless dry (a guide writes its pages only once every one of them rendered). pre is the
    finished English page body before the i18n runtime and core head go in;
    title_for(key, strings) gives the tab title, head_for(key, folder, title, desc) the core
    <head> block."""
    gaps = missing_strings(pre, translations)
    if gaps:
        raise ContentError(f"{path or 'home page'} has untranslated strings:\n    " + "\n    ".join(gaps))
    meta = load_meta_desc()
    pages = []
    page_paths = ({"/"} | {f"/{s}/" for s, sp in visible_products().items() if sp.get("template")}
                  | {f"/{p}" for p in EXTRA_PAGES})
    for key, folder, hreflang in LANG_PAGES:
        strings = translations.get(key, {})
        desc = meta.get(key, {}).get(meta_key)
        if not desc:
            raise ContentError(f"i18n/_meta.json has no {key} description for {meta_key!r}")
        title = title_for(key, strings)
        page = translate_static(pre, strings)
        page = set_lang_ui(page, key)
        page = page.replace('<html lang="en"', f'<html lang="{hreflang}"', 1)
        page = re.sub(r"<title>.*?</title>", f"<title>{htmllib.escape(title, quote=False)}</title>", page, count=1, flags=re.S)
        page = DESC_RE.sub(lambda m: m.group(0).replace(m.group(1), htmllib.escape(desc, quote=True)), page, count=1)
        here = f"/{folder}/{path}"
        page = page.replace("</body>", lang_switch_script(key, path, here) + "</body>", 1)
        page = inject_core(page, head_for(key, folder, title, desc))
        page = relocate(page, "/" + path, here, page_paths, folder)
        left = sorted(set(re.findall(r"\{\{[^{}]{1,60}\}\}", page)))
        if left:
            raise ContentError(f"{folder}/{path}index.html still contains {', '.join(left)}")
        pages.append((ROOT / folder / path / "index.html", page))
    if not dry:
        for f, page in pages:
            write(f, page)
    return pages


def page_meta(html: str) -> tuple[str, str]:
    t = TITLE_RE.search(html)
    d = DESC_RE.search(html)
    return (htmllib.unescape(t.group(1).strip()) if t else "G Pen",
            htmllib.unescape(d.group(1)) if d else "")


# ─────────────────────────────────────────────────────────────────────────────────────
# Search + AI discoverability: schema.org JSON-LD, llms.txt
# ─────────────────────────────────────────────────────────────────────────────────────
ORG = {
    "@type": "Organization", "@id": "https://www.gpen.com/#org", "name": "G Pen",
    "url": "https://www.gpen.com/",
    "logo": f"{BASE_URL}core/apple-touch-icon.png",
    "contactPoint": {"@type": "ContactPoint", "contactType": "customer support",
                     "telephone": "+1-833-691-3224", "email": "help@gpen.com"},
}
WEBSITE = {"@type": "WebSite", "@id": f"{BASE_URL}#site", "url": BASE_URL,
           "name": "G Pen Product Guides", "publisher": {"@id": "https://www.gpen.com/#org"},
           "inLanguage": ["en", "es", "de", "it", "fr", "pt-BR", "sv", "pl", "da"]}


def plain(s: str) -> str:
    """Content text without the **bold** markers."""
    return " ".join(s.replace("**", "").split())


def step_text(step: dict) -> str:
    parts = [plain(b["text"]) for b in step.get("bullets", [])]
    for p in step.get("press", []):
        parts.append(plain(p["action"]) + (f": {plain(p['sub'])}" if p.get("sub") else ""))
    if step.get("note"):
        parts.append(plain(step["note"]["text"]))
    return " ".join(x if x.endswith((".", "!", "?")) else x + "." for x in parts)


def guide_jsonld(slug: str, spec: dict, content: dict, title: str, desc: str,
                 lang: str = "en", folder: str = "", home_name: str = "G Pen Product Guides") -> dict:
    """lang/folder/home_name: a translated page's language, its /<folder>/ and the home page's
    name in that language (its content arrives already translated, see localize_content)."""
    home = f"{BASE_URL}{folder + '/' if folder else ''}"
    url = f"{home}{slug}/"
    img = lambda ref: f"{BASE_URL}{slug}/img/{pathlib.PurePosixPath(ref).name}"
    card = spec.get("card_image", "")
    howto = {
        "@type": "HowTo", "@id": f"{url}#howto",
        "name": f"How to use the {spec['name']}" if lang == "en" else title,
        "description": desc, "inLanguage": lang,
        "step": [{"@type": "HowToStep", "position": i, "name": plain(s["title"]),
                  "text": step_text(s), "image": img(s["image"]), "url": f"{url}#use"}
                 for i, s in enumerate(content.get("steps", []), start=1)],
    }
    if card and not card.startswith("http"):
        howto["image"] = f"{BASE_URL}{slug}/img/{card}"
    graph = [
        {"@type": "WebPage", "@id": url, "url": url, "name": title, "description": desc,
         "inLanguage": lang, "isPartOf": {"@id": f"{BASE_URL}#site"},
         "breadcrumb": {"@id": f"{url}#breadcrumb"}, "mainEntity": {"@id": f"{url}#howto"},
         "publisher": {"@id": "https://www.gpen.com/#org"}},
        howto,
        {"@type": "BreadcrumbList", "@id": f"{url}#breadcrumb", "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": home_name, "item": home},
            {"@type": "ListItem", "position": 2, "name": spec["name"], "item": url}]},
        WEBSITE, ORG,
    ]
    if content.get("faq"):
        graph.append({"@type": "FAQPage", "@id": f"{url}#faq", "url": f"{url}#help", "inLanguage": lang,
                      "mainEntity": [{"@type": "Question", "name": plain(f["question"]),
                                      "acceptedAnswer": {"@type": "Answer", "text": plain(f["answer"])}}
                                     for f in content["faq"]]})
    return {"@context": "https://schema.org", "@graph": graph}


def index_jsonld(title: str, desc: str, lang: str = "en", folder: str = "", howto: str = "How to use the {}") -> dict:
    guides = [(s, p) for s, p in visible_products().items() if p.get("template")]
    home = f"{BASE_URL}{folder + '/' if folder else ''}"
    return {"@context": "https://schema.org", "@graph": [
        {"@type": "CollectionPage", "@id": home, "url": home, "name": title,
         "description": desc, "inLanguage": lang, "isPartOf": {"@id": f"{BASE_URL}#site"},
         "mainEntity": {"@type": "ItemList", "itemListElement": [
             {"@type": "ListItem", "position": i, "name": howto.format(p["name"]),
              "url": f"{home}{s}/"} for i, (s, p) in enumerate(guides, start=1)]}},
        WEBSITE, ORG]}


def build_llms_files() -> None:
    """/llms.txt (the llmstxt.org convention: a short map of the site for AI assistants) and
    /llms-full.txt (every guide's instructions, specs and FAQ as plain Markdown)."""
    guides = [(s, p) for s, p in visible_products().items() if p.get("template")]
    lines = ["# G Pen Product Guides", "",
             "> Official how-to guides for G Pen devices, published by G Pen: how to charge, "
             "load, use and clean each device, its specs, and answers to common questions. "
             "Customers reach each guide by scanning the QR code on the device's packaging.", "",
             "Each guide is also published in Spanish, German, Italian, French, Brazilian "
             "Portuguese, Swedish, Polish and Danish, at the same path under " +
             ", ".join(f"/{f}/" for _, f, _ in LANG_PAGES) + f" (for example {BASE_URL}es/hydout/).", "",
             "## Guides", ""]
    full = ["# G Pen Product Guides: full text", "",
            f"Source: {BASE_URL} (official G Pen help site). Support: +1 833-691-3224, help@gpen.com.", ""]
    for slug, spec in guides:
        content = load_content(slug) or {}
        url = f"{BASE_URL}{slug}/"
        tpl = (SRC / spec["template"]).read_text()
        d = DESC_RE.search(tpl)
        lines.append(f"- [{spec['name']}]({url}): {spec['category']}. "
                     + (htmllib.unescape(d.group(1)) if d else ""))
        full += [f"## {spec['name']} ({spec['category']})", "", f"Guide: {url}", "", "### How to use", ""]
        for i, s in enumerate(content.get("steps", []), start=1):
            full.append(f"{i}. **{plain(s['title'])}**")
            for bl in s.get("bullets", []):
                full.append(f"    - {plain(bl['text'])}")
            for p in s.get("press", []):
                badge = p["badge"]
                how = {"count": lambda b: f"{b['n']}x", "pill": lambda b: b["label"],
                       "text": lambda b: b["value"], "arrows": lambda b: "left/right"}.get(
                           badge["kind"], lambda b: "")(badge)
                full.append(f"    - {plain(p['action'])} ({how})" + (f": {plain(p['sub'])}" if p.get("sub") else ""))
            if s.get("note"):
                full.append(f"    - Note: {plain(s['note']['text'])}")
        for a in content.get("attachments", []):
            full.append(f"- Attachment, **{plain(a['title'])}**: " + " ".join(plain(b["text"]) for b in a.get("bullets", [])))
        if content.get("specs"):
            full += ["", "### Specs", ""] + [f"- {plain(x['label'])}: {plain(x['value'])}" for x in content["specs"]]
        if content.get("faq"):
            full += ["", "### Common questions", ""]
            for f in content["faq"]:
                full += [f"**{plain(f['question'])}**", "", plain(f["answer"]), ""]
        full.append("")
    lines += ["", f"- [Which G Pen do I have?]({BASE_URL}identify/): photos and look-for cues to identify a G Pen device",
              "", "## Optional", "",
              f"- [All guides as plain text]({BASE_URL}llms-full.txt): every guide's steps, specs and FAQ",
              "- [G Pen store](https://www.gpen.com/): products, warranty and registration",
              "", "Support: +1 833-691-3224, help@gpen.com", ""]
    (ROOT / "llms.txt").write_text("\n".join(lines))
    (ROOT / "llms-full.txt").write_text("\n".join(full))


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
    (out / "share").mkdir()
    for f in sorted((SRC / "share").glob("*.jpg")):
        shutil.copy(f, out / "share" / f.name)
    shutil.copy(CORE_SRC / "favicon.ico", ROOT / "favicon.ico")   # browsers still ask for /favicon.ico


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
WIDTHS_CARD = (160, 320, 480, 640)


CARD_FILL = 0.80   # a product card's cut-out fills 80% of its square, whatever its source framing


def framed(im: Image.Image) -> Image.Image:
    """Trim a cut-out's transparent margin and centre it on a square transparent canvas at
    CARD_FILL, so the index and switcher thumbnails show every product at one scale (the
    sources fill anywhere from 56% to 92% of their frame)."""
    im = im.convert("RGBA")
    box = im.getchannel("A").getbbox()
    if not box:
        return im
    im = im.crop(box)
    side = round(max(im.size) / CARD_FILL)
    canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    canvas.paste(im, ((side - im.width) // 2, (side - im.height) // 2))
    return canvas


def webp_variant(src: pathlib.Path, width: int, out_dir: pathlib.Path, frame: bool = False) -> tuple[str, int, int]:
    """Write <stem>-<width>.webp into out_dir (from a content-hash cache) and return
    (filename, width, height). Never upscales: a request wider than the source yields a
    rendition at the source's own width."""
    data = src.read_bytes()
    with Image.open(src) as im0:
        im = framed(im0) if frame else im0
        W, H = im.size
        w = min(width, W)
        h = round(H * w / W)
        name = f"{src.stem}-{width}.webp"
        key = hashlib.sha1(data + f"|{w}|q80m6|{'f%s' % CARD_FILL if frame else ''}".encode()).hexdigest()[:16]
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
    body = render_product_body(slug, content) if content else None
    if body:
        # A content section whose template has no slot for it would vanish without a word.
        missing = [k for k in ("STEPS", "ATTACHMENTS", "SPECS_ROWS", "FAQ_ITEMS", "VIDEOS")
                   if body[k].strip() and "{{%s}}" % k not in template]
        if missing:
            raise ContentError(f"{slug}: content has {', '.join(missing)} but {spec['template']} "
                               "has no placeholder for it, so it would not appear on the page")
    out_dir = ROOT / slug
    # Everything is rendered first and only swapped in once every page has rendered, so a
    # content error leaves the live guide exactly as it was (the stores read the sitemap
    # that lists these pages). Images go to a staging folder that replaces img/ at the end.
    img_dir = out_dir / ".img-next"
    shutil.rmtree(img_dir, ignore_errors=True)
    img_dir.mkdir(parents=True)
    try:
        _build_product(slug, spec, template, content, body, out_dir, img_dir)
    finally:
        shutil.rmtree(img_dir, ignore_errors=True)


def _build_product(slug, spec, template, content, body, out_dir, img_dir) -> None:

    register_button = ("" if spec.get("register") is False else
                       (ROOT / "sections" / "partials" / "register-button.html").read_text().rstrip("\n"))
    hosted = offline = (template.replace("{{ACCESSORIES}}", accessories_html(slug))
                                .replace("{{REGISTER_BUTTON}}", register_button)
                                .replace("{{SUPPORT_FOOTER}}", support_footer()))

    # Structured content (steps/attachments/specs/faq/videos) — still contains unresolved
    # {{img:...}} image tokens, resolved by the per-image loop right below.
    if content:
        for key in ("STEPS", "ATTACHMENTS", "SPECS_ROWS", "FAQ_ITEMS", "VIDEOS"):
            hosted = hosted.replace("{{%s}}" % key, body[key])
            offline = offline.replace("{{%s}}" % key, body[key])

    # Template-level images ({{KEY}} in "images"): published only if the template uses them.
    for key, filename in spec["images"].items():
        if "{{%s}}" % key not in hosted:
            continue
        src = SRC / filename
        if key.startswith("UPG_"):
            # an Upgrades card picture (drawn ~104px wide): a small WebP, not the source PNG
            name, _, _ = webp_variant(src, 320, img_dir)
            hosted = hosted.replace("{{%s}}" % key, f"img/{name}")
            offline = offline.replace("{{%s}}" % key, data_uri(img_dir / name))
            continue
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
        inline_name, _, _ = webp_variant(src, widths[-1], img_dir)
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
            webp_variant(SRC / card_image, w, img_dir, frame=True)

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
    pre_i18n = hosted
    hosted = hosted.replace("</body>", lang_switch_script("EN", f"{slug}/", f"/{slug}/", save=False) + "</body>", 1)
    offline = inject_i18n(offline, translations)

    # G Pen Core: fonts, shared CSS + behavior, icons, canonical + share tags.
    title, desc = page_meta(hosted)
    canonical = f"{BASE_URL}{slug}/"
    og_image = share_image(slug)
    ld = guide_jsonld(slug, spec, content, title, desc) if content else None
    hosted = inject_core(hosted, core_head("../", False, canonical, title, desc, og_image, jsonld=ld,
                                           alts=alternates(f"{slug}/"), lang_path=f"{slug}/"))
    offline = inject_core(offline, core_head("../", True, canonical, title, desc, og_image, noindex=True))

    # Any {{...}} left means a placeholder nothing filled (a missing image key, a typo):
    # fail loudly rather than publish a broken image or a literal "{{X}}".
    for label, page in (("index.html", hosted), ("offline.html", offline)):
        left = sorted(set(re.findall(r"\{\{[^{}]{1,60}\}\}", page)))
        if left:
            raise ContentError(f"{slug}/{label} still contains {', '.join(left)}")

    # The same guide at /es/<slug>/, /de/<slug>/ ...: what a visitor's browser would show
    # after translating, written out so search engines can index it.
    core_t = merge_translations(None)
    def title_for(key, strings):
        return strings.get("doc_title") or f"{title.rsplit(': ', 1)[0]}: {strings.get('nav_use', 'How to use')}"
    def head_for(key, folder, t, d):
        leaf = (cache or {}).get(key, {}).get("content", {})
        jl = (guide_jsonld(slug, spec, localize_content(content, leaf), t, d, LANG_NAMES[key], folder,
                           core_t[key].get("doc_title_index", "G Pen Product Guides")) if content else None)
        return core_head("../", False, f"{BASE_URL}{folder}/{slug}/", t, d, og_image, jsonld=jl,
                         alts=alternates(f"{slug}/"), translated=True)
    lang_pages = write_lang_pages(pre_i18n, f"{slug}/", translations, slug, title_for, head_for, dry=True)

    # every page rendered: swap in the new images, then write
    final_img = out_dir / "img"
    shutil.rmtree(final_img, ignore_errors=True)
    img_dir.rename(final_img)
    write(out_dir / "index.html", hosted)
    write(out_dir / "offline.html", offline)
    for _, folder, _ in LANG_PAGES:
        shutil.rmtree(ROOT / folder / slug, ignore_errors=True)
    for f, page in lang_pages:
        write(f, page)


def build_index() -> None:
    template = (SRC / "index.template.html").read_text()
    grouped, ungrouped, legacy_html = {g: [] for g, _, _ in INDEX_GROUPS}, [], []
    # display order: group by group, then anything unfiled; the first four cards on screen
    # load their pictures right away
    rank = {g: i for i, (g, _, _) in enumerate(INDEX_GROUPS)}
    ordered = sorted(visible_products().items(), key=lambda kv: rank.get(kv[1].get("group"), len(rank)))
    for n, (slug, spec) in enumerate(ordered):
        href, extattr = _card_href(slug, spec)
        srcset, dims = card_srcset(slug, spec, "", SIZES_INDEX_CARD)
        card = CARD.format(
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
        )
        if spec.get("legacy"):
            legacy_html.append(card)
        elif spec.get("group") in grouped:
            grouped[spec["group"]].append(card)
        else:
            ungrouped.append(card)   # a product nobody has filed yet still shows, at the end
    blocks = []
    for key, i18n_key, heading in INDEX_GROUPS:
        if grouped[key]:
            blocks.append(
                f'    <div class="group" role="group" aria-labelledby="grp-{key}">\n'
                f'      <h2 class="group-title" id="grp-{key}" data-i18n="{i18n_key}">{heading}</h2>\n'
                '      <div class="grid">\n' + "\n".join(grouped[key]) + "\n      </div>\n"
                "    </div>")
    if ungrouped:
        blocks.append('    <div class="group">\n      <div class="grid">\n' + "\n".join(ungrouped) + "\n      </div>\n    </div>")
    cards_html = blocks
    legacy_section = ""
    if legacy_html:
        legacy_section = (
            '\n    <details class="legacy">\n'
            f'      <summary data-i18n="legacy_title">{LEGACY_LABEL}</summary>\n'
            '      <div class="grid">\n' + "\n".join(legacy_html) + "\n      </div>\n"
            "    </details>"
        )
    page = (template.replace("{{CARDS}}", "\n".join(cards_html))
                    .replace("{{SUPPORT_FOOTER}}", support_footer())
                    .replace("{{LEGACY_SECTION}}", legacy_section)
                    .replace("{{YEAR}}", YEAR))
    # The shared strings reach every page, so the index's own tab title rides under its own
    # key and is mapped to doc_title (what the runtime reads) here, for this page only.
    def titled(key):
        t = merge_translations(None)
        return {lang: {**strings, "doc_title": strings.get(key, "")} for lang, strings in t.items()}
    page_plain = page
    page = page_plain.replace("</body>", lang_switch_script("EN", "", "/", save=False) + "</body>", 1)
    title, desc = page_meta(page)
    first = next(iter(visible_products().items()))
    og_image = share_image("home")
    index = inject_core(page, core_head("", False, BASE_URL, title, desc, og_image, jsonld=index_jsonld(title, desc),
                                        alts=alternates(""), lang_path=""))
    write(ROOT / "index.html", index)

    # /es/, /de/ ... home pages
    use = {k: v.get("shell", {}).get("nav_use", "How to use") for k, v in (load_i18n("hydout") or {}).items()}
    def head_for(key, folder, t, d):
        jl = index_jsonld(t, d, LANG_NAMES[key], folder, "{}: " + use.get(key, "How to use"))
        return core_head("", False, f"{BASE_URL}{folder}/", t, d, og_image, jsonld=jl,
                         alts=alternates(""), translated=True)
    write_lang_pages(page_plain, "", titled("doc_title_index"), "index",
                     lambda key, strings: strings["doc_title_index"], head_for)

    # 404: GitHub Pages serves /404.html for any missing path, at any depth, so every
    # relative link on it is resolved against the site root with <base>.
    notice = ('<p class="notfound" data-i18n="nf_text">We couldn\'t find that page. '
              'Pick your device below to get to its guide.</p>\n')
    nf = inject_i18n(page_plain, titled("doc_title_404"))
    nf = nf.replace("<head>", f'<head>\n<base href="{BASE_URL}">', 1)
    nf = nf.replace("<title>", "<title>Page not found: ", 1)
    nf = nf.replace('  <div class="wrap list">', f'  <div class="wrap">{notice}  </div>\n  <div class="wrap list">', 1)
    nf = inject_core(nf, core_head("", False, BASE_URL, "Page not found: G Pen Product Guides", desc, None, noindex=True))
    write(ROOT / "404.html", nf)


# ─────────────────────────────────────────────────────────────────────────────────────
# "Which G Pen do I have?" (/identify/): every guide's photo with three "look for" cues,
# grouped by what goes in the device, plus tips for the look-alikes
# ─────────────────────────────────────────────────────────────────────────────────────
# look-alike tips (i18n id_tip_<key>, id_tip_<key>_t), each shown only when every device it
# names is on the page
ID_TIPS = {
    "dryherb": [("elite", ["elite-ii", "dash-ii", "dash-plus"]), ("dash", ["dash-ii", "dash-plus"])],
    "concentrate": [("hydmic", ["hydout", "micro-ii"]), ("micro", ["micro-ii", "micro-plus"]),
                    ("rig", ["hyer", "connect"])],
    "510": [("510", ["hydout", "510-original"])],
}

ID_DEV = """        <article class="dev" id="{slug}">
          <{photo_tag} class="dev-photo"{photo_attrs}><img src="{img}"{srcset} alt=""{dims}{loading}></{photo_tag}>
          <div class="dev-head">
            <{h} class="dev-name">{name_html}</{h}>
            <span class="eyebrow" data-i18n="cat_{slug}">{category}</span>
          </div>
          <div class="dev-cues">
            <p class="eyebrow" data-i18n="id_look">{look}</p>
            <ul>
{cues}
            </ul>
          </div>
          {action}
        </article>"""


def build_identify() -> None:
    data = json.loads((I18N_DIR / "identify.json").read_text())
    en = data["EN"]
    esc = lambda t: htmllib.escape(keep_together(no_widow(t)), quote=False)
    guides = [(s, p) for s, p in visible_products().items() if p.get("template")]
    # older devices are listed whether or not their guide is published yet
    shown = guides + [(s, p) for s, p in PRODUCTS.items() if p.get("legacy") and (s, p) not in guides]
    has_guide = {s for s, _ in guides}
    missing = [f"id_{s}_{n}" for s, _ in shown for n in (1, 2, 3) if not en.get(f"id_{s}_{n}")]
    unfiled = [s for s, p in shown if p.get("group") not in {g for g, _, _ in INDEX_GROUPS}]
    if missing or unfiled:
        raise ContentError("identify: every device on the page needs three 'look for' cues in "
                           f"i18n/identify.json and a group in PRODUCTS (missing {', '.join(missing + unfiled)})")
    img_dir = ROOT / "identify" / "img"          # photos of devices that have no guide folder
    shutil.rmtree(img_dir, ignore_errors=True)
    on_page = {s for s, _ in shown}
    core_en = merge_translations(None)["EN"]

    def card(slug, spec, n, h):
        if slug in has_guide:
            srcset, dims = card_srcset(slug, spec, "../", "96px")
            img = _card_img(slug, spec, is_switcher=True)
            photo_tag, photo_attrs = "a", f' href="../{slug}/" tabindex="-1" aria-hidden="true"'
            name_html = f'<a href="../{slug}/">{spec["name"]}</a>'
            action = (f'<a class="dev-go" href="../{slug}/"><span data-i18n="id_open">{esc(en["id_open"])}</span>'
                      f'<span class="sr-only">: {spec["name"]}</span><span aria-hidden="true">→</span></a>')
        else:
            src = SRC / (spec.get("id_image") or spec["card_image"])
            img_dir.mkdir(parents=True, exist_ok=True)
            parts = []
            for w in WIDTHS_CARD:
                name, rw, _ = webp_variant(src, w, img_dir, frame=True)
                parts.append(f"img/{name} {rw}w")
            with Image.open(src) as im:
                W, H = framed(im).size
            img = f"img/{webp_variant(src, WIDTHS_CARD[1], img_dir, frame=True)[0]}"
            srcset, dims = f' srcset="{", ".join(dict.fromkeys(parts))}" sizes="96px"', f' width="{W}" height="{H}"'
            photo_tag, photo_attrs, name_html = "div", "", spec["name"]
            action = (f'<a class="dev-go dev-help" href="#support"><span data-i18n="id_help_btn">'
                      f'{esc(en["id_help_btn"])}</span><span aria-hidden="true">↓</span></a>')
        return ID_DEV.format(
            slug=slug, img=img, srcset=srcset, dims=dims, loading="" if n < 2 else ' loading="lazy"',
            photo_tag=photo_tag, photo_attrs=photo_attrs, h=h, name_html=name_html,
            category=spec["category"], look=esc(en["id_look"]), action=action,
            cues="\n".join(f'              <li data-i18n="id_{slug}_{i}">{esc(en[f"id_{slug}_{i}"])}</li>' for i in (1, 2, 3)))

    chips, blocks, n = [], [], 0
    for key, i18n_key, heading in INDEX_GROUPS:
        current = [(s, p) for s, p in shown if p.get("group") == key and not p.get("legacy")]
        older = [(s, p) for s, p in shown if p.get("group") == key and p.get("legacy")]
        if not current and not older:
            continue
        chips.append(f'        <a class="chip" href="#id-{key}" data-i18n="id_chip_{key}">{esc(en[f"id_chip_{key}"])}</a>')
        body = []
        if current:
            body.append('      <div class="grid">\n' + "\n".join(card(s, p, n + i, "h3") for i, (s, p) in enumerate(current)) + "\n      </div>")
            n += len(current)
        if older:
            body.append(f'      <h3 class="older-title" data-i18n="legacy_title">{esc(core_en["legacy_title"])}</h3>\n'
                        '      <div class="grid">\n' + "\n".join(card(s, p, n + i, "h4") for i, (s, p) in enumerate(older)) + "\n      </div>")
            n += len(older)
        tips = "".join(
            f'\n      <aside class="tip"><p class="tip-t" data-i18n="id_tip_{t}_t">{esc(en[f"id_tip_{t}_t"])}</p>'
            f'<p data-i18n="id_tip_{t}">{esc(en[f"id_tip_{t}"])}</p></aside>'
            for t, names in ID_TIPS.get(key, []) if all(x in on_page for x in names))
        blocks.append(
            f'    <section class="group" id="id-{key}" aria-labelledby="idg-{key}">\n'
            f'      <h2 class="group-title" id="idg-{key}" data-i18n="{i18n_key}">{heading}</h2>\n'
            f'      <p class="group-sub" data-i18n="id_sub_{key}">{esc(en[f"id_sub_{key}"])}</p>\n'
            + "\n".join(body) + tips + "\n    </section>")
    page = ((SRC / "identify.template.html").read_text()
            .replace("{{ID_CHIPS}}", "\n".join(chips)).replace("{{ID_GROUPS}}", "\n".join(blocks))
            .replace("{{SUPPORT_FOOTER}}", support_footer())
            .replace("{{YEAR}}", YEAR))

    page_t = {lang: {k: v for k, v in strings.items()} for lang, strings in data.items() if not lang.startswith("_")}
    translations = merge_translations(page_t)
    for lang, strings in translations.items():
        strings["doc_title"] = strings.get("doc_title_identify", "")
    pre = page
    page = page.replace("</body>", lang_switch_script("EN", "identify/", "/identify/", save=False) + "</body>", 1)
    title, desc = page_meta(page)
    url = f"{BASE_URL}identify/"

    def jsonld(t, d, lang, folder, home_name):
        home = f"{BASE_URL}{folder + '/' if folder else ''}"
        me = f"{home}identify/"
        return {"@context": "https://schema.org", "@graph": [
            {"@type": "WebPage", "@id": me, "url": me, "name": t, "description": d, "inLanguage": lang,
             "isPartOf": {"@id": f"{BASE_URL}#site"}, "breadcrumb": {"@id": f"{me}#breadcrumb"},
             "mainEntity": {"@type": "ItemList", "itemListElement": [
                 {"@type": "ListItem", "position": i, "name": p["name"], "url": f"{home}{s}/",
                  "image": f"{BASE_URL}{s}/img/{p['card_image']}"} for i, (s, p) in enumerate(guides, start=1)]}},
            {"@type": "BreadcrumbList", "@id": f"{me}#breadcrumb", "itemListElement": [
                {"@type": "ListItem", "position": 1, "name": home_name, "item": home},
                {"@type": "ListItem", "position": 2, "name": t, "item": me}]},
            WEBSITE, ORG]}

    og_image = share_image("home")
    page = inject_core(page, core_head("../", False, url, title, desc, og_image,
                                       jsonld=jsonld(title, desc, "en", "", "G Pen Product Guides"),
                                       alts=alternates("identify/"), lang_path="identify/"))
    write(ROOT / "identify" / "index.html", page)

    core_t = merge_translations(None)
    def head_for(key, folder, t, d):
        return core_head("../", False, f"{BASE_URL}{folder}/identify/", t, d, og_image,
                         jsonld=jsonld(t, d, LANG_NAMES[key], folder, core_t[key].get("doc_title_index", "G Pen Product Guides")),
                         alts=alternates("identify/"), translated=True)
    write_lang_pages(pre, "identify/", translations, "identify",
                     lambda key, strings: strings.get("doc_title_identify") or title, head_for)


def build_seo_files() -> None:
    paths = [""] + [f"{s}/" for s, spec in visible_products().items() if spec.get("template")] + EXTRA_PAGES
    # every language version of a page lists all of them (itself included) plus x-default,
    # the same set as the hreflang links in each page's <head>
    sitemap = ['<?xml version="1.0" encoding="UTF-8"?>',
               '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" '
               'xmlns:xhtml="http://www.w3.org/1999/xhtml">']
    # no <lastmod>: a date that moves on every rebuild would claim every page changed daily
    for folder in [""] + [f for _, f, _ in LANG_PAGES]:
        for p in paths:
            sitemap.append(f"  <url><loc>{BASE_URL}{folder + '/' if folder else ''}{p}</loc>")
            sitemap += [f'    <xhtml:link rel="alternate" hreflang="{h}" href="{u}"/>' for h, u in alternates(p)]
            sitemap.append("  </url>")
    sitemap.append("</urlset>")
    (ROOT / "sitemap.xml").write_text("\n".join(sitemap) + "\n")
    (ROOT / f"{INDEXNOW_KEY}.txt").write_text(INDEXNOW_KEY)
    # Keeps the build inputs, which GitHub Pages also serves, out of search results.
    (ROOT / "robots.txt").write_text(
        "User-agent: *\n"
        "Disallow: /src/\nDisallow: /content/\nDisallow: /i18n/\nDisallow: /sections/\nDisallow: /scripts/\n"
        "Disallow: /.claude/\nDisallow: /build.py\nDisallow: /serve.py\nDisallow: /README.md\n"
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
    for name, step in (("home page", build_index), ("identify page", build_identify)):
        try:
            step()
        except ContentError as e:
            failed.append(name)
            print(f"\n  ✗ {e}\n")
    publish_core()
    if failed:
        # the sitemap, llms files and IndexNow list would describe pages that weren't rebuilt
        print("  kept the previous sitemap.xml, robots.txt and llms files (build failed)")
    else:
        build_seo_files()
        build_llms_files()

    for slug, spec in PRODUCTS.items():
        if spec.get("hidden") and spec.get("template") and (ROOT / slug).is_dir():
            # ignore_errors: macOS ._ sidecars on network volumes vanish mid-walk
            shutil.rmtree(ROOT / slug, ignore_errors=True)
            for _, folder, _ in LANG_PAGES:
                shutil.rmtree(ROOT / folder / slug, ignore_errors=True)
            print(f"  removed {slug}/ (hidden — source kept in src/, content/, i18n/)")

    if failed:
        print(f"\nFAILED: {', '.join(failed)} — fix the content errors above; their pages were not rebuilt.")
        sys.exit(1)
    print(f"\nDone. Preview with: python3 serve.py")
