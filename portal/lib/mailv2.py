"""The v2 mail bodies: the installed lib/mail_v2 templates, personalised and localised.

Boundary: this module is LAYOUT. It knows the templates and how to swap their
sample content for real values; it never reads client data, never decides
wording of its own, and never talks to cfg or booking. mailer.py prepares every
value (already localised where the sentence is a founder-locked one) and calls
in. That keeps the import direction one-way — mailer imports mailv2 — and keeps
every guardrail sentence in exactly one place.

The templates carry a fully-worked sample client (Elena Martín). Rendering is
substitution against that sample. Substitution is STRICT: if a sample string is
no longer found, the template drifted and we raise rather than silently ship a
mail with Elena's data in it — a wrong-name mail to a real client is the worst
outcome this file can produce, so it is the one this file makes impossible.

German is the template text; EN and ES swap in the founder-approved translations
that mailer.py has carried since the language work — the v2 designer wrote the
German FROM those dicts, so the packs below are reuse, not re-translation.
"""
from __future__ import annotations

import html
import re
from html.entities import codepoint2name
from pathlib import Path

_DIR = Path(__file__).resolve().parent / "mail_v2"
_CACHE: dict[str, str] = {}

TPL = {
    "ack": "01-Buchung-Eingangsbestaetigung",
    "booking": "02-Termin-Bestaetigung",
    "reminder": "03-Termin-Erinnerung",
    "cancel": "04-Termin-Absage",
    "creds": "05-Zugangsdaten-Portal",
    "sessions": "06-Programm-Terminplan",
    "report": "07-Bericht-Zustellung",
    "feedback": "08-Feedback-Anfrage",
    "newsletter": "09-Newsletter",
    "briefing": "10-Neue-Buchung-Briefing",
    "social": "11-Social-Wochenpaket",
}


def _tpl(key: str) -> str:
    name = TPL[key]
    if name not in _CACHE:
        _CACHE[name] = (_DIR / f"{name}.html").read_text(encoding="utf-8")
    return _CACHE[name]


def _entity(s: str) -> str:
    """Encode non-ASCII as named entities, the way half the templates store text."""
    out = []
    for ch in s:
        cp = ord(ch)
        if cp > 127 and cp in codepoint2name:
            out.append(f"&{codepoint2name[cp]};")
        else:
            out.append(ch)
    return "".join(out)


def _sub(doc: str, old: str, new: str, required: bool = True) -> str:
    """Replace every occurrence of `old`, tolerating the template's two source
    encodings (raw UTF-8 and named entities). Raises on a miss so template
    drift is loud, never a mail with the sample client's data in it."""
    for form in (old, _entity(old)):
        if form in doc:
            return doc.replace(form, new)
    if required:
        raise KeyError(f"mail template drift: {old[:70]!r} not found")
    return doc


def _pack(doc: str, lang: str, rows: list[tuple[str, str, str]]) -> str:
    """Apply a language pack: rows of (german, english, spanish)."""
    if lang == "de":
        return doc
    idx = 1 if lang == "en" else 2
    # longest German string first: "Erinnerung" must never fire before the
    # sentence "eine kleine Erinnerung an unser Gespräch:" it lives inside.
    # The replacement is NOT html.escape()d: rows may carry < and > as
    # structural anchors (">bestätigt" targets the <em> content), and the
    # translations are our own literals, not user input. Only a bare & is
    # entity-encoded so it cannot start an accidental entity.
    for row in sorted(rows, key=lambda r: -len(r[0])):
        repl = row[idx]
        if "&" in repl and ";" not in repl:
            repl = repl.replace("&", "&amp;")
        doc = _sub(doc, row[0], repl)
    return doc


def _e(v: str) -> str:
    return html.escape(str(v or ""))


# ---------------------------------------------------------------- shared parts

# The masthead sub-line and the footer are identical across templates.
_CHROME = [
    ("Auralis Natura bietet Gesundheitscoaching und Gesundheitsbildung, keine "
     "medizinische Diagnose oder Therapie.",
     "Auralis Natura offers health coaching and health education, not medical "
     "diagnosis or treatment.",
     "Auralis Natura ofrece coaching y educación en salud, no diagnóstico ni "
     "tratamiento médico."),
]

_MONTHS = {
    "de": ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August",
           "September", "Oktober", "November", "Dezember"],
    "en": ["January", "February", "March", "April", "May", "June", "July", "August",
           "September", "October", "November", "December"],
    "es": ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
           "septiembre", "octubre", "noviembre", "diciembre"],
}
_DAYS = {
    "de": ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"],
    "en": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
    "es": ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"],
}


def _class_swap(doc: str, cls: str, new: str) -> str:
    """Replace the text content of the unique element with class=cls."""
    pat = re.compile(rf'(class="{cls}"[^>]*>)(?:(?!</).)*?(</)', re.S)
    if not pat.search(doc):
        raise KeyError(f"mail template drift: no element with class {cls!r}")
    return pat.sub(lambda m: m.group(1) + new + m.group(2), doc, count=1)


