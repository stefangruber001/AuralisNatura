#!/usr/bin/env python3
"""Assemble the WhatsApp Business setup sheet as one self-contained HTML file.

Everything is inlined as data URIs — the artifact host blocks every external
request, so a linked font or image would silently fall back to nothing. Built by
a script rather than hand-pasted base64 so it can be regenerated when the copy,
the palette or the avatars change.

  python3 brand/build_whatsapp_guide.py
"""
from __future__ import annotations
import base64, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
FONTS = ROOT / "design-system" / "assets" / "fonts"
SOCIAL = ROOT / "brand" / "social"
OUT = ROOT / "brand" / "whatsapp-business-setup.html"


def durl(p: pathlib.Path, mime: str) -> str:
    return f"data:{mime};base64," + base64.b64encode(p.read_bytes()).decode()


def font_face(family: str, path: pathlib.Path, weight: str, style: str = "normal") -> str:
    return (f"@font-face{{font-family:'{family}';font-style:{style};"
            f"font-weight:{weight};font-display:swap;"
            f"src:url({durl(path, 'font/woff2')}) format('woff2')}}")


FACES = "".join([
    font_face("Fraunces", FONTS / "fraunces-normal-300_600-latin.woff2", "300 600"),
    font_face("Hanken Grotesk", FONTS / "hanken-grotesk-normal-300_700-latin.woff2", "300 700"),
    font_face("IBM Plex Mono", FONTS / "ibm-plex-mono-normal-400-latin.woff2", "400"),
    font_face("IBM Plex Mono", FONTS / "ibm-plex-mono-normal-500-latin.woff2", "500"),
])

AV_CINNAMON = durl(SOCIAL / "auralis-avatar-cinnamon-640.png", "image/png")
AV_CREAM = durl(SOCIAL / "auralis-avatar-cream-640.png", "image/png")


def thumb(src: pathlib.Path, px: int) -> str:
    """A data URI for one scale-strip thumbnail.

    Reusing the 640px data URI at width=32 would re-embed ~480 KB of base64 per
    occurrence — six of those took the page from 1 MB to 4 MB. Pre-rendering also
    downsamples properly instead of leaving it to the browser at 5% scale.
    """
    from PIL import Image
    import io
    im = Image.open(src).convert("RGB").resize((px, px), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, "PNG", optimize=True)
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


STRIP = {
    f"t_{name}_{px}": thumb(SOCIAL / f"auralis-avatar-{name}-640.png", px)
    for name in ("cinnamon", "cream")
    for px in (128, 64, 48, 32)
}

# ─────────────────────────────────────────────────────────────── the content ──
# Every value here is taken from something authoritative in the repo, not
# invented: the canonical URL and phone from index.html, the mailbox and booking
# link from portal/config/config.json, the opening windows from
# portal/config/availability.json. The compliance lines come from CLAUDE.md §2.

DESCRIPTIONS = [
    ("Deutsch", "empfohlen",
     "Wissenschaftlich fundiertes Gesundheitscoaching mit Dr. rer. nat. Desiree "
     "Gruber. Ernährung, Energie und Frauengesundheit — klar erklärt, alltagstauglich. "
     "Bildung und Begleitung, keine ärztliche Behandlung. Kostenloses Erstgespräch: "
     "auralisnatura.com"),
    ("English", "",
     "Science-based health coaching with Dr. rer. nat. Desiree Gruber. Nutrition, "
     "energy and women's health — explained clearly, made doable. Education and "
     "coaching, not a substitute for medical care. Free first call at auralisnatura.com"),
    ("Español", "",
     "Coaching de salud con base científica, con Dr. rer. nat. Desiree Gruber. "
     "Nutrición, energía y salud femenina, explicado con claridad. Educación y "
     "acompañamiento, no sustituye la atención médica. Primera llamada gratuita en "
     "auralisnatura.com"),
    ("Deutsch + English", "wenn du beide Sprachen zeigen willst",
     "Wissenschaftlich fundiertes Gesundheitscoaching · Dr. rer. nat. Desiree Gruber, "
     "Barcelona. Bildung und Begleitung, keine medizinische Behandlung.\n"
     "Science-based health coaching. Education, not medical care. "
     "Free first call: auralisnatura.com"),
]

