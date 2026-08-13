"""Social-Media module — config, materials, and (from S2 on) the weekly engine.

Design rules this module lives by:

* social.json carries FOUNDER INTENT only (sources, objective, cadence) behind a
  whitelist, exactly like company.json. Machine state — last runs, seen-hashes,
  scan status — lives in output_docs/social/state.json, so the whitelist stays
  honest and the updater/backup story is automatic (output_docs is symlinked and
  backed up on the server; a stray key can never be smuggled into config).
* Everything under output_docs/social/ resolves through cfg.OUTPUT_DIR AT CALL
  TIME — the test sandbox redirects that attribute after import, and a cached
  Path would write test artifacts into live data.
* No new dependencies. Uploads are validated by magic bytes (stdlib), the index
  is plain JSON, names are slugged the same way mailer._safe does it.
"""
from __future__ import annotations
import json
import re
import threading
import time
import uuid
from ipaddress import ip_address
from pathlib import Path
from urllib.parse import urlparse

from . import cfg

_LOCK = threading.RLock()

# ─────────────────────────────────────────────── config (founder intent) ────
SOCIAL_EDITABLE = {"objective_week", "objective_month", "cadence", "auto_strategy",
                   "agents"}
_AGENT_FIELDS = {"id", "name", "type", "urls", "keywords", "enabled"}
_MAX_AGENTS = 12
_MAX_URLS = 5


def _path() -> Path:
    return cfg.CONFIG_DIR / "social.json"


def social() -> dict:
    """Seed-on-first-read from the committed example, like cfg.clients()."""
    p = _path()
    if not p.exists():
        example = cfg.CONFIG_DIR / "social.example.json"
        try:
            seed = json.loads(example.read_text(encoding="utf-8")) if example.exists() else {}
        except Exception:
            seed = {}
        seed.pop("_comment", None)
        _write(_clean(seed))
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def _write(data: dict) -> None:
    tmp = _path().with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    tmp.replace(_path())


def _url_ok(u: str) -> bool:
    """http(s) to a public host — the scanner runs server-side, so a URL like
    http://127.0.0.1:5056/api/… would let a config edit probe the loopback."""
    try:
        p = urlparse(u)
    except Exception:
        return False
    if p.scheme not in ("http", "https") or not p.hostname:
        return False
    host = p.hostname.lower()
    if host in ("localhost",) or host.endswith(".local") or host.endswith(".internal"):
        return False
    try:
        if ip_address(host).is_private or ip_address(host).is_loopback \
           or ip_address(host).is_link_local or ip_address(host).is_reserved:
            return False
    except ValueError:
        pass                     # a normal hostname, not an IP literal
    return True


def _clean_agent(a: dict) -> dict | None:
    if not isinstance(a, dict):
        return None
    out = {
        "id": re.sub(r"[^a-z0-9-]", "", str(a.get("id", ""))[:40].lower()) or uuid.uuid4().hex[:8],
        "name": str(a.get("name", ""))[:120].strip() or "Quelle",
        "type": a.get("type") if a.get("type") in ("rss", "web") else "web",
        "keywords": str(a.get("keywords", ""))[:300],
        "enabled": bool(a.get("enabled")),
    }
    urls = []
    for u in (a.get("urls") or [])[:_MAX_URLS]:
        u = str(u).strip()[:500]
        if u and _url_ok(u):
            urls.append(u)
    out["urls"] = urls
    if out["enabled"] and not urls:
        out["enabled"] = False   # an enabled source with nothing to read is noise
    return out


def _clean(data: dict) -> dict:
    d = data if isinstance(data, dict) else {}
    cad = d.get("cadence") if isinstance(d.get("cadence"), dict) else {}
    agents = []
    seen_ids = set()
    for a in (d.get("agents") or [])[:_MAX_AGENTS]:
        ca = _clean_agent(a)
        if ca is None:
            continue
        while ca["id"] in seen_ids:
            ca["id"] += "x"
        seen_ids.add(ca["id"])
        agents.append(ca)
    return {
        "objective_week": str(d.get("objective_week", ""))[:2000],
        "objective_month": str(d.get("objective_month", ""))[:2000],
        "cadence": {
            "posts": max(0, min(7, int(cad.get("posts", 3) or 0))),
            "stories": max(0, min(7, int(cad.get("stories", 2) or 0))),
            "reels": max(0, min(7, int(cad.get("reels", 1) or 0))),
        },
        "auto_strategy": bool(d.get("auto_strategy", True)),
        "agents": agents,
    }


