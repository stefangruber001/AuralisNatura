"""Console 3.0: finance engine, plan editor, alerts, outbox, newsletter, build."""
import sys, os
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import _sandbox  # noqa: F401  — temp DB + config shield, restored at exit
os.environ["AURALIS_API_KEY"] = "k"
import shutil
# (live-DB deletion removed — _sandbox gives every run a fresh temp DB)
# (output_docs deletion removed — _sandbox redirects cfg.OUTPUT_DIR to a temp dir)
(ROOT/"config"/"clients.json").write_text('{"clients":{}}', encoding="utf-8")
(ROOT/"config"/"plan.json").exists() and (ROOT/"config"/"plan.json").unlink()
from server.app import app
from lib import finance, store
import datetime as dt
K={"X-Auralis-Key":"k"}; fails=[]
def ck(n,c): print(("  PASS " if c else "  FAIL ")+n); (c or fails.append(n))

def run():
    c=app.test_client()
    print("· finance engine (deterministic)")
    ev=[{"ts":"2026-03-01T09:00:00","event":"won","package":"bloom","amount":398}]
    r=finance.report(events=ev, today=dt.date(2026,7,1))
    ck("guv has plan+ist", any(g["pos"].startswith("Betriebsergebnis") for g in r["guv"]))
    ck("cashflow 12 months", len(r["cashflow"])==12)
    a=r["bilanz"]["aktiva"][-1]["wert"]; p=r["bilanz"]["passiva"][-1]["wert"]
    ck("bilanz balances", abs(a-p)<0.01)
    ck("breakeven positive", r["breakeven"]["kunden_pro_monat"]>0)
    ck("3 szenarien", len(r["szenarien"])==3)
    ck("ist ytd = 398", r["ist_umsatz"]["ytd"]==398.0)

    print("· plan endpoints")
    ck("plan get", c.get("/api/plan",headers=K).status_code==200)
    ck("plan patch german decimal", c.post("/api/plan",headers=K,
        json={"path":"mengenplan.bloom.pro_monat","value":"1,5"}).status_code==200)
    ck("value parsed", finance.get_plan()["mengenplan"]["bloom"]["pro_monat"]==1.5)
    ck("underscore path rejected", c.post("/api/plan",headers=K,json={"path":"_x","value":1}).status_code==400)
    ck("finanzen endpoint", c.get("/api/finanzen",headers=K).status_code==200)

    print("· alerts")
    # create a lead whose call is in the past
    slot=(dt.datetime.now(dt.timezone.utc)+dt.timedelta(hours=30)).isoformat()
    inv=c.post("/api/clients",headers=K,json={"name":"Stale Lead","email":"sl@x.com","language":"de"}).get_json()
    cid=inv["client_id"]
    rec=store.ensure(cid); rec["stage"]="lead"
    rec["booking"]={"slot_utc":(dt.datetime.now(dt.timezone.utc)-dt.timedelta(days=3)).isoformat()}
    rec["updated"]=(dt.datetime.now(dt.timezone.utc)-dt.timedelta(days=3)).isoformat()
    store.upsert(rec)
    al=c.get("/api/alerts",headers=K).get_json()["alerts"]
    ck("stale-lead alert raised", any(a["key"]=="stale_lead" for a in al))
    # won without credentials
    c.post(f"/api/client/{cid}/stage",headers=K,json={"stage":"won"})
    import json as _j
    data=_j.loads((ROOT/"config"/"clients.json").read_text()); data["clients"][cid]["status"]="lead"
    (ROOT/"config"/"clients.json").write_text(_j.dumps(data))
    al=c.get("/api/alerts",headers=K).get_json()["alerts"]
    ck("cred-missing alert raised", any(a["key"]=="cred_missing" for a in al))

    print("· outbox + newsletter + build")
    c.post(f"/api/client/{cid}/credentials",headers=K)
    ob=c.get("/api/outbox",headers=K).get_json()["items"]
    ck("outbox lists eml", any(i["kind"]=="eml" for i in ob))
    first=[i for i in ob if i["kind"]=="eml"][0]["file"]
    ck("outbox download", c.get(f"/api/outbox/{first}",headers=K).status_code==200)
    ck("traversal blocked", c.get("/api/outbox/../config/config.json",headers=K).status_code==404)
    nl=c.post("/api/newsletter/draft",headers=K,json={"subject":"Test","body":"Hallo.\n\nZweiter Absatz."})
    ck("newsletter drafted", nl.status_code==200 and nl.get_json()["recipients"]>=1)
    ck("build label", "Auralis" in c.get("/api/build").get_json()["label"])
    ck("outbox needs key", c.get("/api/outbox").status_code==401)
    ck("plan needs key", c.get("/api/plan").status_code==401)

    (ROOT/"config"/"plan.json").unlink(missing_ok=True)
    print("\n"+("CONSOLE3 TESTS PASSED ✓" if not fails else f"FAILED: {fails}"))
    return 0 if not fails else 1
if __name__=="__main__": sys.exit(run())
