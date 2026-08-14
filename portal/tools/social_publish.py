#!/usr/bin/env python3
"""Publish-queue walker — the auralis-social-publish.timer entry (every 10 min).

Quiet by design: not connected, or nothing due → exit 0 having printed one
line. Also keeps the long-lived token alive: within ten days of expiry it
trades the token for a fresh one (needs app id/secret in portal.env).
"""
from __future__ import annotations
import datetime as dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from lib import instagram, social  # noqa: E402


def main() -> int:
    if not instagram.connected():
        print("instagram: nicht verbunden — Queue bleibt stehen")
        return 0
    st = social.state()
    exp = (st.get("ig_token") or {}).get("expires", "")
    if exp:
        try:
            days = (dt.date.fromisoformat(exp) - dt.date.today()).days
            if days <= 10:
                r = instagram.refresh_token()
                print(f"token refresh ({days}d left): {r}")
        except Exception as e:
            print(f"token expiry check failed: {e}", file=sys.stderr)
    out = instagram.run_queue()
    print(f"publish queue: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
