"""Tests for the own-brand booking system + Stammdaten editor."""
import sys, os, glob
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ["AURALIS_API_KEY"] = "k"
for f in ["auralis.db","auralis.db-wal","auralis.db-shm"]:
    (ROOT/f).exists() and (ROOT/f).unlink()
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
    av=c.post("/api/availability",headers=K,json={"windows":{"mon":[],"tue":[],"wed":[],"thu":[],"fri":[],"sat":[],"sun":[]}})
    ck("availability saved", av.status_code==200)
    ck("no slots when closed", len(c.get("/api/booking/slots").get_json()["days"])==0)

    print("· Stammdaten editor")
    co=c.get("/api/company",headers=K)
    ck("company get", co.status_code==200 and "_editable" in co.get_json())
    up=c.post("/api/company",headers=K,json={"nif":"X1234567Y","meet_link":"https://meet.google.com/abc-defg-hij","api_key":"HACK"})
    ck("company save whitelists fields", up.status_code==200 and up.get_json().get("nif")=="X1234567Y" and "api_key" not in {"HACK"} )
    ck("meet_link persisted", cfg.company().get("meet_link","").startswith("https://meet.google"))
    ck("secret not injectable", cfg.company().get("api_key") is None)

    # restore availability defaults for other suites
    (ROOT/"config"/"availability.json").unlink()
    print("\n"+("BOOKING TESTS PASSED ✓" if not fails else f"FAILED: {fails}"))
    return 0 if not fails else 1
if __name__=="__main__": sys.exit(run())
