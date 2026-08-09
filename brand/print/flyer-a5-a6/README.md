# Handoff: Auralis Natura print flyer (A5 + A6, EN/DE/ES)

## Overview

A premium double-sided flyer for **Auralis Natura**, a holistic health coaching practice.
The flyers are placed in high-end hairdressers, hotel receptions and similar venues; their
single job is to move a reader from paper to `auralisnatura.com` and into a free intro call.

Two trim sizes, three languages, front and back each — **12 artboards in total**:

| Format | Trim | Bleed box (artboard) | Page box | Languages |
|---|---|---|---|---|
| A6 (narrowed) | 95 × 148 mm | 101 × 154 mm | 111 × 164 mm | EN, DE, ES |
| A5 (narrowed) | 138 × 210 mm | 144 × 216 mm | 154 × 226 mm | EN, DE, ES |

Both are 10 mm narrower than the DIN standard at unchanged height — a deliberate
proportion change (A6 → 1 : 1.56, A5 → 1 : 1.52, both nearer the golden ratio than DIN's
1 : 1.41). **This is a design decision, not a mistake — do not "correct" it to 105 × 148 /
148 × 210.**

## About the design files

The files in `design/` are **design references created in HTML** — print-accurate
prototypes showing the intended output, not production code to copy directly. The task is
to **recreate these designs in the target environment**, using its established patterns and
libraries. If no environment exists yet, choose the framework that fits the project.

That said, this deliverable is unusual in one respect: **its output medium is a PDF for a
commercial printer, not a screen.** If the target codebase's job is to *generate* these
flyers (e.g. a marketing site that renders localised print PDFs on demand), the HTML here is
close to directly reusable — the geometry has been measured and corrected against a real
print run, and re-deriving it from scratch will reintroduce bugs that took several rounds to
find. Section **"Print geometry — read before changing anything"** explains which numbers are
load-bearing.

## Fidelity

**High-fidelity.** Every colour, size, weight and offset below is final and measured. All
dimensions are in **millimetres** and all type sizes in **points** — these are physical print
units, not CSS pixels. Reproduce them exactly; a value that looks "roughly 6 mm" is 6 mm.

---

## Print geometry — read before changing anything

Each page is a three-layer stack:

1. **Page box** (`<section class="page">`) — the sheet the browser prints. Trim + 3 mm bleed
   on every side + 5 mm of margin for the crop marks.
2. **Artboard** — a `position:absolute` div at `left:5mm; top:5mm`, sized to the bleed box
   (trim + 3 mm each side). All artwork lives here; `overflow:hidden` clips the bleed.
3. **Crop marks** — an SVG of eight 0.15 mm hairlines in `#aaa39a`, drawn 1 mm outside the
   trim edge, 4 mm long. Plus a caption strip at `bottom:1.2mm` naming language, side, trim
   and bleed.

### The registration bug — root cause, and why it is fixed this way

An early version printed with the **back side ~20 mm higher on the sheet than the front**.
The cause was not a margin: the two sides had *different content heights*, so the browser's
print pagination placed each on its page independently. The fix, and the invariant to
preserve:

> **Every page is the same fixed page box, and the artboard is absolutely positioned at a
> fixed offset inside it. No page's geometry depends on its content.**

Content flows *inside* the artboard using `flex:1; min-height:0` and `margin-top:auto`, so
overflow is impossible to hide — it shows up as clipped content rather than as a page that
silently grows. The CI check in `ci/` asserts this on every build.

If you re-implement in another engine (Puppeteer, WeasyPrint, Prince, React-PDF), keep the
invariant: **fixed page box, absolutely positioned artboard, content clipped not reflowed.**

### The combined document

`Auralis Natura Flyers A5 - A6.dc.html` puts all 12 pages on the **single 154 × 226 mm page
box** so it prints as one job. The A6 pages keep their true 95 × 148 mm trim, centred at
`left:26.5mm; top:36mm` with their own crop marks. **Both formats stay life-size** — the A6
is not scaled up. Never let a print dialog apply "fit to page"; it must print at 100 %.

---

## Screens / Views

Six artboards per format. The A6 numbers are given in full (it is the master); the A5 is
the same structure at a larger scale, with its differing values noted.

### 1. Front (EN / DE / ES)

Centred column, `display:flex; flex-direction:column; align-items:center; text-align:center`
on `#F5EEE0`. Vertical rhythm is built from explicit `height:*mm; flex:none` spacer divs, not
margins — deliberate, so the stack reads top-to-bottom in source order and spacing survives
element reordering.

