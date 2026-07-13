#!/usr/bin/env python3
"""Scripted quality audits for the Auralis Natura iOS app (no Swift compiler needed).

Checks:
 1. L10n parity: every key used in code exists in de/en/es; dictionaries have equal key sets.
 2. Brace/paren balance per file (comments + string literals stripped first).
 3. Image("...")/named assets referenced in code exist in Assets.xcassets; custom font
    names exist as TTFs in Fonts/ (by PostScript name).
 4. API paths used in Swift exist as routes in portal/server/app.py.
Exit non-zero on any failure. Run from repo root or ios-app/.
"""
import re, sys, json
from pathlib import Path

HERE = Path(__file__).resolve().parent
APP = HERE / "AuralisApp"
SERVER = HERE.parent / "portal" / "server" / "app.py"
fails = []


def ok(name, cond, detail=""):
    print(("  PASS " if cond else "  FAIL ") + name + (f" — {detail}" if detail and not cond else ""))
    if not cond:
        fails.append(name)


def swift_files():
    return sorted(APP.rglob("*.swift"))


def strip_swift(src: str) -> str:
    src = re.sub(r"/\*.*?\*/", "", src, flags=re.S)          # block comments
    src = re.sub(r"//[^\n]*", "", src)                        # line comments
    # strings: handle multiline first, then simple (interpolation braces stay — strip conservatively)
    src = re.sub(r'"""(?:.|\n)*?"""', '""', src)
    src = re.sub(r'"(?:\\.|[^"\\\n])*"', '""', src)
    return src


def check_braces():
    print("· brace/paren balance")
    for f in swift_files():
        s = strip_swift(f.read_text(encoding="utf-8"))
        for o, c in [("{", "}"), ("(", ")"), ("[", "]")]:
            ok(f"{f.name} {o}{c} balanced", s.count(o) == s.count(c),
               f"{s.count(o)} vs {s.count(c)}")


def load_l10n():
    src = (APP / "L10n.swift").read_text(encoding="utf-8")
    langs = {}
    for lang in ("de", "en", "es"):
        m = re.search(rf'"{lang}"\s*:\s*\[(.*?)\n\s*\](?:,|\s*\])', src, re.S)
        if not m:
            m = re.search(rf'{lang}\s*:\s*\[String:\s*String\]\s*=\s*\[(.*?)\n\s*\]', src, re.S)
        block = m.group(1) if m else ""
        keys = set(re.findall(r'"([a-z0-9_.]+)"\s*:', block))
        langs[lang] = keys
    return langs


def check_l10n():
    print("· L10n parity & coverage")
    langs = load_l10n()
    de, en, es = langs["de"], langs["en"], langs["es"]
    ok(f"de/en parity ({len(de)}/{len(en)})", de == en, f"only-de:{sorted(de-en)[:6]} only-en:{sorted(en-de)[:6]}")
    ok(f"de/es parity ({len(de)}/{len(es)})", de == es, f"only-de:{sorted(de-es)[:6]} only-es:{sorted(es-de)[:6]}")
    used = set()
    for f in swift_files():
        if f.name == "L10n.swift":
            continue
        src = f.read_text(encoding="utf-8")
        used |= set(re.findall(r'L10n\.t\(\s*"([a-z0-9_.]+)"', src))
        used |= set(re.findall(r'L10n\[\s*"([a-z0-9_.]+)"', src))
    missing = used - de
    ok(f"all {len(used)} used keys exist in de", not missing, f"missing:{sorted(missing)[:10]}")


def check_assets_fonts():
    print("· assets & fonts")
    sets = {p.name.replace(".imageset", "").replace(".colorset", "")
            for p in (APP / "Assets.xcassets").iterdir() if p.suffix in (".imageset", ".colorset")}
    used_imgs = set()
    for f in swift_files():
        used_imgs |= set(re.findall(r'Image\("([A-Za-z0-9]+)"\)', f.read_text(encoding="utf-8")))
    missing = used_imgs - sets
    ok(f"images referenced exist ({sorted(used_imgs)})", not missing, f"missing:{sorted(missing)}")
    ttf_ps = {p.stem for p in (APP / "Fonts").glob("*.ttf")}
    used_fonts = set()
    for f in swift_files():
        used_fonts |= set(re.findall(r'(?:Font\.custom|UIFont)\(\s*"([A-Za-z-]+)"', f.read_text(encoding="utf-8")))
    missing_f = used_fonts - ttf_ps
    ok(f"custom fonts have TTFs ({sorted(used_fonts)})", not missing_f, f"missing:{sorted(missing_f)}")


def check_api_paths():
    print("· API paths vs server routes")
    server = SERVER.read_text(encoding="utf-8")
    routes = set(re.findall(r'@app\.(?:get|post|delete|route)\("(/api/[^"<]*)', server))
    prefixes = tuple(routes)
    used = set()
    for f in swift_files():
        used |= set(re.findall(r'"(/api/[a-z0-9/_-]+)"', f.read_text(encoding="utf-8")))
    unknown = {u for u in used if u not in routes and not any(u.startswith(p.rstrip("/")) for p in prefixes)}
    ok(f"all {len(used)} Swift API paths exist on server", not unknown, f"unknown:{sorted(unknown)}")


if __name__ == "__main__":
    if not APP.exists():
        print("AuralisApp dir missing"); sys.exit(2)
    n = len(swift_files())
    print(f"auditing {n} swift files")
    check_braces(); check_l10n(); check_assets_fonts(); check_api_paths()
    print("\n" + ("AUDITS ALL PASSED ✓" if not fails else f"{len(fails)} FAILED: {fails[:8]}"))
    sys.exit(0 if not fails else 1)
