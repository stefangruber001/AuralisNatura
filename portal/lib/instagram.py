"""Instagram Graph API publishing — approve in the console, the server posts.

Why this design and not "drafts in Meta Business Suite": Meta's API cannot
create drafts in that UI — it can only publish (two-step: create a media
container, then publish it). So the review-and-approve step lives in the
Betriebskonsole, and approval queues the slot for its planned day+time; a
systemd timer walks the queue and publishes. Zero copy-paste, human gate
intact (CLAUDE.md §2.5: nothing reaches a client surface unapproved).

Free: the Graph API costs nothing; the one-time setup (Meta developer app in
dev mode, Instagram Professional account, linked Facebook Page, a long-lived
token) is the founder's ~40 minutes, guided from the tab. Until then
connected() is False and everything stays politely queued.

Media files must be PUBLICLY fetchable by Meta's crawler, so assets are
served through short-lived HMAC-signed URLs on the already-public
api.auralisnatura.com — the token encodes the exact file path and expires;
nothing else in output_docs becomes reachable.

The HTTP layer is injectable (api=) — tests run against a mock, the dry-run
mode logs what WOULD be published without calling Meta at all.
"""
from __future__ import annotations
import datetime as _dt
import json
import time
import urllib.parse
import urllib.request
from pathlib import Path
from zoneinfo import ZoneInfo

from . import auth, cfg
from . import social as _social

