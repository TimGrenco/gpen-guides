"""Render a product's structured content/<slug>.json into the same HTML shapes the
site's hand-authored templates already use for steps, attachments, specs, FAQ and videos.

Two entry points:
  render_product_body(slug, content)                 -> {"STEPS": ..., "SPECS_ROWS": ..., ...}
      English, still containing unresolved {{STEP1}}-style image tokens for build.py's
      existing image-substitution loop to resolve.
  compose_translations(slug, content, cache)          -> {"EN": {...}, "ES": {...}, ...}
      The old zone-shaped dict inject_i18n() already expects (data-i18n-zone keys map to
      inner HTML, scalar data-i18n keys map to plain text) — re-rendered per language with
      each leaf's cached translation substituted in by its stable ID, English fallback for
      anything not yet translated.
"""

import html as htmllib
import pathlib
import re

PARTIALS_DIR = pathlib.Path(__file__).parent / "partials"
_partial_cache = {}


def _partial(name):
    if name not in _partial_cache:
        _partial_cache[name] = (PARTIALS_DIR / f"{name}.html").read_text()
    return _partial_cache[name]


def _fill(template, **tokens):
    out = template
    for k, v in tokens.items():
        out = out.replace("{{%s}}" % k, v)
    return out


_BOLD_RE = re.compile(r'\*\*(.+?)\*\*')


def render_inline(text, quote=False):
    """HTML-escape plain text, then turn **bold** markers into <b> tags."""
    escaped = htmllib.escape(text, quote=quote)
    return _BOLD_RE.sub(lambda m: f"<b>{m.group(1)}</b>", escaped)


NOTE_ICON_TIP = (
    '<svg class="note-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
    'stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
    '<path d="M9 18h6"/><path d="M10 22h4"/>'
    '<path d="M12 2a7 7 0 0 0-4 12.7c.6.5 1 1.2 1 2.1v.2h6v-.2c0-.9.4-1.6 1-2.1A7 7 0 0 0 12 2z"/></svg>'
)
NOTE_ICON_WARNING = (
    '<svg class="note-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
    'stroke-width="1.8" stroke-linecap="round" aria-hidden="true">'
    '<circle cx="12" cy="12" r="9"/><line x1="5.5" y1="18.5" x2="18.5" y2="5.5"/></svg>'
)


def render_badge(badge):
    """Return (css_class, style_attr, inner_html) for a press-badge."""
    kind = badge["kind"]
    if kind == "count":
        return "press-badge", "", f'{badge["n"]}×'
    if kind == "pill":
        return "press-badge press-hold", "", htmllib.escape(badge["label"], quote=False)
    if kind == "text":
        return "press-badge", "", htmllib.escape(badge["value"], quote=False)
    if kind == "arrows":
        return ("press-badge",
                ' style="display:flex;align-items:center;justify-content:center;gap:3px"',
                "<span>◀</span><span>▶</span>")
    raise ValueError(f"unknown badge kind {kind!r}")


def _leaf(leaf_lookup, leaf_id, fallback_text):
    if leaf_lookup is None:
        return fallback_text
    return leaf_lookup.get(leaf_id, fallback_text)


def render_bullets(bullets, id_prefix, leaf_lookup):
    if not bullets:
        return ""
    items = []
    for b in bullets:
        text = _leaf(leaf_lookup, f"{id_prefix}.bullet.{b['id']}", b["text"])
        items.append(_fill(_partial("bullet-item"), TEXT=render_inline(text)))
    return _fill(_partial("do-list"), ITEMS="\n".join(items))


