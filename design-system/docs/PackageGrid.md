---
category: Commerce
keywords: [pricing grid, row, layout, packages]
---

# PackageGrid

The row that holds `PackageCard`s — three across on desktop, stacking on mobile
with equal-height alignment.

```jsx
<PackageGrid>
  <PackageCard name="Klarheit" price="€199" … />
  <PackageCard name="Wandel"   price="€399" mid … />
  <PackageCard name="Balance"  price="€899" featured … />
</PackageGrid>
```

**The grid is a fixed three columns** (collapsing to one below 1024px), so ship
exactly three cards. Two leave an empty third column; four wrap into a lonely
second row. Three is also what makes the light → `mid` → `featured` stepping
legible: the row has to read as a ladder, and a ladder needs three rungs.

Order cheapest to most expensive, left to right.
