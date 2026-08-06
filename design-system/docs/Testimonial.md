---
category: Content
keywords: [review, quote, social proof, stars]
---

# Testimonial

A client review on the dark testimonial band: stars, the quote, then an initial
avatar with name and programme.

```jsx
<Testimonial
  rating={5}
  quote="Dank ihrer kompetenten, individuellen Beratung habe ich meine Ernährung nachhaltig umgestellt. Ich habe spürbar mehr Energie im Alltag."
  name="Rebecca E."
  role="Balance · Hausmannstätten"
/>
```

**Only genuine reviews, ever.** Fabricated testimonials are a hard guardrail for
this brand, not a style preference — no placeholder quotes shipped as if real,
no invented names, no rating that was not given. If there is no review yet, ship
the section without one.

`role` carries programme and place, which is what makes a review feel specific
rather than generic. `rating` is optional — omit it rather than assume five
stars.

Two or three testimonials fill the band. More reads as a wall and gets skipped.