GRAPH = "https://graph.facebook.com/v21.0"
_TZ = ZoneInfo("Europe/Madrid")
_DAY_IDX = {d: i for i, d in enumerate(
    ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"])}


# ─────────────────────────────────────────────────────────────── connection ──
def _token() -> str:
    st = _social.state()
    cached = st.get("ig_token") or {}
    if cached.get("token"):
        return cached["token"]
    return str(cfg.config().get("ig_token", "") or "")


def _user_id() -> str:
    return str(cfg.config().get("ig_user_id", "") or "")


def connected() -> bool:
    return bool(_token() and _user_id())


def _api(method: str, path: str, params: dict, api=None) -> dict:
    """One Graph call. Never raises into the queue loop — errors come back as
    {'error': …} exactly like Meta sends them."""
    if api is not None:
        return api(method, path, params)
    params = {**params, "access_token": _token()}
    url = f"{GRAPH}{path}"
    data = urllib.parse.urlencode(params).encode()
    try:
        if method == "GET":
            req = urllib.request.Request(f"{url}?{urllib.parse.urlencode(params)}")
        else:
            req = urllib.request.Request(url, data=data, method="POST")
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as e:
        try:
            return json.loads(e.read().decode("utf-8", "replace"))
        except Exception:
            return {"error": {"message": f"http {e.code}"}}
    except Exception as e:
        return {"error": {"message": str(e)[:200]}}


def check_connection(api=None) -> dict:
    if not connected():
        return {"connected": False,
                "hint": "IG-User-ID und Token in /etc/auralis/portal.env eintragen (Anleitung im Tab)"}
    r = _api("GET", f"/{_user_id()}", {"fields": "username"}, api)
    if "error" in r:
        return {"connected": False, "error": r["error"].get("message", "?")}
    st = _social.state()
    exp = (st.get("ig_token") or {}).get("expires", "")
    return {"connected": True, "username": r.get("username", "?"), "token_expires": exp}


def refresh_token(api=None) -> dict:
    """Long-lived tokens die after ~60 days; the monthly timer trades the
    current one for a fresh one and caches it in state.json (the env file is
    root-owned — the service can read it, not rewrite it)."""
    c = cfg.config()
    app_id, app_secret = c.get("ig_app_id", ""), c.get("ig_app_secret", "")
    if not (app_id and app_secret and _token()):
        return {"ok": False, "error": "App-ID/-Secret oder Token fehlen"}
    r = _api("GET", "/oauth/access_token",
             {"grant_type": "fb_exchange_token", "client_id": app_id,
              "client_secret": app_secret, "fb_exchange_token": _token()}, api)
    if "access_token" not in r:
        return {"ok": False, "error": (r.get("error") or {}).get("message", "?")}
    st = _social.state()
    exp = (_dt.datetime.now(_dt.timezone.utc)
           + _dt.timedelta(seconds=int(r.get("expires_in", 60 * 86400)))).strftime("%Y-%m-%d")
    st["ig_token"] = {"token": r["access_token"], "expires": exp,
                      "refreshed": time.strftime("%Y-%m-%dT%H:%M")}
    _social.save_state(st)
    return {"ok": True, "expires": exp}


# ─────────────────────────────────────────────── public signed asset URLs ───
def asset_token(week: str, sid: str, name: str) -> str:
    return auth.issue_token(f"{week}/{sid}/{name}", ttl_seconds=4 * 3600,
                            scope="ig-asset")


def verify_asset_token(token: str, week: str, sid: str, name: str) -> bool:
    return auth.verify_token(token, scope="ig-asset") == f"{week}/{sid}/{name}"


def asset_url(week: str, sid: str, name: str) -> str:
    base = cfg.config().get("public_base_url", "").rstrip("/")
    tok = asset_token(week, sid, name)
    return f"{base}/pub/social/{tok}/{week}/{sid}/{name}"


# ──────────────────────────────────────────────────────────── the schedule ──
def publish_at_utc(week: str, day: str, hhmm: str) -> str:
    """'2026-W34' + 'Mittwoch' + '18:00' → the UTC instant, DST-safe."""
    y, w = int(week[:4]), int(week[-2:])
    monday = _dt.date.fromisocalendar(y, w, 1)
    d = monday + _dt.timedelta(days=_DAY_IDX.get(day, 0))
    try:
        hh, mm = int(hhmm[:2]), int(hhmm[3:5])
    except Exception:
        hh, mm = 12, 0
    local = _dt.datetime.combine(d, _dt.time(hh, mm), _TZ)
    return local.astimezone(_dt.timezone.utc).isoformat()


def queue_slot(week: str, slot: dict) -> dict:
    slot["publish_at"] = publish_at_utc(week, slot.get("day", "Montag"),
                                        slot.get("time", "12:00"))
    slot["publish_status"] = "queued"
    slot.pop("publish_error", None)
    return slot


# ─────────────────────────────────────────────────────────────── publishing ──
def _wait_ready(cid: str, api=None, tries: int = 30, delay: float = 5.0) -> bool:
    """Video containers process asynchronously; poll until FINISHED."""
    for _ in range(tries):
        r = _api("GET", f"/{cid}", {"fields": "status_code"}, api)
        code = r.get("status_code")
        if code == "FINISHED":
            return True
        if code in ("ERROR", "EXPIRED") or "error" in r:
            return False
        time.sleep(delay if api is None else 0)
    return False


def publish_slot(week: str, slot: dict, api=None) -> dict:
    """The two-step container→publish dance, per format. Returns the updated
    slot; success carries media_id, failure carries publish_error — and a
    failed slot stays visible in the queue instead of vanishing."""
    ig = _user_id()
    sid = slot["id"]
    adir = _social._slot_asset_dir(week, sid)
    caption = _social.assemble_caption(slot)
    files = sorted(p.name for p in adir.iterdir() if p.is_file()) if adir.is_dir() else []
    pngs = [f for f in files if f.endswith(".png")]

    def fail(msg: str) -> dict:
        slot["publish_status"] = "failed"
        slot["publish_error"] = str(msg)[:300]
        return slot

    try:
        kind = slot.get("kind", "post")
        if kind == "reel":
            if "reel.mp4" not in files:
                return fail("kein reel.mp4 — erst Bilder/Reel erzeugen (ffmpeg nötig)")
            r = _api("POST", f"/{ig}/media",
                     {"media_type": "REELS", "video_url": asset_url(week, sid, "reel.mp4"),
                      "caption": caption}, api)
            if "id" not in r:
                return fail((r.get("error") or {}).get("message", "container failed"))
            if not _wait_ready(r["id"], api):
                return fail("Video-Verarbeitung bei Meta nicht fertig geworden")
            pub = _api("POST", f"/{ig}/media_publish", {"creation_id": r["id"]}, api)
        elif kind == "story":
            if not pngs:
                return fail("kein Bild — erst „Bilder erzeugen“")
            r = _api("POST", f"/{ig}/media",
                     {"media_type": "STORIES",
                      "image_url": asset_url(week, sid, pngs[0])}, api)
            if "id" not in r:
                return fail((r.get("error") or {}).get("message", "container failed"))
            pub = _api("POST", f"/{ig}/media_publish", {"creation_id": r["id"]}, api)
        elif kind == "carousel" or len(pngs) > 1:
            if not pngs:
                return fail("keine Bilder — erst „Bilder erzeugen“")
            children = []
            for f in pngs[:10]:
                r = _api("POST", f"/{ig}/media",
                         {"image_url": asset_url(week, sid, f), "is_carousel_item": "true"}, api)
                if "id" not in r:
                    return fail((r.get("error") or {}).get("message", f"child {f} failed"))
                children.append(r["id"])
            r = _api("POST", f"/{ig}/media",
                     {"media_type": "CAROUSEL", "children": ",".join(children),
                      "caption": caption}, api)
            if "id" not in r:
                return fail((r.get("error") or {}).get("message", "carousel container failed"))
            pub = _api("POST", f"/{ig}/media_publish", {"creation_id": r["id"]}, api)
        else:
            if not pngs:
                return fail("kein Bild — erst „Bilder erzeugen“")
            r = _api("POST", f"/{ig}/media",
                     {"image_url": asset_url(week, sid, pngs[0]), "caption": caption}, api)
            if "id" not in r:
                return fail((r.get("error") or {}).get("message", "container failed"))
            pub = _api("POST", f"/{ig}/media_publish", {"creation_id": r["id"]}, api)
        if "id" not in pub:
            return fail((pub.get("error") or {}).get("message", "publish failed"))
        slot["publish_status"] = "published"
        slot["media_id"] = pub["id"]
        slot["published_at"] = time.strftime("%Y-%m-%dT%H:%M")
        slot.pop("publish_error", None)
        return slot
    except Exception as e:                      # a crash must not kill the queue walk
        return fail(str(e)[:200])


def run_queue(now: _dt.datetime | None = None, api=None, dry_run: bool = False) -> dict:
    """Walk every week's plan; publish what is due. The timer entry point."""
    if not connected() and api is None:
        return {"published": 0, "due": 0, "note": "nicht verbunden"}
    now = now or _dt.datetime.now(_dt.timezone.utc)
    published, due, failed = 0, 0, 0
    for wk in _social.list_weeks():
        plan = _social.load_plan(wk)
        changed = False
        for slot in plan["slots"]:
            if not slot.get("approved") or slot.get("publish_status") not in ("queued",):
                continue
            at = slot.get("publish_at", "")
            try:
                due_now = _dt.datetime.fromisoformat(at) <= now
            except Exception:
                due_now = True
            if not due_now:
                continue
            due += 1
            if dry_run:
                continue
            slot = publish_slot(wk, slot, api)
            changed = True
            if slot["publish_status"] == "published":
                published += 1
            else:
                failed += 1
        if changed:
            _social.save_plan(plan)
    return {"published": published, "failed": failed, "due": due}
