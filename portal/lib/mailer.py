"""Build and deliver the report email.

Modes (config.email_mode):
- "off"   : write the finished .eml to output_docs (audit trail). Default for dev.
- "draft" : APPEND the finished mail to the Gmail Drafts folder over IMAP, so
            Desiree reviews and sends it herself (the recommended production mode).
- "send"  : send immediately over SMTP.

Either way the mail is branded (seal header), attaches the report PDF, and carries
the review-call booking link. Nothing here bypasses the human step: in "draft"
mode Desiree still clicks Send.
"""
from __future__ import annotations
import os, smtplib, imaplib, time, html
from email.message import EmailMessage
from email.utils import formatdate, make_msgid
from pathlib import Path
from . import cfg


def _stamp(msg: EmailMessage, key: str = "") -> EmailMessage:
    """Give the message a Date and a Message-ID before it leaves the building.

    Both matter more than they look:

    * smtplib.send_message() adds a Date for us, but an IMAP APPEND does not —
      so every draft Desiree reviewed so far had NO Date header at all. A
      dateless message is one of the oldest spam heuristics there is, and Yahoo
      still weights it. Setting it here fixes the drafts too.
    * A stable Message-ID keyed to the booking means re-running the same
      delivery cannot produce a second, subtly different draft: it is the same
      message, and every sane client collapses it.

    The domain must be the SENDING domain (auralisnatura.com), never the
    machine's hostname — a Message-ID whose domain does not resolve is another
    small spam signal, and Python's default uses the local hostname.
    """
    dom = (cfg.config().get("from_email", "") or "@auralisnatura.com").split("@")[-1] \
          or "auralisnatura.com"
    if not msg["Date"]:
        msg["Date"] = formatdate(localtime=True)
    if not msg["Message-ID"]:
        msg["Message-ID"] = f"<{key}@{dom}>" if key else make_msgid(domain=dom)
    return msg

_GREETING = {
    "de": ("Hallo {name},", "dein persönlicher Auralis-Natura-Bericht ist angehängt. Er bringt zusammen, "
           "was dein Aufnahmebogen gezeigt hat, und 2–3 machbare erste Schritte.",
           "Wähle hier eine Zeit für unser Besprechungsgespräch:", "Herzlich,"),
    "es": ("Hola {name}:", "adjunto tu informe personal de Auralis Natura. Reúne lo que mostró tu cuestionario "
           "y 2–3 primeros pasos realizables.",
           "Reserva aquí un momento para comentarlo:", "Un saludo,"),
    "en": ("Hi {name},", "your personal Auralis Natura report is attached. It brings together what your intake "
           "revealed and 2–3 realistic first steps.",
           "Book a time to talk it through here:", "Warmly,"),
}


def build_email(to_email: str, client_name: str, pdf_path: Path, language: str = "en") -> EmailMessage:
    co = cfg.company()
    c = cfg.config()
    lang = language if language in _GREETING else "en"
    g1, g2, g3, g4 = _GREETING[lang]
    booking = c.get("booking_review_url", "")
    subj = {"de": "Dein persönlicher Auralis-Natura-Bericht",
            "es": "Tu informe personal de Auralis Natura",
            "en": "Your personal Auralis Natura report"}[lang]

    msg = EmailMessage()
    msg["Subject"] = subj
    msg["From"] = f'{c.get("from_name","Auralis Natura")} <{c.get("from_email","")}>'
    msg["To"] = to_email
    text = (f'{g1.format(name=client_name)}\n\n{g2}\n\n{g3}\n{booking}\n\n{g4}\nDesiree\n\n'
            f'{co.get("brand","Auralis Natura")} · {co.get("email","")} · {co.get("phone","")}')
    msg.set_content(text)

    have_seal = (cfg.ASSETS_DIR / "logo-lockup-email.png").exists() or (cfg.ASSETS_DIR / "seal.png").exists()
    seal_img = ('<img src="cid:auralislogo" width="176" alt="Auralis Natura" style="display:block;margin:0 auto;width:176px;max-width:60%;height:auto;border:0">'
                if have_seal else "")
    body_html = _HTML.format(
        seal=seal_img, g1=html.escape(g1.format(name=client_name)), g2=html.escape(g2),
        g3=html.escape(g3), booking=html.escape(booking), g4=html.escape(g4),
        owner=html.escape(co.get("owner", "")), brand=html.escape(co.get("brand", "")),
        contact=html.escape(f'{co.get("email","")} · {co.get("phone","")}'),
        disc=_disc(lang),
    )
    msg.add_alternative(body_html, subtype="html")
    if have_seal:
        _inline_seal(msg)

    if pdf_path and Path(pdf_path).exists():
        data = Path(pdf_path).read_bytes()
        maintype, subtype = ("application", "pdf") if str(pdf_path).endswith(".pdf") else ("text", "html")
        msg.add_attachment(data, maintype=maintype, subtype=subtype,
                           filename=f"Auralis-Report-{_safe(client_name)}.{'pdf' if subtype=='pdf' else 'html'}")
    return _stamp(msg)


def deliver(msg: EmailMessage, client_id: str) -> dict:
    _stamp(msg)
    mode = cfg.config().get("email_mode", "off")
    outbox = cfg.OUTPUT_DIR / client_id / "sent"
    outbox.mkdir(parents=True, exist_ok=True)
    eml_path = outbox / f"report-{int(time.time())}.eml"
    eml_path.write_bytes(bytes(msg))
    result = {"mode": mode, "eml": str(eml_path)}
    if mode == "draft":
        result.update(_imap_draft(msg))
    elif mode == "send":
        result.update(_smtp_send(msg))
    return result


def drafts_mailbox(M) -> str:
    """The IMAP name of the Drafts folder on THIS account, quoted for APPEND.

    Not a constant. Gmail localises its system folders: on a German-language
    account the drafts folder is '[Gmail]/Entwürfe' (IMAP-UTF-7:
    '[Gmail]/Entw&APw-rfe'), on a Spanish one '[Gmail]/Borradores'. Appending to
    a hardcoded '[Gmail]/Drafts' there raises, _imap_draft() catches it, and the
    report mail is lost with nothing but a string in a dict to show for it.

    RFC 6154 solves this properly: the server flags the folder \\Drafts in its
    LIST response, whatever it is called. Find it by the flag, and only fall
    back to guessing if the server does not advertise one.
    """
    try:
        typ, data = M.list()
    except Exception:
        typ, data = "NO", []
    if typ == "OK":
        for raw in data or []:
            line = raw.decode("utf-8", "replace") if isinstance(raw, (bytes, bytearray)) else str(raw)
            # (\HasNoChildren \Drafts) "/" "[Gmail]/Entw&APw-rfe"
            if "\\Drafts" not in line:
                continue
            # The mailbox name is the last space-separated token, usually quoted.
            name = line.rsplit(" ", 1)[-1].strip()
            if name.startswith('"') and name.endswith('"'):
                return name              # already quoted, keep it verbatim
            return '"%s"' % name
    return '"[Gmail]/Drafts"'            # the common case, and a sane last resort


