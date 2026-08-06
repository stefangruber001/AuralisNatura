---
category: Typography
keywords: [h2, h3, section title, card title]
---

# Heading

Section and card headings, in Fraunces.

- `level={2}` — the section heading. One per section, directly under its
  `Label`, or supplied through `SectionHead`.
- `level={3}` — a card title: package names, FAQ groups, the closing CTA.

```jsx
<Heading level={2}>
  Dein Körper sendet Signale.<br />
  <Em>Finden wir heraus, was dahintersteckt.</Em>
</Heading>

<Heading level={3}>Klarheit</Heading>
```

A manual `<br />` is how the brand controls a two-part headline — the second
half is usually the `Em` turn. Use it deliberately, and check it at 360px wide
before shipping.

`as` decouples the visual size from the heading tag so document outline stays
correct when a card title is not really a level-3 heading.
