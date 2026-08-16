#!/usr/bin/env python3
"""The CSS inliner that makes the v2 mail designs survive real mail clients.

Every failure below was a real one found while building it, and each is silent
in the browser — which is exactly why they are pinned here. A mail that looks
right in a preview and arrives unstyled is the failure mode this guards.
"""
from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import _sandbox  # noqa: E402,F401
from lib.cssinline import inline  # noqa: E402

FAILS: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    print(f"  {'ok  ' if ok else 'FAIL'} {label}" + (f"\n         {detail}" if detail and not ok else ""))
    if not ok:
        FAILS.append(label)


def run() -> int:
    print("· the cascade lands on the element")
    check("single class", 'style="color:red"' in inline('<style>.a{color:red}</style><p class="a">x</p>'))
    check("class beats tag",
          "color:green" in inline('<style>p{color:red}.a{color:green}</style><p class="a">x</p>'))
    check("author inline wins over the sheet",
          "color:blue" in inline('<style>.a{color:red}</style><p class="a" style="color:blue">x</p>'))

    print("\n· selector scoping is not approximate")
    check("descendant applies inside",
          "font-size:9px" in inline('<style>.c .t{font-size:9px}</style><div class="c"><i class="t">x</i></div>'))
    check("descendant does not leak outside",
          "font-size:9px" not in inline('<style>.c .t{font-size:9px}</style><i class="t">x</i>'))
    check("child combinator stays strict",
          "color:red" not in inline('<style>.a>.b{color:red}</style><div class="a"><div><i class="b">x</i></div></div>'))
    check(":first-child / :last-child",
          'style="color:red"' in inline('<style>li:first-child{color:red}</style><ul><li>a</li><li>b</li></ul>'))

    print("\n· things that silently destroy a mail")
    # A font stack carries quotes. Unescaped they close the style attribute and
    # every declaration after it is dropped — including font-size on <body>.
    out = inline('<style>body{font-family:"Hanken Grotesk",sans-serif;font-size:15.5px}</style>'
                 '<body><p>x</p></body>')
    check("quotes in a font stack do not truncate the attribute",
          "font-size:15.5px" in out and 'font-family:&quot;' in out, out[:160])
    # Losing the doctype drops the client into quirks mode: a different box
    # model and a silently shorter mail.
    check("doctype survives",
          inline('<!doctype html><style>.a{color:red}</style><p class="a">x</p>').lstrip().lower()
          .startswith("<!doctype html>"))
    # An inline style may use var(); no mail client resolves it.
    check("var() resolved in author inline styles",
          "color:#281F16" in inline('<style>:root{--ink:#281F16}</style><p style="color:var(--ink)">x</p>'))
    check("var() resolved in the sheet",
          "color:#A8492A" in inline('<style>:root{--c:#A8492A}.a{color:var(--c)}</style><p class="a">x</p>'))
    check("no var() ever survives",
          "var(--" not in inline('<style>:root{--c:#111}.a{color:var(--c)}</style>'
                                 '<p class="a" style="border-color:var(--c)">x</p>'))
    # A retained rule must still be able to beat what we inlined, or the
    # override it exists for is lost.
    out = inline('<style>.a{color:red}.a:hover{color:blue}</style><p class="a">x</p>')
    check("retained rules keep their override power",
          ":hover" in out and "!important" in out, out[-90:])

    print("\n· nothing is lost in translation")
    check("entities preserved",
          "a&nbsp;&amp;&nbsp;b" in inline('<style>.a{color:red}</style><p class="a">a&nbsp;&amp;&nbsp;b</p>'))
    check("void tags get no closing tag",
          "</img>" not in inline('<style>.i{border:0}</style><img class="i" src="x">'))
    check("@media kept for clients that honour it",
          "@media" in inline('<style>@media(max-width:560px){.a{display:none}}</style><p class="a">x</p>'))

    print("\n" + ("CSS INLINER ALL PASSED ✓" if not FAILS else f"{len(FAILS)} FAILED: {FAILS}"))
    return 0 if not FAILS else 1


if __name__ == "__main__":
    sys.exit(run())
