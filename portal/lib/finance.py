"""Pure finance calculator for the Finanzen tab (Paramur-pattern).

Inputs: the editable plan (config/plan.json, template plan.example.json), the
package price list (config.packages) and the anonymous events log (won/paid
amounts per month). Output: GuV (Plan vs Ist), 12-month cashflow table,
simplified balance sheet, break-even and scenario table — all plain dicts,
no I/O side effects beyond reading config. German labels; the UI formats
numbers (1.234,56 €).

Honesty rules (never fake numbers):
- "Ist" revenue comes only from logged events (won packages).
- Actual costs are not tracked -> Ist-Kosten are the plan pro-rated over the
  elapsed months and clearly labelled "Plan-Näherung".
- The Bilanz is a simplified founder view (Kasse, Forderungen, USt, Eigen-
  kapital), labelled as such.
"""
from __future__ import annotations
import json, shutil, datetime as _dt
from . import cfg, store


def _plan_path():
    return cfg.CONFIG_DIR / "plan.json"


def get_plan() -> dict:
    p = _plan_path()
    if not p.exists():
        tpl = cfg.CONFIG_DIR / "plan.example.json"
        if tpl.exists():
            shutil.copy(tpl, p)
        else:
            p.write_text("{}", encoding="utf-8")
    with open(p, encoding="utf-8") as f:
        d = json.load(f)
    d.pop("_comment", None)
    return d


def patch_plan(dotpath: str, value) -> dict:
    """Set a single value by dot path, e.g. 'kosten_monatlich.marketing'."""
    plan = get_plan()
    parts = [p for p in str(dotpath).split(".") if p]
    if not parts:
        raise ValueError("empty path")
    node = plan
    for part in parts[:-1]:
        node = node.setdefault(part, {})
        if not isinstance(node, dict):
            raise ValueError(f"path collision at {part!r}")
    node[parts[-1]] = value
    tmp = _plan_path().with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(plan, f, ensure_ascii=False, indent=2)
    tmp.replace(_plan_path())
    return plan


# ---------- helpers ----------
def _package_prices() -> dict:
    return {p["key"]: float(p.get("price") or 0) for p in cfg.config().get("packages", [])}


def _months_of(year: int) -> list[str]:
    return [f"{year:04d}-{m:02d}" for m in range(1, 13)]


def _actual_revenue_by_month(events: list[dict], year: int) -> dict:
    out = {m: 0.0 for m in _months_of(year)}
    for e in events:
        if e.get("event") == "won" and e.get("ts", "")[:4] == str(year):
            out[e["ts"][:7]] = out.get(e["ts"][:7], 0.0) + float(e.get("amount") or 0)
    return out


