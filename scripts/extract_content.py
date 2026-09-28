#!/usr/bin/env python3
"""One-time migration: parse each src/<slug>.template.html and mint content/<slug>.json —
the structured steps/attachments/specs/faq/videos data the new renderer (sections/render.py)
consumes. Stable IDs are derived from each item's own title/label text (slugified), not its
position, so a later reorder in the CMS doesn't orphan its translation cache entry.

Usage:
  python3 scripts/extract_content.py              # all products
  python3 scripts/extract_content.py micro-ii      # one product only
"""

import html as htmllib
import importlib.util
import json
import pathlib
import re
import sys
from html.parser import HTMLParser

ROOT = pathlib.Path(__file__).parent.parent
SRC = ROOT / "src"
CONTENT_DIR = ROOT / "content"

sys.path.insert(0, str(ROOT))
from sections.schema import validate_content  # noqa: E402


# ── Minimal HTML tree ────────────────────────────────────────────────────────

class Node:
    __slots__ = ("tag", "attrs", "children")

    def __init__(self, tag, attrs):
        self.tag = tag
        self.attrs = dict(attrs)
        self.children = []  # list of Node | str


VOID_TAGS = {
    "br", "img", "hr", "input", "meta", "link",
    "circle", "line", "path", "rect", "polyline", "polygon",
}


class TreeParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = Node("#root", {})
        self.stack = [self.root]

    def handle_starttag(self, tag, attrs):
        node = Node(tag, attrs)
        self.stack[-1].children.append(node)
        if tag not in VOID_TAGS:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        self.stack[-1].children.append(Node(tag, attrs))

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, 0, -1):
            if self.stack[i].tag == tag:
                del self.stack[i:]
                return

    def handle_data(self, data):
        self.stack[-1].children.append(data)


def classes(node):
    return node.attrs.get("class", "").split()


def find_all(node, pred, acc=None):
    if acc is None:
        acc = []
    for c in node.children:
        if isinstance(c, str):
            continue
        if pred(c):
            acc.append(c)
        find_all(c, pred, acc)
    return acc


def find_first(node, pred):
    for c in node.children:
        if isinstance(c, str):
            continue
        if pred(c):
            return c
        r = find_first(c, pred)
        if r is not None:
            return r
    return None


def contains_tag(node, tag):
    return find_first(node, lambda n: n.tag == tag) is not None


def inline_to_markdown(node):
    """A node's mixed text/<b> children -> **bold**-markdown plain text."""
    if node is None:
        return ""
    parts = []
    for c in node.children:
        if isinstance(c, str):
            parts.append(htmllib.unescape(c))
        elif c.tag == "b":
            parts.append(f"**{inline_to_markdown(c)}**")
        else:
            raise ValueError(f"unexpected inline <{c.tag}> inside <{node.tag}>")
    return "".join(parts).strip()


def slugify(text):
    s = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    return s or "item"


def img_token(src):
    return src.strip("{}")


# ── Section parsers ──────────────────────────────────────────────────────────

def classify_badge(div_node):
    if div_node.attrs.get("style"):
        return {"kind": "arrows"}
    text = inline_to_markdown(div_node)
    if "press-hold" in classes(div_node):
        return {"kind": "pill", "label": text}
    if text.endswith("×"):
        try:
            return {"kind": "count", "n": int(text[:-1])}
        except ValueError:
            pass
    return {"kind": "text", "value": text}


def classify_note(p_node):
    if "warn" in classes(p_node):
        return {"type": "hazard", "text": inline_to_markdown(p_node)}
    svg = find_first(p_node, lambda n: n.tag == "svg")
    span = find_first(p_node, lambda n: n.tag == "span")
    note_type = "warning" if (svg is not None and contains_tag(svg, "line")) else "tip"
    return {"type": note_type, "text": inline_to_markdown(span)}


