#!/usr/bin/env python3
"""S6: automatic Instagram publishing — queue, schedule, mocked Graph API.

No call ever reaches Meta from here: the api= layer is a mock that records
every request, including the async video-processing dance for reels.
"""
from __future__ import annotations
import datetime as dt
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import _sandbox  # noqa: F401
import os
os.environ.setdefault("AURALIS_API_KEY", "test-key")
os.environ["AURALIS_IG_USER_ID"] = "1789"
os.environ["AURALIS_IG_TOKEN"] = "test-token"

from lib import cfg, social, instagram, auth  # noqa: E402
cfg.reset_caches()
from server.app import app  # noqa: E402

KEY = {"X-Auralis-Key": "test-key"}
FAILS: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    print(f"  {'ok  ' if ok else 'FAIL'} {label}" + (f"\n         {detail}" if detail and not ok else ""))
    if not ok:
        FAILS.append(label)


class MockGraph:
    def __init__(self, fail_on=None):
        self.calls = []
        self.fail_on = fail_on or set()
        self.n = 0

    def __call__(self, method, path, params):
        self.calls.append((method, path, dict(params)))
        if path.endswith("/media") and method == "POST":
            if "container" in self.fail_on:
                return {"error": {"message": "bad media"}}
            self.n += 1
            return {"id": f"c{self.n}"}
        if path.endswith("/media_publish"):
            if "publish" in self.fail_on:
                return {"error": {"message": "publish denied"}}
            return {"id": f"m{params['creation_id']}"}
        if "status_code" in params.get("fields", ""):
            return {"status_code": "FINISHED"}
        if params.get("fields") == "username":
            return {"username": "auralis_natura"}
        return {}


def model(prompt, timeout):
    return {"strategy": {"theme": "T", "rationale": "R"}, "slots": [
        {"kind": "post", "day": "Montag", "time": "09:00", "hook": "h",
         "caption_de": "DE.", "caption_en": "EN.", "caption_es": "ES.",
         "hashtags": ["#a"], "alt_text": "x", "cta": "",
         "visual": {"template": "quote", "headline": "H", "sub": "S"}},
        {"kind": "carousel", "day": "Dienstag", "time": "10:00", "hook": "h",
         "caption_de": "DE.", "caption_en": "", "caption_es": "", "hashtags": [],
         "alt_text": "", "cta": "",
         "visual": {"template": "carousel",
                    "slides": [{"title": f"S{i}", "body": "b"} for i in range(5)]}},
        {"kind": "story", "day": "Mittwoch", "time": "18:00", "hook": "h",
         "caption_de": "DE.", "caption_en": "", "caption_es": "", "hashtags": [],
         "alt_text": "", "cta": "", "visual": {"template": "story", "question": "F?"}},
    ]}


