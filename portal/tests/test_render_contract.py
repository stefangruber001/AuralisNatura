#!/usr/bin/env python3
"""R1: the redesigned report keeps its contracts and drops its crutches."""
from __future__ import annotations
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import _sandbox  # noqa: F401

from lib import render  # noqa: E402

FAILS: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    print(f"  {'ok  ' if ok else 'FAIL'} {label}" + (f"\n         {detail}" if detail and not ok else ""))
    if not ok:
        FAILS.append(label)


TITLES = {
    "de": ["Dein Ausgangspunkt", "Was wir sehen", "Die Wissenschaft, einfach",
           "Dein Plan", "Wann zur Ärztin", "Deine nächsten Schritte"],
    "en": ["Your starting point", "What we're seeing", "The science, simply",
           "Your plan", "When to see a doctor", "Your next steps"],
    "es": ["Tu punto de partida", "Lo que vemos", "La ciencia, en simple",
           "Tu plan", "Cuándo ir al médico", "Tus próximos pasos"],
}
KEYS = ["starting_point", "what_were_seeing", "the_science_simply",
        "your_plan", "when_to_see_a_doctor", "next_steps"]


def sections(lang):
    return [{"key": k, "title": t, "body": f"Absatz eins zu {t}.\nAbsatz zwei.",
             "science": "Eine Studienlage, einfach erklärt.",
             "actions": ["Schritt eins", "Schritt zwei"]}
            for k, t in zip(KEYS, TITLES[lang])]


REPORT = {"priorities": [{"title": f"Prio {i}", "why": "Weil.", "first_step": "Klein anfangen."}
                         for i in (1, 2, 3)],
          "weekly_plan": {k: "Fokus" for k in ("mon", "tue", "wed", "thu", "fri", "sat", "sun")},
          "habits": ["Licht am Morgen", "Protein früh", "Bildschirm dimmen"]}
CHARTS = {"energy": 2, "sleep": 3, "stress": 4, "digestion": 3}


def run() -> int:
    print("· module contracts survive (preflight reaches into these)")
    check("_chrome() exists", callable(render._chrome))
    check("_CHROME_CANDIDATES exists", isinstance(render._CHROME_CANDIDATES, list))
    check("to_pdf exists", callable(render.to_pdf))

    for lang in ("de", "en", "es"):
        doc = render.build_html("Elena Martin", sections(lang), charts=CHARTS,
                                language=lang, report=REPORT,
                                profile={"symptoms": ["fatigue", "sleep"]})
        print(f"\n· {lang}")
        import html as _h
        check("all six section titles verbatim (escaped form)",
              all(_h.escape(t) in doc for t in TITLES[lang]),
              str([t for t in TITLES[lang] if _h.escape(t) not in doc]))
        check("no Google-Fonts CDN link (the offline-PDF defect)",
              "fonts.googleapis" not in doc and "fonts.gstatic" not in doc)
        check("brand fonts embedded", doc.count("data:font/woff2") >= 3)
        check("no external URL at all",
              not re.findall(r'(?:src|href)="https?:', doc))
        nums = [int(m) for m in re.findall(r"(?:Seite|Page|Página) (\d{2})", doc)]
        check("footer page numbers consecutive from 2 (cover carries none)",
              nums == list(range(2, len(nums) + 2)), str(nums[:6]))
        check("TOC present with dotted leaders",
              ('class="toc"' in doc) and ("trow" in doc))
        toc_first = re.search(r'class="trow chp">.*?class="tp">(\d{2})', doc, re.S)
        check("TOC chapter 1 page number matches the real page",
              toc_first and f'{_page_of(doc, TITLES[lang][0]):02d}' == toc_first.group(1),
              toc_first.group(1) if toc_first else "no toc row")
        check("QR embedded on the closing page", 'class="qrp"' in doc)
        check("watermark bleeds on cover", 'class="wm"' in doc)
        check("print-color-adjust set", "print-color-adjust:exact" in doc)
        check("radar carries status markers + per-axis values",
              doc.count('transform="rotate(45') >= 3 and "<tspan" in doc)
        check("safety chapter renders as the medical box", 'class="medbox"' in doc)

    print("\n· to_pdf html-fallback contract")
    import os
    real = render._CHROME_CANDIDATES[:]
    env = os.environ.pop("AURALIS_CHROME", None)
    try:
        render._CHROME_CANDIDATES.clear()
        out = render.to_pdf("<body>x</body>", ROOT / "output_docs" / "contract" / "x.pdf")
        check("no chromium → .html beside the target", out.suffix == ".html" and out.exists())
    finally:
        render._CHROME_CANDIDATES.extend(real)
        if env:
            os.environ["AURALIS_CHROME"] = env

    print("\n" + ("RENDER CONTRACT ALL PASSED ✓" if not FAILS else f"{len(FAILS)} FAILED: {FAILS}"))
    return 0 if not FAILS else 1


def _page_of(doc: str, needle: str) -> int:
    """1-based index of the .page whose CHAPTER OPENER carries needle — the
    TOC also names every chapter, so a plain contains-search finds page 3.
    Openers carry the chapter number rail (chnum) AND the title (continuation
    pages carry the rail but no title; the TOC has titles but no rail)."""
    import html as _h
    pages = doc.split('<section class="page')
    for i, p in enumerate(pages[1:], start=1):
        if 'class="chnum"' in p and f'class="ph">{_h.escape(needle)}<' in p:
            return i
    return -1


if __name__ == "__main__":
    sys.exit(run())