def tile(doc: str, parts: dict, lang: str) -> str:
    """Fill the date 'ticket': parts = {day, month(1-12), year, weekday(0-6),
    time 'HH:MM', tz}. Localised here because the tile is pure layout."""
    doc = _class_swap(doc, "d", _e(parts["day"]))
    doc = _class_swap(doc, "m", _e(_MONTHS[lang][parts["month"] - 1]))
    doc = _class_swap(doc, "y", _e(parts["year"]))
    doc = _class_swap(doc, "wd", _e(_DAYS[lang][parts["weekday"]]))
    suffix = {"de": "&ensp;Uhr", "en": "", "es": "&ensp;h"}[lang]
    pat = re.compile(r'(class="tm"[^>]*>)(?:(?!</span>).)*?(</span>)', re.S)
    m0 = pat.search(doc)
    inner = m0.group(0)
    b = re.search(r"(<b[^>]*>)[^<]*(</b>)", inner)
    new_inner = (inner[: b.start() - m0.start()] if False else None)
    # rebuild the tm span: keep the <b> styling, swap time, localise suffix
    rebuilt = re.sub(r"(<b[^>]*>)[^<]*(</b>)(?:&ensp;)?[^<]*",
                     lambda m: m.group(1) + _e(parts["time"]) + m.group(2) + suffix,
                     inner, count=1)
    doc = doc[: m0.start()] + rebuilt + doc[m0.end():]
    return doc


def _tile_fallback(doc: str, when_text: str) -> str:
    """No slot timestamp — a rare legacy path. The tile degrades to the
    formatted date line rather than showing the sample date."""
    doc = _class_swap(doc, "d", "&middot;")
    doc = _class_swap(doc, "m", "")
    doc = _class_swap(doc, "y", "")
    doc = _class_swap(doc, "wd", _e(when_text))
    doc = re.sub(r'(class="tm"[^>]*>).*?(</span>)', r"\1\2", doc, count=1, flags=re.S)
    return doc


def footer(doc: str, owner: str, brand: str, email: str, phone: str, lang: str) -> str:
    doc = _pack(doc, lang, _CHROME)
    doc = _sub(doc, "Dr. rer. nat. Desiree Gruber · Auralis Natura",
               f"{_e(owner)} · {_e(brand)}", required=False)
    contact = f"{_e(email)} · {_e(phone)}" if phone else _e(email)
    doc = _sub(doc, "team@auralisnatura.com · +34 614 489 656", contact, required=False)
    return doc


def _apple_span(doc: str) -> str:
    """The Apple cell links nowhere — the .ics rides as an attachment, which is
    what Apple Mail opens natively. A dead '#' link is worse than no link."""
    return re.sub(r'<a href="#"([^>]*)>((?:Apple)[^<]*)</a>',
                  r"<span\1>\2</span>", doc)


def calendar(doc: str, links: dict | None, lang: str) -> str:
    """Fill the Google/Outlook one-click links; Apple stays the attachment."""
    labels = {
        "de": ("In den Kalender eintragen", "Apple / .ics im Anhang"),
        "en": ("Add it to your calendar", "Apple / .ics attached"),
        "es": ("Añadir a tu calendario", "Apple / .ics adjunto"),
    }[lang]
    doc = _sub(doc, "In den Kalender eintragen", _e(labels[0]), required=False)
    doc = _sub(doc, "Apple / .ics im Anhang", _e(labels[1]), required=False)
    if links:
        doc = re.sub(r'href="#"(?=[^>]*>Google Calendar)',
                     f'href="{_e(links.get("google", ""))}"', doc)
        doc = re.sub(r'href="#"(?=[^>]*>Outlook)',
                     f'href="{_e(links.get("outlook", ""))}"', doc)
        doc = _apple_span(doc)
    else:
        # no slot to link: drop the whole calendar row rather than dead buttons
        doc = re.sub(r'<div class="cal"[^>]*>.*?</div>\s*', "", doc, flags=re.S)
        doc = _apple_span(doc)
    return doc


_MEET_BTN = {
    "de": "Zum Gespräch (Google Meet)",
    "en": "Join the call (Google Meet)",
    "es": "Unirse a la llamada (Google Meet)",
}


def meet_block(meet: str, lang: str) -> str:
    """The join link, in the body, one tap away — founder decision 2026-08-10.
    Styled like the template's own primary button (creds mail .btn)."""
    if not meet:
        return ""
    return (
        f'<p style="margin:0 0 8px;text-align:center">'
        f'<a href="{_e(meet)}" style="display:inline-block;background:#A8492A;'
        f'color:#FBF6EB;text-decoration:none;padding:14px 28px;font-weight:600;'
        f'font-size:15px;letter-spacing:.02em">{_e(_MEET_BTN[lang])} &#8594;</a></p>'
        f'<p style="margin:0 0 20px;text-align:center;font-size:12px;line-height:1.5">'
        f'<a href="{_e(meet)}" style="color:#8C7E6E;text-decoration:none;'
        f'word-break:break-all">{_e(meet)}</a></p>')


# ---------------------------------------------------------------- client mails

_TICKET_WORDS = [
    ("Dein Termin", "Your appointment", "Tu cita"),
    ("Videogespräch", "Video call", "Videollamada"),
    ("Kennenlerngespräch", "Introductory call", "Llamada de presentación"),
]


