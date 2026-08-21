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
import os, re, smtplib, imaplib, time, html
from email.message import EmailMessage
from email.utils import formatdate, make_msgid
from pathlib import Path
from . import cfg


from . import mailv2


def _tile_of(slot_utc: str):
    """(tile_parts, tzname) for the v2 date ticket; (None, tz) without a slot."""
    from . import booking as _b
    import datetime as _dt
    from zoneinfo import ZoneInfo
    tzname = "Europe/Madrid"
    try:
        tzname = _b.get_availability().get("timezone", tzname)
    except Exception:
        pass
    if not slot_utc:
        return None, tzname
    try:
        t = _dt.datetime.fromisoformat(slot_utc).astimezone(ZoneInfo(tzname))
    except Exception:
        return None, tzname
    return ({"day": t.day, "month": t.month, "year": t.year,
             "weekday": t.weekday(), "time": t.strftime("%H:%M")}, tzname)


def _pdf_pages(path) -> int | None:
    """Page count straight off the PDF bytes — 'compute, don't hardcode' (the
    v2 handoff), without importing a PDF library into the mail path."""
    try:
        counts = [int(x) for x in re.findall(rb"/Count\s+(\d+)", Path(path).read_bytes())]
        return max(counts) if counts else None
    except Exception:
        return None


def _finish_v2(msg: EmailMessage, doc: str, lang: str) -> EmailMessage:
    """Company footer, then data: images become cid: attachments — Gmail strips
    data: URIs, so an inlined emblem simply vanishes there."""
    co = cfg.company()
    doc = mailv2.footer(doc, co.get("owner", ""), co.get("brand", "Auralis Natura"),
                        co.get("email", ""), co.get("phone", ""), lang)
    cids: dict[str, str] = {}

    def _swap(m):
        cid = cids.setdefault(m.group(1), f"anv2i{len(cids) + 1}")
        return f'src="cid:{cid}"'

    doc = re.sub(r'src="data:image/png;base64,([^"]+)"', _swap, doc)
    msg.add_alternative(doc, subtype="html")
    part = msg.get_payload()[-1]
    import base64 as _b64
    for b64, cid in cids.items():
        part.add_related(_b64.b64decode(b64), maintype="image", subtype="png",
                         cid=f"<{cid}>")
    return msg


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

    _finish_v2(msg, mailv2.render_report(client_name, lang, booking,
                                         _pdf_pages(pdf_path)), lang)

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
    # time_ns, not seconds: two mails delivered in the same second (report +
    # schedule + feedback in one console flow) used to collide on the filename
    # and the earlier .eml — the audit copy — was silently overwritten.
    eml_path = outbox / f"report-{time.time_ns()}.eml"
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
    from . import booking as _bk
    _tp, _tz = _tile_of(slot_utc)
    try:
        _links = _bk.calendar_links(slot_utc, name, lang) if slot_utc else None
    except Exception:
        _links = None
    _finish_v2(msg, mailv2.render_booking(name, lang, _tp, _tz, _links, meet,
                                          when_local), lang)
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
    _finish_v2(msg, mailv2.render_creds(name, lang, cid, password,
                                        magic_link, url), lang)
    return _stamp(msg, f"access-{cid}")



def build_newsletter(subject: str, body_text: str, bcc: list[str]) -> EmailMessage:
    """Premium branded newsletter — To: the practice itself, all clients in BCC."""
    co = cfg.company(); c = cfg.config()
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = f'{c.get("from_name","Auralis Natura")} <{c.get("from_email","")}>'
    msg["To"] = c.get("from_email", "")
    msg["Bcc"] = ", ".join(bcc)
    msg.set_content(body_text + "\n\nHerzlich,\nDesiree\n\n" + _disc("de"))
    paras = "".join(f"<p style=\"margin:0 0 14px\">{html.escape(p.strip())}</p>"
                    for p in body_text.split("\n\n") if p.strip())
    _finish_v2(msg, mailv2.render_newsletter(subject, body_text), "de")
    return _stamp(msg)


_PERSONAL = {
    # salutation · closing · kicker — the body itself is Desiree's own text
    "de": ("Hallo {name},", "Herzlich,", "Persönliche Nachricht"),
    "en": ("Hi {name},", "Warmly,", "Personal note"),
    "es": ("Hola {name}:", "Un abrazo,", "Mensaje personal"),
}


