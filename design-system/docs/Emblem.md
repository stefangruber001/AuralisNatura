---
category: Foundations
keywords: [seal, logo, mark, watermark, brand]
---

# Emblem

The botanical seal — the recurring brand mark, and the only illustrative
element in the system. It ships inside the stylesheet as a data URI, so it needs
no image path and works offline.

Two treatments:

- **Solid** — 96px in the About column, 54px paired with a photograph, 30px in
  the app bar. The mark signs a block; it never decorates one.
- **`watermark`** — 7% opacity at 180–260px, sitting behind the dark bands and
  the closing CTA card. It should be felt, not seen; if a viewer notices it as
  an image, it is too strong or too large.

```jsx
<Emblem size={96} />
<Emblem size={220} watermark />
```

One solid emblem per page section at most. The seal earns its authority from
scarcity.
