---
category: Media
keywords: [portrait, image, frame, about]
---

# PhotoFrame

A photograph in the house frame: square corners, a soft wide shadow, and a gold
hairline inset just inside the edge. It is how a person appears on an Auralis
page.

```jsx
<PhotoFrame
  src="/images/desiree-portrait.jpg"
  alt="Dr. rer. nat. Desiree Gruber"
  width={1122}
  height={1402}
  objectPosition="center 22%"
/>
```

- **Always pass `width` and `height`.** They are the intrinsic dimensions and
  they prevent the layout shift that otherwise happens on a slow connection.
- **`objectPosition` is a face-placement control.** Faces sit high in a 4:5
  crop, so the default is `center 22%`. Check it per image rather than trusting
  the default.
- Portrait crops (4:5) are the house format. A landscape photograph in this
  frame competes with `ImageBand` and usually belongs there instead.

Keep the frame smaller than instinct suggests when it sits beside text: the
photograph supports the argument, it is not the argument.
