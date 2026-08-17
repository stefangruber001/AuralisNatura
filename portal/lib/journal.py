"""Impulse — Desiree's editorial channel from the Betriebskonsole into the app.

An article is its OWN object, not a social slot with a destination flag. The two
overlap in content and diverge in almost everything else: a slot is scheduled,
square, 1080×1350 with her typography baked into the canvas, and aimed at
strangers; an article is read, reflowable, has a title and a body, and is aimed
at a named client in her own language. Modelling one as the other would force
every future field on both. So a slot can SEED an article — she writes once —
and the article then has its own life.

Two audiences, and the distinction is load-bearing:

  clients  — visible to signed-in clients only.
  public   — also visible without a login, which is what makes guest mode work.
             The App Store listing points at a login wall today, so a prospect
             who downloads the app can see nothing and converts at zero.

What deliberately does NOT live here:

* Read state. Which article a client opened is an Article 9 inference about her
  health interests, so it stays on her device and is never sent to the server.
* The scope disclaimer. It is appended at render time from the app's own
  localisation, so no console edit can drop it and no stored article can
  contradict it.
"""
from __future__ import annotations

import datetime as dt
import json
import re
import threading
import uuid
from pathlib import Path

from . import cfg

_LOCK = threading.RLock()
LANGS = ("de", "en", "es")
AUDIENCES = ("clients", "public")


def _dir() -> Path:
    # resolved per call: cfg.OUTPUT_DIR is redirected by the test sandbox
    p = cfg.OUTPUT_DIR / "journal"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _path() -> Path:
    return _dir() / "articles.json"


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def load() -> list[dict]:
    p = _path()
    if not p.exists():
        return []
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
        return d.get("articles", []) if isinstance(d, dict) else []
    except Exception:
        return []


def save(articles: list[dict]) -> None:
    with _LOCK:
        tmp = _path().with_suffix(".json.tmp")
        tmp.write_text(json.dumps({"articles": articles}, ensure_ascii=False, indent=2),
                       encoding="utf-8")
        tmp.replace(_path())


# ---------------------------------------------------------------- compliance

# Health-claim language that must not reach a client unreviewed. Mirrors
# social.py's intent, but blocking here rather than warning: a social caption is
# read by strangers, an article by someone who has paid for guidance.
_CLAIM = re.compile(
    r"\b(heilt|heilen|heilung|cures?|curar|cura|diagnostiz\w*|diagnos(?:e|es|is|ing)\b"
    r"|therapiert|behandelt|treats?|garantiert|guaranteed|garantiza\w*)\b", re.I)

# The refer-out sentence the guardrails REQUIRE contains "Diagnose". A bare
# substring match would block the very safety copy it exists to protect, and
# teach her to delete the word from it. These contexts are always allowed.
_SAFE = re.compile(
    r"(keine?\s+(?:medizinische\s+)?diagnos|nicht\s+diagnos|ersetzt\s+kein"
    r"|falls\s+du\s+eine\s+diagnose|wenn\s+du\s+eine\s+diagnose"
    r"|no\s+diagnos|not\s+a\s+diagnos|does\s+not\s+replace|if\s+you\s+have\s+a\s+diagnos"
    r"|no\s+sustituye|sin\s+diagnos|si\s+tienes\s+un\s+diagn)", re.I)


def lint(text: str) -> list[str]:
    """Claim terms found outside a safe context. Empty list means publishable."""
    hits: list[str] = []
    for m in _CLAIM.finditer(text or ""):
        window = (text[max(0, m.start() - 60):m.end() + 60])
        if _SAFE.search(window):
            continue
        hits.append(m.group(0))
    return sorted(set(hits))


def lint_article(art: dict) -> dict:
    """{lang: [terms]} for every language that has copy."""
    out = {}
    for lang in LANGS:
        body = art.get("body", {}).get(lang, "") or ""
        title = art.get("title", {}).get(lang, "") or ""
        hits = lint(title + "\n" + body)
        if hits:
            out[lang] = hits
    return out


# ---------------------------------------------------------------- authoring