def _imap_draft(msg: EmailMessage) -> dict:
    c = cfg.config()
    pw = os.environ.get("AURALIS_SMTP_PASSWORD", c.get("smtp_password", ""))
    if not pw:
        return {"draft": "skipped — no AURALIS_SMTP_PASSWORD set"}
    try:
        M = imaplib.IMAP4_SSL(c.get("imap_host", "imap.gmail.com"), int(c.get("imap_port", 993)))
        M.login(c.get("smtp_user", ""), pw)
        box = drafts_mailbox(M)
        # (\Draft), not "". Appending to the Drafts folder without the flag
        # leaves Gmail an ordinary message that merely happens to be labelled
        # Drafts; its own draft-sync then wraps it in a draft object, and some
        # clients (Gmail on iOS among them) list both — one booking, two drafts.
        # The flag says outright what this is, so exactly one appears.
        M.append(box, r"(\Draft)", imaplib.Time2Internaldate(time.time()), bytes(msg))
        M.logout()
        return {"draft": f"uploaded to {box.strip(chr(34))}"}
    except Exception as e:  # pragma: no cover
        return {"draft": f"failed: {e}"}


def _smtp_send(msg: EmailMessage) -> dict:
    c = cfg.config()
    pw = os.environ.get("AURALIS_SMTP_PASSWORD", c.get("smtp_password", ""))
    if not pw:
        return {"send": "skipped — no AURALIS_SMTP_PASSWORD set"}
    try:
        s = smtplib.SMTP(c.get("smtp_host", "smtp.gmail.com"), int(c.get("smtp_port", 587)))
        s.starttls(); s.login(c.get("smtp_user", ""), pw); s.send_message(msg); s.quit()
        return {"send": "sent"}
    except Exception as e:  # pragma: no cover
        return {"send": f"failed: {e}"}


def _safe(name: str) -> str:
    return "".join(ch for ch in (name or "client") if ch.isalnum() or ch in "-_") or "client"


def _disc(lang: str) -> str:
    return {
        # Same wording as /book, so a client does not meet two different
        # disclaimers from the same practice on the same day.
        "de": "Auralis Natura bietet Gesundheitscoaching und Gesundheitsbildung, keine medizinische Diagnose oder Therapie.",
        "es": "Auralis Natura ofrece coaching y educación en salud, no diagnóstico ni tratamiento médico.",
        "en": "Auralis Natura offers health coaching and health education, not medical diagnosis or treatment.",
    }[lang]


_HTML = """<div style="margin:0;padding:28px 20px 40px;background:#F5EEE0">
<div style="max-width:560px;margin:0 auto;font-family:'Hanken Grotesk','Helvetica Neue',Arial,sans-serif;font-size:16px;line-height:1.62;color:#5C4A3A">
<div style="text-align:center;padding:0 0 18px">{seal}</div>
<p style="margin:0 0 14px;color:#281F16">{g1}</p><p style="margin:0 0 18px">{g2}</p>
<p style="margin:0 0 18px">{g3}<br><a href="{booking}" style="color:#A8492A">{booking}</a></p>
<p style="margin:0">{g4}<br><span style="font-family:Fraunces,Georgia,serif;font-size:19px;color:#281F16">Desiree</span></p>
<p style="margin:22px 0 0;padding-top:14px;border-top:1px solid #DCD2C2;font-size:12px;line-height:1.6;color:#75685A">{owner} · {brand}<br>{contact}<br>{disc}</p>
</div></div>"""


_BOOKING = {
    "de": ("Dein Termin ist bestätigt", "Hallo {name},",
           "dein kostenloses Kennenlerngespräch ist bestätigt für:",
           "Du erhältst den Link unten — füge den Termin mit der angehängten Einladung zu deinem Kalender hinzu.",
           "Bis bald,"),
    "es": ("Tu cita está confirmada", "Hola {name}:",
           "tu llamada gratuita de presentación está confirmada para:",
           "Encontrarás el enlace abajo — añade la cita a tu calendario con la invitación adjunta.",
           "Hasta pronto,"),
    "en": ("Your call is confirmed", "Hi {name},",
           "your free introductory call is confirmed for:",
           "You'll find the link below — add it to your calendar with the attached invite.",
           "See you soon,"),
}




_PREP = {
 "de": ("So läuft unser Gespräch",
        ["Der Link öffnet sich direkt im Browser — du musst nichts installieren.",
         "Such dir einen ruhigen Ort und Kopfhörer, wenn du welche hast.",
         "Leg dir bereit, was dir wichtig ist: Fragen, Befunde, Notizen — nichts davon ist Pflicht."],
        "Wir schauen gemeinsam, wo du gerade stehst, was du dir wünschst und "
        "welcher nächste Schritt für dich sinnvoll ist. Kein Verkaufsgespräch, "
        "keine Vorbereitung nötig.",
        "Wenn dir etwas dazwischenkommt, antworte einfach auf diese E-Mail — "
        "eine Absage ist jederzeit in Ordnung.",
        "Dr. rer. nat. Desiree Gruber · promoviert in Chemie · "
        "über fünfzehn Jahre in Forschung und pharmazeutischer Industrie · "
        "zertifiziert in ganzheitlicher Gesundheit, Ernährung und Frauengesundheit"),
 "en": ("How our conversation works",
        ["The link opens straight in your browser — nothing to install.",
         "Find a quiet spot, and headphones if you have them.",
         "Bring whatever matters to you: questions, results, notes — none of it required."],
        "Together we look at where you are right now, what you are hoping for and "
        "which next step makes sense for you. Not a sales call, and nothing to prepare.",
        "If something comes up, just reply to this email — cancelling is always fine.",
        "Dr. rer. nat. Desiree Gruber · doctorate in chemistry · "
        "over fifteen years in research and the pharmaceutical industry · "
        "certified in holistic health, nutrition and women's health"),
 "es": ("Cómo será nuestra conversación",
        ["El enlace se abre directamente en el navegador — no hay que instalar nada.",
         "Busca un lugar tranquilo y auriculares, si tienes.",
         "Trae lo que te importe: preguntas, informes, notas — nada es obligatorio."],
        "Miramos juntas dónde estás ahora, qué deseas y cuál es el siguiente paso "
        "que tiene sentido para ti. No es una llamada de venta y no hay que preparar nada.",
        "Si te surge algo, responde a este correo — cancelar siempre está bien.",
        "Dr. rer. nat. Desiree Gruber · doctorada en química · "
        "más de quince años en investigación e industria farmacéutica · "
        "certificada en salud holística, nutrición y salud femenina"),
}

def _inline_seal(msg: EmailMessage, px: int = 176) -> str:
    """Attach the LOCKUP (seal + wordmark) inline and return its cid.

    Three things this has to get right, all learned from the real thing:

    * cid, not a data: URI. Gmail strips data:-sourced <img> outright, which is
      why the header was a broken box in every mail.
    * The lockup, not the bare seal. A mark on its own reads as decoration; with
      "Auralis Natura" beside it, it reads as a letterhead.
    * width/height ATTRIBUTES are not enough. Gmail on iOS scales inline images
      up to the message width regardless, which is how a 52px seal filled the
      screen. The caller also sets an inline max-width style; both are needed.

    Rendered at 2x and displayed at px, so it stays sharp on a retina phone, and
    composited onto the mail's own paper colour — the lockup ships on near-white
    (#FDFAF6) and would otherwise sit in a faintly visible pale rectangle.
    """
    # Kept in portal/assets/ beside the code, pre-sized and pre-composited —
    # not reached for outside the package, which broke once already.
    src = cfg.ASSETS_DIR / "logo-lockup-email.png"
    if not src.exists():
        src = cfg.ASSETS_DIR / "seal.png"
    if not src.exists():
        return ""
    try:
        from PIL import Image
        import io
        im = Image.open(src).convert("RGBA")
        w2 = px * 2
        im.thumbnail((w2, w2), Image.LANCZOS)
        bg = Image.new("RGBA", im.size, (0xF5, 0xEE, 0xE0, 255))
        flat = Image.alpha_composite(bg, im).convert("RGB")
        buf = io.BytesIO(); flat.save(buf, "PNG", optimize=True)
        data = buf.getvalue()
    except Exception:
        data = src.read_bytes()
    cid = "auralislogo"
    msg.get_payload()[-1].add_related(
        data, maintype="image", subtype="png", cid=f"<{cid}>",
        filename="auralis-natura.png", disposition="inline")
    return f"cid:{cid}"


