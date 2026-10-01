"""Render a product's structured content/<slug>.json into the same HTML shapes the
site's hand-authored templates already use for steps, attachments, specs, FAQ and videos.

Two entry points:
  render_product_body(slug, content)                 -> {"STEPS": ..., "SPECS_ROWS": ..., ...}
      English, still containing unresolved {{img:...}} image tokens for build.py's
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


def no_widow(text, max_pair=12):
    """Join the last two words with a non-breaking space so a line never ends with one
    word stranded on its own. Only for 4+ word copy with a short final pair, so short
    labels can still wrap in narrow columns."""
    words = text.split(" ")
    if len(words) >= 4 and len(words[-2].strip("*")) + len(words[-1].strip("*")) <= max_pair:
        return " ".join(words[:-2]) + " " + words[-2] + "\u00a0" + words[-1]
    return text


NBSP = "\u00a0"
_UNIT_RE = re.compile(
    r"(\d)\s+(?=(?:g|mm|cm|V|mAh|°F|°C|min|minutes?|seconds?|sec|s|hours?|h|Sek\.?|Sekunden|Minuten|"
    r"Stunden?|segundos?|minutos?|horas?|secondi|minuti|ore|secondes|heures?|mois|jours?|días|dias|"
    r"giorni|Tage|Monate|meses|mesi|ans?|años|anos|anni|Jahre?|veces|vezes|volte|fois|mal|times|"
    r"sekunder|sekundach|minutach|godzinach|sekundy?|sekundę|minuter|minutter|minuty|minutę|minut|timmar|timme|timer|time|godzin[yę]?|"
    r"månader|måneder|miesięcy|miesiące|dagar|dage|dni|år|lat|lata|gånger|gange|razy|×)(?![\w]))")
_SEP_RE = re.compile(r" ([/=→·])([ \u00a0])")
_NUMHY_RE = re.compile(r"(\d[a-zA-Z]{0,2})-(?=\w)")
_NAMES = ("G Pen", "Micro II", "Dash II", "Micro+", "510 Original", "Rig Adapter")


def keep_together(text):
    """Non-breaking spaces where a line break would strand half of a unit: a number and its
    unit ("5 seconds", "3,8 V"), the product names, and the separators that read as part of
    the next item ("/ 302°F", "= decrease", "→ 3.8V", "· Haptics")."""
    text = _UNIT_RE.sub(lambda m: m.group(1) + NBSP, text)
    for name in _NAMES:
        if " " in name:
            text = text.replace(name, name.replace(" ", NBSP))
    # a separator stays with the item it introduces (no_widow may already have joined it
    # to the next word with a non-breaking space, hence [ \u00a0]); "=" binds both sides
    text = _SEP_RE.sub(lambda m: NBSP + m.group(1) + (NBSP if m.group(1) == "=" else m.group(2)), text)
    # "+ and −" (a button pair, in any language: "+ und −", "+ et −") stays on one line
    text = re.sub(r"\+ (\S{1,4}) −", "+" + NBSP + r"\1" + NBSP + "−", text)
    # a dash never starts a line
    text = text.replace(" — ", NBSP + "— ").replace(" – ", NBSP + "– ")
    # hyphens inside number compounds and product codes never break: USB-C, 510-Gewinde,
    # 20-Sekunden, 5er-Pack, 1-Year
    text = text.replace("USB-C", "USB\u2011C")
    return _NUMHY_RE.sub(lambda m: m.group(1) + "\u2011", text)


_NOHY_RE = re.compile(r"(Rig\u00a0Adapter|Sidecar|Showerhead|Hydout|Micro\u00a0II|Dash\u00a0II|Dash\+|G\u00a0Pen)")


def render_inline(text, quote=False):
    """HTML-escape plain text, then turn **bold** markers into <b> tags."""
    escaped = htmllib.escape(keep_together(text), quote=quote)
    if not quote:   # not inside an attribute
        escaped = _NOHY_RE.sub(r'<span class="nohy">\1</span>', escaped)
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
        items.append(_fill(_partial("bullet-item"), TEXT=render_inline(no_widow(text))))
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
            sub_line = f'                <span class="press-sub">{render_inline(no_widow(sub_text, 14))}</span>\n'
        rows.append(_fill(
            _partial("press-row"),
            BADGE_CLASS=badge_class, BADGE_STYLE=badge_style, BADGE_CONTENT=badge_content,
            ACTION=render_inline(no_widow(action, 14)), SUB_LINE=sub_line,
        ))
    return _fill(_partial("press-list"), ROWS="\n".join(rows))


def render_note(note, id_prefix, leaf_lookup):
    if note is None:
        return ""
    text = _leaf(leaf_lookup, f"{id_prefix}.note", note["text"])
    rendered = render_inline(no_widow(text))
    if note["type"] == "hazard":
        return _fill(_partial("note-hazard"), TEXT=rendered)
    icon = NOTE_ICON_TIP if note["type"] == "tip" else NOTE_ICON_WARNING
    return _fill(_partial("note"), ICON=icon, TEXT=rendered)


def img_ref(filename):
    """Placeholder build.py resolves per output: img/<basename> (hosted) or a data: URI
    (offline). filename is relative to src/ — e.g. "dash-ii-step-01-charge.jpg" or a
    newly added image like "images/new-step.jpg"."""
    return "{{img:%s}}" % filename


IMG_REF_RE = re.compile(r"\{\{img:([^}]+)\}\}")


def _img_tag(token, alt, indent, num=99, alt_key=None):
    # Steps 1 and 2 are on screen when a phone opens the page (step 2's photo is usually the
    # largest paint), so they load right away; step 1 gets download priority. The rest stay lazy.
    load = ' fetchpriority="high"' if num == 1 else ('' if num == 2 else ' loading="lazy"')
    # alt_key: the i18n key that translates the alt text (screen readers read it)
    tr = f' data-i18n-attr="alt:{alt_key}"' if alt_key else ""
    return f'{indent}<div class="step-circle"><img src="{img_ref(token)}" alt="{alt}"{tr}{load}></div>'


def render_step_image(step, num):
    token = step["image"]
    alt = htmllib.escape(step["imageAlt"], quote=True)
    if step.get("image2"):
        token2 = step["image2"]
        alt2 = htmllib.escape(step["image2Alt"], quote=True)
        return (
            '        <div class="step-img-wrap step-img-stack">\n'
            '          <div class="step-img-main">\n'
            f'{_img_tag(token, alt, "            ", num, f"step{num}_alt")}\n'
            f'            <div class="num">{num}</div>\n'
            '          </div>\n'
            f'{_img_tag(token2, alt2, "          ", alt_key=f"step{num}_alt2")}\n'
            '        </div>'
        )
    return (
        '        <div class="step-img-wrap">\n'
        f'{_img_tag(token, alt, "          ", num, f"step{num}_alt")}\n'
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
        NUM=str(num),
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


def render_attach_item(item, num, leaf_lookup):
    return _fill(
        _partial("attach-item"),
        IMG=img_ref(item["image"]),
        IMG_ALT=htmllib.escape(item["imageAlt"], quote=True),
        ZONE_KEY=f"attach{num}_body",
        ALT_KEY=f"attach{num}_alt",
        BODY=_attach_zone_inner(item, leaf_lookup),
    )


def _attach_zone_inner(item, leaf_lookup):
    """The translatable inner HTML of an attachment's text column: <h3> + its bullets.
    The image sits outside the zone, so no {{img:}} token ever lands in a translation."""
    id_prefix = f"attach.{item['id']}"
    title = _leaf(leaf_lookup, f"{id_prefix}.title", item["title"])
    do_block = render_bullets(item.get("bullets", []), id_prefix, leaf_lookup)
    return "\n".join(x for x in (f'          <h3 class="attach-name">{render_inline(title)}</h3>', do_block) if x)


def render_spec_row(spec, leaf_lookup):
    id_prefix = f"specs.{spec['id']}"
    label = _leaf(leaf_lookup, f"{id_prefix}.label", spec["label"])
    value = _leaf(leaf_lookup, f"{id_prefix}.value", spec["value"])
    return _fill(_partial("spec-row"), LABEL=render_inline(label), VALUE=render_inline(value))


def render_faq_item(item, leaf_lookup, num=1):
    id_prefix = f"faq.{item['id']}"
    q = _leaf(leaf_lookup, f"{id_prefix}.question", item["question"])
    a = _leaf(leaf_lookup, f"{id_prefix}.answer", item["answer"])
    # id="faq-N": support can link straight to one answer (/micro-ii/#faq-2 opens it)
    return _fill(_partial("faq-item"), NUM=str(num), QUESTION=render_inline(q), ANSWER=render_inline(no_widow(a)))


def _video_card(video, num, leaf_lookup):
    id_prefix = f"video.{video['id']}"
    title = _leaf(leaf_lookup, f"{id_prefix}.title", video["title"])
    hash_attr = ""
    if video.get("vimeoHash"):
        hash_attr = f' data-vimeo-hash="{video["vimeoHash"]}"'
    card = _fill(
        _partial("video-card"),
        VIMEO_ID=video["vimeoId"], HASH_ATTR=hash_attr,
        THUMB=img_ref(video["thumb"]),
        TITLE=render_inline(title, quote=True),
        TITLE_KEY=f"vid{num}_title",
    )
    return card, title


def _render_body(content, leaf_lookup, need_help_text=NEED_HELP_TEXT_EN):
    steps = content.get("steps", [])
    steps_html = [render_step(s, i, leaf_lookup, need_help_text) for i, s in enumerate(steps, start=1)]
    attach_html = [render_attach_item(a, i, leaf_lookup) for i, a in enumerate(content.get("attachments", []), start=1)]
    specs_html = [render_spec_row(s, leaf_lookup) for s in content.get("specs", [])]
    faq_html = [render_faq_item(f, leaf_lookup, i) for i, f in enumerate(content.get("faq", []), start=1)]

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
    """English render, still containing unresolved {{img:...}} image tokens."""
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
        if step.get("imageAlt"):
            leaves[f"{prefix}.imageAlt"] = step["imageAlt"]
        if step.get("image2Alt"):
            leaves[f"{prefix}.image2Alt"] = step["image2Alt"]
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
    for a in content.get("attachments", []):
        prefix = f"attach.{a['id']}"
        leaves[f"{prefix}.title"] = a["title"]
        if a.get("imageAlt"):
            leaves[f"{prefix}.imageAlt"] = a["imageAlt"]
        for b in a.get("bullets", []):
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
            flat[f"step{i}_alt"] = _leaf(leaf_lookup, f"step.{step['id']}.imageAlt", step.get("imageAlt", ""))
            if step.get("image2Alt"):
                flat[f"step{i}_alt2"] = _leaf(leaf_lookup, f"step.{step['id']}.image2Alt", step["image2Alt"])
        for i, a in enumerate(content.get("attachments", []), start=1):
            flat[f"attach{i}_body"] = _attach_zone_inner(a, leaf_lookup).strip()
            flat[f"attach{i}_alt"] = _leaf(leaf_lookup, f"attach.{a['id']}.imageAlt", a.get("imageAlt", ""))
        if content.get("specs"):
            flat["specs_body"] = _specs_zone_inner(content["specs"], leaf_lookup)
        if content.get("faq"):
            flat["faq_body"] = body["FAQ_ITEMS"]
        flat.update(body["_video_scalars"])
        out[lang] = flat
    return out
