---
category: Content
keywords: [ribbon, credentials, trust bar, hero]
---

# CredentialRibbon

The row of credential chips that sits immediately under the hero. Trust is
established here, in the first screen, before any argument is made.

```jsx
<CredentialRibbon>
  <CredentialChip>🔬 Dr. rer. nat. in Chemie</CredentialChip>
  <CredentialChip>🧬 15+ Jahre Forschung</CredentialChip>
  <CredentialChip>🥗 Ganzheitliche Ernährungsberatung</CredentialChip>
  <CredentialChip>🌿 Spezialisiert auf Frauengesundheit</CredentialChip>
</CredentialRibbon>
```

**Five chips maximum.** The ribbon is scanned in about a second; a sixth chip
does not add credibility, it just pushes the row into a second line and turns a
confident statement into a list.

The ribbon brings its own wrap and background — put it between sections, not
inside one.