def build_personal_email(to_email: str, name: str, subject: str, body_text: str,
                         language: str = "de") -> EmailMessage:
    """A one-off personal mail in the premium shell, salutation and footer in
    the client's language. The text is Desiree's, verbatim — nothing is
    generated, nothing is templated except the chrome around her words."""
    co, c = cfg.company(), cfg.config()
    lang = language if language in _PERSONAL else "de"
    hello, close, kicker = _PERSONAL[lang]
    first = (name or "").strip().split(" ")[0] or name
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = f'{c.get("from_name","Auralis Natura")} <{c.get("from_email","")}>'
    msg["To"] = to_email
    msg.set_content(f"{hello.format(name=first)}\n\n{body_text}\n\n{close}\nDesiree\n\n"
                    f"{co.get('brand','Auralis Natura')} · {co.get('email','')}\n{_disc(lang)}")
    _finish_v2(msg, mailv2.render_newsletter(
        subject, f"{hello.format(name=first)}\n\n{body_text}\n\n{close}\nDesiree",
        kicker=kicker), lang)
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



def build_reminder_email(to_email: str, name: str, when_local: str, language: str,
                         slot_utc: str = "", ics: bytes = b"") -> EmailMessage:
    """The nudge before the call — same join button and calendar row as the
    confirmation, because this is the mail the client actually has open when
    the call is about to start.

    It used to render through the v1 booking template, which grew placeholders the reminder
    never supplied: every reminder raised KeyError: 'tlabel' and the console
    returned a 500. It gets its own, shorter template now.
    """
    co = cfg.company(); c = cfg.config()
    lang = language if language in _REMIND else "en"
    subj, g1, g2, g3, g4 = _REMIND[lang]
    meet = co.get("meet_link", "")
    jbtn, _jc, _jo, jno = _JOIN.get(lang, _JOIN["de"])
    msg = EmailMessage()
    msg["Subject"] = f"{subj} · {when_local}"
    msg["From"] = f'{c.get("from_name","Auralis Natura")} <{c.get("from_email","")}>'
    msg["To"] = to_email
    msg.set_content(f"{g1.format(name=name)}\n\n{g2}\n\n    {when_local}\n"
                    + (f"\n{jbtn}:\n{meet}\n" if meet else f"\n{jno}\n")
                    + f"\n{g3}\n\n{g4}\nDesiree\n\n{_disc(lang)}")
    from . import booking as _bk
    _tp, _tz = _tile_of(slot_utc)
    try:
        _links = _bk.calendar_links(slot_utc, name, lang) if slot_utc else None
    except Exception:
        _links = None
    _finish_v2(msg, mailv2.render_reminder(name, lang, _tp, _tz, _links, meet,
                                           when_local), lang)
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


# subj · g1 · g2 (intro naming the programme) · table head date/time · g3 (rhythm
# is adjustable) · g4 (sign-off)
_SESSIONS = {
    "de": ("Deine Termine · {prog}", "Hallo {name},",
           "hier sind die Termine für unsere gemeinsamen Gespräche in deinem Programm "
           "{prog} — alle auf einen Blick, und als Kalender-Einladung angehängt: einmal "
           "annehmen, und alle stehen in deinem Kalender.",
           "Termin",
           "Wenn dir ein Termin nicht passt, antworte einfach auf diese E-Mail — wir "
           "verschieben ihn gemeinsam.",
           "Ich freue mich auf unseren Weg,"),
    "en": ("Your programme dates · {prog}", "Hi {name},",
           "here are the dates for our calls in your {prog} programme — all at a "
           "glance, and attached as one calendar invitation: accept once and every "
           "call lands in your calendar.",
           "Session",
           "If a date doesn't suit you, simply reply to this email — we'll move it "
           "together.",
           "Looking forward to our journey,"),
    "es": ("Tus citas · {prog}", "Hola {name}:",
           "aquí tienes las fechas de nuestras sesiones en tu programa {prog} — todas "
           "de un vistazo, y adjuntas como una invitación de calendario: acéptala una "
           "vez y todas quedarán en tu calendario.",
           "Sesión",
           "Si alguna fecha no te viene bien, responde a este correo — la movemos "
           "juntas.",
           "Con ganas de empezar este camino,"),
}


