---
category: Content
keywords: [accordion, faq, wrapper, list]
---

# FaqList

The accordion wrapper. It supplies the hairline rules between items and the
column width that keeps answers readable.

```jsx
<FaqList>
  <FaqItem question="Ist das eine medizinische Beratung?" defaultOpen>…</FaqItem>
  <FaqItem question="Bist du Ärztin oder Ernährungsberaterin?">…</FaqItem>
  <FaqItem question="Was passiert mit meinen Gesundheitsdaten?">…</FaqItem>
</FaqList>
```

Five to eight questions. An FAQ is a place to close the remaining objections
before booking — beyond eight, it becomes documentation and stops converting.

Order by objection strength, not by topic: the doubt most likely to stop a
booking goes first.