def build_booking_email(to_email: str, name: str, when_local: str, language: str,
                        ics: bytes, booking_id: str, slot_utc: str = "") -> EmailMessage:
    """Premium branded confirmation + REAL calendar invite (METHOD:REQUEST).
    team@ is in Cc, so the booking lands in the practice inbox and — thanks to
    the invite part — appears in the Google Calendar automatically."""
    co = cfg.company(); c = cfg.config()
    lang = language if language in _BOOKING else "en"
    subj, g1, g2, g3, g4 = _BOOKING[lang]
    meet = co.get("meet_link", "")
    own = c.get("from_email", "")
    msg = EmailMessage()
    msg["Subject"] = f"{subj} · {when_local}"
    msg["From"] = f'{c.get("from_name","Auralis Natura")} <{own}>'
    msg["To"] = to_email
    if own:
        msg["Cc"] = own
    jbtn, jcal, _jo, jno = _JOIN.get(lang, _JOIN["de"])
    body = (f"{g1.format(name=name)}\n\n{g2}\n\n    {when_local}\n\n{g3}\n"
            + (f"\n{jbtn}:\n{meet}\n" if meet else f"\n{jno}\n")
            + f"\n{g4}\nDesiree\n\n{co.get('brand','Auralis Natura')} · {co.get('email','')} · {co.get('phone','')}\n{_disc(lang)}")
    msg.set_content(body.replace("&amp;", "&"))
    cal_note = {"de": "Der Termin ist reserviert. Trag ihn dir mit einem Klick ein:",
                "es": "La cita está reservada. Añádela con un clic:",
                "en": "The time is reserved. Add it with one click:"}[lang]
    tlabel = {"de": "Dein Termin", "es": "Tu cita", "en": "Your call"}[lang]
    ph, plist, pintro, pmove, creds = _PREP[lang]
    rows = "".join(
        f'<tr><td style="padding:4px 10px 4px 0;vertical-align:top;color:#A8492A">&#8226;</td>'
        f'<td style="padding:4px 0;vertical-align:top;font-size:15px;line-height:1.55">'
        f'{html.escape(x)}</td></tr>' for x in plist)
    # The cid goes into the markup BEFORE the part exists — add_related() turns
    # the html part into a multipart/related, so rewriting it afterwards means
    # reaching into the wrong node (and raises KeyError: multipart/related).
    have_seal = (cfg.ASSETS_DIR / "logo-lockup-email.png").exists() or (cfg.ASSETS_DIR / "seal.png").exists()
    seal_img = ('<img src="cid:auralislogo" width="176" alt="Auralis Natura" style="display:block;margin:0 auto;width:176px;max-width:60%;height:auto;border:0">'
                if have_seal else "")
    msg.add_alternative(_BOOK_HTML.format(
        seal=seal_img, g1=html.escape(g1.format(name=name)), g2=html.escape(g2),
        tlabel=html.escape(tlabel), when=html.escape(when_local),
        cal=html.escape(cal_note),
        meetrow=_join_block(lang, slot_utc, name),
        ph=html.escape(ph), pintro=html.escape(pintro), plist=rows,
        pmove=html.escape(pmove), creds=html.escape(creds),
        g4=html.escape(g4), owner=html.escape(co.get("owner", "")),
        brand=html.escape(co.get("brand", "")),
        contact=html.escape(f'{co.get("email","")} · {co.get("phone","")}'), disc=_disc(lang),
    ), subtype="html")
    if have_seal:
        _inline_seal(msg)
    # text/calendar with method=REQUEST inline -> Gmail renders the event card
    msg.add_attachment(ics, maintype="text", subtype="calendar",
                       filename="einladung.ics")
    for part in msg.walk():
        if part.get_content_type() == "text/calendar":
            part.set_param("method", "REQUEST")
            part.set_param("charset", "UTF-8")
    return _stamp(msg, f"confirm-{booking_id}" if booking_id else "")


_JOIN = {
    "de": ("Zum Gespräch (Google Meet)", "In den Kalender eintragen",
           "Apple / andere (.ics im Anhang)",
           "Den Link zum Videogespräch schicke ich dir rechtzeitig vor unserem Termin."),
    "en": ("Join the call (Google Meet)", "Add it to your calendar",
           "Apple / other (.ics attached)",
           "I will send you the video link in good time before our call."),
    "es": ("Unirse a la llamada (Google Meet)", "Añadir a tu calendario",
           "Apple / otros (.ics adjunto)",
           "Te enviaré el enlace de vídeo con tiempo antes de nuestra cita."),
}


def _join_block(lang: str, slot_utc: str = "", client_name: str = "") -> str:
    """The join link and the add-to-calendar row — the two things the client
    actually needs, both one tap away.

    Written as its own block because the confirmation and the reminder both
    need exactly this, and because the link belongs in the BODY of the mail:
    burying it in an .ics attachment ("super difficult to add the ics file")
    hides the one thing the mail exists to deliver. The raw URL is printed
    under the button as well — a button is a dead end when the client is
    reading in a client that strips styling, or wants to paste it elsewhere.
    """
    from . import booking as _b
    e = html.escape
    meet = cfg.company().get("meet_link", "")
    btn, calhead, other, nolink = _JOIN.get(lang, _JOIN["de"])

    if meet:
        top = (f'<p style="margin:0 0 8px;text-align:center">'
               f'<a href="{e(meet)}" style="background:#A8492A;color:#FBF3EC;text-decoration:none;'
               f'padding:15px 30px;font-weight:600;font-size:16px;display:inline-block">'
               f'{e(btn)} &#8594;</a></p>'
               f'<p style="margin:0 0 22px;text-align:center;font-size:13px;line-height:1.5">'
               f'<a href="{e(meet)}" style="color:#8C7E6E;text-decoration:none;word-break:break-all">'
               f'{e(meet)}</a></p>')
    else:
        top = (f'<p style="margin:0 0 22px;padding:13px 16px;background:#FFFCF6;'
               f'border-left:3px solid #AD7A32;font-size:14px;line-height:1.6;color:#5C4A3A">'
               f'{e(nolink)}</p>')

    if not slot_utc:
        return top
    try:
        links = _b.calendar_links(slot_utc, client_name, lang)
    except Exception:
        return top
    pill = ('display:inline-block;padding:9px 16px;margin:0 4px 6px;border:1px solid #DCD2C2;'
            'background:#FFFCF6;color:#5C4A3A;text-decoration:none;font-size:14px')
    return top + (
        f'<p style="margin:0 0 8px;text-align:center;font-size:11px;letter-spacing:.18em;'
        f'text-transform:uppercase;color:#927B4A">{e(calhead)}</p>'
        f'<p style="margin:0 0 24px;text-align:center;line-height:1.9">'
        f'<a href="{e(links["google"])}" style="{pill}">Google Calendar</a>'
        f'<a href="{e(links["outlook"])}" style="{pill}">Outlook</a>'
        f'<span style="display:inline-block;padding:9px 4px;font-size:13px;color:#8C7E6E">'
        f'{e(other)}</span></p>')


