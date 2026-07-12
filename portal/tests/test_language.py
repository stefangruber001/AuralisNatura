"""End-to-end test: the per-client language selected in the Betriebskonsole
drives EVERY external communication AND the report document.

Scenario: a client books + fills intake in ENGLISH, then the operator switches
their language to GERMAN in the Kundinnen tab. From that point on every artifact
— credentials email, the AI report draft, the rendered report document, the
report email, the feedback email and the call reminder — must be in German,
regardless of the English intake. Finally a switch to Spanish re-drafts in ES.

Runs fully offline (agent_provider=stub, email_mode=off → .eml files on disk).
"""
import sys, os, email
from email.header import decode_header
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

os.environ.setdefault("AURALIS_API_KEY", "test-key")
for f in [ROOT / "auralis.db", ROOT / "auralis.db-wal", ROOT / "auralis.db-shm"]:
    if f.exists():
        f.unlink()
import shutil as _sh
for _p in list(ROOT.glob("output_docs/AN-*")) + [ROOT / "output_docs" / "bookings"]:
    _sh.rmtree(_p, ignore_errors=True)
for _n in ("availability.json", "plan.json"):
    (ROOT / "config" / _n).unlink() if (ROOT / "config" / _n).exists() else None
(ROOT / "config" / "clients.json").write_text('{"clients":{}}', encoding="utf-8")

from server.app import app          # noqa: E402
from lib import cfg, render         # noqa: E402

KEY = {"X-Auralis-Key": "test-key"}
FAILS = []


def check(name, cond):
    print(("  PASS " if cond else "  FAIL ") + name)
    if not cond:
        FAILS.append(name)


def _subject_of_newest(folder: Path) -> str:
    """Decode the Subject header of the single .eml in `folder` (we clear the
    folder before each send so exactly one mail is present)."""
    emls = sorted(folder.glob("*.eml"), key=lambda p: p.stat().st_mtime)
    if not emls:
        return ""
    msg = email.message_from_bytes(emls[-1].read_bytes())
    out = []
    for data, enc in decode_header(msg.get("Subject", "")):
        out.append(data.decode(enc or "utf-8") if isinstance(data, bytes) else data)
    return "".join(out)


def _clear(folder: Path):
    _sh.rmtree(folder, ignore_errors=True)


def run():
    c = app.test_client()
    book_sent = cfg.OUTPUT_DIR / "bookings" / "sent"

    print("· book a free call IN ENGLISH (auto-creates a lead)")
    slots = c.get("/api/booking/slots").get_json()
    slot = next((s["utc"] for d in slots["days"] for s in d["slots"]), None)
    check("a slot is offered", bool(slot))
    r = c.post("/api/booking/book", json={
        "slot": slot, "name": "Elena Martin", "email": "elena@example.com",
        "language": "en", "note": "",
        "consent": {"gdpr": True, "health_data": True},
        "profile": {"goal": "more energy", "symptoms": ["fatigue"], "red_flags": ["none"],
                    "scales": {"energy": 2}, "sleep_hours": "5-6"}})
    check("booking accepted", r.status_code == 200)
    bid = r.get_json()["id"]
    check("booking confirmation is English", "Your call is confirmed" in _subject_of_newest(book_sent))

    # find the auto-created client
    clients = c.get("/api/clients", headers=KEY).get_json()["clients"]
    cid = next((x["client_id"] for x in clients if x["email"] == "elena@example.com"), None)
    check("lead auto-created", bool(cid))
    check("lead language seeded EN", next(x for x in clients if x["client_id"] == cid)["language"] == "en")
    sent = cfg.OUTPUT_DIR / cid / "sent"

    print("· operator wins the client & SWITCHES LANGUAGE TO GERMAN")
    c.post(f"/api/client/{cid}/stage", headers=KEY, json={"stage": "won", "force": True})
    r = c.post(f"/api/client/{cid}/profile", headers=KEY, json={"language": "de"})
    check("language saved", r.status_code == 200)
    check("client now DE", next(x for x in c.get("/api/clients", headers=KEY).get_json()["clients"]
                                if x["client_id"] == cid)["language"] == "de")

    print("· credentials email → must be GERMAN")
    _clear(sent)
    r = c.post(f"/api/client/{cid}/credentials", headers=KEY)
    pw = r.get_json()["password"]
    check("credentials email is German", "Dein Zugang zum Auralis-Natura-Portal" == _subject_of_newest(sent))

    print("· client logs in and fills intake IN ENGLISH")
    tok = c.post("/api/login", json={"client_id": cid, "password": pw}).get_json()["token"]
    H = {"Authorization": f"Bearer {tok}"}
    intake = {"goal": "more energy through the afternoon", "why_now": "exhausted since spring",
              "tried": "coffee", "b": {"energy": 2, "sleep": 3, "stress": 4, "digestion": 3},
              "language": "en", "red_flags": ["none"],
              "consent": {"coaching_not_medical": True, "gdpr_health_data": True}}
    check("intake accepted", c.post("/api/intake", headers=H, json=intake).status_code == 200)

    print("· AI report DRAFT → German document even though intake was English")
    rep = c.post(f"/api/client/{cid}/draft", headers=KEY).get_json()["report"]
    check("report language is DE", rep.get("language") == "de")
    check("section title is German (Dein Ausgangspunkt)",
          rep["sections"][0]["title"] == "Dein Ausgangspunkt")
    check("body is German, not English", "You came to Auralis" not in rep["sections"][0]["body"])

    print("· the RENDERED report document is German")
    html_doc = render.build_html("Elena Martin", rep["sections"], report=rep,
                                 charts=rep.get("charts", {}), language=rep["language"])
    check("rendered doc has German heading", "Dein Ausgangspunkt" in html_doc)
    check("rendered doc has no English heading", "Your starting point" not in html_doc)

    print("· approve + generate → report email is German")
    c.post(f"/api/client/{cid}/report/save", headers=KEY, json={"sections": rep["sections"], "approved": True})
    _clear(sent)
    g = c.post(f"/api/client/{cid}/generate", headers=KEY)
    check("generate 200", g.status_code == 200)
    check("report email is German", "Dein persönlicher Auralis-Natura-Bericht" == _subject_of_newest(sent))

    print("· feedback request → German")
    _clear(sent)
    c.post(f"/api/client/{cid}/feedback-request", headers=KEY)
    check("feedback email is German", "Wie war deine Zeit mit Auralis Natura?" == _subject_of_newest(sent))

    print("· call reminder → client's German wins over the booking's English")
    _clear(book_sent)
    c.post(f"/api/booking/{bid}/remind", headers=KEY)
    check("reminder is German", _subject_of_newest(book_sent).startswith("Erinnerung: unser Gespräch"))

    print("· switch to SPANISH and re-draft → Spanish document")
    c.post(f"/api/client/{cid}/profile", headers=KEY, json={"language": "es"})
    rep2 = c.post(f"/api/client/{cid}/draft", headers=KEY).get_json()["report"]
    check("re-draft language is ES", rep2.get("language") == "es")
    check("section title is Spanish (Tu punto de partida)",
          rep2["sections"][0]["title"] == "Tu punto de partida")

    print("\n" + ("LANGUAGE E2E ALL PASSED ✓" if not FAILS else f"{len(FAILS)} FAILED: {FAILS}"))
    return 0 if not FAILS else 1


if __name__ == "__main__":
    sys.exit(run())
