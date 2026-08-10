"""Auralis Natura — portal + Betriebskonsole + Cloud Report Agent API.

One Flask app. Binds to 127.0.0.1 only; the internet reaches it exclusively
through the Cloudflare tunnel, and /staff sits behind Cloudflare Access.

Auth:
  [P] client  -> Bearer token (Authorization: Bearer <token>) from /api/login
  [K] staff   -> X-Auralis-Key header (behind Cloudflare Access in prod)
  [-] public  -> pages + health
"""
from __future__ import annotations
import os, sys, json, functools, shutil, threading, datetime as _dt
from pathlib import Path
from flask import Flask, request, jsonify, Response, send_file

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from lib import cfg, store, auth, agent, render, mailer, backup, booking, finance  # noqa: E402

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 512 * 1024   # cap request bodies (DoS)
_CLIENTS_LOCK = threading.RLock()


# ---------- CORS + security headers ----------
def _origin_ok(origin: str) -> bool:
    from urllib.parse import urlparse
    c = cfg.config()
    if origin in c.get("allowed_origins", []):
        return True
    try:
        host = urlparse(origin).hostname or ""
    except Exception:
        return False
    # match the host on a label boundary — NOT a raw string endswith
    # (so "eviltrycloudflare.com" does not match the "trycloudflare.com" suffix)
    for s in c.get("allowed_origin_suffixes", []):
        if host == s or host.endswith("." + s):
            return True
    return False


# Content-Security-Policy for the two app pages: same-origin only, allow the
# Google Fonts CDN used by the UI, inline styles/scripts (the pages are self-contained).
_CSP = ("default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline' "
        "https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com; "
        "script-src 'self' 'unsafe-inline'; connect-src 'self'; frame-ancestors 'none'; "
        "base-uri 'none'; form-action 'self'")


@app.after_request
def _headers(resp: Response) -> Response:
    origin = request.headers.get("Origin", "")
    if origin and _origin_ok(origin):
        resp.headers["Access-Control-Allow-Origin"] = origin
        resp.headers["Vary"] = "Origin"
        resp.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization, X-Auralis-Key"
        resp.headers["Access-Control-Allow-Methods"] = "GET, POST, DELETE, OPTIONS"
        resp.headers["Access-Control-Allow-Credentials"] = "true"
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["X-Frame-Options"] = "DENY"
    resp.headers["Referrer-Policy"] = "no-referrer"
    resp.headers["Content-Security-Policy"] = _CSP
    resp.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return resp


@app.route("/api/<path:_p>", methods=["OPTIONS"])
def _preflight(_p):
    return ("", 204)


# ---------- auth decorators ----------
def staff_required(fn):
    @functools.wraps(fn)
    def wrap(*a, **k):
        if not auth.check_api_key(request.headers.get("X-Auralis-Key")):
            return jsonify(error="unauthorized"), 401
        return fn(*a, **k)
    return wrap


def client_required(fn):
    @functools.wraps(fn)
    def wrap(*a, **k):
        hdr = request.headers.get("Authorization", "")
        token = hdr[7:] if hdr.startswith("Bearer ") else None
        cid = auth.verify_token(token)
        if not cid:
            return jsonify(error="unauthorized"), 401
        request.client_id = cid  # type: ignore[attr-defined]
        return fn(*a, **k)
    return wrap


def _json() -> dict:
    d = request.get_json(silent=True)
    return d if isinstance(d, dict) else {}


import re as _re, time as _t
_CID_RE = _re.compile(r"^AN-\d{3,}$")


def _valid_cid(cid: str) -> bool:
    return bool(_CID_RE.match(cid or ""))




_NOTE_LABELS = {"beobachtungen": "Beobachtungen", "themen": "Hauptthemen",
                "prioritaeten": "Prioritäten der Klientin", "vereinbart": "Vereinbart"}


def _notes_text(n) -> str:
    if isinstance(n, dict):
        return "\n".join(f"{_NOTE_LABELS.get(k, k)}: {v}" for k, v in n.items() if str(v).strip())
    return str(n or "")

# ---------- activity log (GDPR accountability) ----------
def _log(rec: dict, event: str) -> None:
    log = rec.setdefault("meta", {}).setdefault("activity", [])
    log.append({"ts": store._now(), "event": event})
    del log[:-100]   # keep the most recent 100 events


# ---------- login rate limiting (per client-id + IP) ----------
_ATTEMPTS: dict = {}
_MAX_ATTEMPTS = 6
_WINDOW = 900          # 15 minutes


def _rl_key() -> str:
    d = request.get_json(silent=True)
    cid = d.get("client_id", "") if isinstance(d, dict) else ""
    ip = (request.headers.get("X-Forwarded-For", request.remote_addr or "")).split(",")[0].strip()
    return f'{ip}:{str(cid)[:40]}'


def _rl_blocked(key: str) -> bool:
    now = _t.time()
    hits = [h for h in _ATTEMPTS.get(key, []) if now - h < _WINDOW]
    _ATTEMPTS[key] = hits
    return len(hits) >= _MAX_ATTEMPTS


def _rl_fail(key: str) -> None:
    _ATTEMPTS.setdefault(key, []).append(_t.time())


@app.errorhandler(400)
def _e400(e): return jsonify(error="bad request"), 400
@app.errorhandler(404)
def _e404(e): return jsonify(error="not found"), 404
@app.errorhandler(413)
def _e413(e): return jsonify(error="payload too large"), 413
@app.errorhandler(500)
def _e500(e):
    app.logger.exception("unhandled error"); return jsonify(error="internal error"), 500


# ---------- pages + health ----------
@app.get("/health")
def health():
    return jsonify(ok=True, time=store._now())


@app.get("/api/version")
def version():
    return jsonify(name="auralis-portal", version="1.0")


@app.get("/")
def home():
    return _page("portal.html")


@app.get("/portal")
def portal_page():
    return _page("portal.html")


@app.get("/staff")
def staff_page():
    return _page("staff.html")


@app.get("/assets/seal.png")
def seal():
    return send_file(cfg.ASSETS_DIR / "seal.png")


@app.get("/manifest.webmanifest")
def manifest():
    return send_file(cfg.WEB_DIR / "manifest.webmanifest", mimetype="application/manifest+json")


@app.get("/assets/office-180.png")
def office_icon():
    return send_file(cfg.ASSETS_DIR / "office-180.png")


@app.get("/assets/office-512.png")
def office_icon5():
    return send_file(cfg.ASSETS_DIR / "office-512.png")


@app.get("/assets/desiree.jpg")
def founder_photo():
    p = cfg.ASSETS_DIR / "desiree.jpg"
    if not p.exists():
        return ("", 404)
    return send_file(p)


def _page(name: str):
    p = cfg.WEB_DIR / name
    if not p.exists():
        return ("not built", 404)
    resp = Response(p.read_text(encoding="utf-8"), mimetype="text/html")
    # the home-screen app must always load the newest UI after a server update
    resp.headers["Cache-Control"] = "no-cache, must-revalidate"
    return resp


