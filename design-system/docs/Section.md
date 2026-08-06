---
category: Layout
keywords: [band, wrapper, rhythm, container]
---

# Section

A full-width page section carrying the site's vertical rhythm and max-width
wrap. Every block of the page is a `Section`; the page is a stack of them.

## Tone is a pacing decision

- `paper` (default) — the light surface. Most of the page.
- `cream` — a slightly warmer light surface, for a change of register that is
  not a full stop.
- `dark` — the warm-brown gradient band. This is the emotional turn: the
  problem, the closing argument, the testimonials.

**Three or four `dark` sections per page at most.** They work because they are
rare; a page that alternates light and dark reads as striped, not composed.

On a dark section: `Label` needs `onDark`, `Em` switches to amber
automatically, and `<strong>` becomes amber gold — all handled by the
stylesheet.

```jsx
<Section tone="dark" id="problem">
  <Label onDark>Warum Auralis</Label>
  <Heading level={2}>Dein Körper sendet Signale.</Heading>
</Section>
```

`padding="sm"` tightens an interstitial section — a credentials ribbon or a
single-line statement between two full sections.