def render_press(press, id_prefix, leaf_lookup):
    if not press:
        return ""
    rows = []
    for p in press:
        badge = p["badge"]
        if badge["kind"] == "pill":
            # pill labels are real words in some products ("draw") and got translated
            # historically, even though others ("Hold") were pinned by the translator's
            # own preserve-list — treat all of them as a translatable leaf uniformly.
            label = _leaf(leaf_lookup, f"{id_prefix}.press.{p['id']}.badge", badge["label"])
            badge = dict(badge, label=label)
        badge_class, badge_style, badge_content = render_badge(badge)
        action = _leaf(leaf_lookup, f"{id_prefix}.press.{p['id']}.action", p["action"])
        sub = p.get("sub")
        sub_line = ""
        if sub is not None:
            sub_text = _leaf(leaf_lookup, f"{id_prefix}.press.{p['id']}.sub", sub)
            sub_line = f'                <span class="press-sub">{render_inline(sub_text)}</span>\n'
        rows.append(_fill(
            _partial("press-row"),
            BADGE_CLASS=badge_class, BADGE_STYLE=badge_style, BADGE_CONTENT=badge_content,
            ACTION=render_inline(action), SUB_LINE=sub_line,
        ))
    return _fill(_partial("press-list"), ROWS="\n".join(rows))


def render_note(note, id_prefix, leaf_lookup):
    if note is None:
        return ""
    text = _leaf(leaf_lookup, f"{id_prefix}.note", note["text"])
    rendered = render_inline(text)
    if note["type"] == "hazard":
        return _fill(_partial("note-hazard"), TEXT=rendered)
    icon = NOTE_ICON_TIP if note["type"] == "tip" else NOTE_ICON_WARNING
    return _fill(_partial("note"), ICON=icon, TEXT=rendered)


def _img_tag(token, alt, indent):
    return f'{indent}<div class="step-circle"><img src="{{{{{token}}}}}" alt="{alt}" loading="lazy"></div>'


def render_step_image(step, num):
    token = step["image"]
    alt = htmllib.escape(step["imageAlt"], quote=True)
    if step.get("image2"):
        token2 = step["image2"]
        alt2 = htmllib.escape(step["image2Alt"], quote=True)
        return (
            '        <div class="step-img-wrap step-img-stack">\n'
            '          <div class="step-img-main">\n'
            f'{_img_tag(token, alt, "            ")}\n'
            f'            <div class="num">{num}</div>\n'
            '          </div>\n'
            f'{_img_tag(token2, alt2, "          ")}\n'
            '        </div>'
        )
    return (
        '        <div class="step-img-wrap">\n'
        f'{_img_tag(token, alt, "          ")}\n'
        f'          <div class="num">{num}</div>\n'
        '        </div>'
    )


NEED_HELP_TEXT_EN = "Need help?"


def _step_body_blocks(step, id_prefix, leaf_lookup, need_help_text=NEED_HELP_TEXT_EN):
    """Return the list of rendered block strings that follow <h3> inside a step body
    (do-list / press-list / note-or-help), in document order, empty blocks omitted."""
    blocks = []
    do_block = render_bullets(step.get("bullets", []), id_prefix, leaf_lookup)
    if do_block:
        blocks.append(do_block)
    press_block = render_press(step.get("press", []), id_prefix, leaf_lookup)
    if press_block:
        blocks.append(press_block)
    if step.get("helpWidget"):
        # note-help is a static partial (not per-product content), but it contains the
        # need_help_inline SCALAR string — since the zone's innerHTML overwrite runs
        # AFTER the scalar data-i18n pass at runtime (i18n-runtime.js), a translated
        # page must have that translation already baked into the zone HTML itself, or
        # switching language would revert this one button back to English.
        blocks.append(_fill(_partial("note-help"), NEED_HELP_TEXT=need_help_text).rstrip("\n"))
    else:
        note_block = render_note(step.get("note"), id_prefix, leaf_lookup)
        if note_block:
            blocks.append(note_block)
    return blocks


