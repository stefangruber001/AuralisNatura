"""Buchhaltung & Finanzamt für Auralis Natura — spanisches Recht (autónoma, Barcelona).

Nach der Paramur-Bauanleitung gebaut, aber vollständig auf Spanien übersetzt:
Desiree gründet als autónoma in Barcelona (estimación directa simplificada).
Die Regeln, die den Aufbau bestimmen — wer sie später einbaut, baut zweimal:

  · Zufluss/Abfluss (criterio de cobros y pagos, Art. 7.2 RIRPF, auf dem
    Modelo 036/037 zu wählen, bindet 3 Jahre): es zählt das ZAHLdatum.
  · Belege fortlaufend und lückenlos je Jahr (A-2026-0001 …), nie löschen —
    nur stornieren. Aufbewahrung: 6 Jahre (Art. 30 Código de Comercio;
    steuerlich 4 Jahre, Art. 66 LGT — die 6 gewinnen).
  · IVA-Sätze 21 / 10 / 4 / 0. Coaching ist mit 21 % STEUERPFLICHTIG — die
    Befreiung für Heilberufe (Art. 20.Uno.3 LIVA) gilt NICHT, Desiree ist
    keine sanitaria (dieselbe Wahrheit wie §2 der Guardrails).
  · Atenciones a clientes (Kundengeschenke/-bewirtung): als Ausgabe mit Beleg
    absetzbar, aber der IVA darauf ist NIE abziehbar (Art. 96.Uno.5 LIVA) —
    die spanische Umkehrung der österreichischen Bewirtungs-Falle.
  · Eigene Verpflegung unterwegs: max. 26,67 €/Tag (Inland, ohne Übernachtung,
    elektronisch gezahlt, Gastronomie — Art. 30.2.5ª LIRPF).
  · Privat-PKW: IVA zu 50 % vermutet abziehbar (Art. 95.Tres LIVA), als
    IRPF-Ausgabe ohne ausschließlich betriebliche Nutzung NICHT absetzbar —
    Vorbelegung hier: Gewinnwirkung 0, IVA 50 %.
  · Privatanteil kürzt Aufwand UND IVA (z. B. Homeoffice-Suministros: 30 %
    des Flächenanteils, Art. 30.2.5ª.b LIRPF — als privat_pct erfasst).
  · Simplificada: +5 % gastos de difícil justificación (max. 2.000 €/Jahr)
    auf den positiven Rohüberschuss; Grenze der Simplificada: 600.000 €
    Vorjahresumsatz — Warnung, wenn es eng wird.
  · Modelo 303 (IVA) quartalsweise: 1.–20.4. / 20.7. / 20.10., Q4 bis 30.1.;
    Lastschrift (domiciliación) endet 5 Tage früher. Modelo 390 (Jahres-
    zusammenfassung) 1.–30.1. Modelo 130 (IRPF-Vorauszahlung, 20 % des
    kumulierten Nettoertrags minus bereits gezahlt) in denselben Fenstern.
    Renta (Modelo 100): Kampagne ~April bis 30.6. des Folgejahres.
  · Vor der Alta (Modelo 036/037) gibt es KEINE Pflichten: ohne hinterlegtes
    Alta-Datum erscheint keine einzige Frist — sonst begrüßt die Konsole
    einen Betrieb, der noch gar nicht existiert, mit überfälligen Terminen.

Der Finanzamt-Teil rechnet NICHTS eigenes: er liest dieselbe ea()-Auswertung.
Wer die Zahl an zwei Stellen berechnet, hat irgendwann zwei Wahrheiten.

Einnahmen kommen automatisch aus den bezahlten Programmen (paid-Events aus
der events-Tabelle — Stripe-Webhook und 💶-Knopf schreiben sie); erfasst
werden von Hand nur Ausgaben-Belege und sonstige Einnahmen. Die Preise
199/399/899 sind Endpreise INKLUSIVE 21 % IVA.
"""
from __future__ import annotations

import datetime as _dt
import json
import re
import shutil
import sqlite3
import subprocess
import threading
import uuid
from contextlib import closing
from pathlib import Path

from . import cfg, store

_LOCK = threading.RLock()
_INIT = False

IVA_SAETZE = (21, 10, 4, 0)
IVA_STANDARD = 21.0                    # Dienstleistungssatz — Coaching ist nicht befreit
SIMPLIFICADA_GRENZE = 600_000.0        # Art. 30 RIRPF — darüber estimación directa normal
DIFICIL_PCT = 5.0                      # gastos de difícil justificación (seit 2024 wieder 5 %)
DIFICIL_CAP = 2_000.0                  # Jahresdeckel
MOD130_PCT = 20.0                      # pago fraccionado
FENSTER_TAGE = 80                      # Fristen-Sichtfenster

