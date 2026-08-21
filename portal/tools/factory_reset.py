#!/usr/bin/env python3
"""factory_reset.py — empty the business data and open with a clean slate.

WHAT IT REMOVES
  Every client (journey record, documents, portal login), every booking —
  enquiries AND planned programme sessions — and the events that feed Cockpit
  revenue and the sales funnel. Plus the mail audit copies for all of it, the
  handled-Stripe-event ids and the push-device tokens.

WHY IT IS NOT JUST "DELETE THE CLIENTS"
  A booking lives in its own table, not on the client record. Erasing every
  client therefore leaves the appointments behind: still blocking slots on
  /book, still listed under Termine, still counted as enquiries. Deleting
  clients alone LOOKS clean and is not.

WHAT IT KEEPS — this is her work, not customer data
  Journal/Impulse articles, social plans and rendered posts, availability,
  company master data, prices and packages, every configuration switch.

SAFETY
  Irreversible, so the portal always writes a snapshot first (the encrypted
  database + clients.json) next to the live database and prints the path. It
  refuses to reset if that snapshot cannot be written. You must type RESET.

WHERE IT RUNS
    on the server:  sudo -u auralis /opt/auralis/venv/bin/python \\
                        /opt/auralis/app/portal/tools/factory_reset.py
    from anywhere:  python3 tools/factory_reset.py \\
                        --base https://api.auralisnatura.com --key <staff key>
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

C0, CG, CY, CR, CB, CD = ("\033[0m", "\033[32m", "\033[33m", "\033[31m",
                          "\033[1m", "\033[2m")
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36 AuralisFactoryReset/1.0")


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


def call(base: str, path: str, key: str, method: str = "GET", body: dict | None = None):
    h = {"X-Auralis-Key": key, "User-Agent": UA, "Accept": "*/*"}
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        h["Content-Type"] = "application/json"
    r = urllib.request.Request(base + path, data=data, headers=h, method=method)
    try:
        with urllib.request.urlopen(r, timeout=120) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode("utf-8"))
        except Exception:
            return e.code, {}
    except Exception as e:
        return 0, {"error": f"{type(e).__name__}: {e}"}


def step(msg: str) -> None:
    print(f"\n{CB}▸ {msg}{C0}")


def ok(msg: str, detail: str = "") -> None:
    print(f"  {CG}✔{C0} {msg}" + (f"  {CD}{detail}{C0}" if detail else ""))


def warn(msg: str) -> None:
    print(f"  {CY}!{C0} {msg}")


def die(msg: str, code: int = 1):
    print(f"\n  {CR}✖ {msg}{C0}\n", file=sys.stderr)
    sys.exit(code)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base", default=None,
                    help="portal URL (default http://127.0.0.1:$AURALIS_PORT)")
    ap.add_argument("--key", default=None, help="staff API key")
    ap.add_argument("--keep-events", action="store_true",
                    help="keep the funnel/revenue history (clients and bookings still go)")
    ap.add_argument("--yes", action="store_true",
                    help="skip the typed confirmation (for scripted use only)")
    args = ap.parse_args()

    base = (args.base or f"http://127.0.0.1:{os.environ.get('AURALIS_PORT', '5056')}").rstrip("/")
    key = args.key or env_value("AURALIS_API_KEY")
    if not key:
        try:
            from lib import cfg
            key = str(cfg.config().get("api_key", ""))
        except Exception:
            key = ""

    print(f"\n{CB}Auralis Natura — fresh start{C0}\n  {CD}host {base}{C0}")

    # ── what is there right now ──────────────────────────────────────────────
    step("What would be erased")
    st, d = call(base, "/api/clients", key)
    if st == 401:
        die("the staff key is not accepted — check AURALIS_API_KEY")
    if st != 200:
        die(f"cannot read the client list ({st}) — is the portal running? {d.get('error','')}")
    clients = d.get("clients", [])
    for c in clients:
        print(f"    {c.get('client_id')}  {c.get('name','')}  {c.get('email','')}  "
              f"{CD}Phase {c.get('stage','')}{C0}")
    print(f"    {CB}{len(clients)} Kundin(nen){C0}")

    _, d = call(base, "/api/bookings", key)
    bk = [b for b in d.get("bookings", []) if b.get("status") == "confirmed"]
    calls = [b for b in bk if b.get("kind") != "session"]
    sess = [b for b in bk if b.get("kind") == "session"]
    for b in calls:
        print(f"    {b.get('start_utc','')[:16].replace('T',' ')}  {b.get('name','?')}  "
              f"{CD}Anfrage{C0}")
    print(f"    {CB}{len(calls)} Anfrage(n) · {len(sess)} Programm-Termin(e){C0}")

    _, dash = call(base, "/api/dashboard", key)
    rev = float(((dash.get("revenue") or {}).get("total")) or 0)
    print(f"    {CB}{rev:.0f} EUR{C0} Umsatz im Cockpit"
          + (f" {CD}(bleibt, --keep-events){C0}" if args.keep_events else " (wird zurückgesetzt)"))

    if not clients and not bk and not rev:
        ok("nothing to erase — the console is already empty")
        return 0

    print(f"""
  {CD}Kept: Impulse-Artikel, Social-Pläne und -Posts, Verfügbarkeit, Stammdaten,
  Preise und Pakete, alle Schalter. Nur Kundendaten gehen.{C0}""")

    # ── confirm ──────────────────────────────────────────────────────────────
    if not args.yes:
        print(f"\n  {CR}{CB}This cannot be undone (a snapshot is written first).{C0}")
        if input("  Type RESET to confirm: ").strip() != "RESET":
            print(f"\n  {CY}Not confirmed — nothing was deleted.{C0}\n")
            return 1

    # ── do it ────────────────────────────────────────────────────────────────
    step("Erasing")
    st, r = call(base, "/api/admin/reset", key, "POST",
                 {"confirm": "RESET", "keep_events": args.keep_events})
    if st != 200:
        die(f"the reset failed ({st}): {r.get('error', r)}")
    ok(f"snapshot written first", r.get("snapshot", ""))
    ok(f"{r.get('clients_erased', 0)} client(s) erased",
       "record, documents and portal login")
    ok(f"{r.get('bookings_removed', 0)} booking(s) removed", "enquiries and programme sessions")
    ok(f"{r.get('events_removed', 0)} event(s) removed", "revenue and funnel history")
    if r.get("docs_removed"):
        ok(f"{len(r['docs_removed'])} document folder(s) removed",
           ", ".join(r["docs_removed"][:6]))
    if r.get("files_cleared"):
        ok("cleared: " + ", ".join(r["files_cleared"]))

    # ── prove it, through the portal's own eyes ──────────────────────────────
    # Read it back through the PORTAL, not from this process: a reset that
    # verified itself against its own idea of the data would prove nothing.
    step("What the Betriebskonsole shows now")
    fails: list[str] = []

    def gate(good: bool, label: str) -> None:
        if good:
            ok(label)
        else:
            fails.append(label)
            print(f"  {CR}✖{C0} {label}")

    _, d = call(base, "/api/clients", key)
    n = len(d.get("clients", []))
    gate(n == 0, f"Kundinnen: {n}")
    _, d = call(base, "/api/bookings", key)
    n = len([b for b in d.get("bookings", []) if b.get("status") == "confirmed"])
    gate(n == 0, f"Termine: {n}")
    _, d = call(base, "/api/dashboard", key)
    rev = float(((d.get("revenue") or {}).get("total")) or 0)
    gate(rev == 0 or args.keep_events, f"Cockpit-Umsatz: {rev:.0f} EUR")
    _, d = call(base, "/api/alerts", key)
    keys = [a.get("key") for a in d.get("alerts", [])]
    noisy = [k for k in keys if k in ("new_enquiry", "cred_missing", "unpaid",
                                      "unpaid_start", "unpaid_running", "followup")]
    gate(not noisy, "keine offenen Kundinnen-Alerts" if not noisy
         else f"Alerts stehen noch: {', '.join(noisy)}")
    # The point of clearing the bookings table is that the calendar opens again.
    _, d = call(base, "/api/booking/slots", key)
    free = sum(len(x.get("slots") or []) for x in d.get("days", []))
    if free:
        ok(f"/book bietet wieder {free} freie Zeiten an")
    else:
        warn("/book bietet keine Zeiten an — das liegt an der Verfügbarkeit, "
             "nicht am Reset (Termine-Tab)")

    if fails:
        print(f"\n  {CR}{CB}Not fully clean:{C0}")
        for f in fails:
            print(f"    · {f}")
        print(f"""
  The snapshot is at {r.get('snapshot','?')} if you need to go back.
""")
        return 1

    print(f"""
  {CG}{CB}Clean slate. The next booking will be AN-0001 again.{C0}

  Kept, because it is your work and not customer data: Impulse-Artikel,
  Social-Pläne und gerenderte Posts, Verfügbarkeit, Stammdaten, Preise und
  Pakete, alle Schalter (der Shop bleibt an).

  Snapshot of everything that was just erased:
    {r.get('snapshot','?')}
  Delete it once you are sure — it contains real health data.
""")
    return 0


if __name__ == "__main__":
    sys.exit(main())
