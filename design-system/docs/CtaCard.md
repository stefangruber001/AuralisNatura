---
category: Commerce
keywords: [cta, closing, conversion, booking]
---

# CtaCard

The closing dark card that ends the page — the final ask, with the seal
watermarked behind it.

```jsx
<CtaCard
  label="Kostenlos & unverbindlich"
  title={<>Buche dein kostenloses<br /> Erstgespräch.</>}
  body="In einem ruhigen Gespräch schauen wir gemeinsam, wo du gerade stehst."
  aside={<BookingForm />}
/>
```

**One per page.** It is the last thing on the page for a reason; repeated
mid-page it stops being a conclusion and becomes a nag.

`aside` fills the right-hand column — a booking widget, a short form, or the
primary `Button`. Leave it out and the card centres on the message alone, which
is the right choice when the actual booking lives elsewhere.

Keep `body` to one or two sentences. Everything that needed arguing has been
argued by the time a reader arrives here; this card only has to make the next
step feel small.
