#!/usr/bin/env python3
"""Render the link-preview images (og:image) for help.gpen.com: one per guide plus one for
the home page, 1200x630, written to src/share/ (build.py publishes them to /core/share/).

    python3 scripts/make_share_cards.py          # every card
    python3 scripts/make_share_cards.py hydout   # just these

Run it after adding a product or changing a product photo, then build. Each card is an HTML
page (the site's own fonts and wordmark) screenshotted by headless Chrome. No translated words
on the image (wordmark, product name, address), so one card serves every language: the
preview's title and description under it are already in the page's language.
"""
import pathlib
import subprocess
import sys
import tempfile

from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import build  # noqa: E402  (PRODUCTS, framed, SRC, CORE_SRC)

OUT = build.SRC / "share"
W, H = 1200, 630
import re  # noqa: E402
# the exact wordmark the site uses (from the home page template), in white
WORDMARK = re.search(r'<svg class="wordmark".*?</svg>', (build.SRC / "index.template.html").read_text(), re.S).group(0)
WORDMARK = WORDMARK.replace('fill="currentColor"', 'fill="#fff"').replace(' class="wordmark"', "")

CSS = """
@font-face{font-family:Kanit;font-style:italic;font-weight:800;src:url(%(fonts)s/kanit-800i-latin.woff2)}
@font-face{font-family:Lato;font-weight:700;src:url(%(fonts)s/lato-700-latin.woff2)}
*{box-sizing:border-box;margin:0}
html,body{width:%(w)dpx;height:%(h)dpx;overflow:hidden}
body{background:radial-gradient(120%% 140%% at 18%% 20%%,#22252b 0%%,#121418 46%%,#08090b 100%%);
  font-family:Lato,Arial,sans-serif;color:#fff;position:relative}
body::before{content:"";position:absolute;left:0;right:0;top:0;height:6px;background:#FFC876}
.wm{position:absolute;left:72px;top:78px;width:210px}
.wm svg{width:100%%;height:auto;display:block}
.name{position:absolute;left:72px;top:200px;width:560px;font-family:Kanit,'Arial Black',sans-serif;
  font-style:italic;font-weight:800;text-transform:uppercase;letter-spacing:-.01em;line-height:.98}
.bar{position:absolute;left:72px;width:72px;height:8px;background:#FFC876;border-radius:4px}
.url{position:absolute;left:72px;bottom:66px;font-size:30px;font-weight:700;letter-spacing:.02em;color:#C9CDD3}
.plate{position:absolute;right:64px;top:55px;width:520px;height:520px;border-radius:44px;
  background:radial-gradient(80%% 80%% at 50%% 40%%,#F4F5F6 0%%,#E4E5E7 62%%,#D6D8DB 100%%);
  box-shadow:0 30px 80px -20px rgba(0,0,0,.6);display:grid;place-items:center}
.plate img{width:84%%;height:84%%;object-fit:contain;filter:drop-shadow(0 18px 22px rgba(0,0,0,.28))}
/* home card: the lineup on one long plate */
.home .wm{left:72px;top:70px;width:230px}
.home .lock{position:absolute;left:330px;top:98px;font-size:26px;font-weight:700;letter-spacing:.18em;
  text-transform:uppercase;color:#E9EBEE}
.home .tag{position:absolute;right:72px;top:92px;font-size:30px;font-weight:700;color:#C9CDD3;letter-spacing:.02em}
.home .shelf{position:absolute;left:56px;right:56px;bottom:56px;height:330px;border-radius:40px;
  background:radial-gradient(70%% 90%% at 50%% 30%%,#F4F5F6 0%%,#E4E5E7 60%%,#D6D8DB 100%%);
  box-shadow:0 30px 80px -24px rgba(0,0,0,.6);display:flex;align-items:center;justify-content:space-evenly;padding:0 18px}
.home .shelf img{height:210px;width:auto;max-width:150px;object-fit:contain;filter:drop-shadow(0 14px 16px rgba(0,0,0,.28))}
.home .shelf img.wide{height:auto;width:150px}
"""