# ── Kategorien — die zentrale Tabelle ────────────────────────────────────────
# `renta` ist die Rubrik, unter der der Betrag in Renta Web (Modelo 100,
# Wirtschaftstätigkeit) eingetragen wird — dadurch ist der Jahres-Export für
# die Gestoría 1:1 übernehmbar. `iva` ist nur die VORBELEGUNG des Satzes im
# Formular. `abzug_pct` wirkt auf den Gewinn, `iva_abzug_pct` auf den
# IVA-Abzug — in Spanien laufen die beiden auseinander (atenciones, PKW).
KATEGORIEN = [
 {"key": "material",   "name": "Material & Waren",                              "renta": "Consumos de explotación",                   "iva": 21},
 {"key": "fremd",      "name": "Fremdleistungen (Design, Übersetzung …)",       "renta": "Servicios de profesionales independientes", "iva": 21},
 {"key": "gestoria",   "name": "Gestoría, Recht & Beratung",                    "renta": "Servicios de profesionales independientes", "iva": 21},
 {"key": "miete",      "name": "Miete, Coworking & Raum",                       "renta": "Arrendamientos y cánones",                  "iva": 21},
 {"key": "suministros","name": "Strom, Wasser, Internet (Homeoffice-Anteil)",   "renta": "Suministros",                               "iva": 21},
 {"key": "software",   "name": "Software, Telefon & Hosting",                   "renta": "Otros servicios exteriores",                "iva": 21},
 {"key": "werbung",    "name": "Marketing & Werbung",                           "renta": "Otros servicios exteriores",                "iva": 21},
 {"key": "buero",      "name": "Büromaterial & Porto",                          "renta": "Otros servicios exteriores",                "iva": 21},
 {"key": "reise",      "name": "Reisen & Transport",                            "renta": "Otros servicios exteriores",                "iva": 10},
 {"key": "manutencion","name": "Verpflegung unterwegs (max. 26,67 €/Tag)",      "renta": "Manutención del titular",                   "iva": 10},
 {"key": "atenciones", "name": "Kundengeschenke & Bewirtung (IVA nie abziehbar)","renta": "Otros servicios exteriores",               "iva": 21, "iva_abzug_pct": 0},
 {"key": "vehiculo",   "name": "PKW (privat kaum absetzbar — Gestoría fragen)", "renta": "—",                                         "iva": 21, "iva_abzug_pct": 50, "abzug_pct": 0},
 {"key": "formacion",  "name": "Fortbildung & Fachliteratur",                   "renta": "Otros servicios exteriores",                "iva": 21},
 {"key": "versich",    "name": "Versicherungen",                                "renta": "Primas de seguros",                         "iva": 0},
 {"key": "reta",       "name": "Seguridad Social (RETA-Beitrag)",               "renta": "Seguridad Social del titular",              "iva": 0},
 {"key": "bank",       "name": "Bank- & Stripe-Gebühren",                       "renta": "Gastos financieros",                        "iva": 0},
 {"key": "tributos",   "name": "Gebühren & Abgaben (Tasas)",                    "renta": "Tributos fiscalmente deducibles",           "iva": 0},
 {"key": "equipo",     "name": "Ausstattung bis 300 € (sofort absetzbar)",      "renta": "Amortizaciones",                            "iva": 21},
 {"key": "sonstig",    "name": "Sonstige Betriebsausgaben",                     "renta": "Otros servicios exteriores",                "iva": 21},
 # NEUTRAL: Geld fließt ab, aber keine Betriebsausgabe. Ohne diese Trennung
 # stimmt entweder der Kontostand nicht oder der Gewinn.
 {"key": "aeat_iva",   "name": "AEAT: IVA-Zahlung (Modelo 303)",                "renta": "—", "iva": 0, "neutral": True},
 {"key": "aeat_irpf",  "name": "AEAT: IRPF-Vorauszahlung (Modelo 130)",         "renta": "—", "iva": 0, "neutral": True},
 {"key": "privat",     "name": "Privatentnahme",                                "renta": "—", "iva": 0, "neutral": True},
]
_KAT = {k["key"]: k for k in KATEGORIEN}


# ── Store: eigene Tabellen in der bestehenden SQLite-DB ──────────────────────
# store._DB ist auf dem Server nach /var/lib/auralis symlinkt, wird stündlich
# gesichert und vom Factory-Reset-Snapshot erfasst — genau die Eigenschaften,
# die Buchhaltungsdaten brauchen. Eine zweite JSON-Datei hätte keine davon.
def _conn() -> sqlite3.Connection:
    global _INIT
    c = sqlite3.connect(store._DB, timeout=15)
    c.execute("PRAGMA busy_timeout=15000")
    if not _INIT:
        c.execute("CREATE TABLE IF NOT EXISTS buch_entries("
                  "id TEXT PRIMARY KEY, jahr TEXT NOT NULL, beleg TEXT NOT NULL, "
                  "data TEXT NOT NULL)")
        c.execute("CREATE TABLE IF NOT EXISTS buch_meta(k TEXT PRIMARY KEY, v TEXT)")
        # Beleg-Leser: was gelesen wurde und was die Betreiberin daraus gemacht
        # hat — der Unterschied ist das Lernmaterial für den nächsten Scan.
        c.execute("CREATE TABLE IF NOT EXISTS buch_scans("
                  "id TEXT PRIMARY KEY, ts TEXT NOT NULL, lieferant TEXT, "
                  "extracted TEXT, final TEXT)")
        c.commit()
        _INIT = True
    return c


def _meta_get(key: str, default: str = "") -> str:
    with _LOCK, closing(_conn()) as c:
        row = c.execute("SELECT v FROM buch_meta WHERE k=?", (key,)).fetchone()
    return row[0] if row else default


def _meta_set(key: str, value: str) -> None:
    with _LOCK, closing(_conn()) as c, c:
        c.execute("INSERT INTO buch_meta(k,v) VALUES(?,?) "
                  "ON CONFLICT(k) DO UPDATE SET v=excluded.v", (key, value))


def get_alta() -> str:
    """Datum der Alta (Modelo 036/037) — vor diesem Tag existiert der Betrieb
    steuerlich nicht und KEINE Frist wird angezeigt."""
    return _meta_get("alta")


def set_alta(datum: str) -> None:
    if datum and not re.match(r"^\d{4}-\d{2}-\d{2}$", datum):
        raise ValueError("Datum als JJJJ-MM-TT")
    _meta_set("alta", datum)


def get_anfangsbestand() -> float:
    try:
        return float(_meta_get("anfangsbestand", "0") or 0)
    except ValueError:
        return 0.0


