"""Tests for the own-brand booking system + Stammdaten editor."""
import sys, os, glob
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ["AURALIS_API_KEY"] = "k"
for f in ["auralis.db","auralis.db-wal","auralis.db-shm"]:
    (ROOT/f).exists() and (ROOT/f).unlink()
import shutil as _sh
for _p in ROOT.glob("output_docs/AN-*"): _sh.rmtree(_p, ignore_errors=True)
(ROOT/"config"/"clients.json").write_text('{"clients":{}}', encoding="utf-8")
(ROOT/"config"/"availability.json").exists() and (ROOT/"config"/"availability.json").unlink()
from server.app import app
from lib import booking, cfg
K={"X-Auralis-Key":"k"}; fails=[]
def ck(n,c): print(("  PASS " if c else "  FAIL ")+n); (c or fails.append(n))

def run():
    c=app.test_client()
    print("· slots are offered from default availability")
    r=c.get("/api/booking/slots"); d=r.get_json()
    ck("slots endpoint public 200", r.status_code==200)
    ck("has days with slots", len(d.get("days",[]))>0 and len(d["days"][0]["slots"])>0)
    ck("timezone present", d.get("timezone")=="Europe/Madrid")
    slot=d["days"][0]["slots"][0]["utc"]

    print("· booking flow")
    bad=c.post("/api/booking/book",json={"slot":slot,"name":"","email":"x","consent":{"gdpr":True}})
    ck("rejects missing name/email", bad.status_code==400)
    noc=c.post("/api/booking/book",json={"slot":slot,"name":"Elena","email":"e@x.com"})
    ck("rejects missing consent", noc.status_code==400)
    ok=c.post("/api/booking/book",json={"slot":slot,"name":"Elena Martín","email":"e@x.com",
        "language":"de","note":"Freue mich","consent":{"gdpr":True}})
    ck("books successfully", ok.status_code==200 and ok.get_json()["ok"])
    bid=ok.get_json()["id"]
    dup=c.post("/api/booking/book",json={"slot":slot,"name":"Other","email":"o@x.com","consent":{"gdpr":True}})
    ck("double-booking rejected 409", dup.status_code==409)
    d2=c.get("/api/booking/slots").get_json()
    all_slots={s["utc"] for day in d2["days"] for s in day["slots"]}
    ck("slot removed from offer", slot not in all_slots)

    print("· artifacts: .ics + confirmation .eml")
    ck("ics written", (cfg.OUTPUT_DIR/"bookings"/f"{bid}.ics").exists())
    ics=(cfg.OUTPUT_DIR/"bookings"/f"{bid}.ics").read_text()
    ck("ics valid-ish", "BEGIN:VCALENDAR" in ics and "DTSTART" in ics)
    ck("confirmation eml written", bool(glob.glob(str(cfg.OUTPUT_DIR/"bookings"/"sent"/"*.eml"))))
    eml=open(glob.glob(str(cfg.OUTPUT_DIR/"bookings"/"sent"/"*.eml"))[0],encoding="utf-8",errors="ignore").read()
    ck("eml is German (client language)", "ist best" in eml or "Hallo" in eml)

    print("· staff: list + cancel + availability")
    ck("bookings need staff key", c.get("/api/bookings").status_code==401)
    lst=c.get("/api/bookings",headers=K).get_json()["bookings"]
    ck("booking listed with decrypted name", any(b["name"]=="Elena Martín" for b in lst))
    ck("cancel works", c.post(f"/api/booking/{bid}/cancel",headers=K).status_code==200)
    d3=c.get("/api/booking/slots").get_json()
    all3={s["utc"] for day in d3["days"] for s in day["slots"]}
    ck("cancelled slot offered again", slot in all3)
    print("· booking with wellbeing profile -> lead in journey")
    d4=c.get("/api/booking/slots").get_json()
    s2=d4["days"][0]["slots"][0]["utc"]
    ok2=c.post("/api/booking/book",json={"slot":s2,"name":"Marcus Weber","email":"marcus@x.com",
        "language":"en","consent":{"gdpr":True,"health_data":True},
        "profile":{"goal":"sharper mornings","symptoms":["fatigue","stress","BOGUS"],
                   "scales":{"energy":2,"stress":9},"red_flags":["none"],"since":"months"}})
    ck("profiled booking 200", ok2.status_code==200)
    cls=c.get("/api/clients",headers=K).get_json()["clients"]
    lead=[x for x in cls if x.get("email")=="marcus@x.com"]
    ck("lead auto-created", len(lead)==1 and lead[0]["stage"]=="lead" and lead[0]["status"]=="lead")
    lid=lead[0]["client_id"]
    det=c.get(f"/api/client/{lid}",headers=K).get_json()["record"]
    ck("profile sanitised+stored", det["pre_intake"]["symptoms"]==["fatigue","stress"]
       and det["pre_intake"]["scales"]["stress"]==5)
    ck("booking slot linked", det["booking"]["slot_utc"]==s2)

    print("· journey: stage + package + credentials")
    ck("stage->call", c.post(f"/api/client/{lid}/stage",headers=K,json={"stage":"call"}).status_code==200)
    ck("bad stage rejected", c.post(f"/api/client/{lid}/stage",headers=K,json={"stage":"HAX"}).status_code==400)
    ck("package+phone saved", c.post(f"/api/client/{lid}/profile",headers=K,
        json={"package":"flourish","phone":"+34 600 1"}).status_code==200)
    ck("stage->won", c.post(f"/api/client/{lid}/stage",headers=K,json={"stage":"won"}).status_code==200)
    cr=c.post(f"/api/client/{lid}/credentials",headers=K).get_json()
    ck("credentials issued", bool(cr.get("password")))
    ck("lead can now log in", c.post("/api/login",
        json={"client_id":lid,"password":cr["password"]}).status_code==200)
    import glob as _g
    emls=_g.glob(str(cfg.OUTPUT_DIR/lid/"sent"/"*.eml"))
    body_=open(emls[-1],encoding="utf-8",errors="ignore").read() if emls else ""
    ck("credentials email branded", lid in body_ and "/portal" in body_)

    print("· dashboard KPIs")
    db=c.get("/api/dashboard",headers=K).get_json()
    ck("funnel counts bookings", db["funnel"]["bookings"]>=2)
    ck("revenue counts won package", db["revenue"]["total"]>=798)
    ck("series has 6 months", len(db["series"])==6)
    ck("packages exposed", any(p["key"]=="root" for p in db["packages"]))
    ck("dashboard needs key", c.get("/api/dashboard").status_code==401)


    av=c.post("/api/availability",headers=K,json={"windows":{"mon":[],"tue":[],"wed":[],"thu":[],"fri":[],"sat":[],"sun":[]}})
    ck("availability saved", av.status_code==200)
    ck("no slots when closed", len(c.get("/api/booking/slots").get_json()["days"])==0)

    print("· Stammdaten editor")
    # snapshot the real company.json — this test mutates it and must restore it,
    # or it would clobber the founder's committed Stammdaten (and Desiree's on the Mac)
    _co_path = ROOT/"config"/"company.json"
    _co_backup = _co_path.read_text(encoding="utf-8")
    try:
        co=c.get("/api/company",headers=K)
        ck("company get", co.status_code==200 and "_editable" in co.get_json())
        up=c.post("/api/company",headers=K,json={"nif":"X1234567Y","meet_link":"https://meet.google.com/abc-defg-hij","api_key":"HACK"})
        ck("company save whitelists fields", up.status_code==200 and up.get_json().get("nif")=="X1234567Y" and "api_key" not in {"HACK"} )
        ck("meet_link persisted", cfg.company().get("meet_link","").startswith("https://meet.google"))
        ck("secret not injectable", cfg.company().get("api_key") is None)
    finally:
        _co_path.write_text(_co_backup, encoding="utf-8")
        cfg.reset_caches()

    # restore availability defaults for other suites
    (ROOT/"config"/"availability.json").unlink()
    print("\n"+("BOOKING TESTS PASSED ✓" if not fails else f"FAILED: {fails}"))
    return 0 if not fails else 1
if __name__=="__main__": sys.exit(run())
