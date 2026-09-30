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

Base URL: <https://timgrenco.github.io/gpen-guides/>

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

Each guide also has a single-file copy at `/<product>/offline.html` (every image
inlined — for email, trade-show USB sticks, anywhere without a network). QR codes
should point at the hosted `/<product>/` page.

**Product paths go inside printed QR codes, so treat them as permanent.** Once codes
ship on packaging a path can never move. If this should live on a custom domain
such as `guides.gpen.com`, set that up **before** anything goes to print: add a
`CNAME` file at the repo root and point a DNS CNAME record at `timgrenco.github.io`.

## How it's built

```
content/<product>.json       steps, specs, FAQ, videos for each guide
src/accessories.json         Upgrades cards (all products)
src/images/                  guide images (steps, attachments, video stills)
src/<product>.template.html  page shell: CSS, header/nav, section wrappers, scripts
src/*-card.png, *-hero.*     index / switcher thumbnails
sections/                    renderer: content JSON -> HTML
  render.py                    partials/ fragments, translations, text polish
  schema.py / normalize.py     validation + cleanup of what the editor saves
i18n/<product>.json          translation cache, one entry per string (stable IDs)
admin/                       Decap CMS content editor (config.yml = the forms)
build.py                     renders everything into the served pages
serve.py                     local preview on :8811

index.html, <product>/       generated — never edit by hand
```

Copy lives in `content/*.json`; layout lives in the template shells. `PRODUCTS` in
`build.py` lists every guide (name, category, card image, Upgrades button).

```bash
python3 build.py        # validates content, renders every guide, exits 1 on bad content
python3 serve.py        # then open http://localhost:8811
```

## Editing content

**Content editor (Decap CMS) at `/admin/`.** Each save is a commit to
`content/<product>.json` or `src/accessories.json`. Signing in on the live site
needs a GitHub OAuth proxy, which isn't set up yet (see *Not done yet*); until then
the editor runs locally against this checkout:

```bash
npx decap-server        # terminal 1 — lets the editor write to this checkout
python3 serve.py        # terminal 2 — then open http://localhost:8811/admin/ and click Login
```

Or edit the JSON directly. Text fields support `**bold**`.

**After any content change:**

```bash
python3 build.py                        # re-render (also mints IDs for new items)
python3 scripts/gen_i18n.py <product>   # translate only the strings that changed
python3 build.py                        # pick up the new translations
```

`gen_i18n.py` needs the `claude` CLI signed in (it translates via Claude). It only
sends strings whose English changed, keyed by each item's stable ID, so editing or
reordering one bullet re-translates just that bullet.

Locally the step thumbnails in the editor stay blank until you open **Media** once
— a quirk of the local backend only.

## Adding a product

1. Copy an existing shell to `src/<product>.template.html` — e.g.
   `src/melt.template.html`, or `src/grinder.template.html` for a guide without
   videos — and change the title, meta description, bar name, product name and
   Upgrades subtitle.
2. Add the product to `PRODUCTS` in `build.py` and a file entry in `admin/config.yml`.
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

## Not done yet

- **Live editor sign-in:** Decap's GitHub login needs a small OAuth proxy
  (e.g. a free Cloudflare Worker); then set `backend.base_url` in `admin/config.yml`.
- **Auto-publish on save:** a GitHub Action that runs `build.py` +
  `gen_i18n.py` on push (translation in CI needs an Anthropic API key as a secret).
  Until then someone runs the three commands above and commits.

## One-time migration scripts

`scripts/extract_content.py`, `apply_content_tokens.py`, `migrate_i18n_cache.py`
and `verify_migration.py` converted the original hand-written HTML guides into
`content/*.json`. They're kept for reference; day-to-day work doesn't need them.