# ---------- the full report ----------
def report(events: list[dict] | None = None, today: _dt.date | None = None) -> dict:
    plan = get_plan()
    today = today or _dt.date.today()
    year = int((plan.get("ziele") or {}).get("jahr") or today.year)
    months = _months_of(year)
    elapsed = 12 if year < today.year else (0 if year > today.year else today.month)
    prices = _package_prices()
    if events is None:
        events = store.list_events()

    # ---- Plan revenue ----
    mp = plan.get("mengenplan", {})
    plan_monthly_rev = 0.0
    plan_rev_rows = []
    for key, m in mp.items():
        price = float(m.get("preis_annahme") or prices.get(key) or 0)
        per_month = float(m.get("pro_monat") or 0)
        rev_y = per_month * price * 12
        plan_monthly_rev += per_month * price
        plan_rev_rows.append({"paket": key, "pro_monat": per_month, "preis": price,
                              "umsatz_jahr": round(rev_y, 2)})
    plan_rev_year = round(plan_monthly_rev * 12, 2)

    # ---- Ist revenue (events) ----
    ist_by_month = _actual_revenue_by_month(events, year)
    ist_rev_ytd = round(sum(ist_by_month[m] for m in months[:elapsed]), 2)
    ist_rev_by_pkg: dict = {}
    for e in events:
        if e.get("event") == "won" and e.get("ts", "")[:4] == str(year):
            k = e.get("package") or "unbekannt"
            ist_rev_by_pkg[k] = round(ist_rev_by_pkg.get(k, 0) + float(e.get("amount") or 0), 2)

    # ---- Costs ----
    km = {k: float(v) for k, v in plan.get("kosten_monatlich", {}).items()}
    ke = {k: float(v) for k, v in plan.get("kosten_einmalig", {}).items()}
    cost_month = sum(km.values())
    plan_cost_year = round(cost_month * 12 + sum(ke.values()), 2)
    ist_cost_ytd = round(cost_month * elapsed + sum(ke.values()) * (1 if elapsed else 0), 2)

    st = plan.get("steuern", {})
    iva = float(st.get("iva_satz") or 0.21)
    irpf = float(st.get("irpf_satz") or 0.20)

    # gross prices -> the IVA share inside collected revenue is owed to Hacienda
    def iva_part(gross): return round(gross * iva / (1 + iva), 2)
    def net_of_iva(gross): return round(gross / (1 + iva), 2)

    # ---- GuV (Plan vs Ist YTD) ----
    guv_rows = []
    guv_rows.append({"pos": "Umsatzerlöse (brutto)", "plan": plan_rev_year, "ist": ist_rev_ytd})
    guv_rows.append({"pos": "davon IVA (21 %) abzuführen", "plan": -iva_part(plan_rev_year),
                     "ist": -iva_part(ist_rev_ytd)})
    guv_rows.append({"pos": "Nettoumsatz", "plan": net_of_iva(plan_rev_year),
                     "ist": net_of_iva(ist_rev_ytd)})
    for k, v in sorted(km.items()):
        guv_rows.append({"pos": f"Kosten · {k}", "plan": -round(v * 12, 2),
                         "ist": -round(v * elapsed, 2), "note": "Ist = Plan-Näherung"})
    for k, v in sorted(ke.items()):
        guv_rows.append({"pos": f"Einmalig · {k}", "plan": -v, "ist": -(v if elapsed else 0),
                         "note": "Ist = Plan-Näherung"})
    ebit_plan = round(net_of_iva(plan_rev_year) - plan_cost_year, 2)
    ebit_ist = round(net_of_iva(ist_rev_ytd) - ist_cost_ytd, 2)
    guv_rows.append({"pos": "Betriebsergebnis (EBIT)", "plan": ebit_plan, "ist": ebit_ist, "strong": True})
    guv_rows.append({"pos": f"IRPF-Rückstellung ({int(irpf*100)} %)",
                     "plan": -round(max(0, ebit_plan) * irpf, 2),
                     "ist": -round(max(0, ebit_ist) * irpf, 2)})
    res_plan = round(ebit_plan - max(0, ebit_plan) * irpf, 2)
    res_ist = round(ebit_ist - max(0, ebit_ist) * irpf, 2)
    guv_rows.append({"pos": "Ergebnis nach Steuern", "plan": res_plan, "ist": res_ist, "strong": True})

    # ---- Cashflow: 12-month table (Ist for elapsed, Plan for future) ----
    cash_rows = []
    kum = 0.0
    for i, m in enumerate(months):
        einz = ist_by_month[m] if i < elapsed else round(plan_monthly_rev, 2)
        ausz = cost_month + (sum(ke.values()) if i == 0 else 0)
        iva_out = iva_part(einz)
        netto = round(einz - ausz - iva_out, 2)
        kum = round(kum + netto, 2)
        cash_rows.append({"monat": m, "einzahlungen": round(einz, 2),
                          "auszahlungen": round(ausz, 2), "iva": iva_out,
                          "netto": netto, "kumuliert": kum,
                          "typ": "ist" if i < elapsed else "plan"})

    # ---- Simplified Bilanz (Stichtag = today) ----
    kasse = round(sum(r["netto"] for r in cash_rows[:elapsed]), 2)
    # Forderungen: won but unpaid packages (live records)
    forderungen = 0.0
    for r in store.list_records():
        rec = store.get(r["client_id"]) or {}
        pkg = rec.get("package") or {}
        ix = store.stage_index(rec.get("stage", ""))
        if pkg.get("price") and (rec.get("won_at") or ix == store.stage_index("won")) \
           and ix >= store.stage_index("won") \
           and rec.get("stage") != "lost" and not rec.get("paid"):
            forderungen += float(pkg["price"])
    forderungen = round(forderungen, 2)
    iva_verb = iva_part(ist_rev_ytd)
    aktiva = round(kasse + forderungen, 2)
    eigenkapital = round(aktiva - iva_verb, 2)
    bilanz = {
        "stichtag": today.isoformat(),
        "aktiva": [{"pos": "Kasse / Bank (kumulierter Cashflow)", "wert": kasse},
                   {"pos": "Forderungen (gewonnen, unbezahlt)", "wert": forderungen},
                   {"pos": "Summe Aktiva", "wert": aktiva, "strong": True}],
        "passiva": [{"pos": "Eigenkapital (rechnerisch)", "wert": eigenkapital},
                    {"pos": "Verbindlichkeit IVA (abzuführen)", "wert": iva_verb},
                    {"pos": "Summe Passiva", "wert": round(eigenkapital + iva_verb, 2), "strong": True}],
        "hinweis": "Vereinfachte Gründerinnen-Bilanz: Kasse aus Ist-Cashflow, Kosten als Plan-Näherung, ohne Anlagevermögen.",
    }

    # ---- Break-even ----
    kon = plan.get("konversion", {})
    b2g = float(kon.get("buchung_zu_gespraech") or 0.8)
    g2k = float(kon.get("gespraech_zu_kunde") or 0.35)
    total_pm = sum(float(m.get("pro_monat") or 0) for m in mp.values()) or 1
    avg_price = plan_monthly_rev / total_pm if total_pm else 0
    contribution = net_of_iva(avg_price)   # no variable costs in a coaching business
    be_clients = round(cost_month / contribution, 2) if contribution else 0
    be_calls = round(be_clients / g2k, 1) if g2k else 0
    be_bookings = round(be_calls / b2g, 1) if b2g else 0
    breakeven = {"fixkosten_monat": round(cost_month, 2),
                 "deckungsbeitrag_je_kunde": round(contribution, 2),
                 "kunden_pro_monat": be_clients, "gespraeche_pro_monat": be_calls,
                 "buchungen_pro_monat": be_bookings,
                 "hinweis": f"Ø Paketpreis {avg_price:.0f} € brutto · Konversion {int(b2g*100)} % / {int(g2k*100)} %"}

    # ---- Szenarien ----
    szen = []
    for name, f in (plan.get("szenarien") or {"konservativ": .55, "basis": 1.0, "ambitioniert": 1.5}).items():
        rev = round(plan_rev_year * float(f), 2)
        ebit = round(net_of_iva(rev) - plan_cost_year, 2)
        szen.append({"szenario": name, "faktor": float(f), "umsatz": rev,
                     "kosten": plan_cost_year, "ebit": ebit,
                     "nach_steuern": round(ebit - max(0, ebit) * irpf, 2)})

    ziel = float((plan.get("ziele") or {}).get("jahresumsatz") or plan_rev_year or 1)
    return {
        "jahr": year, "monate_vergangen": elapsed,
        "ziel": {"jahresumsatz": ziel, "erreicht": ist_rev_ytd,
                 "quote": round(ist_rev_ytd / ziel * 100, 1) if ziel else 0},
        "plan_umsatz": {"jahr": plan_rev_year, "monat": round(plan_monthly_rev, 2),
                        "rows": plan_rev_rows},
        "ist_umsatz": {"ytd": ist_rev_ytd, "nach_paket": ist_rev_by_pkg},
        "guv": guv_rows, "cashflow": cash_rows, "bilanz": bilanz,
        "breakeven": breakeven, "szenarien": szen,
    }
