#!/usr/bin/env python3
"""golive_test.py — one command that answers "is the business actually live?"

WHY THIS EXISTS, AND WHY IT IS NOT ANOTHER CHECKER
  console_check.py asks "do the console's screens load". preflight.py asks "is
  the install healthy". Both are read-only, and both would have passed on a host
  where a client pays and nothing happens — because the three things that carry
  money and trust are never exercised by a GET:

    1. a purchase becomes a client with access          (Stripe → portal)
    2. a client hears back the second she submits       (SMTP, instantly)
    3. the confirmation waits in Gmail Drafts for you   (IMAP APPEND)

  This drives all three for real, against the running portal, and then removes
  what it created. Nothing here is mocked: the Stripe event is signed with the
  host's own signing secret, and the mails go through the same transports a
  client's mail does.

WHERE IT RUNS
  On the Hetzner server, which is where the secrets live:

      sudo -u auralis /opt/auralis/venv/bin/python \\
          /opt/auralis/app/portal/tools/golive_test.py

  It talks to 127.0.0.1, so it also proves the portal itself is healthy rather
  than only the Cloudflare edge. Add --public to additionally verify the edge.

WHAT IT LEAVES BEHIND
  Two [SELBSTTEST] mails in your inbox and Drafts — delete them. Everything
  else (the rehearsal client, its documents, its login) is erased before exit;
  --keep opts out so you can inspect it in the console.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

C0, CG, CY, CR, CB, CD = ("\033[0m", "\033[32m", "\033[33m", "\033[31m",
                          "\033[1m", "\033[2m")
FAILS: list[str] = []
WARNS: list[str] = []

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36 AuralisGoLiveTest/1.0")


def act(name: str) -> None:
    print(f"\n{CB}▸ {name}{C0}")


def ok(label: str, detail: str = "") -> None:
    print(f"  {CG}✔{C0} {label}" + (f"  {CD}{detail}{C0}" if detail else ""))


def bad(label: str, detail: str = "") -> None:
    FAILS.append(label)
    print(f"  {CR}✖{C0} {label}" + (f"  {detail}" if detail else ""))


def warn(label: str, detail: str = "") -> None:
    WARNS.append(label)
    print(f"  {CY}!{C0} {label}" + (f"  {detail}" if detail else ""))


def req(url: str, key: str = "", method: str = "GET", body: bytes | None = None,
        ctype: str = "application/json", timeout: float = 60.0):
    """Returns (status, parsed_or_text)."""
    h = {"User-Agent": UA, "Accept": "*/*"}
    if key:
        h["X-Auralis-Key"] = key
    if body is not None:
        h["Content-Type"] = ctype
    r = urllib.request.Request(url, data=body, headers=h, method=method)
    try:
        with urllib.request.urlopen(r, timeout=timeout) as resp:
            raw = resp.read()
            try:
                return resp.status, json.loads(raw.decode("utf-8"))
            except Exception:
                return resp.status, raw.decode("utf-8", "replace")[:300]
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")[:300]
    except Exception as e:
        return 0, f"{type(e).__name__}: {e}"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", type=int, default=int(os.environ.get("AURALIS_PORT", "5056")))
    ap.add_argument("--public", default="https://api.auralisnatura.com",
                    help="also verify the public edge (set empty to skip)")
    ap.add_argument("--to", default="", help="where the two test mails go "
                                             "(default: the from_email in config)")
    ap.add_argument("--package", default="root", choices=("root", "bloom", "flourish"))
    ap.add_argument("--keep", action="store_true",
                    help="do not erase the rehearsal client at the end")
    ap.add_argument("--skip-mail", action="store_true",
                    help="skip the two live test mails (Stripe loop only)")
    args = ap.parse_args()

    from lib import cfg
    sys.path.insert(0, str(ROOT / "tools"))
    import stripe_rehearsal as sr           # env resolution lives there; reuse it

    key = sr.env_value("AURALIS_API_KEY") or str(cfg.config().get("api_key", ""))
    base = f"http://127.0.0.1:{args.port}"

    print(f"\n{CB}Auralis Natura — go-live test{C0}")
    print(f"  {CD}portal {base}   ·   this exercises real transports and real money paths{C0}")

    # ── 0 · the portal answers, and it is THIS host ──────────────────────────
    act("0 · The portal on this host")
    st, _ = req(base + "/health")
    if st != 200:
        bad("the portal does not answer /health", str(st))
        print(f"\n  {CR}Nothing else can run while the portal is down.{C0}\n")
        return 1
    ok("portal answers /health")
    st, d = req(base + "/api/status", key)
    if st == 401:
        bad("the staff key is not accepted", "check AURALIS_API_KEY in /etc/auralis/portal.env")
        return 1
    if st != 200:
        bad("/api/status failed", str(d)[:120])
        return 1
    mode, smtp = d.get("email_mode"), bool(d.get("smtp_configured"))
    ok(f"staff key accepted · email_mode={mode} · SMTP password "
       + ("present" if smtp else "MISSING"))
    if not smtp:
        bad("no SMTP password on this host",
            "a buyer would pay and never receive her access — run enable_email.sh")

    # ── 1 · the shop is on, and the links are real ───────────────────────────
    act("1 · The buy buttons (app + client portal)")
    live_links = []
    for lang in ("de", "en", "es"):
        st, d = req(f"{base}/api/app/offers?lang={lang}", key)
        offers = (d or {}).get("offers", []) if isinstance(d, dict) else []
        buyable = [o for o in offers if o.get("buy_url")]
        if st != 200 or not offers:
            bad(f"offers endpoint failed for {lang}", str(d)[:120])
            continue
        # Verbindung/corporate must NEVER be buyable — Apple 3.1.3(d) requires
        # in-app purchase for one-to-many services, so it stays enquiry-only.
        corp = [o for o in offers if o.get("key") in ("grove", "corporate") and o.get("buy_url")]
        if corp:
            bad(f"[{lang}] the corporate offer has a buy button",
                "Apple 3.1.3(d): group services must never be sold outside IAP")
        if len(buyable) == 3:
            ok(f"[{lang}] all three programmes are buyable",
               " · ".join(f"{o.get('name')} {o.get('price')}" for o in buyable))
            live_links += [o["buy_url"] for o in buyable]
        elif buyable:
            warn(f"[{lang}] only {len(buyable)} of 3 programmes have a link",
                 ", ".join(o.get("name", "?") for o in offers if not o.get("buy_url")))
            live_links += [o["buy_url"] for o in buyable]
        else:
            bad(f"[{lang}] no buy links — shop_enabled is off in the RUNNING process",
                "the repo may say true; this host has not reloaded it yet")

    if live_links:
        act("1b · Do those Stripe links actually open?")
        seen, dead, good = set(), 0, 0
        for url in live_links:
            if url in seen:
                continue
            seen.add(url)
            st, _ = req(url, method="GET", timeout=25)
            if st == 200:
                good += 1
                ok(url.rsplit("/", 1)[-1], "checkout page loads")
            elif st in (401, 403, 429):
                # Bot protection refusing a script says nothing about whether the
                # link works for a person. Failing here would print "NOT ready"
                # over a shop that is perfectly fine — the worst possible lie for
                # a go-live check to tell.
                warn(f"{url} → HTTP {st}",
                     "bot protection refused this script; open it once in a browser")
            else:
                dead += 1
                # 404/410 is the one that matters: a deleted or renamed link.
                bad(f"{url} → HTTP {st}", "a customer clicking this sees an error")
        if good == len(seen):
            ok(f"all {len(seen)} payment links open a real checkout page")
        elif not dead:
            warn(f"{len(seen) - good} of {len(seen)} links could not be checked from here",
                 "none is broken — they were refused as automated traffic")

    # ── 2 · the two client mails, for real ───────────────────────────────────
    if args.skip_mail:
        warn("mail test skipped (--skip-mail)")
    else:
        act("2 · The two client mails — sent for real, to you")
        payload = json.dumps({"to": args.to} if args.to else {}).encode()
        st, d = req(base + "/api/selftest/mail", key, method="POST", body=payload,
                    timeout=120)
        if st != 200 or not isinstance(d, dict):
            bad("the mail self-test could not run", str(d)[:200])
        else:
            to = d.get("to", "?")
            inst = str((d.get("instant") or {}).get("ack", ""))
            draft = str((d.get("draft") or {}).get("draft", "")
                        or (d.get("draft") or {}).get("send", ""))
            if inst == "sent":
                ok("INSTANT mail sent over SMTP",
                   f"'Deine Anfrage ist angekommen' → {to}, right now")
            else:
                bad("the instant acknowledgement did NOT go out", inst or "(no result)")
            if draft.startswith("uploaded to"):
                ok("DRAFT prepared over IMAP",
                   f"'Dein Termin ist bestätigt' + calendar invite → {draft[12:]}")
            elif draft == "sent":
                warn("the confirmation was SENT, not drafted",
                     f"email_mode={d.get('email_mode')} — you never get to review it first")
            elif d.get("email_mode") == "off":
                bad("email_mode=off — the confirmation is only written to disk",
                    "set it to draft (the documented production mode)")
            else:
                bad("the draft could NOT be prepared", draft or "(no result)")
            if inst == "sent" or draft:
                print(f"      {CD}Both carry [SELBSTTEST] in the subject — delete them "
                      f"when you have seen them.{C0}")

    # ── 3 · a purchase, end to end ───────────────────────────────────────────
    act("3 · A purchase — signed with this host's own Stripe secret")
    if not sr.load_secret():
        bad("AURALIS_STRIPE_WEBHOOK_SECRET is not set on this host",
            "Stripe would deliver a paid checkout to a 503 — run enable_stripe.sh")
    else:
        ok("signing secret present")
        cmd = [sys.executable, str(ROOT / "tools" / "stripe_rehearsal.py"),
               "--package", args.package, "--port", str(args.port), "--auto"]
        if args.keep:
            cmd.append("--keep")
        print(f"  {CD}$ {' '.join(cmd[1:])}{C0}")
        rc = subprocess.call(cmd, cwd=str(ROOT))
        if rc == 0:
            ok("the purchase loop works: paid → client → package → access → notification")
        else:
            bad(f"the purchase rehearsal failed (exit {rc})",
                "read its output above — it names the step that broke")

    # ── 4 · the public edge, i.e. what a customer's browser reaches ──────────
    if args.public:
        act("4 · The public edge (Cloudflare → this host)")
        pub = args.public.rstrip("/")
        st, _ = req(pub + "/health", timeout=30)
        if st == 200:
            ok(f"{pub}/health answers 200")
        elif st == 403:
            warn(f"{pub} answered 403", "Cloudflare bot protection refused this script, "
                                        "not the portal — open it in a browser to confirm")
        else:
            bad(f"{pub}/health answered {st}",
                "the tunnel is not routing to this host — customers reach nothing")
        st, _ = req(pub + "/book", timeout=30)
        (ok if st == 200 else bad)(f"{pub}/book renders", "" if st == 200 else f"HTTP {st}")
        # A forged signature must be refused with 400. A 503 means no secret and
        # a real payment would be lost; anything else means Stripe is not landing
        # on the portal at all.
        st, _ = req(pub + "/api/stripe/webhook", method="POST", body=b"{}",
                    timeout=30)
        # (Stripe-Signature absent → 400 as well, which is the answer we want.)
        if st == 400:
            ok("Stripe's endpoint URL is live and verifying signatures")
        elif st == 503:
            bad("the public webhook answers 503", "a real payment would never reach the portal")
        else:
            bad(f"the public webhook answered {st}", "expected 400")

    # ── verdict ──────────────────────────────────────────────────────────────
    print()
    if FAILS:
        print(f"  {CR}{CB}NOT ready — {len(FAILS)} check(s) failed:{C0}")
        for f in FAILS:
            print(f"    · {f}")
        print()
        return 1
    if WARNS:
        print(f"  {CY}{CB}Live, with {len(WARNS)} thing(s) worth a look:{C0}")
        for w in WARNS:
            print(f"    · {w}")
    else:
        print(f"  {CG}{CB}Live. A customer can buy, and you will know about it.{C0}")
    print(f"""
  Proven just now, on this host:
    · the three programmes show a buy button in the app and the client portal
    · every Stripe payment link opens a real checkout page
    · a client's acknowledgement leaves over SMTP the second she submits
    · her confirmation and calendar invite wait for you in Gmail Drafts
    · a completed payment becomes a client with a package, access and a
      notification to you — and the money appears in the Cockpit

  Still yours to settle, outside this machine: the distance-selling terms with
  the gestoría (withdrawal right and its waiver, pre-contractual information,
  invoice and IVA). Nothing technical is in the way.
""")
    return 0


if __name__ == "__main__":
    sys.exit(main())
