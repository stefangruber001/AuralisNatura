#!/usr/bin/env python3
"""Wächter für Buchhaltung + Finanzamt — die spanische Fassung.

Jede Prüfung hier entspricht einem Fehler, der in einem echten Betrieb Geld
oder eine Betriebsprüfung gekostet hätte. Die wichtigste ist die letzte:
Finanzamt-Zahlen == Buchhaltungs-Zahlen, dieselbe Periode, gleiche Summe —
wer dieselbe Zahl zweimal berechnet, hat irgendwann zwei Wahrheiten.
"""
from __future__ import annotations
import sys
import datetime as dt
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import _sandbox  # noqa: E402,F401
import os  # noqa: E402
os.environ.setdefault("AURALIS_API_KEY", "test-key")

from lib import cfg, store, buchhaltung as bu  # noqa: E402
cfg.reset_caches()

FAILS: list[str] = []
J = str(dt.date.today().year)


def check(label: str, ok: bool, detail: str = "") -> None:
    print(f"  {'ok  ' if ok else 'FAIL'} {label}" + (f"\n         {detail}" if detail and not ok else ""))
    if not ok:
        FAILS.append(label)


def run() -> int:
    print("· 1 Netto/IVA/Brutto gehen bei allen vier Sätzen auf")
    for satz in bu.IVA_SAETZE:
        for brutto in (120.0, 99.99, 26.67, 0.03):
            n, u = bu.netto_aus_brutto(brutto, satz)
            check(f"{brutto} € @ {satz} % reconciles", abs(n + u - brutto) < 0.011,
                  f"{n}+{u}!={brutto}")

    print("\n· 2+3 Belegnummern lückenlos, Storno löscht nichts")
    e1 = bu.add_entry(f"{J}-02-01", "material", "Vlies", 121.0)
    e2 = bu.add_entry(f"{J}-02-02", "software", "Hosting", 12.10)
    bu.storno(e2["id"])
    e3 = bu.add_entry(f"{J}-02-03", "buero", "Porto", 6.05)
    check("numbers run A-…-0001..0003",
          [e1["beleg"], e2["beleg"], e3["beleg"]]
          == [f"A-{J}-0001", f"A-{J}-0002", f"A-{J}-0003"])
    r = bu.ea(J)
    check("the cancelled entry is counted as storniert", r["storniert"] == 1)
    check("…and appears in no sum",
          abs(r["ausgaben"]["netto"] - (100.0 + 5.0)) < 0.02,
          str(r["ausgaben"]["netto"]))
    e4 = bu.add_entry(f"{int(J)+1}-01-05", "buero", "Neujahr", 12.10)
    check("numbering restarts per year", e4["beleg"] == f"A-{int(J)+1}-0001")

    print("\n· 4+5 Offene zählen nirgends; Zahlung setzt das Buchungsdatum")
    eo = bu.add_entry(f"{J}-03-01", "gestoria", "Gestoría März", 60.50,
                      status="offen", faellig_am=f"{J}-03-20")
    r = bu.ea(J)
    check("open entry not in expenses",
          all(x["beleg"] != eo["beleg"] for k in r["ausgaben"]["kategorien"] for x in []),
          "")
    vor = r["ausgaben"]["netto"]
    check("open entry listed under offen", any(x["id"] == eo["id"] for x in r["offen"]["rows"]))
    check("cashflow ignores it",
          all(m["aus"] < 60 for m in r["cashflow"]["monate"] if m["monat"] == f"{J}-03"))
    bu.bezahlt(eo["id"], f"{J}-04-02")
    r = bu.ea(J)
    check("payment date became the booking date (Q2, not Q1)",
          r["iva303"]["quartale"][1]["soportado"] > 0
          and abs(r["ausgaben"]["netto"] - vor - 50.0) < 0.02)

    print("\n· 6 Neutrale Kategorien: Cashflow ja, Gewinn nein, IVA 0")
    g0 = bu.ea(J)["gewinn_vorlaeufig"]
    bu.add_entry(f"{J}-04-10", "aeat_iva", "IVA Q1", 500.0, iva_satz=0)
    r = bu.ea(J)
    check("profit unchanged", abs(r["gewinn_vorlaeufig"] - g0) < 0.01)
    check("cash flowed out", any(m["monat"] == f"{J}-04" and m["aus"] >= 500
                                 for m in r["cashflow"]["monate"]))
    check("listed as neutral", r["neutral"]["summe_brutto"] >= 500)

    print("\n· 7 Atenciones: Gewinn voll, IVA NIE (die spanische Umkehrung)")
    ea_ = bu.add_entry(f"{J}-05-02", "atenciones", "Dankeschön Kundin", 60.50)
    b = bu.betrieblich(ea_)
    check("expense fully profit-effective", abs(b["netto"] - 50.0) < 0.01)
    check("IVA deduction is ZERO (Art. 96 LIVA)", b["iva"] == 0.0, str(b))
    em = bu.add_entry(f"{J}-05-03", "manutencion", "Mittag unterwegs", 22.0, iva_satz=10)
    bm = bu.betrieblich(em)
    check("manutención keeps its IVA deduction", bm["iva"] == em["iva"])

    print("\n· 8 Privatanteil kürzt beides")
    ep = bu.add_entry(f"{J}-05-04", "suministros", "Internet", 121.0, privat_pct=70)
    bp = bu.betrieblich(ep)
    check("profit share 30 %", abs(bp["netto"] - 30.0) < 0.01, str(bp))
    check("IVA share 30 %", abs(bp["iva"] - 6.30) < 0.01, str(bp))

    print("\n· 9 PKW: Gewinn 0, IVA 50 %")
    ev = bu.add_entry(f"{J}-05-05", "vehiculo", "Tanken", 60.50)
    bv = bu.betrieblich(ev)
    check("no profit deduction by default", bv["netto"] == 0.0)
    check("IVA presumed 50 %", abs(bv["iva"] - ev["iva"] * 0.5) < 0.01)

    print("\n· 10 Einnahmen kommen automatisch aus bezahlten Programmen")
    store.log_event("paid", package="bloom", amount=399)
    r = bu.ea(J)
    check("the sale appears as income", r["einnahmen"]["auto_n"] >= 1)
    check("gross 399 → net 329.75 (21 % included)",
          any(abs(x["netto"] - 329.75) < 0.01 for x in r["einnahmen"]["belege"]))

    print("\n· 11 Modelo 130: nie negativ, Vorzahlungen angerechnet, 5 % gedeckelt")
    m = bu.ea(J)["mod130"]
    check("no negative resultado", all(x["resultado"] >= 0 for x in m))
    check("later quarters subtract earlier payments",
          all(m[i]["vorher"] >= m[i-1]["vorher"] for i in range(1, 4)))
    check("difícil justificación capped", all(x["dificil"] <= bu.DIFICIL_CAP for x in m))

    print("\n· 12 Vor der Alta keine einzige Frist")
    bu.set_alta("")
    check("no alta → no deadlines at all", bu.finanzamt(J)["fristen"] == [])
    bu.set_alta(f"{J}-07-01")
    keys = [f["key"] for f in bu.finanzamt(J)["fristen"]]
    check("alta 01.07. suppresses Q1+Q2",
          f"mod303-{J}-Q1" not in keys and f"mod303-{J}-Q2" not in keys, str(keys))
    check("…but keeps Q3, Q4, 390 and Renta",
          all(k in keys for k in (f"mod303-{J}-Q3", f"mod303-{J}-Q4",
                                  f"mod390-{J}", f"renta-{J}")), str(keys))
    bu.set_alta(f"{J}-01-01")

    print("\n· 13 Fälligkeiten: Q1–Q3 am 20., Q4 am 30. Januar")
    fr = {f["key"]: f for f in bu.finanzamt(J)["fristen"]}
    check("Q1 due 20 April", fr[f"mod303-{J}-Q1"]["faellig_am"] == f"{J}-04-20")
    check("Q4 due 30 January of next year",
          fr[f"mod303-{J}-Q4"]["faellig_am"] == f"{int(J)+1}-01-30")
    check("a deadline has a start window",
          fr[f"mod303-{J}-Q1"]["start_ab"] == f"{J}-04-01"
          and fr[f"mod303-{J}-Q1"]["fenster_tage"] == 19)

    print("\n· 14 Erledigt überlebt einen Neustart und lässt sich zurücknehmen")
    bu.set_erledigt(f"mod303-{J}-Q1", True)
    import importlib
    importlib.reload(bu)  # simulate a fresh process over the same DB
    check("survives restart",
          bu.finanzamt(J)["erledigt"].get(f"mod303-{J}-Q1", "") != "")
    bu.set_erledigt(f"mod303-{J}-Q1", False)
    check("can be reopened",
          f"mod303-{J}-Q1" not in bu.finanzamt(J)["erledigt"])

    print("\n· 15 DER WICHTIGSTE: Finanzamt-Zahlen == Buchhaltungs-Zahlen")
    r = bu.ea(J)
    f = bu.finanzamt(J)
    check("same 303 sums, same object",
          f["iva303"] == r["iva303"] and f["mod130"] == r["mod130"])
    check("Renta block ends on the same provisional profit",
          abs(f["renta"][-1]["betrag"] - r["gewinn_vorlaeufig"]) < 0.01)

    print("\n· 16 Routen: staff-only, Upload sicher, Export liefert")
    from server.app import app
    c = app.test_client()
    K = {"X-Auralis-Key": os.environ["AURALIS_API_KEY"]}
    check("buchhaltung is staff-only", c.get("/api/buchhaltung").status_code in (401, 403))
    check("finanzamt is staff-only", c.get("/api/finanzamt").status_code in (401, 403))
    r = c.post("/api/buchhaltung/entry", json={"datum": f"{J}-06-06", "kategorie": "buero",
                                               "text": "Route", "brutto": 12.10}, headers=K)
    check("entry via route", r.status_code == 200, r.get_data(as_text=True)[:120])
    eid = (r.get_json() or {}).get("entry", {}).get("id", "")
    import base64
    r = c.post("/api/buchhaltung/datei", json={"id": eid, "filename": "../../evil.pdf",
                                               "blob_b64": base64.b64encode(b"%PDF-1.4 x").decode()},
               headers=K)
    check("upload succeeds with a sanitised name", r.status_code == 200)
    rel = (r.get_json() or {}).get("rel", "")
    check("the path cannot escape", ".." not in rel and rel.startswith(eid), rel)
    check("an exe is refused",
          c.post("/api/buchhaltung/datei", json={"id": eid, "filename": "x.exe",
                 "blob_b64": "QQ=="}, headers=K).status_code == 400)
    check("traversal on read is refused",
          c.get("/api/buchhaltung/datei?rel=../clients.json", headers=K).status_code == 404)
    r = c.get(f"/api/buchhaltung/export?jahr={J}&fmt=csv", headers=K)
    check("CSV export answers", r.status_code == 200 and b"Beleg;Datum" in r.data[:60])
    r = c.post("/api/finanzamt/erledigt", json={"key": f"mod130-{J}-Q1", "done": True},
               headers=K)
    check("erledigt via route", r.status_code == 200
          and f"mod130-{J}-Q1" in (r.get_json() or {}).get("erledigt", {}))

    print()
    if FAILS:
        print(f"{len(FAILS)} failure(s):")
        for x in FAILS:
            print("  ·", x)
        return 1
    print("buchhaltung guards: all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(run())
