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
content/<product>.json     steps, specs, FAQ, videos for each guide — edit via the CMS
src/accessories.json       Upgrades cards (all products) — edit via the CMS
src/images/                guide images (steps, attachments, video stills)
src/<product>.template.html  the page shell: CSS, nav, section wrappers, scripts
sections/                  renderer: content JSON -> HTML (partials/, render.py,
                           schema.py validation, normalize.py cleanup)
i18n/<product>.json        translation cache (per-string, keyed by stable IDs)
admin/                     Decap CMS editor (config.yml defines the forms)
build.py                   renders everything into the served pages below
serve.py                   local preview on :8811

index.html, <product>/     generated — committed because Pages serves them
```

Never hand-edit a generated file. Copy lives in `content/*.json`; layout lives in
the template shells.

## Editing content

The editor is at `/admin/`. Every save is a commit to `content/<product>.json`
or `src/accessories.json`. Signing in on the live site needs the GitHub OAuth
proxy (not set up yet); until then, edit locally:

```bash
npx decap-server        # terminal 1 — lets the editor write to this checkout
python3 serve.py        # terminal 2
```

Open <http://localhost:8811/admin/>, click Login (no password locally), edit,
then rebuild and refresh translations:

```bash
python3 build.py                      # validates content; fails loudly on bad input
python3 scripts/gen_i18n.py <product> # translates only strings that changed
```

`build.py` normalizes what the editor saves: new bullets/steps/rows get a stable
ID written back to the file (that ID is what keeps a string's translations
attached to it when things are reordered), and blank optional fields become
empty. Text fields support `**bold**`.

Locally the step thumbnails in the editor stay blank until you open **Media**
once — a quirk of the local backend only.

## Working on it

```bash
python3 build.py && python3 serve.py
python3 scripts/verify_migration.py   # built HTML + translations vs. last commit
```

## Adding a product

1. Copy an existing `src/<product>.template.html` shell to the new slug and update
   its name, meta description and Upgrades subtitle.
2. Add an entry to `PRODUCTS` in `build.py` and a file entry in `admin/config.yml`.
3. Create `content/<product>.json` (copy one and edit it in the CMS) and add its
   images to `src/images/`.
4. `python3 build.py`, `python3 scripts/gen_i18n.py <product>`, check locally, commit.

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
