#!/usr/bin/env python3
"""One-time migration: in src/<slug>.template.html, replace the hand-written repeated
children (steps, attachments, spec rows, faq items, video cards) with the {{TOKEN}}
placeholders build.py now resolves from content/<slug>.json via sections/render.py.
The surrounding wrapper markup (section/table/div shells) is untouched — it's still
hand-authored per product.

Usage: python3 scripts/apply_content_tokens.py <slug> [<slug> ...]
"""

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).parent.parent
SRC = ROOT / "src"

REPLACEMENTS = [
    (r'<ol class="steps">.*?\n    </ol>', '<ol class="steps">\n{{STEPS}}\n    </ol>'),
    (r'<ul class="attach-list">.*?\n    </ul>', '<ul class="attach-list">\n{{ATTACHMENTS}}\n    </ul>'),
    (r'<tbody>.*?\n            </tbody>', '<tbody>\n{{SPECS_ROWS}}\n            </tbody>'),
    (r'<div class="faq" data-i18n-zone="faq_body">.*?\n        </div>',
     '<div class="faq" data-i18n-zone="faq_body">\n{{FAQ_ITEMS}}\n        </div>'),
    (r'<div class="vids" data-i18n-zone="vids_block">.*?\n    </div>',
     '<div class="vids" data-i18n-zone="vids_block">\n{{VIDEOS}}\n    </div>'),
]


def main():
    slugs = sys.argv[1:]
    if not slugs:
        raise SystemExit("usage: apply_content_tokens.py <slug> [<slug> ...]")
    for slug in slugs:
        path = SRC / f"{slug}.template.html"
        text = path.read_text()
        for pattern, replacement in REPLACEMENTS:
            new_text, n = re.subn(pattern, replacement, text, count=1, flags=re.DOTALL)
            if n:
                text = new_text
        path.write_text(text)
        print(f"{slug}: tokenized")


if __name__ == "__main__":
    main()