# ---------- customer app — live browser preview ----------
# Serves the SAME bundle that ships in the iOS/Android build (app/www at repo
# root), so the founder can open/try the app on any phone without Xcode.
# No secrets in the bundle; login still gates all data. Same-origin → the app's
# API calls hit this server directly.
_APP_DIR = (cfg.ROOT.parent / "app" / "www").resolve()


@app.get("/app")
@app.get("/app/")
def app_index():
    return app_asset("index.html")


@app.get("/app/<path:asset>")
def app_asset(asset):
    if not _APP_DIR.exists():
        return ("app bundle not present", 404)
    from flask import send_from_directory
    resp = send_from_directory(_APP_DIR, asset)  # safe-join, no traversal
    if asset.endswith((".html", ".js", ".css")):
        resp.headers["Cache-Control"] = "no-cache, must-revalidate"  # updates flow instantly
    return resp


# ---------- client (portal) ----------
_DUMMY_HASH = auth.hash_password("timing-equaliser")  # burn equal CPU on unknown users


@app.post("/api/login")
def login():
    key = _rl_key()
    if _rl_blocked(key):
        return jsonify(error="too many attempts — please wait a few minutes"), 429
    d = _json()
    cid = str(d.get("client_id", "")).strip()
    pw = str(d.get("password", ""))
    clients = cfg.clients().get("clients", {})
    rec = clients.get(cid)
    if rec is None and cid:
        # case-insensitive fallback: some keyboards auto-capitalise the login id
        low = cid.lower()
        for _k, _v in clients.items():
            if _k.lower() == low:
                cid, rec = _k, _v
                break
    if not rec or rec.get("status") == "disabled":
        auth.verify_password(pw, _DUMMY_HASH)   # equalise timing to avoid user enumeration
        _rl_fail(key)
        return jsonify(error="invalid credentials"), 401
    if not auth.verify_password(pw, rec.get("password", "")):
        _rl_fail(key)
        return jsonify(error="invalid credentials"), 401
    _ATTEMPTS.pop(key, None)
    return jsonify(token=auth.issue_token(cid), client_id=cid,
                   name=rec.get("name"), language=rec.get("language", "de"))


def _safe_login(cid: str, info: dict) -> dict:
    """Serialize a client login record without any secret fields."""
    safe = {k: v for k, v in info.items() if k not in ("password", "password_plaintext")}
    safe["client_id"] = cid
    return safe


def _wellbeing(data: dict) -> dict:
    """The client's own 4 wellbeing scales (1–5) from intake, else the booking
    pre-intake. Plus a 0–100 balance score (stress is inverse)."""
    b = (data.get("intake") or {}).get("b") or {}
    if not b:
        b = (data.get("pre_intake") or {}).get("scales") or {}
    out = {}
    for k in ("energy", "sleep", "stress", "digestion"):
        v = b.get(k)
        try:
            out[k] = max(1, min(5, int(round(float(v)))))
        except (TypeError, ValueError):
            pass
    score = None
    if out:
        good = [out.get("energy"), out.get("sleep"), out.get("digestion")]
        good = [g for g in good if g is not None]
        parts = list(good) + ([6 - out["stress"]] if "stress" in out else [])
        if parts:
            score = int(round(sum(parts) / (len(parts) * 5) * 100))
    return {"scales": out, "score": score}


@app.get("/api/me")
@client_required
def me():
    cid = request.client_id  # type: ignore[attr-defined]
    rec = cfg.clients().get("clients", {}).get(cid, {})
    data = store.get(cid) or {}
    report = data.get("report") or {}
    ready = data.get("stage") in ("sent", "done")
    wb = _wellbeing(data)
    # the client's own report highlights, only once the report is approved/ready
    priorities, habits = [], []
    if ready and report:
        priorities = [{"title": str(p.get("title", ""))[:120], "first_step": str(p.get("first_step", ""))[:200]}
                      for p in (report.get("priorities") or [])][:3]
        habits = [str(h)[:80] for h in (report.get("habits") or [])][:6]
    return jsonify(client_id=cid, name=rec.get("name"), language=rec.get("language", "de"),
                   stage=data.get("stage", "invited"), has_intake=bool(data.get("intake")),
                   report_ready=ready, wellbeing=wb, priorities=priorities, habits=habits,
                   created=rec.get("created", ""))


@app.post("/api/intake")
@client_required
def submit_intake():
    cid = request.client_id  # type: ignore[attr-defined]
    d = _json()
    consent = d.get("consent")
    if not isinstance(consent, dict) or not consent.get("coaching_not_medical") or not consent.get("gdpr_health_data"):
        return jsonify(error="consent required"), 400
    rec = store.ensure(cid)
    # don't let a re-submission clobber a report that's already in progress
    if store.stage_index(rec.get("stage", "invited")) >= store.stage_index("intake"):
        return jsonify(error="intake already submitted — please contact team@auralisnatura.com to change it"), 409
    rec["intake"] = d
    rec.setdefault("meta", {})["intake_submitted"] = store._now()
    _log(rec, "intake submitted")
    store.upsert(rec)
    store.set_stage(cid, "intake")
    # opportunistically pre-compute the meeting prep (best-effort; log if it fails)
    try:
        rec = store.get(cid)
        rec["prep"] = agent.meeting_prep(d)
        store.upsert(rec)
        store.set_stage(cid, "prep")
    except Exception as e:
        app.logger.warning("meeting_prep failed for %s: %s", cid, e)
    return jsonify(ok=True)


@app.post("/api/my/change-password")
@client_required
def my_change_password():
    """Client changes their own password (current password required)."""
    cid = request.client_id  # type: ignore[attr-defined]
    d = _json()
    cur = str(d.get("current", "")); new = str(d.get("new", ""))
    if len(new) < 8:
        return jsonify(error="password too short (min 8)"), 400
    with cfg._CLIENTS_LOCK:
        data = cfg.clients()
        info = data.get("clients", {}).get(cid)
        if not info or not auth.verify_password(cur, info.get("password", "")):
            return jsonify(error="current password incorrect"), 403
        info["password"] = auth.hash_password(new)
        cfg.save_clients(data)
    rec = store.get(cid)
    if rec:
        _log(rec, "password changed by client (app)")
        store.update_existing(rec)
    return jsonify(ok=True)


@app.get("/api/my/documents")
@client_required
def my_documents():
    """Customer-visible documents only (currently: the personal report)."""
    cid = request.client_id  # type: ignore[attr-defined]
    rec = store.get(cid) or {}
    docs = []
    if rec.get("stage") in ("sent", "done"):
        pdf = cfg.OUTPUT_DIR / cid / "report" / "report.pdf"
        if not pdf.exists():
            pdf = pdf.with_suffix(".html")
        if pdf.exists():
            gen = (rec.get("report") or {}).get("generated_at") or rec.get("updated", "")
            docs.append({"key": "report", "name": "Persönlicher Bericht",
                         "type": pdf.suffix.lstrip("."), "date": gen[:10]})
    return jsonify(documents=docs)