def render_ack(name: str, lang: str, tile_parts: dict | None, tz: str,
               when_local: str = "") -> str:
    doc = _tpl("ack")
    doc = _sub(doc, "Elena Martín", _e(name))
    doc = tile(doc, tile_parts, lang) if tile_parts else _tile_fallback(doc, when_local)
    doc = _sub(doc, "Europe/Madrid", _e(tz), required=False)
    rows = [
        ("Deine Anfrage ist angekommen.", "Your request has arrived.", "Tu solicitud ha llegado."),
        ("Buchungsanfrage", "Booking request", "Solicitud de reserva"),
        ("Deine Anfrage ist", "Your request has", "Tu solicitud ha"),
        (">angekommen", ">arrived", ">llegado"),
        ("Hallo ", "Hi ", "Hola "),
        ("vielen Dank für deine Anfrage — ich habe sie erhalten.",
         "thank you for your request — it has reached me.",
         "gracias por tu solicitud — la he recibido."),
        ("Gewünschter Termin", "Requested time", "Horario solicitado"),
        ("Angefragt", "Requested", "Solicitado"),
        ("So geht es weiter", "What happens next", "Los próximos pasos"),
        ("Ich sehe mir deine Angaben in Ruhe an.",
         "I will look through what you shared.",
         "Revisaré con calma lo que has compartido."),
        ("Ich bestätige dir den Termin anschließend mit einer Kalender-Einladung.",
         "I will then confirm the appointment with a calendar invitation.",
         "Después te confirmaré la cita con una invitación de calendario."),
        ("Du musst dafür nichts weiter tun.",
         "There is nothing else you need to do.",
         "No tienes que hacer nada más."),
        ("Falls sich etwas ändert oder du lieber eine andere Zeit hättest, antworte "
         "einfach auf diese E-Mail.",
         "If anything changes, or you would prefer a different time, simply reply to "
         "this email.",
         "Si algo cambia o prefieres otro horario, basta con responder a este correo."),
        ("Bis bald,", "See you soon,", "Hasta pronto,"),
        ("Videogespräch", "Video call", "Videollamada"),
    ]
    return _pack(doc, lang, rows)


def render_booking(name: str, lang: str, tile_parts: dict | None, tz: str,
                   links: dict | None, meet: str, when_local: str = "") -> str:
    doc = _tpl("booking")
    doc = _sub(doc, "Elena Martín", _e(name))
    doc = _sub(doc, "Dein Termin ist bestätigt · Mittwoch, 26. August 2026 · 10:05 (Europe/Madrid)",
               {"de": "Dein Termin ist bestätigt",
                "en": "Your call is confirmed",
                "es": "Tu cita está confirmada"}[lang])
    doc = tile(doc, tile_parts, lang) if tile_parts else _tile_fallback(doc, when_local)
    doc = _sub(doc, "Europe/Madrid", _e(tz), required=False)
    fallback = ("Der Termin ist reserviert. Trag ihn dir mit einem Klick ein — den Link "
                "zum Videogespräch schicke ich dir rechtzeitig vor unserem Termin.")
    if meet:
        kept = {"de": "Der Termin ist reserviert. Trag ihn dir mit einem Klick ein.",
                "en": "The appointment is reserved. Add it with one click.",
                "es": "La cita está reservada. Añádela con un clic."}[lang]
        doc = _sub(doc, fallback, _e(kept) + "</p>" + meet_block(meet, lang) + "<p>")
    else:
        doc = _sub(doc, fallback, _e({
            "de": fallback,
            "en": "The appointment is reserved. Add it with one click — I will send "
                  "you the video link in good time before our call.",
            "es": "La cita está reservada. Añádela con un clic — te enviaré el enlace "
                  "de vídeo con tiempo antes de nuestra cita."}[lang]))
    doc = calendar(doc, links, lang)
    rows = [
        ("Terminbestätigung", "Appointment confirmed", "Cita confirmada"),
        ("Dein Termin ist", "Your call is", "Tu cita está"),
        (">bestätigt", ">confirmed", ">confirmada"),
        ("Hallo ", "Hi ", "Hola "),
        ("dein kostenloses Kennenlerngespräch ist bestätigt für:",
         "your free introductory call is confirmed for:",
         "tu llamada gratuita de presentación está confirmada para:"),
        ("Reserviert", "Reserved", "Reservado"),
        ("Kostenlos", "Free", "Gratis"),
        ("So läuft unser Gespräch", "How our conversation works",
         "Cómo será nuestra conversación"),
        ("Wir schauen gemeinsam, wo du gerade stehst, was du dir wünschst und welcher "
         "nächste Schritt für dich sinnvoll ist. Kein Verkaufsgespräch, keine "
         "Vorbereitung nötig.",
         "Together we look at where you are right now, what you are hoping for and "
         "which next step makes sense for you. Not a sales call, and nothing to prepare.",
         "Miramos juntas dónde estás ahora, qué deseas y cuál es el siguiente paso que "
         "tiene sentido para ti. No es una llamada de venta y no hay que preparar nada."),
        ("Der Link öffnet sich direkt im Browser — du musst nichts installieren.",
         "The link opens straight in your browser — nothing to install.",
         "El enlace se abre directamente en el navegador — no hay que instalar nada."),
        ("Such dir einen ruhigen Ort und Kopfhörer, wenn du welche hast.",
         "Find a quiet spot, and headphones if you have them.",
         "Busca un lugar tranquilo y auriculares, si tienes."),
        ("Leg dir bereit, was dir wichtig ist: Fragen, Befunde, Notizen — nichts davon "
         "ist Pflicht.",
         "Bring whatever matters to you: questions, results, notes — none of it required.",
         "Trae lo que te importe: preguntas, informes, notas — nada es obligatorio."),
        ("Wenn dir etwas dazwischenkommt, antworte einfach auf diese E-Mail — eine "
         "Absage ist jederzeit in Ordnung.",
         "If something comes up, just reply to this email — cancelling is always fine.",
         "Si te surge algo, responde a este correo — cancelar siempre está bien."),
        ("Bis bald,", "See you soon,", "Hasta pronto,"),
        ("promoviert in Chemie", "doctorate in chemistry", "doctorada en química"),
        ("über fünfzehn Jahre in Forschung und pharmazeutischer Industrie",
         "over fifteen years in research and the pharmaceutical industry",
         "más de quince años en investigación e industria farmacéutica"),
        ("zertifiziert in ganzheitlicher Gesundheit, Ernährung und Frauengesundheit",
         "certified in holistic health, nutrition and women's health",
         "certificada en salud holística, nutrición y salud femenina"),
    ] + _TICKET_WORDS
    return _pack(doc, lang, rows)


