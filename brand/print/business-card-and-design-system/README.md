# Handoff: Auralis Natura — Homepage

## Overview

Build the marketing homepage for **Auralis Natura**, the holistic health coaching practice of **Dr. Desiree Gruber** (Barcelona). The brand positioning is "Modern Materia Medica": PhD-level scientific rigour meeting botanical warmth — premium, calm, editorial.

This handoff carries two things:

1. **The bound design system** (`design_system/`) — the real `@auralis/design-system` library, 22 components, tokens, and self-hosted fonts. This is the source of truth for the homepage.
2. **The approved brand reference** (`brand_reference/`) — the finished business card, design **5B "Reine Fläche"**. It is the most refined expression of this brand that exists, and it settles several decisions the homepage should honour (see *Brand decisions the card already settled*).

> ⚠️ **Read this before you start.** No homepage screens were designed in the conversation that produced this bundle — only the business card. This README therefore specifies the homepage **from the design system's own composition guide plus the brand decisions the card locked in**. It is a build brief, not a pixel spec of approved mockups. Where it says "compose with `X`", that is binding. Where it describes copy or imagery, treat it as a starting point to be reviewed with Desiree.

## About the design files

The files in `brand_reference/` are **design references authored in HTML** — they are the production artwork for a printed card, not application code and not a component library. Do not port their HTML/CSS into the website. Read them to understand the brand's visual character, then build the homepage with the design system's React components.

The files in `design_system/` **are** real code: the published library, bundled for the browser. Use them.

## Fidelity

**Mixed — read carefully.**

- **The design system is high fidelity and binding.** Every colour, type ramp, spacing value and component is final. Do not invent components, do not restyle raw HTML to imitate them, do not introduce colours outside the tokens.
- **The business card is high fidelity and final.** It is shipped artwork.
- **The homepage composition below is a specification, not an approved mockup.** Section order, component choice and the rules are binding because they come from the design system's own guidance. Copy, photography and exact section content need a design and content review before launch.

---

## Setup

React must be on the page first. Then, once at the app root:

```jsx
import '@auralis/design-system/styles.css';
import { Section, Display, Em, Text, Button } from '@auralis/design-system';
```

If the target codebase cannot consume the npm package, the bundled browser build in this folder is equivalent:

```html
<link rel="stylesheet" href="design_system/_ds/auralis-natura-…/styles.css">
<script src="design_system/_ds/auralis-natura-…/_ds_bundle.js"></script>
<!-- components are then at window.AuralisNatura.* -->
```

Importing that one stylesheet is the entire type setup. **Fraunces** (display) and **Hanken Grotesk** (body) ship as self-hosted woff2 declared inside it. Nothing is fetched from a font host — keep it that way; a font-host request is a GDPR problem on this brand (see *Compliance*).

Mount the design system into its own child node, not the host app's React root, so the two trees don't collide.

---

## Screens / views

### Homepage — one page, ten sections

The order below is not a suggestion. It is the argument the components were shaped around, and skipping or reordering steps breaks the pacing rules the system encodes.

| # | Section | Components | Purpose |
|---|---|---|---|
| 1 | **Hero** | `Display` with the second sentence in `Em`; one `Text variant="lead"`; one `clay` `Button` with `arrow` + risk-removing `subLabel`; one `ghost` `Button` beside it | The turn: name the reader's goal and the shift |
| 2 | **Credential ribbon** | `CredentialRibbon` of `CredentialChip`s | Trust, immediately, before any argument is made |
| 3 | **The problem** | `Section tone="dark"` | Name what the reader is living with. First dark band, the emotional turn |
| 4 | **The method** | `Section` (light), `SectionHead` | How the work is actually done |
| 5 | **Image band** | `ImageBand` with a one-sentence `caption` | Let the page breathe |
| 6 | **Packages** | `SectionHead` then `PackageGrid` with **exactly three** `PackageCard`s | The commercial ask |
| 7 | **About** | `PhotoFrame` + `MetaList` in the narrow left column; story + `Signature` in the wide right column. Split ≈ `.82fr 1.18fr` | Who she is, and why the credential matters |
| 8 | **Testimonials** | `Section tone="dark"` + `Testimonial` | Social proof — **real reviews only** |
| 9 | **FAQ** | `SectionHead center` + `FaqList` of `FaqItem`s, strongest objection first | Remove the last barriers |
| 10 | **Closing CTA** | `CtaCard` | The final ask. One per page, always last |

**Per-page limits — enforce these:**

