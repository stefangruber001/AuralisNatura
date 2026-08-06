# Auralis Natura — building with this system

"Modern Materia Medica": PhD-level scientific rigour meeting botanical warmth. Premium,
calm, editorial. This is a **holistic health coaching** brand — never medical care.

## Setup

No provider or context is needed. Import the stylesheet **once** at the app root — without
it every component renders unstyled, because all styling lives in plain CSS classes:

```jsx
import '@auralis/design-system/styles.css';
import { Section, Display, Em, Button } from '@auralis/design-system';

<Section>
  <Display>Understand your body. <Em>Improve your health for good.</Em></Display>
  <Button variant="clay" size="lg" arrow subLabel="free, no obligation">
    Book an intro call
  </Button>
</Section>
```

The two brand faces — **Fraunces** (display) and **Hanken Grotesk** (body) — ship with the
system as self-hosted woff2 and are declared inside `styles.css`. Importing that one
stylesheet is all the type setup there is; nothing needs to be fetched from a font host.

## Styling idiom

**Plain CSS classes plus CSS custom properties — no utility framework, no style props.**
Components already carry their classes; for your own layout glue, use the tokens via
`var(--*)` rather than raw hex. Never invent class names — nothing outside this stylesheet
resolves.

Colour tokens (all defined in `styles.css`):
`--ink` `--ink-soft` `--ink-faint` · `--forest` `--forest-soft` `--forest-deep` `--forest-2` ·
`--sage` `--sage-soft` · `--clay` `--clay-deep` `--clay-soft` · `--gold` `--gold-bright` ·
`--paper` `--paper-2` `--paper-3` `--cream`

Structure tokens: `--line` `--line-strong` `--gold-hair` `--shadow-sm` `--shadow-md`
`--ease` `--maxw` `--gut` `--r` `--r-lg` `--font-display` `--font-body`.

Utility classes that exist and are safe to reuse: `wrap` (max-width container),
`sec-pad` / `sec-pad-sm` (vertical rhythm), `u-kick` (kicker rule), `em` (italic accent).

## Rules that define the look

1. **Corners are square.** `--r` and `--r-lg` are `0px`. Never add `border-radius` —
   it is the single most defining structural decision in this system.
2. **`--clay` is the action colour, never a large field.** Use it for one primary button
   per view. Large surfaces are `--paper` / `--cream`, or the dark brown band.
3. **On dark bands** (`<Section tone="dark">`, `CtaCard`) body text is cream and emphasis
   is `--gold-bright`. On light sections emphasis is `--ink` at weight 600 (`<strong>`).
4. **Never hyphenate.** `hyphens` is `none` throughout. German compounds are handled by
   type size, not by breaking words.
5. **Edges are hairlines**, and shadows are wide and soft — never tight or dark.
6. Use `tone="dark"` sparingly — three or four times on a long page at most.

## Components — 22, in six groups

- **Foundations** — `Button` `Label` `Emblem` `Spark`
- **Typography** — `Display` `Heading` `Text` `Em` `Signature`
- **Layout** — `Section` `SectionHead`
- **Media** — `ImageBand` `PhotoFrame`
- **Content** — `CredentialChip` `CredentialRibbon` `MetaList` `Testimonial` `FaqItem` `FaqList`
- **Commerce** — `PackageCard` `PackageGrid` `CtaCard`

Each has a `*Props` type and a written `.prompt.md` with worked examples and the rules
that matter. `PackageCard` takes `featured` to invert one card in a row to the dark band;
`PackageGrid` is a fixed three columns, so ship exactly three cards. `Button` variants are
`clay | forest | ghost`. `Label` and `SectionHead` take `onDark` on the brown bands.

Page-level guidance — the section order, the pacing rules and how to write the copy —
is in `guidelines/`.

## Content guardrails — legal, not stylistic

Copy written for this brand must respect these; they are not preferences:

1. **Coaching and health education — never medical care.** No diagnosis, no treatment,
   no prescriptive medical nutrition therapy.
2. **"Dr." means Dr. rer. nat.** (a chemistry doctorate), disclosed plainly. Never imply
   a physician.
3. **Complement, never replace, medical care** — refer out, and keep the emergency note.
4. **Testimonials must be real.** Never generate an invented review into `Testimonial`.
5. Health data is GDPR special-category: consent, minimisation, EU hosting.

Voice: warm, intelligent, calm, precise — *a brilliant friend who happens to be a
scientist.* German is the master language; English and Spanish are re-derived from it,
never translated literally.
