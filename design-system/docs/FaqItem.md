---
category: Content
keywords: [accordion, question, faq, disclosure]
---

# FaqItem

One question in the FAQ accordion. It manages its own open state.

```jsx
<FaqItem question="Ist das eine medizinische Beratung?" defaultOpen>
  Nein. Auralis Natura ist ganzheitliche Gesundheits- und Ernährungsberatung.
  Sie ersetzt keine ärztliche Diagnose, Behandlung oder Therapie.
</FaqItem>
```

`defaultOpen` on exactly one item — the question that removes the biggest doubt.
An accordion that opens fully closed makes the reader work; one that opens with
everything expanded is just a wall of text.

On this site the FAQ carries the compliance answers: not medical care, a
doctorate rather than a medical degree, and how health data is handled. Those
three belong in every FAQ built with this system, in plain language.