def parse_bullets(ul_node):
    if ul_node is None:
        return []
    lis = [c for c in ul_node.children if not isinstance(c, str) and c.tag == "li"]
    return [{"id": f"b{i}", "text": inline_to_markdown(li)} for i, li in enumerate(lis, start=1)]


def parse_press(press_list_node):
    if press_list_node is None:
        return []
    rows = [c for c in press_list_node.children if not isinstance(c, str) and "press-row" in classes(c)]
    out = []
    for i, row in enumerate(rows, start=1):
        badge_div = find_first(row, lambda n: n.tag == "div" and "press-badge" in classes(n))
        action_span = find_first(row, lambda n: n.tag == "span" and "press-action" in classes(n))
        sub_span = find_first(row, lambda n: n.tag == "span" and "press-sub" in classes(n))
        out.append({
            "id": f"p{i}",
            "badge": classify_badge(badge_div),
            "action": inline_to_markdown(action_span),
            "sub": inline_to_markdown(sub_span) if sub_span is not None else None,
        })
    return out


def parse_step_body(body):
    """Parse the title/bullets/press/note/helpWidget out of a step-body-shaped node —
    reused as-is for a data-i18n-zone="stepN_body" fragment, which has the same shape
    minus the step-img-wrap (a synthetic root works fine since lookups are recursive)."""
    h3 = find_first(body, lambda n: n.tag == "h3")
    title = inline_to_markdown(h3)

    do_ul = find_first(body, lambda n: n.tag == "ul" and "do" in classes(n))
    press_list = find_first(body, lambda n: n.tag == "div" and "press-list" in classes(n))
    help_widget_node = find_first(body, lambda n: n.tag == "details" and "note-help" in classes(n))

    note = None
    if help_widget_node is None:
        note_p = find_first(body, lambda n: n.tag == "p" and ("note" in classes(n) or "warn" in classes(n)))
        if note_p is not None:
            note = classify_note(note_p)

    return {
        "title": title,
        "bullets": parse_bullets(do_ul),
        "press": parse_press(press_list),
        "note": note,
        "helpWidget": help_widget_node is not None,
    }


def parse_step(li):
    wrap = find_first(li, lambda n: n.tag == "div" and "step-img-wrap" in classes(n))
    is_stack = "step-img-stack" in classes(wrap)
    imgs = find_all(wrap, lambda n: n.tag == "img")

    image = img_token(imgs[0].attrs.get("src", ""))
    image_alt = htmllib.unescape(imgs[0].attrs.get("alt", ""))
    image2 = image2_alt = None
    if is_stack and len(imgs) > 1:
        image2 = img_token(imgs[1].attrs.get("src", ""))
        image2_alt = htmllib.unescape(imgs[1].attrs.get("alt", ""))

    body = find_first(li, lambda n: n.tag == "div" and "step-body" in classes(n))
    parsed = parse_step_body(body)

    return {
        "id": slugify(parsed["title"]),
        "title": parsed["title"],
        "image": image,
        "imageAlt": image_alt,
        "image2": image2,
        "image2Alt": image2_alt,
        "bullets": parsed["bullets"],
        "press": parsed["press"],
        "note": parsed["note"],
        "helpWidget": parsed["helpWidget"],
    }


def parse_attachments(attach_ul):
    items = [c for c in attach_ul.children if not isinstance(c, str) and c.tag == "li"]
    out = []
    for li in items:
        wrap = find_first(li, lambda n: n.tag == "div" and "step-img-wrap" in classes(n))
        img = find_first(wrap, lambda n: n.tag == "img")
        h3 = find_first(li, lambda n: n.tag == "h3" and "attach-name" in classes(n))
        title = inline_to_markdown(h3)
        do_ul = find_first(li, lambda n: n.tag == "ul" and "do" in classes(n))
        out.append({
            "id": slugify(title),
            "title": title,
            "image": img_token(img.attrs.get("src", "")),
            "imageAlt": htmllib.unescape(img.attrs.get("alt", "")),
            "bullets": parse_bullets(do_ul),
        })
    return out