def new_article(title: dict | None = None, body: dict | None = None,
                audience: str = "clients", cover: str = "",
                cta: dict | None = None, source_slot: str = "") -> dict:
    return {
        "id": "imp-" + uuid.uuid4().hex[:10],
        "created": _now(),
        "published_at": "",
        "status": "draft",
        "audience": audience if audience in AUDIENCES else "clients",
        "title": {k: (title or {}).get(k, "") for k in LANGS},
        "body": {k: (body or {}).get(k, "") for k in LANGS},
        "cover": cover,                 # asset name, served uncropped or not at all
        "cta": cta or {},               # {"kind": "book"|"link"|"", "url": "", "label": {}}
        "source_slot": source_slot,     # the social slot this was seeded from
        "override": {},                 # {"reason": str, "at": iso} when lint was overridden
    }


def from_slot(slot: dict, audience: str = "clients") -> dict:
    """Seed an article from a social slot so she writes once.

    Takes the captions she already wrote in all three languages and the hook as
    a working title. The rendered image is NOT carried over as a cover by
    default: her typography is baked into the 1080×1350 canvas, so a feed that
    crops it cuts her own words. She attaches a cover deliberately or not at all.
    """
    caps = {lang: (slot.get(f"caption_{lang}") or "").strip() for lang in LANGS}
    hook = (slot.get("hook") or "").strip()
    title = {lang: (hook if caps.get(lang) else "") for lang in LANGS}
    return new_article(title=title, body=caps, audience=audience,
                       source_slot=slot.get("id", ""))


def upsert(art: dict) -> dict:
    arts = load()
    for i, a in enumerate(arts):
        if a.get("id") == art.get("id"):
            arts[i] = art
            break
    else:
        arts.append(art)
    save(arts)
    return art


def get(aid: str) -> dict | None:
    return next((a for a in load() if a.get("id") == aid), None)


def delete(aid: str) -> bool:
    arts = load()
    keep = [a for a in arts if a.get("id") != aid]
    if len(keep) == len(arts):
        return False
    save(keep)
    return True


def publish(aid: str, override_reason: str = "") -> tuple[dict | None, dict]:
    """Publish, unless the claim lint objects.

    Blocking by default. An override is possible but must be given a reason,
    which is stored on the article — she is the compliance owner and the sole
    reviewer, so the answer to a false positive is an audit trail, not a wall
    she learns to defeat by rewording safety copy.
    """
    art = get(aid)
    if art is None:
        return None, {"error": "not found"}
    problems = lint_article(art)
    if problems and not override_reason.strip():
        return None, {"error": "claim_language", "terms": problems}
    if not any((art.get("body", {}).get(l) or "").strip() for l in LANGS):
        return None, {"error": "empty"}
    if problems:
        art["override"] = {"reason": override_reason.strip(), "at": _now(),
                           "terms": problems}
    art["status"] = "published"
    art["published_at"] = art.get("published_at") or _now()
    upsert(art)
    return art, {}


def unpublish(aid: str) -> dict | None:
    art = get(aid)
    if art is None:
        return None
    art["status"] = "draft"
    upsert(art)
    return art


# ---------------------------------------------------------------- reading

FEED_CAP = 30            # a finite feed with an end, not an infinite scroll


def feed(language: str = "de", public_only: bool = False) -> list[dict]:
    """Published articles, newest first, in one language.

    public_only is guest mode: no login, so only what she marked public.
    Returns a flattened per-language shape — the app never sees the other two
    languages, and never sees the override note or the source slot.
    """
    lang = language if language in LANGS else "de"
    out = []
    for a in load():
        if a.get("status") != "published":
            continue
        if public_only and a.get("audience") != "public":
            continue
        title = (a.get("title", {}).get(lang) or "").strip()
        body = (a.get("body", {}).get(lang) or "").strip()
        if not body:
            continue                     # not written in this language yet
        out.append({
            "id": a.get("id", ""),
            "title": title,
            "body": body,
            "published_at": a.get("published_at", ""),
            "cover": a.get("cover", "") or "",
            "cta": {k: v for k, v in (a.get("cta") or {}).items() if k != "label"} | (
                {"label": (a.get("cta") or {}).get("label", {}).get(lang, "")}
                if (a.get("cta") or {}).get("label") else {}),
            "audience": a.get("audience", "clients"),
        })
    out.sort(key=lambda x: x.get("published_at", ""), reverse=True)
    return out[:FEED_CAP]