_BOOK_HTML = """<div style="margin:0;padding:28px 20px 40px;background:#F5EEE0">
<div style="max-width:560px;margin:0 auto;font-family:'Hanken Grotesk','Helvetica Neue',Arial,sans-serif;font-size:16px;line-height:1.62;color:#5C4A3A">
<div style="text-align:center;padding:0 0 18px">{seal}</div>
<p style="margin:0 0 14px">{g1}</p>
<p style="margin:0 0 20px">{g2}</p>
<div style="margin:0 0 8px;padding:18px;background:#FFFCF6;border:1px solid #DCD2C2;
  border-top:1px solid rgba(173,122,50,.42);text-align:center">
  <p style="margin:0 0 5px;font-size:11px;letter-spacing:.18em;text-transform:uppercase;color:#927B4A">{tlabel}</p>
  <p style="margin:0;font-family:Fraunces,Georgia,serif;font-size:20px;color:#281F16">{when}</p>
</div>
<p style="margin:0 0 22px;font-size:13px;color:#75685A;text-align:center">{cal}</p>
{meetrow}
<p style="margin:26px 0 8px;font-family:Fraunces,Georgia,serif;font-size:18px;color:#281F16">{ph}</p>
<p style="margin:0 0 12px">{pintro}</p>
<table cellpadding="0" cellspacing="0" style="border-collapse:collapse;margin:0 0 22px">{plist}</table>
<p style="margin:0 0 22px;font-size:15px;color:#75685A">{pmove}</p>
<p style="margin:0">{g4}<br>
  <span style="font-family:Fraunces,Georgia,serif;font-size:19px;color:#281F16">Desiree</span></p>
<p style="margin:22px 0 0;padding:14px 16px;background:#FFFCF6;border-left:3px solid #AD7A32;
  font-size:13px;line-height:1.6;color:#5C4A3A">{creds}</p>
<p style="margin:22px 0 0;padding-top:14px;border-top:1px solid #DCD2C2;font-size:12px;
  line-height:1.6;color:#75685A">{owner} · {brand}<br>{contact}<br>{disc}</p>
</div></div>"""


# subj · g1 · g2 (what this is) · btn · lid · lpw · note · g4
# qh/q1/q2 · the questionnaire block: heading, the invitation, the release
_CREDS = {
    "de": ("Dein Zugang zum Auralis-Natura-Portal", "Hallo {name},",
           "hier ist dein persönlicher Zugang zu deinem geschützten Klienten-Portal — "
           "und darin dein Fragebogen.",
           "Fragebogen öffnen", "Login-ID", "Passwort",
           "Der Button meldet dich direkt an. ID und Passwort brauchst du nur, wenn du "
           "dich später von einem anderen Gerät anmeldest — bewahre sie gut auf.",
           "Bis bald,",
           "Dein Fragebogen",
           "Du kannst jetzt schon in Ruhe damit anfangen. Er dauert etwa 15 Minuten, "
           "<b>speichert automatisch</b> und du kannst jederzeit pausieren und später "
           "weitermachen.",
           "Und falls es zeitlich nicht klappt: kein Problem. Dann gehen wir ihn im "
           "Erstgespräch gemeinsam durch."),
    "en": ("Your access to the Auralis Natura portal", "Hi {name},",
           "here is your personal access to your protected client portal — and to your "
           "questionnaire inside it.",
           "Open my questionnaire", "Login ID", "Password",
           "The button signs you in directly. You only need the ID and password if you "
           "sign in later from another device — keep them somewhere safe.",
           "See you soon,",
           "Your questionnaire",
           "You can make a start whenever it suits you. It takes about 15 minutes, "
           "<b>saves automatically</b>, and you can pause and pick it up again at any time.",
           "And if you don't get to it: no problem at all. We'll go through it together "
           "in our first call."),
    "es": ("Tu acceso al portal de Auralis Natura", "Hola {name}:",
           "aquí tienes tu acceso personal a tu portal de cliente protegido — y dentro, "
           "tu cuestionario.",
           "Abrir mi cuestionario", "ID de acceso", "Contraseña",
           "El botón te identifica directamente. Solo necesitas el ID y la contraseña si "
           "entras más adelante desde otro dispositivo — guárdalos bien.",
           "Hasta pronto,",
           "Tu cuestionario",
           "Puedes empezar cuando te venga bien. Dura unos 15 minutos, <b>se guarda "
           "solo</b> y puedes pausarlo y retomarlo cuando quieras.",
           "Y si no te da tiempo: no pasa nada. Lo repasamos juntas en nuestra primera "
           "llamada."),
}

_CREDS_HTML = """<div style="margin:0;padding:28px 20px 40px;background:#F5EEE0">
<div style="max-width:560px;margin:0 auto;font-family:'Hanken Grotesk','Helvetica Neue',Arial,sans-serif;font-size:16px;line-height:1.62;color:#5C4A3A">
<div style="text-align:center;padding:0 0 18px">{seal}</div>
<p style="margin:0 0 14px">{g1}</p>
<p style="margin:0 0 24px">{g2}</p>
<p style="margin:0 0 6px;font-family:Fraunces,Georgia,serif;font-size:19px;color:#281F16">{qh}</p>
<p style="margin:0 0 12px">{q1}</p>
<p style="margin:0 0 22px;font-size:15px;color:#75685A">{q2}</p>
<p style="margin:0 0 10px;text-align:center">
  <a href="{magic}" style="background:#A8492A;color:#FBF3EC;text-decoration:none;
     padding:15px 30px;font-weight:600;font-size:16px;display:inline-block">{btn} &#8594;</a></p>
<p style="margin:0 0 26px;text-align:center;font-size:13px;color:#8C7E6E">{oneclick}</p>
<div style="margin:0 0 20px;padding:18px;background:#FFFCF6;border:1px solid #DCD2C2;
  border-top:1px solid rgba(173,122,50,.42)">
  <p style="margin:0 0 12px;font-size:11px;letter-spacing:.18em;text-transform:uppercase;color:#927B4A">{manual}</p>
  <table cellpadding="0" cellspacing="0" style="font-size:15px;border-collapse:collapse">
    <tr><td style="color:#8C7E6E;padding:3px 18px 3px 0;font-size:12px;letter-spacing:.08em;text-transform:uppercase">{lid}</td>
        <td style="font-family:Menlo,Consolas,monospace;font-weight:600;color:#281F16">{cid}</td></tr>
    <tr><td style="color:#8C7E6E;padding:3px 18px 3px 0;font-size:12px;letter-spacing:.08em;text-transform:uppercase">{lpw}</td>
        <td style="font-family:Menlo,Consolas,monospace;font-weight:600;color:#281F16">{pw}</td></tr>
  </table>
  <p style="margin:12px 0 0;font-size:13px;line-height:1.5">
    <a href="{url}" style="color:#8C7E6E;text-decoration:none;word-break:break-all">{url}</a></p>
</div>
<p style="margin:0 0 22px;font-size:13px;line-height:1.6;color:#8C7E6E">{note}</p>
<p style="margin:0">{g4}<br>
  <span style="font-family:Fraunces,Georgia,serif;font-size:19px;color:#281F16">Desiree</span></p>
<p style="margin:22px 0 0;padding-top:14px;border-top:1px solid #DCD2C2;font-size:12px;
  line-height:1.6;color:#75685A">{owner} · {brand}<br>{contact}<br>{disc}</p>
</div></div>"""

_CREDS_UI = {
    "de": ("Ein Klick — kein Passwort nötig.", "Oder von Hand anmelden"),
    "en": ("One click — no password needed.", "Or sign in manually"),
    "es": ("Un clic — sin contraseña.", "O inicia sesión a mano"),
}