FIELDS = [
    ("Business name", "Auralis Natura",
     "Nur die Marke. WhatsApp zeigt den Namen neben dem Bild in einer Breite, in "
     "der „Auralis Natura · Holistic Health“ mitten im Wort abgeschnitten würde."),
    ("Kategorie", "Professional Services",
     "<strong>Nicht „Medical &amp; Health“.</strong> <em>Dietista-nutricionista</em> "
     "ist in Spanien nach Ley 44/2003 ein geschützter Beruf, und eine "
     "Gesundheitskategorie auf einem öffentlichen Profil ist eine implizite "
     "Berufsbehauptung. „Education“ wäre die andere unbedenkliche Wahl."),
    ("E-Mail", "team@auralisnatura.com",
     "Die Adresse, von der Website und Portal ohnehin senden. (In CLAUDE.md steht "
     "noch <code>office@</code> aus der ursprünglichen Übergabe — die Website nutzt "
     "an allen 17 Stellen <code>team@</code>, das ist die echte.)"),
    ("Website 1", "https://www.auralisnatura.com",
     "Die kanonische Adresse aus dem <code>&lt;link rel=\"canonical\"&gt;</code> "
     "der Seite selbst."),
    ("Website 2", "https://api.auralisnatura.com/book",
     "Direkt in den Buchungs-Assistenten. WhatsApp erlaubt zwei Links — den zweiten "
     "auf das zu setzen, was Leute tatsächlich tun sollen, bringt mehr als ein "
     "Social-Profil."),
    ("Adresse", "Barcelona, España",
     "Nur die Stadt. Die Straße in <code>company.json</code> ist noch ein "
     "Platzhalter, und eine Privatadresse gehört nicht versehentlich auf ein "
     "öffentliches Profil. Straße später ergänzen, falls ein Praxisraum dazukommt."),
]

HOURS = [
    ("Montag", "09:30 – 12:00", "14:00 – 17:00"),
    ("Dienstag", "09:30 – 12:00", "14:00 – 17:00"),
    ("Mittwoch", "09:30 – 12:00", ""),
    ("Donnerstag", "09:30 – 12:00", "14:00 – 17:00"),
    ("Freitag", "09:30 – 12:00", ""),
    ("Samstag", "geschlossen", ""),
    ("Sonntag", "geschlossen", ""),
]

GREETING = (
    "Willkommen bei Auralis Natura 🌿\n"
    "Danke für deine Nachricht — ich melde mich zu den Sprechzeiten.\n"
    "Termin direkt buchen: auralisnatura.com\n"
    "Bitte keine Gesundheitsdaten per WhatsApp senden.\n\n"
    "Welcome to Auralis Natura. Thanks for your message — I'll reply during "
    "business hours. Book directly: auralisnatura.com. Please don't send health "
    "details via WhatsApp."
)

AWAY = (
    "Danke für deine Nachricht 🌿 Ich bin gerade nicht erreichbar und antworte zu "
    "den Sprechzeiten (Mo–Fr).\n"
    "Termin buchen: auralisnatura.com\n"
    "Auralis Natura ist Gesundheitscoaching und Bildung — keine medizinische "
    "Behandlung. Dr. rer. nat. = Doktortitel in Chemie, keine Ärztin. "
    "Bei einem Notfall: 112.\n\n"
    "Thanks for your message. I reply during business hours (Mon–Fri). "
    "Book: auralisnatura.com. This is coaching and education, not medical care. "
    "In an emergency call 112."
)