def build_sessions_email(to_email: str, name: str, sessions: list[dict],
                         language: str, prog_name: str, cid: str,
                         ics: bytes = b"", cancel_ics: bytes = b"") -> EmailMessage:
    """The programme schedule, as one premium mail + one multi-event invite.

    Follows email_mode like every mail that carries Desiree's judgement — in
    draft mode she reads the plan once more before it reaches the client.
    A re-plan that drops sessions carries a second, METHOD:CANCEL calendar
    part so the dropped events leave the client's calendar too.
    """
    from . import booking as _b
    co, c = cfg.company(), cfg.config()
    lang = language if language in _SESSIONS else "de"
    subj, g1, g2, _thead, g3, g4 = _SESSIONS[lang]
    unit = {"de": "Min.", "en": "min", "es": "min"}[lang]
    e = html.escape
    rows = ""
    lines_txt = []
    for s in sessions:
        label = _b.session_label(s.get("key", s.get("session_key", "weekly")),
                                 int(s.get("n", s.get("session_n", 1))), lang)
        when = _b.format_when(s.get("utc", s.get("start_utc")), lang)
        mins = int(s.get("minutes", 45))
        lines_txt.append(f"{label}: {when} ({mins} {unit})")
    msg = EmailMessage()
    msg["Subject"] = subj.format(prog=prog_name)
    msg["From"] = f'{c.get("from_name","Auralis Natura")} <{c.get("from_email","")}>'
    msg["To"] = to_email
    msg.set_content(f"{g1.format(name=name)}\n\n{g2.format(prog=prog_name)}\n\n"
                    + "\n".join(lines_txt) + f"\n\n{g3}\n\n{g4}\nDesiree\n\n{_disc(lang)}")
    _rows = [(_b.session_label(x.get("key", x.get("session_key", "weekly")),
                               int(x.get("n", x.get("session_n", 1))), lang),
              _b.format_when(x.get("utc", x.get("start_utc")), lang),
              int(x.get("minutes", 45))) for x in sessions]
    _finish_v2(msg, mailv2.render_sessions(name, lang, prog_name, _rows, unit), lang)
    if ics:
        msg.add_attachment(ics, maintype="text", subtype="calendar",
                           filename="programm-termine.ics")
    if cancel_ics:
        msg.add_attachment(cancel_ics, maintype="text", subtype="calendar",
                           filename="entfallene-termine.ics")
    for part in msg.walk():
        if part.get_content_type() != "text/calendar":
            continue
        is_cancel = (part.get_filename() or "").startswith("entfallene")
        part.set_param("method", "CANCEL" if is_cancel else "REQUEST")
        part.set_param("charset", "UTF-8")
    # Unkeyed Message-ID on purpose: a re-planned schedule is a NEW message —
    # keying it to the cid would make Gmail collapse the new draft into the old.
    return _stamp(msg)


_SESS_CANCEL = {
    "de": ("Termin abgesagt · {when}", "Hallo {name},",
           "unser Termin am {when} entfällt. Die angehängte Absage entfernt ihn "
           "automatisch aus deinem Kalender.",
           "Wenn du magst, finden wir gemeinsam einen neuen Termin — antworte "
           "einfach auf diese E-Mail.",
           "Herzlich,"),
    "en": ("Appointment cancelled · {when}", "Hi {name},",
           "our call on {when} is cancelled. The attached cancellation removes it "
           "from your calendar automatically.",
           "If you like, we'll find a new time together — simply reply to this "
           "email.",
           "Warmly,"),
    "es": ("Cita cancelada · {when}", "Hola {name}:",
           "nuestra sesión del {when} queda cancelada. La anulación adjunta la "
           "elimina automáticamente de tu calendario.",
           "Si quieres, buscamos juntas una nueva fecha — basta con responder a "
           "este correo.",
           "Un abrazo,"),
}