def build_credentials_email(to_email: str, name: str, cid: str, password: str,
                            language: str = "de", magic_link: str = "") -> EmailMessage:
    """The Zugangsdaten-Karte, led by the questionnaire rather than by a password.

    Two changes that matter to the person receiving it: the button signs them
    in (magic_link), because asking someone to copy a generated password off a
    phone screen into a login form is where people quietly give up; and the
    mail says plainly that starting the questionnaire is optional — it saves as
    it goes, and if life gets in the way it is done together in the first call.
    ID and password stay, one step down the page, for the second device.
    """
    co = cfg.company(); c = cfg.config()
    lang = language if language in _CREDS else "de"
    subj, g1, g2, btn, lid, lpw, note, g4, qh, q1, q2 = _CREDS[lang]
    oneclick, manual = _CREDS_UI[lang]
    url = c.get("public_base_url", "").rstrip("/") + "/portal"
    e = html.escape
    msg = EmailMessage()
    msg["Subject"] = subj
    msg["From"] = f'{c.get("from_name","Auralis Natura")} <{c.get("from_email","")}>'
    msg["To"] = to_email
    strip = lambda s: s.replace("<b>", "").replace("</b>", "")
    msg.set_content(
        f"{g1.format(name=name)}\n\n{g2}\n\n{qh}\n{strip(q1)}\n{q2}\n\n"
        + (f"{btn}: {magic_link}\n\n" if magic_link else "")
        + f"{manual}\n{lid}: {cid}\n{lpw}: {password}\n{url}\n\n{note}\n\n{g4}\nDesiree\n\n"
        + f"{co.get('brand','Auralis Natura')} · {co.get('email','')}\n{_disc(lang)}")
    have_seal = (cfg.ASSETS_DIR / "logo-lockup-email.png").exists() or (cfg.ASSETS_DIR / "seal.png").exists()
    seal_img = ('<img src="cid:auralislogo" width="176" alt="Auralis Natura" style="display:block;margin:0 auto;width:176px;max-width:60%;height:auto;border:0">'
                if have_seal else "")
    msg.add_alternative(_CREDS_HTML.format(
        seal=seal_img, g1=e(g1.format(name=name)), g2=e(g2),
        qh=e(qh), q1=q1, q2=e(q2),                      # q1 carries an intentional <b>
        magic=e(magic_link or url), btn=e(btn), oneclick=e(oneclick), manual=e(manual),
        lid=e(lid), lpw=e(lpw), cid=e(cid), pw=e(password), url=e(url),
        note=e(note), g4=e(g4),
        owner=e(co.get("owner", "")), brand=e(co.get("brand", "")),
        contact=e(f'{co.get("email","")} · {co.get("phone","")}'), disc=_disc(lang),
    ), subtype="html")
    if have_seal:
        _inline_seal(msg)
    return _stamp(msg, f"access-{cid}")


_NEWS_HTML = """<div style="margin:0;padding:28px 20px 40px;background:#F5EEE0">
<div style="max-width:600px;margin:0 auto;font-family:'Hanken Grotesk','Helvetica Neue',Arial,sans-serif;background:#FBF6EB;border:1px solid rgba(61,39,25,.18)">
<div style="text-align:center;padding:26px 0 16px;border-bottom:1px solid rgba(173,122,50,.42)">
  {seal}
  <div style="font-size:10px;letter-spacing:.22em;text-transform:uppercase;color:#A8492A;font-weight:600;margin-top:8px">Holistic Health</div>
</div>
<div style="padding:26px 30px;font-size:16px;line-height:1.65;color:#3d3126">{body}</div>
<div style="padding:0 30px 26px"><p style="margin:0">Herzlich,<br><span style="font-family:Fraunces,Georgia,serif;font-size:19px;color:#281F16">Desiree</span></p></div>
<div style="border-top:1px solid rgba(61,39,25,.16);padding:14px 30px;font-size:11px;color:#8C7E6E;line-height:1.6">{owner} · {brand}<br>{contact}<br>{disc}</div></div></div>"""


def build_newsletter(subject: str, body_text: str, bcc: list[str]) -> EmailMessage:
    """Premium branded newsletter — To: the practice itself, all clients in BCC."""
    co = cfg.company(); c = cfg.config()
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = f'{c.get("from_name","Auralis Natura")} <{c.get("from_email","")}>'
    msg["To"] = c.get("from_email", "")
    msg["Bcc"] = ", ".join(bcc)
    msg.set_content(body_text + "\n\nHerzlich,\nDesiree\n\n" + _disc("de"))
    have_seal = (cfg.ASSETS_DIR / "logo-lockup-email.png").exists() or (cfg.ASSETS_DIR / "seal.png").exists()
    seal_img = ('<img src="cid:auralislogo" width="176" alt="Auralis Natura" style="display:block;margin:0 auto;width:176px;max-width:60%;height:auto;border:0">'
                if have_seal else "")
    paras = "".join(f"<p style=\"margin:0 0 14px\">{html.escape(p.strip())}</p>"
                    for p in body_text.split("\n\n") if p.strip())
    msg.add_alternative(_NEWS_HTML.format(
        seal=seal_img, body=paras,
        owner=html.escape(co.get("owner", "")), brand=html.escape(co.get("brand", "")),
        contact=html.escape(f'{co.get("email","")} · {co.get("phone","")}'), disc=_disc("de"),
    ), subtype="html")
    if have_seal:
        _inline_seal(msg)
    return _stamp(msg)


_REMIND = {
    "de": ("Erinnerung: unser Gespräch", "Hallo {name},",
           "eine kleine Erinnerung an unser Gespräch:",
           "Falls dir etwas dazwischenkommt, antworte einfach auf diese E-Mail — wir finden einen neuen Termin.",
           "Bis gleich,"),
    "es": ("Recordatorio: nuestra llamada", "Hola {name}:",
           "un pequeño recordatorio de nuestra llamada:",
           "Si te surge algo, responde a este correo y buscamos otro momento.",
           "Hasta ahora,"),
    "en": ("Reminder: our call", "Hi {name},",
           "a gentle reminder of our upcoming call:",
           "If something comes up, just reply to this email and we'll find a new time.",
           "See you soon,"),
}


_REMIND_HTML = """<div style="margin:0;padding:28px 20px 40px;background:#F5EEE0">
<div style="max-width:560px;margin:0 auto;font-family:'Hanken Grotesk','Helvetica Neue',Arial,sans-serif;font-size:16px;line-height:1.62;color:#5C4A3A">
<div style="text-align:center;padding:0 0 18px">{seal}</div>
<p style="margin:0 0 14px">{g1}</p>
<p style="margin:0 0 20px">{g2}</p>
<div style="margin:0 0 22px;padding:18px;background:#FFFCF6;border:1px solid #DCD2C2;
  border-top:1px solid rgba(173,122,50,.42);text-align:center">
  <p style="margin:0 0 5px;font-size:11px;letter-spacing:.18em;text-transform:uppercase;color:#927B4A">{tlabel}</p>
  <p style="margin:0;font-family:Fraunces,Georgia,serif;font-size:20px;color:#281F16">{when}</p>
</div>
{meetrow}
<p style="margin:0 0 22px;font-size:15px;color:#75685A">{g3}</p>
<p style="margin:0">{g4}<br>
  <span style="font-family:Fraunces,Georgia,serif;font-size:19px;color:#281F16">Desiree</span></p>
<p style="margin:22px 0 0;padding-top:14px;border-top:1px solid #DCD2C2;font-size:12px;
  line-height:1.6;color:#75685A">{owner} · {brand}<br>{contact}<br>{disc}</p>
</div></div>"""