QUICK_REPLIES = [
    ("/termin",
     "Such dir hier einen Termin aus, der dir passt: https://api.auralisnatura.com/book\n"
     "Das Erstgespräch dauert 25 Minuten und ist kostenlos."),
    ("/preise",
     "Klarheit · 199 € — Standortbestimmung mit persönlichem Bericht\n"
     "Wandel · 399 € — 4 Wochen Begleitung\n"
     "Balance · 899 € — 12 Wochen Begleitung\n"
     "Alle Details: auralisnatura.com"),
    ("/arzt",
     "Wichtig: Auralis Natura ist Gesundheitscoaching und Bildung — keine "
     "medizinische Behandlung und kein Ersatz dafür. Bei Beschwerden wende dich "
     "bitte an deine Ärztin oder deinen Arzt. Im Notfall: 112."),
]


def esc(s: str) -> str:
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def copyblock(value: str, *, mono: bool = True, counted: int | None = None) -> str:
    cls = "verbatim" + (" verbatim--mono" if mono else "")
    count = ""
    if counted is not None:
        count = (f'<span class="count">{len(value)}/{counted}</span>')
    return (f'<div class="{cls}">'
            f'<pre>{esc(value)}</pre>'
            f'<div class="verbatim__foot">{count}'
            f'<button class="copy" type="button" data-copy="{esc(value)}">Kopieren</button>'
            f'</div></div>')


def build() -> str:
    fields_html = "".join(
        f'<div class="field">'
        f'<div class="field__name">{esc(name)}</div>'
        f'<div class="field__body">{copyblock(value)}'
        f'<p class="field__why">{why}</p></div></div>'
        for name, value, why in FIELDS
    )

    desc_html = "".join(
        f'<div class="opt">'
        f'<div class="opt__head"><span class="opt__lang">{esc(lang)}</span>'
        + (f'<span class="pill">{esc(tag)}</span>' if tag else "")
        + f'</div>{copyblock(text, counted=256)}</div>'
        for lang, tag, text in DESCRIPTIONS
    )

    hours_html = "".join(
        f'<tr><th scope="row">{esc(day)}</th>'
        f'<td>{esc(a)}</td><td>{esc(b) if b else "—"}</td></tr>'
        for day, a, b in HOURS
    )

    qr_html = "".join(
        f'<div class="qr"><div class="qr__key">{esc(k)}</div>{copyblock(v)}</div>'
        for k, v in QUICK_REPLIES
    )

    return TEMPLATE.format(
        faces=FACES, av_cinnamon=AV_CINNAMON, av_cream=AV_CREAM,
        fields=fields_html, descriptions=desc_html, hours=hours_html,
        greeting=copyblock(GREETING, counted=1000),
        away=copyblock(AWAY, counted=1000),
        quick_replies=qr_html,
        **STRIP,
    )


