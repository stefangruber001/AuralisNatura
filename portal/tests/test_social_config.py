#!/usr/bin/env python3
"""Social tab S1: config whitelist, materials upload, and the body-size cap.

The cap test matters most: raising Flask's global MAX_CONTENT_LENGTH for photo
uploads must NOT loosen the 512 KB limit on any other route — that limit is the
API's DoS guard and it has to keep biting everywhere else.
"""
from __future__ import annotations
import io
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import _sandbox  # noqa: F401  — temp DB + config shield, restored at exit
import os
os.environ.setdefault("AURALIS_API_KEY", "test-key")

from server.app import app  # noqa: E402
from lib import social  # noqa: E402

KEY = {"X-Auralis-Key": "test-key"}
FAILS: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    print(f"  {'ok  ' if ok else 'FAIL'} {label}" + (f"\n         {detail}" if detail and not ok else ""))
    if not ok:
        FAILS.append(label)


# a real 1x1 PNG, then padded to megabytes for the size tests
_PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
    "0000000d49444154789c626001000000ffff03000006000557bfabd40000000049454e44ae426082")


def run() -> int:
    c = app.test_client()

    print("· config: seeded from the example, saved through the whitelist")
    r = c.get("/api/social/config", headers=KEY)
    check("config loads", r.status_code == 200)
    d = r.get_json()
    check("seeded agents present", len(d.get("agents", [])) >= 4)
    check("cadence default 3/2/1", d["cadence"] == {"posts": 3, "stories": 2, "reels": 1})
    check("no _comment leaked from the example", "_comment" not in d)

    r = c.post("/api/social/config", headers=KEY, json={
        "objective_week": "Sichtbarkeit für das Klarheit-Paket",
        "cadence": {"posts": 99, "stories": -3, "reels": 2},
        "secret_key": "evil", "email_mode": "send",
        "agents": [
            {"id": "ok1", "name": "Gute Quelle", "type": "rss",
             "urls": ["https://example.org/feed"], "enabled": True},
            {"id": "bad", "name": "Loopback", "type": "web",
             "urls": ["http://127.0.0.1:5056/api/clients"], "enabled": True},
            {"id": "bad2", "name": "FTP", "type": "web",
             "urls": ["ftp://example.org/x"], "enabled": True},
        ]})
    d = r.get_json()
    check("save 200", r.status_code == 200)
    check("objective saved", d["objective_week"].startswith("Sichtbarkeit"))
    check("cadence clamped to 0..7", d["cadence"] == {"posts": 7, "stories": 0, "reels": 2})
    check("unknown keys dropped", "secret_key" not in d and "email_mode" not in d)
    by_id = {a["id"]: a for a in d["agents"]}
    check("good https URL kept", by_id["ok1"]["urls"] == ["https://example.org/feed"])
    check("loopback URL stripped AND agent auto-disabled",
          by_id["bad"]["urls"] == [] and by_id["bad"]["enabled"] is False)
    check("non-http scheme stripped", by_id["bad2"]["urls"] == [])
    check("unauthenticated config rejected", c.get("/api/social/config").status_code == 401)

    print("\n· the 512 KB cap still bites everywhere except the upload door")
    big_json = {"pad": "x" * (600 * 1024)}
    r = c.post("/api/company", headers=KEY, json=big_json)
    check("600 KB JSON on /api/company → 413", r.status_code == 413)
    r = c.post("/api/social/config", headers=KEY, json=big_json)
    check("600 KB JSON on social config → 413 too", r.status_code == 413)

    print("\n· materials: upload, list, note, download, delete")
    photo = _PNG + b"\x00" * (5 * 1024 * 1024)
    r = c.post("/api/social/materials", headers=KEY, data={
        "file": (io.BytesIO(photo), "Retreat Foto (1).jpg"),
        "note": "Foto vom Retreat, Querformat"},
        content_type="multipart/form-data")
    check("5 MB photo accepted through the big door", r.status_code == 200, str(r.get_json()))
    mid = (r.get_json() or {}).get("item", {}).get("id", "")
    check("indexed with note", any(i["id"] == mid and "Retreat" in i["note"]
                                   for i in social.list_materials()))
    check("kind detected from magic bytes, not the .jpg name",
          next(i for i in social.list_materials() if i["id"] == mid)["kind"] == "png")

    r = c.post("/api/social/materials", headers=KEY, data={
        "file": (io.BytesIO(b"MZ\x90\x00 not an image"), "malware.jpg")},
        content_type="multipart/form-data")
    check("wrong magic bytes rejected", r.status_code == 400)

    r = c.post("/api/social/materials", headers=KEY, data={
        "file": (io.BytesIO("Notizen für Posts: Zyklus & Energie".encode()), "ideen.txt")},
        content_type="multipart/form-data")
    check("text file accepted", r.status_code == 200)

    r = c.post(f"/api/social/material/{mid}/note", headers=KEY, json={"note": "neu"})
    check("note updated", r.status_code == 200
          and next(i for i in social.list_materials() if i["id"] == mid)["note"] == "neu")

    r = c.get(f"/api/social/material/{mid}", headers=KEY)
    check("download round-trips the bytes", r.status_code == 200 and r.data == photo)
    # werkzeug collapses ../ segments before routing, so this lands on a
    # different endpoint entirely (405) — the material route never sees it.
    # The property under test is only: no file bytes come back.
    rt = c.get("/api/social/material/..%2f..%2fclients", headers=KEY)
    check("traversal id serves nothing", rt.status_code in (400, 404, 405))
    check("unknown id → 404", c.get("/api/social/material/deadbeef00", headers=KEY).status_code == 404)

    r = c.delete(f"/api/social/material/{mid}", headers=KEY)
    check("delete works", r.status_code == 200
          and all(i["id"] != mid for i in social.list_materials()))
    check("file really gone from disk", social.material_path(mid) is None)

    print("\n· oversize and unauthenticated uploads")
    r = c.post("/api/social/materials", headers=KEY, data={
        "file": (io.BytesIO(_PNG + b"\x00" * (24 * 1024 * 1024)), "huge.png")},
        content_type="multipart/form-data")
    check("24 MB rejected (20 MB module cap)", r.status_code == 400)
    r = c.post("/api/social/materials", data={
        "file": (io.BytesIO(_PNG), "x.png")}, content_type="multipart/form-data")
    check("upload without key rejected", r.status_code == 401)

    print("\n" + ("SOCIAL CONFIG ALL PASSED ✓" if not FAILS else f"{len(FAILS)} FAILED: {FAILS}"))
    return 0 if not FAILS else 1


if __name__ == "__main__":
    sys.exit(run())