| Element | A6 | A5 |
|---|---|---|
| Top spacer | 10 mm | 19 mm |
| Botanical seal (`assets/seal.png`) | 16 × 16 mm | 24 × 24 mm |
| Spacer | 4.16 mm | 6.24 mm |
| Wordmark "Auralis Natura" | Fraunces 11.5 pt / 400 / .16em / lh 1 | Fraunces 15.5 pt |
| Spacer | 2 mm | 2 mm |
| Descriptor ("Holistic Health") | 6 pt / 500 / .38em / uppercase / `#75685A` | 7 pt |
| Spacer | 6 mm | 6 mm |
| Gold rule | 14 × 0.25 mm `#AD7A32` | 20 × 0.25 mm |
| Spacer | 7 mm | 7 mm |
| Headline `<h1>` | Fraunces 20.5 pt (DE 17 pt) / 330 / lh 1.15 / -.022em / width 79 mm | 29 pt (DE 24 pt) / lh 1.14 / width 112 mm |
| Spacer | 6 mm | 6 mm |
| Lede `<p>` | 8.6 pt / lh 1.6 / `#5C4A3A` / width 80 mm / `text-wrap:balance` | 11 pt / width 112 mm |
| Spacer | 5 mm | 5 mm |
| Meta (2 lines) | 6 pt / 600 / .22em / uppercase / `#927B4A` / lh 2 | 7 pt / .24em |
| **Dark band** | `margin-top:auto`, 46 mm tall | 58 mm tall |

**Headline** is two lines: line 1 plain `#281F16`, line 2 an `<em>` in italic, weight 360,
`#8A4A2A`. The German headline drops to 17 pt (A6) / 24 pt (A5) because the compound words
are longer — **size, never hyphenation**; `hyphens:none` is set globally and is a brand rule.

**Dark band** (`#4A3020`, full artboard width, `padding:0 10mm 3mm` A6 / `0 14mm 3mm` A5,
`align-items:center`, gap 5.5 mm). Left column:

- Kicker — 6 pt / 600 / .17em / uppercase / `#E0B45E` / `white-space:nowrap`
- 3 mm spacer
- Value line — Fraunces 11 pt / 350 / lh 1.24 / `#FBF6EB`, second clause an `<em>` in `#EDCB80`
- 3.2 mm spacer
- Website row — 7.2 pt / 600 / `#E0B45E`, globe icon + `www.auralisnatura.com`

Right column: QR, 18 mm A6 / 23 mm A5, on a `#FBF6EB` plate. **No caption under it** — removed
deliberately; a QR on a flyer needs no instruction.

> The front carries the website only. Email and phone are back-side only — the front's job is
> one action, not a contact directory.

### 2. Back (EN / DE / ES)

| Element | A6 | A5 |
|---|---|---|
| Portrait band | 42 mm tall, `object-fit:cover`, `object-position:center 6%` | 70 mm |
| Band bottom border | 0.25 mm `#AD7A32` | same |
| Content column padding | 6 mm 10 mm 5 mm | 9 mm 14 mm 6 mm |
| Founder name | 7.6 pt / 700 / .13em / uppercase / lh 1 | 9.6 pt |
| Role | 6.2 pt / 600 / .19em / uppercase / `#927B4A` | 7.2 pt |
| Credentials (4 lines, `<br>`) | 6.9 pt / lh 1.46 / `#5C4A3A` | 8.6 pt / lh 1.7 |
| Divider | 0.25 mm `rgba(61,39,25,.28)` | same |
| "The programmes" | 6 pt / 600 / .22em / uppercase / `#A8492A` | 7 pt |
| Package name | Fraunces 10 pt / 430 / `#281F16` | 13 pt |
| Package descriptor | 6.2 pt / .07em / uppercase / `#75685A`, 2.5 mm left of name | 7.2 pt |
| Package price | Fraunces 8.2 pt / 400 / `#5C4A3A` | 10.4 pt |
| Row separators | 0.2 mm `rgba(61,39,25,.20)`, 2 mm above and below | same |
| Dark band | 29 mm tall | 39 mm |

**Package rows** — four, `display:flex; align-items:baseline; gap:4mm`, name and descriptor
in a `flex:1` group, price `flex:none` right-aligned:

