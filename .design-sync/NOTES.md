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

**Still never uploaded, after two attempts (2026-08-12 and 2026-08-15).** `DesignSync`
cannot authorize in this environment — the tool's own message says `/design-login`
requires an interactive terminal and suggests Claude Design's "Send to Claude Code Web"
or supplying the project files directly. `config.json` therefore still carries no
`projectId`, and no claude.ai/design project exists.

Do not spend another run rediscovering this: **from a claude.ai/code remote session the
upload leg is simply unavailable.** Either run the sync from an interactive terminal, or
take the manual route below, which is now built and is the founder's chosen path.

### The manual route (built 2026-08-15)

`brand/build_design_package.py` assembles **`brand/Auralis-Natura-Design-Package.zip`**
(~28 MB) whose `02-design-system/` folder is exactly the verified `ds-bundle/` contents
minus `_screenshots/` and dot-files — i.e. the format Claude Design consumes. The founder
uploads that folder's *contents* at a Design project root. Rebuild order is
`design-system && npm run build` → converter → `build_design_handbook.py` →
`build_design_package.py`.

`brand/build_design_handbook.py` builds the 20-page Design Handbook that ships as
`01-handbook/`. Its swatches parse `src/styles/tokens.css` and its component roster parses
`docs/*.md` frontmatter, so both track the code automatically. Page geometry is checked by
measuring every `.page` against 297 mm in headless chromium — if an edit makes a page
overflow, the PDF silently grows a blank spill page, so re-run that measurement after any
content change.

Note `ds-bundle/tokens/` is emitted **empty** here: all 33 tokens live inside
`_ds_bundle.css` (which is `dist/auralis.css`, tokens + components in one file) and reach
designs through the `styles.css` import closure. That is correct, not a missing directory.

## Re-sync risks

- `components.css` is copied from `index.html`. If the site changes and the copy does
  not, every preview silently renders against a stale stylesheet. Diff them before
  trusting a re-sync. **This already happened once** (caught 2026-08-15): the copy
  predated the 2026-08-10 homepage changes and was missing the seventh life-phase tag
  and its re-spacing, `.seasons-media`/`.seasons-photo`, the `.seasons` one-size rule
  and the `.about-lede` mobile pairing. Regenerate with: take `index.html`'s `<style>`
  block, drop the banner comment and the `:root` block (that is what `tokens.css`
  carries), keep the three-line header. Verify afterwards that the two CSS fixes listed
  above still survive — they were mirrored into the site, so a regeneration preserves
  them, but a future fix made only in `components.css` would be silently reverted.
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