def build_session_cancel_email(to_email: str, name: str, session: dict,
                               language: str, cancel_ics: bytes) -> EmailMessage:
    """A cancelled programme call must LEAVE the client's calendar.

    Without this, the console's ✕ freed the slot on /book and told nobody —
    the client would have sat down for a call that no longer existed.
    """
    from . import booking as _b
    co, c = cfg.company(), cfg.config()
    lang = language if language in _SESS_CANCEL else "de"
    subj, g1, g2, g3, g4 = _SESS_CANCEL[lang]
    when = _b.format_when(session.get("utc") or session["start_utc"], lang)
    e = html.escape
    msg = EmailMessage()
    msg["Subject"] = subj.format(when=when)
    msg["From"] = f'{c.get("from_name","Auralis Natura")} <{c.get("from_email","")}>'
    msg["To"] = to_email
    msg.set_content(f"{g1.format(name=name)}\n\n{g2.format(when=when)}\n\n"
                    f"{g3}\n\n{g4}\nDesiree\n\n{_disc(lang)}")
    _tp, _tz = _tile_of(session.get("utc") or session.get("start_utc") or "")
    _finish_v2(msg, mailv2.render_cancel(name, lang, when, _tp, _tz), lang)
    msg.add_attachment(cancel_ics, maintype="text", subtype="calendar",
                       filename="absage.ics")
    for part in msg.walk():
        if part.get_content_type() == "text/calendar":
            part.set_param("method", "CANCEL")
            part.set_param("charset", "UTF-8")
    return _stamp(msg)


def build_internal_alert(subject: str, lines: list[str]) -> EmailMessage:
    """A plain notice to the practice inbox — deliberately unstyled.

    Used for operational events that need Desiree's eyes rather than a client's:
    a Stripe payment arriving, or worse, a payment that could not be matched to a
    package. Client mail gets the v2 templates; a note to yourself gets to be a
    note. Pair with notify_internal() so it sends regardless of email_mode.
    """
    c = cfg.config()
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = f'{c.get("from_name","Auralis Natura")} <{c.get("from_email","")}>'
    msg["To"] = c.get("smtp_user") or c.get("from_email", "")
    msg.set_content("\n".join(lines) + "\n")
    return _stamp(msg)


def build_social_package_email(week: str, plan: dict, zip_path=None,
                               zip_stats: dict | None = None) -> EmailMessage:
    """The week's approved posts, mailed to the practice inbox.

    notify_internal() semantics (send-now-to-self, .eml audit): this is
    Desiree mailing herself work material, not client communication — no
    review gate applies. The ZIP rides along only under 15 MB; a reel-heavy
    week would bounce at Gmail's 25 MB wall, so past the threshold the mail
    carries the captions and points at the console download instead.
    """
    from . import social as _social
    c = cfg.config()
    approved = [s for s in plan.get("slots", []) if s.get("approved")]
    e = html.escape
    rows = ""
    for s in approved:
        cap = _social.assemble_caption(s)
        rows += (f'<div style="margin:0 0 18px;padding:14px 16px;background:#FFFCF6;'
                 f'border:1px solid #DCD2C2">'
                 f'<b>{e(s["id"])} · {e(s["kind"].upper())} · {e(s["day"])} {e(s["time"])}</b>'
                 f'<pre style="white-space:pre-wrap;font-family:inherit;font-size:14px;'
                 f'margin:8px 0 0">{e(cap)}</pre></div>')
    msg = EmailMessage()
    msg["Subject"] = f"Social-Wochenpaket · {week} · {len(approved)} Posts"
    msg["From"] = f'{c.get("from_name","Auralis Natura")} <{c.get("from_email","")}>'
    msg["To"] = c.get("smtp_user") or c.get("from_email", "")
    text = f"Wochenpaket {week}: {len(approved)} freigegebene Posts.\n\n" + \
        "\n\n----\n\n".join(f"{s['id']} · {s['kind']} · {s['day']} {s['time']}\n\n"
                            + _social.assemble_caption(s) for s in approved)
    msg.set_content(text)
    _finish_v2(msg, mailv2.render_social(week, approved), "de")
    size = zip_path.stat().st_size if zip_path and zip_path.exists() else 0
    if zip_path and 0 < size < 15 * 1024 * 1024:
        msg.add_attachment(zip_path.read_bytes(), maintype="application", subtype="zip",
                           filename=zip_path.name)
    return _stamp(msg)


