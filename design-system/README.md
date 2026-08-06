# @auralis/design-system

The production design system behind **www.auralisnatura.com** — *Modern Materia Medica*:
PhD-level scientific rigour meeting botanical warmth.

The stylesheet in `src/styles/components.css` is the **live site's CSS, unmodified**.
Components consume those classes; nothing here is a reimplementation.

## Use

```bash
npm install
npm run build      # -> dist/index.js + dist/auralis.css + dist/**/*.d.ts
```

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

**Fraunces** and **Hanken Grotesk** are self-hosted in `assets/fonts/` and declared
inside `dist/auralis.css`. Importing the stylesheet is the whole type setup — no font
host, no network.

## Components

| | |
|---|---|
| **Foundations** | `Button` `Label` `Emblem` `Spark` |
| **Typography** | `Display` `Heading` `Text` `Em` `Signature` |
| **Layout** | `Section` `SectionHead` |
| **Media** | `ImageBand` `PhotoFrame` |
| **Content** | `CredentialChip` `CredentialRibbon` `MetaList` `Testimonial` `FaqItem` `FaqList` |
| **Commerce** | `PackageCard` `PackageGrid` `CtaCard` |

Every component ships a `*Props` type, worked `@example` blocks, and a written page in
[`docs/`](docs) covering when to use it and — as often matters more — when not to.
Page-level guidance lives in [`docs/guides/`](docs/guides).

## Demo

`examples/demo.tsx` composes a full page from the library alone — the reference for how
the parts go together, and the harness used to verify each renders correctly.

```bash
npx esbuild examples/demo.tsx --bundle --format=esm --jsx=automatic --outfile=examples/demo.js
python3 -m http.server 8908   # then open /examples/
```

## The rules that define the look

1. **Corners are square** (`--r: 0px`). Never add `border-radius`.
2. **`--clay` is the action colour**, never a large field.
3. **Dark bands** carry cream text and amber (`--gold-bright`) emphasis.
4. **Never hyphenate** — `hyphens: none` throughout.
5. Edges are hairlines; shadows are wide and soft.

Full conventions, including the brand's non-negotiable content guardrails:
[`../.design-sync/conventions.md`](../.design-sync/conventions.md).
