---
category: Content
keywords: [credential, trust, chip, qualification]
---

# CredentialChip

One credential in the ribbon beneath the hero. Each chip leads with a glyph and
states a single verifiable fact.

```jsx
<CredentialChip>🔬 Dr. rer. nat. in Chemie</CredentialChip>
<CredentialChip>🧬 15+ Jahre Forschung und Pharmaindustrie</CredentialChip>
<CredentialChip>🌿 Spezialisiert auf Frauengesundheit</CredentialChip>
```

The glyphs in production use are 🔬 🧬 🥗 🌿 🧘 — a deliberate choice over
line-drawn icons, because the emoji carry warmth that matched icon sets did not.

**Every chip must be true and checkable.** These sit directly under the
headline, they are the first evidence a visitor gets, and this brand's
compliance guardrails do not tolerate an inflated credential. In particular:
"Dr. rer. nat." is an academic doctorate in chemistry, never a medical title.
