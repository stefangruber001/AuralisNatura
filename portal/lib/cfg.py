"""Config + paths + env-secret resolution for the Auralis portal.

Secrets ALWAYS come from environment variables when present; the JSON files hold
dev defaults / placeholders only. Never commit real secrets.
"""
from __future__ import annotations
import json, os, functools, threading
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent          # portal/
CONFIG_DIR = ROOT / "config"
WEB_DIR = ROOT / "web"
ASSETS_DIR = ROOT / "assets"
OUTPUT_DIR = ROOT / "output_docs"
OUTPUT_DIR.mkdir(exist_ok=True)

# env var -> the config.json key it overrides
_ENV = {
    "AURALIS_API_KEY": "api_key",
    "AURALIS_SECRET": "secret_key",
    "AURALIS_SMTP_PASSWORD": "smtp_password",
    "AURALIS_FROM_EMAIL": "from_email",
    "AURALIS_BOOKING_URL": "booking_review_url",
    "AURALIS_AGENT_PROVIDER": "agent_provider",
    "AURALIS_EMAIL_MODE": "email_mode",
    "AURALIS_PUBLIC_BASE_URL": "public_base_url",
    # Instagram Graph API (Social tab): identifiers + secrets live ONLY in
    # /etc/auralis/portal.env, never in a JSON config that gets backed up around
    "AURALIS_IG_USER_ID": "ig_user_id",
    "AURALIS_IG_TOKEN": "ig_token",
    "AURALIS_IG_APP_ID": "ig_app_id",
    "AURALIS_IG_APP_SECRET": "ig_app_secret",
    # Stripe: only the webhook SIGNING secret is ever needed. Verifying a
    # signature and reading the event body requires no API call, so no sk_ key
    # exists anywhere in this system.
    "AURALIS_STRIPE_WEBHOOK_SECRET": "stripe_webhook_secret",
}


def _load(name: str) -> dict:
    p = CONFIG_DIR / name
    with open(p, encoding="utf-8") as f:
        return json.load(f)


@functools.lru_cache(maxsize=None)
def config() -> dict:
    c = _load("config.json")
    for env, key in _ENV.items():
        v = os.environ.get(env)
        if v:
            c[key] = v
    return c


@functools.lru_cache(maxsize=None)
def company() -> dict:
    return _load("company.json")


@functools.lru_cache(maxsize=None)
def report_engine() -> dict:
    return _load("report_engine.json")


def clients() -> dict:
    """Not cached — mutated at runtime (invite / password reset). Seeds from the
    committed example on first run so a fresh clone works (clients.json is
    git-ignored: it holds logins + consent and must survive `git reset --hard`)."""
    p = CONFIG_DIR / "clients.json"
    if not p.exists():
        example = CONFIG_DIR / "clients.example.json"
        seed = _load("clients.example.json") if example.exists() else {"clients": {}}
        seed.pop("_comment", None)
        seed.setdefault("clients", {})
        save_clients(seed)
    return _load("clients.json")


def save_clients(data: dict) -> None:
    tmp = CONFIG_DIR / "clients.json.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    tmp.replace(CONFIG_DIR / "clients.json")


def is_production() -> bool:
    return os.environ.get("AURALIS_ENV", "").lower() in ("production", "prod")


def data_key() -> bytes:
    """Key for encrypting the backbone. Required from env in production; a local
    dev key file is used otherwise (gitignored, never in prod)."""
    from cryptography.fernet import Fernet
    env = os.environ.get("AURALIS_DATA_KEY")
    if env:
        env = env.strip()
        try:                                   # a real 44-char urlsafe-b64 Fernet key?
            Fernet(env.encode()); return env.encode()
        except Exception:
            return _derive(env)                # otherwise treat as a passphrase
    if is_production():
        raise RuntimeError(
            "AURALIS_DATA_KEY must be set in production — refusing a throwaway dev key "
            "(would defeat encryption-at-rest and risk permanent data loss).")
    devfile = ROOT / ".dev_data.key"
    if devfile.exists():
        return devfile.read_bytes().strip()
    k = Fernet.generate_key()
    devfile.write_bytes(k)
    return k


def _derive(passphrase: str) -> bytes:
    import base64, hashlib
    return base64.urlsafe_b64encode(hashlib.sha256(passphrase.encode()).digest())


_DEV_DEFAULTS = {"dev-staff-key-change-me", "dev-secret-change-me",
                 "REPLACE_WITH_A_LONG_RANDOM_STRING", "change-me"}


def validate_secrets() -> None:
    """Fail closed at startup if real secrets are missing in production."""
    if not is_production():
        return
    c = config()
    bad = [name for name, key in (("AURALIS_API_KEY", "api_key"), ("AURALIS_SECRET", "secret_key"))
           if str(c.get(key, "")) in _DEV_DEFAULTS or not c.get(key)]
    if bad:
        raise RuntimeError(f"Refusing to start in production with dev/empty secrets: {bad}. "
                           "Set them via environment variables.")
    if c.get("require_api_key") is not True:
        raise RuntimeError("Refusing to start in production with require_api_key disabled.")
    data_key()  # raises if AURALIS_DATA_KEY missing in prod


def reset_caches():
    config.cache_clear(); company.cache_clear(); report_engine.cache_clear()