@app.post("/api/my/report-token")
@client_required
def my_report_token():
    """Mint a short-lived, REPORT-SCOPED token JUST for opening the report PDF in
    the system viewer (which cannot send an Authorization header). 90s TTL + a
    scope claim so a leaked URL can only ever fetch the report — never /api/me,
    intake, or a fresh token — and is useless within 90s anyway."""
    cid = request.client_id  # type: ignore[attr-defined]
    return jsonify(token=auth.issue_token(cid, ttl_seconds=90, scope="report"))


@app.get("/api/my/report")
def my_report():
    # header path accepts a full session token; the ?token= path accepts ONLY a
    # report-scoped token (the app opens this URL in the system PDF viewer).
    hdr = request.headers.get("Authorization", "")
    cid = auth.verify_token(hdr[7:]) if hdr.startswith("Bearer ") else None
    if not cid:
        cid = auth.verify_token(request.args.get("token") or None, scope="report")
    if not cid:
        return jsonify(error="unauthorized"), 401
    rec = store.get(cid) or {}
    if rec.get("stage") not in ("sent", "done"):
        return jsonify(error="not ready"), 404
    pdf = cfg.OUTPUT_DIR / cid / "report" / "report.pdf"
    if not pdf.exists():
        pdf = pdf.with_suffix(".html")
    if not pdf.exists():
        return jsonify(error="not found"), 404
    ext = pdf.suffix.lstrip(".")  # real extension → correct name + mimetype
    return send_file(pdf, as_attachment=False, download_name=f"Auralis-Bericht-{cid}.{ext}")


@app.get("/api/app/offers")
def app_offers():
    """Public: the buyable programmes for the mobile app shop (name, price,
    tagline, Stripe Payment Link). No secrets — Payment Links are public URLs."""
    out = []
    for p in cfg.config().get("packages", []):
        if p.get("key") == "grove":
            continue  # corporate = enquiry only, not a fixed-price in-app buy
        out.append({"key": p.get("key"), "name": p.get("name"), "price": p.get("price", 0),
                    "tagline": p.get("tagline", ""), "buy_url": p.get("buy_url", "")})
    return jsonify(offers=out)


_PUSH_LOCK = threading.RLock()


@app.post("/api/app/push-token")
@client_required
def app_push_token():
    """Store this client's device push token so a future sender can notify them.
    Authenticated (no anonymous writes), keyed by client_id so the file is bounded
    (one entry per client), locked, and self-healing if the file is ever corrupt.
    Whitelisted fields only; no health data."""
    cid = request.client_id  # type: ignore[attr-defined]
    d = _json()
    token = str(d.get("token", ""))[:512]
    platform = str(d.get("platform", ""))[:20]
    if not token:
        return jsonify(ok=False), 200
    try:
        path = cfg.CONFIG_DIR / "push_tokens.json"
        with _PUSH_LOCK:
            try:
                data = json.loads(path.read_text("utf-8")) if path.exists() else {}
                if not isinstance(data, dict):
                    data = {}
            except Exception:
                data = {}  # corrupt file → start fresh rather than block all writes
            data[cid] = {"token": token, "platform": platform, "ts": store._now()}
            tmp = path.with_suffix(".tmp")
            tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), "utf-8")
            tmp.replace(path)
    except Exception:
        app.logger.warning("push-token store failed", exc_info=True)
    return jsonify(ok=True)


@app.post("/api/my/delete-request")
@client_required
def my_delete_request():
    """Client-initiated data-deletion request (GDPR Art. 17 / Apple 5.1.1(v)).
    Flags the record + logs an anonymous event so the operator completes the
    erasure (a coaching relationship carries financial/legal records, so deletion
    is operator-confirmed within the statutory window rather than instant)."""
    cid = request.client_id  # type: ignore[attr-defined]
    rec = store.get(cid)
    if rec is not None:
        rec.setdefault("meta", {})["deletion_requested"] = store._now()
        _log(rec, "Löschung angefragt (durch Kundin)")
        store.update_existing(rec)
    store.log_event("deletion_requested")
    return jsonify(ok=True)


# ---------- staff (Betriebskonsole) ----------
@app.get("/api/clients")
@staff_required
def clients_list():
    logins = cfg.clients().get("clients", {})
    recs = {r["client_id"]: r for r in store.list_records()}
    out = []
    for cid, info in logins.items():
        r = recs.get(cid, {})
        # A single record encrypted under a rotated/lost key must not blank the
        # whole console — degrade to login-only info and flag it instead of 500.
        try:
            full = store.get(cid) or {}
            decrypt_error = False
        except store.DecryptError:
            app.logger.error("client %s: record cannot be decrypted (data-key mismatch)", cid)
            full, decrypt_error = {}, True
        pkg = full.get("package") or {}
        out.append({"client_id": cid, "name": info.get("name"), "email": info.get("email"),
                    "phone": info.get("phone", ""), "created": info.get("created", ""),
                    "address": info.get("address", ""), "city": info.get("city", ""),
                    "country": info.get("country", ""),
                    "language": info.get("language", "de"), "status": info.get("status", "active"),
                    "stage": r.get("stage", "invited"), "updated": r.get("updated"),
                    "package": pkg.get("key", ""), "package_name": pkg.get("name", ""),
                    "price": pkg.get("price", 0), "paid": bool(full.get("paid")),
                    "has_pre_intake": bool(full.get("pre_intake")),
                    "decrypt_error": decrypt_error,
                    "booking_slot": (full.get("booking") or {}).get("slot_utc", "")})
    out.sort(key=lambda x: x.get("updated") or "", reverse=True)
    return jsonify(clients=out)


@app.get("/api/client/<cid>")
@staff_required
def client_detail(cid):
    info = cfg.clients().get("clients", {}).get(cid)
    if not info:
        return jsonify(error="not found"), 404
    rec = store.get(cid) or store.ensure(cid)
    return jsonify(client=_safe_login(cid, info), record=rec)


@app.post("/api/client/<cid>/notes")
@staff_required
def save_notes(cid):
    rec = store.ensure(cid)
    n = _json().get("notes", "")
    if isinstance(n, dict):
        rec["notes"] = {k: str(n.get(k, ""))[:2000] for k in
                        ("beobachtungen", "themen", "prioritaeten", "vereinbart")}
    else:
        rec["notes"] = str(n)
    store.upsert(rec)
    store.set_stage(cid, "call")
    return jsonify(ok=True)


@app.post("/api/client/<cid>/prep")
@staff_required
def run_prep(cid):
    rec = store.get(cid)
    if not rec or not rec.get("intake"):
        return jsonify(error="no intake"), 400
    rec["prep"] = agent.meeting_prep(rec["intake"])
    store.upsert(rec)
    return jsonify(prep=rec["prep"])


