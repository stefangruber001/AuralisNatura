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
    """Not cached — mutated at runtime (invite / password reset)."""
    return _load("clients.json")


def save_clients(data: dict) -> None:
    tmp = CONFIG_DIR / "clients.json.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    tmp.replace(CONFIG_DIR / "clients.json")


def data_key() -> bytes:
    """32-byte key for encrypting the backbone. From env in production; a
    local dev key file otherwise (gitignored, never in prod)."""
    env = os.environ.get("AURALIS_DATA_KEY")
    if env:
        # accept a urlsafe-base64 Fernet key or a raw passphrase
        return env.encode() if len(env) >= 44 else _derive(env)
    devfile = ROOT / ".dev_data.key"
    if devfile.exists():
        return devfile.read_bytes().strip()
    from cryptography.fernet import Fernet
    k = Fernet.generate_key()
    devfile.write_bytes(k)
    return k


def _derive(passphrase: str) -> bytes:
    import base64, hashlib
    return base64.urlsafe_b64encode(hashlib.sha256(passphrase.encode()).digest())


def reset_caches():
    config.cache_clear(); company.cache_clear(); report_engine.cache_clear()
