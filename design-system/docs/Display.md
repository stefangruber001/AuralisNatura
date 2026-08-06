---
category: Typography
keywords: [hero, headline, fraunces, h1]
---

# Display

The largest editorial voice — Fraunces at a fluid clamp, set once per page for
the hero headline. A second `Display` on a page destroys the hierarchy the first
one creates.

It is a light weight at a very large size, so it needs short lines. Aim for
three or four lines of four to six words; the stylesheet balances the rag for
you (`text-wrap: balance`), but it cannot rescue a sentence that is simply too
long.

Set the turn of the sentence in `Em` — that contrast between upright and italic
is the brand's signature move.

```jsx
<Display>
  Verstehe deinen Körper. <Em>Verbessere deine Gesundheit nachhaltig.</Em>
</Display>
```

`as` changes the tag when the hero is not the document's `h1` — the visual level
and the semantic level are set separately on purpose.

Never hyphenate or force a break inside a word here. Words break badly at this
size, and the founder's standing instruction is that words are not broken.
