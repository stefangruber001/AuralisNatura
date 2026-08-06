---
category: Content
keywords: [credentials, table, facts, definition list]
---

# MetaList

The credentials table: term on the left, value right-aligned, hairline between
rows. Quiet and factual — and, on this site, the single most persuasive element
on the page, because it is the only one that makes no argument at all.

```jsx
<MetaList entries={[
  { term: 'Wissenschaftlicher Hintergrund', value: 'Dr. rer. nat. in Chemie' },
  { term: 'Berufserfahrung',                value: 'Mehr als fünfzehn Jahre in der Forschung' },
  { term: 'Schwerpunkte',                   value: 'Ganzheitliche Gesundheit · Ernährung · Frauengesundheit' },
  { term: 'Standort',                       value: 'Barcelona · Online weltweit' },
]} />
```

Four to six rows. Values stay short enough to hold one line at tablet width —
a wrapping value breaks the column rhythm that makes the block feel like a
record rather than a paragraph.

**Facts only.** Every line must be verifiable; this component is where a
regulator or a sceptical client looks first.