@app.post("/api/client/<cid>/draft")
@staff_required
def run_draft(cid):
    rec = store.get(cid)
    if not rec or not rec.get("intake"):
        return jsonify(error="no intake"), 400
    # the operator's chosen client language drives the whole document, so the
    # report matches the language of every other external communication
    info = cfg.clients().get("clients", {}).get(cid, {})
    result = agent.draft_report(rec["intake"], _notes_text(rec.get("notes", "")),
                                client_ref=cid, language=info.get("language"))
    rec["report"] = {"sections": result["sections"], "approved": False,
                     "red_flag": result.get("red_flag"), "provider": result.get("provider"),
                     "charts": result.get("charts", {}), "language": result.get("language", "de"),
                     "priorities": result.get("priorities", []),
                     "weekly_plan": result.get("weekly_plan", {}),
                     "habits": result.get("habits", []),
                     "generated_at": None}
    _log(rec, f"report drafted ({result.get('provider')})" + (" · RED FLAG" if result.get("red_flag") else ""))
    store.upsert(rec)
    store.set_stage(cid, "draft")
    return jsonify(report=rec["report"])


@app.post("/api/client/<cid>/report/save")
@staff_required
def save_report(cid):
    rec = store.get(cid)
    if not rec or not rec.get("report"):
        return jsonify(error="no draft"), 400
    d = _json()
    posted = d.get("sections")
    if isinstance(posted, list):
        # merge body edits into existing sections — never drop science/actions/extras
        cur = {sec.get("key"): sec for sec in rec["report"].get("sections", [])}
        merged = []
        for p in posted:
            key = p.get("key")
            base = dict(cur.get(key, {}))
            base.update({"key": key, "title": p.get("title", base.get("title", "")),
                         "body": p.get("body", base.get("body", ""))})
            merged.append(base)
        rec["report"]["sections"] = merged
    rec["report"]["approved"] = bool(d.get("approved", rec["report"].get("approved")))
    if rec["report"]["approved"]:
        _log(rec, "report approved by founder")
    store.upsert(rec)
    if rec["report"]["approved"]:
        store.set_stage(cid, "review")
    return jsonify(ok=True, approved=rec["report"]["approved"])


@app.post("/api/client/<cid>/generate")
@staff_required
def generate(cid):
    if not _valid_cid(cid):
        return jsonify(error="invalid client id"), 400
    info = cfg.clients().get("clients", {}).get(cid)
    rec = store.get(cid)
    if not info or not rec or not rec.get("report"):
        return jsonify(error="not ready"), 400
    if not rec["report"].get("approved"):
        return jsonify(error="report not approved — review & approve first"), 400
    lang = rec["report"].get("language", info.get("language", "de"))
    try:
        html_text = render.build_html(info.get("name", ""), rec["report"]["sections"],
                                      report=rec["report"], profile=rec.get("pre_intake") or {},
                                      charts=rec["report"].get("charts", {}), language=lang)
        out = cfg.OUTPUT_DIR / cid / "report" / "report.pdf"
        produced = render.to_pdf(html_text, out)
    except Exception as e:
        app.logger.exception("render failed for %s", cid)
        return jsonify(error=f"report render failed: {e}"), 500
    try:
        msg = mailer.build_email(info.get("email", ""), info.get("name", ""), produced, language=lang)
        delivery = mailer.deliver(msg, cid)
    except Exception as e:
        app.logger.exception("email build/deliver failed for %s", cid)
        # the PDF exists; surface the failure but don't mark as sent
        return jsonify(error=f"report rendered but email failed: {e}", pdf=str(produced.name)), 500
    # only advance to "sent" once the render AND the draft/send both succeeded
    failed = any(str(v).startswith(("failed", "skipped")) for v in delivery.values())
    rec["report"]["generated_at"] = store._now()
    _log(rec, "report generated · " + ("; ".join(f"{k}:{v}" for k, v in delivery.items() if k != "eml")))
    if not failed:
        rec["stage"] = "sent"
    # write ONLY if the record still exists — never resurrect a client erased mid-generate
    if not store.update_existing(rec):
        shutil.rmtree(cfg.OUTPUT_DIR / cid, ignore_errors=True)
        return jsonify(error="client was erased during generation"), 410
    return jsonify(ok=(not failed), pdf=str(produced.name), delivery=delivery)


@app.get("/api/client/<cid>/report.pdf")
@staff_required
def download_report(cid):
    if not _valid_cid(cid):
        return jsonify(error="invalid client id"), 400
    pdf = cfg.OUTPUT_DIR / cid / "report" / "report.pdf"
    if not pdf.exists():
        pdf = pdf.with_suffix(".html")
    if not pdf.exists():
        return jsonify(error="not found"), 404
    return send_file(pdf, as_attachment=True)


@app.post("/api/clients")
@staff_required
def invite_client():
    d = _json()
    name = str(d.get("name", "")).strip()
    email = str(d.get("email", "")).strip()
    lang = str(d.get("language", "de")).strip() or "de"
    if not name or not email or "@" not in email:
        return jsonify(error="valid name and email required"), 400
    if lang not in ("de", "en", "es"):
        lang = "de"
    pw = auth.new_password()
    cid = cfg.allocate_client(name, email, lang, status="active",
                              password_hash=auth.hash_password(pw))
    with cfg._CLIENTS_LOCK:   # allocate may have returned an existing entry (same email)
        data = cfg.clients()
        data["clients"][cid]["password"] = auth.hash_password(pw)
        data["clients"][cid]["status"] = "active"
        cfg.save_clients(data)
    r0 = store.ensure(cid); _log(r0, "client invited"); store.upsert(r0)
    return jsonify(client_id=cid, password=pw, portal_url=cfg.config().get("public_base_url", "") + "/portal")


@app.post("/api/client/<cid>/reset-password")
@staff_required
def reset_password(cid):
    with _CLIENTS_LOCK:
        data = cfg.clients()
        if cid not in data.get("clients", {}):
            return jsonify(error="not found"), 404
        pw = auth.new_password()
        data["clients"][cid]["password"] = auth.hash_password(pw)
        cfg.save_clients(data)
    return jsonify(client_id=cid, password=pw)


@app.get("/api/client/<cid>/gdpr-export")
@staff_required
def gdpr_export(cid):
    info = cfg.clients().get("clients", {}).get(cid, {})
    rec = store.get(cid) or {}
    return jsonify(login=_safe_login(cid, info), record=rec)


@app.delete("/api/client/<cid>")
@staff_required
def gdpr_erase(cid):
    if not _valid_cid(cid):
        return jsonify(error="invalid client id"), 400
    db_removed = store.delete(cid)
    shutil.rmtree(cfg.OUTPUT_DIR / cid, ignore_errors=True)   # rendered PDFs + sent .eml
    with _CLIENTS_LOCK:
        data = cfg.clients()
        login_removed = data.get("clients", {}).pop(cid, None) is not None
        cfg.save_clients(data)
    disk_gone = not (cfg.OUTPUT_DIR / cid).exists()
    return jsonify(ok=True, erased=cid, db_removed=db_removed,
                   login_removed=login_removed, disk_removed=disk_gone)


