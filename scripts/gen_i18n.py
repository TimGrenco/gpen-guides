#!/usr/bin/env python3
"""Generate i18n translations for all G Pen product guide pages.

Usage:
  python3 scripts/gen_i18n.py              # translate all products
  python3 scripts/gen_i18n.py elite-ii     # one product only
  python3 scripts/gen_i18n.py --force      # re-translate even if cached

Output: i18n/<slug>.json — one file per product with all 5 non-EN languages.

Requires the `claude` CLI to be logged in (Pro/Max subscription).
"""

import json
import re
import subprocess
import sys
import pathlib

ROOT = pathlib.Path(__file__).parent.parent
I18N_DIR = ROOT / "i18n"
I18N_DIR.mkdir(exist_ok=True)

LANGUAGES = {
    "ES": "Spanish (Latin America)",
    "DE": "German",
    "IT": "Italian",
    "FR": "French (France)",
    "PT": "Portuguese (Brazil)",
}

# ── HTML extraction helpers ─────────────────────────────────────────────────

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


ZONE_SKIP = {
    "vids_block",  # video buttons have JS event listeners — skip zone, use vid1_title/vid2_title instead
}

def _extract_zones(html):
    """Return {key: inner_html} for every data-i18n-zone="key" element."""
    strings = {}
    zone_keys = re.findall(r'data-i18n-zone="([^"]+)"', html)
    for key in zone_keys:
        if key in ZONE_SKIP:
            continue
        if key in strings:
            continue
        m = re.search(r'<(\w+)\b[^>]*\bdata-i18n-zone="' + re.escape(key) + r'"[^>]*>', html)
        if not m:
            continue
        tag = m.group(1)
        start = m.end()
        depth, pos = 1, start
        open_re = re.compile(r'<' + tag + r'\b', re.IGNORECASE)
        close_re = re.compile(r'</' + tag + r'\s*>', re.IGNORECASE)
        while depth > 0 and pos < len(html):
            no = open_re.search(html, pos)
            nc = close_re.search(html, pos)
            if nc is None:
                break
            if no is not None and no.start() < nc.start():
                depth += 1
                pos = no.end()
            else:
                depth -= 1
                if depth == 0:
                    strings[key] = html[start:nc.start()].strip()
                pos = nc.end()
    return strings


def extract_en_strings(html):
    """Extract all translatable EN strings from a built HTML page."""
    strings = {}
    strings.update(_extract_text_attrs(html))
    strings.update(_extract_zones(html))
    return strings


# ── Translation via Claude CLI ──────────────────────────────────────────────

SYSTEM_PROMPT = """You are a professional translator for G Pen (gpen.com), a premium cannabis vaporizer brand.
Translate product guide strings naturally and accurately. Rules:
- Keep ALL HTML tags and their attributes exactly as-is (class, data-*, id, href, etc.)
- Keep technical/brand terms in English: USB-C, Micro USB, WiFi, LED, USB, G Pen, Elite II, Micro+, Hyer, Connect, Dash+, Hydout, Melt, Dash II, Micro II, 510 Original, Hydout
- Keep press-indicator labels exactly as-is: 3s, 2×, 5×, Hold, Side, +, −, ◀, ▶
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
For HTML zone values, translate only the visible text content — preserve all HTML tags and attributes.

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

    # Load EN strings from the built (image-substituted) HTML
    html = built_html_path.read_text(encoding='utf-8')
    en_strings = extract_en_strings(html)
    if not en_strings:
        print(f"  {slug}: no data-i18n strings found — skipping")
        return

    # Check cache: if the file exists and EN strings haven't changed, skip
    if out_path.exists() and not force:
        cached = json.loads(out_path.read_text())
        if cached.get('EN') == en_strings:
            print(f"  {slug}: up-to-date, skipping")
            return
        print(f"  {slug}: EN strings changed, re-translating …")
    else:
        print(f"  {slug}: translating {len(en_strings)} strings to {len(LANGUAGES)} languages …")

    translations = translate_strings(en_strings, slug)

    # Build final object: EN + all translations
    output = {"EN": en_strings}
    for code in LANGUAGES:
        output[code] = translations.get(code, {})

    out_path.write_text(json.dumps(output, ensure_ascii=False, indent=2))
    print(f"  {slug}: saved → i18n/{slug}.json")


# ── Main ────────────────────────────────────────────────────────────────────

def main():
    # Import PRODUCTS from build.py without running __main__
    import importlib.util, types
    spec = importlib.util.spec_from_file_location("build", ROOT / "build.py")
    mod = importlib.util.module_from_spec(spec)
    # Patch so __name__ != '__main__' — skip the build run
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
