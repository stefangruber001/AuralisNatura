"""Auralis Natura — portal + Betriebskonsole + Cloud Report Agent API.

One Flask app. Binds to 127.0.0.1 only; the internet reaches it exclusively
through the Cloudflare tunnel, and /staff sits behind Cloudflare Access.

Auth:
  [P] client  -> Bearer token (Authorization: Bearer <token>) from /api/login
  [K] staff   -> X-Auralis-Key header (behind Cloudflare Access in prod)
  [-] public  -> pages + health
"""
from __future__ import annotations
import sys, functools, shutil, threading, datetime as _dt
from pathlib import Path
from flask import Flask, request, jsonify, Response, send_file

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from lib import cfg, store, auth, agent, render, mailer  # noqa: E402

app = Flask(__name__)
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
    return request.get_json(silent=True) or {}


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
    d = _json()
    cid = str(d.get("client_id", "")).strip()
    pw = str(d.get("password", ""))
    rec = cfg.clients().get("clients", {}).get(cid)
    if not rec or rec.get("status") == "disabled":
        auth.verify_password(pw, _DUMMY_HASH)   # equalise timing to avoid user enumeration
        return jsonify(error="invalid credentials"), 401
    if not auth.verify_password(pw, rec.get("password", "")):
        return jsonify(error="invalid credentials"), 401
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
    if store.stage_index(rec.get("stage", "invited")) > store.stage_index("intake"):
        return jsonify(error="intake already submitted — please contact team@auralisnatura.com to change it"), 409
    rec["intake"] = d
    rec["meta"]["intake_submitted"] = store._now()
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
    store.upsert(rec)
    if rec["report"]["approved"]:
        store.set_stage(cid, "review")
    return jsonify(ok=True, approved=rec["report"]["approved"])


@app.post("/api/client/<cid>/generate")
@staff_required
def generate(cid):
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
    failed = any(str(v).startswith("failed") for v in delivery.values())
    rec["report"]["generated_at"] = store._now()
    store.upsert(rec)
    if not failed:
        store.set_stage(cid, "sent")
    return jsonify(ok=(not failed), pdf=str(produced.name), delivery=delivery)


@app.get("/api/client/<cid>/report.pdf")
@staff_required
def download_report(cid):
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
    store.ensure(cid)
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


def main():
    cfg.validate_secrets()   # fail closed if prod secrets are missing/default
    c = cfg.config()
    app.run(host=c.get("host", "127.0.0.1"), port=int(c.get("port", 5056)), debug=False)


if __name__ == "__main__":
    main()
