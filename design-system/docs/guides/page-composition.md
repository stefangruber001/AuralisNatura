# Composing a page

The Auralis homepage is a stack of `Section`s in a deliberate order. Anything
built with this system should follow the same argument, because the components
were shaped by it.

## The sequence

1. **Hero** — `Display` with the turn in `Em`, one `Text variant="lead"`, then
   one `clay` `Button` with `arrow` and a risk-removing `subLabel`, plus a
   `ghost` button beside it.
2. **`CredentialRibbon`** — trust, immediately, before any argument.
3. **The problem**, on `Section tone="dark"` — name what the reader is living
   with. This is the emotional turn and the first dark band.
4. **The method** — how the work is done, on light surfaces.
5. **`ImageBand`** — let the page breathe.
6. **Packages** — `SectionHead` then `PackageGrid` with three `PackageCard`s,
   cheapest first, `featured` on the middle one.
7. **About** — `PhotoFrame` and `MetaList` in a narrow left column, the
   founder's story and `Signature` in the wide right column.
8. **Testimonials**, on a dark band — genuine reviews only.
9. **FAQ** — `SectionHead center` then `FaqList`, objections ordered strongest
   first.
10. **`CtaCard`** — the closing ask. One per page, always last.

## Rhythm

- Alternate density, not colour. Two dense sections in a row get an `ImageBand`
  or a `padding="sm"` section between them.
- Three or four dark bands on a long page at most.
- One `Display`, one `Signature`, one `CtaCard`, one `clay` button per view.

## Widths

Everything lives inside `wrap` (supplied by `Section`). The About split is
roughly `.82fr 1.18fr` — the photograph column is the narrower one, on purpose:
the argument outweighs the portrait.
