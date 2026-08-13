#!/usr/bin/env python3
"""Weekly social-media screening — the auralis-social-scan.timer entry point.

Fetches every enabled agent's public sources, writes the week's digest
(output_docs/social/digests/YYYY-WW.json), and — unless auto_strategy is off or
--scan-only is passed — chains straight into the weekly strategy draft (S3), so
the drafts are already waiting when Desiree opens the console on Monday.

Exit code 0 even when individual sources fail: per-source errors live in the
digest and the console; a red systemd unit should mean "the run itself broke",
not "one blog was down".
"""
from __future__ import annotations
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from lib import social  # noqa: E402


def main() -> int:
    scan_only = "--scan-only" in sys.argv
    digest = social.run_scan()
    ok = digest.get("summary") is not None
    print(f"scan {digest['week']}: {digest['items_total']} neue Funde · "
          f"Digest {'✓' if ok else 'ohne Zusammenfassung (' + str(digest.get('provider','')) + ')'}")
    if not scan_only and social.social().get("auto_strategy", True):
        try:
            from lib import social as s
            if hasattr(s, "run_strategy"):        # arrives with S3
                plan = s.run_strategy()
                print(f"strategy {plan.get('week')}: {len(plan.get('slots', []))} Entwürfe")
        except Exception as e:  # the scan result must survive a strategy failure
            print(f"strategy failed: {e}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
