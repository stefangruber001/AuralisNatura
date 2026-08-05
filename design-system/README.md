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

Load **Fraunces** and **Hanken Grotesk** from Google Fonts in the host page.

## Components

| | |
|---|---|
| **Primitives** | `Button` `Label` `Spark` `Emblem` |
| **Typography** | `Display` `Heading` `Text` `Em` `Signature` |
| **Layout** | `Section` `SectionHead` |
| **Composites** | `PackageCard` `PackageGrid` `Testimonial` `CredentialChip` `CredentialRibbon` `CtaCard` `PhotoFrame` `FaqItem` `FaqList` `MetaList` `ImageBand` |

Every component ships a `*Props` type and worked `@example` blocks.

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