def run() -> int:
    print("· schedule math (DST-safe local time)")
    check("summer: Mi 18:00 Madrid = 16:00Z",
          instagram.publish_at_utc("2026-W34", "Mittwoch", "18:00") == "2026-08-19T16:00:00+00:00",
          instagram.publish_at_utc("2026-W34", "Mittwoch", "18:00"))
    check("winter: Mi 18:00 Madrid = 17:00Z",
          instagram.publish_at_utc("2026-W50", "Mittwoch", "18:00") == "2026-12-09T17:00:00+00:00")
    check("connected() sees the env credentials", instagram.connected())

    print("\n· approving queues; un-approving un-queues")
    plan = social.run_strategy(claude=model)
    wk = plan["week"]
    c = app.test_client()
    for s in plan["slots"]:
        c.post(f"/api/social/week/{wk}/slot/{s['id']}/render", headers=KEY)
    r = c.post(f"/api/social/week/{wk}/slot/slot-01", headers=KEY, json={"approved": True})
    s = r.get_json()["slot"]
    check("approved → queued with a publish time",
          s["publish_status"] == "queued" and s["publish_at"].endswith("+00:00"), str(s.get("publish_at")))
    r = c.post(f"/api/social/week/{wk}/slot/slot-01", headers=KEY, json={"approved": False})
    check("un-approved → queue entry gone", "publish_status" not in r.get_json()["slot"])

    print("\n· the queue walker publishes what is due, in every format")
    for s in social.load_plan(wk)["slots"]:
        c.post(f"/api/social/week/{wk}/slot/{s['id']}", headers=KEY, json={"approved": True})
    mock = MockGraph()
    late = dt.datetime(2099, 1, 1, tzinfo=dt.timezone.utc)
    out = instagram.run_queue(now=late, api=mock)
    check("all three slots published", out["published"] == 3 and out["failed"] == 0, str(out))
    plan2 = social.load_plan(wk)
    check("statuses + media ids persisted",
          all(s["publish_status"] == "published" and s.get("media_id") for s in plan2["slots"]))
    posts = [c_ for c_ in mock.calls if c_[1] == "/1789/media"]
    check("carousel built 5 children + 1 container",
          sum(1 for m, p, prm in mock.calls if prm.get("is_carousel_item")) == 5
          and any(prm.get("media_type") == "CAROUSEL" for _, _, prm in mock.calls))
    check("story used STORIES media_type",
          any(prm.get("media_type") == "STORIES" for _, _, prm in mock.calls))
    check("caption is the stacked assemble_caption text",
          any("DE.\n\n·\n\nEN.\n\n·\n\nES.\n\n#a" == prm.get("caption")
              for _, _, prm in mock.calls))
    check("media URLs are signed public asset URLs",
          all("/pub/social/" in prm.get("image_url", prm.get("video_url", "/pub/social/"))
              for _, _, prm in mock.calls if "image_url" in prm or "video_url" in prm))
    check("published slots are not re-published",
          instagram.run_queue(now=late, api=mock)["due"] == 0)

    print("\n· not yet due stays queued; failures stay visible")
    plan3 = social.run_strategy(claude=model)   # fresh plan, same week — overwrites
    for s in plan3["slots"][:1]:
        c.post(f"/api/social/week/{wk}/slot/{s['id']}", headers=KEY, json={"approved": True})
    early = dt.datetime(2000, 1, 1, tzinfo=dt.timezone.utc)
    out = instagram.run_queue(now=early, api=MockGraph())
    check("nothing due in the past-relative now", out["due"] == 0 and out["published"] == 0)
    out = instagram.run_queue(now=late, api=MockGraph(fail_on={"publish"}))
    check("failure recorded, queue walk survives", out["failed"] == 1, str(out))
    s = social.load_plan(wk)["slots"][0]
    check("slot carries the error for the console",
          s["publish_status"] == "failed" and "publish denied" in s["publish_error"])

    print("\n· the public asset door")
    sid = "slot-01"
    base = cfg.OUTPUT_DIR / "social" / "weeks" / wk / "assets" / sid
    fname = sorted(p.name for p in base.iterdir() if p.suffix == ".png")[0]
    tok = instagram.asset_token(wk, sid, fname)
    r = c.get(f"/pub/social/{tok}/{wk}/{sid}/{fname}")
    check("signed URL serves the file WITHOUT the staff key",
          r.status_code == 200 and r.data[:4] == b"\x89PNG")
    r = c.get(f"/pub/social/{tok}/{wk}/{sid}/../../../../clients.json")
    check("token pins the exact path", r.status_code == 404)
    tok2 = auth.issue_token(f"{wk}/{sid}/{fname}", ttl_seconds=600)   # WRONG scope
    check("a session token does not open the door",
          c.get(f"/pub/social/{tok2}/{wk}/{sid}/{fname}").status_code == 404)

    print("\n· token refresh (mocked)")
    def refresh_api(method, path, params):
        assert params["grant_type"] == "fb_exchange_token"
        return {"access_token": "fresh-token", "expires_in": 5184000}
    os.environ["AURALIS_IG_APP_ID"] = "app"
    os.environ["AURALIS_IG_APP_SECRET"] = "secret"
    cfg.reset_caches()
    out = instagram.refresh_token(api=refresh_api)
    check("refresh stores the new token + expiry", out["ok"] and social.state()["ig_token"]["token"] == "fresh-token")
    check("subsequent calls use the cached fresh token", instagram._token() == "fresh-token")

    print("\n" + ("SOCIAL PUBLISH ALL PASSED ✓" if not FAILS else f"{len(FAILS)} FAILED: {FAILS}"))
    return 0 if not FAILS else 1


if __name__ == "__main__":
    sys.exit(run())
