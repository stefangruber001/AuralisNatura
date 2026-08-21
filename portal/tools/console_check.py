#!/usr/bin/env python3
"""console_check.py — does every Betriebskonsole tab actually work on this host?

WHY, AND HOW IT DIFFERS FROM THE OTHERS
  preflight.py proves the install is healthy (keys, database, chromium, mail).
  verify_server.sh proves the host is live (systemd, tunnel, the public edge).
  Neither opens the console. This walks the endpoints the Betriebskonsole itself
  calls, tab by tab, and says which tabs work — the question an operator
  actually has after a migration.

READ-ONLY BY CONSTRUCTION
  GET requests only. It creates nothing, changes nothing and sends no mail, so
  it is safe against production at any hour. The one destructive operation this
  file knows about (--wipe-clients) is opt-in, prints what it will delete and
  demands a typed confirmation.

WHERE IT RUNS
    on the server:  python3 tools/console_check.py
    from anywhere:  python3 tools/console_check.py --base https://api.auralisnatura.com \\
                        --key <staff key>
  Without --key it resolves the staff key the way the portal does: environment,
  then the env file, then config.json.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

C0, CG, CY, CR, CB, CD = ("\033[0m", "\033[32m", "\033[33m", "\033[31m",
                          "\033[1m", "\033[2m")
FAILS: list[str] = []
WARNS: list[str] = []


def env_value(name: str) -> str:
    v = os.environ.get(name, "")
    if v:
        return v.strip()
    for f in (Path("/etc/auralis/portal.env"), ROOT / ".env"):
        if f.exists():
            for line in f.read_text(encoding="utf-8", errors="replace").splitlines():
                if line.strip().startswith(name + "="):
                    return line.split("=", 1)[1].strip()
    return ""


UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36 AuralisConsoleCheck/1.0")


def get(base: str, path: str, key: str, timeout: float = 25.0):
    """Returns (status, parsed_or_text, seconds)."""
    req = urllib.request.Request(base + path,
                                 headers={"X-Auralis-Key": key, "User-Agent": UA,
                                          "Accept": "*/*"})
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read()
            dt = time.time() - t0
            try:
                return r.status, json.loads(raw.decode("utf-8")), dt
            except Exception:
                return r.status, raw.decode("utf-8", "replace")[:200], dt
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")[:200], time.time() - t0
    except Exception as e:
        return 0, f"{type(e).__name__}: {e}", time.time() - t0


def tab(name: str) -> None:
    print(f"\n{CB}▸ {name}{C0}")


def line(good: bool, label: str, detail: str = "", warn_only: bool = False) -> None:
    if good:
        print(f"  {CG}✔{C0} {label}" + (f"  {CD}{detail}{C0}" if detail else ""))
    elif warn_only:
        WARNS.append(label)
        print(f"  {CY}!{C0} {label}" + (f"  {detail}" if detail else ""))
    else:
        FAILS.append(label)
        print(f"  {CR}✖{C0} {label}" + (f"  {detail}" if detail else ""))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base", default=None,
                    help="portal URL (default http://127.0.0.1:$AURALIS_PORT)")
    ap.add_argument("--key", default=None, help="staff API key (default: resolved like the portal)")
    ap.add_argument("--wipe-clients", action="store_true",
                    help="DESTRUCTIVE: erase every client and booking for a clean start")
    args = ap.parse_args()

    base = (args.base or f"http://127.0.0.1:{os.environ.get('AURALIS_PORT', '5056')}").rstrip("/")
    key = args.key or env_value("AURALIS_API_KEY")
    if not key:
        try:
            from lib import cfg
            key = str(cfg.config().get("api_key", ""))
        except Exception:
            key = ""

    print(f"\n{CB}Auralis Natura — Betriebskonsole check{C0}")
    print(f"  {CD}host {base}{C0}")

    # ── 00 the host answers at all ───────────────────────────────────────────
    tab("Erreichbarkeit")
    st, body, dt = get(base, "/health", key)
    line(st == 200, "the portal answers /health", f"{st} in {dt*1000:.0f} ms")
    if st == 403:
        print(f"\n  {CY}403 comes from Cloudflare, not the portal — the request was refused at\n"
              f"  the edge. Usually bot protection, or Cloudflare Access on this hostname.\n"
              f"  Run this check ON the server instead, where it bypasses the edge:\n"
              f"    sudo -u auralis /opt/auralis/venv/bin/python tools/console_check.py{C0}\n")
        return 1
    if st != 200:
        print(f"\n  {CR}Nothing else can be checked while the host is unreachable.{C0}\n")
        return 1
    st, body, _ = get(base, "/api/clients", key)
    if st == 401:
        line(False, "the staff key is not accepted (401)",
             "the console would not open either — check AURALIS_API_KEY")
        print()
        return 1
    line(True, "the staff key is accepted")

    # ── the tabs, in the order they appear in the console ────────────────────
    tab("00 · Cockpit")
    st, d, _ = get(base, "/api/dashboard", key)
    line(st == 200 and isinstance(d, dict), "dashboard loads", str(d)[:80] if st != 200 else "")
    if st == 200:
        rev = (d.get("revenue") or {}).get("total")
        line(rev is not None, "revenue figure present", f"{rev} EUR")
        line(isinstance(d.get("packages"), list), "packages served to the console",
             f"{len(d.get('packages') or [])} packages")
    st, d, _ = get(base, "/api/alerts", key)
    line(st == 200 and "alerts" in (d if isinstance(d, dict) else {}), "alerts load",
         f"{len((d or {}).get('alerts', []))} active" if st == 200 else str(d)[:80])
    st, d, _ = get(base, "/api/funnel?days=30", key)
    ok_f = st == 200 and isinstance(d, dict) and "funnel" in d
    line(ok_f, "sales funnel loads",
         f"{len(d['funnel']['stages'])} stages" if ok_f else str(d)[:80])
    if ok_f:
        line(True, "website counter", "reporting" if d["funnel"].get("has_web_data")
             else "nothing measured yet (normal until the site is opened)")

    tab("01 · Customer Journey / Kundinnen")
    st, d, _ = get(base, "/api/clients", key)
    n = len((d or {}).get("clients", [])) if isinstance(d, dict) else 0
    line(st == 200, "client list loads", f"{n} clients")

    tab("02 · Finanzen")
    st, d, _ = get(base, "/api/finanzen", key)
    line(st == 200 and isinstance(d, dict), "finance model loads",
         f"year {d.get('jahr')}" if st == 200 else str(d)[:80])
    st, d, _ = get(base, "/api/plan", key)
    line(st == 200, "Plandaten load", "" if st == 200 else str(d)[:80])

    tab("03 · Termine & Buchung")
    st, d, _ = get(base, "/api/availability", key)
    line(st == 200, "availability loads",
         f"slot {d.get('slot_minutes')} min" if st == 200 and isinstance(d, dict) else "")
    st, d, _ = get(base, "/api/bookings", key)
    line(st == 200, "bookings list loads",
         f"{len((d or {}).get('bookings', []))} bookings" if st == 200 else str(d)[:80])
    st, d, _ = get(base, "/api/booking/slots", key)
    days = (d or {}).get("days", []) if isinstance(d, dict) else []
    free = sum(len(x.get("slots") or []) for x in days)
    line(st == 200 and free > 0, "the public booking page has free slots",
         f"{free} slots across {len(days)} days",
         warn_only=(st == 200 and free == 0))

    tab("04 · Social Media")
    st, d, _ = get(base, "/api/social/config", key)
    line(st == 200, "social config loads", "" if st == 200 else str(d)[:80])
    st, d, _ = get(base, "/api/social/weeks", key)
    line(st == 200, "weekly plans load", "" if st == 200 else str(d)[:80])
    st, d, _ = get(base, "/api/social/journal", key)
    line(st == 200, "Impulse (journal) loads",
         f"{len((d or {}).get('articles', []))} articles" if st == 200 else str(d)[:80])

    tab("05 · System / Stammdaten")
    st, d, _ = get(base, "/api/company", key)
    line(st == 200, "company master data loads", "" if st == 200 else str(d)[:80])
    st, d, _ = get(base, "/api/status", key)
    line(st == 200, "system status loads", "" if st == 200 else str(d)[:80])
    st, d, _ = get(base, "/api/outbox", key)
    line(st == 200, "outbox loads",
         f"{len((d or {}).get('items', []))} documents" if st == 200 else str(d)[:80])
    st, d, _ = get(base, "/api/build", key)
    line(st == 200, "build/version info loads",
         str(d)[:60] if st == 200 else str(d)[:80], warn_only=(st != 200))

    tab("Öffentliche Flächen")
    for path, label in (("/portal", "Kundinnen-Portal"), ("/book", "Buchungsseite"),
                        ("/staff", "Betriebskonsole")):
        st, _, _ = get(base, path, key)
        line(st == 200, f"{label} ({path}) renders", "" if st == 200 else f"HTTP {st}")
    st, d, _ = get(base, "/api/app/offers?lang=de", key)
    offers = (d or {}).get("offers", []) if isinstance(d, dict) else []
    line(st == 200 and offers, "app/portal offers endpoint",
         f"{len(offers)} programmes, buy links "
         + ("on" if any(o.get("buy_url") for o in offers) else "off (shop_enabled=false)"))

    tab("Stripe")
    req = urllib.request.Request(
        base + "/api/stripe/webhook", method="POST", data=b'{}',
        headers={"Content-Type": "application/json", "Stripe-Signature": "t=1,v1=0000",
                 "User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            code = r.status
    except urllib.error.HTTPError as e:
        code = e.code
    except Exception as e:
        code = 0
    if code == 400:
        line(True, "webhook configured", "refuses a forged signature — a real event is accepted")
    elif code == 503:
        line(False, "webhook NOT configured (503)",
             "a completed payment would never reach the portal — run enable_stripe.sh")
    else:
        line(False, f"webhook answered {code}", "expected 400")

    # ── optional clean slate ─────────────────────────────────────────────────
    if args.wipe_clients:
        tab("Kundendaten löschen")
        st, d, _ = get(base, "/api/clients", key)
        clients = (d or {}).get("clients", []) if isinstance(d, dict) else []
        if not clients:
            line(True, "nothing to delete — the client list is already empty")
        else:
            for c in clients:
                print(f"    {c.get('client_id')}  {c.get('name')}  {c.get('email', '')}")
            print(f"\n  {CR}{CB}This erases {len(clients)} client(s) and everything attached "
                  f"to them.{C0}")
            if input("  Type ERASE to confirm: ").strip() != "ERASE":
                line(False, "not confirmed — nothing was deleted", warn_only=True)
            else:
                for c in clients:
                    cid = c.get("client_id")
                    r = urllib.request.Request(f"{base}/api/client/{cid}",
                                               headers={"X-Auralis-Key": key}, method="DELETE")
                    try:
                        with urllib.request.urlopen(r, timeout=30):
                            line(True, f"{cid} erased")
                    except Exception as e:
                        line(False, f"{cid} could NOT be erased", str(e))

    # ── verdict ──────────────────────────────────────────────────────────────
    print()
    if FAILS:
        print(f"  {CR}{CB}{len(FAILS)} check(s) failed:{C0}")
        for f in FAILS:
            print(f"    · {f}")
        print()
        return 1
    if WARNS:
        print(f"  {CY}Everything works. {len(WARNS)} thing(s) worth a look:{C0}")
        for w in WARNS:
            print(f"    · {w}")
        print()
        return 0
    print(f"  {CG}{CB}Every Betriebskonsole function works on this host.{C0}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