def build_reminder_email(to_email: str, name: str, when_local: str, language: str,
                         slot_utc: str = "", ics: bytes = b"") -> EmailMessage:
    """The nudge before the call — same join button and calendar row as the
    confirmation, because this is the mail the client actually has open when
    the call is about to start.

    It used to render through _BOOK_HTML, which grew placeholders the reminder
    never supplied: every reminder raised KeyError: 'tlabel' and the console
    returned a 500. It gets its own, shorter template now.
    """
    co = cfg.company(); c = cfg.config()
    lang = language if language in _REMIND else "en"
    subj, g1, g2, g3, g4 = _REMIND[lang]
    meet = co.get("meet_link", "")
    jbtn, _jc, _jo, jno = _JOIN.get(lang, _JOIN["de"])
    tlabel = {"de": "Dein Termin", "es": "Tu cita", "en": "Your call"}[lang]
    msg = EmailMessage()
    msg["Subject"] = f"{subj} · {when_local}"
    msg["From"] = f'{c.get("from_name","Auralis Natura")} <{c.get("from_email","")}>'
    msg["To"] = to_email
    msg.set_content(f"{g1.format(name=name)}\n\n{g2}\n\n    {when_local}\n"
                    + (f"\n{jbtn}:\n{meet}\n" if meet else f"\n{jno}\n")
                    + f"\n{g3}\n\n{g4}\nDesiree\n\n{_disc(lang)}")
    have_seal = (cfg.ASSETS_DIR / "logo-lockup-email.png").exists() or (cfg.ASSETS_DIR / "seal.png").exists()
    seal_img = ('<img src="cid:auralislogo" width="176" alt="Auralis Natura" style="display:block;margin:0 auto;width:176px;max-width:60%;height:auto;border:0">'
                if have_seal else "")
    msg.add_alternative(_REMIND_HTML.format(
        seal=seal_img, g1=html.escape(g1.format(name=name)), g2=html.escape(g2),
        tlabel=html.escape(tlabel), when=html.escape(when_local),
        meetrow=_join_block(lang, slot_utc, name), g3=html.escape(g3),
        g4=html.escape(g4), owner=html.escape(co.get("owner", "")),
        brand=html.escape(co.get("brand", "")),
        contact=html.escape(f'{co.get("email","")} · {co.get("phone","")}'), disc=_disc(lang),
    ), subtype="html")
    if have_seal:
        _inline_seal(msg)
    if ics:
        msg.add_attachment(ics, maintype="text", subtype="calendar",
                           filename="termin.ics")
        for part in msg.walk():
            if part.get_content_type() == "text/calendar":
                part.set_param("method", "REQUEST")
                part.set_param("charset", "UTF-8")
    return _stamp(msg)


_FEEDBACK = {
    "de": ("Wie war deine Zeit mit Auralis Natura?", "Hallo {name},",
           "dein Programm ist abgeschlossen — danke für dein Vertrauen und deine Offenheit. "
           "Es war mir eine Freude, dich zu begleiten.",
           "Zwei kleine Bitten: Antworte mir in zwei, drei Sätzen — was hat dir geholfen, was hätte besser sein können? "
           "Und wenn du magst: Dürfte ich einen Satz davon (mit Vornamen) als Stimme auf der Website zeigen?",
           "Von Herzen,"),
    "es": ("¿Cómo fue tu tiempo con Auralis Natura?", "Hola {name}:",
           "tu programa ha terminado — gracias por tu confianza y tu apertura. Ha sido un placer acompañarte.",
           "Dos pequeños favores: respóndeme en dos o tres frases — ¿qué te ayudó, qué podría mejorar? "
           "Y si quieres: ¿podría mostrar una frase (con tu nombre de pila) como testimonio en la web?",
           "Con cariño,"),
    "en": ("How was your time with Auralis Natura?", "Hi {name},",
           "your programme is complete — thank you for your trust and openness. It was a joy to accompany you.",
           "Two small favours: reply in two or three sentences — what helped, what could be better? "
           "And if you like: may I show one sentence (first name only) as a voice on the website?",
           "Warmly,"),
}


def build_feedback_email(to_email: str, name: str, language: str) -> EmailMessage:
    co = cfg.company(); c = cfg.config()
    lang = language if language in _FEEDBACK else "en"
    subj, g1, g2, g3, g4 = _FEEDBACK[lang]
    msg = EmailMessage()
    msg["Subject"] = subj
    msg["From"] = f'{c.get("from_name","Auralis Natura")} <{c.get("from_email","")}>'
    msg["To"] = to_email
    msg.set_content(f"{g1.format(name=name)}\n\n{g2}\n\n{g3}\n\n{g4}\nDesiree\n\n{_disc(lang)}")
    have_seal = (cfg.ASSETS_DIR / "logo-lockup-email.png").exists() or (cfg.ASSETS_DIR / "seal.png").exists()
    seal_img = ('<img src="cid:auralislogo" width="176" alt="Auralis Natura" style="display:block;margin:0 auto;width:176px;max-width:60%;height:auto;border:0">'
                if have_seal else "")
    msg.add_alternative(f"""<div style="margin:0;padding:28px 20px 40px;background:#F5EEE0">
<div style="max-width:560px;margin:0 auto;font-family:'Hanken Grotesk','Helvetica Neue',Arial,sans-serif;font-size:16px;line-height:1.62;color:#5C4A3A">
<div style="text-align:center;padding:0 0 18px">{seal_img}</div>
<p style="margin:0 0 14px;color:#281F16">{html.escape(g1.format(name=name))}</p>
<p style="margin:0 0 18px">{html.escape(g2)}</p>
<div style="background:#FFFCF6;border:1px solid #DCD2C2;border-left:3px solid #AD7A32;padding:16px 20px;margin:0 0 18px;line-height:1.6">{html.escape(g3)}</div>
<p style="margin:0">{html.escape(g4)}<br><span style="font-family:Fraunces,Georgia,serif;font-size:19px;color:#281F16">Desiree</span></p>
<p style="margin:22px 0 0;padding-top:14px;border-top:1px solid #DCD2C2;font-size:12px;line-height:1.6;color:#75685A">{html.escape(co.get("owner",""))} · {html.escape(co.get("brand",""))}<br>{_disc(lang)}</p>
</div></div>""",
        subtype="html")
    if have_seal:
        _inline_seal(msg)
    return _stamp(msg)


# ─────────────────────────────────────── internal booking notification ──────
# Goes to Desiree, not to a client, and is the one mail in this file that is
# SENT rather than drafted. The human-review gate exists so nothing unreviewed
# reaches a client; a note to yourself does not need reviewing, and a draft
# sitting in Gmail is exactly the thing you do not notice when a booking lands.

_SYM_DE = {
    "fatigue": "Erschöpfung / Energie", "sleep": "Schlaf", "digestion": "Verdauung",
    "stress": "Stress", "cycle": "Zyklus & Hormone", "fertility": "Kinderwunsch",
    "pregnancy": "Schwangerschaft", "breastfeeding": "Stillzeit", "weight": "Gewicht",
    "skin": "Haut & Haare", "mood": "Stimmung", "pain": "Schmerzen",
    "immune": "Immunsystem", "other": "Etwas anderes",
    "hormonal": "Hormonelle Balance",           # pre-2026-08-10 bookings
}
_STAGE_DE = {
    "none": "Keine besondere Lebensphase", "work": "Hohe berufliche Belastung",
    "family": "Familienphase / Elternschaft", "fertility": "Kinderwunsch",
    "pregnancy": "Schwangerschaft, Stillzeit oder Wochenbett",
    "perimenopause": "Perimenopause / Wechseljahre",
    "health": "Gesundheitliche Veränderung",
    "transition": "Persönlicher oder beruflicher Übergang", "other": "Etwas anderes",
    "postpartum": "Nach der Geburt", "menopause": "Menopause",   # legacy values
}
_SINCE_DE = {"weeks": "einigen Wochen", "months": "mehreren Monaten", "years": "Jahren"}
_FLAG_DE = {
    "weightloss": "ungewollter Gewichtsverlust", "chestpain": "Brustschmerz / Atemnot",
    "severepain": "starke oder anhaltende Schmerzen", "fainting": "Ohnmacht",
    "selfharm": "Gedanken an Selbstverletzung", "eating": "belastetes Essverhalten",
    "pregnancy": "Schwangerschaftskomplikation", "none": "keine",
}
_SCALE_DE = {"energy": "Energie", "sleep": "Schlaf", "stress": "Stress",
             "digestion": "Verdauung", "mood": "Stimmung"}


