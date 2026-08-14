# G Pen Product Guides

Mobile-first how-to guides for G Pen devices. A customer scans a QR code on the
device or its packaging and lands directly on that product's page: how to charge
it, load it, use it, and keep it clean.

Served as a static site from this repo via GitHub Pages — no build step runs on
push, the generated HTML is committed.

## URLs

Base: <https://timgrenco.github.io/gpen-guides/>

| Page | Path |
|---|---|
| Portal index | `/` |
| G Pen Hydout guide | `/hydout/` |
| Hydout, single file | `/hydout/offline.html` |

If this ever moves to a custom domain such as `guides.gpen.com`, add a `CNAME`
file at the repo root and point a DNS CNAME record at `timgrenco.github.io`.
Worth doing **before** any QR code goes to print — a github.io URL is hard to
migrate away from once it is stamped on packaging.

**The product path is what gets printed inside a QR code, so treat it as
permanent.** Once codes ship on packaging, `/hydout/` can never move or the
printed codes break. Add products alongside it; don't rename existing ones.

## Layout

```
src/                       source of truth — edit here
  index.template.html      portal index
  hydout.template.html     the Hydout guide, with {{PLACEHOLDER}} slots
  *.jpg, *.png             master images
build.py                   renders src/ into the served pages below
serve.py                   local preview on :8811

index.html                 generated
hydout/index.html          generated
hydout/offline.html        generated — all images inlined as data URIs
hydout/img/                generated — copied from src/
```

Generated files are committed because Pages serves them directly. Never hand-edit
a generated file; change the template in `src/` and rebuild.

## Working on it

```bash
python3 build.py && python3 serve.py
```

Then open <http://localhost:8811>.

## Adding a product

1. Copy `src/hydout.template.html` to `src/<product>.template.html` and rewrite
   the copy, image placeholders, and YouTube links.
2. Drop the product's images into `src/`.
3. Add an entry to `PRODUCTS` in `build.py`.
4. Run `python3 build.py`, check it locally, commit.

## Where the content comes from

Product copy, spec and SKU tables, manual PDFs, and how-to video links all come
from the brand assets portal at <https://assets.gpen.com>. Step photos are
currently cropped from the printed manual PDF; they are placeholders until clean
individual step photos are available.

### Not yet confirmed

- **The five heat settings.** Only the 2.4V–3.8V range is documented, not the
  individual voltages, so the guide shows setting *number* rather than a voltage.
- **The FAQ answers** were written from the product specs, not from official
  support documentation. They need a review before customers rely on them.

## The single-file build

`offline.html` is the whole guide — markup, styles, and every image — in one
file with no external requests. Useful for email, a USB stick at a trade show,
or anywhere without a network. It is ~440 KB against ~30 KB for the hosted page,
so the hosted version is what QR codes should point at.
