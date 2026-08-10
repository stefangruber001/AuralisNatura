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
import os, smtplib, imaplib, time, base64, html
from email.message import EmailMessage
from pathlib import Path
from . import cfg

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

    seal = ""
    seal_path = cfg.ASSETS_DIR / "seal.png"
    if seal_path.exists():
        seal = base64.b64encode(seal_path.read_bytes()).decode()
    body_html = _HTML.format(
        seal=seal, g1=html.escape(g1.format(name=client_name)), g2=html.escape(g2),
        g3=html.escape(g3), booking=html.escape(booking), g4=html.escape(g4),
        owner=html.escape(co.get("owner", "")), brand=html.escape(co.get("brand", "")),
        contact=html.escape(f'{co.get("email","")} · {co.get("phone","")}'),
        disc=_disc(lang),
    )
    msg.add_alternative(body_html, subtype="html")

    if pdf_path and Path(pdf_path).exists():
        data = Path(pdf_path).read_bytes()
        maintype, subtype = ("application", "pdf") if str(pdf_path).endswith(".pdf") else ("text", "html")
        msg.add_attachment(data, maintype=maintype, subtype=subtype,
                           filename=f"Auralis-Report-{_safe(client_name)}.{'pdf' if subtype=='pdf' else 'html'}")
    return msg


def deliver(msg: EmailMessage, client_id: str) -> dict:
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
        M.append(box, "", imaplib.Time2Internaldate(time.time()), bytes(msg))
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


_HTML = """<div style="font-family:'Hanken Grotesk',Arial,sans-serif;color:#281F16;max-width:560px;margin:0 auto">
<div style="text-align:center;padding:18px 0"><img src="data:image/png;base64,{seal}" width="56" height="56" alt=""></div>
<p>{g1}</p><p style="color:#5C4A3A;line-height:1.6">{g2}</p>
<p style="color:#5C4A3A">{g3}<br><a href="{booking}" style="color:#A8492A">{booking}</a></p>
<p style="margin-top:22px">{g4}<br><span style="font-family:Fraunces,Georgia,serif;font-size:18px">Desiree</span></p>
<hr style="border:none;border-top:1px solid rgba(61,39,25,.16);margin:18px 0">
<p style="font-size:11px;color:#8C7E6E;line-height:1.6">{owner} · {brand}<br>{contact}<br>{disc}</p></div>"""


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
        "Dr. rer. nat. Desiree Gruber · promoviert in bioorganischer Chemie · "
        "über fünfzehn Jahre in Forschung und pharmazeutischer Industrie · "
        "zertifiziert in ganzheitlicher Gesundheit, Ernährung und Frauengesundheit"),
 "en": ("How our conversation works",
        ["The link opens straight in your browser — nothing to install.",
         "Find a quiet spot, and headphones if you have them.",
         "Bring whatever matters to you: questions, results, notes — none of it required."],
        "Together we look at where you are right now, what you are hoping for and "
        "which next step makes sense for you. Not a sales call, and nothing to prepare.",
        "If something comes up, just reply to this email — cancelling is always fine.",
        "Dr. rer. nat. Desiree Gruber · doctorate in bioorganic chemistry · "
        "over fifteen years in research and the pharmaceutical industry · "
        "certified in holistic health, nutrition and women's health"),
 "es": ("Cómo será nuestra conversación",
        ["El enlace se abre directamente en el navegador — no hay que instalar nada.",
         "Busca un lugar tranquilo y auriculares, si tienes.",
         "Trae lo que te importe: preguntas, informes, notas — nada es obligatorio."],
        "Miramos juntas dónde estás ahora, qué deseas y cuál es el siguiente paso "
        "que tiene sentido para ti. No es una llamada de venta y no hay que preparar nada.",
        "Si te surge algo, responde a este correo — cancelar siempre está bien.",
        "Dr. rer. nat. Desiree Gruber · doctorada en química bioorgánica · "
        "más de quince años en investigación e industria farmacéutica · "
        "certificada en salud holística, nutrición y salud femenina"),
}