@app.post("/api/client/<cid>/preview")
@staff_required
def preview(cid):
    """Render the CURRENT (possibly unsaved) sections to HTML so the founder can
    see the real report before approving/generating. Never leaves the box."""
    if not _valid_cid(cid):
        return jsonify(error="invalid client id"), 400
    info = cfg.clients().get("clients", {}).get(cid)
    rec = store.get(cid)
    if not info or not rec or not rec.get("report"):
        return jsonify(error="no draft"), 400
    d = _json()
    sections = d.get("sections") or rec["report"]["sections"]
    lang = rec["report"].get("language", info.get("language", "de"))
    html_text = render.build_html(info.get("name", ""), sections,
                                  report=rec["report"], profile=rec.get("pre_intake") or {},
                                  charts=rec["report"].get("charts", {}), language=lang)
    return Response(html_text, mimetype="text/html")


@app.get("/api/status")
@staff_required
def status():
    c = cfg.config()
    from lib import render as _r
    smtp_ok = bool(os.environ.get("AURALIS_SMTP_PASSWORD") or c.get("smtp_password"))
    return jsonify(
        server="ok",
        agent_provider=c.get("agent_provider"),
        claude_cli_available=bool(shutil.which("claude")),
        email_mode=c.get("email_mode"),
        smtp_configured=smtp_ok,
        chrome_available=_r._chrome() is not None,
        backup_dir_set=bool(os.environ.get("AURALIS_BACKUP_DIR") or c.get("backup_dir")),
        production=cfg.is_production(),
        booking_url=c.get("booking_review_url"),
    )






_PROFILE_FIELDS = {"goal": 400, "symptoms": None, "since": 120, "tried": 400,
                   "conditions": 400, "medications": 400, "life_stage": 60,
                   "scales": None, "red_flags": None,
                   "sleep_hours": 20, "movement": 20, "diet": None,
                   "stimulants": None, "allergies": 200}
_KNOWN_SYMPTOMS = {"fatigue", "sleep", "digestion", "stress", "hormonal", "weight",
                   "skin", "mood", "pain", "immune", "other"}
_KNOWN_FLAGS = {"none", "weight_loss", "chest_pain", "severe_pain", "fainting",
                "self_harm", "eating", "pregnancy_complication"}
_KNOWN_DIET = {"omnivore", "vegetarian", "vegan", "lowcarb", "irregular", "sugar", "processed"}
_KNOWN_STIM = {"coffee", "alcohol", "nicotine", "energy", "none"}
_KNOWN_SLEEP = {"lt5", "5-6", "6-7", "7-8", "gt8"}
_KNOWN_MOVE = {"rare", "1-2", "3-4", "daily"}


def _clean_profile(p: dict) -> dict:
    out = {}
    for k, cap in _PROFILE_FIELDS.items():
        v = p.get(k)
        if v is None:
            continue
        if k == "symptoms":
            out[k] = [str(x)[:40] for x in v if str(x) in _KNOWN_SYMPTOMS][:11] if isinstance(v, list) else []
        elif k == "diet":
            out[k] = [str(x)[:40] for x in v if str(x) in _KNOWN_DIET][:7] if isinstance(v, list) else []
        elif k == "stimulants":
            out[k] = [str(x)[:40] for x in v if str(x) in _KNOWN_STIM][:5] if isinstance(v, list) else []
        elif k == "sleep_hours":
            out[k] = str(v) if str(v) in _KNOWN_SLEEP else ""
        elif k == "movement":
            out[k] = str(v) if str(v) in _KNOWN_MOVE else ""
        elif k == "red_flags":
            out[k] = [str(x)[:40] for x in v if str(x) in _KNOWN_FLAGS][:8] if isinstance(v, list) else []
        elif k == "scales":
            out[k] = {sk: max(1, min(5, int(sv))) for sk, sv in v.items()
                      if sk in ("energy", "sleep", "stress", "digestion")
                      and str(sv).lstrip("-").isdigit()} if isinstance(v, dict) else {}
        else:
            out[k] = str(v).strip()[:cap]
    return out


# ---------- business console: journey, dashboard, credentials ----------
@app.post("/api/client/<cid>/stage")
@staff_required
def set_client_stage(cid):
    stage = str(_json().get("stage", "")).strip()
    if stage not in store.STAGES:
        return jsonify(error="unknown stage"), 400
    rec = store.get(cid)
    if rec is None:
        return jsonify(error="not found"), 404
    prev = rec.get("stage")
    rec = store.set_stage(cid, stage, force=True)
    if stage == "won" and not rec.get("won_at"):
        rec["won_at"] = store._now()
    _log(rec, f"stage: {prev} -> {stage}")
    store.upsert(rec)
    # log funnel events only on first FORWARD transition (no double counting
    # when a stage is corrected back and forth)
    if (stage in ("call", "won", "sent", "done", "lost") and prev != stage
            and store.stage_index(prev) < store.stage_index(stage)
            and not rec.get("meta", {}).get(f"ev_{stage}")):
        rec.setdefault("meta", {})[f"ev_{stage}"] = True
        store.upsert(rec)
        pkg = (rec.get("package") or {})
        store.log_event(stage, package=pkg.get("key", ""), amount=pkg.get("price", 0))
    return jsonify(ok=True, stage=stage)


@app.post("/api/client/<cid>/profile")
@staff_required
def edit_client_profile(cid):
    """Edit contact + business data: name, email, phone, language, package, paid."""
    d = _json()
    with cfg._CLIENTS_LOCK:
        data = cfg.clients()
        info = data.get("clients", {}).get(cid)
        if not info:
            return jsonify(error="not found"), 404
        for k in ("name", "email", "phone", "language", "address", "city", "country"):
            if k in d:
                info[k] = str(d[k]).strip()[:200]
        cfg.save_clients(data)
    rec = store.ensure(cid)
    if "package" in d:
        key = str(d.get("package", "")).strip()
        pkgs = {p["key"]: p for p in cfg.config().get("packages", [])}
        if key and key in pkgs:
            price = d.get("price")
            price = float(price) if isinstance(price, (int, float)) else pkgs[key]["price"]
            rec["package"] = {"key": key, "name": pkgs[key]["name"], "price": price}
            _log(rec, f"package set: {key} ({price:.0f} EUR)")
        elif not key:
            rec.pop("package", None)
    if "paid" in d:
        was_paid = bool(rec.get("paid"))
        rec["paid"] = bool(d["paid"])
        if rec["paid"] and not was_paid:
            _log(rec, "payment received")
            store.log_event("paid", package=(rec.get("package") or {}).get("key", ""),
                            amount=(rec.get("package") or {}).get("price", 0))
    store.upsert(rec)
    return jsonify(ok=True)


