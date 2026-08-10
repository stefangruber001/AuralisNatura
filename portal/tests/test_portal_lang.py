#!/usr/bin/env python3
"""The client portal in three languages, plus one-click entry from the mail.

Drives the real page in Chromium against a live app, because the last two
language bugs in this project were both "the switch exists but nothing moves"
and both survived a source-level check.
"""
from __future__ import annotations
import json
import sys
import threading
import time
from pathlib import Path
from wsgiref.simple_server import make_server, WSGIRequestHandler

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from lib import cfg, auth  # noqa: E402
from server.app import app  # noqa: E402

CHROME = "/opt/pw-browsers/chromium-1194/chrome-linux/chrome"
FAILS: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    print(f"  {'ok  ' if ok else 'FAIL'} {label}" + (f"\n         {detail}" if detail and not ok else ""))
    if not ok:
        FAILS.append(label)


class Quiet(WSGIRequestHandler):
    def log_message(self, *a):
        pass


def serve():
    srv = make_server("127.0.0.1", 0, app, handler_class=Quiet)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_address[1]}"


def temp_client() -> tuple[str, str]:
    """A throwaway client, removed again at the end — never a live record."""
    pw = auth.new_password()
    with cfg._CLIENTS_LOCK:
        data = cfg.clients()
        cid = "AN-9099"
        data.setdefault("clients", {})[cid] = {
            "name": "Testerin Portal", "email": "portal-test@example.invalid",
            "language": "de", "phone": "", "password": auth.hash_password(pw),
            "status": "active", "created": "2026-01-01",
            "consent": {"coaching_not_medical": None, "gdpr_health_data": None, "version": "1.0"}}
        cfg.assign_login_id(cid, "Testerin Portal", data)   # → testerin.portal
        cfg.save_clients(data)
    return cid, pw


def drop_client(cid: str) -> None:
    with cfg._CLIENTS_LOCK:
        data = cfg.clients()
        data.get("clients", {}).pop(cid, None)
        cfg.save_clients(data)


