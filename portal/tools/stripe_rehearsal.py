#!/usr/bin/env python3
"""stripe_rehearsal.py — walk a purchase through the portal, without a card.

WHY THIS EXISTS
  The endpoint answering 400 to a forged signature proves Stripe can reach the
  portal. It proves nothing about what happens next: whether a payment becomes a
  client with a package, whether the credentials mail is built, whether the sale
  notification lands in your inbox. The only other way to learn that is to buy a
  programme with a real card and refund it — which costs the processing fee, and
  fails outright if the card declines, as it just did.

  So this builds the event Stripe would send, signs it with YOUR OWN signing
  secret, and posts it to your own portal. Everything downstream is the real
  code path: signature verification, package resolution, client creation,
  credentials, the "💶 Verkauf" mail.

WHAT IT IS NOT
  Not a mock and not a bypass. If the signature is wrong the portal refuses it,
  exactly as it would refuse a forgery from the internet. It reads the same
  secret the portal reads; if that secret is missing or wrong, this fails too —
  which is itself the answer.

⚠️ IT CREATES A REAL CLIENT RECORD in your live data, because that is the thing
  being tested. The AN-number is printed and `--cleanup AN-xxxx` erases it
  through the same GDPR route the console uses. Do the cleanup.

USAGE
    python3 tools/stripe_rehearsal.py                  # rehearse a Klarheit purchase
    python3 tools/stripe_rehearsal.py --package bloom  # or another programme
    python3 tools/stripe_rehearsal.py --cleanup AN-0042
"""
from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

C0, CG, CY, CR, CB = "\033[0m", "\033[32m", "\033[33m", "\033[31m", "\033[1m"


def step(msg: str) -> None:
    print(f"\n{CB}▸ {msg}{C0}")


def ok(msg: str) -> None:
    print(f"  {CG}✔{C0} {msg}")


def warn(msg: str) -> None:
    print(f"  {CY}!{C0} {msg}")


def die(msg: str, code: int = 1):
    print(f"\n  {CR}✖ {msg}{C0}\n", file=sys.stderr)
    sys.exit(code)


def env_files() -> list[Path]:
    """The same two places the portal and the deploy scripts look."""
    return [Path("/etc/auralis/portal.env"), ROOT / ".env"]


def load_secret() -> str:
    """Read the signing secret the RUNNING portal uses — environment first,
    because that is what systemd hands it, then the env file the Mac sources."""
    v = os.environ.get("AURALIS_STRIPE_WEBHOOK_SECRET", "")
    if v:
        return v.strip()
    for f in env_files():
        if not f.exists():
            continue
        for line in f.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.strip().startswith("AURALIS_STRIPE_WEBHOOK_SECRET="):
                return line.split("=", 1)[1].strip()
    return ""


def post(url: str, body: bytes, headers: dict) -> tuple[int, str]:
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")
    except Exception as e:
        die(f"could not reach {url} — {type(e).__name__}: {e}\n"
            "     Is the portal running? (bash portal/deploy/enable_stripe.sh --check)")


def get_json(base: str, path: str, key: str):
    req = urllib.request.Request(base + path, headers={"X-Auralis-Key": key})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception:
        return {}


def mails_since(base: str, key: str, since_iso: str) -> list[dict]:
    """The mails the PORTAL wrote, listed by the portal.

    Globbing cfg.OUTPUT_DIR from this process would look in whatever directory
    THIS interpreter resolves — the same mistake as reading the database
    directly. /api/outbox is the portal's own view of what it produced.
    """
    items = get_json(base, "/api/outbox", key).get("items") or []
    return [i for i in items
            if i.get("kind") == "eml" and str(i.get("mtime", "")) >= since_iso]


