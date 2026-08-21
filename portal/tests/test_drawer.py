#!/usr/bin/env python3
"""The Anfrage-Detail drawer: its data endpoint and its wiring.

The drawer reads three things: the client detail, the sessions, and a NEW
per-client document listing. The document listing is the part that can go
wrong quietly — it walks the filesystem, labels mails by their Subject, and
must only ever show THIS client's paper trail. These checks pin that, plus
the console markup that makes a journey row open the drawer at all.
"""
from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import _sandbox  # noqa: E402,F401
import os  # noqa: E402
os.environ.setdefault("AURALIS_API_KEY", "test-key")

from lib import cfg, store, booking  # noqa: E402
cfg.reset_caches()

K = {"X-Auralis-Key": os.environ["AURALIS_API_KEY"]}
FAILS: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    print(f"  {'ok  ' if ok else 'FAIL'} {label}" + (f"\n         {detail}" if detail and not ok else ""))
    if not ok:
        FAILS.append(label)


def run() -> int:
    from server.app import app
    c = app.test_client()

    print("· the documents endpoint is staff-only and validates the id")
    check("no key → refused", c.get("/api/client/AN-0001/documents").status_code in (401, 403))
    check("bad id → 400",
          c.get("/api/client/hack/documents", headers=K).status_code == 400)
    check("unknown client → 404",
          c.get("/api/client/AN-9999/documents", headers=K).status_code == 404)

    print("\n· a booking produces a client whose drawer shows her paper trail")
    slot = next(s["utc"] for d in booking.compute_slots()["days"] for s in d["slots"])
    r = c.post("/api/booking/book", json={
        "name": "Drawer Test", "email": "drawer@example.com", "language": "de",
        "slot": slot, "consent": {"gdpr": True},
        "profile": {"goal": "Mehr Energie", "symptoms": ["fatigue"],
                    "scales": {"energy": 2, "stress": 4}}})
    check("booking accepted", r.status_code == 200, r.get_data(as_text=True)[:200])
    cid = next(k for k in cfg.clients()["clients"])

    d = c.get(f"/api/client/{cid}/documents", headers=K).get_json()
    items = d.get("items", [])
    check("the mails she was sent are listed", any(i["kind"] == "eml" for i in items),
          str(items))
    subj = " | ".join(i["label"] for i in items if i["kind"] == "eml")
    check("mails are labelled by SUBJECT, not filename",
          "angekommen" in subj or "bestätigt" in subj, subj)
    check("her calendar invite is listed", any(i["kind"] == "ics" for i in items),
          str(items))
    check("every file path stays inside output_docs",
          all(".." not in i["file"] and not i["file"].startswith("/") for i in items))

    print("\n· another client's drawer does not see her documents")
    cid2 = cfg.allocate_client("Andere Kundin", "andere@example.com", "de")
    d2 = c.get(f"/api/client/{cid2}/documents", headers=K).get_json()
    check("a fresh client has no documents", d2.get("items") == [], str(d2))

    print("\n· the console wires the drawer")
    html = (ROOT / "web" / "staff.html").read_text(encoding="utf-8")
    for needle, why in (
        ('onclick="openDrawer(', "journey rows open the drawer"),
        ('id="drawer"', "the drawer element exists"),
        ('onclick="event.stopPropagation()"', "action buttons do not also open it"),
        ("function renderDrawer", "the renderer exists"),
        ("Stressbalance", "the stress scale keeps its higher-is-better name"),
        ("dw-empty", "empty sections say when they will fill"),
        ("closeDrawer();                 // die Vollansicht", "full view closes the drawer"),
    ):
        check(why, needle in html, needle)

    print()
    if FAILS:
        print(f"{len(FAILS)} failure(s):")
        for f in FAILS:
            print("  ·", f)
        return 1
    print("drawer: all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(run())
