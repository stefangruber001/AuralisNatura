"""Fold a <style> block into inline style= attributes, for e-mail.

Why this exists: the v2 mail designs are authored as browser documents — 141
selectors, 89 of them descendant, plus custom properties. That renders
perfectly in Chrome and unreliably in mail. Gmail's web client honours a
<style> block, but Outlook on Windows drops much of it and no major client
supports var(). A mail that previews beautifully in the browser can reach the
recipient as unstyled black-on-white, and nothing in the sending path would
show it.

So the cascade is resolved here, at build time, and written onto the elements.
What genuinely cannot be inlined — :hover, ::after, @media — is left behind in
a <style> block, which is the correct place for it: those are enhancements, and
a client that ignores them still gets a complete, styled mail.

Deliberately small. It handles the selector grammar these documents actually
use (tag, .class, descendant, child, :first-child, :last-child) and nothing
else, because a half-right general CSS engine is worse than an exact partial
one — it fails silently on the cases it does not cover.
"""
from __future__ import annotations

import re
from html import escape as _html_escape
from html.parser import HTMLParser


def _escape(v: str) -> str:
    return _html_escape(str(v), quote=True)

# tags that never carry content and must not be given a closing tag
_VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input",
         "link", "meta", "param", "source", "track", "wbr"}
# left in the retained <style>; none of them can become an attribute
_UNINLINABLE = (":hover", ":focus", ":active", "::after", "::before",
                ":visited", "::selection")


class _Node:
    __slots__ = ("tag", "attrs", "kids", "parent", "text", "style")

    def __init__(self, tag, attrs=None, parent=None):
        self.tag = tag
        self.attrs = dict(attrs or {})
        self.kids: list = []
        self.parent = parent
        self.text = ""
        self.style: list[tuple[int, int, str]] = []   # (specificity, order, decls)

    @property
    def classes(self) -> set[str]:
        return set((self.attrs.get("class") or "").split())

    def elems(self) -> list:
        return [k for k in self.kids if isinstance(k, _Node)]


class _Tree(HTMLParser):
    """Tolerant tree builder. Mail HTML is hand-written, so it may omit an
    optional closing tag; an unmatched </p> must not unwind the whole document."""

    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.root = _Node("#root")
        self.cur = self.root

    def handle_starttag(self, tag, attrs):
        n = _Node(tag, dict(attrs), self.cur)
        self.cur.kids.append(n)
        if tag not in _VOID:
            self.cur = n

    def handle_startendtag(self, tag, attrs):
        self.cur.kids.append(_Node(tag, dict(attrs), self.cur))

    def handle_endtag(self, tag):
        n = self.cur
        while n is not self.root and n.tag != tag:
            n = n.parent
        if n is not self.root:
            self.cur = n.parent

    def handle_data(self, data):
        self.cur.kids.append(data)

    def handle_entityref(self, name):
        self.cur.kids.append(f"&{name};")

    def handle_charref(self, name):
        self.cur.kids.append(f"&#{name};")

    def handle_comment(self, data):
        self.cur.kids.append(f"<!--{data}-->")

    def handle_decl(self, decl):
        # Losing this drops <!doctype html>, which puts the client in quirks
        # mode: different box model, different default sizing, a silently
        # shorter mail. Cost a real debugging session — keep it.
        self.cur.kids.append(f"<!{decl}>")

    def handle_pi(self, data):
        self.cur.kids.append(f"<?{data}>")


# ---------------------------------------------------------------- selectors

def _parse_compound(part: str):
    """'div.card.big' -> ('div', {'card','big'}, set-of-pseudo)"""
    pseudo = set(re.findall(r":([a-z-]+)", part))
    part = re.sub(r":[a-z-]+", "", part)
    m = re.match(r"^([a-zA-Z][\w-]*)?((?:\.[\w-]+)*)$", part)
    if not m:
        return None
    tag = (m.group(1) or "").lower()
    cls = set(c for c in (m.group(2) or "").split(".") if c)
    return tag, cls, pseudo


def _compound_matches(node: _Node, comp) -> bool:
    tag, cls, pseudo = comp
    if tag and node.tag != tag:
        return False
    if cls and not cls <= node.classes:
        return False
    for p in pseudo:
        sibs = node.parent.elems() if node.parent else [node]
        if p == "first-child" and (not sibs or sibs[0] is not node):
            return False
        if p == "last-child" and (not sibs or sibs[-1] is not node):
            return False
        if p not in ("first-child", "last-child"):
            return False
    return True


def _selector_matches(node: _Node, sel: str) -> bool:
    """Right-to-left match over descendant (' ') and child ('>') combinators."""
    parts = re.split(r"\s*(>)\s*|\s+", sel.strip())
    parts = [p for p in parts if p]
    if not parts:
        return False
    comps = []
    for p in parts:
        if p == ">":
            comps.append(">")
            continue
        c = _parse_compound(p)
        if c is None:
            return None            # selector we do not understand — do not guess
        comps.append(c)

    i = len(comps) - 1
    if not _compound_matches(node, comps[i]):
        return False
    i -= 1
    cur = node.parent
    while i >= 0:
        if comps[i] == ">":
            i -= 1
            if i < 0 or cur is None or not _compound_matches(cur, comps[i]):
                return False
            cur = cur.parent
            i -= 1
        else:
            hit = None
            probe = cur
            while probe is not None and probe.tag != "#root":
                if _compound_matches(probe, comps[i]):
                    hit = probe
                    break
                probe = probe.parent
            if hit is None:
                return False
            cur = hit.parent
            i -= 1
    return True


def _specificity(sel: str) -> int:
    return len(re.findall(r"\.[\w-]+", sel)) * 10 + len(re.findall(r"(?:^|[\s>])[a-zA-Z]", sel))


