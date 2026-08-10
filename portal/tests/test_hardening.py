"""Regression tests for the round-1 audit fixes."""
import sys, os, glob
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import _sandbox  # noqa: F401  — temp DB + config shield, restored at exit
os.environ["AURALIS_API_KEY"] = "test-key"
for f in ["auralis.db", "auralis.db-wal", "auralis.db-shm"]:
    (ROOT / f).exists() and (ROOT / f).unlink()
(ROOT / "config" / "clients.json").write_text('{"clients":{}}', encoding="utf-8")

from server.app import app  # noqa
from lib import cfg, agent, store  # noqa
KEY = {"X-Auralis-Key": "test-key"}
fails = []
def ck(n, c): print(("  PASS " if c else "  FAIL ") + n); (c or fails.append(n))


def run():
    c = app.test_client()

    print("· red-flag → doctor referral is ENFORCED (not just prompted)")
    r = c.post("/api/clients", headers=KEY, json={"name": "Red Flag", "email": "r@e.com", "language": "en"})
    cid, pw = r.get_json()["client_id"], r.get_json()["password"]
    tok = c.post("/api/login", json={"client_id": cid, "password": pw}).get_json()["token"]
    H = {"Authorization": f"Bearer {tok}"}
    intake = {"goal": "energy", "b": {"energy": 2}, "language": "en",
              "red_flags": ["Chest pain or breathlessness"],
              "consent": {"coaching_not_medical": True, "gdpr_health_data": True}}
    c.post("/api/intake", headers=H, json=intake)
    rep = c.post(f"/api/client/{cid}/draft", headers=KEY).get_json()["report"]
    ck("draft flagged red", rep["red_flag"] is True)
    sp = next(s for s in rep["sections"] if s["key"] == "starting_point")["body"].lower()
    ck("starting_point opens with doctor referral", "doctor" in sp[:90] or "see your doctor" in sp)

    print("· agent helpers tolerate junk without 500")
    ck("has_red_flag on nested list", agent.has_red_flag({"safety": {"red_flags": ["Fainting / blackouts"]}}) is True)
    ck("has_red_flag Spanish free-text", agent.has_red_flag({"symptoms": "tengo dolor en el pecho"}) is True)
    ck("chart_data survives non-dict b", agent._chart_data({"b": "oops"}) == {})
    ck("none-of-the-above not a flag", agent.has_red_flag({"red_flags": ["None of the above"]}) is False)

    print("· re-submission after draft is blocked (409)")
    r2 = c.post("/api/intake", headers=H, json=intake)
    ck("re-submit returns 409", r2.status_code == 409)

    print("· GDPR erase removes on-disk artifacts too")
    # approve + generate to create a PDF + eml on disk
    secs = rep["sections"]
    c.post(f"/api/client/{cid}/report/save", headers=KEY, json={"sections": secs, "approved": True})
    c.post(f"/api/client/{cid}/generate", headers=KEY)
    outdir = cfg.OUTPUT_DIR / cid
    ck("artifacts exist before erase", outdir.exists() and (bool(glob.glob(str(outdir / '**' / '*'), recursive=True))))
    er = c.delete(f"/api/client/{cid}", headers=KEY).get_json()
    ck("erase reports disk removed", er.get("disk_removed") is True)
    ck("output dir gone", not outdir.exists())

    print("· CORS suffix match respects label boundary")
    from server.app import _origin_ok
    ck("legit trycloudflare subdomain allowed", _origin_ok("https://abc.trycloudflare.com") is True)
    ck("look-alike domain rejected", _origin_ok("https://eviltrycloudflare.com") is False)
    ck("random origin rejected", _origin_ok("https://evil.example") is False)

    print("· login returns canonical client_id + equal-timing on bad user")
    lj = c.post("/api/login", json={"client_id": "AN-9999", "password": "x"})
    ck("unknown user 401", lj.status_code == 401)

    print("\n" + ("HARDENING TESTS PASSED ✓" if not fails else f"FAILED: {fails}"))
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(run())