def build_internal_booking_email(name: str, email: str, when_local: str,
                                 language: str, profile: dict,
                                 note: str = "", booking_id: str = "",
                                 ics: bytes = b"") -> EmailMessage:
    """The at-a-glance briefing for a new intro call: when, who, what.

    It also carries the calendar invite, and that is not decoration. The
    confirmation mail is a DRAFT in email_mode=draft, so its invite reaches
    Google Calendar only once Desiree presses Send — which is why the Maria
    Moser booking (12.08.2026, 10:05) never appeared in the calendar at all.
    This briefing is SENT the moment the form is submitted, so hanging the same
    invite (same UID, so the two can never become two events) on it means the
    slot is blocked in team@'s calendar from the second it is booked.
    """
    co, c = cfg.company(), cfg.config()
    p = profile or {}
    e = html.escape

    flags = [f for f in (p.get("red_flags") or []) if f and f != "none"]
    syms = [_SYM_DE.get(s, s) for s in (p.get("symptoms") or [])]
    if p.get("symptoms_other"):
        syms = [s for s in syms if s != "Etwas anderes"] + [p["symptoms_other"]]

    rows = []
    def row(k, v, strong=False):
        if not v:
            return
        rows.append(
            f'<tr><td style="padding:9px 16px 9px 0;vertical-align:top;white-space:nowrap;'
            f'font-size:12px;letter-spacing:.09em;text-transform:uppercase;color:#927B4A;'
            f'border-bottom:1px solid #EAE1D2">{e(k)}</td>'
            f'<td style="padding:9px 0;vertical-align:top;font-size:15px;line-height:1.55;'
            f'color:#281F16;border-bottom:1px solid #EAE1D2'
            f'{";font-weight:600" if strong else ""}">{v}</td></tr>')

    row("Alter", e(str(p["age"])) + " Jahre" if p.get("age") else "")
    row("Wunsch", e(p["goal"]) if p.get("goal") else "", strong=True)
    row("Themen", " · ".join(e(s) for s in syms))
    row("Seit", e(_SINCE_DE.get(p.get("since"), p.get("since") or "")))
    row("Lebensphase", e(_STAGE_DE.get(p.get("life_stage"), p.get("life_stage") or "")))
    sc = p.get("scales") or {}
    if sc:
        row("Selbsteinschätzung", " · ".join(
            f'{e(_SCALE_DE.get(k, k))} {e(str(v))}/5' for k, v in sc.items()))
    row("Bisher versucht", e(p["tried"]) if p.get("tried") else "")
    row("Erkrankungen", e(p["conditions"]) if p.get("conditions") else "")
    row("Medikamente", e(p["medications"]) if p.get("medications") else "")
    row("Nachricht", e(note) if note else "")

    # Red flags open the mail, above everything else. CLAUDE.md §2: a red flag
    # changes what the first sentence of the call has to be.
    flagbox = ""
    if flags:
        flagbox = (
            f'<div style="margin:0 0 22px;padding:14px 16px;background:#FBEDE8;'
            f'border-left:3px solid #A8492A">'
            f'<p style="margin:0 0 4px;font-size:13px;letter-spacing:.1em;'
            f'text-transform:uppercase;color:#A8492A;font-weight:700">Sicherheitsfrage</p>'
            f'<p style="margin:0;font-size:15px;line-height:1.55;color:#281F16">'
            + e(", ".join(_FLAG_DE.get(f, f) for f in flags)) +
            '</p><p style="margin:6px 0 0;font-size:13px;color:#5C4A3A">'
            'Vor dem Gespräch ansehen — ärztliche Abklärung zuerst ansprechen.</p></div>')

    have_seal = (cfg.ASSETS_DIR / "logo-lockup-email.png").exists() or (cfg.ASSETS_DIR / "seal.png").exists()
    seal_img = ('<img src="cid:auralislogo" width="176" alt="Auralis Natura" style="display:block;margin:0 auto;width:176px;max-width:60%;height:auto;border:0">'
                if have_seal else "")

    langs = {"de": "Deutsch", "en": "English", "es": "Español"}
    body = f"""<div style="margin:0;padding:26px 20px 40px;background:#F5EEE0">
<div style="max-width:600px;margin:0 auto;font-family:'Helvetica Neue',Helvetica,Arial,sans-serif;color:#5C4A3A">
<div style="text-align:center;padding:0 0 18px">
  {seal_img}
  <p style="margin:8px 0 0;font-size:11px;letter-spacing:.2em;text-transform:uppercase;color:#927B4A">Neue Buchung</p>
</div>
<h1 style="margin:0 0 4px;font-family:Georgia,serif;font-size:25px;font-weight:normal;color:#281F16;line-height:1.2;text-align:center">{e(name)}</h1>
<p style="margin:0 0 4px;text-align:center;font-size:17px;color:#A8492A">{e(when_local)}</p>
<p style="margin:0 0 24px;text-align:center;font-size:13px;color:#75685A">
  {e(email)} · Gesprächssprache {e(langs.get(language, language))}</p>
{flagbox}
<table cellpadding="0" cellspacing="0" style="border-collapse:collapse;width:100%">{''.join(rows) or
  '<tr><td style="font-size:15px;color:#75685A">Keine Vorab-Angaben ausgefüllt.</td></tr>'}</table>
<p style="margin:26px 0 0;padding-top:14px;border-top:1px solid #DCD2C2;font-size:12px;line-height:1.6;color:#75685A">
Vollständiger Aufnahmebogen in der Betriebskonsole{f' · Buchung {e(booking_id)}' if booking_id else ''}.<br>
Diese Nachricht enthält Gesundheitsangaben (Art. 9 DSGVO) — nicht weiterleiten.</p>
</div></div>"""

    text = "\n".join(
        [f"NEUE BUCHUNG — {name}", when_local, f"{email} · {langs.get(language, language)}", ""]
        + ([f"SICHERHEITSFRAGE: {', '.join(_FLAG_DE.get(f, f) for f in flags)}", ""] if flags else [])
        + [f"Alter: {p.get('age') or '—'}", f"Wunsch: {p.get('goal','—')}", f"Themen: {' · '.join(syms) or '—'}",
           f"Seit: {_SINCE_DE.get(p.get('since'), p.get('since') or '—')}",
           f"Lebensphase: {_STAGE_DE.get(p.get('life_stage'), p.get('life_stage') or '—')}",
           f"Bisher versucht: {p.get('tried','—')}", f"Erkrankungen: {p.get('conditions','—')}",
           f"Medikamente: {p.get('medications','—')}", f"Nachricht: {note or '—'}"])

    msg = EmailMessage()
    when_short = when_local.split("·")[0].strip()
    msg["Subject"] = f"Neue Buchung · {name} · {when_short}"
    msg["From"] = f'{c.get("from_name","Auralis Natura")} <{c.get("from_email","")}>'
    msg["To"] = c.get("smtp_user") or c.get("from_email", "")
    if email:
        msg["Reply-To"] = email
    msg.set_content(text)
    msg.add_alternative(body, subtype="html")
    if have_seal:
        _inline_seal(msg, 150)
    if ics:
        msg.add_attachment(ics, maintype="text", subtype="calendar",
                           filename="termin.ics")
        for part in msg.walk():
            if part.get_content_type() == "text/calendar":
                part.set_param("method", "REQUEST")
                part.set_param("charset", "UTF-8")
    return _stamp(msg, f"booking-{booking_id}" if booking_id else "")


