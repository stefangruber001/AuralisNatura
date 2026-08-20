#!/usr/bin/env python3
"""Stripe → portal: the loop that used to be open.

Before this, money arrived in Stripe and nothing told the portal — `paid` was a
checkbox a human ticked. These checks cover the ways an automatic ingress can go
wrong when real money is involved: a forged signature, a replayed request, a
retry that rotates the password out from under the mail already sent, and a
payment nobody can match to a package.
"""
from __future__ import annotations
import hashlib
import hmac
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import _sandbox  # noqa: E402,F401
import os  # noqa: E402
os.environ.setdefault("AURALIS_API_KEY", "test-key")

from lib import cfg, store  # noqa: E402
cfg.reset_caches()

SECRET = "whsec_test_secret_for_the_suite"
FAILS: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    print(f"  {'ok  ' if ok else 'FAIL'} {label}" + (f"\n         {detail}" if detail and not ok else ""))
    if not ok:
        FAILS.append(label)


def signed(body: dict, secret: str = SECRET, age: int = 0) -> tuple[bytes, dict]:
    raw = json.dumps(body).encode()
    ts = int(time.time()) - age
    sig = hmac.new(secret.encode(), f"{ts}.".encode() + raw, hashlib.sha256).hexdigest()
    return raw, {"Stripe-Signature": f"t={ts},v1={sig}", "Content-Type": "application/json"}


def event(eid: str, *, email: str = "kaeuferin@test.de", name: str = "Käuferin Test",
          cents: int = 19900, package: str | None = None,
          kind: str = "checkout.session.completed") -> dict:
    obj: dict = {"amount_total": cents, "currency": "eur", "locale": "de",
                 "customer_details": {"email": email, "name": name}}
    if package is not None:
        obj["metadata"] = {"package": package}
    return {"id": eid, "type": kind, "data": {"object": obj}}


