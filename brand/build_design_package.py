#!/usr/bin/env python3
"""Assemble the Auralis Natura Design Package — one ZIP holding everything a
designer, a web developer, or Claude Design needs to build on this brand.

Layout mirrors chapter 13 of the handbook, so the document and the folder agree:

  01-handbook/        the Design Handbook (PDF + self-contained HTML)
  02-design-system/   the built component library, in the format Claude Design reads
  03-brand-masters/   the best copies of the seal + the website QR
  04-print/           approved business card + A5/A6 trilingual flyer artwork
  05-fonts/           self-hosted Fraunces + Hanken Grotesk woff2 with @font-face CSS
  06-photography/     the real photography library
  07-website/         the live homepage, as shipped

  python3 brand/build_design_package.py
"""
from __future__ import annotations

import pathlib
import shutil
import zipfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
STAGE = ROOT / "brand" / ".package-stage"
OUT = ROOT / "brand" / "Auralis-Natura-Design-Package.zip"

# ds-bundle working files that must not ship: local build state and the QA
# screenshot tree (~30 MB of contact sheets nobody downstream needs).
BUNDLE_SKIP_DIRS = {"_screenshots"}


def copy_tree(src: pathlib.Path, dst: pathlib.Path, *, skip_hidden: bool = True,
              skip_dirs: set[str] | None = None) -> int:
    n = 0
    skip_dirs = skip_dirs or set()
    for p in sorted(src.rglob("*")):
        rel = p.relative_to(src)
        if any(part in skip_dirs for part in rel.parts):
            continue
        if skip_hidden and any(part.startswith(".") for part in rel.parts):
            continue
        if p.is_dir():
            continue
        target = dst / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, target)
        n += 1
    return n


README = """# Auralis Natura — Design Package

Everything needed to design or build on the Auralis Natura brand, in one place.
**Start with `01-handbook/`** — it explains every rule the rest of this package
embodies.

| Folder | What it is |
|---|---|
| `01-handbook/` | **The Design Handbook** (20 pages, PDF + self-contained HTML). The reference: marks, colour, type, layout, components, page composition, copy, print production, photography, guardrails. |
| `02-design-system/` | The **built component library** — 22 compiled React components, typed props, per-component usage docs, tokens, self-hosted fonts, and a rendered preview card for each. This is the format **Claude Design** consumes directly. |
| `03-brand-masters/` | The seal at its best available quality: full colour 1600 px, gold-on-dark, single-colour brown, the 10 %-opacity watermark variant, and the website QR code. |
| `04-print/` | Production artwork: the approved **business card** (design 5B "Reine Fläche") and the **A5 + A6 trilingual flyer** (12 artboards), with their handoff notes and the CI print check. |
| `05-fonts/` | **Fraunces** and **Hanken Grotesk** as self-hosted woff2 (latin + latin-ext) with the `@font-face` CSS. Both are open-source. |
| `06-photography/` | The real photography library — portraits, consultation, still life, certificates. |
| `07-website/` | The live homepage as a single HTML file — the canonical shipped expression of the whole system. |

## Loading the design system into Claude Design

Upload the **contents** of `02-design-system/` at the project root (not the folder
itself). The app reads:

- `_ds_bundle.js` — every component on `window.AuralisNatura`
- `styles.css` — the complete style closure, including the self-hosted fonts
- `components/<group>/<Name>/` — `.d.ts` props contract, `.prompt.md` usage
  reference, `.html` preview card, `.jsx` re-export
- `tokens/`, `fonts/`, `_vendor/`, `guidelines/`, `README.md`

## The five rules that matter most

1. **Corners are square.** `--r` is `0px`. Never add a `border-radius`.
2. **Clay `#A8492A` is the accent, never a field** — one primary clay button per view.
3. **Gold is structural, not shiny** — hairlines and small caps, flat colour.
4. **Never hyphenate.** German compounds are handled by reducing type size.
5. **Restraint is the premium signal** — the printed card runs at ~4 % ink coverage.

## Two things that are legal, not stylistic

- This is **holistic health coaching and education — never medical care**. In Spain
  *dietista-nutricionista* is a protected profession (Ley 44/2003), so never
  "Nutritionist" / "Ernährungsberaterin". "Dr." means **Dr. rer. nat.**, a chemistry
  doctorate, and never implies a physician.
- **Testimonials must be real.** Never invent, embellish or composite a review —
  in production, in a mockup, or in a component preview.

Chapter 12 of the handbook carries the full set.

---
Dr. rer. nat. Desiree Gruber · Holistic Health · Barcelona · auralisnatura.com
"""


def main() -> None:
    if STAGE.exists():
        shutil.rmtree(STAGE)
    STAGE.mkdir(parents=True)
    counts: list[tuple[str, int]] = []

    # 01 — the handbook
    d = STAGE / "01-handbook"
    d.mkdir()
    hb = ROOT / "brand" / "handbook"
    for f in ("Auralis-Natura-Design-Handbook.pdf", "Auralis-Natura-Design-Handbook.html"):
        src = hb / f
        if not src.exists():
            raise SystemExit(f"missing {src} — run brand/build_design_handbook.py first")
        shutil.copy2(src, d / f)
    counts.append(("01-handbook", 2))

    # 02 — the built design system, in Claude Design's own format
    bundle = ROOT / "ds-bundle"
    if not bundle.exists():
        raise SystemExit("missing ds-bundle/ — run the design-sync converter first")
    counts.append(("02-design-system",
                   copy_tree(bundle, STAGE / "02-design-system",
                             skip_dirs=BUNDLE_SKIP_DIRS)))

    # 03 — brand masters
    counts.append(("03-brand-masters",
                   copy_tree(ROOT / "brand" / "masters", STAGE / "03-brand-masters")))

    # 04 — print artwork
    counts.append(("04-print",
                   copy_tree(ROOT / "brand" / "print", STAGE / "04-print",
                             skip_dirs={"node_modules"})))

    # 05 — fonts
    d = STAGE / "05-fonts"
    counts.append(("05-fonts",
                   copy_tree(ROOT / "design-system" / "assets", d)))

    # 06 — photography
    counts.append(("06-photography",
                   copy_tree(ROOT / "images", STAGE / "06-photography")))

    # 07 — the live website
    d = STAGE / "07-website"
    d.mkdir()
    shutil.copy2(ROOT / "index.html", d / "index.html")
    counts.append(("07-website", 1))

    (STAGE / "README.md").write_text(README, encoding="utf-8")

    if OUT.exists():
        OUT.unlink()
    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for p in sorted(STAGE.rglob("*")):
            if p.is_file():
                z.write(p, p.relative_to(STAGE))

    total = sum(n for _, n in counts) + 1
    for name, n in counts:
        print(f"  {name:<20} {n:>4} file(s)")
    print(f"\n✓ {OUT.relative_to(ROOT)}  "
          f"({OUT.stat().st_size/1024/1024:.1f} MB, {total} files)")
    shutil.rmtree(STAGE)


if __name__ == "__main__":
    main()