def notify_internal(msg: EmailMessage, tag: str = "bookings") -> dict:
    """Send now if we can, and always keep the .eml.

    Deliberately NOT deliver(): that honours email_mode, and both of its
    non-send modes lose this mail. off writes a file nobody opens; draft parks
    an alert in the Drafts folder, which is the one place you never look when a
    booking arrives. A notification to yourself has no review gate to respect.
    """
    _stamp(msg)
    outbox = cfg.OUTPUT_DIR / tag / "internal"
    outbox.mkdir(parents=True, exist_ok=True)
    path = outbox / f"notify-{int(time.time())}.eml"
    path.write_bytes(bytes(msg))
    pw = os.environ.get("AURALIS_SMTP_PASSWORD", cfg.config().get("smtp_password", ""))
    if not pw:
        return {"internal": "no AURALIS_SMTP_PASSWORD — not sent", "eml": str(path)}
    out = _smtp_send(msg)
    return {"internal": out.get("send", "?"), "eml": str(path)}


# ───────────────────────────────────── immediate acknowledgement to client ──
# Sent the moment the form is submitted. Deliberately NOT the confirmation:
# email_mode=draft means the confirmation and its calendar invite wait in Gmail
# until Desiree sends them, which is right — she wants to look at the intake
# first — but it leaves the client with nothing at all in the meantime, and
# silence after handing over health details reads as "did that even go through".
#
# So this one is transactional and fixed: it repeats the requested time, says
# what happens next, and asks for nothing. No advice, nothing AI-generated,
# nothing that needs reviewing before it goes out.

_ACK = {
    "de": ("Deine Anfrage ist angekommen.",
           "Hallo {name},",
           "vielen Dank für deine Anfrage — ich habe sie erhalten.",
           "Gewünschter Termin",
           "Ich sehe mir deine Angaben in Ruhe an und bestätige dir den Termin "
           "anschließend mit einer Kalender-Einladung. Du musst dafür nichts weiter tun.",
           "Falls sich etwas ändert oder du lieber eine andere Zeit hättest, "
           "antworte einfach auf diese E-Mail.",
           "Bis bald,"),
    "en": ("Your request has arrived.",
           "Hi {name},",
           "thank you for your request — it has reached me.",
           "Requested time",
           "I will look through what you shared and then confirm the appointment "
           "with a calendar invitation. There is nothing else you need to do.",
           "If anything changes, or you would prefer a different time, simply "
           "reply to this email.",
           "See you soon,"),
    "es": ("Tu solicitud ha llegado.",
           "Hola {name}:",
           "gracias por tu solicitud — la he recibido.",
           "Horario solicitado",
           "Revisaré con calma lo que has compartido y después te confirmaré la "
           "cita con una invitación de calendario. No tienes que hacer nada más.",
           "Si algo cambia o prefieres otro horario, basta con responder a este "
           "correo.",
           "Hasta pronto,"),
}


def build_ack_email(to_email: str, name: str, when_local: str,
                    language: str = "de", booking_id: str = "") -> EmailMessage:
    co, c = cfg.company(), cfg.config()
    lang = language if language in _ACK else "de"
    subj, g1, g2, wlabel, g3, g4, g5 = _ACK[lang]
    e = html.escape

    have_seal = (cfg.ASSETS_DIR / "logo-lockup-email.png").exists() or (cfg.ASSETS_DIR / "seal.png").exists()
    seal_img = ('<img src="cid:auralislogo" width="176" alt="Auralis Natura" style="display:block;margin:0 auto;width:176px;max-width:60%;height:auto;border:0">'
                if have_seal else "")

    body = f"""<div style="margin:0;padding:28px 20px 40px;background:#F5EEE0">
<div style="max-width:560px;margin:0 auto;font-family:'Hanken Grotesk','Helvetica Neue',Arial,sans-serif;font-size:16px;line-height:1.62;color:#5C4A3A">
<div style="text-align:center;padding:0 0 20px">
  {seal_img}
</div>
<h1 style="margin:0 0 20px;font-family:Fraunces,Georgia,serif;font-size:26px;font-weight:normal;
  color:#281F16;line-height:1.22;text-align:center">{e(subj)}</h1>
<p style="margin:0 0 14px">{e(g1.format(name=name))}</p>
<p style="margin:0 0 22px">{e(g2)}</p>
<div style="margin:0 0 22px;padding:16px 18px;background:#FFFCF6;border:1px solid #DCD2C2;
  border-top:1px solid rgba(173,122,50,.42);text-align:center">
  <p style="margin:0 0 4px;font-size:11px;letter-spacing:.18em;text-transform:uppercase;
    color:#927B4A">{e(wlabel)}</p>
  <p style="margin:0;font-family:Fraunces,Georgia,serif;font-size:19px;color:#281F16">{e(when_local)}</p>
</div>
<p style="margin:0 0 14px">{e(g3)}</p>
<p style="margin:0 0 24px;color:#75685A;font-size:15px">{e(g4)}</p>
<p style="margin:0">{e(g5)}<br>
  <span style="font-family:Fraunces,Georgia,serif;font-size:19px;color:#281F16">Desiree</span></p>
<p style="margin:26px 0 0;padding-top:14px;border-top:1px solid #DCD2C2;font-size:12px;
  line-height:1.6;color:#75685A">{e(co.get('owner',''))} · {e(co.get('brand',''))}<br>
  {e(co.get('email',''))} · {e(co.get('phone',''))}<br>{_disc(lang)}</p>
</div></div>"""

    text = (f"{g1.format(name=name)}\n\n{g2}\n\n{wlabel}: {when_local}\n\n{g3}\n\n{g4}\n\n"
            f"{g5}\nDesiree\n\n{co.get('brand','')} · {co.get('email','')}")

    msg = EmailMessage()
    msg["Subject"] = subj
    msg["From"] = f'{c.get("from_name","Auralis Natura")} <{c.get("from_email","")}>'
    msg["To"] = to_email
    msg.set_content(text)
    msg.add_alternative(body, subtype="html")
    if have_seal:
        _inline_seal(msg)
    return _stamp(msg, f"ack-{booking_id}" if booking_id else "")


def send_now(msg: EmailMessage, tag: str = "bookings") -> dict:
    """Send immediately, and always keep the .eml.

    Same reasoning as notify_internal(): email_mode governs mail that carries
    Desiree's judgement and therefore needs her eyes. This one carries none.
    """
    _stamp(msg)
    outbox = cfg.OUTPUT_DIR / tag / "ack"
    outbox.mkdir(parents=True, exist_ok=True)
    path = outbox / f"ack-{int(time.time())}.eml"
    path.write_bytes(bytes(msg))
    pw = os.environ.get("AURALIS_SMTP_PASSWORD", cfg.config().get("smtp_password", ""))
    if not pw:
        return {"ack": "no AURALIS_SMTP_PASSWORD — not sent", "eml": str(path)}
    return {"ack": _smtp_send(msg).get("send", "?"), "eml": str(path)}