def set_anfangsbestand(betrag: float) -> None:
    _meta_set("anfangsbestand", f"{float(betrag):.2f}")


def _erledigt() -> dict:
    try:
        return json.loads(_meta_get("erledigt", "{}") or "{}")
    except Exception:
        return {}


def set_erledigt(key: str, done: bool) -> dict:
    """Abhaken UND wieder öffnen — beides muss gehen (versehentlich abgehakt)."""
    d = _erledigt()
    if done:
        d[key] = _dt.date.today().isoformat()
    else:
        d.pop(key, None)
    _meta_set("erledigt", json.dumps(d))
    return d


# ── Belege ───────────────────────────────────────────────────────────────────
def _rows(jahr: str = "") -> list[dict]:
    with _LOCK, closing(_conn()) as c:
        if jahr:
            rows = c.execute("SELECT data FROM buch_entries WHERE jahr=? ORDER BY beleg",
                             (jahr,)).fetchall()
        else:
            rows = c.execute("SELECT data FROM buch_entries ORDER BY beleg").fetchall()
    return [json.loads(r[0]) for r in rows]


def netto_aus_brutto(brutto: float, iva_satz: float) -> tuple[float, float]:
    """Immer aus dem BRUTTO rechnen — das ist die Zahl auf dem Beleg und die
    Zahl, die vom Konto abgeht."""
    netto = round(float(brutto) / (1 + float(iva_satz) / 100), 2)
    return netto, round(float(brutto) - netto, 2)


def add_entry(datum: str, kategorie: str, text: str, brutto: float,
              iva_satz: float | None = None, zahlung: str = "bank",
              status: str = "bezahlt", faellig_am: str = "",
              privat_pct: float = 0.0, notiz: str = "",
              typ: str = "ausgabe") -> dict:
    if kategorie not in _KAT and typ == "ausgabe":
        raise ValueError(f"unbekannte Kategorie {kategorie!r}")
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", datum or ""):
        raise ValueError("Datum als JJJJ-MM-TT")
    if float(brutto) <= 0:
        raise ValueError("Brutto muss positiv sein")
    if iva_satz is None:
        iva_satz = float(_KAT.get(kategorie, {}).get("iva", IVA_STANDARD))
    if float(iva_satz) not in [float(x) for x in IVA_SAETZE]:
        raise ValueError(f"IVA-Satz {iva_satz} — erlaubt: {IVA_SAETZE}")
    jahr = datum[:4]
    netto, ust = netto_aus_brutto(float(brutto), float(iva_satz))
    with _LOCK, closing(_conn()) as c, c:
        # Belegnummer lückenlos je Jahr — auch über Storni und Papierkorb
        # hinweg: gezählt wird, was existiert, nicht was gerade sichtbar ist.
        n = c.execute("SELECT COUNT(*) FROM buch_entries WHERE jahr=?", (jahr,)).fetchone()[0]
        beleg = f"A-{jahr}-{n + 1:04d}"
        e = {
            "id": uuid.uuid4().hex[:10], "beleg": beleg, "datum": datum,
            "typ": typ if typ in ("ausgabe", "einnahme_sonstig") else "ausgabe",
            "kategorie": kategorie, "text": str(text)[:300],
            "netto": netto, "iva_satz": float(iva_satz), "iva": ust,
            "brutto": round(float(brutto), 2),
            "zahlung": zahlung if zahlung in ("bank", "bar", "karte") else "bank",
            "notiz": str(notiz)[:500], "storniert": False,
            "status": status if status in ("bezahlt", "offen") else "bezahlt",
            "faellig_am": faellig_am if status == "offen" else "",
            "privat_pct": max(0.0, min(100.0, float(privat_pct or 0))),
            "dateien": [], "papierkorb": False,
            "erfasst_am": _dt.datetime.now().isoformat(timespec="seconds"),
        }
        c.execute("INSERT INTO buch_entries(id,jahr,beleg,data) VALUES(?,?,?,?)",
                  (e["id"], jahr, beleg, json.dumps(e, ensure_ascii=False)))
    return e


def _update(entry_id: str, fn) -> dict | None:
    with _LOCK, closing(_conn()) as c, c:
        row = c.execute("SELECT data FROM buch_entries WHERE id=?", (entry_id,)).fetchone()
        if not row:
            return None
        e = json.loads(row[0])
        fn(e)
        c.execute("UPDATE buch_entries SET data=?, jahr=?, beleg=? WHERE id=?",
                  (json.dumps(e, ensure_ascii=False), e["datum"][:4], e["beleg"], entry_id))
    return e


def get_entry(entry_id: str) -> dict | None:
    with _LOCK, closing(_conn()) as c:
        row = c.execute("SELECT data FROM buch_entries WHERE id=?", (entry_id,)).fetchone()
    return json.loads(row[0]) if row else None


def storno(entry_id: str) -> dict | None:
    """Nie löschen — der Eintrag bleibt, zählt aber in keiner Summe mehr."""
    return _update(entry_id, lambda e: e.update(storniert=True))


def bezahlt(entry_id: str, datum: str) -> dict | None:
    """Die Umbuchung: das ZAHLdatum wird zum Buchungsdatum (cobros y pagos)."""
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", datum or ""):
        raise ValueError("Zahldatum als JJJJ-MM-TT")
    return _update(entry_id, lambda e: e.update(status="bezahlt", datum=datum,
                                                faellig_am=""))


def papierkorb(entry_id: str, grund: str = "", restore: bool = False) -> dict | None:
    def fn(e):
        e["papierkorb"] = not restore
        e["papierkorb_grund"] = "" if restore else str(grund)[:200]
    return _update(entry_id, fn)


