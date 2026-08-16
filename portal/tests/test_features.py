"""Tests for the top-5 features added after E2E testing."""
import sys, os, glob
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import _sandbox  # noqa: F401  — temp DB + config shield, restored at exit
os.environ["AURALIS_API_KEY"] = "k"
# (live-DB deletion removed — _sandbox gives every run a fresh temp DB)
(_sandbox.CONFIG / "clients.json").write_text('{"clients":{}}', encoding="utf-8")
from server.app import app
from lib import store, backup
K={"X-Auralis-Key":"k"}; fails=[]
def ck(n,c): print(("  PASS " if c else "  FAIL ")+n); (c or fails.append(n))

def run():
    c=app.test_client()
    print("· Feature: system status")
    st=c.get("/api/status",headers=K)
    ck("status ok",st.status_code==200 and st.get_json()["server"]=="ok")
    ck("status reports agent+email+renderer", all(k in st.get_json() for k in ("agent_provider","email_mode","chrome_available")))

    print("· Feature: login rate-limiting")
    r=None
    for _ in range(7): r=c.post("/api/login",json={"client_id":"AN-9999","password":"x"})
    ck("locks out after burst (429)", r.status_code==429)

    print("· Feature: activity log + preview")
    inv=c.post("/api/clients",headers=K,json={"name":"Ana","email":"a@b.com","language":"de"}).get_json()
    cid=inv["client_id"]
    tok=c.post("/api/login",json={"client_id":cid,"password":inv["password"]}).get_json()["token"]
    c.post("/api/intake",headers={"Authorization":"Bearer "+tok},json={"goal":"x","language":"de",
        "red_flags":["none"],"consent":{"coaching_not_medical":True,"gdpr_health_data":True}})
    c.post(f"/api/client/{cid}/draft",headers=K)
    det=c.get(f"/api/client/{cid}",headers=K).get_json()["record"]
    evs=[a["event"] for a in det["meta"].get("activity",[])]
    ck("activity logs invited+intake+drafted", any("invited" in e for e in evs) and any("intake" in e for e in evs) and any("drafted" in e for e in evs))
    pv=c.post(f"/api/client/{cid}/preview",headers=K,json={"sections":det["report"]["sections"]})
    ck("preview returns branded HTML", pv.status_code==200 and b"Auralis" in pv.data and b"<html" in pv.data.lower())

    print("· Feature: backup + restore")
    os.environ["AURALIS_BACKUP_DIR"]=str(ROOT/".ci"/"bk3")
    backup.backup_now()
    ok = bool(glob.glob(str(ROOT/".ci"/"bk3"/"auralis-*"/"auralis.db")))
    ck("backup snapshot written", ok)
    import shutil; shutil.rmtree(ROOT/".ci"/"bk3",ignore_errors=True); os.environ.pop("AURALIS_BACKUP_DIR",None)

    print("\n"+("FEATURE TESTS PASSED ✓" if not fails else f"FAILED: {fails}"))
    return 0 if not fails else 1
if __name__=="__main__": sys.exit(run())
