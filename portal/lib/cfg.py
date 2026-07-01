"""Config + paths + env-secret resolution for the Auralis portal.

Secrets ALWAYS come from environment variables when present; the JSON files hold
dev defaults / placeholders only. Never commit real secrets.
"""
from __future__ import annotations
import json, os, functools
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