| | EN | DE | ES | Price |
|---|---|---|---|---|
| 1 | Clarity — Where you stand & health analysis | Klarheit — Standortbestimmung & Analyse | Claridad — Punto de partida y análisis | €199 |
| 2 | Change — From analysis to action · 4 weeks | Wandel — Von der Analyse ins Handeln · 4 Wochen | Cambio — Del análisis a la acción · 4 semanas | €399 |
| 3 | Balance — In-depth guidance · 12 weeks | Balance — Tiefgehende Begleitung · 12 Wochen | Balance — Acompañamiento profundo · 12 semanas | €899 |
| 4 | Connection — Group workshops for teams | Verbindung — Gruppen-Workshops für Teams | Conexión — Talleres para equipos | On request / Auf Anfrage / A consultar |

German and Spanish set the price as `199 €` (numeral, space, symbol) — correct for both
locales. **Do not normalise to `€199` globally.**

**Back dark band** — closing CTA (Fraunces 10.5 pt A6 / 13.5 pt A5, `#FBF6EB`), then a
1.5 mm-gap column of three contact rows at 7.2 pt / 600 / `#E0B45E`, each an inline SVG icon
(1em square, `stroke-width:2`, `stroke:#E0B45E`) plus text:

- globe → `www.auralisnatura.com`
- envelope → `team@auralisnatura.com`
- handset → `+34 614 489 656`

QR at 17 mm A6 / 20 mm A5.

---

## Interactions & behavior

Print artefact — no runtime interaction. Two behaviours matter anyway:

**QR codes.** All six QRs in each file encode the same payload: `www.auralisnatura.com`.
Rendered as inline SVG rectangles (not an image) so they print at press resolution.
`shape-rendering:crispEdges` is required — without it the module edges antialias and cheap
scanners fail. Quiet zone is **4 modules**, set via `viewBox="-4 -4 37 37"` on a 29-module
symbol; this is the ISO minimum and QR scanning degrades sharply below it.

**Known limitation, worth fixing in code:** the back QR should ideally land on the booking
section rather than the homepage, but the live site's "Book your free intro call" buttons
link to a bare `#` and are script-driven, so there is no addressable anchor. **Add
`id="booking"` to that section** (or better, ship per-placement landing URLs like
`/hotel`, `/salon` for attribution) and regenerate the QRs.

## State management

None. The pages are static. Language is a build-time concern, not runtime state — each
language is its own pair of artboards, not a switchable view.

---

## Design tokens

From the bound **Auralis Natura** design system. Where the system exposes a token name, it is
given; the flyer uses literal values because print output cannot depend on a runtime
stylesheet.

### Colour

| Role | Hex | DS token |
|---|---|---|
| Paper (artboard) | `#F5EEE0` | `--paper` |
| Cream (on dark) | `#FBF6EB` | `--cream` |
| Ink (headings) | `#281F16` | `--ink` |
| Body text | `#5C4A3A` | `--ink-soft` |
| Muted / descriptor | `#75685A` | `--ink-faint` |
| Meta gold | `#927B4A` | — |
| Gold rule / hairline | `#AD7A32` | `--gold` |
| Gold bright (on dark) | `#E0B45E` | `--gold-bright` |
| Amber emphasis (on dark) | `#EDCB80` | — |
| Clay emphasis | `#8A4A2A` | `--clay` |
| Clay bright | `#A8492A` | `--clay-deep` |
| Dark band | `#4A3020` | `--forest-deep` equivalent |
| QR ink | `#2A1B0E` | — |
| Crop marks | `#aaa39a` | — |
| Page caption | `#b5aea4` | — |

