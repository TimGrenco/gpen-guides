#!/usr/bin/env python3
"""Generate i18n translations for all G Pen product guide pages.

Usage:
  python3 scripts/gen_i18n.py              # translate all products
  python3 scripts/gen_i18n.py elite-ii     # one product only
  python3 scripts/gen_i18n.py --force      # re-translate even if cached

Output: i18n/<slug>.json — one file per product, {"EN": {"shell": {...}, "content": {...}},
"ES": {...}, ...}. "shell" is scalar data-i18n UI-chrome strings scraped from the built HTML
(nav labels, upgrade_sub, accessory card text, ...). "content" is per-leaf translations of
content/<slug>.json (bullets, press actions, notes, spec rows, FAQ, video titles), keyed by
the item's own stable ID (step.charge.bullet.b1, specs.battery.value, ...) so editing or
reordering one item only invalidates that one cached translation, not its whole step/section.

Requires the `claude` CLI to be logged in (Pro/Max subscription).
"""

import json
import re
import subprocess
import sys
import pathlib

ROOT = pathlib.Path(__file__).parent.parent
I18N_DIR = ROOT / "i18n"
CONTENT_DIR = ROOT / "content"
I18N_DIR.mkdir(exist_ok=True)

sys.path.insert(0, str(ROOT))
from sections.render import extract_content_leaves  # noqa: E402

LANGUAGES = {
    "ES": "Spanish (Latin America)",
    "DE": "German",
    "IT": "Italian",
    "FR": "French (France)",
    "PT": "Portuguese (Brazil)",
}

# ── HTML extraction: shell (UI-chrome) strings only ─────────────────────────
# Content strings (steps/attachments/specs/faq/videos) now come from
# content/<slug>.json directly via extract_content_leaves(), not from the built HTML.

_VID_TITLE_KEY = re.compile(r"^vid\d+_title$")


def _extract_text_attrs(html):
    """Return {key: text} for every data-i18n="key" element (plain text content).

    Mirrors the runtime's own logic (i18n-runtime.js applyLang): if the element
    contains an <svg> or <button> child (e.g. an icon-prefixed nav link), only the
    trailing text node is real label text, so we take the last non-empty text run
    rather than the text immediately after the opening tag.
    """
    strings = {}
    open_tag = re.compile(
        r'<(p|h[1-6]|span|a|button|summary|li|label)\b[^>]*\bdata-i18n="([^"]+)"[^>]*>'
    )
    for m in open_tag.finditer(html):
        tag, key = m.group(1), m.group(2)
        if key in strings:
            continue
        close_m = re.search(r'</' + tag + r'\s*>', html[m.end():], re.IGNORECASE)
        if not close_m:
            continue
        inner = html[m.end():m.end() + close_m.start()]
        if re.search(r'<(svg|button)\b', inner, re.IGNORECASE):
            text = ''
            for part in reversed(re.split(r'<[^>]+>', inner)):
                part = part.strip()
                if part:
                    text = part
                    break
        else:
            text = re.sub(r'<[^>]+>', '', inner).strip()
        if text:
            strings[key] = text
    return strings


def extract_shell_strings(html):
    """Scalar data-i18n strings NOT derived from content/<slug>.json — nav labels,
    section headings, upgrade_sub, accessory card text, etc. vid*_title is excluded:
    it's still a scalar data-i18n key in the DOM, but its source of truth is now
    content/<slug>.json's video.title, extracted separately via extract_content_leaves()."""
    strings = _extract_text_attrs(html)
    return {k: v for k, v in strings.items() if not _VID_TITLE_KEY.match(k)}


def load_content(slug):
    path = CONTENT_DIR / f"{slug}.json"
    if path.exists():
        return json.loads(path.read_text())
    return None


# ── Translation via Claude CLI ──────────────────────────────────────────────

SYSTEM_PROMPT = """You are a professional translator for G Pen (gpen.com), a premium cannabis vaporizer brand.
Translate product guide strings naturally and accurately. Rules:
- Keep ALL HTML tags and their attributes exactly as-is (class, data-*, id, href, etc.)
- Preserve **bold** markdown markers exactly as-is around whatever text they wrap after
  translation (e.g. "**Hold**" -> "**Manterla presionada**") — do not drop or move the **
- Keep technical/brand terms in English: USB-C, Micro USB, WiFi, LED, USB, G Pen, Elite II, Micro+, Hyer, Connect, Dash+, Hydout, Melt, Dash II, Micro II, 510 Original, Hydout
- Keep these press-indicator badges exactly as-is, untranslated: 3s, 2×, 5×, Hold, Side, +, −, ◀, ▶
  (other press-badge words, e.g. "draw", should be translated normally)
- Keep temperature values exactly as-is: °F, °C, numbers
- Keep support contact information exactly as-is (phone numbers, email addresses)
- Translate all body text, headings, instructions, FAQ questions and answers naturally
- Match the friendly, instructional tone of a premium consumer electronics guide
- Return ONLY valid JSON, no markdown fences, no commentary"""