def card_photo(spec: dict, tmp: pathlib.Path, slug: str, tight: bool = False) -> pathlib.Path:
    """The product cut-out squared the way the site's cards frame it, or (tight) trimmed to
    the product itself so a row of them can share one height."""
    src = build.SRC / (spec.get("id_image") or spec["card_image"])
    out = tmp / f"{slug}{'-tight' if tight else ''}.png"
    with Image.open(src) as im:
        im = im.convert("RGBA")
        (im.crop(im.getchannel("A").getbbox()) if tight else build.framed(im)).save(out)
    return out


JOBS = []   # (html file, png file, card name): rendered together by scripts/share_shot.mjs


def shoot(html: str, tmp: pathlib.Path, name: str) -> None:
    page = tmp / f"{name}.html"
    page.write_text(html)
    JOBS.append((page, tmp / f"{name}-shot.png", name))


def render_all(tmp: pathlib.Path) -> None:
    args = [str(x) for page, png, _ in JOBS for x in (page, png)]
    subprocess.run(["node", str(ROOT / "scripts" / "share_shot.mjs"), str(tmp / "profile"), *args],
                   check=True, timeout=300)
    OUT.mkdir(exist_ok=True)
    for _, png, name in JOBS:
        with Image.open(png) as im:
            im.convert("RGB").save(OUT / f"{name}.jpg", quality=88, optimize=True, progressive=True)
        print(f"  src/share/{name}.jpg")


def page(body: str, cls: str = "") -> str:
    css = CSS % {"fonts": (build.CORE_SRC / "fonts").as_uri(), "w": W, "h": H}
    return f'<!doctype html><meta charset="utf-8"><style>{css}</style><body class="{cls}">{body}</body>'


def guide_card(slug: str, spec: dict, tmp: pathlib.Path) -> None:
    name = spec["name"].removeprefix("G Pen ").strip()
    size = 112 if len(name) <= 9 else 92 if len(name) <= 13 else 74
    photo = card_photo(spec, tmp, slug)
    shoot(page(f'<div class="wm">{WORDMARK}</div>'
               f'<div class="name" style="font-size:{size}px">{name}</div>'
               f'<div class="bar" id="bar"></div>'
               f'<div class="url">help.gpen.com</div>'
               f'<div class="plate"><img src="{photo.as_uri()}" alt=""></div>'
               # the name and its gold bar sit centered between the wordmark and the address
               '<script>var n=document.querySelector(".name"),b=document.getElementById("bar"),'
               'lo=150,hi=520,h=n.offsetHeight+28+8,y=Math.round(lo+(hi-lo-h)/2);'
               'n.style.top=y+"px";b.style.top=(y+n.offsetHeight+28)+"px"</script>'),
          tmp, slug)


def home_card(tmp: pathlib.Path, lang: str = "EN", folder: str = "") -> None:
    lineup = [(s, p) for s, p in build.visible_products().items() if p.get("template") and not p.get("legacy")]
    def tag(s, p):
        f = card_photo(p, tmp, s, tight=True)
        with Image.open(f) as im:
            wide = im.width > im.height * 1.2     # the grinder lies flat: size it by width
        return f'<img src="{f.as_uri()}" alt=""{" class=wide" if wide else ""}>'
    imgs = "".join(tag(s, p) for s, p in lineup)
    import html as h, json as j
    title = j.loads((build.I18N_DIR / "_core.json").read_text())[lang]["idx_title"]
    shoot(page(f'<div class="wm">{WORDMARK}</div><div class="lock">{h.escape(title)}</div><div class="tag">help.gpen.com</div>'
               f'<div class="shelf">{imgs}</div>', "home"), tmp, "home" + (f"-{folder}" if folder else ""))


if __name__ == "__main__":
    only = set(sys.argv[1:])
    with tempfile.TemporaryDirectory() as t:
        tmp = pathlib.Path(t)
        if not only or "home" in only:
            # the home card says "Product Guides", so each language gets its own
            home_card(tmp)
            for key, folder, _ in build.LANG_PAGES:
                home_card(tmp, key, folder)
        for slug, spec in build.visible_products().items():
            if spec.get("template") and (not only or slug in only):
                guide_card(slug, spec, tmp)
        render_all(tmp)