def parse_specs(table_node):
    rows = find_all(table_node, lambda n: n.tag == "tr")
    out, seen = [], {}
    for row in rows:
        th = find_first(row, lambda n: n.tag == "th")
        td = find_first(row, lambda n: n.tag == "td")
        label = inline_to_markdown(th)
        value = inline_to_markdown(td)
        base = slugify(label)
        seen[base] = seen.get(base, 0) + 1
        sid = base if seen[base] == 1 else f"{base}-{seen[base]}"
        out.append({"id": sid, "label": label, "value": value})
    return out


def parse_faq(faq_div):
    items = [c for c in faq_div.children if not isinstance(c, str) and c.tag == "details"]
    out = []
    for i, d in enumerate(items, start=1):
        summary = find_first(d, lambda n: n.tag == "summary")
        p = find_first(d, lambda n: n.tag == "p")
        out.append({"id": f"f{i}", "question": inline_to_markdown(summary), "answer": inline_to_markdown(p)})
    return out


def parse_videos(vids_div):
    btns = [c for c in vids_div.children if not isinstance(c, str) and c.tag == "button"]
    out = []
    for i, b in enumerate(btns, start=1):
        h3 = find_first(b, lambda n: n.tag == "h3")
        img = find_first(b, lambda n: n.tag == "img")
        vimeo_hash = b.attrs.get("data-vimeo-hash") or b.attrs.get("data-vimeo-h") or b.attrs.get("data-hash")
        out.append({
            "id": f"v{i}",
            "vimeoId": b.attrs.get("data-vimeo", ""),
            "vimeoHash": vimeo_hash,
            "title": inline_to_markdown(h3),
            "thumb": img_token(img.attrs.get("src", "")),
        })
    return out


def extract_product(html_text):
    parser = TreeParser()
    parser.feed(html_text)
    root = parser.root
    content = {"steps": [], "attachments": [], "specs": [], "faq": [], "videos": []}

    ol = find_first(root, lambda n: n.tag == "ol" and "steps" in classes(n))
    if ol is not None:
        lis = [c for c in ol.children if not isinstance(c, str) and c.tag == "li"]
        content["steps"] = [parse_step(li) for li in lis]

    attach_ul = find_first(root, lambda n: n.tag == "ul" and "attach-list" in classes(n))
    if attach_ul is not None:
        content["attachments"] = parse_attachments(attach_ul)

    specs_table = find_first(root, lambda n: n.tag == "table" and "specs" in classes(n))
    if specs_table is not None:
        content["specs"] = parse_specs(specs_table)

    faq_div = find_first(root, lambda n: n.tag == "div" and classes(n) == ["faq"])
    if faq_div is not None:
        content["faq"] = parse_faq(faq_div)

    vids_div = find_first(root, lambda n: n.tag == "div" and "vids" in classes(n))
    if vids_div is not None:
        content["videos"] = parse_videos(vids_div)

    return content


def main():
    spec = importlib.util.spec_from_file_location("build", ROOT / "build.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    args = sys.argv[1:]
    slugs = args if args else [s for s, sp in mod.PRODUCTS.items() if sp.get("template")]

    CONTENT_DIR.mkdir(exist_ok=True)
    for slug in slugs:
        sp = mod.PRODUCTS[slug]
        html_text = (SRC / sp["template"]).read_text()
        content = extract_product(html_text)
        errors = validate_content(slug, content)
        (CONTENT_DIR / f"{slug}.json").write_text(json.dumps(content, ensure_ascii=False, indent=2) + "\n")
        if errors:
            print(f"{slug}: {len(errors)} validation error(s):")
            for e in errors:
                print(f"  {e}")
        else:
            print(f"{slug}: ok — {len(content['steps'])} steps, {len(content['attachments'])} attachments, "
                  f"{len(content['specs'])} specs, {len(content['faq'])} faq, {len(content['videos'])} videos")


if __name__ == "__main__":
    main()