def add_datei(entry_id: str, rel: str, name: str, typ: str = "rechnung") -> dict | None:
    return _update(entry_id, lambda e: e["dateien"].append(
        {"rel": rel, "name": name, "typ": typ}))


# ── Rechenwege ───────────────────────────────────────────────────────────────
def betrieblich(e: dict) -> dict:
    """Privatanteil kürzt Aufwand UND IVA. Die Kategorie-Prozente laufen in
    Spanien getrennt: atenciones kürzen NUR den IVA (auf 0), der PKW den
    Gewinn (auf 0) und den IVA (auf 50 %)."""
    kat = _KAT.get(e.get("kategorie", ""), {})
    p = 1 - float(e.get("privat_pct", 0)) / 100
    abz = float(kat.get("abzug_pct", 100)) / 100
    iva_abz = float(kat.get("iva_abzug_pct", 100)) / 100
    return {
        "netto_voll": e["netto"],
        "netto": round(e["netto"] * p * abz, 2),          # Gewinnwirkung
        "iva_voll": e["iva"],
        "iva": round(e["iva"] * p * iva_abz, 2),           # IVA-Abzug
    }


def _einnahmen_auto(jahr: str) -> list[dict]:
    """Bezahlte Programme aus der events-Tabelle — Stripe-Webhook und der
    💶-Knopf schreiben beide ein paid-Event mit Betrag. Endpreis = brutto
    inkl. 21 % IVA. Nummeriert als I-<Jahr>-#### in Zeitreihenfolge; die
    förmliche factura-Serie kommt mit der Gestoría-Vorlage."""
    out = []
    n = 0
    for ev in store.list_events():
        if ev.get("event") != "paid" or not str(ev.get("ts", "")).startswith(jahr):
            continue
        brutto = float(ev.get("amount") or 0)
        if brutto <= 0:
            continue
        n += 1
        netto, ust = netto_aus_brutto(brutto, IVA_STANDARD)
        out.append({"beleg": f"I-{jahr}-{n:04d}", "datum": str(ev["ts"])[:10],
                    "text": f"Programm {ev.get('package', '') or '—'}",
                    "netto": netto, "iva_satz": IVA_STANDARD, "iva": ust,
                    "brutto": brutto, "auto": True})
    return out


def _q_of(datum: str) -> int:
    return (int(datum[5:7]) - 1) // 3 + 1


def ea(jahr: str) -> dict:
    """DIE eine Auswertung. Der Finanzamt-Teil liest dieses Ergebnis und
    rechnet nichts eigenes nach."""
    jahr = str(jahr)
    alle = [e for e in _rows(jahr) if not e.get("papierkorb")]
    aktiv = [e for e in alle if not e.get("storniert")]
    offen = [e for e in aktiv if e.get("status") == "offen"]
    gebucht = [e for e in aktiv if e.get("status") != "offen"]

    ein_auto = _einnahmen_auto(jahr)
    ein_man = [e for e in gebucht if str(e.get("typ", "")).startswith("einnahme")]
    einnahmen = ein_auto + [
        {"beleg": e["beleg"], "datum": e["datum"], "text": e["text"],
         "netto": e["netto"], "iva_satz": e["iva_satz"], "iva": e["iva"],
         "brutto": e["brutto"], "auto": False} for e in ein_man]
    einnahmen.sort(key=lambda x: x["datum"])

    aus_all = [e for e in gebucht if e.get("typ") == "ausgabe"]
    neutral = [e for e in aus_all if _KAT.get(e["kategorie"], {}).get("neutral")]
    aus = [e for e in aus_all if not _KAT.get(e["kategorie"], {}).get("neutral")]

    kat_rows, aus_netto, aus_iva, gek_n, gek_i = [], 0.0, 0.0, 0.0, 0.0
    for k in KATEGORIEN:
        if k.get("neutral"):
            continue
        es = [e for e in aus if e["kategorie"] == k["key"]]
        if not es:
            continue
        b = [betrieblich(e) for e in es]
        n_ = round(sum(x["netto"] for x in b), 2)
        i_ = round(sum(x["iva"] for x in b), 2)
        gek_n += sum(x["netto_voll"] - x["netto"] for x in b)
        gek_i += sum(x["iva_voll"] - x["iva"] for x in b)
        aus_netto += n_
        aus_iva += i_
        kat_rows.append({"key": k["key"], "name": k["name"], "renta": k["renta"],
                         "netto": n_, "iva": i_, "n": len(es),
                         "kuerzung": round(sum(x["netto_voll"] - x["netto"] for x in b), 2)})

    ein_netto = round(sum(e["netto"] for e in einnahmen), 2)
    ein_iva = round(sum(e["iva"] for e in einnahmen), 2)

    # ── IVA je Quartal (Modelo 303) ──────────────────────────────────────────
    quartale = []
    for q in (1, 2, 3, 4):
        qe = [e for e in einnahmen if _q_of(e["datum"]) == q]
        qa = [e for e in aus if _q_of(e["datum"]) == q]
        rep = round(sum(e["iva"] for e in qe), 2)
        sop = round(sum(betrieblich(e)["iva"] for e in qa), 2)
        quartale.append({"q": q, "basis": round(sum(e["netto"] for e in qe), 2),
                         "repercutido": rep, "soportado": sop,
                         "zahllast": round(rep - sop, 2)})

    # ── Modelo 130 je Quartal: 20 % kumuliert minus bereits gezahlt ─────────
    mod130, prior = [], 0.0
    for q in (1, 2, 3, 4):
        bis = [e for e in einnahmen if _q_of(e["datum"]) <= q]
        aus_bis = [betrieblich(e) for e in aus if _q_of(e["datum"]) <= q]
        ing = round(sum(e["netto"] for e in bis), 2)
        gas = round(sum(x["netto"] for x in aus_bis), 2)
        roh = ing - gas
        dificil = round(min(max(roh, 0) * DIFICIL_PCT / 100, DIFICIL_CAP), 2)
        rend = round(roh - dificil, 2)
        quota = round(max(rend, 0) * MOD130_PCT / 100, 2)
        res = round(max(quota - prior, 0.0), 2)
        mod130.append({"q": q, "ingresos": ing, "gastos": gas,
                       "dificil": dificil, "rendimiento": rend,
                       "quota": quota, "vorher": round(prior, 2), "resultado": res})
        prior += res

    dificil_jahr = mod130[-1]["dificil"] if mod130 else 0.0
    gewinn = round(ein_netto - aus_netto - dificil_jahr, 2)

    # ── Cashflow: alles Geld, auch das neutrale ─────────────────────────────
    anfang = get_anfangsbestand()
    monate, saldo = [], anfang
    for m in range(1, 13):
        mm = f"{jahr}-{m:02d}"
        ins = round(sum(e["brutto"] for e in einnahmen if e["datum"][:7] == mm), 2)
        outs = round(sum(e["brutto"] for e in aus_all if e["datum"][:7] == mm), 2)
        saldo = round(saldo + ins - outs, 2)
        monate.append({"monat": mm, "ein": ins, "aus": outs, "saldo": saldo})

    return {
        "jahr": jahr,
        "einnahmen": {"netto": ein_netto, "iva": ein_iva,
                      "brutto": round(sum(e["brutto"] for e in einnahmen), 2),
                      "belege": einnahmen, "auto_n": len(ein_auto)},
        "ausgaben": {"netto": round(aus_netto, 2), "iva": round(aus_iva, 2),
                     "belege": len(aus), "kategorien": kat_rows,
                     "gekuerzt_netto": round(gek_n, 2), "gekuerzt_iva": round(gek_i, 2)},
        "dificil": {"pct": DIFICIL_PCT, "cap": DIFICIL_CAP, "betrag": dificil_jahr},
        "gewinn_vorlaeufig": gewinn,
        "iva303": {"quartale": quartale,
                   "jahr": {"repercutido": round(sum(q["repercutido"] for q in quartale), 2),
                            "soportado": round(sum(q["soportado"] for q in quartale), 2),
                            "zahllast": round(sum(q["zahllast"] for q in quartale), 2)}},
        "mod130": mod130,
        "cashflow": {"anfangsbestand": anfang, "monate": monate,
                     "endbestand": monate[-1]["saldo"] if monate else anfang},
        "neutral": {"rows": [{"beleg": e["beleg"], "datum": e["datum"],
                              "name": _KAT[e["kategorie"]]["name"],
                              "brutto": e["brutto"]} for e in neutral],
                    "summe_brutto": round(sum(e["brutto"] for e in neutral), 2)},
        "offen": {"rows": offen,
                  "summe_brutto": round(sum(e["brutto"] for e in offen), 2)},
        "storniert": sum(1 for e in alle if e.get("storniert")),
    }


