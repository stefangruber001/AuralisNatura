"""Regression tests for round-3 fixes."""
import sys, os
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import _sandbox  # noqa: F401  — temp DB + config shield, restored at exit
os.environ["AURALIS_API_KEY"] = "test-key"
# (live-DB deletion removed — _sandbox gives every run a fresh temp DB)
(_sandbox.CONFIG / "clients.json").write_text('{"clients":{}}', encoding="utf-8")
from server.app import app
from lib import store
KEY={"X-Auralis-Key":"test-key"}; fails=[]
def ck(n,c): print(("  PASS " if c else "  FAIL ")+n); (c or fails.append(n))

def run():
    c=app.test_client()
    print("· non-dict JSON body doesn't 500")
    r=c.post("/api/login", data="[1,2,3]", content_type="application/json")
    ck("array body -> 401 not 500", r.status_code==401)
    print("· invalid cid rejected on FS routes")
    ck("bad cid generate -> 400", c.post("/api/client/NOTACID/generate", headers=KEY).status_code==400)
    ck("bad cid erase -> 400/404", c.delete("/api/client/NOTACID/generate".replace('/generate',''), headers=KEY).status_code in (400,404))
    print("· update_existing never resurrects an erased record")
    store.upsert({"client_id":"AN-0001","stage":"review","report":{"approved":True},"meta":{}})
    store.delete("AN-0001")
    ck("update_existing False after delete", store.update_existing({"client_id":"AN-0001","stage":"sent","meta":{}}) is False)
    ck("record stays gone", store.get("AN-0001") is None)
    print("· decrypt error is a clear typed error")
    ck("DecryptError type exists", hasattr(store,"DecryptError"))
    print("\n"+("R3 TESTS PASSED ✓" if not fails else f"FAILED: {fails}"))
    return 0 if not fails else 1
if __name__=="__main__": sys.exit(run())