def _inline_seal(msg: EmailMessage, px: int = 120) -> str:
    """Attach the seal as an inline part and return the cid: reference.

    NOT a data: URI. Gmail strips data:-sourced <img> outright — which is why
    every one of these mails arrived with a broken image box where the seal
    should be. A related part with a Content-ID is the format mail clients
    actually render. Downscaled first: the master is 193 KB, and nothing here
    displays it above 60 px.
    """
    src = cfg.ASSETS_DIR / "seal.png"
    if not src.exists():
        return ""
    data = src.read_bytes()
    try:
        from PIL import Image
        import io
        im = Image.open(io.BytesIO(data)).convert("RGBA")
        im.thumbnail((px, px), Image.LANCZOS)
        buf = io.BytesIO(); im.save(buf, "PNG", optimize=True)
        data = buf.getvalue()
    except Exception:
        pass                      # ship the full-size original rather than nothing
    cid = "auralisseal"
    msg.get_payload()[-1].add_related(
        data, maintype="image", subtype="png", cid=f"<{cid}>",
        filename="auralis-seal.png", disposition="inline")
    return f"cid:{cid}"

def build_booking_email(to_email: str, name: str, when_local: str, language: str,
                        ics: bytes, booking_id: str) -> EmailMessage:
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
    body = (f"{g1.format(name=name)}\n\n{g2}\n\n    {when_local}\n\n{g3}\n"
            + (f"\n{meet}\n" if meet else "")
            + f"\n{g4}\nDesiree\n\n{co.get('brand','Auralis Natura')} · {co.get('email','')} · {co.get('phone','')}\n{_disc(lang)}")
    msg.set_content(body.replace("&amp;", "&"))
    btn = {"de": "Zum Gespräch (Google Meet)", "es": "Unirme (Google Meet)",
           "en": "Join the call (Google Meet)"}[lang]
    cal_note = {"de": "Die Kalender-Einladung ist angehängt — einmal annehmen, fertig.",
                "es": "La invitación de calendario va adjunta — acéptala y listo.",
                "en": "The calendar invite is attached — accept once and you're set."}[lang]
    tlabel = {"de": "Dein Termin", "es": "Tu cita", "en": "Your call"}[lang]
    ph, plist, pintro, pmove, creds = _PREP[lang]
    rows = "".join(
        f'<tr><td style="padding:4px 10px 4px 0;vertical-align:top;color:#A8492A">&#8226;</td>'
        f'<td style="padding:4px 0;vertical-align:top;font-size:15px;line-height:1.55">'
        f'{html.escape(x)}</td></tr>' for x in plist)
    # The cid goes into the markup BEFORE the part exists — add_related() turns
    # the html part into a multipart/related, so rewriting it afterwards means
    # reaching into the wrong node (and raises KeyError: multipart/related).
    have_seal = (cfg.ASSETS_DIR / "seal.png").exists()
    seal_img = ('<img src="cid:auralisseal" width="52" height="52" alt="Auralis Natura">'
                if have_seal else "")
    msg.add_alternative(_BOOK_HTML.format(
        seal=seal_img, g1=html.escape(g1.format(name=name)), g2=html.escape(g2),
        tlabel=html.escape(tlabel), when=html.escape(when_local),
        cal=html.escape(cal_note),
        meetrow=(f'<p style="margin:4px 0 0;text-align:center"><a href="{html.escape(meet)}" '
                 f'style="background:#A8492A;color:#FBF3EC;text-decoration:none;padding:13px 28px;'
                 f'font-weight:600;display:inline-block">{html.escape(btn)} &#8594;</a></p>' if meet else ""),
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
    return msg


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


_CREDS = {
    "de": ("Dein Zugang zum Auralis-Natura-Portal", "Hallo {name},",
           "willkommen an Bord! Hier ist dein persönlicher Zugang zu deinem geschützten Klienten-Portal. So geht es weiter: 1) Portal öffnen und in Ruhe den Aufnahmebogen ausfüllen (ca. 15 Min., speichert automatisch). 2) Ich bereite unser Tiefengespräch persönlich vor. 3) Danach erstelle ich deinen persönlichen Bericht — du findest ihn ebenfalls im Portal.",
           "Portal öffnen", "Login-ID", "Passwort",
           "Bitte bewahre diese Daten sicher auf. Du kannst das Passwort jederzeit bei mir zurücksetzen lassen.",
           "Bis bald,"),
    "es": ("Tu acceso al portal de Auralis Natura", "Hola {name}:",
           "aquí tienes tu acceso personal a tu portal de cliente protegido. Allí completas tu cuestionario con calma y más adelante encontrarás tu informe personal.",
           "Abrir portal", "ID de acceso", "Contraseña",
           "Guarda estos datos de forma segura. Puedes pedirme restablecer la contraseña en cualquier momento.",
           "Hasta pronto,"),
    "en": ("Your access to the Auralis Natura portal", "Hi {name},",
           "here is your personal access to your protected client portal. There you can complete your intake at your own pace, and later you'll find your personal report.",
           "Open portal", "Login ID", "Password",
           "Please keep these details safe. You can ask me to reset the password at any time.",
           "See you soon,"),
}

_CREDS_HTML = """<div style="font-family:'Hanken Grotesk',Arial,sans-serif;color:#281F16;max-width:560px;margin:0 auto">
<div style="text-align:center;padding:18px 0"><img src="data:image/png;base64,{seal}" width="56" height="56" alt=""></div>
<p>{g1}</p><p style="color:#5C4A3A;line-height:1.6">{g2}</p>
<div style="background:#FBF6EB;border:1px solid rgba(61,39,25,.2);border-top:3px solid #A8492A;padding:20px 24px;margin:18px 0">
  <table style="font-size:15px;border-collapse:collapse">
    <tr><td style="color:#8C7E6E;padding:4px 18px 4px 0;font-size:12px;letter-spacing:.08em;text-transform:uppercase">{lid}</td>
        <td style="font-family:Menlo,monospace;font-weight:600">{cid}</td></tr>
    <tr><td style="color:#8C7E6E;padding:4px 18px 4px 0;font-size:12px;letter-spacing:.08em;text-transform:uppercase">{lpw}</td>
        <td style="font-family:Menlo,monospace;font-weight:600">{pw}</td></tr>
  </table>
  <p style="margin:16px 0 0"><a href="{url}" style="background:#A8492A;color:#FBF3EC;text-decoration:none;padding:11px 22px;font-weight:600;display:inline-block">{btn} →</a></p>
</div>
<p style="color:#8C7E6E;font-size:13px;line-height:1.6">{note}</p>
<p style="margin-top:22px">{g4}<br><span style="font-family:Fraunces,Georgia,serif;font-size:18px">Desiree</span></p>
<hr style="border:none;border-top:1px solid rgba(61,39,25,.16);margin:18px 0">
<p style="font-size:11px;color:#8C7E6E;line-height:1.6">{owner} · {brand}<br>{contact}<br>{disc}</p></div>"""


def build_credentials_email(to_email: str, name: str, cid: str, password: str,
                            language: str = "de") -> EmailMessage:
    """The Zugangsdaten-Karte: login id + password + portal link, branded."""
    co = cfg.company(); c = cfg.config()
    lang = language if language in _CREDS else "en"
    subj, g1, g2, btn, lid, lpw, note, g4 = _CREDS[lang]
    url = c.get("public_base_url", "").rstrip("/") + "/portal"
    msg = EmailMessage()
    msg["Subject"] = subj
    msg["From"] = f'{c.get("from_name","Auralis Natura")} <{c.get("from_email","")}>'
    msg["To"] = to_email
    msg.set_content(f"{g1.format(name=name)}\n\n{g2}\n\n{lid}: {cid}\n{lpw}: {password}\n{url}\n\n{note}\n\n{g4}\nDesiree")
    seal = ""
    seal_path = cfg.ASSETS_DIR / "seal.png"
    if seal_path.exists():
        seal = base64.b64encode(seal_path.read_bytes()).decode()
    msg.add_alternative(_CREDS_HTML.format(
        seal=seal, g1=html.escape(g1.format(name=name)), g2=html.escape(g2),
        lid=html.escape(lid), lpw=html.escape(lpw), cid=html.escape(cid),
        pw=html.escape(password), url=html.escape(url), btn=html.escape(btn),
        note=html.escape(note), g4=html.escape(g4),
        owner=html.escape(co.get("owner", "")), brand=html.escape(co.get("brand", "")),
        contact=html.escape(f'{co.get("email","")} · {co.get("phone","")}'), disc=_disc(lang),
    ), subtype="html")
    return msg


_NEWS_HTML = """<div style="font-family:'Hanken Grotesk',Arial,sans-serif;color:#281F16;max-width:600px;margin:0 auto;background:#FBF6EB;border:1px solid rgba(61,39,25,.18)">
<div style="text-align:center;padding:26px 0 14px;border-bottom:2px solid #A8492A">
  <img src="data:image/png;base64,{seal}" width="60" height="60" alt="">
  <div style="font-family:Fraunces,Georgia,serif;font-size:22px;margin-top:8px">Auralis Natura</div>
  <div style="font-size:10px;letter-spacing:.22em;text-transform:uppercase;color:#A8492A;font-weight:600;margin-top:2px">Holistic Health</div>
</div>
<div style="padding:26px 30px;line-height:1.65;color:#3d3126">{body}</div>
<div style="padding:0 30px 26px"><p style="margin:0">Herzlich,<br><span style="font-family:Fraunces,Georgia,serif;font-size:18px">Desiree</span></p></div>
<div style="border-top:1px solid rgba(61,39,25,.16);padding:14px 30px;font-size:11px;color:#8C7E6E;line-height:1.6">{owner} · {brand}<br>{contact}<br>{disc}</div></div>"""


def build_newsletter(subject: str, body_text: str, bcc: list[str]) -> EmailMessage:
    """Premium branded newsletter — To: the practice itself, all clients in BCC."""
    co = cfg.company(); c = cfg.config()
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = f'{c.get("from_name","Auralis Natura")} <{c.get("from_email","")}>'
    msg["To"] = c.get("from_email", "")
    msg["Bcc"] = ", ".join(bcc)
    msg.set_content(body_text + "\n\nHerzlich,\nDesiree\n\n" + _disc("de"))
    seal = ""
    seal_path = cfg.ASSETS_DIR / "seal.png"
    if seal_path.exists():
        seal = base64.b64encode(seal_path.read_bytes()).decode()
    paras = "".join(f"<p style=\"margin:0 0 14px\">{html.escape(p.strip())}</p>"
                    for p in body_text.split("\n\n") if p.strip())
    msg.add_alternative(_NEWS_HTML.format(
        seal=seal, body=paras,
        owner=html.escape(co.get("owner", "")), brand=html.escape(co.get("brand", "")),
        contact=html.escape(f'{co.get("email","")} · {co.get("phone","")}'), disc=_disc("de"),
    ), subtype="html")
    return msg


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


def build_reminder_email(to_email: str, name: str, when_local: str, language: str) -> EmailMessage:
    co = cfg.company(); c = cfg.config()
    lang = language if language in _REMIND else "en"
    subj, g1, g2, g3, g4 = _REMIND[lang]
    meet = co.get("meet_link", "")
    msg = EmailMessage()
    msg["Subject"] = f"{subj} · {when_local}"
    msg["From"] = f'{c.get("from_name","Auralis Natura")} <{c.get("from_email","")}>'
    msg["To"] = to_email
    msg.set_content(f"{g1.format(name=name)}\n\n{g2}\n\n    {when_local}\n"
                    + (f"\n{meet}\n" if meet else "") + f"\n{g3}\n\n{g4}\nDesiree\n\n{_disc(lang)}")
    seal = ""
    p = cfg.ASSETS_DIR / "seal.png"
    if p.exists():
        seal = base64.b64encode(p.read_bytes()).decode()
    btn = {"de": "Zum Gespräch", "es": "Unirme", "en": "Join the call"}[lang]
    msg.add_alternative(_BOOK_HTML.format(
        seal=seal, g1=html.escape(g1.format(name=name)), g2=html.escape(g2),
        when=html.escape(when_local), cal=html.escape(g3),
        meetrow=(f'<p style="margin:16px 0 0;text-align:center"><a href="{html.escape(meet)}" '
                 f'style="background:#A8492A;color:#FBF3EC;text-decoration:none;padding:12px 26px;'
                 f'font-weight:600;display:inline-block">{html.escape(btn)} →</a></p>' if meet else ""),
        g4=html.escape(g4), owner=html.escape(co.get("owner", "")),
        brand=html.escape(co.get("brand", "")),
        contact=html.escape(f'{co.get("email","")} · {co.get("phone","")}'), disc=_disc(lang),
    ), subtype="html")
    return msg


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
    seal = ""
    p = cfg.ASSETS_DIR / "seal.png"
    if p.exists():
        seal = base64.b64encode(p.read_bytes()).decode()
    msg.add_alternative(f"""<div style="font-family:'Hanken Grotesk',Arial,sans-serif;color:#281F16;max-width:560px;margin:0 auto">
<div style="text-align:center;padding:18px 0"><img src="data:image/png;base64,{seal}" width="56" height="56" alt=""></div>
<p>{html.escape(g1.format(name=name))}</p>
<p style="color:#5C4A3A;line-height:1.6">{html.escape(g2)}</p>
<div style="background:#FBF6EB;border:1px solid rgba(61,39,25,.2);border-left:4px solid #AD7A32;padding:16px 20px;margin:16px 0;color:#5C4A3A;line-height:1.6">{html.escape(g3)}</div>
<p style="margin-top:20px">{html.escape(g4)}<br><span style="font-family:Fraunces,Georgia,serif;font-size:18px">Desiree</span></p>
<hr style="border:none;border-top:1px solid rgba(61,39,25,.16);margin:18px 0">
<p style="font-size:11px;color:#8C7E6E;line-height:1.6">{html.escape(co.get("owner",""))} · {html.escape(co.get("brand",""))}<br>{_disc(lang)}</p></div>""",
        subtype="html")
    return msg


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
                                 note: str = "", booking_id: str = "") -> EmailMessage:
    """The at-a-glance briefing for a new intro call: when, who, what."""
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

    have_seal = (cfg.ASSETS_DIR / "seal.png").exists()
    seal_img = ('<img src="cid:auralisseal" width="46" height="46" alt="">'
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
        _inline_seal(msg, 96)
    return msg


def notify_internal(msg: EmailMessage, tag: str = "bookings") -> dict:
    """Send now if we can, and always keep the .eml.

    Deliberately NOT deliver(): that honours email_mode, and both of its
    non-send modes lose this mail. off writes a file nobody opens; draft parks
    an alert in the Drafts folder, which is the one place you never look when a
    booking arrives. A notification to yourself has no review gate to respect.
    """
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
                    language: str = "de") -> EmailMessage:
    co, c = cfg.company(), cfg.config()
    lang = language if language in _ACK else "de"
    subj, g1, g2, wlabel, g3, g4, g5 = _ACK[lang]
    e = html.escape

    have_seal = (cfg.ASSETS_DIR / "seal.png").exists()
    seal_img = ('<img src="cid:auralisseal" width="52" height="52" alt="Auralis Natura">'
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
    return msg


def send_now(msg: EmailMessage, tag: str = "bookings") -> dict:
    """Send immediately, and always keep the .eml.

    Same reasoning as notify_internal(): email_mode governs mail that carries
    Desiree's judgement and therefore needs her eyes. This one carries none.
    """
    outbox = cfg.OUTPUT_DIR / tag / "ack"
    outbox.mkdir(parents=True, exist_ok=True)
    path = outbox / f"ack-{int(time.time())}.eml"
    path.write_bytes(bytes(msg))
    pw = os.environ.get("AURALIS_SMTP_PASSWORD", cfg.config().get("smtp_password", ""))
    if not pw:
        return {"ack": "no AURALIS_SMTP_PASSWORD — not sent", "eml": str(path)}
    return {"ack": _smtp_send(msg).get("send", "?"), "eml": str(path)}
