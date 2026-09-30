"""Clean up content/<slug>.json before it's validated and rendered.

Hand edits often leave blank optional fields as "" (or drop them), and a newly added
list item has no stable ID yet. Normalizing fixes both deterministically, so an
ID is minted once and then written back to the file — it never changes afterwards,
which is what keeps its cached translations attached to it.
"""

import json
import pathlib
import re


def _slug(text):
    return re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower() or "item"


def _str(v):
    return v.strip() if isinstance(v, str) else ("" if v is None else str(v))


def _opt(v):
    s = _str(v)
    return s or None


def _assign_ids(items, base_for):
    """Give every item a unique id. Existing ids win (first occurrence); a missing or
    duplicate id gets base_for(item, n) for the lowest n that isn't taken."""
    taken = set()
    needs = []
    for item in items:
        id_ = _str(item.get("id"))
        if id_ and id_ not in taken:
            item["id"] = id_
            taken.add(id_)
        else:
            needs.append(item)
    for item in needs:
        n = 1
        while True:
            cand = base_for(item, n)
            if cand not in taken:
                break
            n += 1
        item["id"] = cand
        taken.add(cand)


def _numbered(prefix):
    return lambda item, n: f"{prefix}{n}"


def _slugged(field):
    def base(item, n):
        s = _slug(_str(item.get(field)))
        return s if n == 1 else f"{s}-{n}"
    return base


def _bullets(raw):
    out = [{"id": b.get("id"), "text": _str(b.get("text"))} for b in raw or [] if _str(b.get("text"))]
    _assign_ids(out, _numbered("b"))
    return out


def _badge(raw):
    raw = raw or {}
    kind = _str(raw.get("kind")) or "count"
    if kind == "count":
        try:
            return {"kind": "count", "n": int(raw.get("n"))}
        except (TypeError, ValueError):
            return {"kind": "count", "n": raw.get("n")}
    if kind == "pill":
        return {"kind": "pill", "label": _str(raw.get("label"))}
    if kind == "text":
        return {"kind": "text", "value": _str(raw.get("value"))}
    return {"kind": kind}


def _press(raw):
    out = []
    for p in raw or []:
        out.append({
            "id": p.get("id"),
            "badge": _badge(p.get("badge")),
            "action": _str(p.get("action")),
            "sub": _opt(p.get("sub")),
        })
    _assign_ids(out, _numbered("p"))
    return out


def _note(raw):
    if not raw or not _str(raw.get("text")):
        return None
    return {"type": _str(raw.get("type")) or "tip", "text": _str(raw.get("text"))}


def normalize_content(content):
    steps = []
    for s in content.get("steps") or []:
        image2 = _opt(s.get("image2"))
        help_widget = bool(s.get("helpWidget"))
        steps.append({
            "id": s.get("id"),
            "title": _str(s.get("title")),
            "image": _str(s.get("image")),
            "imageAlt": _str(s.get("imageAlt")),
            "image2": image2,
            "image2Alt": _opt(s.get("image2Alt")) if image2 else None,
            "bullets": _bullets(s.get("bullets")),
            "press": _press(s.get("press")),
            "note": None if help_widget else _note(s.get("note")),
            "helpWidget": help_widget,
        })
    _assign_ids(steps, _slugged("title"))

    attachments = []
    for a in content.get("attachments") or []:
        attachments.append({
            "id": a.get("id"),
            "title": _str(a.get("title")),
            "image": _str(a.get("image")),
            "imageAlt": _str(a.get("imageAlt")),
            "bullets": _bullets(a.get("bullets")),
        })
    _assign_ids(attachments, _slugged("title"))

    specs = [{"id": s.get("id"), "label": _str(s.get("label")), "value": _str(s.get("value"))}
             for s in content.get("specs") or []]
    _assign_ids(specs, _slugged("label"))

    faq = [{"id": f.get("id"), "question": _str(f.get("question")), "answer": _str(f.get("answer"))}
           for f in content.get("faq") or []]
    _assign_ids(faq, _numbered("f"))

    videos = [{
        "id": v.get("id"),
        "vimeoId": _str(v.get("vimeoId")),
        "vimeoHash": _opt(v.get("vimeoHash")),
        "title": _str(v.get("title")),
        "thumb": _str(v.get("thumb")),
    } for v in content.get("videos") or []]
    _assign_ids(videos, _numbered("v"))

    return {"steps": steps, "attachments": attachments, "specs": specs, "faq": faq, "videos": videos}


def dump(content):
    return json.dumps(content, ensure_ascii=False, indent=2) + "\n"


def load_normalized(path: pathlib.Path, write_back=True):
    """Load content/<slug>.json, normalize it, and (by default) persist the normalized
    form so any freshly minted IDs stick."""
    raw_text = path.read_text()
    content = normalize_content(json.loads(raw_text))
    if write_back and dump(content) != raw_text:
        path.write_text(dump(content))
    return content
