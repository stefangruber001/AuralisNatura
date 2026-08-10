"""iOS-app API contract test — verifies every endpoint the native app calls,
with the exact field shapes the Swift Codable models expect (snake_case).
Runs in-process on a fresh, isolated store (never touches live data)."""
import sys, os, json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import _sandbox  # noqa: F401  — temp DB + config shield, restored at exit

os.environ.setdefault("AURALIS_API_KEY", "test-key")
# (live-DB deletion removed — _sandbox gives every run a fresh temp DB)
import shutil as _sh
# (output_docs deletion removed — _sandbox redirects cfg.OUTPUT_DIR)
(ROOT / "config" / "clients.json").write_text('{"clients":{}}', encoding="utf-8")

from server.app import app  # noqa: E402

KEY = {"X-Auralis-Key": "test-key"}
FAILS = []


def check(name, cond):
    print(("  PASS " if cond else "  FAIL ") + name)
    if not cond:
        FAILS.append(name)


def has(d, *keys):
    return all(k in d for k in keys)


def run():
    c = app.test_client()

    print("· auth")
    check("bad login → 401", c.post("/api/login", json={"client_id": "AN-9999", "password": "x"}).status_code == 401)
    r = c.post("/api/clients", headers=KEY, json={"name": "Contract Test", "email": "ct@t.com", "language": "de"})
    cid, pw = r.get_json()["client_id"], r.get_json()["password"]
    lg = c.post("/api/login", json={"client_id": cid, "password": pw}).get_json()
    check("login shape {token,client_id,name,language}", has(lg, "token", "client_id", "name", "language"))
    H = {"Authorization": f"Bearer {lg['token']}"}

    print("· me")
    me = c.get("/api/me", headers=H).get_json()
    check("me shape", has(me, "client_id", "name", "language", "stage", "has_intake",
                          "report_ready", "wellbeing", "priorities", "habits"))
    check("wellbeing empty pre-intake", (me.get("wellbeing") or {}).get("scales") == {})
    check("priorities/habits empty pre-report", me["priorities"] == [] and me["habits"] == [])

    print("· offers (catalog)")
    off = c.get("/api/app/offers").get_json()
    check("offers list", isinstance(off.get("offers"), list) and len(off["offers"]) >= 3)
    check("offer shape", all(has(o, "key", "name", "price", "tagline", "buy_url") for o in off["offers"]))
    keys = [o["key"] for o in off["offers"]]
    check("root+bloom+flourish present", all(k in keys for k in ("root", "bloom", "flourish")))

    print("· intake")
    body = {"goal": "Mehr Energie", "why_now": "Test", "b": {"energy": 2, "sleep": 3, "stress": 4, "digestion": 3},
            "language": "de", "red_flags": ["none"],
            "consent": {"coaching_not_medical": True, "gdpr_health_data": True}}
    check("intake accepted", c.post("/api/intake", headers=H, json=body).status_code == 200)
    check("intake resubmit → 409", c.post("/api/intake", headers=H, json=body).status_code == 409)
    me2 = c.get("/api/me", headers=H).get_json()
    check("has_intake true + wellbeing scales", me2["has_intake"] is True and
          isinstance((me2.get("wellbeing") or {}).get("scales"), dict))

    print("· documents (empty pre-report)")
    docs = c.get("/api/my/documents", headers=H).get_json()
    check("documents shape", isinstance(docs.get("documents"), list) and docs["documents"] == [])

    print("· report flow")
    c.post(f"/api/client/{cid}/draft", headers=KEY)
    d = c.get(f"/api/client/{cid}", headers=KEY).get_json()
    c.post(f"/api/client/{cid}/report/save", headers=KEY,
           json={"sections": d["record"]["report"]["sections"], "approved": True})
    c.post(f"/api/client/{cid}/generate", headers=KEY)
    c.post(f"/api/client/{cid}/stage", headers=KEY, json={"stage": "sent", "force": True})
    docs2 = c.get("/api/my/documents", headers=H).get_json()["documents"]
    check("report document listed", len(docs2) == 1 and has(docs2[0], "key", "name", "type", "date"))
    rt = c.post("/api/my/report-token", headers=H).get_json()
    check("report-token issued", bool(rt.get("token")))
    check("report via query token", c.get(f"/api/my/report?token={rt['token']}").status_code == 200)
    check("report without token → 401", c.get("/api/my/report").status_code == 401)

    print("· change password")
    check("wrong current → 403", c.post("/api/my/change-password", headers=H,
          json={"current": "nope", "new": "longenough1"}).status_code == 403)
    check("short new → 400", c.post("/api/my/change-password", headers=H,
          json={"current": pw, "new": "short"}).status_code == 400)
    check("change ok", c.post("/api/my/change-password", headers=H,
          json={"current": pw, "new": "longenough1"}).status_code == 200)
    check("new pw logs in", c.post("/api/login", json={"client_id": cid, "password": "longenough1"}).status_code == 200)

    print("· delete request + push token")
    check("delete-request ok", c.post("/api/my/delete-request", headers=H).status_code == 200)
    check("push-token authed ok", c.post("/api/app/push-token", headers=H,
          json={"token": "ios-dev-token", "platform": "ios"}).status_code == 200)
    check("push-token unauthed → 401", c.post("/api/app/push-token",
          json={"token": "x"}).status_code == 401)

    print("\n" + ("IOS CONTRACT ALL PASSED ✓" if not FAILS else f"{len(FAILS)} FAILED: {FAILS}"))
    return 0 if not FAILS else 1


if __name__ == "__main__":
    sys.exit(run())
