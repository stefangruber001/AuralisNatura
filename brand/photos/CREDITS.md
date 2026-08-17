# Photo provenance

Where the photography came from and under what terms. Started 2026-08-17, when a
third-party stock photo entered the app for the first time and there was no record
anywhere in the repo of where any image originated.

Keep this current. A licence you cannot evidence is a licence you do not have —
and an App Store listing is commercial use.

## App programme photos

Built into `ios-app/AuralisApp/Assets.xcassets` by
`ios-app/scripts/build_photo_assets.py` (4:3 landscape, 1x/2x/3x ladder).

| Asset | Programme | Master | Source & licence |
|---|---|---|---|
| `PhotoBowl` | Balance · `flourish` | `brand/photos/programme-wandel-bowl.jpg` | **Pexels**, photo **1092730** by **Jane Trang Doan**. Pexels Licence: free to use, commercial use allowed, no attribution required. Added 2026-08-17. |
| `PhotoNourish` | Klarheit · `root` | `images/nourish.jpg` | Provenance not recorded when added (commit `db3925e`, 2026-08-06). Not a photograph of a real client — a still life. |
| `PhotoTea` | Wandel · `bloom` | `images/tea.jpg` | Provenance not recorded when added (commit `db3925e`). Still life. |
| `PhotoPortrait` | Verbindung · `grove`, and any unknown key | `images/desiree-portrait.jpg` | Photograph of Dr. Desiree Gruber, used with her consent as the business owner. Crop biased to 0.10 (near the top) — a centred 4:3 window cut through her forehead. |
| `PhotoDesiree` | welcome screen avatar (56 pt) | `images/desiree-portrait.jpg` | Same photograph, square head-and-shoulders crop, beside her credential line in guest mode. |

## Retired but kept

| File | Note |
|---|---|
| `images/desiree-consult.jpg` | Was `PhotoConsult` on Balance until 2026-08-17. A real photo of Desiree working with a client — the most authentic image in the set. Restoring it is one line in `CatalogStore.photo(for:)` plus an entry in the build script. |

## Website imagery

`images/*.jpg` also carries the certificates (`cert-*.jpg`) and photographs of
Desiree (`desiree-*.jpg`), which are hers. The provenance of the still lifes
(`nourish`, `tea`, `about-evidence`) was never written down; if any turns out to
be licence-encumbered it should be replaced rather than argued about.

## Rule of thumb

- Free-licence sources (Pexels, Unsplash free tier) are fine for commercial use.
  **Unsplash+ is the paid tier** — its previews carry a visible watermark and
  must never be shipped; only the licensed download may be used.
- Never ship a watermarked comp, in the app, the website, the report or social.
- Record every new photo here in the same change that adds it.