# ---------------------------------------------------------------- css

def _strip_comments(css: str) -> str:
    return re.sub(r"/\*.*?\*/", "", css, flags=re.S)


def _var_map(css: str) -> dict:
    root = re.search(r":root\s*\{(.*?)\}", css, re.S)
    if not root:
        return {}
    return dict(re.findall(r"(--[\w-]+)\s*:\s*([^;]+)", root.group(1)))


def _apply_vars(text: str, var: dict) -> str:
    for _ in range(5):                      # vars may reference vars
        out = text
        for k, v in var.items():
            out = out.replace(f"var({k})", v.strip())
        out = re.sub(r"var\((--[\w-]+),\s*([^)]+)\)", r"\2", out)   # fallbacks
        if out == text:
            break
        text = out
    return text


def _resolve_vars(css: str) -> str:
    var = _var_map(css)
    if not var:
        return css
    return _apply_vars(css, var)


def _rules(css: str):
    """Yield (selector, declarations) for top-level rules, in source order."""
    depth, buf, out = 0, "", []
    for ch in css:
        if ch == "{":
            depth += 1
            buf += ch
        elif ch == "}":
            depth -= 1
            buf += ch
            if depth == 0:
                out.append(buf)
                buf = ""
        else:
            buf += ch
    for block in out:
        m = re.match(r"\s*([^{]+)\{(.*)\}\s*$", block, re.S)
        if not m:
            continue
        sels, decls = m.group(1).strip(), m.group(2).strip()
        if sels.startswith("@"):
            continue
        for s in sels.split(","):
            yield s.strip(), decls


# ---------------------------------------------------------------- serialise

def _important(decls: str) -> str:
    """Retained rules must be able to beat the styles we just inlined.

    An inline style= outranks any stylesheet rule, so a selector we could not
    inline — :last-child suppressing a divider, ::after drawing the cancelled
    stamp — would silently lose to the plain rule it is meant to override.
    !important restores the intended order.
    """
    out = []
    for d in decls.split(";"):
        d = d.strip()
        if not d or ":" not in d:
            continue
        out.append(d if "!important" in d else d + " !important")
    return ";".join(out)


def _render(node: _Node, buf: list) -> None:
    for k in node.kids:
        if isinstance(k, str):
            buf.append(k)
            continue
        attrs = dict(k.attrs)
        if k.style:
            merged: dict[str, str] = {}
            for _, _, decls in sorted(k.style, key=lambda x: (x[0], x[1])):
                for d in decls.split(";"):
                    if ":" in d:
                        p, v = d.split(":", 1)
                        merged[p.strip()] = v.strip()
            own = attrs.get("style", "")          # author's inline wins
            for d in own.split(";"):
                if ":" in d:
                    p, v = d.split(":", 1)
                    merged[p.strip()] = v.strip()
            attrs["style"] = ";".join(f"{p}:{v}" for p, v in merged.items() if v)
        # Escape on the way out. Two reasons, both silent if missed: a font
        # stack carries double quotes — font-family:"Hanken Grotesk" — which
        # would close the style attribute early and drop every declaration
        # after it; and HTMLParser hands back attribute values already
        # unescaped, so an &amp; in a URL must be restored.
        a = "".join(f' {n}="{_escape(v)}"' if v is not None else f" {n}"
                    for n, v in attrs.items())
        if k.tag in _VOID:
            buf.append(f"<{k.tag}{a}>")
        else:
            buf.append(f"<{k.tag}{a}>")
            _render(k, buf)
            buf.append(f"</{k.tag}>")


def inline(html: str) -> str:
    """Return `html` with its <style> rules folded into style= attributes.

    Rules that cannot be expressed as an attribute (:hover, ::after, @media)
    are kept in a trailing <style> so clients that support them still apply
    them. Unrecognised selectors are also kept rather than dropped — better a
    rule that only some clients honour than one silently lost.
    """
    m = re.search(r"<style[^>]*>(.*?)</style>", html, re.S | re.I)
    if not m:
        return html
    raw = _strip_comments(m.group(1))
    var = _var_map(raw)
    css = _resolve_vars(raw)
    doc = html[:m.start()] + html[m.end():]
    # An author inline style may use var() as well, and no mail client resolves
    # it. Substitute inside style="…" only, never in text content.
    if var:
        doc = re.sub(r'style="([^"]*)"',
                     lambda mm: 'style="' + _apply_vars(mm.group(1), var) + '"', doc)

    tree = _Tree()
    tree.feed(doc)
    tree.close()

    flat: list[_Node] = []

    def walk(n):
        for k in n.elems():
            flat.append(k)
            walk(k)
    walk(tree.root)

    keep: list[str] = []
    for order, (sel, decls) in enumerate(_rules(css)):
        if sel == ":root" or any(p in sel for p in _UNINLINABLE):
            if sel != ":root":
                keep.append(f"{sel}{{{_important(decls)}}}")
            continue
        spec = _specificity(sel)
        understood = True
        for node in flat:
            r = _selector_matches(node, sel)
            if r is None:
                understood = False
                break
            if r:
                node.style.append((spec, order, decls))
        if not understood:
            keep.append(f"{sel}{{{_important(decls)}}}")
    for mq in re.findall(r"@media[^{]+\{(?:[^{}]*\{[^{}]*\})*[^{}]*\}", css, re.S):
        keep.append(mq)

    buf: list[str] = []
    _render(tree.root, buf)
    out = "".join(buf)
    if keep:
        style = "<style>" + "".join(keep) + "</style>"
        out = (out.replace("</head>", style + "</head>", 1) if "</head>" in out
               else style + out)
    return out