def run() -> int:
    # the secret is env-only in production; inject it into the cached config here
    cfg.config()["stripe_webhook_secret"] = SECRET
    cfg.config()["shop_enabled"] = True
    from server.app import app
    c = app.test_client()

    print("· the shop switch decides whether a buy link is ever handed out")
    cfg.config()["shop_enabled"] = False
    offers = c.get("/api/app/offers").get_json()["offers"]
    check("with the shop off every buy_url is blank",
          all(not o.get("buy_url") for o in offers), str(offers))
    check("prices are still shown so the app can present the programmes",
          all(o.get("price", 0) > 0 for o in offers))
    check("the corporate offer is never in the buyable list",
          not any(o.get("key") == "grove" for o in offers))
    cfg.config()["shop_enabled"] = True
    on = c.get("/api/app/offers").get_json()["offers"]
    check("with the shop on the configured links come back",
          any(o.get("buy_url") for o in on))

    print("\n· a request that is not provably from Stripe changes nothing")
    raw, hdr = signed(event("evt_forged"))
    bad = dict(hdr)
    bad["Stripe-Signature"] = bad["Stripe-Signature"][:-4] + "0000"
    check("a forged signature is refused",
          c.post("/api/stripe/webhook", data=raw, headers=bad).status_code == 400)
    check("a missing signature is refused",
          c.post("/api/stripe/webhook", data=raw,
                 headers={"Content-Type": "application/json"}).status_code == 400)
    raw2, hdr2 = signed(event("evt_wrongsecret"), secret="whsec_not_ours")
    check("a signature from another secret is refused",
          c.post("/api/stripe/webhook", data=raw2, headers=hdr2).status_code == 400)
    raw3, hdr3 = signed(event("evt_replay"), age=3600)
    check("an hour-old signature is refused as a replay",
          c.post("/api/stripe/webhook", data=raw3, headers=hdr3).status_code == 400)
    check("no client was created by any of those",
          not cfg.clients().get("clients"))

    print("\n· a real payment becomes a client with access")
    raw, hdr = signed(event("evt_ok_1", package="bloom", cents=39900,
                            email="wandel@test.de", name="Wandel Kundin"))
    r = c.post("/api/stripe/webhook", data=raw, headers=hdr)
    body = r.get_json() or {}
    cid = body.get("client_id", "")
    check("the webhook accepts it", r.status_code == 200 and body.get("ok"), str(body))
    check("a client id came back", cid.startswith("AN-"), cid)
    info = cfg.clients().get("clients", {}).get(cid, {})
    check("the client is active, not a lead", info.get("status") == "active", str(info.get("status")))
    check("a password hash was set so she can actually sign in",
          bool(info.get("password")))
    rec = store.get(cid) or {}
    check("the package is set from the metadata",
          (rec.get("package") or {}).get("key") == "bloom", str(rec.get("package")))
    check("the price is the configured one, not the raw amount",
          float((rec.get("package") or {}).get("price", 0)) == 399.0)
    check("it is marked paid so revenue reaches the cockpit", rec.get("paid") is True)
    # The webhook sets "won"; _issue_credentials then advances it to "invited",
    # which is what that stage means — access has been sent. Assert the real end
    # state rather than the intermediate one.
    check("the journey reached invited (paid, then access issued)",
          rec.get("stage") == "invited", str(rec.get("stage")))
    check("it is at or past won on the funnel",
          store.stage_index(rec.get("stage", "")) >= store.stage_index("won"))
    trail = " ".join(str(a) for a in (rec.get("meta", {}).get("activity") or []))
    check("the payment is on the record's activity trail", "Stripe" in trail, trail[:120])

    # She is told a sale happened. The console records it either way, but only if
    # she opens it — and a free-call booking already reaches her inbox, so a paid
    # programme has to at least match that.
    inbox = cfg.OUTPUT_DIR / "stripe" / "internal"
    notes = sorted(inbox.glob("notify-*.eml")) if inbox.exists() else []
    # the .eml is quoted-printable; grepping the raw bytes would pass on the
    # headers alone and never actually look at what the mail says
    import email as _email
    body_txt = ""
    if notes:
        m = _email.message_from_bytes(notes[-1].read_bytes())
        body_txt = m.get_payload(decode=True).decode("utf-8", "replace")
    check("a sale notification was written", bool(notes), str(inbox))
    check("it names the buyer, the package and the amount",
          all(t in body_txt for t in ("Wandel Kundin", "wandel@test.de", "399")), body_txt[:200])
    check("it says whether access actually went out",
          ("Zugangsdaten-Mail ist raus" in body_txt) or ("NICHT versendet" in body_txt),
          body_txt[:200])
    check("exactly one mail for one sale — not a second 'by the way'", len(notes) == 1,
          f"{len(notes)} notifications")

    print("\n· a retry must not lock her out of what she just paid for")
    # _issue_credentials rotates the password every call, so a replayed event
    # would invalidate the password the first mail carried.
    pw_before = cfg.clients()["clients"][cid]["password"]
    raw, hdr = signed(event("evt_ok_1", package="bloom", cents=39900,
                            email="wandel@test.de", name="Wandel Kundin"))
    again = c.post("/api/stripe/webhook", data=raw, headers=hdr)
    check("the duplicate event is recognised", (again.get_json() or {}).get("duplicate") is True,
          str(again.get_json()))
    check("her password was NOT rotated by the retry",
          cfg.clients()["clients"][cid]["password"] == pw_before)

    print("\n· the amount resolves the package when metadata is missing")
    raw, hdr = signed(event("evt_amount", cents=89900, email="balance@test.de",
                            name="Balance Kundin"))
    r = c.post("/api/stripe/webhook", data=raw, headers=hdr)
    cid2 = (r.get_json() or {}).get("client_id", "")
    rec2 = store.get(cid2) or {}
    check("899 EUR resolves to flourish",
          (rec2.get("package") or {}).get("key") == "flourish", str(rec2.get("package")))

    print("\n· an unmatchable payment is escalated, never dropped")
    raw, hdr = signed(event("evt_odd", cents=12345, email="odd@test.de", name="Odd Amount"))
    r = c.post("/api/stripe/webhook", data=raw, headers=hdr)
    check("it answers 200 so Stripe stops retrying",
          r.status_code == 200 and (r.get_json() or {}).get("unmatched") is True, str(r.get_json()))
    check("no half-provisioned client was created for it",
          "odd@test.de" not in json.dumps(cfg.clients()))
    raw, hdr = signed(event("evt_noemail", cents=19900, email="", name=""))
    check("a payment without an email is escalated too",
          (c.post("/api/stripe/webhook", data=raw, headers=hdr).get_json() or {}).get("unmatched") is True)

    print("\n· events we do not handle are acknowledged and ignored")
    raw, hdr = signed(event("evt_other", kind="payment_intent.created"))
    r = c.post("/api/stripe/webhook", data=raw, headers=hdr)
    check("an unrelated event type is a no-op 200",
          r.status_code == 200 and (r.get_json() or {}).get("ignored") == "payment_intent.created")

    print("\n· with no secret configured the endpoint refuses to guess")
    cfg.config()["stripe_webhook_secret"] = ""
    raw, hdr = signed(event("evt_nosecret"))
    check("503 rather than accepting anything",
          c.post("/api/stripe/webhook", data=raw, headers=hdr).status_code == 503)
    cfg.config()["stripe_webhook_secret"] = SECRET

    print("\n" + ("STRIPE WEBHOOK ALL PASSED ✓" if not FAILS else f"{len(FAILS)} FAILED: {FAILS}"))
    return 0 if not FAILS else 1


if __name__ == "__main__":
    sys.exit(run())