def render_reminder(name: str, lang: str, tile_parts: dict | None, tz: str,
                    links: dict | None, meet: str, when_local: str = "") -> str:
    doc = _tpl("reminder")
    doc = _sub(doc, "Elena Martín", _e(name))
    doc = _sub(doc, "Erinnerung: unser Gespräch · Mittwoch, 26. August 2026 · 10:05 (Europe/Madrid)",
               {"de": "Erinnerung: unser Gespräch", "en": "Reminder: our call",
                "es": "Recordatorio: nuestra llamada"}[lang])
    doc = tile(doc, tile_parts, lang) if tile_parts else _tile_fallback(doc, when_local)
    doc = _sub(doc, "Europe/Madrid", _e(tz), required=False)
    nolink = "Den Link zum Videogespräch schicke ich dir rechtzeitig vor unserem Termin."
    if meet:
        doc = _sub(doc, nolink, meet_block(meet, lang))
    else:
        doc = _sub(doc, nolink, _e({
            "de": nolink,
            "en": "I will send you the video link in good time before our call.",
            "es": "Te enviaré el enlace de vídeo con tiempo antes de nuestra cita."}[lang]))
    doc = calendar(doc, links, lang)
    rows = [
        ("Erinnerung", "Reminder", "Recordatorio"),
        ("Eine kleine", "A gentle", "Un pequeño"),
        ("Hallo ", "Hi ", "Hola "),
        ("eine kleine Erinnerung an unser Gespräch:",
         "a gentle reminder of our upcoming call:",
         "un pequeño recordatorio de nuestra llamada:"),
        ("Bestätigt", "Confirmed", "Confirmada"),
        ("Falls dir etwas dazwischenkommt, antworte einfach auf diese E-Mail — wir "
         "finden einen neuen Termin.",
         "If something comes up, just reply to this email and we'll find a new time.",
         "Si te surge algo, responde a este correo y buscamos otro momento."),
        ("Bis gleich,", "See you soon,", "Hasta ahora,"),
    ] + _TICKET_WORDS
    return _pack(doc, lang, rows)


def render_cancel(name: str, lang: str, when_local: str,
                  tile_parts: dict | None, tz: str) -> str:
    doc = _tpl("cancel")
    doc = _sub(doc, "Elena Martín", _e(name))
    doc = _sub(doc, "Termin abgesagt · Dienstag, 15. September 2026 · 10:00 (Europe/Madrid)",
               {"de": "Termin abgesagt", "en": "Appointment cancelled",
                "es": "Cita cancelada"}[lang])
    doc = _sub(doc, "Dienstag, 15. September 2026 · 10:00 (Europe/Madrid)", _e(when_local))
    doc = tile(doc, tile_parts, lang) if tile_parts else _tile_fallback(doc, when_local)
    doc = _sub(doc, "Europe/Madrid", _e(tz), required=False)
    rows = [
        ("Termin abgesagt", "Appointment cancelled", "Cita cancelada"),
        ("Unser Termin", "Our appointment", "Nuestra cita"),
        (">entfällt", ">is cancelled", ">queda cancelada"),
        ("Hallo ", "Hi ", "Hola "),
        ("unser Termin am ", "our call on ", "nuestra sesión del "),
        (" entfällt.", " is cancelled.", " queda cancelada."),
        ("Entfällt", "Cancelled", "Cancelada"),
        ("Termin<", "Appointment<", "Cita<"),
        ("Die angehängte Absage entfernt den Termin automatisch aus deinem Kalender.",
         "The attached cancellation removes it from your calendar automatically.",
         "La anulación adjunta la elimina automáticamente de tu calendario."),
        ("Wenn du magst, finden wir gemeinsam einen neuen Termin — antworte einfach "
         "auf diese E-Mail.",
         "If you like, we'll find a new time together — simply reply to this email.",
         "Si quieres, buscamos juntas una nueva fecha — basta con responder a este correo."),
        ("Herzlich,", "Warmly,", "Un abrazo,"),
    ]
    return _pack(doc, lang, rows)


