# G Pen Product Guides

Mobile-first how-to guides for G Pen products. A customer scans a QR code on the
device or its packaging and lands on that product's guide: how to charge it, load
it, use it and keep it clean — in English, Spanish, German, Italian, French and
Portuguese (language switcher, top right).

A static site: the generated HTML is committed and GitHub Pages serves the repo
root as-is. Nothing builds on push.

## Hosting (GitHub Pages)

Settings → Pages → Source: **Deploy from a branch**, branch `main`, folder `/ (root)`.
`.nojekyll` is already in the repo so Pages serves every file untouched.

Live at <https://help.gpen.com/> (custom domain, since 2026-09-30). The old
<https://timgrenco.github.io/gpen-guides/> address redirects there.

| Guide | Path |
|---|---|
| All guides (index) | `/` |
| G Pen Hydout | `/hydout/` |
| G Pen Dash II | `/dash-ii/` |
| G Pen 510 Original | `/510-original/` |
| G Pen Micro II | `/micro-ii/` |
| G Pen Melt | `/melt/` |
| G Pen Dash+ | `/dash-plus/` |
| G Pen Grinder | `/grinder/` |

Each guide also has a single-file copy at `/<product>/offline.html` (step and video
images inlined — for email, trade-show USB sticks, anywhere without a network). Its
links, the All-guides switcher pictures and the fonts point at the live site, so those
need a connection; the instructions themselves don't. QR codes should point at the
hosted `/<product>/` page.

**Product paths go inside printed QR codes, so treat them as permanent.** Once codes
ship on packaging a path can never move. The site is live at **help.gpen.com**; how it
is wired, for reference:

1. DNS (GoDaddy, gpen.com): CNAME record `help` → `timgrenco.github.io`.
2. `BASE_URL = "https://help.gpen.com/"` in `build.py` (canonical links, share previews,
   sitemap and the offline copies all hang off it) and the `CNAME` file at the repo root.
3. Settings → Pages → Custom domain `help.gpen.com`, "Enforce HTTPS" on.

Any guide can be linked in a specific language with `?lang=es` (es, de, it, fr, pt, en);
the choice sticks for that visitor, same as on the brand portal (assets.gpen.com).

## How it's built

```
content/<product>.json       steps, specs, FAQ, videos for each guide
src/accessories.json         Upgrades cards (all products)
src/images/                  guide images (steps, attachments, video stills)
src/<product>.template.html  page shell: CSS, header/nav, section wrappers, scripts
src/*-card.png, *-hero.*     index / switcher thumbnails
sections/                    renderer: content JSON -> HTML
  render.py                    partials/ fragments, translations, text polish
  schema.py / normalize.py     content validation + cleanup (mints IDs for new items)
i18n/<product>.json          translation cache, one entry per string (stable IDs)
i18n/_core.json              strings shared by every page (categories, index, 404)
src/core/                    G Pen Core — the shared layer, see below
build.py                     renders everything into the served pages
serve.py                     local preview on :8811

index.html, 404.html, <product>/, core/,
sitemap.xml, robots.txt      generated — never edit by hand
```

Copy lives in `content/*.json`; layout lives in the template shells. `PRODUCTS` in
`build.py` lists every guide (name, category, card image, Upgrades button).

```bash
python3 build.py        # validates content, renders every guide, exits 1 on bad content
python3 serve.py        # then open http://localhost:8811
```

## G Pen Core (`src/core/`)

The shared layer every page gets, and the piece meant to be reused across the G Pen
sites (gpen.com, assets.gpen.com, training.gpen.com):

```
src/core/core.css     shared rules + fixes; inlined AFTER each template's own <style>, so it wins ties
src/core/guide.js     all page behavior: sticky header, section spy, language menu, All-guides
                      sheet, video player (focus handling, Escape, scroll lock)
src/core/fonts.css    self-hosted Kanit + Lato (woff2 in src/core/fonts/, published to /core/)
src/core/favicon.svg, apple-touch-icon.png
i18n/_core.json       shared translations
```

The per-product templates still carry their own copy of the page CSS (they drifted apart
over time; core.css papers over the differences). The next consolidation step is one
shared template shell with the per-product strings moved into content JSON.

Images: `build.py` writes WebP renditions next to each image (`<name>-300.webp`,
`-450.webp`, …) with `srcset`/`sizes` and `width`/`height`, cached in `.cache/` by
content hash. Output is deterministic: rebuilding an unchanged tree changes no file.

## Editing content

Edit `content/<product>.json` (steps, specs, FAQ, videos) or `src/accessories.json`
(Upgrades cards) directly. Text fields support `**bold**`. Upgrades prices follow
the live gpen.com store price.

**After any content change:**

```bash
python3 build.py                        # re-render (also mints IDs for new items)
python3 scripts/gen_i18n.py <product>   # translate only the strings that changed
python3 build.py                        # pick up the new translations
```

`gen_i18n.py` needs the `claude` CLI signed in (it translates via Claude). It only
sends strings whose English changed, keyed by each item's stable ID, so editing or
reordering one bullet re-translates just that bullet. Each language uses one glossary
across all products (e.g. PT "bocal" for mouthpiece, FR "Boutique" for Upgrades, DE
"Aufladen" = charge vs "Befüllen" = load); keep new strings consistent with the existing
ones rather than re-translating a term differently.

## Adding a product

1. Copy an existing shell to `src/<product>.template.html` — e.g.
   `src/melt.template.html`, or `src/grinder.template.html` for a guide without
   videos — and change the title, meta description, bar name, product name and
   Upgrades subtitle.
2. Add the product to `PRODUCTS` in `build.py`.
3. Create `content/<product>.json` (copy one and edit), add its step images to
   `src/images/` and its card image to `src/`, and its Upgrades cards to
   `src/accessories.json`.
4. `python3 build.py`, `python3 scripts/gen_i18n.py <product>`, `python3 build.py`,
   check it locally, commit.

Step images are 900×900 squares cropped to a circle by CSS;
`scripts/compose_step.py` turns a product render or photo into one.

## Hidden (legacy) products

Elite II, Micro+, Hyer, Connect and the Roam card are `"hidden": True` in
`PRODUCTS`: not built, not listed, not linked. Their source (templates, content,
translations, images) is kept on purpose. To bring one back, set `hidden` to
`False`, run `build.py`, then `gen_i18n.py <product>` (a few strings will need
translating), then `build.py` again.

## Where the content comes from

Product copy, specs, SKU/UPC and manual PDFs come from the brand asset portal
(<https://assets.gpen.com>, whose `assets/data/*.js` files hold the full data) and
the print manuals on the Grenco drive (`GPEN/Packaging/<product>/Manual/`). The
Register button sends visitors to `/pages/register` on www, ca or eu.gpen.com,
picked from the browser's time zone.

The Grinder has no print manual; its guide was written from its one-sheet, box
and store listing.

## Publishing

Nothing builds on push: run the three commands above, commit (including the
regenerated pages), and push to `main`. GitHub Pages republishes within a minute
or two.

## One-time migration scripts

`scripts/extract_content.py`, `apply_content_tokens.py`, `migrate_i18n_cache.py`
and `verify_migration.py` converted the original hand-written HTML guides into
`content/*.json`. They're kept for reference; day-to-day work doesn't need them.