TEMPLATE = r"""<title>Auralis Natura — WhatsApp Business einrichten</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
{faces}

/* The live site's tokens (index.html :root), not a new palette. Warm earth was
   a deliberate founder decision in 2026-06; this sheet is about the brand, so it
   wears it. Light is the base; dark redefines tokens only. */
:root {{
  --paper:#F5EEE0; --cream:#FBF6EB; --surface:#FFFCF6;
  --ink:#281F16; --ink-soft:#5C4A3A; --ink-faint:#75685A;
  --forest:#3D2719; --forest-deep:#221305;
  --clay:#A8492A; --gold:#AD7A32; --olive:#927B4A; --sand:#DAC79E;
  --rule:rgba(40,31,22,.16); --rule-soft:rgba(40,31,22,.08);
  --plate:#3D2719; --plate-ink:#F2E8D8; --plate-soft:#C9B69C; --plate-gold:#D6A84E;
  --r:0px;                       /* the brand's geometry is square */
  --measure:34rem;
}}
@media (prefers-color-scheme: dark) {{
  :root:not([data-theme="light"]) {{
    --paper:#1C1109; --cream:#241708; --surface:#2A1B0D;
    --ink:#F1E7D7; --ink-soft:#C4B29B; --ink-faint:#9C8B75;
    --clay:#C47A52; --gold:#D6A84E; --olive:#B09765; --sand:#DAC79E;
    --rule:rgba(241,231,215,.18); --rule-soft:rgba(241,231,215,.09);
    --plate:#120A03; --plate-ink:#F2E8D8; --plate-soft:#B9A88F; --plate-gold:#D6A84E;
  }}
}}
:root[data-theme="dark"] {{
  --paper:#1C1109; --cream:#241708; --surface:#2A1B0D;
  --ink:#F1E7D7; --ink-soft:#C4B29B; --ink-faint:#9C8B75;
  --clay:#C47A52; --gold:#D6A84E; --olive:#B09765; --sand:#DAC79E;
  --rule:rgba(241,231,215,.18); --rule-soft:rgba(241,231,215,.09);
  --plate:#120A03; --plate-ink:#F2E8D8; --plate-soft:#B9A88F; --plate-gold:#D6A84E;
}}

*,*::before,*::after {{ box-sizing:border-box; }}
body {{
  margin:0; background:var(--paper); color:var(--ink);
  font-family:'Hanken Grotesk',system-ui,sans-serif; font-weight:400;
  font-size:17px; line-height:1.62; -webkit-text-size-adjust:100%;
}}
.wrap {{ max-width:52rem; margin:0 auto; padding:0 1.35rem 5rem; }}

h1,h2,h3 {{ font-family:Fraunces,Georgia,serif; font-weight:500; text-wrap:balance;
  letter-spacing:-.012em; margin:0; }}
h1 {{ font-size:clamp(2rem,6.2vw,2.9rem); line-height:1.1; }}
h2 {{ font-size:clamp(1.4rem,3.9vw,1.85rem); line-height:1.2; }}
h3 {{ font-size:1.05rem; font-weight:600; line-height:1.35; }}
p {{ margin:0; max-width:var(--measure); }}
a {{ color:var(--clay); text-underline-offset:.18em; text-decoration-thickness:1px; }}
code {{ font-family:'IBM Plex Mono',ui-monospace,Menlo,monospace; font-size:.86em;
  background:var(--rule-soft); padding:.08em .32em; }}
strong {{ font-weight:600; }}

/* The "Fig. 0X —" specimen label is the brand's documented section device
   (CLAUDE.md §3), so section order here is real: it is the order of the work. */
.fig {{ font-family:'IBM Plex Mono',ui-monospace,Menlo,monospace; font-size:.68rem;
  font-weight:500; letter-spacing:.15em; text-transform:uppercase;
  color:var(--gold); display:block; margin-bottom:.6rem; }}

header.masthead {{ padding:3.4rem 0 2rem; border-bottom:1px solid var(--rule); }}
.masthead .kicker {{ font-family:'IBM Plex Mono',ui-monospace,Menlo,monospace;
  font-size:.7rem; letter-spacing:.17em; text-transform:uppercase;
  color:var(--olive); margin-bottom:1rem; }}
.masthead p {{ margin-top:1rem; color:var(--ink-soft); font-size:1.06rem; }}

section {{ padding:3rem 0 0; }}
section > h2 {{ margin-bottom:.9rem; }}
section > p {{ color:var(--ink-soft); }}
.stack {{ display:flex; flex-direction:column; gap:1.6rem; margin-top:1.7rem; }}
.stack--tight {{ gap:1.05rem; }}

/* verbatim = a value to be copied exactly. Mono is doing a job here, not a look:
   it marks "this string, character for character". */
.verbatim {{ border:1px solid var(--rule); background:var(--surface); }}
.verbatim pre {{ margin:0; padding:.85rem 1rem; white-space:pre-wrap; word-break:break-word;
  font-family:'Hanken Grotesk',system-ui,sans-serif; font-size:.97rem; line-height:1.55; }}
.verbatim--mono pre {{ font-family:'IBM Plex Mono',ui-monospace,Menlo,monospace;
  font-size:.9rem; }}
.verbatim__foot {{ display:flex; align-items:center; justify-content:flex-end; gap:.85rem;
  border-top:1px solid var(--rule-soft); padding:.35rem .5rem .35rem 1rem; }}
.count {{ font-family:'IBM Plex Mono',ui-monospace,Menlo,monospace; font-size:.7rem;
  color:var(--ink-faint); margin-right:auto; font-variant-numeric:tabular-nums; }}
.copy {{ font:inherit; font-size:.78rem; font-weight:500; letter-spacing:.02em;
  border:1px solid var(--rule); background:transparent; color:var(--ink-soft);
  padding:.28rem .8rem; cursor:pointer; border-radius:var(--r);
  transition:background .14s ease,color .14s ease,border-color .14s ease; }}
.copy:hover {{ background:var(--clay); border-color:var(--clay); color:#FFF8EE; }}
.copy:focus-visible {{ outline:2px solid var(--gold); outline-offset:2px; }}
.copy[data-done="1"] {{ background:var(--olive); border-color:var(--olive); color:#FFF8EE; }}

.field {{ display:grid; gap:.5rem .5rem; }}
.field__name {{ font-family:'IBM Plex Mono',ui-monospace,Menlo,monospace;
  font-size:.72rem; font-weight:500; letter-spacing:.11em; text-transform:uppercase;
  color:var(--olive); padding-top:.15rem; }}
.field__why {{ margin-top:.55rem; font-size:.92rem; color:var(--ink-soft); }}
@media (min-width:44rem) {{
  .field {{ grid-template-columns:11rem 1fr; gap:0 1.6rem; }}
}}

.opt__head {{ display:flex; align-items:baseline; gap:.7rem; margin-bottom:.45rem; }}
.opt__lang {{ font-family:Fraunces,Georgia,serif; font-size:1.02rem; font-weight:500; }}
.pill {{ font-family:'IBM Plex Mono',ui-monospace,Menlo,monospace; font-size:.63rem;
  letter-spacing:.12em; text-transform:uppercase; color:var(--clay);
  border:1px solid var(--clay); padding:.13rem .45rem; }}

/* The plate: the avatars belong on the brand's own dark ground, and the scale
   strip below them is the actual argument for which one to use. */
.plate {{ background:var(--plate); color:var(--plate-ink); padding:2rem 1.35rem 1.8rem;
  margin:1.8rem 0 0; }}
.plate__grid {{ display:grid; gap:1.8rem; grid-template-columns:1fr; }}
@media (min-width:36rem) {{ .plate__grid {{ grid-template-columns:1fr 1fr; }} }}
.opt-av {{ text-align:center; }}
.opt-av img {{ width:100%; max-width:200px; height:auto; border-radius:50%;
  display:block; margin:0 auto .85rem; }}
.opt-av__name {{ font-family:'IBM Plex Mono',ui-monospace,Menlo,monospace;
  font-size:.68rem; letter-spacing:.13em; text-transform:uppercase;
  color:var(--plate-gold); }}
.opt-av__note {{ font-size:.86rem; color:var(--plate-soft); margin:.3rem auto 0;
  max-width:19rem; }}
/* A stand-in for the surface the avatar actually lands on: WhatsApp's chat list
   is white in light mode and stays near-white regardless of the viewer's theme,
   so this band is fixed light on purpose and carries its own ink colours. */
.chatlist {{ background:#FFFFFF; border:1px solid rgba(40,31,22,.14); border-top:0;
  padding:1.2rem 1.35rem 1.35rem; }}
.chatlist__label {{ font-family:'IBM Plex Mono',ui-monospace,Menlo,monospace;
  font-size:.65rem; letter-spacing:.13em; text-transform:uppercase;
  color:#8A7B69; margin-bottom:.95rem; }}
.chatlist__row {{ display:flex; align-items:flex-end; gap:1.25rem; flex-wrap:wrap; }}
.chatlist__row + .chatlist__row {{ margin-top:1.1rem; padding-top:1.1rem;
  border-top:1px solid rgba(40,31,22,.08); }}
.scale__item {{ text-align:center; }}
.scale__item img {{ border-radius:50%; display:block; }}
.scale__item span {{ display:block; margin-top:.4rem;
  font-family:'IBM Plex Mono',ui-monospace,Menlo,monospace; font-size:.62rem;
  color:#8A7B69; font-variant-numeric:tabular-nums; }}
.scale__item--name {{ font-family:'IBM Plex Mono',ui-monospace,Menlo,monospace;
  font-size:.68rem; letter-spacing:.1em; text-transform:uppercase; color:#5C4A3A;
  align-self:center; margin-left:auto; }}

table {{ border-collapse:collapse; width:100%; max-width:30rem; font-size:.95rem; }}
th,td {{ text-align:left; padding:.42rem .8rem .42rem 0; border-bottom:1px solid var(--rule-soft);
  font-variant-numeric:tabular-nums; }}
th[scope="row"] {{ font-weight:400; color:var(--ink-soft); }}
thead th {{ font-family:'IBM Plex Mono',ui-monospace,Menlo,monospace; font-size:.66rem;
  letter-spacing:.11em; text-transform:uppercase; color:var(--olive); font-weight:500; }}

/* Guardrails get a rail, not a rounded card — they are the one thing on this
   page that cannot be treated as a suggestion. */
.guard {{ border-left:3px solid var(--clay); padding:.15rem 0 .15rem 1.15rem; }}
.guard h3 {{ color:var(--clay); margin-bottom:.3rem; }}
.guard p {{ font-size:.95rem; color:var(--ink-soft); }}

.qr {{ display:grid; gap:.45rem; }}
.qr__key {{ font-family:'IBM Plex Mono',ui-monospace,Menlo,monospace; font-size:.82rem;
  font-weight:500; color:var(--clay); }}

.note {{ font-size:.88rem; color:var(--ink-faint); max-width:var(--measure); }}
footer {{ margin-top:4rem; padding-top:1.4rem; border-top:1px solid var(--rule);
  font-size:.84rem; color:var(--ink-faint); }}
@media (prefers-reduced-motion:reduce) {{ * {{ transition:none !important; }} }}
</style>

<div class="wrap">

<header class="masthead">
  <div class="kicker">Auralis Natura · Betriebsunterlage</div>
  <h1>WhatsApp Business einrichten</h1>
  <p>Jedes Feld des Profils, mit dem Text zum Kopieren. Die Werte stammen aus der
  Website, der Portal-Konfiguration und den echten Buchungszeiten — nicht erfunden.</p>
</header>

<section>
  <span class="fig">Fig. 01 — zuerst prüfen</span>
  <h2>Die Nummer</h2>
  <p>WhatsApp Business und das normale WhatsApp können nicht gleichzeitig
  dieselbe Nummer benutzen. <strong>+34 614 489 656</strong> steht auf der Website
  als Geschäftsnummer.</p>
  <div class="stack stack--tight">
    <p class="note"><strong>Wenn die Nummer heute in deinem privaten WhatsApp
    liegt:</strong> die Business-App bietet beim ersten Start an, den Verlauf zu
    übernehmen — danach ist die Nummer nur noch geschäftlich. Das ist meist das,
    was du willst, aber es ist eine Einbahnstraße.</p>
    <p class="note"><strong>Wenn du privat und geschäftlich trennen willst:</strong>
    brauchst du eine zweite Nummer (eSIM reicht, ~5 €/Monat). Dann müsste die
    Website-Nummer geändert werden — sag Bescheid, das ist eine Zeile.</p>
  </div>
</section>

<section>
  <span class="fig">Fig. 02 — Profilbild</span>
  <h2>Zwei Varianten, eine Empfehlung</h2>
  <p>WhatsApp schneidet das Profilbild <em>rund</em> zu und zeigt es in der
  Chatliste bei etwa 48 px. Beide Dateien sind 640 × 640 px — die Größe, die
  WhatsApp tatsächlich speichert.</p>

  <div class="plate">
    <div class="plate__grid">
      <div class="opt-av">
        <img src="{av_cinnamon}" alt="Auralis-Natura-Siegel auf zimtbraunem Grund">
        <div class="opt-av__name">Zimtbraun · nimm dieses</div>
        <p class="opt-av__note">Eigene dunkle Silhouette. Bleibt auf dem hellen
        Grund einer Chatliste sichtbar.</p>
      </div>
      <div class="opt-av">
        <img src="{av_cream}" alt="Auralis-Natura-Siegel auf cremefarbenem Grund">
        <div class="opt-av__name">Creme · Alternative</div>
        <p class="opt-av__note">Für dunkle Hintergründe. In WhatsApp verschwimmt
        es mit dem Weiß ringsum.</p>
      </div>
    </div>
  </div>

  <!-- Deliberately NOT on the dark plate above: a chat list is white, and
       showing the cream variant on brown would flatter exactly the option this
       section argues against. -->
  <div class="chatlist">
    <div class="chatlist__label">wie es in der Chatliste ankommt</div>
    <div class="chatlist__row">
      <div class="scale__item"><img src="{t_cinnamon_64}" width="64" height="64" alt=""><span>64</span></div>
      <div class="scale__item"><img src="{t_cinnamon_48}" width="48" height="48" alt=""><span>48</span></div>
      <div class="scale__item"><img src="{t_cinnamon_32}" width="32" height="32" alt=""><span>32</span></div>
      <div class="scale__item scale__item--name">Zimtbraun</div>
    </div>
    <div class="chatlist__row">
      <div class="scale__item"><img src="{t_cream_64}" width="64" height="64" alt=""><span>64</span></div>
      <div class="scale__item"><img src="{t_cream_48}" width="48" height="48" alt=""><span>48</span></div>
      <div class="scale__item"><img src="{t_cream_32}" width="32" height="32" alt=""><span>32</span></div>
      <div class="scale__item scale__item--name">Creme</div>
    </div>
  </div>

  <p class="note" style="margin-top:1.1rem">Beide Dateien liegen im Chat als
  Anhang. Auf dem iPhone kannst du sie auch hier lange drücken → <em>Sichern</em>.
  Nicht das alte <code>logo-ig-profile.png</code> nehmen: dessen grüner Ring
  stammt aus der früheren Farbwelt und wird vom runden Zuschnitt angeschnitten.</p>
</section>

<section>
  <span class="fig">Fig. 03 — Profilfelder</span>
  <h2>Was in welches Feld gehört</h2>
  <div class="stack">
    {fields}
  </div>
</section>

<section>
  <span class="fig">Fig. 04 — Profilbeschreibung</span>
  <h2>Beschreibung · max. 256 Zeichen</h2>
  <p>Eine Sprache auswählen. Die Website erkennt die Sprache ohnehin selbst;
  deine bisherigen Klientinnen sind Deutsch und Englisch.</p>
  <div class="stack">
    {descriptions}
  </div>
</section>

<section>
  <span class="fig">Fig. 05 — Öffnungszeiten</span>
  <h2>Sprechzeiten</h2>
  <p>Genau die Fenster, die deine Buchungsseite anbietet
  (<code>portal/config/availability.json</code>, Zeitzone Europe/Madrid). So kann
  niemand eine Zeit sehen, die es im Kalender nicht gibt.</p>
  <table>
    <thead><tr><th>Tag</th><th>Vormittag</th><th>Nachmittag</th></tr></thead>
    <tbody>{hours}</tbody>
  </table>
  <p class="note" style="margin-top:1rem">Falls deine WhatsApp-Version pro Tag nur
  <em>ein</em> Zeitfenster erlaubt: 09:30 – 17:00 eintragen und die Mittagspause in
  der Abwesenheitsnachricht erwähnen.</p>
</section>

<section>
  <span class="fig">Fig. 06 — Automatische Nachrichten</span>
  <h2>Begrüßung und Abwesenheit</h2>
  <p>Beide sind zweisprachig, weil du nicht steuern kannst, wer schreibt. Die
  Abwesenheitsnachricht trägt die Pflichtangaben: Coaching statt Behandlung,
  <em>Dr. rer. nat.</em> statt Ärztin, 112 im Notfall.</p>
  <div class="stack">
    <div><h3>Begrüßungsnachricht</h3>{greeting}</div>
    <div><h3>Abwesenheitsnachricht</h3>{away}</div>
  </div>
</section>

<section>
  <span class="fig">Fig. 07 — Schnellantworten</span>
  <h2>Drei Kürzel, die dir Tipparbeit sparen</h2>
  <p>In der App unter <em>Tools → Schnellantworten</em>. Du tippst <code>/</code>
  und das Kürzel, WhatsApp setzt den Text ein.</p>
  <div class="stack">
    {quick_replies}
  </div>
</section>

<section>
  <span class="fig">Fig. 08 — nicht verhandelbar</span>
  <h2>Drei Regeln</h2>
  <div class="stack">
    <div class="guard">
      <h3>Keine Gesundheitskategorie</h3>
      <p>„Medical &amp; Health“ als Kategorie ist auf einem öffentlichen Profil eine
      implizite Berufsbehauptung. <em>Dietista-nutricionista</em> ist in Spanien
      nach Ley 44/2003 geschützt. <strong>Professional Services</strong> oder
      <strong>Education</strong>.</p>
    </div>
    <div class="guard">
      <h3>Keine Gesundheitsdaten im Chat</h3>
      <p>Was jemand dir über Beschwerden, Medikamente oder eine Schwangerschaft
      schreibt, ist besondere Kategorie personenbezogener Daten nach Art. 9 DSGVO —
      und liegt dann auf Metas Servern, außerhalb deines verschlüsselten Portals.
      WhatsApp ist für „wann hast du Zeit“. Alles Inhaltliche gehört in den
      Aufnahmebogen im Portal. Die Begrüßungsnachricht sagt das gleich mit.</p>
    </div>
    <div class="guard">
      <h3>Keine Beratung per Chat</h3>
      <p>Eine schnelle Antwort auf „was soll ich bei X essen?“ ist genau die
      Grenzüberschreitung, die das ganze Modell schützen soll. Freundlich auf das
      Erstgespräch verweisen — dafür ist <code>/termin</code> da. Bei Alarmzeichen:
      zur Ärztin, im Notfall 112.</p>
    </div>
  </div>
</section>

<footer>
  Erstellt aus <code>index.html</code>, <code>portal/config/config.json</code>,
  <code>portal/config/availability.json</code> und CLAUDE.md §2.
  Bilder: <code>brand/social/</code>, erzeugt von
  <code>brand/make_social_avatars.py</code>.
</footer>

</div>

<script>
document.addEventListener('click', function (e) {{
  var b = e.target.closest('.copy');
  if (!b) return;
  var text = b.getAttribute('data-copy');
  var done = function () {{
    var old = b.textContent;
    b.textContent = 'Kopiert';
    b.setAttribute('data-done', '1');
    setTimeout(function () {{ b.textContent = old; b.removeAttribute('data-done'); }}, 1600);
  }};
  if (navigator.clipboard && navigator.clipboard.writeText) {{
    navigator.clipboard.writeText(text).then(done, fallback);
  }} else {{ fallback(); }}
  function fallback() {{
    // Older iOS Safari in an embedded view has no async clipboard.
    var ta = document.createElement('textarea');
    ta.value = text; ta.setAttribute('readonly', '');
    ta.style.cssText = 'position:absolute;left:-9999px';
    document.body.appendChild(ta);
    ta.select(); ta.setSelectionRange(0, text.length);
    try {{ document.execCommand('copy'); done(); }}
    catch (err) {{ b.textContent = 'Bitte markieren'; }}
    document.body.removeChild(ta);
  }}
}});
</script>
"""


if __name__ == "__main__":
    html = build()
    OUT.write_text(html, encoding="utf-8")
    print(f"  {OUT.relative_to(ROOT)}  {len(html.encode()) / 1024:.0f} KB")