def render_step(step, num, leaf_lookup, need_help_text=NEED_HELP_TEXT_EN):
    id_prefix = f"step.{step['id']}"
    title = _leaf(leaf_lookup, f"{id_prefix}.title", step["title"])
    blocks = _step_body_blocks(step, id_prefix, leaf_lookup, need_help_text)
    return _fill(
        _partial("step"),
        IMG_BLOCK=render_step_image(step, num),
        ZONE_KEY=f"step{num}_body",
        TITLE=render_inline(title),
        BODY_EXTRA="\n".join(blocks),
    )


def _step_zone_inner(step, num, leaf_lookup, need_help_text=NEED_HELP_TEXT_EN):
    """The translatable inner HTML of a step's data-i18n-zone div: <h3> + its blocks."""
    id_prefix = f"step.{step['id']}"
    title = _leaf(leaf_lookup, f"{id_prefix}.title", step["title"])
    lines = [f'          <h3>{render_inline(title)}</h3>']
    lines.extend(_step_body_blocks(step, id_prefix, leaf_lookup, need_help_text))
    return "\n".join(lines).strip()


def render_attach_item(item, leaf_lookup):
    id_prefix = f"attach.{item['id']}"
    title = _leaf(leaf_lookup, f"{id_prefix}.title", item["title"])
    do_block = render_bullets(item.get("bullets", []), id_prefix, leaf_lookup)
    return _fill(
        _partial("attach-item"),
        IMG="{{%s}}" % item["image"],
        IMG_ALT=htmllib.escape(item["imageAlt"], quote=True),
        TITLE=render_inline(title),
        DO_BLOCK=do_block,
    )


def render_spec_row(spec, leaf_lookup):
    id_prefix = f"specs.{spec['id']}"
    label = _leaf(leaf_lookup, f"{id_prefix}.label", spec["label"])
    value = _leaf(leaf_lookup, f"{id_prefix}.value", spec["value"])
    return _fill(_partial("spec-row"), LABEL=render_inline(label), VALUE=render_inline(value))


def render_faq_item(item, leaf_lookup):
    id_prefix = f"faq.{item['id']}"
    q = _leaf(leaf_lookup, f"{id_prefix}.question", item["question"])
    a = _leaf(leaf_lookup, f"{id_prefix}.answer", item["answer"])
    return _fill(_partial("faq-item"), QUESTION=render_inline(q), ANSWER=render_inline(a))


def _video_card(video, num, leaf_lookup):
    id_prefix = f"video.{video['id']}"
    title = _leaf(leaf_lookup, f"{id_prefix}.title", video["title"])
    hash_attr = ""
    if video.get("vimeoHash"):
        hash_attr = f' data-vimeo-hash="{video["vimeoHash"]}"'
    card = _fill(
        _partial("video-card"),
        VIMEO_ID=video["vimeoId"], HASH_ATTR=hash_attr,
        THUMB="{{%s}}" % video["thumb"],
        TITLE=render_inline(title, quote=True),
        TITLE_KEY=f"vid{num}_title",
    )
    return card, title


def _render_body(content, leaf_lookup, need_help_text=NEED_HELP_TEXT_EN):
    steps = content.get("steps", [])
    steps_html = [render_step(s, i, leaf_lookup, need_help_text) for i, s in enumerate(steps, start=1)]
    attach_html = [render_attach_item(a, leaf_lookup) for a in content.get("attachments", [])]
    specs_html = [render_spec_row(s, leaf_lookup) for s in content.get("specs", [])]
    faq_html = [render_faq_item(f, leaf_lookup) for f in content.get("faq", [])]

    video_cards, video_scalars = [], {}
    for i, v in enumerate(content.get("videos", []), start=1):
        card, title = _video_card(v, i, leaf_lookup)
        video_cards.append(card)
        video_scalars[f"vid{i}_title"] = title

    result = {
        "STEPS": ("\n" + "\n\n".join(steps_html) + "\n") if steps_html else "",
        "ATTACHMENTS": "\n".join(attach_html),
        "SPECS_ROWS": "\n".join(specs_html),
        "FAQ_ITEMS": "\n".join(faq_html),
        "VIDEOS": "\n".join(video_cards),
        "_video_scalars": video_scalars,
    }
    return result