def render_creds(name: str, lang: str, cid: str, password: str,
                 magic_link: str, portal_url: str) -> str:
    doc = _tpl("creds")
    doc = _sub(doc, "Elena Martín", _e(name))
    # the button signs in directly; the visible address stays the plain portal
    doc = re.sub(r'(class="btn" href=")[^"]*(")',
                 lambda m: m.group(1) + _e(magic_link or portal_url) + m.group(2),
                 doc, count=1)
    doc = _sub(doc, "https://api.auralisnatura.com/portal", _e(portal_url))
    doc = _sub(doc, "AN-0042", _e(cid))
    doc = _sub(doc, "Kf7pQr2mXw", _e(password))
    rows = [
        ("Dein Zugang zum Auralis-Natura-Portal", "Your access to the Auralis Natura portal",
         "Tu acceso al portal de Auralis Natura"),
        ("Dein Portal", "Your portal", "Tu portal"),
        ("Dein Zugang zum", "Your access to your", "Tu acceso a tu"),
        ("Klienten-Portal", "client portal", "portal de cliente"),
        ("Hallo ", "Hi ", "Hola "),
        ("hier ist dein persönlicher Zugang zu deinem geschützten Klienten-Portal — "
         "und darin dein Fragebogen.",
         "here is your personal access to your protected client portal — and to your "
         "questionnaire inside it.",
         "aquí tienes tu acceso personal a tu portal de cliente protegido — y dentro, "
         "tu cuestionario."),
        ("Dein Fragebogen", "Your questionnaire", "Tu cuestionario"),
        ("ca. 15 Minuten", "about 15 minutes", "unos 15 minutos"),
        ("speichert automatisch", "saves automatically", "se guarda solo"),
        ("jederzeit pausierbar", "pause any time", "pausable en todo momento"),
        ("Du kannst jetzt schon in Ruhe damit anfangen — und jederzeit pausieren und "
         "später weitermachen.",
         "You can make a start whenever it suits you — and pause and pick it up again "
         "at any time.",
         "Puedes empezar cuando te venga bien — y pausarlo y retomarlo cuando quieras."),
        ("Und falls es zeitlich nicht klappt: kein Problem. Dann gehen wir ihn im "
         "Erstgespräch gemeinsam durch.",
         "And if you don't get to it: no problem at all. We'll go through it together "
         "in our first call.",
         "Y si no te da tiempo: no pasa nada. Lo repasamos juntas en nuestra primera "
         "llamada."),
        ("Fragebogen öffnen", "Open my questionnaire", "Abrir mi cuestionario"),
        ("Ein Klick — kein Passwort nötig.", "One click — no password needed.",
         "Un clic — sin contraseña."),
        ("Oder von Hand anmelden", "Or sign in manually", "O inicia sesión a mano"),
        ("Login-ID", "Login ID", "ID de acceso"),
        ("Passwort", "Password", "Contraseña"),
        ("Portal-Adresse", "Portal address", "Dirección del portal"),
        ("Der Button meldet dich direkt an. ID und Passwort brauchst du nur, wenn du "
         "dich später von einem anderen Gerät anmeldest — bewahre sie gut auf.",
         "The button signs you in directly. You only need the ID and password if you "
         "sign in later from another device — keep them somewhere safe.",
         "El botón te identifica directamente. Solo necesitas el ID y la contraseña si "
         "entras más adelante desde otro dispositivo — guárdalos bien."),
        ("Bis bald,", "See you soon,", "Hasta pronto,"),
    ]
    return _pack(doc, lang, rows)


def render_sessions(name: str, lang: str, prog: str,
                    rows_data: list[tuple[str, str, int]], unit: str) -> str:
    """rows_data: (label, when_text, minutes) per session, already localised."""
    doc = _tpl("sessions")
    doc = _sub(doc, "Elena Martín", _e(name))
    doc = _sub(doc, "Wandel", _e(prog))
    # regenerate the timeline from the first sample row
    m = re.search(r'<div class="it"[^>]*>.*?</div>\s*</div>\s*</div>', doc, re.S)
    pattern = m.group(0)
    def row(label, when, mins):
        r = pattern
        r = re.sub(r'(class="tt"[^>]*>)(?:(?!<span).)*',
                   lambda x: x.group(1) + _e(label), r, count=1, flags=re.S)
        r = re.sub(r'(class="dur"[^>]*>)[^<]*', lambda x: x.group(1) + f"{mins} {_e(unit)}", r, count=1)
        r = re.sub(r'(class="tm2"[^>]*>).*?(</div>)',
                   lambda x: x.group(1) + _e(when) + x.group(2), r, count=1, flags=re.S)
        return r
    rows_html = "".join(row(*r) for r in rows_data)
    # splice: replace everything between the timeline open and its close
    tl = re.search(r'(<div class="tl"[^>]*>).*?(</div>\s*<p)', doc, re.S)
    doc = doc[:tl.start()] + tl.group(1) + rows_html + "</div><p" + doc[tl.end():]
    rows = [
        ("Deine Termine · ", "Your programme dates · ", "Tus citas · "),
        ("Programm · ", "Programme · ", "Programa · "),
        ("Deine Termine —", "Your dates —", "Tus citas —"),
        ("alle auf einen Blick", "all at a glance", "todas de un vistazo"),
        ("Hallo ", "Hi ", "Hola "),
        ("hier sind die Termine für unsere gemeinsamen Gespräche in deinem Programm",
         "here are the dates for our calls in your programme",
         "aquí tienes las fechas de nuestras sesiones en tu programa"),
        ("— und als Kalender-Einladung angehängt: einmal annehmen, und alle stehen in "
         "deinem Kalender.",
         "— attached as one calendar invitation: accept once and every call lands in "
         "your calendar.",
         "— adjuntas como una invitación de calendario: acéptala una vez y todas "
         "quedarán en tu calendario."),
        ("Den Link zum Videogespräch schicke ich dir rechtzeitig vor jedem Termin.",
         "I will send you the video link in good time before each call.",
         "Te enviaré el enlace de vídeo con tiempo antes de cada sesión."),
        ("Wenn dir ein Termin nicht passt, antworte einfach auf diese E-Mail — wir "
         "verschieben ihn gemeinsam.",
         "If a date doesn't suit you, simply reply to this email — we'll move it together.",
         "Si alguna fecha no te viene bien, responde a este correo — la movemos juntas."),
        ("Ich freue mich auf unseren Weg,", "Looking forward to our journey,",
         "Con ganas de empezar este camino,"),
    ]
    return _pack(doc, lang, rows)


