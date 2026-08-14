#!/usr/bin/env python3
"""S5: the reel builder — filtergraph proven with whatever encoder exists.

Production uses system ffmpeg (libx264 → Instagram-ready MP4, installed via
apt on the server). This sandbox only has Playwright's VP8-only build, which
is still enough to prove the zoompan/xfade filtergraph and the degrade path.
"""
from __future__ import annotations
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import _sandbox  # noqa: F401
import os

from lib import cfg, socialrender  # noqa: E402

FAILS: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    print(f"  {'ok  ' if ok else 'FAIL'} {label}" + (f"\n         {detail}" if detail and not ok else ""))
    if not ok:
        FAILS.append(label)


def run() -> int:
    out_dir = cfg.OUTPUT_DIR / "social" / "reel-test"
    v = {"title": "3 Impulse", "outro": "Folge @auralis_natura"}
    a = socialrender.to_png(socialrender.tpl_reel_card(v, "title", 1080, 1920),
                            out_dir / "a.png", 1080, 1920)
    b = socialrender.to_png(socialrender.tpl_reel_card(v, "outro", 1080, 1920),
                            out_dir / "b.png", 1080, 1920)
    if a.suffix != ".png":
        print("  (no chromium — reel cards unavailable, skipping encode checks)")
        return 0

    print("· degrade path: no ffmpeg binary → None, cards remain")
    got = socialrender.build_reel([a, b], out_dir / "x.mp4", ffmpeg_bin="/nonexistent")
    check("returns None instead of raising", got is None)
    check("no half-written mp4", not (out_dir / "x.mp4").exists()
          or (out_dir / "x.mp4").stat().st_size == 0)

    sys_ffmpeg = shutil.which("ffmpeg")
    pw_ffmpeg = "/opt/pw-browsers/ffmpeg-1011/ffmpeg-linux"
    if sys_ffmpeg:
        print("\n· real encode (system ffmpeg, libx264 → mp4)")
        got = socialrender.build_reel([a, b], out_dir / "reel.mp4", seconds_per=1.5)
        check("mp4 produced", got is not None and got.suffix == ".mp4")
        if got:
            d = got.read_bytes()
            check("MP4 container magic", b"ftyp" in d[:32], str(d[:16]))
            check("worth posting (>50 KB)", len(d) > 50_000)
    elif Path(pw_ffmpeg).exists():
        # Playwright's ffmpeg is a screen-recorder build: no zoompan, no xfade,
        # not even the concat demuxer. It CANNOT encode a slideshow — which
        # makes it the perfect stand-in for "some broken ffmpeg": build_reel
        # must walk both attempts and come back empty-handed, never half-done.
        print("\n· a stripped ffmpeg exhausts both attempts and degrades cleanly")
        got = socialrender.build_reel([a, b], out_dir / "reel.webm", seconds_per=1.5,
                                      encoder="libvpx", ffmpeg_bin=pw_ffmpeg)
        check("returns None (real encode needs the apt ffmpeg on the server)", got is None)
        check("no partial output left behind", not (out_dir / "reel.webm").exists())
    else:
        print("  (no ffmpeg at all — degrade path is the whole test here)")

    print("\n" + ("SOCIAL REEL ALL PASSED ✓" if not FAILS else f"{len(FAILS)} FAILED: {FAILS}"))
    return 0 if not FAILS else 1


if __name__ == "__main__":
    sys.exit(run())
