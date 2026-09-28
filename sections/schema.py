"""Validate content/<slug>.json — the structured content that drives a product guide's
steps/attachments/specs/FAQ/videos. Used by the renderer (defensively) and by the
migration scripts (to catch extraction bugs before they reach committed JSON).
"""

BADGE_KINDS = {"count", "pill", "text", "arrows"}
NOTE_TYPES = {"tip", "warning", "hazard"}


def _err(errors, path, msg):
    errors.append(f"{path}: {msg}")


def _require_str(obj, key, path, errors, allow_empty=False):
    v = obj.get(key)
    if not isinstance(v, str) or (not allow_empty and not v):
        _err(errors, path, f"{key} must be a non-empty string")


def _require_id(obj, path, errors, seen_ids):
    id_ = obj.get("id")
    if not id_ or not isinstance(id_, str):
        _err(errors, path, "missing id")
    elif id_ in seen_ids:
        _err(errors, path, f"duplicate id {id_!r}")
    else:
        seen_ids.add(id_)


def _validate_badge(badge, path, errors):
    if not isinstance(badge, dict):
        _err(errors, path, "badge must be an object")
        return
    kind = badge.get("kind")
    if kind not in BADGE_KINDS:
        _err(errors, path, f"kind must be one of {sorted(BADGE_KINDS)}, got {kind!r}")
        return
    if kind == "count" and not isinstance(badge.get("n"), int):
        _err(errors, path, "n must be an int for kind=count")
    if kind == "pill" and not (isinstance(badge.get("label"), str) and badge["label"]):
        _err(errors, path, "label must be a non-empty string for kind=pill")
    if kind == "text" and not (isinstance(badge.get("value"), str) and badge["value"]):
        _err(errors, path, "value must be a non-empty string for kind=text")


def _validate_note(note, path, errors):
    if note is None:
        return
    if not isinstance(note, dict):
        _err(errors, path, "note must be an object or null")
        return
    if note.get("type") not in NOTE_TYPES:
        _err(errors, path, f"type must be one of {sorted(NOTE_TYPES)}, got {note.get('type')!r}")
    _require_str(note, "text", path, errors)


def _validate_bullets(bullets, path, errors, seen_ids):
    if not isinstance(bullets, list):
        _err(errors, path, "bullets must be a list")
        return
    for i, b in enumerate(bullets):
        bpath = f"{path}[{i}]"
        if not isinstance(b, dict):
            _err(errors, bpath, "bullet must be an object")
            continue
        _require_id(b, bpath, errors, seen_ids)
        _require_str(b, "text", bpath, errors)


def _validate_press(press, path, errors, seen_ids):
    if not isinstance(press, list):
        _err(errors, path, "press must be a list")
        return
    for i, p in enumerate(press):
        ppath = f"{path}[{i}]"
        if not isinstance(p, dict):
            _err(errors, ppath, "press row must be an object")
            continue
        _require_id(p, ppath, errors, seen_ids)
        _validate_badge(p.get("badge"), f"{ppath}.badge", errors)
        _require_str(p, "action", ppath, errors)
        sub = p.get("sub")
        if sub is not None and not isinstance(sub, str):
            _err(errors, ppath, "sub must be a string or null")


def _validate_step(step, path, errors, seen_ids):
    if not isinstance(step, dict):
        _err(errors, path, "step must be an object")
        return
    _require_id(step, path, errors, seen_ids)
    _require_str(step, "title", path, errors)
    _require_str(step, "image", path, errors)
    _require_str(step, "imageAlt", path, errors)

    image2 = step.get("image2")
    if image2 is not None and not isinstance(image2, str):
        _err(errors, path, "image2 must be a string or null")
    if image2 and not step.get("image2Alt"):
        _err(errors, path, "image2Alt is required when image2 is set")

    leaf_ids = set()
    _validate_bullets(step.get("bullets", []), f"{path}.bullets", errors, leaf_ids)
    _validate_press(step.get("press", []), f"{path}.press", errors, leaf_ids)
    _validate_note(step.get("note"), f"{path}.note", errors)

    help_widget = step.get("helpWidget", False)
    if not isinstance(help_widget, bool):
        _err(errors, path, "helpWidget must be a boolean")
    if help_widget and step.get("note") is not None:
        _err(errors, path, "note and helpWidget are mutually exclusive")


def _validate_attach(item, path, errors, seen_ids):
    if not isinstance(item, dict):
        _err(errors, path, "attachment must be an object")
        return
    _require_id(item, path, errors, seen_ids)
    _require_str(item, "title", path, errors)
    _require_str(item, "image", path, errors)
    _require_str(item, "imageAlt", path, errors)
    _validate_bullets(item.get("bullets", []), f"{path}.bullets", errors, set())


def _validate_spec(spec, path, errors, seen_ids):
    if not isinstance(spec, dict):
        _err(errors, path, "spec must be an object")
        return
    _require_id(spec, path, errors, seen_ids)
    _require_str(spec, "label", path, errors)
    _require_str(spec, "value", path, errors)


def _validate_faq(item, path, errors, seen_ids):
    if not isinstance(item, dict):
        _err(errors, path, "faq item must be an object")
        return
    _require_id(item, path, errors, seen_ids)
    _require_str(item, "question", path, errors)
    _require_str(item, "answer", path, errors)


def _validate_video(video, path, errors, seen_ids):
    if not isinstance(video, dict):
        _err(errors, path, "video must be an object")
        return
    _require_id(video, path, errors, seen_ids)
    _require_str(video, "vimeoId", path, errors)
    vh = video.get("vimeoHash")
    if vh is not None and not isinstance(vh, str):
        _err(errors, path, "vimeoHash must be a string or null")
    _require_str(video, "title", path, errors)
    _require_str(video, "thumb", path, errors)


def validate_content(slug, content):
    """Return a list of human-readable error strings; empty list means valid."""
    errors = []
    if not isinstance(content, dict):
        return [f"{slug}: content must be an object"]

    ids = {
        "steps": set(), "attachments": set(), "specs": set(),
        "faq": set(), "videos": set(),
    }
    for i, step in enumerate(content.get("steps", [])):
        _validate_step(step, f"{slug}.steps[{i}]", errors, ids["steps"])
    for i, item in enumerate(content.get("attachments", [])):
        _validate_attach(item, f"{slug}.attachments[{i}]", errors, ids["attachments"])
    for i, spec in enumerate(content.get("specs", [])):
        _validate_spec(spec, f"{slug}.specs[{i}]", errors, ids["specs"])
    for i, item in enumerate(content.get("faq", [])):
        _validate_faq(item, f"{slug}.faq[{i}]", errors, ids["faq"])
    for i, video in enumerate(content.get("videos", [])):
        _validate_video(video, f"{slug}.videos[{i}]", errors, ids["videos"])

    return errors
