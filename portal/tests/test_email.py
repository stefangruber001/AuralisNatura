#!/usr/bin/env python3
"""The email path, in-process — no network, no Gmail account needed.

The one thing worth pinning down here is the drafts folder. mailer._imap_draft()
APPENDs the finished report mail to it and catches every exception, returning a
string in a dict that nothing reads. So if the folder name is wrong the report
mail is simply lost — no traceback, no log line, no client. Gmail localises that
folder ('[Gmail]/Entwürfe' on a German account, '[Gmail]/Borradores' on a Spanish
one), which is exactly the shape of bug that survives a green test suite and
then eats a real client's report.
"""
import sys, pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from lib import mailer  # noqa: E402

FAILURES = []


def check(name, got, want):
    if got == want:
        print(f"  ok   {name}")
    else:
        print(f"  FAIL {name}\n         got  {got!r}\n         want {want!r}")
        FAILURES.append(name)


class FakeIMAP:
    """Just enough of imaplib.IMAP4 for drafts_mailbox()."""

    def __init__(self, lines, typ="OK", raises=False):
        self._lines, self._typ, self._raises = lines, typ, raises

    def list(self):
        if self._raises:
            raise RuntimeError("connection reset by peer")
        return self._typ, [l.encode() for l in self._lines]


GMAIL_EN = [
    r'(\HasNoChildren) "/" "INBOX"',
    r'(\HasNoChildren \All) "/" "[Gmail]/All Mail"',
    r'(\HasNoChildren \Drafts) "/" "[Gmail]/Drafts"',
    r'(\HasNoChildren \Sent) "/" "[Gmail]/Sent Mail"',
]
# IMAP-UTF-7, which is how a German Gmail actually reports it on the wire.
GMAIL_DE = [r'(\HasNoChildren \Drafts) "/" "[Gmail]/Entw&APw-rfe"']
GMAIL_ES = [r'(\HasNoChildren \Drafts) "/" "[Gmail]/Borradores"']

print("drafts_mailbox() — resolved by the \\Drafts flag, not by name")
check("english gmail",        mailer.drafts_mailbox(FakeIMAP(GMAIL_EN)), '"[Gmail]/Drafts"')
check("german gmail",         mailer.drafts_mailbox(FakeIMAP(GMAIL_DE)), '"[Gmail]/Entw&APw-rfe"')
check("spanish gmail",        mailer.drafts_mailbox(FakeIMAP(GMAIL_ES)), '"[Gmail]/Borradores"')
check("unquoted mailbox name",
      mailer.drafts_mailbox(FakeIMAP([r'(\HasNoChildren \Drafts) "/" Drafts'])), '"Drafts"')

print("\nfalls back to the Gmail default rather than raising")
check("no \\Drafts advertised",
      mailer.drafts_mailbox(FakeIMAP([r'(\HasNoChildren) "/" "INBOX"'])), '"[Gmail]/Drafts"')
check("LIST returns NO",      mailer.drafts_mailbox(FakeIMAP([], typ="NO")), '"[Gmail]/Drafts"')
check("LIST raises",          mailer.drafts_mailbox(FakeIMAP([], raises=True)), '"[Gmail]/Drafts"')

print("\nno credential -> a stated skip, never a silent success")
saved = mailer.os.environ.pop("AURALIS_SMTP_PASSWORD", None)
try:
    import lib.cfg as cfg
    real = cfg.config
    cfg.config = lambda: {"email_mode": "draft", "smtp_password": ""}
    try:
        r = mailer._imap_draft(object())          # never reaches the network
        check("draft without a password", r.get("draft"),
              "skipped — no AURALIS_SMTP_PASSWORD set")
        r = mailer._smtp_send(object())
        check("send without a password", r.get("send"),
              "skipped — no AURALIS_SMTP_PASSWORD set")
    finally:
        cfg.config = real
finally:
    if saved is not None:
        mailer.os.environ["AURALIS_SMTP_PASSWORD"] = saved

print()
if FAILURES:
    print(f"{len(FAILURES)} FAILED: {', '.join(FAILURES)}")
    sys.exit(1)
print("all email checks passed")