def render_report(name: str, lang: str, booking_url: str, pages: int | None) -> str:
    doc = _tpl("report")
    doc = _sub(doc, "Elena Martín", _e(name))
    doc = re.sub(r'(class="btn" href=")[^"]*(")',
                 lambda m: m.group(1) + _e(booking_url) + m.group(2), doc, count=1)
    doc = _sub(doc, "https://api.auralisnatura.com/book", _e(booking_url))
    meta = {
        "de": (f"A4 · {pages} Seiten · persönlich erstellt · im Anhang" if pages
               else "A4 · persönlich erstellt · im Anhang"),
        "en": (f"A4 · {pages} pages · personally prepared · attached" if pages
               else "A4 · personally prepared · attached"),
        "es": (f"A4 · {pages} páginas · elaborado personalmente · adjunto" if pages
               else "A4 · elaborado personalmente · adjunto"),
    }[lang]
    doc = _sub(doc, "A4 · 12 Seiten · persönlich erstellt · im Anhang", _e(meta))
    rows = [
        ("Dein persönlicher Auralis-Natura-Bericht", "Your personal Auralis Natura report",
         "Tu informe personal de Auralis Natura"),
        ("Dein Bericht", "Your report", "Tu informe"),
        ("Dein persönlicher", "Your personal", "Tu informe"),
        (">Bericht<", ">report<", ">personal<"),
        ("ist da.", "is here.", "está listo."),
        ("Hallo ", "Hi ", "Hola "),
        ("dein persönlicher Auralis-Natura-Bericht ist angehängt. Er bringt zusammen, "
         "was dein Aufnahmebogen gezeigt hat, und 2–3 machbare erste Schritte.",
         "your personal Auralis Natura report is attached. It brings together what "
         "your intake revealed and 2–3 realistic first steps.",
         "adjunto tu informe personal de Auralis Natura. Reúne lo que mostró tu "
         "cuestionario y 2–3 primeros pasos realizables."),
        ("Persönlicher Gesundheitsbericht", "Personal holistic health report",
         "Informe personal de salud holística"),
        ("Wähle hier eine Zeit für unser Besprechungsgespräch:",
         "Book a time to talk it through here:",
         "Reserva aquí un momento para comentarlo:"),
        ("Termin wählen", "Choose a time", "Elegir un momento"),
        ("Herzlich,", "Warmly,", "Un saludo,"),
    ]
    return _pack(doc, lang, rows)


def render_feedback(name: str, lang: str) -> str:
    doc = _tpl("feedback")
    doc = _sub(doc, "Elena Martín", _e(name))
    rows = [
        ("Wie war deine Zeit mit Auralis Natura?", "How was your time with Auralis Natura?",
         "¿Cómo fue tu tiempo con Auralis Natura?"),
        ("Zum Abschluss", "As we close", "Para terminar"),
        ("Wie war deine Zeit mit", "How was your time with", "¿Cómo fue tu tiempo con"),
        ("Hallo ", "Hi ", "Hola "),
        ("dein Programm ist abgeschlossen — danke für dein Vertrauen und deine "
         "Offenheit. Es war mir eine Freude, dich zu begleiten.",
         "your programme is complete — thank you for your trust and openness. It was "
         "a joy to accompany you.",
         "tu programa ha terminado — gracias por tu confianza y tu apertura. Ha sido "
         "un placer acompañarte."),
        ("Zwei kleine Bitten", "Two small favours", "Dos pequeños favores"),
        ("Antworte mir in zwei, drei Sätzen — was hat dir geholfen, was hätte besser "
         "sein können?",
         "Reply in two or three sentences — what helped, what could be better?",
         "Respóndeme en dos o tres frases — ¿qué te ayudó, qué podría mejorar?"),
        ("Und wenn du magst: Dürfte ich einen Satz davon (mit Vornamen) als Stimme "
         "auf der Website zeigen?",
         "And if you like: may I show one sentence (first name only) as a voice on "
         "the website?",
         "Y si quieres: ¿podría mostrar una frase (con tu nombre de pila) como "
         "testimonio en la web?"),
        ("Von Herzen,", "Warmly,", "Con cariño,"),
    ]
    return _pack(doc, lang, rows)