def translate_strings(en_strings, slug):
    """Call the Claude CLI to translate all EN strings to all 5 languages at once."""
    lang_list = "\n".join(f'- {code}: {name}' for code, name in LANGUAGES.items())
    en_json = json.dumps(en_strings, ensure_ascii=False, indent=2)

    prompt = f"""Translate these G Pen "{slug}" product guide strings from English into these languages:
{lang_list}

Return a single JSON object with one key per language code (ES, DE, IT, FR, PT).
Each language's value is an object with the same keys as the input, containing the translated strings.
For any HTML tags present, translate only the visible text content — preserve all tags and attributes.

Input English strings:
{en_json}"""

    result = subprocess.run(
        ["claude", "-p", prompt, "--system-prompt", SYSTEM_PROMPT, "--model", "claude-sonnet-5"],
        capture_output=True, text=True, timeout=600
    )
    if result.returncode != 0:
        raise RuntimeError(f"claude CLI failed: {result.stderr[:500]}")

    raw = result.stdout.strip()
    # Strip markdown fences if present
    raw = re.sub(r'^```(?:json)?\s*', '', raw, flags=re.MULTILINE)
    raw = re.sub(r'\s*```$', '', raw, flags=re.MULTILINE)
    return json.loads(raw)


# ── Per-product pipeline ────────────────────────────────────────────────────

def process_product(slug, built_html_path, force=False):
    out_path = I18N_DIR / f"{slug}.json"

    html = built_html_path.read_text(encoding='utf-8')
    shell_en = extract_shell_strings(html)
    content = load_content(slug)
    leaf_en = extract_content_leaves(content) if content else {}

    if not shell_en and not leaf_en:
        print(f"  {slug}: no translatable strings found — skipping")
        return
    # Disjoint namespaces by construction (shell keys are bare words like "nav_use",
    # content leaf keys always contain a "." like "step.charge.title") — safe to merge.
    all_en = {**shell_en, **leaf_en}

    cached = json.loads(out_path.read_text()) if out_path.exists() else {}
    cached_en_flat = {**cached.get("EN", {}).get("shell", {}), **cached.get("EN", {}).get("content", {})}

    changed = {k: v for k, v in all_en.items() if force or cached_en_flat.get(k) != v}
    if not changed:
        print(f"  {slug}: up-to-date, skipping")
        return

    print(f"  {slug}: translating {len(changed)} changed/new string(s) of {len(all_en)} total "
          f"to {len(LANGUAGES)} languages …")
    translations = translate_strings(changed, slug)

    output = {"EN": {"shell": shell_en, "content": leaf_en}}
    for code in LANGUAGES:
        prev_flat = {**cached.get(code, {}).get("shell", {}), **cached.get(code, {}).get("content", {})}
        merged = {**prev_flat, **translations.get(code, {})}
        # drop keys that no longer exist in the current EN set (removed/renamed content)
        merged = {k: v for k, v in merged.items() if k in all_en}
        output[code] = {
            "shell": {k: v for k, v in merged.items() if k in shell_en},
            "content": {k: v for k, v in merged.items() if k in leaf_en},
        }

    out_path.write_text(json.dumps(output, ensure_ascii=False, indent=2))
    print(f"  {slug}: saved → i18n/{slug}.json")


# ── Main ────────────────────────────────────────────────────────────────────

def main():
    # Import PRODUCTS from build.py without running __main__
    import importlib.util
    spec = importlib.util.spec_from_file_location("build", ROOT / "build.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    args = sys.argv[1:]
    force = '--force' in args
    args = [a for a in args if not a.startswith('--')]
    slugs = args if args else [s for s, spec in mod.PRODUCTS.items() if spec.get('template')]

    print(f"Translating {len(slugs)} product(s) …\n")
    for slug in slugs:
        if slug not in mod.PRODUCTS or not mod.PRODUCTS[slug].get('template'):
            print(f"  {slug}: unknown or no template — skipping")
            continue
        built_path = ROOT / slug / "index.html"
        if not built_path.exists():
            print(f"  {slug}: not built yet (run build.py first) — skipping")
            continue
        try:
            process_product(slug, built_path, force=force)
        except Exception as e:
            print(f"  {slug}: ERROR — {e}")

    print("\nDone.")


if __name__ == "__main__":
    main()