def save_social(updates: dict) -> dict:
    """Whitelist merge, then re-clean the WHOLE document — a bad value can no
    more enter via an untouched key than via the edited one."""
    with _LOCK:
        cur = social()
        for k, v in (updates or {}).items():
            if k in SOCIAL_EDITABLE:
                cur[k] = v
        clean = _clean(cur)
        _write(clean)
        return clean


# ───────────────────────────────────────────── machine state (not config) ───
def _social_dir() -> Path:
    p = cfg.OUTPUT_DIR / "social"
    p.mkdir(parents=True, exist_ok=True)
    return p


def state() -> dict:
    p = _social_dir() / "state.json"
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_state(data: dict) -> None:
    with _LOCK:
        p = _social_dir() / "state.json"
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(p)


# ─────────────────────────────────────────────────── materials (uploads) ────
# Desiree's own photos and texts — the raw material every strategy run may use.
_MAX_FILE = 20 * 1024 * 1024

# (magic-byte prefix check, kind). HEIC is deliberately absent: iPhone Safari
# transcodes to JPEG on web upload, and nothing server-side could decode HEIC.
_MAGIC = [
    (b"\xff\xd8\xff", "jpg"),
    (b"\x89PNG\r\n\x1a\n", "png"),
    (b"%PDF", "pdf"),
]


def _detect_kind(name: str, data: bytes) -> str | None:
    for magic, kind in _MAGIC:
        if data.startswith(magic):
            return kind
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    if ext in ("txt", "md"):
        try:
            data.decode("utf-8")
        except UnicodeDecodeError:
            return None
        if b"\x00" in data:
            return None
        return "txt" if ext == "txt" else "md"
    return None


def _safe_name(name: str) -> str:
    base = re.sub(r"[^A-Za-z0-9._-]+", "-", (name or "datei")).strip("-.")[:80]
    return base or "datei"


def _materials_dir() -> Path:
    p = _social_dir() / "materials"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _index_path() -> Path:
    return _materials_dir() / "_index.json"


def list_materials() -> list[dict]:
    p = _index_path()
    if not p.exists():
        return []
    try:
        items = json.loads(p.read_text(encoding="utf-8")).get("items", [])
    except Exception:
        return []
    # the index is a claim; the filesystem is the truth
    return [i for i in items if (_materials_dir() / i.get("file", "")).is_file()]


def _save_index(items: list[dict]) -> None:
    tmp = _index_path().with_suffix(".tmp")
    tmp.write_text(json.dumps({"items": items}, ensure_ascii=False, indent=2),
                   encoding="utf-8")
    tmp.replace(_index_path())


def add_material(filename: str, data: bytes, note: str = "") -> dict:
    if not data:
        raise ValueError("leere Datei")
    if len(data) > _MAX_FILE:
        raise ValueError("Datei größer als 20 MB")
    kind = _detect_kind(filename, data)
    if kind is None:
        raise ValueError("Nur JPG, PNG, WebP, PDF, TXT oder MD — "
                         "(iPhone-Fotos kommen über Safari automatisch als JPG an)")
    mid = uuid.uuid4().hex[:10]
    fname = f"{mid}-{_safe_name(filename)}"
    with _LOCK:
        (_materials_dir() / fname).write_bytes(data)
        items = list_materials()
        items.insert(0, {"id": mid, "file": fname, "note": str(note or "")[:300],
                         "kind": kind, "size": len(data),
                         "added": time.strftime("%Y-%m-%dT%H:%M")})
        _save_index(items)
    return items[0]


def set_material_note(mid: str, note: str) -> bool:
    with _LOCK:
        items = list_materials()
        for i in items:
            if i["id"] == mid:
                i["note"] = str(note or "")[:300]
                _save_index(items)
                return True
    return False


def delete_material(mid: str) -> bool:
    with _LOCK:
        items = list_materials()
        keep = [i for i in items if i["id"] != mid]
        if len(keep) == len(items):
            return False
        for i in items:
            if i["id"] == mid:
                (_materials_dir() / i["file"]).unlink(missing_ok=True)
        _save_index(keep)
        return True


def material_path(mid: str) -> Path | None:
    """Traversal-safe: the file must exist inside the materials dir AND be the
    one the index names — a crafted id can address nothing else."""
    for i in list_materials():
        if i["id"] == mid:
            base = _materials_dir().resolve()
            target = (base / i["file"]).resolve()
            if target.is_file() and str(target).startswith(str(base)):
                return target
    return None