def render_newsletter(subject: str, body_text: str, kicker: str = "Impulse") -> str:
    """Newsletter goes out in the language it was written in — the console
    composes it, so no pack; the sample copy is fully replaced. The same shell
    carries the one-off personal mail, with its own kicker."""
    doc = _tpl("newsletter")
    doc = _sub(doc, "Drei Impulse für deinen Spätsommer", _e(subject))
    doc = _sub(doc, "Impulse · Spätsommer", _e(kicker))
    # headline: split "Drei Impulse für deinen" / "Spätsommer"
    words = subject.split()
    head, em = (" ".join(words[:-1]), words[-1]) if len(words) > 1 else (subject, "")
    doc = _sub(doc, "Drei Impulse für deinen", _e(head))
    doc = _sub(doc, "Spätsommer", _e(em) if em else "")
    paras = [p.strip() for p in (body_text or "").split("\n\n") if p.strip()]
    body_html = "".join(
        f'<p style="margin:0 0 16px;font-size:15px;line-height:1.7;color:#5C4A3A">'
        f'{_e(p).replace(chr(10), "<br>")}</p>' for p in paras)
    doc = _sub(doc, "zwischen Urlaub und Alltag liegt oft eine Woche, in der alles "
               "wieder in den alten Rhythmus rutscht. Drei kleine Dinge, die dabei "
               "helfen, das Gute mitzunehmen …", "</p>" + body_html + "<p>")
    return doc


# ---------------------------------------------------------------- internal (DE)

def render_briefing(first: str, last: str, when_compact: str, tz: str,
                    lang_label: str, email: str, goal: str,
                    kv_rows: list[tuple[str, str, bool]],
                    scales: list[tuple[str, int]], booking_id: str,
                    flags: str = "") -> str:
    doc = _tpl("briefing")
    doc = _sub(doc, "Neue Buchung · Elena Martín · Mittwoch, 26. August 2026",
               f"Neue Buchung · {_e(first)} {_e(last)} · {_e(when_compact)}")
    doc = _sub(doc, "Elena Martín", f"{_e(first)} {_e(last)}", required=False)
    doc = _sub(doc, ">Elena <em", ">" + _e(first) + " <em")
    doc = _sub(doc, "Martín</em>", _e(last) + "</em>")
    doc = _sub(doc, "Mi 26.08.2026 · 10:05", _e(when_compact))
    doc = _sub(doc, "Europe/Madrid", _e(tz))
    doc = _sub(doc, "Deutsch", _e(lang_label))
    doc = _sub(doc, "elena.martin@example.com", _e(email))
    if goal:
        doc = _sub(doc, "Wieder Energie für meinen Alltag finden — ich bin seit "
                   "Monaten erschöpft, obwohl ich genug schlafe.", _e(goal))
    else:
        doc = re.sub(r'<div class="pull"[^>]*>.*?</div>\s*', "", doc, flags=re.S)
    # Red flags open the mail, above everything else — section 2: a red flag
    # changes what the first sentence of the call has to be. The v2 handoff
    # dropped this box; it is reinstated here because it is safety, not style.
    if flags:
        box = ('<div style="margin:0 0 20px;padding:14px 16px;background:#FBEDE8;'
               'border-left:3px solid #A8492A">'
               '<p style="margin:0 0 4px;font-size:12px;letter-spacing:.12em;'
               'text-transform:uppercase;color:#A8492A;font-weight:700">Sicherheitsfrage</p>'
               f'<p style="margin:0;font-size:14px;line-height:1.55;color:#281F16">{_e(flags)}</p>'
               '<p style="margin:6px 0 0;font-size:12px;color:#5C4A3A">'
               'Vor dem Gespräch ansehen — ärztliche Abklärung zuerst ansprechen.</p></div>')
        doc = doc.replace('<div class="kv"', box + '<div class="kv"', 1)
    # kv rows regenerated from the template's own row
    m = re.search(r'<div class="row"[^>]*>.*?</div>\s*</div>', doc, re.S)
    pattern = m.group(0)
    def kv(k, v, strong):
        r = re.sub(r'(class="k"[^>]*>)[^<]*', lambda x: x.group(1) + _e(k), pattern, count=1)
        vv = _e(v)
        if strong:
            vv = f"<b>{vv}</b>"
        return re.sub(r'(class="v"[^>]*>)[^<]*', lambda x: x.group(1) + vv, r, count=1)
    rows_html = "".join(kv(k, v, s) for k, v, s in kv_rows if v)
    kvm = re.search(r'(<div class="kv"[^>]*>).*?(</div>\s*<div class="box)', doc, re.S)
    doc = doc[:kvm.start()] + kvm.group(1) + rows_html + '</div><div class="box' + doc[kvm.end():]
    # the self-rating scales
    sm = re.search(r'<div class="scale[^"]*"[^>]*>.*?</span>\s*</div>', doc, re.S)
    spat = sm.group(0)
    def scale(label, val):
        r = spat
        r = r.replace('class="scale low"', f'class="scale{" low" if val <= 2 else ""}"')
        r = re.sub(r'(class="sl"[^>]*>)[^<]*', lambda x: x.group(1) + _e(label), r, count=1)
        segs = re.search(r'(<span class="segs"[^>]*>).*?(</span>)', r, re.S)
        i_on = re.search(r'<i class="on"[^>]*></i>', r).group(0)
        i_off = re.search(r'<i (?:style|)[^>]*></i>(?!</)', r.replace(i_on, "")) or None
        off_m = re.findall(r'<i(?! class="on")[^>]*></i>', r)
        cells = i_on * val + (off_m[0] if off_m else "<i></i>") * (5 - val)
        r = r[:segs.start()] + segs.group(1) + cells + segs.group(2) + r[segs.end():]
        r = re.sub(r'(class="sv"[^>]*>)(\s*<b[^>]*>)[^<]*(</b>)',
                   lambda x: x.group(1) + x.group(2) + str(val) + x.group(3), r, count=1)
        return r
    scales_html = "".join(scale(l, max(1, min(5, int(v)))) for l, v in scales)
    scm = re.search(r'(<div class="scales"[^>]*>).*?(</div>\s*</div>)', doc, re.S)
    doc = doc[:scm.start()] + scm.group(1) + scales_html + scm.group(2) + doc[scm.end():]
    doc = _sub(doc, "BK-MUSTER", _e(booking_id or "—"))
    doc = _sub(doc, "34 Jahre", "", required=False)   # sample age lives in kv now
    return doc


