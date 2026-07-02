"""Auralis Natura — portal + Betriebskonsole + Cloud Report Agent API.

One Flask app. Binds to 127.0.0.1 only; the internet reaches it exclusively
through the Cloudflare tunnel, and /staff sits behind Cloudflare Access.

Auth:
  [P] client  -> Bearer token (Authorization: Bearer <token>) from /api/login
  [K] staff   -> X-Auralis-Key header (behind Cloudflare Access in prod)
  [-] public  -> pages + health
"""
from __future__ import annotations
import os, sys, functools, shutil, threading, datetime as _dt
from pathlib import Path
from flask import Flask, request, jsonify, Response, send_file

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from lib import cfg, store, auth, agent, render, mailer, backup, booking  # noqa: E402

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
        "https://fonts.googleapis.com; font-src https://fonts.gstatic.com; "
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


def _page(name: str):
    p = cfg.WEB_DIR / name
    if not p.exists():
        return ("not built", 404)
    return Response(p.read_text(encoding="utf-8"), mimetype="text/html")


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
    rec = cfg.clients().get("clients", {}).get(cid)
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


@app.get("/api/me")
@client_required
def me():
    cid = request.client_id  # type: ignore[attr-defined]
    rec = cfg.clients().get("clients", {}).get(cid, {})
    data = store.get(cid) or {}
    return jsonify(client_id=cid, name=rec.get("name"), language=rec.get("language", "de"),
                   stage=data.get("stage", "invited"), has_intake=bool(data.get("intake")),
                   report_ready=data.get("stage") in ("sent", "done"))


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


@app.get("/api/my/report")
@client_required
def my_report():
    cid = request.client_id  # type: ignore[attr-defined]
    rec = store.get(cid) or {}
    if rec.get("stage") not in ("sent", "done"):
        return jsonify(error="not ready"), 404
    pdf = cfg.OUTPUT_DIR / cid / "report" / "report.pdf"
    if not pdf.exists():
        pdf = pdf.with_suffix(".html")
    if not pdf.exists():
        return jsonify(error="not found"), 404
    return send_file(pdf, as_attachment=True)


# ---------- staff (Betriebskonsole) ----------
@app.get("/api/clients")
@staff_required
def clients_list():
    logins = cfg.clients().get("clients", {})
    recs = {r["client_id"]: r for r in store.list_records()}
    out = []
    for cid, info in logins.items():
        r = recs.get(cid, {})
        out.append({"client_id": cid, "name": info.get("name"), "email": info.get("email"),
                    "language": info.get("language", "de"), "status": info.get("status", "active"),
                    "stage": r.get("stage", "invited"), "updated": r.get("updated")})
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
    rec["notes"] = str(_json().get("notes", ""))
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
    result = agent.draft_report(rec["intake"], rec.get("notes", ""), client_ref=cid)
    rec["report"] = {"sections": result["sections"], "approved": False,
                     "red_flag": result.get("red_flag"), "provider": result.get("provider"),
                     "charts": result.get("charts", {}), "language": result.get("language", "de"),
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
    rec["report"]["sections"] = d.get("sections", rec["report"]["sections"])
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
    with _CLIENTS_LOCK:
        data = cfg.clients()
        data.setdefault("clients", {})
        n = 1 + len(data["clients"])
        cid = f"AN-{n:04d}"
        while cid in data["clients"]:
            n += 1
            cid = f"AN-{n:04d}"
        pw = auth.new_password()
        data["clients"][cid] = {"name": name, "email": email, "language": lang,
                                "password": auth.hash_password(pw), "status": "active",
                                "created": _dt.date.today().isoformat(),
                                "consent": {"coaching_not_medical": None, "gdpr_health_data": None, "version": "1.0"}}
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


@app.get("/api/dashboard")
@staff_required
def dashboard():
    recs = store.list_records()
    logins = cfg.clients().get("clients", {})
    by_stage = {}
    for r in recs:
        by_stage[r["stage"]] = by_stage.get(r["stage"], 0) + 1
    return jsonify(total_clients=len(logins), by_stage=by_stage,
                   in_draft=by_stage.get("draft", 0) + by_stage.get("review", 0),
                   sent=by_stage.get("sent", 0) + by_stage.get("done", 0))



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
    try:
        b = booking.book(slot, name, email, language, note)
    except ValueError as e:
        return jsonify(error=str(e)), 409
    # confirmation email (draft/send per email_mode) with .ics
    try:
        import datetime as _d
        from zoneinfo import ZoneInfo
        tz = ZoneInfo(booking.get_availability().get("timezone", "Europe/Madrid"))
        local = _d.datetime.fromisoformat(slot).astimezone(tz)
        when = local.strftime("%A, %d %B %Y · %H:%M ") + f"({booking.get_availability().get('timezone')})"
        ics = booking.ics_for(slot, name, b["id"])
        (cfg.OUTPUT_DIR / "bookings").mkdir(parents=True, exist_ok=True)
        (cfg.OUTPUT_DIR / "bookings" / f"{b['id']}.ics").write_bytes(ics)
        msg = mailer.build_booking_email(email, name, when, language, ics, b["id"])
        delivery = mailer.deliver(msg, "bookings")
    except Exception as e:
        app.logger.exception("booking email failed")
        delivery = {"email": f"failed: {e}"}
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
    backup.start_scheduler() # hourly encrypted backup outside the repo (if configured)
    c = cfg.config()
    app.run(host=c.get("host", "127.0.0.1"), port=int(os.environ.get("AURALIS_PORT", c.get("port", 5056))), debug=False)


if __name__ == "__main__":
    main()