@app.post("/api/client/<cid>/credentials")
@staff_required
def send_credentials(cid):
    """Issue (or re-issue) portal access and email the branded Zugangsdaten-Karte."""
    with cfg._CLIENTS_LOCK:
        data = cfg.clients()
        info = data.get("clients", {}).get(cid)
        if not info:
            return jsonify(error="not found"), 404
        pw = auth.new_password()
        info["password"] = auth.hash_password(pw)
        if info.get("status") == "lead":
            info["status"] = "active"
        cfg.save_clients(data)
        email = info.get("email", ""); name = info.get("name", "")
        lang = info.get("language", "de")
    rec = store.ensure(cid)
    # advance to 'invited' only from 'won' — sending access to a lead must not
    # push them into the revenue-counting part of the funnel
    if rec.get("stage") == "won":
        rec["stage"] = "invited"
    _log(rec, "credentials issued & emailed")
    store.upsert(rec)
    delivery = {}
    try:
        msg = mailer.build_credentials_email(email, name, cid, pw, lang)
        delivery = mailer.deliver(msg, cid)
    except Exception as e:
        app.logger.exception("credentials email failed")
        delivery = {"error": str(e)}
    return jsonify(ok=True, client_id=cid, password=pw, delivery=delivery)


@app.get("/api/dashboard")
@staff_required
def dashboard():
    """Business KPIs computed live from records + bookings + anonymous events."""
    import datetime as _d
    now = _d.datetime.now(_d.timezone.utc)
    month_start = now.strftime("%Y-%m-01")
    logins = cfg.clients().get("clients", {})
    recs = {r["client_id"]: store.get(r["client_id"]) or r for r in store.list_records()}
    stages = {}
    revenue_total = revenue_open = 0.0
    won_count = 0
    for cid, rec in recs.items():
        st = rec.get("stage", "invited")
        stages[st] = stages.get(st, 0) + 1
        pkg = rec.get("package") or {}
        if pkg.get("price"):
            ix = store.stage_index(st)
            if (rec.get("won_at") or rec.get("paid")) and ix >= store.stage_index("won") and st != "lost":
                revenue_total += float(pkg["price"]); won_count += 1
                if st != "done":
                    revenue_open += float(pkg["price"])
    events = store.list_events()
    def count(ev, since=""):
        return sum(1 for e in events if e["event"] == ev and e["ts"] >= since)
    def revenue(since=""):
        return sum(float(e.get("amount") or 0) for e in events
                   if e["event"] == "won" and e["ts"] >= since)
    bookings_all = count("booking"); calls = count("call"); wons = count("won")
    sents = count("sent"); losts = count("lost")
    # monthly series for the last 6 months (bookings + revenue)
    y, mth = now.year, now.month
    months = []
    for i in range(6):
        months.append(f"{y:04d}-{mth:02d}")
        mth -= 1
        if mth == 0:
            mth = 12; y -= 1
    months.reverse()
    series = [{"month": m,
               "bookings": sum(1 for e in events if e["event"] == "booking" and e["ts"][:7] == m),
               "revenue": sum(float(e.get("amount") or 0) for e in events
                              if e["event"] == "won" and e["ts"][:7] == m)} for m in months]
    upcoming = [b for b in booking.list_bookings()
                if b.get("status") == "confirmed" and b.get("start_utc", "") >= now.isoformat()][:6]
    for b in upcoming:
        b.pop("profile", None)   # keep the dashboard payload lean
    return jsonify(
        funnel={"bookings": bookings_all, "calls": calls, "won": wons,
                "delivered": sents, "lost": losts,
                "call_rate": round(calls / bookings_all * 100) if bookings_all else 0,
                "win_rate": round(wons / calls * 100) if calls else 0},
        revenue={"total": revenue_total, "month": revenue(month_start),
                 "open_pipeline": revenue_open,
                 "avg_deal": round(revenue_total / won_count) if won_count else 0},
        stages=stages, series=series,
        upcoming=upcoming,
        counts={"clients": len(logins),
                "leads": sum(1 for i in logins.values() if i.get("status") == "lead"),
                "active": sum(1 for i in logins.values() if i.get("status") == "active")},
        packages=cfg.config().get("packages", []),
    )




# ---------- Finanzen / Plandaten (Paramur pattern) ----------
@app.get("/api/finanzen")
@staff_required
def finanzen():
    return jsonify(finance.report())


@app.get("/api/plan")
@staff_required
def plan_get():
    return jsonify(finance.get_plan())


@app.post("/api/plan")
@staff_required
def plan_patch():
    d = _json()
    path = str(d.get("path", "")).strip()
    value = d.get("value")
    if not path or any(seg.startswith("_") for seg in path.split(".")):
        return jsonify(error="invalid path"), 400
    if isinstance(value, str):
        v = value.strip()
        if "," in v:
            v = v.replace(".", "").replace(",", ".")
        elif _re.match(r"^\d{1,3}(\.\d{3})+$", v):
            v = v.replace(".", "")          # German thousands: 1.234 -> 1234
        try:
            value = float(v) if "." in v else int(v)
        except (TypeError, ValueError):
            pass   # keep strings (e.g. hinweis texts)
    try:
        finance.patch_plan(path, value)
    except ValueError as e:
        return jsonify(error=str(e)), 400
    return jsonify(ok=True, plan=finance.get_plan())


