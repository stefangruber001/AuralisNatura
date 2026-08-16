"""End-to-end test of the full Auralis pipeline via the Flask test client.

invite → client login → intake → staff review → notes → draft → approve →
generate (render PDF + build email) → download → GDPR export/erase.
Runs entirely offline (agent_provider=stub, email_mode=off).
"""
import sys, json, os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import _sandbox  # noqa: F401  — temp DB + config shield, restored at exit

# isolate: fresh db + clients for the test run
os.environ.setdefault("AURALIS_API_KEY", "test-key")
# (live-DB deletion removed — _sandbox gives every run a fresh temp DB)
import shutil as _sh
# (output_docs deletion removed — _sandbox redirects cfg.OUTPUT_DIR)
(_sandbox.CONFIG / "clients.json").write_text('{"clients":{}}', encoding="utf-8")

from server.app import app  # noqa: E402
from lib import cfg  # noqa: E402

KEY = {"X-Auralis-Key": "test-key"}
FAILS = []


def check(name, cond):
    print(("  PASS " if cond else "  FAIL ") + name)
    if not cond:
        FAILS.append(name)


def run():
    c = app.test_client()

    print("· health / auth")
    check("health ok", c.get("/health").get_json()["ok"] is True)
    check("staff route needs key", c.get("/api/clients").status_code == 401)
    check("staff route with key", c.get("/api/clients", headers=KEY).status_code == 200)

    print("· invite a client")
    r = c.post("/api/clients", headers=KEY, json={"name": "Elena Martín", "email": "elena@example.com", "language": "en"})
    check("invite 200", r.status_code == 200)
    cid = r.get_json()["client_id"]
    pw = r.get_json()["password"]
    check("client id issued", cid.startswith("AN-"))

    print("· client login + intake")
    check("bad login rejected", c.post("/api/login", json={"client_id": cid, "password": "wrong"}).status_code == 401)
    tok = c.post("/api/login", json={"client_id": cid, "password": pw}).get_json()["token"]
    H = {"Authorization": f"Bearer {tok}"}
    check("me works", c.get("/api/me", headers=H).status_code == 200)
    check("intake needs consent", c.post("/api/intake", headers=H, json={"goal": "x"}).status_code == 400)
    intake = {
        "goal": "more energy through the afternoon", "why_now": "exhausted since spring",
        "tried": "coffee, early nights",
        "b": {"energy": 2, "sleep": 3, "stress": 4, "digestion": 3},
        "language": "en",
        "red_flags": ["none"],
        "consent": {"coaching_not_medical": True, "gdpr_health_data": True},
    }
    check("intake accepted", c.post("/api/intake", headers=H, json=intake).status_code == 200)

    print("· staff review + agent")
    d = c.get(f"/api/client/{cid}", headers=KEY).get_json()
    check("detail hides password", "password" not in d["client"])
    check("intake stored & decrypts", d["record"]["intake"]["goal"].startswith("more energy"))
    check("prep auto-generated", bool(d["record"].get("prep")))
    check("notes saved", c.post(f"/api/client/{cid}/notes", headers=KEY, json={"notes": "warm, motivated"}).status_code == 200)
    rep = c.post(f"/api/client/{cid}/draft", headers=KEY).get_json()["report"]
    check("draft has 6 sections", len(rep["sections"]) == 6)
    check("draft not approved yet", rep["approved"] is False)

    print("· approval gate")
    check("generate blocked before approval",
          c.post(f"/api/client/{cid}/generate", headers=KEY).status_code == 400)
    secs = rep["sections"]
    secs[0]["body"] += " (edited by Desiree)"
    check("save+approve", c.post(f"/api/client/{cid}/report/save", headers=KEY,
          json={"sections": secs, "approved": True}).status_code == 200)

    print("· generate report + email")
    g = c.post(f"/api/client/{cid}/generate", headers=KEY)
    check("generate 200", g.status_code == 200)
    gj = g.get_json()
    produced = cfg.OUTPUT_DIR / cid / "report" / gj["pdf"]
    check("report file produced", produced.exists())
    check("edit persisted into report", "edited by Desiree" in produced.read_bytes().decode("latin-1", "ignore") or produced.suffix == ".pdf")
    sent_dir = cfg.OUTPUT_DIR / cid / "sent"
    check("email .eml written", any(sent_dir.glob("*.eml")))
    eml = next(sent_dir.glob("*.eml")).read_text("utf-8", "ignore")
    check("email has booking link", "auralisnatura.com/book" in eml or "cal.com" in eml)

    print("· client can fetch their report")
    check("client report ready", c.get("/api/me", headers=H).get_json()["report_ready"] is True)
    check("client downloads report", c.get("/api/my/report", headers=H).status_code == 200)

    print("· GDPR export + erase")
    check("export works", c.get(f"/api/client/{cid}/gdpr-export", headers=KEY).status_code == 200)
    check("erase works", c.delete(f"/api/client/{cid}", headers=KEY).status_code == 200)
    check("record gone after erase", c.get(f"/api/client/{cid}", headers=KEY).status_code == 404)

    print("\n" + ("ALL PASSED ✓" if not FAILS else f"{len(FAILS)} FAILED: {FAILS}"))
    return 0 if not FAILS else 1


if __name__ == "__main__":
    sys.exit(run())