def run() -> int:
    from playwright.sync_api import sync_playwright
    srv, base = serve()
    cid, pw = temp_client()
    try:
        with sync_playwright() as p:
            b = p.chromium.launch(executable_path=CHROME, args=["--no-sandbox"])
            pg = b.new_page(viewport={"width": 420, "height": 900})
            errs: list[str] = []
            pg.on("pageerror", lambda e: errs.append(str(e)))

            print("· the login screen asks for a language, and the answer sticks")
            pg.goto(f"{base}/portal")
            pg.wait_for_selector("#langLogin button")
            check("three languages offered on the login card",
                  pg.locator("#langLogin button").count() == 3)
            check("a switcher is also reachable above the card",
                  pg.locator("#langTop button").count() == 3)

            seen = {}
            for lang, want in (("de", "Willkommen zurück"), ("en", "Welcome back"),
                               ("es", "Bienvenida de nuevo")):
                pg.click(f'#langLogin button[lang="{lang}"]')
                h1 = pg.inner_text("#login h1")
                seen[lang] = h1
                check(f"{lang}: login headline", h1 == want, f"got {h1!r}")
                check(f"{lang}: <html lang> follows",
                      pg.evaluate("document.documentElement.lang") == lang)
                check(f"{lang}: the chosen chip is the pressed one",
                      pg.get_attribute(f'#langLogin button[lang="{lang}"]', "aria-pressed") == "true")
            check("the three headlines really differ", len(set(seen.values())) == 3, str(seen))

            check("the choice survives a reload",
                  (pg.reload(), pg.wait_for_selector("#login h1"),
                   pg.inner_text("#login h1"))[2] == "Bienvenida de nuevo")

            print("\n· signing in keeps that language, and the intake is translated")
            pg.click('#langLogin button[lang="en"]')
            pg.fill("#cid", "Testerin.Portal")   # name-based id, wrong case on purpose
            pg.fill("#pw", pw)
            pg.click("#login .btn")
            pg.wait_for_selector("#shell:not(.hidden)")
            check("five tabs", pg.locator("#tabbar button").count() == 5)
            pg.click('#tabbar button:nth-child(2)')     # Fragebogen / Questionnaire
            pg.wait_for_selector("#intake:not(.hidden)")
            check("English intake headline", "your intake" in pg.inner_text("#hello").lower(),
                  pg.inner_text("#hello"))
            # .stepcap is text-transform:uppercase, so inner_text comes back shouted
            check("English step caption",
                  pg.inner_text("#stepcap").lower().startswith("step 1 of 5"),
                  pg.inner_text("#stepcap"))
            check("the explicit choice beats the record's German",
                  "Aufnahmebogen" not in pg.inner_text("#intake"))
            check("no duplicate language question inside step A",
                  pg.locator('[data-k="language"]').count() == 0)

            print("\n· the switcher works from inside the portal too")
            pg.click('#langTop button[lang="es"]')
            check("Spanish step caption",
                  pg.inner_text("#stepcap").lower().startswith("paso 1 de 5"),
                  pg.inner_text("#stepcap"))
            check("Spanish section A", "Sobre ti" in pg.inner_text('[data-step="0"] h1'))
            pg.click('#langTop button[lang="de"]')
            check("German section A", "Über dich" in pg.inner_text('[data-step="0"] h1'))

            print("\n· typed answers survive a language switch")
            pg.fill('[data-k="goal"]', "Mehr Energie am Nachmittag")
            pg.click('#langTop button[lang="es"]')
            check("the answer is still there",
                  pg.input_value('[data-k="goal"]') == "Mehr Energie am Nachmittag")

            print("\n· the safety list reads in the client's language but reports in one")
            pg.click("#next")
            pg.click("#next")
            pg.click("#next")
            pg.wait_for_selector('[data-step="3"]:not(.hidden)')
            labels = pg.locator("#redflags .chk span").all_inner_texts()
            check("Spanish labels", "Nada de lo anterior" in labels, str(labels))
            values = pg.eval_on_selector_all("[data-flag]", "els=>els.map(e=>e.dataset.flag)")
            check("values stay canonical English", "None of the above" in values, str(values))

            print("\n· one click from the Zugangsdaten mail signs you straight in")
            key = auth.issue_token(cid, ttl_seconds=600, scope="portal-magic")
            pg2 = b.new_page(viewport={"width": 420, "height": 900})
            pg2.on("pageerror", lambda e: errs.append(str(e)))
            pg2.goto(f"{base}/portal#k={key}")
            pg2.wait_for_selector("#intake:not(.hidden)", timeout=8000)  # straight into the questionnaire
            check("no ID or password typed, and we are inside", True)
            check("the key is wiped from the address bar", "#k=" not in pg2.url, pg2.url)

            print("\n· a magic key is not a session key")
            r = pg2.evaluate("""async k => (await fetch('/api/me',
                {headers:{'Authorization':'Bearer '+k}})).status""", key)
            check("scoped key rejected on /api/me", r == 401, f"status {r}")
            r = pg2.evaluate("""async () => (await fetch('/api/login/magic',
                {method:'POST',headers:{'Content-Type':'application/json'},
                 body:JSON.stringify({k:'nonsense.deadbeef'})})).status""")
            check("a forged key is rejected", r == 401, f"status {r}")

            check("no JavaScript errors anywhere", not errs, "; ".join(errs[:3]))
            b.close()
    finally:
        drop_client(cid)
        srv.shutdown()

    print("\n" + ("PORTAL LANGUAGE CHECKS ALL PASSED ✓" if not FAILS else f"{len(FAILS)} FAILED: {FAILS}"))
    return 0 if not FAILS else 1


if __name__ == "__main__":
    sys.exit(run())