# ---------- Alerts (cockpit banner -> jump to journey row) ----------
@app.get("/api/alerts")
@staff_required
def alerts():
    import datetime as _d
    now = _d.datetime.now(_d.timezone.utc)
    out = []

    def _bucket(level, key, title, subtitle, items):
        if items:
            out.append({"level": level, "key": key, "title": title,
                        "subtitle": subtitle, "items": items})

    stale_lead, cred_missing, intake_wait, report_stale, unpaid = [], [], [], [], []
    logins = cfg.clients().get("clients", {})
    for r in store.list_records():
        cid = r["client_id"]
        rec = store.get(cid) or {}
        info = logins.get(cid, {})
        name = info.get("name", cid)
        st = rec.get("stage", "")
        upd = rec.get("updated") or rec.get("created") or ""
        try:
            age_d = (now - _d.datetime.fromisoformat(upd)).days if upd else 0
        except ValueError:
            age_d = 0
        slot = (rec.get("booking") or {}).get("slot_utc", "")
        if st == "lead" and slot:
            try:
                slot_age = (now - _d.datetime.fromisoformat(slot)).days
            except ValueError:
                slot_age = -1
            if slot_age >= 1:
                stale_lead.append({"id": cid, "label": f"{name} — Call war {slot[:10]}, Phase noch „Anfrage“"})
        if st == "won" and info.get("status") == "lead":
            cred_missing.append({"id": cid, "label": f"{name} — gewonnen, Zugangsdaten noch nicht gesendet"})
        if st == "invited" and age_d >= 7:
            intake_wait.append({"id": cid, "label": f"{name} — seit {age_d} Tagen ohne Intake"})
        if st in ("draft", "review") and age_d >= 5:
            report_stale.append({"id": cid, "label": f"{name} — Bericht seit {age_d} Tagen in {st}"})
        pkg = rec.get("package") or {}
        if st in ("sent", "done") and pkg.get("price") and not rec.get("paid") and age_d >= 14:
            unpaid.append({"id": cid, "label": f"{name} — {pkg.get('name','Paket')} ({pkg.get('price',0):.0f} €) unbezahlt seit {age_d} Tagen"})

    upcoming = []
    horizon = (now + _d.timedelta(hours=24)).isoformat()
    for b in booking.list_bookings():
        if b.get("status") == "confirmed" and now.isoformat() <= b.get("start_utc", "") <= horizon:
            hhmm = b["start_utc"][11:16]
            upcoming.append({"id": "", "label": f"{b.get('name','?')} — heute/morgen {hhmm} UTC"})

    _bucket("error", "unpaid", "Zahlung offen", "Geliefert, aber unbezahlt (>14 Tage)", unpaid)
    _bucket("warn", "cred_missing", "Zugangsdaten ausstehend", "Gewonnen ohne Portal-Zugang", cred_missing)
    _bucket("warn", "stale_lead", "Nachfassen", "Erstgespräch vorbei, Phase nicht aktualisiert", stale_lead)
    _bucket("warn", "intake_wait", "Intake-Erinnerung", "Zugang gesendet, Fragebogen offen (≥7 Tage)", intake_wait)
    _bucket("warn", "report_stale", "Bericht offen", "Entwurf/Review wartet (≥5 Tage)", report_stale)
    _bucket("info", "upcoming", "Nächste 24 h", "Anstehende Erstgespräche", upcoming)
    return jsonify(alerts=out)


# ---------- Outbox (generated documents & emails) ----------
@app.get("/api/outbox")
@staff_required
def outbox_list():
    base = cfg.OUTPUT_DIR.resolve()
    cand = []
    for ext in ("*.eml", "*.pdf", "*.html", "*.ics"):
        for p in base.rglob(ext):
            if p.is_file():
                st = p.stat()
                cand.append((st.st_mtime, p, st.st_size))
    cand.sort(key=lambda t: t[0], reverse=True)
    items = [{"file": str(p.relative_to(base)), "kind": p.suffix.lstrip(".").lower(),
              "size": size,
              "mtime": _dt.datetime.fromtimestamp(m).isoformat(timespec="minutes")}
             for m, p, size in cand[:200]]
    return jsonify(items=items)


@app.get("/api/outbox/<path:relpath>")
@staff_required
def outbox_file(relpath):
    base = cfg.OUTPUT_DIR.resolve()
    target = (base / relpath).resolve()
    if not str(target).startswith(str(base) + os.sep) or not target.is_file():
        return jsonify(error="not found"), 404
    return send_file(target, as_attachment=True)


# ---------- Version + self-update (launcher restarts on our exit) ----------
import subprocess as _sp
def _build_number() -> str:
    try:
        return _sp.run(["git", "rev-list", "--count", "HEAD"], cwd=cfg.ROOT,
                       capture_output=True, text=True, timeout=10).stdout.strip() or "?"
    except Exception:
        return "?"
_BUILD = _build_number()


@app.get("/api/build")
def build_info():
    return jsonify(build=_BUILD, label=f"Version Auralis {_BUILD}")


@app.post("/api/update")
@staff_required
def self_update():
    try:
        _sp.run(["git", "fetch", "origin", "main"], cwd=cfg.ROOT, capture_output=True, timeout=30)
        local = _sp.run(["git", "rev-parse", "HEAD"], cwd=cfg.ROOT, capture_output=True, text=True).stdout.strip()
        remote = _sp.run(["git", "rev-parse", "origin/main"], cwd=cfg.ROOT, capture_output=True, text=True).stdout.strip()
    except Exception as e:
        return jsonify(error=f"git check failed: {e}"), 500
    if local == remote:
        return jsonify(ok=True, updated=False, message="Bereits aktuell.")
    threading.Timer(1.0, lambda: os._exit(42)).start()   # launcher pulls + restarts
    return jsonify(ok=True, updated=True, message="Update gefunden — Konsole startet in wenigen Sekunden neu.")


# ---------- Newsletter (BCC an alle aktiven Kundinnen) ----------
@app.post("/api/newsletter/draft")
@staff_required
def newsletter_draft():
    d = _json()
    subject = str(d.get("subject", "")).strip()[:200]
    body = str(d.get("body", "")).strip()[:8000]
    if not subject or not body:
        return jsonify(error="subject and body required"), 400
    recipients = [i.get("email") for i in cfg.clients().get("clients", {}).values()
                  if i.get("status") == "active" and i.get("email")]
    if not recipients:
        return jsonify(error="no active clients with email"), 400
    msg = mailer.build_newsletter(subject, body, recipients)
    delivery = mailer.deliver(msg, "newsletter")
    return jsonify(ok=True, recipients=len(recipients), delivery=delivery)


# ---------- own-brand booking (public page + API) ----------
@app.get("/book")
def book_page():
    return _page("book.html")


@app.get("/api/booking/slots")
def booking_slots():
    return jsonify(booking.compute_slots())