Rules: **square corners everywhere** (`--r` is `0px`; adding `border-radius` breaks the
system's most defining decision). Clay is the action colour and never a large field. On dark
bands, body is cream and emphasis is gold-bright.

### Typography

- **Display** — Fraunces, weights 300–600 + italic. Self-hosted woff2 in `fonts/`.
- **Body** — Hanken Grotesk, weights 300–700. Self-hosted woff2 in `fonts/`.
- Fallbacks: `Georgia, serif` and `system-ui, -apple-system, sans-serif`.
- `hyphens: none` globally — a brand rule, not a preference.
- **6 pt is the hard minimum size.** Nothing on either format goes below it.

### Spacing

No abstract scale. Spacing is explicit millimetres via spacer divs, chosen per format.
Recurring values: 2, 3, 3.2, 5, 6, 7, 10 mm (A6) and 5, 6, 7, 9, 14, 19 mm (A5).

### Structure

Hairlines only: 0.15 mm (crop marks), 0.2 mm (row separators), 0.25 mm (rules, band borders).
No shadows anywhere in the print pieces.

---

## Assets

| File | Size | Status |
|---|---|---|
| `assets/seal.png` | 300 × 300 px | **Under spec.** 254 dpi at A5's 24 mm. |
| `assets/seal-hi.png` | 1600 × 1600 px | Resampled from the above. Prevents blockiness; cannot add detail. |
| `assets/emblem-gold.png` | — | Alternate gold mark, not currently placed. |
| Portrait | 1122 × 1402 px | **Loaded from `https://www.auralisnatura.com/images/desiree-portrait.jpg`.** |

**Two asset problems to close in the target implementation:**

1. **The portrait is a remote URL.** If the file is opened without network access, six of the
   twelve pages print with an empty band. It must be vendored locally.
2. **Both rasters are under 300 dpi at placed size** (portrait ≈ 282 dpi, seal 254 dpi).
   Source the seal as SVG if it exists — it is line art and would then be resolution-free.

The CI checks in `ci/` gate both of these, so they cannot silently regress.

---

## Files

```
design/
  Auralis Natura A6 Print.dc.html       6 pages — EN/DE/ES × front/back, 95 × 148 mm trim
  Auralis Natura A5 Print.dc.html       6 pages — EN/DE/ES × front/back, 138 × 210 mm trim
  Auralis Natura Flyers A5 - A6.dc.html 12 pages, one 154 × 226 mm page box, print-in-one-job
  doc-page.js                           paged-document web component (owns print geometry)
  support.js                            runtime for the .dc.html format
  assets/                               seal.png, seal-hi.png, emblem-gold.png
  fonts/                                Fraunces + Hanken Grotesk woff2 + fonts.css
ci/
  spec.json                             machine-readable geometry + content contract
  check-print.mjs                       the checks, as a Playwright script
  package.json
  workflows/print-checks.yml            GitHub Actions workflow
```

The `.dc.html` files open directly in a browser. `<doc-page>` owns all print geometry —
never add `@page` rules, page-break CSS or fake sheet backgrounds alongside it.

---

## CI — what to automate and why

Print bugs are expensive: they are discovered on paper, after money is spent. Every check
below exists because the corresponding bug actually happened during this design, or would
have been caught for free. Run them on every PR touching the flyer source.

`ci/check-print.mjs` implements checks 1–7 with Playwright and exits non-zero on failure.

**1. Zero-overflow gate.** For every artboard, `scrollHeight === clientHeight`. Catches
content silently clipped by a copy change — the single most common failure when translating,
because German runs 15–30 % longer than English.

**2. Registration gate.** Front and back artboards must sit at an identical offset within
their page box, and every page box must be identical in size. *This is the check that would
have caught the ~20 mm front/back misalignment found on the first real print run.*

**3. Trim/bleed gate.** Artboard = trim + 6 mm in both axes; crop marks 1 mm clear of trim.
Catches someone "tidying" a size and losing the bleed.

**4. Type-floor gate.** No rendered `font-size` below 6 pt on any page. A 5.4 pt descriptor
slipped through manually and had to be caught by eye.

**5. Offline-asset gate.** No `img[src]` may be an `http(s)` URL. Directly targets the
remote-portrait problem above: a print shop's machine may have no network.

**6. Resolution gate.** Every raster asset ≥ 300 dpi at its placed size —
`naturalWidth / (placedMm / 25.4)`. Currently **failing by design** for the two known assets;
run with `--warn-dpi` until they are replaced, then make it blocking.

**7. Content parity gate.** All three languages must have the same package-row count and the
same set of prices, and every QR payload must equal the expected URL (decoded, not assumed).
Catches a price updated in one language only — an expensive, entirely silent bug.

**8. Visual regression (recommended, not implemented).** Snapshot each page to PNG and diff
against a committed baseline with a tight threshold. Font-rendering changes between CI image
versions will cause noise; pin the container image.

**9. PDF artifact.** Have CI print the combined document to PDF and upload it as a build
artifact, so every commit has a downloadable, press-ready proof. Print at scale 1,
`preferCSSPageSize: true`, background graphics on.

### Wiring it up

```bash
cd ci && npm install && npx playwright install --with-deps chromium
node check-print.mjs ../design            # blocking
node check-print.mjs ../design --warn-dpi # while the two known assets are unresolved
```

`workflows/print-checks.yml` is ready to drop into `.github/workflows/`.

**A note on scope:** if the target codebase generates these flyers, port these checks
alongside the templates. If it only *hosts* the resulting PDFs, keep checks 5, 6 and 7 —
asset resolution and price parity remain worth gating, and check 7's QR decode is the only
thing standing between a typo and 5,000 printed flyers pointing at a dead URL.
