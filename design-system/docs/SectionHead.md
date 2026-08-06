---
category: Layout
keywords: [section title, kicker, intro, header]
---

# SectionHead

The standard opening of a section: kicker label, title, optional lead
paragraph. Using it instead of hand-assembling `Label` + `Heading` + `Text` is
what keeps every section on the page starting on the same beat.

```jsx
<SectionHead
  label="Wege der Zusammenarbeit"
  title={<>Verstehen. Verändern. <Em>Dranbleiben.</Em></>}
  sub="Jeder Weg beginnt mit einem kostenlosen Gespräch."
/>
```

`center` centres the block — used for the certificates carousel and the FAQ,
where the content beneath is symmetrical. Left-aligned is the default and the
right choice whenever the content below is a grid or a column.

Pass `onDark` inside a `Section tone="dark"` so the kicker switches to warm
sand.