def build_feedback_email(to_email: str, name: str, language: str) -> EmailMessage:
    co = cfg.company(); c = cfg.config()
    lang = language if language in _FEEDBACK else "en"
    subj, g1, g2, g3, g4 = _FEEDBACK[lang]
    msg = EmailMessage()
    msg["Subject"] = subj
    msg["From"] = f'{c.get("from_name","Auralis Natura")} <{c.get("from_email","")}>'
    msg["To"] = to_email
    msg.set_content(f"{g1.format(name=name)}\n\n{g2}\n\n{g3}\n\n{g4}\nDesiree\n\n{_disc(lang)}")
    _finish_v2(msg, mailv2.render_feedback(name, lang), lang)
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




    langs = {"de": "Deutsch", "en": "English", "es": "Español"}

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
    _first, _, _last = name.partition(" ")
    _kv = [("Alter", (str(p.get("age")) + " Jahre") if p.get("age") else "", False),
           ("Themen", " · ".join(syms), False),
           ("Seit", _SINCE_DE.get(p.get("since"), p.get("since") or ""), False),
           ("Lebensphase", _STAGE_DE.get(p.get("life_stage"), p.get("life_stage") or ""), False),
           ("Bisher versucht", p.get("tried") or "", False),
           ("Erkrankungen", p.get("conditions") or "", False),
           ("Medikamente", p.get("medications") or "", False),
           ("Nachricht", note or "", False)]
    _scales = [(_SCALE_DE.get(k, k), int(v)) for k, v in (p.get("scales") or {}).items()]
    _tzname = _tile_of("")[1]
    _finish_v2(msg, mailv2.render_briefing(
        _first, _last or "—", when_local, _tzname,
        langs.get(language, language), email, p.get("goal") or "",
        _kv, _scales, booking_id,
        flags=", ".join(_FLAG_DE.get(f, f) for f in flags)), "de")
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
    # time_ns like deliver(): two notifications in the same second must not
    # overwrite each other's audit copy
    path = outbox / f"notify-{time.time_ns()}.eml"
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
                    language: str = "de", booking_id: str = "",
                    slot_utc: str = "") -> EmailMessage:
    co, c = cfg.company(), cfg.config()
    lang = language if language in _ACK else "de"
    subj, g1, g2, wlabel, g3, g4, g5 = _ACK[lang]
    e = html.escape



    text = (f"{g1.format(name=name)}\n\n{g2}\n\n{wlabel}: {when_local}\n\n{g3}\n\n{g4}\n\n"
            f"{g5}\nDesiree\n\n{co.get('brand','')} · {co.get('email','')}")

    msg = EmailMessage()
    msg["Subject"] = subj
    msg["From"] = f'{c.get("from_name","Auralis Natura")} <{c.get("from_email","")}>'
    msg["To"] = to_email
    msg.set_content(text)
    _tp, _tz = _tile_of(slot_utc)
    _finish_v2(msg, mailv2.render_ack(name, lang, _tp, _tz, when_local), lang)
    return _stamp(msg, f"ack-{booking_id}" if booking_id else "")


def send_now(msg: EmailMessage, tag: str = "bookings") -> dict:
    """Send immediately, and always keep the .eml.

    Same reasoning as notify_internal(): email_mode governs mail that carries
    Desiree's judgement and therefore needs her eyes. This one carries none.
    """
    _stamp(msg)
    outbox = cfg.OUTPUT_DIR / tag / "ack"
    outbox.mkdir(parents=True, exist_ok=True)
    # time_ns, not seconds: two bookings in the same second used to collide
    # here and the first acknowledgement's audit copy was silently replaced —
    # found because a client's ack was missing from her document drawer.
    path = outbox / f"ack-{time.time_ns()}.eml"
    path.write_bytes(bytes(msg))
    pw = os.environ.get("AURALIS_SMTP_PASSWORD", cfg.config().get("smtp_password", ""))
    if not pw:
        return {"ack": "no AURALIS_SMTP_PASSWORD — not sent", "eml": str(path)}
    return {"ack": _smtp_send(msg).get("send", "?"), "eml": str(path)}
