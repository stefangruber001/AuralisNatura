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


def _imap_draft(msg: EmailMessage) -> dict:
    c = cfg.config()
    pw = os.environ.get("AURALIS_SMTP_PASSWORD", c.get("smtp_password", ""))
    if not pw:
        return {"draft": "skipped — no AURALIS_SMTP_PASSWORD set"}
    try:
        M = imaplib.IMAP4_SSL(c.get("imap_host", "imap.gmail.com"), int(c.get("imap_port", 993)))
        M.login(c.get("smtp_user", ""), pw)
        M.append('"[Gmail]/Drafts"', "", imaplib.Time2Internaldate(time.time()), bytes(msg))
        M.logout()
        return {"draft": "uploaded to Gmail Drafts"}
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
        "de": "Auralis Natura — ganzheitliches Gesundheits- und Ernährungscoaching (Bildung, keine medizinische Versorgung).",
        "es": "Auralis Natura — coaching holístico de salud y nutrición (educación, no atención médica).",
        "en": "Auralis Natura — holistic health &amp; nutrition coaching (education, not medical care).",
    }[lang]


_HTML = """<div style="font-family:'Hanken Grotesk',Arial,sans-serif;color:#2A211A;max-width:560px;margin:0 auto">
<div style="text-align:center;padding:18px 0"><img src="data:image/png;base64,{seal}" width="56" height="56" alt=""></div>
<p>{g1}</p><p style="color:#5C4A3A;line-height:1.6">{g2}</p>
<p style="color:#5C4A3A">{g3}<br><a href="{booking}" style="color:#A8492A">{booking}</a></p>
<p style="margin-top:22px">{g4}<br><span style="font-family:Fraunces,Georgia,serif;font-size:18px">Desiree</span></p>
<hr style="border:none;border-top:1px solid rgba(61,39,25,.16);margin:18px 0">
<p style="font-size:11px;color:#8C7E6E;line-height:1.6">{owner} · {brand}<br>{contact}<br>{disc}</p></div>"""


_BOOKING = {
    "de": ("Dein Termin ist bestätigt", "Hallo {name},",
           "dein kostenloses 25-Minuten-Gespräch ist bestätigt für:",
           "Du erhältst den Link unten — füge den Termin mit der angehängten Einladung zu deinem Kalender hinzu.",
           "Bis bald,"),
    "es": ("Tu cita está confirmada", "Hola {name}:",
           "tu llamada gratuita de 25 minutos está confirmada para:",
           "Encontrarás el enlace abajo — añade la cita a tu calendario con la invitación adjunta.",
           "Hasta pronto,"),
    "en": ("Your call is confirmed", "Hi {name},",
           "your free 25-minute call is confirmed for:",
           "You'll find the link below — add it to your calendar with the attached invite.",
           "See you soon,"),
}


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
    seal = ""
    seal_path = cfg.ASSETS_DIR / "seal.png"
    if seal_path.exists():
        seal = base64.b64encode(seal_path.read_bytes()).decode()
    btn = {"de": "Zum Gespräch (Google Meet)", "es": "Unirme (Google Meet)",
           "en": "Join the call (Google Meet)"}[lang]
    cal_note = {"de": "Die Kalender-Einladung ist angehängt — einmal annehmen, fertig.",
                "es": "La invitación de calendario va adjunta — acéptala y listo.",
                "en": "The calendar invite is attached — accept once and you're set."}[lang]
    msg.add_alternative(_BOOK_HTML.format(
        seal=seal, g1=html.escape(g1.format(name=name)), g2=html.escape(g2),
        when=html.escape(when_local), cal=html.escape(cal_note),
        meetrow=(f'<p style="margin:16px 0 0;text-align:center"><a href="{html.escape(meet)}" '
                 f'style="background:#A8492A;color:#FBF3EC;text-decoration:none;padding:12px 26px;'
                 f'font-weight:600;display:inline-block">{html.escape(btn)} →</a></p>' if meet else ""),
        g4=html.escape(g4), owner=html.escape(co.get("owner", "")),
        brand=html.escape(co.get("brand", "")),
        contact=html.escape(f'{co.get("email","")} · {co.get("phone","")}'), disc=_disc(lang),
    ), subtype="html")
    # text/calendar with method=REQUEST inline -> Gmail renders the event card
    msg.add_attachment(ics, maintype="text", subtype="calendar",
                       filename="einladung.ics")
    for part in msg.walk():
        if part.get_content_type() == "text/calendar":
            part.set_param("method", "REQUEST")
            part.set_param("charset", "UTF-8")
    return msg


