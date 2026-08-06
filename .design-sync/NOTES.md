# design-sync notes — @auralis/design-system

## Repo shape

- The design system lives in `design-system/`, not at the repo root. Run the converter
  from the repo root with `--node-modules ./design-system/node_modules --entry
  ./design-system/dist/index.js`; `.design-sync/` and `ds-bundle/` stay at the root.
- `npm ci && npm run build` inside `design-system/` produces `dist/index.js`,
  `dist/auralis.css` and the `.d.ts` tree. The build is a 20-line `build.mjs` (esbuild,
  React external) plus `tsc --emitDeclarationOnly`; it takes under a second.
- `src/styles/components.css` **is the production site's stylesheet**
  (`index.html`'s `<style>` block), kept byte-identical apart from the seal URL. Any fix
  made here must be mirrored into `index.html` in the same commit, or the two drift.

## Fonts

- Fraunces and Hanken Grotesk are **self-hosted** in `design-system/assets/fonts/`
  (latin + latin-ext woff2, ~340 KB) with `assets/fonts.css` wired via `cfg.extraFonts`.
  The live site loads them from Google Fonts; the design system cannot, because a
  rendered design gets only the `styles.css` import closure and no network.
- Hanken Grotesk is one *variable* file per subset — Google's CSS repeats the same file
  for weights 300–700. The download step dedupes it to one `@font-face` per subset with
  `font-weight: 300 700`. If you re-download, dedupe again or the bundle carries 5×.

## Bugs this sync found in the shipped code (all fixed)

1. `.pkg.feat .pk-price .from` inherited `--ink-faint`, so the price label was illegible
   on the featured (dark) package card — on the live site too. Now `--sage-soft`.
2. `p.big` was scoped to `.about-body`, so `<Text variant="big">` was a no-op anywhere
   else. The selector is now unscoped (same computed result on the site; the
   `.about-body p` rule still loses on source order).
3. `FaqItem` only toggled the `open` class, but the stylesheet keeps `.faq-a` at
   `max-height:0` and the site's own script measures and sets the height. The component
   now does the same in `useLayoutEffect` — before the fix the accordion never opened.
4. `Label`/`SectionHead` set `onDark` with an inline colour, which recoloured the text
   but not the leaf glyph in `::before`. They now add the stylesheet's own
   `label--cream` class, which does both.

## Known render warns

None. `package-validate.mjs` exits clean with zero warnings.

## Card presentation

Almost every component here is page-width — headlines, bands, cards. Most carry
`cfg.overrides.<Name>.cardMode = "column"` so each story gets the full card width;
without it the big Fraunces headlines wrapped mid-word in the product's grid cells.
`PackageCard`, `PackageGrid` and `Testimonial` also pin `viewport: "1280x900"` — their
grids collapse to one column at ≤1024px, so a 900px capture would misrepresent them.

## Preview imagery

`.design-sync/previews/_assets.ts` inlines three of the site's own photographs as data
URIs (portrait 4:5, a 2:3 tall crop for the `objectPosition` demo, and a 16:7 band).
The bundle ships no image directory, so a `/images/...` path would render as a broken
image in every card. Regenerate with PIL if the photography changes.

## Content rules that are not style preferences

- **Testimonials must be real.** The three quotes in `previews/Testimonial.tsx` are
  verbatim from the live site (Rebecca E., Bettina P., Helmut P.). If you need another
  example, take another real one — never invent a review, in a preview or anywhere else.
- Credential lines are checkable facts. "Dr. rer. nat." is a chemistry doctorate and is
  never to be presented as a medical title.

## Upload status

**This run produced a verified `ds-bundle/` but never uploaded it.** The `DesignSync`
tool could not authorize in this environment (`/design-login` needs an interactive
terminal). No claude.ai/design project exists yet, so `config.json` carries no
`projectId`. A future run from an authenticated client should create the project, record
its id, and upload — everything else is done and reproducible from this config.

## Re-sync risks

- `components.css` is copied from `index.html`. If the site changes and the copy does
  not, every preview silently renders against a stale stylesheet. Diff them before
  trusting a re-sync.
- The inlined photographs in `_assets.ts` are a snapshot. They will not track edits to
  `images/`.
- `docs/*.md` quote live prices (€199 / €399 / €899) and the package names
  Klarheit · Wandel · Balance. Those changed once already in 2026; re-check them against
  `CLAUDE.md` on any re-sync.
- Playwright is pinned to 1.56.0 here because the container caches chromium build 1194 at
  `/opt/pw-browsers`. A different image will need a different playwright version — read
  `playwright-core/browsers.json` as a file to check the pin.
- The bundle was verified only through the local render check and the absolute rubric; it
  has never been seen inside claude.ai/design itself.
