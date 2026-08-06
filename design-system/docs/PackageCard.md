---
category: Commerce
keywords: [pricing, package, offer, plan, card]
---

# PackageCard

A pricing card — the commercial heart of the page.

```jsx
<PackageCard
  tag="Standortbestimmung & Gesundheitsanalyse"
  name="Klarheit"
  priceLabel="Individuelle Beratung"
  price="€199"
  description={<>
    <strong>Klarheit zeigt dir, wo deine Gesundheit heute steht.</strong>{' '}
    Gemeinsam erfassen wir deine Gewohnheiten, deine Umstände und deine Ziele.
  </>}
  featuresLabel="Enthalten sind:"
  features={[
    { text: 'Ausführlicher Gesundheitsfragebogen' },
    { text: 'Persönlicher schriftlicher Bericht' },
    { text: '60-minütiges 1:1-Gespräch' },
  ]}
  ctaLabel="Programm Klarheit buchen"
  ctaHref="https://book.stripe.com/…"
/>
```

## Rules that matter

- **Bold the first sentence of `description`.** The card is scanned before it is
  read; the bolded promise is what the scanner takes away.
- **Features are single lines**, four to six of them, each a deliverable rather
  than a benefit. "60-minütiges 1:1-Gespräch", not "Zeit für dich".
- **The row steps light → sand → dark.** Leave the first card plain, give the
  middle one `mid` (the warm sand treatment) and the last one `featured` (the
  dark brown band with the `clay` button). That rising weight *is* the ladder;
  it reads as value increasing, not as one card shouting.
- **`featured` on at most one card in a row.** Two featured cards mean no
  recommendation was made. `featured` wins over `mid` if both are passed.
- **The CTA names the programme** — "Programm Klarheit buchen", not "Jetzt
  buchen". Three identical buttons in a row are three unlabelled doors.

The production ladder is Klarheit €199 · Wandel €399 (4 weeks) · Balance €899
(12 weeks), localised per language (EN Clarity · Change · Balance, ES Claridad ·
Cambio · Equilibrio), ordered cheapest first: plain, `mid`, `featured`.