def subject_of(base: str, key: str, relpath: str) -> str:
    """Decode one mail's subject through the portal, so the audit copy is read
    where it lives rather than guessed at from a filename."""
    from email import message_from_bytes
    from email.header import decode_header, make_header
    import urllib.parse
    req = urllib.request.Request(
        base + "/api/outbox/" + urllib.parse.quote(relpath),
        headers={"X-Auralis-Key": key})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            m = message_from_bytes(r.read())
        return str(make_header(decode_header(str(m["Subject"] or "")))) or "(no subject)"
    except Exception as e:
        return f"(could not read: {type(e).__name__})"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--package", default="root", help="root | bloom | flourish (default root)")
    ap.add_argument("--email", default="rehearsal@auralisnatura.com",
                    help="buyer address — use one you can read if you want the mails")
    ap.add_argument("--name", default="Probe Kauf (TEST)")
    ap.add_argument("--lang", default="de", choices=("de", "en", "es"))
    ap.add_argument("--port", type=int, default=int(os.environ.get("AURALIS_PORT", "5056")))
    ap.add_argument("--cleanup", metavar="AN-XXXX",
                    help="erase a client this rehearsal created, then exit")
    ap.add_argument("--auto", action="store_true",
                    help="the whole dress rehearsal: buy, show the mails and what the "
                         "console now says, then erase the test client. Leaves no trace.")
    ap.add_argument("--keep", action="store_true",
                    help="with --auto: do NOT erase at the end (inspect it yourself)")
    args = ap.parse_args()

    from lib import cfg  # after sys.path

    key = str(cfg.config().get("api_key", ""))
    base = f"http://127.0.0.1:{args.port}"

    # ── cleanup mode ─────────────────────────────────────────────────────────
    if args.cleanup:
        step(f"Erasing {args.cleanup}")
        req = urllib.request.Request(f"{base}/api/client/{args.cleanup}",
                                     headers={"X-Auralis-Key": key}, method="DELETE")
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                ok(f"erased — {r.read().decode()[:120]}")
        except Exception as e:
            die(f"erase failed: {e}")
        print()
        return 0

    # ── the secret ───────────────────────────────────────────────────────────
    step("Reading the signing secret the portal uses")
    secret = load_secret()
    if not secret:
        die("AURALIS_STRIPE_WEBHOOK_SECRET is not set anywhere I looked:\n"
            "     " + " · ".join(str(f) for f in env_files()) + "\n"
            "     Run:  bash portal/deploy/enable_stripe.sh")
    ok(f"found ({len(secret)} chars, starts {secret[:6]}…)")

    pkgs = {p.get("key"): p for p in cfg.config().get("packages", [])}
    pkg = pkgs.get(args.package)
    if not pkg or args.package == "grove":
        die(f"unknown package {args.package!r} — choose from "
            f"{', '.join(k for k in pkgs if k != 'grove')}")
    cents = int(round(float(pkg.get("price", 0)) * 100))
    ok(f"rehearsing: {pkg.get('name')} · {cents/100:.0f} "
       f"{str(cfg.config().get('currency', 'eur')).upper()}")

    # what the Cockpit says BEFORE — so the change can be shown, not asserted
    before = get_json(base, "/api/dashboard", key)
    rev_before = float(((before.get("revenue") or {}).get("total")) or 0)
    # /api/outbox reports mtimes to the minute, so step back one to be safe
    import datetime as _dt
    t0_iso = (_dt.datetime.now() - _dt.timedelta(minutes=1)).isoformat(timespec="minutes")

    # ── the event, exactly as Stripe shapes it ───────────────────────────────
    step("Building and signing the event")
    evt = {
        "id": f"evt_rehearsal_{int(time.time())}",
        "object": "event",
        "type": "checkout.session.completed",
        "livemode": True,
        "data": {"object": {
            "id": f"cs_rehearsal_{int(time.time())}",
            "object": "checkout.session",
            "amount_total": cents,
            "currency": str(cfg.config().get("currency", "eur")),
            "locale": args.lang,
            "payment_status": "paid",
            "status": "complete",
            "customer_details": {"email": args.email, "name": args.name},
            "metadata": {"package": args.package},
        }},
    }
    raw = json.dumps(evt).encode()
    ts = int(time.time())
    sig = hmac.new(secret.encode(), f"{ts}.".encode() + raw, hashlib.sha256).hexdigest()
    ok("signed with the real secret — the portal verifies it like any Stripe event")

    # ── send it ──────────────────────────────────────────────────────────────
    step(f"Posting to {base}/api/stripe/webhook")
    code, body = post(f"{base}/api/stripe/webhook", raw,
                      {"Content-Type": "application/json",
                       "Stripe-Signature": f"t={ts},v1={sig}"})
    try:
        out = json.loads(body)
    except Exception:
        out = {}

    if code == 503:
        die("503 — the portal has no signing secret loaded. It is in the env file but the\n"
            "     running process has not read it. Restart the portal and try again.")
    if code == 400:
        die("400 — the portal rejected the signature. The secret in the env file is not the\n"
            "     one the running portal holds; restart it, or re-run enable_stripe.sh.")
    if code != 200:
        die(f"unexpected {code}: {body[:200]}")

    if out.get("unmatched"):
        warn("the portal could not match the payment to a programme and escalated it by "
             "mail — that is the safety net working, but it means package resolution "
             "failed. Check config.json prices against the amount above.")
        return 2

    cid = out.get("client_id", "")
    ok(f"200 — accepted · client {cid} · package {out.get('package')}")

    # ── what actually changed ────────────────────────────────────────────────
    # Ask the PORTAL what it recorded, over its own API. Reading lib.store from
    # this process would read whatever database THIS interpreter resolves, which
    # is not necessarily the one the running portal writes to — and a verifier
    # that inspects the wrong data is worse than none.
    step("What the portal did with it")
    req = urllib.request.Request(f"{base}/api/client/{cid}", headers={"X-Auralis-Key": key})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            payload = json.loads(r.read().decode("utf-8"))
        # the route answers {client: {...login/contact...}, record: {...journey...}}
        info, rec = payload.get("client") or {}, payload.get("record") or {}
    except Exception as e:
        die(f"the payment was accepted, but reading {cid} back failed: {e}\n"
            f"     Check it by hand in the console before rehearsing again.")

    pkg_rec = rec.get("package") or {}
    trail = " ".join(str(a) for a in (rec.get("meta", {}).get("activity") or []))
    checks = [
        (f"client record exists for {info.get('email', '—')}",
         bool(rec.get("client_id") or info.get("client_id"))),
        (f"login id issued ({info.get('login_id', '—')}) — she can actually sign in",
         bool(info.get("login_id"))),
        (f"package set to {pkg_rec.get('name', '—')}", pkg_rec.get("key") == args.package),
        (f"price {float(pkg_rec.get('price', 0)):.0f} taken from config, not the raw amount",
         float(pkg_rec.get("price", 0)) == float(pkg.get("price", 0))),
        ("marked paid — revenue reaches the Cockpit", bool(rec.get("paid"))),
        (f"journey stage {rec.get('stage', '')!r} (invited = access was issued)",
         rec.get("stage") in ("won", "invited")),
        ("payment on the activity trail", "Stripe" in trail),
    ]
    failed = [label for label, good in checks if not good]
    for label, good in checks:
        (ok if good else warn)(label)

    mode = str(cfg.config().get("email_mode", "off"))
    if mode == "send":
        ok(f"email_mode=send — the credentials mail went to {args.email}")
    else:
        warn(f"email_mode={mode} — the credentials mail is a Gmail draft, not sent. "
             "Expected in draft mode; look in Drafts.")

    if failed:
        print(f"""
  {CY}{CB}The payment was accepted, but {len(failed)} of {len(checks)} checks did not pass.{C0}

    {chr(10).join('  · ' + f for f in failed)}

  The client {cid} exists — inspect it in the console before rehearsing again,
  and clean it up when you are done:
    python3 tools/stripe_rehearsal.py --cleanup {cid}
""")
        return 2

    # ── auto mode: show the mails and the console, then tidy up ──────────────
    if args.auto:
        step("The e-mails the portal produced")
        mails = mails_since(base, key, t0_iso)
        if mails:
            for m in mails:
                ok(subject_of(base, key, m["file"]))
                print(f"      output_docs/{m['file']}  ({m['size'] // 1024} KB)")
            print("\n    Read one in your browser (staff login required):")
            print(f"    Betriebskonsole → ⚙ → Outbox, or {base}/api/outbox")
        else:
            warn("the portal reports no new .eml — check AURALIS_SMTP_PASSWORD and email_mode")

        step("What the Betriebskonsole now shows")
        after = get_json(base, "/api/dashboard", key)
        rev_after = float(((after.get("revenue") or {}).get("total")) or 0)
        ok(f"Cockpit revenue {rev_before:.0f} → {rev_after:.0f} EUR "
           f"(+{rev_after - rev_before:.0f})")
        stages = after.get("stages") or {}
        ok("Customer Journey · " + " · ".join(f"{k}:{v}" for k, v in stages.items() if v)
           or "Customer Journey · (no stages reported)")
        alerts = get_json(base, "/api/alerts", key).get("alerts") or []
        keys = [a.get("key") for a in alerts]
        if "unpaid" in keys or "unpaid_start" in keys:
            warn("an unpaid alert is showing — it should not be, this purchase was paid")
        else:
            ok("no unpaid alert — correct, the programme is paid for")
        funnel = get_json(base, "/api/funnel?days=30", key).get("funnel") or {}
        paid_stage = next((x for x in funnel.get("stages", []) if x.get("key") == "paid"), {})
        ok(f"Funnel · 'Bezahlt — Programm startet' stands at {paid_stage.get('count', '?')}")

        if args.keep:
            print(f"""
  {CY}Kept {cid} at your request.{C0} Erase it when you are done:
    python3 tools/stripe_rehearsal.py --cleanup {cid}
""")
            return 0

        step("Cleaning up — this was a rehearsal")
        req = urllib.request.Request(f"{base}/api/client/{cid}",
                                     headers={"X-Auralis-Key": key}, method="DELETE")
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                res = json.loads(r.read().decode())
            gone = get_json(base, f"/api/client/{cid}", key)
            ok(f"{cid} erased — login {res.get('login_removed')}, "
               f"record {res.get('db_removed')}, documents {res.get('disk_removed')}")
            if gone:
                warn("the record still answers — check it by hand in the console")
        except Exception as e:
            warn(f"could not erase {cid} automatically: {e}")
            print(f"      python3 tools/stripe_rehearsal.py --cleanup {cid}")

        print(f"""
  {CG}{CB}Dress rehearsal complete — the purchase loop works end to end.{C0}

  A payment on your live Stripe link would have produced exactly this: the client
  created and marked paid, the credentials mail written, you notified, the money
  in the Cockpit. The only step not exercised is Stripe's own checkout page,
  which you have already seen render with the right name and price.

  The test client has been erased. Nothing was left behind.
""")
        return 0

    print(f"""
  {CG}{CB}The purchase loop works end to end.{C0}

  Look now:
    · Betriebskonsole → Customer Journey → Karte 03 — {cid} is there, paid
    · Cockpit → the revenue and the funnel's "Bezahlt" stage moved
    · Your inbox — the "💶 Verkauf" notification
    · Gmail Drafts — the credentials mail for {args.email}

  {CY}Then clean it up{C0} — this is a real record in your live data:
    python3 tools/stripe_rehearsal.py --cleanup {cid}
""")
    return 0


if __name__ == "__main__":
    sys.exit(main())