# ── Pflichten & Warnungen für den Buchhaltungs-Tab ───────────────────────────
def pflichten(jahr: str, ea_res: dict | None = None) -> dict:
    r = ea_res or ea(jahr)
    belege = [e for e in _rows(jahr)
              if not e.get("papierkorb") and not e.get("storniert")
              and e.get("typ") == "ausgabe"]
    ohne_doc = [e for e in belege if not e.get("dateien")]
    heute = _dt.date.today()
    faellig, bald = [], []
    for e in r["offen"]["rows"]:
        f = e.get("faellig_am") or e.get("datum")
        if f <= heute.isoformat():
            faellig.append(e)
        elif f <= (heute + _dt.timedelta(days=7)).isoformat():
            bald.append(e)
    warn = []
    if not get_alta():
        warn.append({"level": "warn", "text": "Kein Alta-Datum (Modelo 036/037) hinterlegt — "
                     "die Fristen im Finanzamt-Tab erscheinen erst damit. Vor der Alta gibt "
                     "es keine Pflichten; nach der Gründung hier eintragen."})
    umsatz = r["einnahmen"]["netto"]
    if umsatz > SIMPLIFICADA_GRENZE * 0.8:
        warn.append({"level": "err" if umsatz > SIMPLIFICADA_GRENZE else "warn",
                     "text": f"Umsatz {umsatz:,.0f} € — die estimación directa simplificada "
                             f"endet bei {SIMPLIFICADA_GRENZE:,.0f} € Vorjahresumsatz. "
                             "Mit der Gestoría den Wechsel planen."})
    if ohne_doc:
        warn.append({"level": "warn", "text": f"{len(ohne_doc)} Buchung(en) ohne Beleg-Datei — "
                     "der häufigste Prüfungsmangel. Foto oder PDF nachreichen."})
    bar = [e for e in r["einnahmen"]["belege"] if not e.get("auto")]
    _ = bar  # manuelle Einnahmen sind legitim; keine Warnung nötig
    # nächste Frist als Countdown
    tage_frist = None
    for f in finanzamt(jahr)["fristen"]:
        if not f["erledigt_am"]:
            tage_frist = f["tage"]
            break
    return {"ohne_dokument": [e["id"] for e in ohne_doc],
            "faellig": [e["id"] for e in faellig], "bald": [e["id"] for e in bald],
            "faellig_summe": round(sum(e["brutto"] for e in faellig), 2),
            "bald_summe": round(sum(e["brutto"] for e in bald), 2),
            "tage_bis_frist": tage_frist, "warnungen": warn}


