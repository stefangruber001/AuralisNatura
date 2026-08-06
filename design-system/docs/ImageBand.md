---
category: Media
keywords: [photo, full-bleed, banner, caption]
---

# ImageBand

A full-bleed photographic band with an optional caption plate. Its job is to let
the page breathe between two dense sections — it is white space that happens to
be a photograph.

```jsx
<ImageBand
  src="/images/nourish.jpg"
  alt="Gemüse und ein Notizbuch auf einem Tisch"
  label="Der Ansatz"
  caption="Fundierte Wissenschaft. Persönliche Begleitung."
/>
```

The caption is **one editorial sentence**, set in Fraunces italic over the
image — never a paragraph, never a list. If it needs two sentences it belongs in
a `Section`, not on a photograph.

`hero` is the taller variant for a band that opens a page.

Photography is warm-graded toward the palette before it arrives here. An
ungraded stock image will read as foreign against the earth tones no matter how
good it is on its own.
