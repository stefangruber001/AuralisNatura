---
category: Foundations
keywords: [action, cta, link, primary]
---

# Button

The one interactive element that carries an action. Everything else on an
Auralis page is type, rule and photograph — so a button is loud by default, and
its restraint is what makes it read as premium.

## Choosing a variant

| Variant | Use it for |
|---|---|
| `clay` (default) | The single primary action on a surface — booking, buying, enquiring. |
| `forest` | The dark button that lives in the header and app bar. |
| `ghost` | The quiet secondary next to a `clay` button ("See how it works"). |

**Never render two `clay` buttons in one view.** The colour is the page's only
"do this" signal; a second one halves it. A surface with two equal actions is a
surface with an unresolved decision — pick a primary and make the other `ghost`.

## Arrow and sub-label

`arrow` adds the diagonal glyph used on conversion calls to action. `subLabel`
puts a quiet second line inside the button — reserve it for removing risk at the
moment of clicking ("kostenlos und unverbindlich"), never for extra marketing.

```jsx
<Button variant="clay" size="lg" arrow subLabel="kostenlos und unverbindlich">
  Kostenloses Gespräch buchen
</Button>

<Button variant="ghost" size="lg" href="#services">So funktioniert es</Button>
```

Passing `href` renders an anchor, otherwise a `<button>`. Use `external` only
with `href` — it adds `target="_blank"` with the safe `rel`.
