---
category: Typography
keywords: [paragraph, body, lead, copy]
---

# Text

Body copy, in Hanken Grotesk.

| Variant | Where |
|---|---|
| `body` (default) | Ordinary paragraphs. |
| `lead` | The sentence that opens a section, under the heading. |
| `big` | The emphasised opening paragraph of a long passage — the About column. |

At most one `lead` and one `big` per section; they are openings, and a page of
openings has no body.

```jsx
<Text variant="lead">Jeder Weg beginnt mit einem kostenlosen Gespräch.</Text>

<Text>
  <strong>Es geht nicht um die nächste Diät.</strong> Es geht darum, deine
  Ernährung so zu gestalten, dass sie zu deinem Leben passt.
</Text>
```

Emphasis inside body copy is `<strong>`: ink on light surfaces, amber on the
dark bands — the stylesheet handles the switch. Bold the first sentence of a
paragraph the reader must not miss, and only that one.
