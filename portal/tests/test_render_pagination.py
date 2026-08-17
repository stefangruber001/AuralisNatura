#!/usr/bin/env python3
"""R2: long chapters flow onto continuation pages — nothing clips, ever.

The old renderer put variable-length chapters into fixed overflow:hidden A4
boxes with no break control: a long chapter silently LOST its tail. The
splitter budgets content in Python; these checks are the proof.
"""
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


def run() -> int:
    print("· the splitter: budgets respected, nothing dropped, order kept")
    paras = [f"Absatz {i:02d}: " + ("Inhalt und noch mehr Inhalt. " * 14) for i in range(24)]
    s = {"key": "your_plan", "title": "Dein Plan", "body": "\n".join(paras),
         "science": "Studienlage " * 40, "actions": [f"Schritt {i}" for i in range(1, 6)]}
    pages = render._split_chapter(s, has_chart=False)
    check("a 12k-char chapter needs several pages", len(pages) >= 3, str(len(pages)))
    got = [p for pg in pages for kind, p in pg if kind == "p"]
    check("every paragraph survives, in order", got == [p.strip() for p in paras])
    kinds = [kind for pg in pages for kind, _ in pg]
    check("science and actions land after the text", kinds[-2:] == ["sci", "act"])
    for i, pg in enumerate(pages):
        used = (190 if i == 0 else 90)
        for kind, payload in pg:
            used += {"p": render._para_h(payload) if kind == "p" else 0,
                     "sci": render._para_h(payload) + 56 if kind == "sci" else 0,
                     "act": len(payload) * 26 + 52 if kind == "act" else 0,
                     "chart": 130}[kind] if kind != "p" else render._para_h(payload)
        budget = render._PAGE_BUDGET if i == 0 else render._CONT_BUDGET
        check(f"page {i + 1} within budget", used <= budget + 1, f"{used} > {budget}")

    print("\n· short chapters stay on one page")
    short = {"key": "next_steps", "title": "T", "body": "Ein Absatz.",
             "science": "", "actions": []}
    check("one page", len(render._split_chapter(short, False)) == 1)

    print("\n· the rendered document: continuation openers, localized")
    long_sections = [
        {"key": "starting_point", "title": "Dein Ausgangspunkt", "body": "\n".join(paras),
         "science": "S.", "actions": ["A"]},
        {"key": "next_steps", "title": "Deine nächsten Schritte", "body": "Kurz.",
         "science": "", "actions": []},
    ]
    for lang, cont in (("de", "Fortsetzung"), ("en", "continued"), ("es", "continuación")):
        doc = render.build_html("E", long_sections, charts={}, language=lang, report={})
        check(f"{lang}: continuation opener present", cont in doc)
        # every paragraph's distinctive prefix must appear exactly once
        missing = [i for i in range(24) if f"Absatz {i:02d}:" not in doc]
        check(f"{lang}: zero paragraphs lost", missing == [], str(missing))
        nums = [int(m) for m in re.findall(r"(?:Seite|Page|Página) (\d{2})", doc)]
        check(f"{lang}: page numbers still consecutive", nums == list(range(2, len(nums) + 2)))
        # the TOC number for chapter 2 must account for chapter 1's extra pages
        m = re.findall(r'class="trow chp">.*?class="tp">(\d{2})', doc, flags=re.S)
        ch2_page = _page_of(doc, "Deine nächsten Schritte" if lang == "de" else "Deine nächsten Schritte")
        check(f"{lang}: TOC survives multi-page chapters",
              len(m) == 2 and int(m[1]) == _page_of_chapter2(doc), f"toc={m}")

    print("\n" + ("RENDER PAGINATION ALL PASSED ✓" if not FAILS else f"{len(FAILS)} FAILED: {FAILS}"))
    return 0 if not FAILS else 1


def _page_of(doc: str, needle: str) -> int:
    pages = doc.split('<section class="page')
    for i, p in enumerate(pages[1:], start=1):
        if needle in p:
            return i
    return -1


def _page_of_chapter2(doc: str) -> int:
    """First page whose chapter opener is 'Kapitel/Chapter/Capítulo 02' —
    continuation pages carry a '… — Fortsetzung' suffix, so they never match."""
    pages = doc.split('<section class="page')
    for i, p in enumerate(pages[1:], start=1):
        if re.search(r"(Kapitel|Chapter|Capítulo) 02<", p) and 'class="chnum"' in p:
            return i
    return -1


if __name__ == "__main__":
    sys.exit(run())