# ── Finanzamt: Fristen mit Startfenster ──────────────────────────────────────
_SEDE = "https://sede.agenciatributaria.gob.es"


def _frist(key, titel, faellig, start_ab, start_grund, wohin, pfad, aktion, tun,
           betrag, kat, heute, erledigt):
    tage = (_dt.date.fromisoformat(faellig) - heute).days
    tage_start = (_dt.date.fromisoformat(start_ab) - heute).days
    return {
        "key": key, "titel": titel, "faellig_am": faellig, "tage": tage,
        "wohin": wohin, "pfad": pfad, "aktion": aktion, "tun": tun,
        "betrag": betrag, "url": _SEDE, "kategorie_key": kat,
        "erledigt_am": erledigt.get(key, ""),
        "start_ab": start_ab, "start_grund": start_grund,
        "startbar": tage_start <= 0, "tage_bis_start": max(tage_start, 0),
        "fenster_tage": (_dt.date.fromisoformat(faellig)
                         - _dt.date.fromisoformat(start_ab)).days,
        "puffer_tage": max(tage, 0),
        "sichtbar": tage < 0 or tage <= FENSTER_TAGE,
    }


def finanzamt(jahr: str) -> dict:
    """Fristen, Kennzahlen und Rücklagen — alles aus derselben ea()."""
    jahr = str(jahr)
    j = int(jahr)
    r = ea(jahr)
    heute = _dt.date.today()
    done = _erledigt()
    alta = get_alta()

    fristen = []
    # Modelo 303 + 130 je Quartal. Q1–Q3: 1.–20. des Folgemonats; Q4: 1.–30.1.
    # Lastschrift endet 5 Tage vor der Frist — steht in `tun`, nicht als eigene Frist.
    qdef = [(1, f"{j}-04-01", f"{j}-04-20"), (2, f"{j}-07-01", f"{j}-07-20"),
            (3, f"{j}-10-01", f"{j}-10-20"), (4, f"{j+1}-01-01", f"{j+1}-01-30")]
    for q, start, due in qdef:
        q303 = r["iva303"]["quartale"][q - 1]
        q130 = r["mod130"][q - 1]
        dom = (_dt.date.fromisoformat(due) - _dt.timedelta(days=5)).strftime("%d.%m.")
        fristen.append(_frist(
            f"mod303-{jahr}-Q{q}", f"Modelo 303 · IVA Q{q} {jahr}", due, start,
            "Quartal muss vorbei sein", "AEAT Sede Electrónica",
            "Todas las gestiones ▸ IVA ▸ Modelo 303",
            "IVA-Kennzahlen übertragen und absenden",
            f"Kennzahlen aus dem Block unten kopieren (Basis 21 %, IVA repercutido, "
            f"IVA soportado) → Ergebnis prüfen → absenden. Lastschrift (domiciliación) "
            f"nur bis {dom} möglich, danach NRC-Sofortzahlung.",
            q303["zahllast"], "aeat_iva", heute, done))
        fristen.append(_frist(
            f"mod130-{jahr}-Q{q}", f"Modelo 130 · IRPF Q{q} {jahr}", due, start,
            "Quartal muss vorbei sein", "AEAT Sede Electrónica",
            "Todas las gestiones ▸ IRPF ▸ Modelo 130",
            "IRPF-Vorauszahlung erklären (20 % kumuliert)",
            "Kumulierte Einnahmen und Ausgaben aus dem 130er-Block kopieren → "
            "Ergebnis " + f"{q130['resultado']:.2f}".replace(".", ",")
            + f" € → absenden. Lastschrift bis {dom}.",
            q130["resultado"], "aeat_irpf", heute, done))
    fristen.append(_frist(
        f"mod390-{jahr}", f"Modelo 390 · IVA-Jahreszusammenfassung {jahr}",
        f"{j+1}-01-30", f"{j+1}-01-01", "Jahr muss vorbei sein",
        "AEAT Sede Electrónica", "Todas las gestiones ▸ IVA ▸ Modelo 390",
        "Jahres-IVA zusammenfassen (informativ, keine Zahlung)",
        "Die vier 303er-Quartale werden zusammengefasst — Zahlen unten, Jahresblock.",
        None, "", heute, done))
    fristen.append(_frist(
        f"renta-{jahr}", f"Renta {jahr} (Modelo 100)", f"{j+1}-06-30",
        f"{j+1}-04-06", "Kampagnenstart der AEAT (Anfang April, variiert leicht)",
        "Renta Web (AEAT)", "Renta ▸ Servicio de tramitación ▸ actividades económicas",
        "Jahreserklärung einreichen",
        "Rubriken aus dem Renta-Block unten übertragen; die vier 130er-Zahlungen "
        "werden angerechnet. Mit der Gestoría gegenprüfen.",
        None, "", heute, done))

    # Vor der Alta gibt es keine Pflichten: Perioden, die vor der Alta enden,
    # fallen weg; ganz ohne Alta-Datum wird ALLES unterdrückt.
    def _period_ende(f):
        return (_dt.date.fromisoformat(f["start_ab"]) - _dt.timedelta(days=1)).isoformat()
    if alta:
        fristen = [f for f in fristen if _period_ende(f) >= alta]
    else:
        fristen = []
    fristen.sort(key=lambda f: f["faellig_am"])

    offen = [f for f in fristen if not f["erledigt_am"]]
    startbar = [f for f in offen if f["startbar"] and f["sichtbar"]]

    # Rücklagen — Richtwerte, keine Steuerberechnung: IRPF läuft progressiv,
    # die 20 % des Modelo 130 sind die ehrlichste einfache Näherung.
    gezahlt_130 = round(sum(x["resultado"] for x in r["mod130"]), 2)
    ruecklagen = {
        "hinweis": "Richtwerte — IRPF ist progressiv; die Gestoría rechnet den echten Satz.",
        "irpf": round(max(max(r["gewinn_vorlaeufig"], 0) * MOD130_PCT / 100
                          - gezahlt_130, 0), 2),
        "mod130_soll": gezahlt_130,
        "iva": max(r["iva303"]["jahr"]["zahllast"], 0),
    }

    by_renta: dict[str, float] = {}
    for row in r["ausgaben"]["kategorien"]:
        if row["renta"] == "—":
            continue
        by_renta[row["renta"]] = round(by_renta.get(row["renta"], 0) + row["netto"], 2)
    renta_rows = ([{"renta": "Ingresos de explotación", "betrag": r["einnahmen"]["netto"]}]
                  + [{"renta": k, "betrag": v} for k, v in by_renta.items()]
                  + [{"renta": f"Gastos de difícil justificación ({DIFICIL_PCT:.0f} %, max. {DIFICIL_CAP:.0f} €)",
                      "betrag": r["dificil"]["betrag"]},
                     {"renta": "Rendimiento neto (vorläufig)", "betrag": r["gewinn_vorlaeufig"]}])

    return {"jahr": jahr, "heute": heute.isoformat(), "alta": alta,
            "fenster_tage": FENSTER_TAGE, "fristen": fristen,
            "startbar_jetzt": [f["key"] for f in startbar],
            "iva303": r["iva303"], "mod130": r["mod130"],
            "renta": renta_rows, "ruecklagen": ruecklagen,
            "erledigt": done}


