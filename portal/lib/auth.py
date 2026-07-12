"""Auth for the Auralis portal.

- Staff (Betriebskonsole): a shared API key in the `X-Auralis-Key` header.
  In production this sits *behind* Cloudflare Access as a second factor.
- Clients (portal): PBKDF2-hashed passwords + a signed, expiring bearer token
  (HMAC) so the intake can be submitted without a long-lived cookie.
"""
from __future__ import annotations
import hashlib, hmac, os, base64, json, time, secrets
from . import cfg

_PBKDF2_ROUNDS = 240_000


# ---------- passwords ----------
def hash_password(password: str) -> str:
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _PBKDF2_ROUNDS)
    return f"pbkdf2_sha256${_PBKDF2_ROUNDS}${salt.hex()}${dk.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, rounds, salt_hex, hash_hex = stored.split("$")
        assert algo == "pbkdf2_sha256"
        dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt_hex), int(rounds))
        return hmac.compare_digest(dk.hex(), hash_hex)
    except Exception:
        return False


def new_password(length: int = 12) -> str:
    # readable, no ambiguous chars
    alphabet = "abcdefghjkmnpqrstuvwxyzABCDEFGHJKMNPQRSTUVWXYZ23456789"
    return "".join(secrets.choice(alphabet) for _ in range(length))


# ---------- staff API key ----------
def check_api_key(header_value: str | None) -> bool:
    c = cfg.config()
    if not c.get("require_api_key", True):
        return True
    expected = c.get("api_key", "")
    return bool(header_value) and hmac.compare_digest(str(header_value), str(expected))


# ---------- client bearer tokens (HMAC, expiring) ----------
def _secret() -> bytes:
    return str(cfg.config().get("secret_key", "")).encode("utf-8")


def issue_token(client_id: str, ttl_seconds: int = 24 * 3600, scope: str = "") -> str:
    body = {"cid": client_id, "exp": int(time.time()) + ttl_seconds}
    if scope:
        body["scope"] = scope
    raw = json.dumps(body, separators=(",", ":")).encode("utf-8")
    b = base64.urlsafe_b64encode(raw).decode().rstrip("=")
    sig = hmac.new(_secret(), b.encode(), hashlib.sha256).hexdigest()
    return f"{b}.{sig}"


def verify_token(token: str | None, scope: str = "") -> str | None:
    """Return the client id iff the token is valid AND its scope matches. Default
    scope="" means only full (unscoped) session tokens pass — so a narrow, scoped
    token (e.g. a 90s report token) can never be used on general client endpoints."""
    if not token or "." not in token:
        return None
    b, sig = token.rsplit(".", 1)
    good = hmac.new(_secret(), b.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(sig, good):
        return None
    try:
        pad = "=" * (-len(b) % 4)
        body = json.loads(base64.urlsafe_b64decode(b + pad))
    except Exception:
        return None
    if int(body.get("exp", 0)) < int(time.time()):
        return None
    if str(body.get("scope", "")) != scope:
        return None
    return body.get("cid")