- One `Display`
- One `Signature`
- One `CtaCard`
- One `clay` button (the hero's primary; every other CTA on the page is `forest` or `ghost`)
- Three or four dark bands maximum
- `PackageGrid` is a fixed three columns — ship exactly three cards, cheapest first, `featured` on the middle one

**Rhythm.** Alternate density, not colour. Two dense sections in a row get an `ImageBand` or a `padding="sm"` section between them.

**Widths.** Everything lives inside `wrap`, which `Section` supplies. Don't add your own max-width container.

---

## Brand decisions the card already settled

These carried the card and should carry the site. They are not re-open questions.

1. **Square corners, everywhere.** `--r` and `--r-lg` are `0px`. Never add a `border-radius` — it is the single most defining structural decision in this system, and the card is built on it.
2. **The seal is the recurring mark.** On the card it appears twice: small and solid as a signature, and large at **10 % opacity bleeding off the edge** as a watermark. That watermark treatment is the brand's signature move — reuse it on the site for large quiet surfaces (hero background, dark bands, the `CtaCard`), never as loud decoration. Asset supplied at 1200 px.
3. **Clay (`--clay`, `#A8492A`) is the accent, never a field.** On the card it is the role line, the two flanking squares and every icon — small, precise, high-value marks. One primary `clay` button per view; large surfaces are `--paper` / `--cream` or the dark brown band.
4. **Gold is structural, not shiny.** The card rejected mirrored/gradient "chrome" gold as dated. Gold appears as hairlines, small caps and the seal — `--gold` and `--gold-bright`, flat. Never a gradient gold field on the site.
5. **Edges are hairlines; shadows are wide and soft.** The card's frame is a 0.2 mm hairline. Never tight, dark shadows.
6. **Restraint is the premium signal.** The card prints at roughly 4 % ink coverage — the paper does the work. The web equivalent is generous whitespace and few elements per viewport. Resist filling space.
7. **The name never breaks.** "Desiree" and "Gruber" always sit on one line, at every breakpoint.
8. **Never hyphenate.** `hyphens` is `none` throughout. German compounds are handled by reducing type size, not by splitting words — **check every headline at 360 px before shipping**.

---

## Interactions & behaviour

The design system ships the interactive behaviour; don't re-implement it.

- **`Button`** — variants `clay | forest | ghost`, sizes incl. `lg`, optional `arrow` and `subLabel`. The `subLabel` is where the risk is removed ("free, no obligation"). Hover/active/focus states are in the stylesheet.
- **`FaqList` / `FaqItem`** — an accordion; the components own the open/closed state.
- **`PackageCard featured`** — inverts one card in the row to the dark band. Use it on the middle card only.
- **`Label` and `SectionHead`** take `onDark` when placed on a brown band — pass it, or the contrast is wrong.
- **Transitions** use the `--ease` token. Wide, soft, unhurried. Nothing bouncy, no countdown timers, no urgency mechanics — they contradict the voice.

**Responsive.** `PackageGrid` stacks on mobile. The About split collapses to a single column. Test every headline at **360 px**.

## State management

The homepage is a static marketing page — no application state beyond:

- FAQ accordion open/closed (owned by `FaqList`)
- Any intro-call booking flow. The primary CTA points at a booking destination; if that is an embedded scheduler, it is a third-party embed and needs a consent gate before it loads (see *Compliance*).

No data fetching is required for the page itself.

---

## Design tokens

Use the tokens via `var(--*)`. Never a raw hex, never an invented class name — nothing outside the stylesheet resolves.

**Colour**
`--ink` `--ink-soft` `--ink-faint` · `--forest` `--forest-soft` `--forest-deep` `--forest-2` · `--sage` `--sage-soft` · `--clay` `--clay-deep` `--clay-soft` · `--gold` `--gold-bright` · `--paper` `--paper-2` `--paper-3` `--cream`

**Structure**
`--line` `--line-strong` `--gold-hair` `--shadow-sm` `--shadow-md` `--ease` `--maxw` `--gut` `--r` `--r-lg` `--font-display` `--font-body` `--font-mono`

**Emphasis rule.** On light sections, emphasis is `--ink` at weight 600 (`<strong>`). On dark bands, body text is cream and emphasis is `--gold-bright` (`Em`).

**Utility classes that exist and are safe to reuse:** `wrap`, `sec-pad`, `sec-pad-sm`, `u-kick`, `em`.

### Values fixed by the printed card

Supplied so the site can be checked against the card. Prefer the token when one matches.

| Use | Hex |
|---|---|
| Primary ink (name, values) | `#281F16` |
| Soft ink (brand statement) | `#3D2719` |
| Muted ink (fine print) | `#5C4A3A` |
| Clay — role line, icons, accent squares | `#A8492A` |
| Gold — brand line | `#8A6A2E` |
| Gold — secondary / fine caps | `#92783F` |
| Gold — hairline rule | `#B99A5E` |

**Type on the card**, for reference: name in Fraunces 400 at 15.6 pt with `-0.02em` tracking; brand statement in Fraunces 300 italic; everything else Hanken Grotesk 400/600 in small caps with wide tracking (0.28–0.38 em). That wide-tracked small-caps treatment is the brand's label voice — it maps to `Label` and `u-kick` on the site.

---

## Assets

| File | Size | Notes |
|---|---|---|
| `assets/seal-gold-watermark.png` | 1200 × 1200 px | The botanical seal in the champagne→amber gradient used on the card. **This is the one to use on the site.** Transparent background. Use at 10 % opacity for watermarks, full opacity as a mark. |
| `assets/seal-gold-hi.png` | 1200 × 1200 px | Paler gold seal — alternate, unused on the card |
| `assets/seal-brown-hi.png` | 1200 × 1200 px | Seal in solid `#3D2719` — for light surfaces where gold is too warm |
| `assets/qr-website.png` | 1480 × 1480 px | QR encoding `https://www.auralisnatura.com`. **Print asset — not for the website.** Included so the card set stays complete. |

The seal is derived from the design system's `Emblem` component artwork. If the site needs it live rather than as a raster, use `Emblem` from the library rather than the PNG.

**Photography is not supplied.** Sections 5 (`ImageBand`) and 7 (`PhotoFrame`) both need real photographs. Use placeholders and flag them — do not generate or substitute stock imagery on this brand.

---

## Copy

**Voice:** warm, intelligent, calm, precise — *a brilliant friend who happens to be a scientist*. Never breathless, never a promise of transformation, never a countdown timer.

**German is the master language.** English and Spanish are re-derived from the German so they sound native, never translated word by word. Spanish is gender-neutral where the German is.

Sentence shapes that fit the components:

- `Display` — two short sentences, the second in `Em`. e.g. "Verstehe deinen Körper. *Verbessere deine Gesundheit nachhaltig.*"
- `Text variant="lead"` — one sentence stating what the section is for
- `PackageCard description` — bold the first sentence; it is the promise, and the only line a scanner reads
- `CredentialChip` — a noun phrase, no verb, one verifiable fact
- `ImageBand caption` — one editorial sentence, never a paragraph

Prefer "kann unterstützen" to "beseitigt". Where evidence is mixed, say so — on this brand, admitting uncertainty *is* the credibility.

---

## Compliance — legal, not stylistic

These are not preferences. They constrain what the page may say and load.

1. **Coaching and health education — never medical care.** No diagnosis, no treatment, no prescriptive medical nutrition therapy anywhere in the copy.
2. **"Dr." is Dr. rer. nat.** — a doctorate in **chemistry**, disclosed plainly wherever the title appears. Never imply a physician. The card spells it out in full; the site's About section and `MetaList` must do the same.
3. **Complement, never replace, medical care.** Refer out, and keep the emergency note.
4. **Testimonials must be real.** Never generate an invented review into `Testimonial`. Real or absent — there is no third option.
5. **Health data is GDPR special-category.** Consent, data minimisation, EU hosting. Any contact or intake form needs an explicit consent checkbox and a linked privacy policy. Third-party embeds (schedulers, analytics, maps) load only behind a consent gate. Self-hosted fonts are part of this — do not swap them for a font-host link.

Contact details as they appear on the card:

```
Dr. Desiree Gruber — Holistic Health Coach
+34 614 489 656
team@auralisnatura.com
www.auralisnatura.com
Barcelona · Online worldwide
```

---

## Open questions to resolve before build

1. **Language at launch** — German only, or DE/EN/ES from day one? This changes the routing and the copy workload. German is the master in all cases.
2. **The three packages** — names, prices, and what each includes. `PackageGrid` requires exactly three.
3. **Booking destination** — external scheduler, embedded scheduler, or a form? Determines whether a consent gate is needed.
4. **Photography** — portrait for `PhotoFrame`, and one editorial image for `ImageBand`.
5. **Credentials for the ribbon and `MetaList`** — each must be one verifiable fact.
6. **Real testimonials** — or section 8 is cut.

---

## Files in this bundle

```
design_system/
  _ds/auralis-natura-…/
    _ds_bundle.js          ← all 22 components → window.AuralisNatura
    _ds_bundle.css         ← compiled tokens + component styles
    styles.css             ← the single entry point: link this
    fonts/                 ← self-hosted Fraunces + Hanken Grotesk (woff2)

brand_reference/
  Visitenkarte 5B - Druck ohne Untergrund.dc.html   ← final card artwork (production)
  Visitenkarte 5B - Druck.dc.html                   ← same card, simulated paper, screen review
  doc-page.js, support.js                           ← runtime for the two files above

assets/
  seal-gold-watermark.png   ← use this on the site
  seal-gold-hi.png, seal-brown-hi.png
  qr-website.png            ← print only
```

The full design-system source tree — per-component `.prompt.md` files with worked examples, `.d.ts` types, and variant grids — lives in the bound design system at `components/<group>/<Name>/`. **Read the `.prompt.md` for any component before you first use it**; each one carries the rules that matter for that component. The two page-level guides are `guidelines/docs/guides/page-composition.md` and `guidelines/docs/guides/writing-copy.md`, and both are summarised above.

Open any `.dc.html` directly in a browser — no build step, no server, no dependencies.