def render_social(week: str, slots: list[dict]) -> str:
    doc = _tpl("social")
    start = doc.index('<div class="slot"')
    end = doc.index('<p class="quiet"', start)
    pattern = doc[start:end]
    lang_m = re.search(r'<div class="lang"[^>]*>.*?</div>\s*</div>', pattern, re.S)
    lang_pat = lang_m.group(0)
    hm = re.search(r'<div class="hash"[^>]*>(.*?)</div>', pattern, re.S)
    hash_container, hash_inner = hm.group(0), hm.group(1)
    span_pat = re.search(r"<span[^>]*>[^<]*</span>", hash_inner).group(0)

    def one(s):
        r = pattern
        r = re.sub(r'(class="cap"[^>]*><b[^>]*>)[^<]*(</b>)',
                   lambda x: x.group(1) + _e(f'{s.get("id","")} · {s.get("kind","post").capitalize()}') + x.group(2),
                   r, count=1)
        r = re.sub(r'(</b><span[^>]*>)[^<]*(</span>)',
                   lambda x: x.group(1) + _e(f'{s.get("day","")} {s.get("time","")}') + x.group(2),
                   r, count=1)
        r = re.sub(r'(class="big"[^>]*>)[^<]*', lambda x: x.group(1) + _e(s.get("hook", "")), r, count=1)
        # language blocks: only the ones with copy
        blocks = []
        for code in ("de", "en", "es"):
            cap = (s.get(f"caption_{code}") or "").strip()
            if not cap:
                continue
            ps = "".join(f"<p style=\"margin:0 0 8px;font-size:13px;line-height:1.6;"
                         f"color:#5C4A3A\">{_e(p)}</p>"
                         for p in cap.split("\n\n") if p.strip())
            b = re.sub(r'(class="lc"[^>]*>)[^<]*', lambda x: x.group(1) + code.upper(), lang_pat, count=1)
            b = re.sub(r'(<div>).*?(</div>)\s*</div>$', lambda x: x.group(1) + ps + x.group(2) + "</div>",
                       b, count=1, flags=re.S)
            blocks.append(b)
        li = r.index('<div class="lang"')
        hi = r.index('<div class="hash"')
        r = r[:li] + "".join(blocks) + r[hi:]
        tags = "".join(re.sub(r">[^<]*<", ">" + _e(t) + "<", span_pat)
                       for t in (s.get("hashtags") or []))
        r = r.replace(hash_container,
                      hash_container.replace(hash_inner, tags) if tags else "", 1)
        alt = (s.get("alt_text") or "").strip()
        r = re.sub(r'(class="alt"[^>]*>.*?</b>\s*)[^<]*',
                   lambda x: x.group(1) + _e(alt), r, count=1, flags=re.S)
        return r

    slots_html = "".join(one(s) for s in slots)
    doc = doc[:start] + slots_html + doc[end:]
    n = len(slots)
    doc = _sub(doc, "Social-Wochenpaket · 2026-W35 · 1 Post",
               f"Social-Wochenpaket · {_e(week)} · {n} Post{'s' if n != 1 else ''}")
    doc = _sub(doc, "2026-W35", _e(week), required=False)
    doc = _sub(doc, "2026–W35", _e(week), required=False)
    doc = _sub(doc, "Woche 35", "Woche " + _e(week.split("W")[-1] if "W" in week else week),
               required=False)
    doc = _sub(doc, "1 Slot", f"{n} Slot{'s' if n != 1 else ''}", required=False)
    return doc