# ── Beleg-Leser: Foto/PDF → Vorschlag, den die Betreiberin bestätigt ─────────
# Der Leser bucht NIE selbst (Bauanleitung §4.4: der Operator bestätigt, die
# Maschine bucht nicht). Er wird mit jedem Upload besser, auf zwei ehrliche
# Arten — kein Training, nur Gedächtnis:
#   1. Lieferanten-Gedächtnis: hat die Betreiberin »Canva« schon dreimal als
#      Software @ 21 % gebucht, gewinnt IHRE Wahl über die Lese-Vermutung.
#   2. Korrektur-Beispiele: die letzten Abweichungen (gelesen ≠ gebucht)
#      wandern als Beispiele in den Lese-Prompt des nächsten Scans.
# Beides ist erklärbar — die Oberfläche sagt pro Feld, WOHER der Vorschlag
# stammt (»gelesen« oder »aus deinen früheren Buchungen«).

SCAN_FELDER = ("datum", "text", "brutto", "iva_satz", "kategorie")
_AUSGABE_KEYS = [k["key"] for k in KATEGORIEN if not k.get("neutral")]


def scan_verfuegbar() -> bool:
    return shutil.which("claude") is not None


def _norm_vendor(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(s or "").lower())[:60]


def _scan_rows() -> list[dict]:
    with _LOCK, closing(_conn()) as c:
        rows = c.execute("SELECT id,ts,lieferant,extracted,final FROM buch_scans "
                         "ORDER BY ts DESC LIMIT 400").fetchall()
    out = []
    for r in rows:
        try:
            out.append({"id": r[0], "ts": r[1], "lieferant": r[2] or "",
                        "extracted": json.loads(r[3]) if r[3] else {},
                        "final": json.loads(r[4]) if r[4] else {}})
        except Exception:
            continue
    return out


def _scan_save(scan_id: str, lieferant: str = "", extracted: dict | None = None,
               final: dict | None = None) -> None:
    with _LOCK, closing(_conn()) as c, c:
        row = c.execute("SELECT extracted,final,lieferant FROM buch_scans WHERE id=?",
                        (scan_id,)).fetchone()
        ex = json.dumps(extracted, ensure_ascii=False) if extracted is not None \
            else (row[0] if row else None)
        fi = json.dumps(final, ensure_ascii=False) if final is not None \
            else (row[1] if row else None)
        lf = lieferant or (row[2] if row else "")
        c.execute("INSERT INTO buch_scans(id,ts,lieferant,extracted,final) "
                  "VALUES(?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET "
                  "lieferant=excluded.lieferant, extracted=COALESCE(excluded.extracted,extracted), "
                  "final=COALESCE(excluded.final,final)",
                  (scan_id, _dt.datetime.now().isoformat(timespec="seconds"), lf, ex, fi))


def vendor_erfahrung() -> dict:
    """{lieferant_norm: {kategorie, iva_satz, n, name}} — die JÜNGSTE bestätigte
    Buchung je Lieferant gewinnt, n zählt, wie oft es so bestätigt wurde."""
    out: dict[str, dict] = {}
    for s in reversed(_scan_rows()):          # alt → neu, Neueres überschreibt
        fin = s["final"]
        v = _norm_vendor(s["lieferant"])
        if not v or not fin.get("kategorie"):
            continue
        prev = out.get(v)
        same = prev and prev["kategorie"] == fin.get("kategorie") \
            and prev["iva_satz"] == fin.get("iva_satz")
        out[v] = {"kategorie": fin.get("kategorie"),
                  "iva_satz": fin.get("iva_satz", IVA_STANDARD),
                  "n": (prev["n"] + 1 if same else 1),
                  "name": s["lieferant"]}
    return out


