"""The Art. 15 Datenauskunft as a readable document, not a JSON dump.

Same approach as mailv2: the installed v2 template is the layout, this module
swaps the worked sample for the real record. Strict where it matters — the one
unacceptable outcome is another client's sample data inside somebody's legal
data export, so the final guard asserts no trace of the sample survives.
"""
from __future__ import annotations

import html
import json
import re
from pathlib import Path

_DOC: str | None = None


def _e(v) -> str:
    return html.escape(str(v if v is not None else ""))


def _load() -> str:
    global _DOC
    if _DOC is None:
        _DOC = (Path(__file__).resolve().parent / "gdpr_v2.html").read_text(encoding="utf-8")
    return _DOC


def _span(doc: str, start_marker: str, end_marker: str) -> tuple[int, int]:
    a = doc.index(start_marker)
    b = doc.index(end_marker, a)
    return a, b


def render(cid: str, info: dict, rec: dict, exported: str) -> str:
    doc = _load()

    # header: real id + timestamp, the sample chip goes
    doc = doc.replace("Datenauskunft nach Art. 15 DSGVO — Elena Martín",
                      f"Datenauskunft nach Art. 15 DSGVO — {_e(info.get('name', cid))}")
    doc = doc.replace("Klientin AN-0042", f"Klientin {_e(cid)}")
    doc = doc.replace("Exportiert 2026-08-15 &middot; 09:00", f"Exportiert {_e(exported)}")
    doc = doc.replace('<span class="m">Beispieldaten</span>', "")

    # 01 Stammdaten — the five fixed rows, real values (blank when absent)
    lang_names = {"de": "Deutsch (de)", "en": "English (en)", "es": "Español (es)"}
    doc = doc.replace("<td>Elena Mart&iacute;n</td>", f"<td>{_e(info.get('name', '—'))}</td>")
    doc = doc.replace("<td>elena.martin@example.com</td>", f"<td>{_e(info.get('email', '—'))}</td>")
    doc = doc.replace("<td>Deutsch (de)</td>",
                      f"<td>{_e(lang_names.get(info.get('language', ''), info.get('language', '—')))}</td>")
    doc = doc.replace("<td>elena.martin</td>", f"<td>{_e(info.get('login_id', '—'))}</td>")
    doc = doc.replace("<td>2026-08-14</td>", f"<td>{_e((info.get('created', '') or '—')[:10])}</td>")

    # 02 Einwilligungen — the tick reflects the record, never the sample
    consent = (rec.get("consent") or {}) if isinstance(rec.get("consent"), dict) else {}
    for key in ("coaching_not_medical", "gdpr_health_data"):
        given = bool(consent.get(key))
        pat = re.compile(
            r'(<div class="okrow"><span class="tick">)[^<]*(</span><span>(?:(?!</div>).)*?)'
            r'(Einwilligung erteilt|keine Einwilligung hinterlegt)?\s*\(' + key + r'\)',
            re.S)
        doc = pat.sub(lambda m: m.group(1) + ("&#10003;" if given else "&mdash;") + m.group(2)
                      + ("Einwilligung erteilt" if given else "keine Einwilligung hinterlegt")
                      + f" ({key})", doc, count=1)
    ver = str(consent.get("text_version", consent.get("version", "")) or "—")
    doc = doc.replace("der Einwilligung: 1.0", f"der Einwilligung: {_e(ver)}")

    # 03 Buchungen — regenerate the rows between the header row and </table>
    a = doc.index(">03<")
    tbl_a = doc.index("<table", a)
    head_end = doc.index("</tr>", tbl_a) + 5
    tbl_b = doc.index("</table>", tbl_a)
    rows = "".join(
        f"<tr><td>{_e(b.get('id', ''))}</td>"
        f"<td>{_e((b.get('slot_utc', '') or '').replace('T', ' · ')[:18])} UTC</td>"
        f"<td>{_e(b.get('status', ''))}</td></tr>"
        for b in (rec.get("bookings") or [])) or \
        '<tr><td colspan="3">— keine —</td></tr>'
    doc = doc[:head_end] + rows + doc[tbl_b:]

    # 04 Aufnahmebogen — goal + real scales; the encrypted-storage note stays
    intake = rec.get("pre_intake") or {}
    goal = (intake.get("goal") or "").strip()
    if goal:
        doc = re.sub(r'(<div class="pull"[^>]*>).*?(</div>)',
                     lambda m: m.group(1) + "&bdquo;" + _e(goal) + "&ldquo;" + m.group(2),
                     doc, count=1, flags=re.S)
    else:
        doc = re.sub(r'<div class="pull"[^>]*>.*?</div>\s*', "", doc, count=1, flags=re.S)
    labels = {"energy": "Energie", "sleep": "Schlaf", "stress": "Stress",
              "digestion": "Verdauung", "mood": "Stimmung"}
    sm = re.search(r'<div class="scale[^"]*"[^>]*>.*?</span></div>', doc, re.S)
    spat = sm.group(0)
    on = re.search(r'<i class="on"[^>]*></i>', spat).group(0)
    offs = re.findall(r'<i(?! class="on")[^>]*></i>', spat)
    off = offs[0] if offs else "<i></i>"

    def srow(label, val):
        val = max(1, min(5, int(val)))
        r = spat.replace('class="scale low"', f'class="scale{" low" if val <= 2 else ""}"')
        r = re.sub(r'(class="sl"[^>]*>)[^<]*', lambda m: m.group(1) + _e(label), r, count=1)
        segs = re.search(r'(<span class="segs"[^>]*>).*?(</span>)', r, re.S)
        r = r[:segs.start()] + segs.group(1) + on * val + off * (5 - val) + segs.group(2) + r[segs.end():]
        return re.sub(r'(<b[^>]*>)[^<]*(</b>)', lambda m: m.group(1) + str(val) + m.group(2), r, count=1)

    scales = intake.get("scales") or {}
    scm = re.search(r'(<div class="scales"[^>]*>).*?(</div>)\s*(?=<p|<div class="sec")', doc, re.S)
    if scm:
        inner = "".join(srow(labels.get(k, k), v) for k, v in scales.items())
        doc = doc[:scm.start()] + scm.group(1) + inner + "</div>" + doc[scm.end():]

    # 05 Bericht — the record's stage, in words
    stage = rec.get("stage", "")
    status = {"sent": "freigegeben &amp; zugestellt", "done": "abgeschlossen",
              "approved": "freigegeben", "draft": "Entwurf"}.get(stage, stage or "—")
    a = doc.index(">05<")
    doc = doc[:a] + re.sub(">freigegeben<", f">{status}<", doc[a:], count=1)

    # 06 Aktivität — the real event trail
    a = doc.index(">06<")
    tbl_a = doc.index("<table", a)
    head_end = doc.index("</tr>", tbl_a) + 5
    tbl_b = doc.index("</table>", tbl_a)
    rows = "".join(
        f"<tr><td>{_e((ev.get('at', '') or '').replace('T', ' · ')[:18])}</td>"
        f"<td>{_e(ev.get('event', ev.get('kind', '')))}</td></tr>"
        for ev in (rec.get("events") or [])[-40:]) or \
        '<tr><td colspan="2">— keine —</td></tr>'
    doc = doc[:head_end] + rows + doc[tbl_b:]

    # raw JSON — Art. 15 wants completeness; the styled sections want reading
    payload = json.dumps({"client_id": cid, "exported": exported,
                          "stammdaten": info, "record": rec},
                         ensure_ascii=False, indent=2, default=str)
    # the sample JSON lives in whatever element carries "client_id" — replace
    # from the tag boundary before its opening brace to the element's close
    j = doc.index('"client_id"')
    start = doc.rindex(">", 0, doc.rindex("{", 0, j) + 1) + 1
    end = doc.index("</", j)
    doc = doc[:start] + _e(payload) + doc[end:]

    for probe in ("Elena", "Mart&iacute;n", "elena.martin", "BK-MUSTER"):
        if probe in doc:
            raise AssertionError(f"gdpr view: sample data survived ({probe})")
    return doc
