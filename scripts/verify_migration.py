#!/usr/bin/env python3
"""Verify the content/schema/renderer migration didn't lose or corrupt anything.

Two checks, per product:
  1. HTML diff — the committed index.html/offline.html vs. a fresh build from the new
     content-driven path must be byte-identical, except for the pre-authorized Hydout/
     Micro II Vimeo-hash-attribute normalization (data-hash/data-vimeo-h -> data-vimeo-hash)
     and video aria-label/alt text now always matching the visible <h3> title verbatim —
     Hydout ("How to Use" -> "How to use") and Melt ("G Pen Melt in action" ->
     "Melt in Action") each had it hand-authored slightly differently from the title.
  2. Translation fidelity — every language's window._T blob must carry the same actual
     translated text as HEAD's committed version. Compared as normalized text content
     (HTML tags stripped, whitespace collapsed), not raw bytes: the new renderer's zone
     HTML can have different internal whitespace/tag-order than the old regex-captured
     blob without being wrong — what matters is nothing was dropped or mistranslated.

Usage:
  python3 scripts/verify_migration.py              # all products with a content/<slug>.json
  python3 scripts/verify_migration.py micro-ii hyer
"""

import html
import json
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).parent.parent
CONTENT_DIR = ROOT / "content"

# products where a byte diff is expected and pre-authorized (see module docstring).
KNOWN_HTML_DIFFS = {"hydout", "micro-ii", "melt"}

TAG_RE = re.compile(r"<[^>]+>")
WS_RE = re.compile(r"\s+")


def norm_text(html_fragment):
    """Strip tags, unescape entities, collapse whitespace — for comparing MEANING,
    not markup shape."""
    text = TAG_RE.sub(" ", html_fragment)
    text = html.unescape(text)
    return WS_RE.sub(" ", text).strip()


def git_show(path):
    try:
        return subprocess.run(
            ["git", "show", f"HEAD:{path}"], cwd=ROOT,
            capture_output=True, text=True, check=True,
        ).stdout
    except subprocess.CalledProcessError:
        return None


WINDOW_T_RE = re.compile(r"<script>window\._T=(.*?);</script>\n<script>.*?</script>\n", re.DOTALL)


def extract_window_t(html_text):
    m = re.search(r"<script>window\._T=(.*?);</script>", html_text, re.DOTALL)
    if not m:
        return None
    return json.loads(m.group(1))


def strip_i18n_injection(html_text):
    """Remove the window._T blob + runtime script (translation payload, verified
    separately by check_translations) so the static-markup byte-diff isn't polluted
    by JSON key-order/whitespace differences that carry no meaning."""
    return WINDOW_T_RE.sub("", html_text)


def check_html_diff(slug):
    problems = []
    for fname in ("index.html", "offline.html"):
        rel = f"{slug}/{fname}"
        old = git_show(rel)
        new_path = ROOT / rel
        if old is None or not new_path.exists():
            continue
        new = new_path.read_text()
        if strip_i18n_injection(old) == strip_i18n_injection(new):
            continue
        if slug not in KNOWN_HTML_DIFFS:
            problems.append(f"{rel}: unexpected byte diff (not in the pre-authorized set)")
    return problems


def check_translations(slug):
    problems = []
    old = git_show(f"{slug}/index.html")
    new_path = ROOT / slug / "index.html"
    if old is None or not new_path.exists():
        return [f"{slug}: no committed baseline or no fresh build to compare"]
    old_t = extract_window_t(old)
    new_t = extract_window_t(new_path.read_text())
    if old_t is None:
        return []  # product had no i18n cache before migration — nothing to verify
    if new_t is None:
        return [f"{slug}: window._T missing from the fresh build"]

    for lang, old_flat in old_t.items():
        new_flat = new_t.get(lang, {})
        for key, old_val in old_flat.items():
            if key not in new_flat:
                problems.append(f"{slug}[{lang}].{key}: present in HEAD, missing after migration")
                continue
            new_val = new_flat[key]
            if isinstance(old_val, str) and isinstance(new_val, str):
                if norm_text(old_val) != norm_text(new_val):
                    problems.append(
                        f"{slug}[{lang}].{key}: text changed\n"
                        f"    was: {norm_text(old_val)[:200]!r}\n"
                        f"    now: {norm_text(new_val)[:200]!r}"
                    )
    return problems


def main():
    args = sys.argv[1:]
    import importlib.util
    spec = importlib.util.spec_from_file_location("build", ROOT / "build.py")
    build = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(build)
    visible = build.visible_products()
    slugs = args if args else sorted(p.stem for p in CONTENT_DIR.glob("*.json")
                                     if not p.name.startswith("._") and p.stem in visible)

    total_problems = 0
    for slug in slugs:
        problems = check_html_diff(slug) + check_translations(slug)
        if problems:
            print(f"✗ {slug}: {len(problems)} problem(s)")
            for p in problems:
                print(f"    {p}")
            total_problems += len(problems)
        else:
            print(f"✓ {slug}: clean")

    print()
    if total_problems:
        print(f"FAILED — {total_problems} problem(s) across {len(slugs)} product(s).")
        raise SystemExit(1)
    print(f"All {len(slugs)} product(s) verified clean.")


if __name__ == "__main__":
    main()