def _lern_beispiele(limit: int = 8) -> str:
    """Die letzten echten Korrekturen (gelesen ≠ gebucht) als Prompt-Beispiele —
    so lernt der Leser die Praxis dieser einen Betreiberin, Scan für Scan."""
    lines = []
    for s in _scan_rows():
        ex, fin = s["extracted"], s["final"]
        if not ex or not fin:
            continue
        diffs = [f for f in ("kategorie", "iva_satz") if ex.get(f) != fin.get(f)
                 and fin.get(f) not in (None, "")]
        if not diffs or not s["lieferant"]:
            continue
        lines.append(f"- {s['lieferant']}: " + ", ".join(
            f"{f} ist {fin[f]!r} (nicht {ex.get(f)!r})" for f in diffs))
        if len(lines) >= limit:
            break
    return ("\nAus früheren Korrekturen der Betreiberin (befolge sie bei "
            "denselben oder ähnlichen Lieferanten):\n" + "\n".join(lines) + "\n"
            ) if lines else ""


def _sanitize_scan(d: dict) -> tuple[dict, dict]:
    """Aus dem Lese-Ergebnis wird ein Vorschlag — nie mehr. Unbrauchbare Felder
    fallen weg (leer heißt: von Hand ausfüllen), nichts wird erraten."""
    felder: dict = {}
    quelle: dict = {}
    unsicher = {str(x) for x in (d.get("unsicher") or [])}
    dat = str(d.get("datum", ""))
    if re.match(r"^\d{4}-\d{2}-\d{2}$", dat):
        try:
            _dt.date.fromisoformat(dat)
            felder["datum"] = dat
        except ValueError:
            pass
    txt = str(d.get("text", "")).strip()[:300]
    if txt:
        felder["text"] = txt
    try:
        br = round(float(d.get("brutto")), 2)
        if 0 < br < 1_000_000:
            felder["brutto"] = br
    except (TypeError, ValueError):
        pass
    try:
        iva = float(d.get("iva_satz"))
        if iva in [float(x) for x in IVA_SAETZE]:
            felder["iva_satz"] = iva
    except (TypeError, ValueError):
        pass
    kat = str(d.get("kategorie", ""))
    if kat in _AUSGABE_KEYS:
        felder["kategorie"] = kat
    for f in felder:
        quelle[f] = "gelesen — unsicher" if f in unsicher else "gelesen"
    lieferant = str(d.get("lieferant", "")).strip()[:120]
    return felder, quelle | {"lieferant": lieferant}


def scan_beleg(scan_id: str, path: Path) -> dict:
    """Eine Datei lesen. Wirft bei CLI-Fehlern — der Aufrufer degradiert ehrlich
    (Datei bleibt gespeichert, Formular wird von Hand gefüllt)."""
    kats = "\n".join(f'  "{k["key"]}" = {k["name"]}' for k in KATEGORIEN
                     if not k.get("neutral"))
    prompt = f"""Du liest einen Ausgaben-Beleg (Foto oder PDF) für die Buchhaltung einer
Gesundheitscoaching-Praxis in Barcelona (Spanien). Lies die Datei: {path}

Antworte NUR mit einem JSON-Objekt, kein Text davor oder danach:
{{"datum":"JJJJ-MM-TT","lieferant":"…","text":"kurzer deutscher Buchungstext: Lieferant + Leistung","brutto":0.00,"iva_satz":21,"kategorie":"…","unsicher":["…"]}}

Regeln:
- datum: das Beleg-/Zahldatum. brutto: der ENDBETRAG inkl. IVA (die Zahl, die
  tatsächlich bezahlt wurde), Punkt als Dezimaltrenner.
- iva_satz: 21, 10, 4 oder 0 — wie auf dem Beleg ausgewiesen; ohne Ausweis: 0.
- kategorie: GENAU einer dieser Schlüssel:
{kats}
- "unsicher": Liste jedes Feldes, bei dem du nicht sicher bist. Lieber unsicher
  melden als raten — die Betreiberin bestätigt jede Zeile von Hand.
{_lern_beispiele()}"""
    proc = subprocess.run(["claude", "-p", prompt, "--output-format", "text"],
                          capture_output=True, text=True, timeout=150)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip()[:200] or "claude cli error")
    m = re.search(r"\{.*\}", proc.stdout, re.S)
    if not m:
        raise RuntimeError("keine JSON-Antwort vom Leser")
    raw = json.loads(m.group(0))
    felder, quelle = _sanitize_scan(raw)
    lieferant = quelle.pop("lieferant", "")
    # gespeichert wird, was der LESER sagte — die Differenz zur späteren
    # Buchung ist das Lernmaterial; ein Gedächtnis-Override darf sie nicht
    # unsichtbar machen
    _scan_save(scan_id, lieferant=lieferant, extracted=dict(felder))
    # Lieferanten-Gedächtnis: die bestätigte Praxis der Betreiberin gewinnt
    mem = vendor_erfahrung().get(_norm_vendor(lieferant))
    if mem and mem.get("kategorie") in _AUSGABE_KEYS:
        felder["kategorie"] = mem["kategorie"]
        quelle["kategorie"] = f"aus deinen Buchungen ({mem['n']}× {mem['name']})"
        try:
            if float(mem.get("iva_satz")) in [float(x) for x in IVA_SAETZE]:
                felder["iva_satz"] = float(mem["iva_satz"])
                quelle["iva_satz"] = quelle["kategorie"]
        except (TypeError, ValueError):
            pass
    return {"felder": felder, "quelle": quelle, "lieferant": lieferant}


def scan_feedback(scan_id: str, final: dict) -> None:
    """Was wirklich gebucht wurde — die Differenz zum Gelesenen ist das
    Lernmaterial für den nächsten Scan."""
    fin = {f: final.get(f) for f in SCAN_FELDER if final.get(f) not in (None, "")}
    _scan_save(scan_id, lieferant=str(final.get("lieferant", ""))[:120] or "",
               final=fin)