@app.post("/api/booking/book")
def booking_book():
    key = "book:" + _rl_key()
    if _rl_blocked(key):
        return jsonify(error="too many attempts — please wait a few minutes"), 429
    d = _json()
    name = str(d.get("name", "")).strip()[:120]
    email = str(d.get("email", "")).strip()[:200]
    language = str(d.get("language", "de")).strip()
    note = str(d.get("note", "")).strip()[:1000]
    slot = str(d.get("slot", "")).strip()
    consent = d.get("consent")
    if not name or "@" not in email or not slot:
        _rl_fail(key)
        return jsonify(error="name, valid email and a time slot are required"), 400
    if not isinstance(consent, dict) or not consent.get("gdpr"):
        return jsonify(error="consent required"), 400
    if language not in ("de", "en", "es"):
        language = "de"
    profile = d.get("profile") if isinstance(d.get("profile"), dict) else {}
    profile = _clean_profile(profile)
    try:
        b = booking.book(slot, name, email, language, note, profile=profile)
    except ValueError as e:
        return jsonify(error=str(e)), 409
    # the booking IS the first funnel step: create/find the lead record so the
    # journey pipeline shows the person immediately, with their pre-intake attached
    try:
        cid = cfg.allocate_client(name, email, language, status="lead")
        rec = store.ensure(cid)
        ix = store.stage_index(rec.get("stage", ""))
        # a record fresh from ensure() sits at the default stage with no history —
        # treat it (and genuine pre-win leads) as funnel entries; never downgrade
        # an onboarded client who books a follow-up call
        fresh = (ix < 0 or (not rec.get("won_at") and not rec.get("intake")
                            and ix <= store.stage_index("invited")))
        if fresh or ix <= store.stage_index("call"):
            rec["pre_intake"] = profile
            rec["booking"] = {"id": b["id"], "slot_utc": b["start_utc"], "note": note}
            if ix < 0 or fresh:
                rec["stage"] = "lead"
        else:
            rec.setdefault("followup_bookings", []).append(
                {"id": b["id"], "slot_utc": b["start_utc"]})
        _log(rec, f"call booked ({b['start_utc'][:16]})")
        store.upsert(rec)
        store.log_event("booking", language=language,
                        symptoms=len(profile.get("symptoms", [])))
    except Exception:
        app.logger.exception("lead creation failed (booking still confirmed)")
    # confirmation email (draft/send per email_mode) with .ics
    try:
        import datetime as _d
        from zoneinfo import ZoneInfo
        tz = ZoneInfo(booking.get_availability().get("timezone", "Europe/Madrid"))
        local = _d.datetime.fromisoformat(slot).astimezone(tz)
        when = local.strftime("%A, %d %B %Y · %H:%M ") + f"({booking.get_availability().get('timezone')})"
        ics = booking.ics_for(slot, name, b["id"], client_email=email)
        (cfg.OUTPUT_DIR / "bookings").mkdir(parents=True, exist_ok=True)
        (cfg.OUTPUT_DIR / "bookings" / f"{b['id']}.ics").write_bytes(ics)
        # Acknowledgement FIRST and sent immediately: the confirmation below is a
        # draft in email_mode=draft, so without this the client hands over health
        # details and hears nothing at all until Desiree gets to her inbox.
        try:
            delivery = mailer.send_now(
                mailer.build_ack_email(email, name, when, language))
        except Exception as e:
            app.logger.exception("acknowledgement mail failed")
            delivery = {"ack": f"failed: {e}"}
        msg = mailer.build_booking_email(email, name, when, language, ics, b["id"])
        delivery.update(mailer.deliver(msg, "bookings"))
    except Exception as e:
        app.logger.exception("booking email failed")
        delivery = {"email": f"failed: {e}"}
    # Internal briefing to team@ — separate try, because a client whose
    # confirmation failed must still surface, and a notification that fails must
    # never take the confirmation (or the booking) down with it.
    try:
        # `when` is built inside the confirmation try above; if that failed
        # before reaching it, recompute rather than NameError our way out of the
        # one mail that still matters.
        try:
            when
        except NameError:
            when = slot
        note_txt = (profile or {}).get("note") or note or ""
        internal = mailer.build_internal_booking_email(
            name, email, when, language, profile or {}, note_txt, b["id"])
        delivery.update(mailer.notify_internal(internal))
    except Exception as e:
        app.logger.exception("internal booking notification failed")
        delivery["internal"] = f"failed: {e}"
    return jsonify(ok=True, id=b["id"], when=slot, delivery_mode=delivery.get("mode", "off"))


@app.get("/api/availability")
@staff_required
def availability_get():
    return jsonify(booking.get_availability())


@app.post("/api/availability")
@staff_required
def availability_save():
    return jsonify(booking.save_availability(_json()))


@app.get("/api/bookings")
@staff_required
def bookings_list():
    return jsonify(bookings=booking.list_bookings())


@app.post("/api/booking/<bid>/cancel")
@staff_required
def booking_cancel(bid):
    ok = booking.cancel(bid)
    return (jsonify(ok=True) if ok else (jsonify(error="not found"), 404))




@app.post("/api/booking/<bid>/remind")
@staff_required
def booking_remind(bid):
    """One-click branded reminder email for an upcoming call."""
    b = next((x for x in booking.list_bookings() if x.get("id") == bid), None)
    if not b or b.get("status") != "confirmed":
        return jsonify(error="not found"), 404
    import datetime as _d
    from zoneinfo import ZoneInfo
    tz = ZoneInfo(booking.get_availability().get("timezone", "Europe/Madrid"))
    local = _d.datetime.fromisoformat(b["start_utc"]).astimezone(tz)
    when = local.strftime("%A, %d %B %Y · %H:%M ") + f"({booking.get_availability().get('timezone')})"
    # a known client's operator-chosen language wins over the booking's own,
    # so every external message honours the language set in the Kundinnen tab
    lang = b.get("language", "de")
    bmail = (b.get("email") or "").strip().lower()
    if bmail:
        for info in cfg.clients().get("clients", {}).values():
            if info.get("email", "").strip().lower() == bmail and info.get("language"):
                lang = info["language"]; break
    msg = mailer.build_reminder_email(b.get("email", ""), b.get("name", ""), when, lang)
    delivery = mailer.deliver(msg, "bookings")
    return jsonify(ok=True, delivery=delivery)


@app.post("/api/client/<cid>/feedback-request")
@staff_required
def feedback_request(cid):
    """Close the flywheel: branded thank-you + testimonial ask after completion."""
    info = cfg.clients().get("clients", {}).get(cid)
    if not info:
        return jsonify(error="not found"), 404
    msg = mailer.build_feedback_email(info.get("email", ""), info.get("name", ""),
                                      info.get("language", "de"))
    delivery = mailer.deliver(msg, cid)
    rec = store.ensure(cid)
    _log(rec, "feedback / testimonial angefragt")
    store.upsert(rec)
    store.log_event("feedback_asked")
    return jsonify(ok=True, delivery=delivery)


# ---------- Stammdaten (company master data) ----------
@app.get("/api/company")
@staff_required
def company_get():
    co = dict(cfg.company())
    co["_editable"] = sorted(cfg.COMPANY_EDITABLE)
    return jsonify(co)


@app.post("/api/company")
@staff_required
def company_save():
    return jsonify(cfg.save_company(_json()))


def main():
    cfg.validate_secrets()   # fail closed if prod secrets are missing/default
    # Loud, early warning if AURALIS_DATA_KEY doesn't match the encrypted store.
    # Without this the mismatch only surfaces as a confusing 500 ("key not
    # accepted") the first time the console reads a client. We DON'T hard-exit —
    # the site (booking, health checks) should still serve — but we scream in the
    # log so the cause is obvious.
    if store.key_matches_store() is False:
        banner = ("!!! AURALIS_DATA_KEY does NOT match the encrypted store — client "
                  "records cannot be decrypted (key rotated or lost). The staff "
                  "console will fail to load clients until the correct key is restored. "
                  "Do NOT overwrite the store. See tools/an_recover / migrate.")
        app.logger.error("=" * 88 + "\n" + banner + "\n" + "=" * 88)
        print("\n" + banner + "\n", flush=True)
    backup.start_scheduler() # hourly encrypted backup outside the repo (if configured)
    c = cfg.config()
    app.run(host=c.get("host", "127.0.0.1"), port=int(os.environ.get("AURALIS_PORT", c.get("port", 5056))), debug=False)


if __name__ == "__main__":
    main()