_BOOK_HTML = """<div style="font-family:'Hanken Grotesk',Arial,sans-serif;color:#2A211A;max-width:560px;margin:0 auto;background:#FBF6EB;border:1px solid rgba(61,39,25,.18)">
<div style="text-align:center;padding:24px 0 12px;border-bottom:2px solid #A8492A">
  <img src="data:image/png;base64,{seal}" width="58" height="58" alt="">
  <div style="font-family:Fraunces,Georgia,serif;font-size:21px;margin-top:6px">Auralis Natura</div>
  <div style="font-size:10px;letter-spacing:.22em;text-transform:uppercase;color:#A8492A;font-weight:600;margin-top:2px">Holistic Health</div>
</div>
<div style="padding:24px 30px">
<p style="margin:0 0 12px">{g1}</p>
<p style="margin:0 0 16px;color:#5C4A3A;line-height:1.6">{g2}</p>
<div style="background:#fff;border:1px solid rgba(61,39,25,.2);border-top:3px solid #AD7A32;padding:18px 22px;text-align:center">
  <div style="font-size:10px;letter-spacing:.18em;text-transform:uppercase;color:#8C7E6E;font-weight:600">Dein Termin · Your call</div>
  <div style="font-family:Fraunces,Georgia,serif;font-size:20px;margin-top:6px;color:#3D2719">{when}</div>
  {meetrow}
</div>
<p style="margin:14px 0 0;color:#8C7E6E;font-size:13px">📅 {cal}</p>
<p style="margin:20px 0 0">{g4}<br><span style="font-family:Fraunces,Georgia,serif;font-size:18px">Desiree</span></p>
</div>
<div style="border-top:1px solid rgba(61,39,25,.16);padding:12px 30px;font-size:11px;color:#8C7E6E;line-height:1.6">{owner} · {brand}<br>{contact}<br>{disc}</div></div>"""


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

_CREDS_HTML = """<div style="font-family:'Hanken Grotesk',Arial,sans-serif;color:#2A211A;max-width:560px;margin:0 auto">
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


_NEWS_HTML = """<div style="font-family:'Hanken Grotesk',Arial,sans-serif;color:#2A211A;max-width:600px;margin:0 auto;background:#FBF6EB;border:1px solid rgba(61,39,25,.18)">
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
    msg.add_alternative(f"""<div style="font-family:'Hanken Grotesk',Arial,sans-serif;color:#2A211A;max-width:560px;margin:0 auto">
<div style="text-align:center;padding:18px 0"><img src="data:image/png;base64,{seal}" width="56" height="56" alt=""></div>
<p>{html.escape(g1.format(name=name))}</p>
<p style="color:#5C4A3A;line-height:1.6">{html.escape(g2)}</p>
<div style="background:#FBF6EB;border:1px solid rgba(61,39,25,.2);border-left:4px solid #AD7A32;padding:16px 20px;margin:16px 0;color:#5C4A3A;line-height:1.6">{html.escape(g3)}</div>
<p style="margin-top:20px">{html.escape(g4)}<br><span style="font-family:Fraunces,Georgia,serif;font-size:18px">Desiree</span></p>
<hr style="border:none;border-top:1px solid rgba(61,39,25,.16);margin:18px 0">
<p style="font-size:11px;color:#8C7E6E;line-height:1.6">{html.escape(co.get("owner",""))} · {html.escape(co.get("brand",""))}<br>{_disc(lang)}</p></div>""",
        subtype="html")
    return msg
