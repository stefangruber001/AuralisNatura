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
    """Remove comments and string literals, correctly handling Swift string
    interpolation \\( ... ) which may itself contain nested strings."""
    out = []
    i, n = 0, len(src)
    mode = []  # stack: "str", "tstr" (triple), "interp"
    while i < n:
        c = src[i]
        top = mode[-1] if mode else None
        if top in ("str", "tstr"):
            if c == "\\" and i + 1 < n:
                if src[i + 1] == "(":
                    mode.append("interp"); out.append("(")  # interpolation code counts
                    i += 2; continue
                i += 2; continue
            if top == "tstr" and src.startswith('"""', i):
                mode.pop(); i += 3; continue
            if top == "str" and c == '"':
                mode.pop(); i += 1; continue
            i += 1; continue
        # code context (incl. inside interpolation)
        if c == "/" and src.startswith("//", i):
            j = src.find("\n", i); i = n if j == -1 else j; continue
        if c == "/" and src.startswith("/*", i):
            j = src.find("*/", i + 2); i = n if j == -1 else j + 2; continue
        if src.startswith('"""', i):
            mode.append("tstr"); i += 3; continue
        if c == '"':
            mode.append("str"); i += 1; continue
        if top == "interp":
            if c == "(":
                mode.append("interp")  # nested paren inside interpolation
            elif c == ")":
                mode.pop()
            out.append(c); i += 1; continue
        out.append(c); i += 1
    return "".join(out)


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

    # Keys built by interpolation — L10n["scale.\(key)"], L10n["journey.step\(n).sub"]
    # — are invisible to the scan above, so a typo there would ship as a raw key
    # string on screen. Check the generated families against their real inputs.
    dyn = set()
    home = (APP / "Views" / "HomeView.swift").read_text(encoding="utf-8")
    m = re.search(r"scaleOrder = \[([^\]]*)\]", home)
    if m:
        dyn |= {f"scale.{k}" for k in re.findall(r'"([a-z_]+)"', m.group(1))}
    if 'L10n["journey.step\\(' in home:
        dyn |= {f"journey.step{n}.sub" for n in range(1, 5)}
    miss_dyn = dyn - de
    ok(f"all {len(dyn)} interpolated keys exist in de", not miss_dyn, f"missing:{sorted(miss_dyn)}")


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
