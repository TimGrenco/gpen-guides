#!/usr/bin/env python3
"""One-time migration: convert i18n/<slug>.json from the old whole-zone-HTML-blob format
to the new flat, stable-ID-keyed format compose_translations() expects — WITHOUT calling
the `claude` CLI again. Each language's already-translated zone HTML (step1_body, specs_body,
faq_body) is re-parsed with the same structural logic as extract_content.py and zipped
positionally against the freshly-minted stable IDs in content/<slug>.json — valid because
this runs once, before any reordering has happened under the new scheme.

New format: {"EN": {"shell": {key: str}, "content": {stable_id: str}}, "ES": {...}, ...}
  - "shell": untouched scalar data-i18n strings not derived from content/<slug>.json
    (nav_use, eyebrow, upgrade_sub, acc*_name/note, ...).
  - "content": leaf translations keyed by stable ID (step.<id>.bullet.<bid>, specs.<id>.value,
    faq.<id>.answer, video.<id>.title, ...).

Usage:
  python3 scripts/migrate_i18n_cache.py            # all products with both a cache and content file
  python3 scripts/migrate_i18n_cache.py micro-ii   # one product only
"""

import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).parent.parent
I18N_DIR = ROOT / "i18n"
CONTENT_DIR = ROOT / "content"

sys.path.insert(0, str(ROOT))
from scripts.extract_content import (  # noqa: E402
    TreeParser, find_first, parse_step_body, parse_specs, parse_faq,
)


def parse_fragment(html_fragment):
    p = TreeParser()
    p.feed(html_fragment)
    return p.root


def migrate_product(content, old_cache):
    steps = content.get("steps", [])
    specs = content.get("specs", [])
    faq = content.get("faq", [])
    videos = content.get("videos", [])

    skip_keys = {f"step{i}_body" for i in range(1, len(steps) + 1)}
    skip_keys |= {"specs_body", "faq_body"}
    skip_keys |= {f"vid{i}_title" for i in range(1, len(videos) + 1)}

    new_cache = {}
    for lang, flat in old_cache.items():
        leaves = {}

        for i, step in enumerate(steps, start=1):
            frag = flat.get(f"step{i}_body")
            if not frag:
                continue
            parsed = parse_step_body(parse_fragment(frag))
            prefix = f"step.{step['id']}"
            leaves[f"{prefix}.title"] = parsed["title"]
            for b_en, b_tr in zip(step.get("bullets", []), parsed["bullets"]):
                leaves[f"{prefix}.bullet.{b_en['id']}"] = b_tr["text"]
            for p_en, p_tr in zip(step.get("press", []), parsed["press"]):
                leaves[f"{prefix}.press.{p_en['id']}.action"] = p_tr["action"]
                if p_en.get("sub") is not None and p_tr.get("sub") is not None:
                    leaves[f"{prefix}.press.{p_en['id']}.sub"] = p_tr["sub"]
                if p_en["badge"]["kind"] == "pill" and p_tr["badge"].get("kind") == "pill":
                    leaves[f"{prefix}.press.{p_en['id']}.badge"] = p_tr["badge"]["label"]
            if step.get("note") and parsed.get("note"):
                leaves[f"{prefix}.note"] = parsed["note"]["text"]

        if specs and flat.get("specs_body"):
            root = parse_fragment(flat["specs_body"])
            table = find_first(root, lambda n: n.tag == "table")
            if table is not None:
                for s_en, s_tr in zip(specs, parse_specs(table)):
                    prefix = f"specs.{s_en['id']}"
                    leaves[f"{prefix}.label"] = s_tr["label"]
                    leaves[f"{prefix}.value"] = s_tr["value"]

        if faq and flat.get("faq_body"):
            root = parse_fragment(flat["faq_body"])
            for f_en, f_tr in zip(faq, parse_faq(root)):
                prefix = f"faq.{f_en['id']}"
                leaves[f"{prefix}.question"] = f_tr["question"]
                leaves[f"{prefix}.answer"] = f_tr["answer"]

        for i, v in enumerate(videos, start=1):
            title = flat.get(f"vid{i}_title")
            if title:
                leaves[f"video.{v['id']}.title"] = title

        shell = {k: v for k, v in flat.items() if k not in skip_keys}
        new_cache[lang] = {"shell": shell, "content": leaves}

    return new_cache


def main():
    args = sys.argv[1:]
    slugs = args if args else sorted(p.stem for p in I18N_DIR.glob("*.json") if not p.name.startswith("._"))
    for slug in slugs:
        content_path = CONTENT_DIR / f"{slug}.json"
        cache_path = I18N_DIR / f"{slug}.json"
        if not content_path.exists() or not cache_path.exists():
            print(f"  {slug}: skipping (missing content or cache file)")
            continue
        content = json.loads(content_path.read_text())
        old_cache = json.loads(cache_path.read_text())
        if old_cache and next(iter(old_cache.values())).get("shell") is not None:
            print(f"  {slug}: already migrated, skipping")
            continue
        new_cache = migrate_product(content, old_cache)
        cache_path.write_text(json.dumps(new_cache, ensure_ascii=False, indent=2) + "\n")
        n_leaves = len(new_cache.get("EN", {}).get("content", {}))
        print(f"  {slug}: migrated — {n_leaves} content leaves per language")


if __name__ == "__main__":
    main()