# fields Desiree may edit from the Betriebskonsole (Stammdaten)
COMPANY_EDITABLE = {
    "legal_name", "owner", "email", "phone", "web", "instagram",
    "address_lines", "nif", "register_no", "bank", "vat_rate", "vat_note",
    "meet_link", "booking_note",
}


def save_company(updates: dict) -> dict:
    """Merge whitelisted fields into company.json and refresh the cache."""
    data = _load("company.json")
    for k, v in (updates or {}).items():
        if k in COMPANY_EDITABLE:
            data[k] = v
    tmp = CONFIG_DIR / "company.json.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    tmp.replace(CONFIG_DIR / "company.json")
    reset_caches()
    return data


_CLIENTS_LOCK = threading.RLock()


def allocate_client(name: str, email: str, language: str = "de",
                    status: str = "active", password_hash: str = "",
                    phone: str = "") -> str:
    """Create a clients.json entry with the next free AN-id and return the id.
    Leads are created with an empty password hash (login impossible) until
    credentials are issued from the console. If an entry with the same email
    already exists (any status), its id is returned instead of a duplicate."""
    with _CLIENTS_LOCK:
        data = clients()
        data.setdefault("clients", {})
        if email:
            for cid, info in data["clients"].items():
                if info.get("email", "").strip().lower() == email.strip().lower():
                    return cid
        nums = [int(c.split("-")[1]) for c in data["clients"] if c.startswith("AN-")
                and c.split("-")[1].isdigit()]
        try:
            from . import store as _store
            nums += [int(r["client_id"].split("-")[1]) for r in _store.list_records()
                     if r["client_id"].startswith("AN-") and r["client_id"].split("-")[1].isdigit()]
        except Exception:
            pass
        n = (max(nums) + 1) if nums else 1
        cid = f"AN-{n:04d}"
        import datetime as _dt
        data["clients"][cid] = {"name": name, "email": email, "language": language,
                                "phone": phone, "password": password_hash, "status": status,
                                "created": _dt.date.today().isoformat(),
                                "consent": {"coaching_not_medical": None, "gdpr_health_data": None, "version": "1.0"}}
        assign_login_id(cid, name, data)
        save_clients(data)
        return cid


def slug_login_id(name: str) -> str:
    """'Maria Moser' → 'maria.moser'. Empty for a name with nothing usable in it.

    Umlauts are transliterated the German way (ä→ae), not stripped: a client
    called Müller expecting 'mueller' and finding 'mller' would reasonably
    assume the mail was broken.
    """
    import unicodedata
    s = (name or "").strip().lower()
    for a, b in (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss"),
                 ("å", "aa"), ("æ", "ae"), ("ø", "oe")):
        s = s.replace(a, b)
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    out, prev_dot = [], True          # leading separators are dropped
    for ch in s:
        if ch.isalnum() and ch.isascii():
            out.append(ch); prev_dot = False
        elif not prev_dot:
            out.append("."); prev_dot = True
    return "".join(out).strip(".")[:40]


def assign_login_id(cid: str, name: str, data: dict) -> str:
    """A unique login id for one client. Caller holds _CLIENTS_LOCK and saves."""
    base = slug_login_id(name) or cid.lower()
    taken = {str(i.get("login_id", "")).lower() for k, i in data.get("clients", {}).items()
             if k != cid}
    taken |= {k.lower() for k in data.get("clients", {}) if k != cid}
    lid, n = base, 2
    while lid in taken:
        lid = f"{base}{n}"; n += 1
    data["clients"][cid]["login_id"] = lid
    return lid


def ensure_login_ids() -> int:
    """Backfill login ids for clients created before they existed.

    Runs once at startup. Without it, everyone onboarded so far could still
    only sign in with AN-0007 while their mail told them to use their name.
    """
    with _CLIENTS_LOCK:
        data = clients()
        changed = 0
        for cid, info in list(data.get("clients", {}).items()):
            if not str(info.get("login_id", "")).strip():
                assign_login_id(cid, info.get("name", ""), data)
                changed += 1
        if changed:
            save_clients(data)
        return changed


def resolve_login(identifier: str) -> tuple[str, dict] | tuple[None, None]:
    """Find a client by login id or by AN-id, ignoring case and stray spaces.

    Phone keyboards capitalise the first letter of anything that looks like a
    word, so 'Maria.moser' has to work exactly as well as 'maria.moser'.
    """
    key = (identifier or "").strip().lower()
    if not key:
        return None, None
    for cid, info in clients().get("clients", {}).items():
        if cid.lower() == key or str(info.get("login_id", "")).lower() == key:
            return cid, info
    return None, None


def set_client_language(cid: str, language: str) -> bool:
    """Record the language the client themselves last chose.

    Every customer-facing message — credentials, reminder, report, feedback —
    reads clients.json for its language, so this single field decides what
    language a person is written to in. When someone fills in the booking form
    in English, that IS their answer to the question, and it has to overwrite
    whatever was on the record before.

    Deliberately narrow: only the language field, only for a known id, and only
    for a language we actually have copy for.
    """
    if language not in ("de", "en", "es"):
        return False
    with _CLIENTS_LOCK:
        data = clients()
        info = data.get("clients", {}).get(cid)
        if not info or info.get("language") == language:
            return False
        info["language"] = language
        save_clients(data)
        return True