def render_product_body(slug, content):
    """English render, still containing unresolved {{STEP1}}-style image tokens."""
    return _render_body(content, leaf_lookup=None)


def _specs_zone_inner(specs, leaf_lookup):
    """The data-i18n-zone="specs_body" element sits one level above the rows (it wraps
    the table-scroll/table/tbody too), so its translated innerHTML must include that
    wrapper — not just the <tr> rows — or a language switch would leave bare rows with
    no table around them."""
    rows = "\n".join(render_spec_row(s, leaf_lookup) for s in specs)
    return (
        '<div class="table-scroll">\n'
        '          <table class="specs">\n'
        '            <tbody>\n'
        f'{rows}\n'
        '            </tbody>\n'
        '          </table>\n'
        '        </div>'
    )


def extract_content_leaves(content):
    """Return {stable_id: english_text} for every translatable leaf in content.
    Used by gen_i18n.py to build the translation prompt and diff the cache per-leaf.
    """
    leaves = {}
    for step in content.get("steps", []):
        prefix = f"step.{step['id']}"
        leaves[f"{prefix}.title"] = step["title"]
        for b in step.get("bullets", []):
            leaves[f"{prefix}.bullet.{b['id']}"] = b["text"]
        for p in step.get("press", []):
            leaves[f"{prefix}.press.{p['id']}.action"] = p["action"]
            if p.get("sub") is not None:
                leaves[f"{prefix}.press.{p['id']}.sub"] = p["sub"]
            if p["badge"]["kind"] == "pill":
                leaves[f"{prefix}.press.{p['id']}.badge"] = p["badge"]["label"]
        if step.get("note"):
            leaves[f"{prefix}.note"] = step["note"]["text"]
    for item in content.get("attachments", []):
        prefix = f"attach.{item['id']}"
        leaves[f"{prefix}.title"] = item["title"]
        for b in item.get("bullets", []):
            leaves[f"{prefix}.bullet.{b['id']}"] = b["text"]
    for spec in content.get("specs", []):
        prefix = f"specs.{spec['id']}"
        leaves[f"{prefix}.label"] = spec["label"]
        leaves[f"{prefix}.value"] = spec["value"]
    for item in content.get("faq", []):
        prefix = f"faq.{item['id']}"
        leaves[f"{prefix}.question"] = item["question"]
        leaves[f"{prefix}.answer"] = item["answer"]
    for v in content.get("videos", []):
        leaves[f"video.{v['id']}.title"] = v["title"]
    return leaves


def compose_translations(slug, content, cache):
    """cache: {lang: {"shell": {key: str}, "content": {stable_id: str}}} loaded from
    i18n/<slug>.json. Returns the flat {lang: {key: str}} dict inject_i18n() expects —
    zone keys (step1_body, specs_body, faq_body) map to inner HTML, scalar keys map to
    plain text — by re-rendering with each language's leaf translations substituted in,
    English fallback for anything not yet translated.
    """
    out = {}
    steps = content.get("steps", [])
    for lang, bucket in cache.items():
        leaf_lookup = None if lang == "EN" else bucket.get("content", {})
        shell = bucket.get("shell", {})
        need_help_text = shell.get("need_help_inline", NEED_HELP_TEXT_EN)
        body = _render_body(content, leaf_lookup, need_help_text)
        flat = dict(shell)
        for i, step in enumerate(steps, start=1):
            flat[f"step{i}_body"] = _step_zone_inner(step, i, leaf_lookup, need_help_text)
        if content.get("specs"):
            flat["specs_body"] = _specs_zone_inner(content["specs"], leaf_lookup)
        if content.get("faq"):
            flat["faq_body"] = body["FAQ_ITEMS"]
        flat.update(body["_video_scalars"])
        out[lang] = flat
    return out
