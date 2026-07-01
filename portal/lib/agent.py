"""The Cloud Report Agent.

Turns a *pseudonymised* intake + Desiree's call notes into a structured, six-part
DRAFT. It never emails a client and never bypasses the human-approval gate — it
only returns a draft the console renders for review.

Providers:
- "stub"       : deterministic, offline draft built from the intake. Lets the
                 whole pipeline be tested with no credentials. Also the safe
                 fallback if the real provider is unavailable.
- "claude_cli" : shells out to the `claude` CLI (Claude Code) which is signed in
                 with Desiree's Pro/Max subscription — no per-token API cost.

GDPR: `pseudonymise()` strips direct identifiers before anything leaves the box.
Only a client ref + health content + notes are sent to the model.
"""
from __future__ import annotations
import json, subprocess, shutil, re
from . import cfg

SECTIONS = [
    ("starting_point", "Your starting point"),
    ("what_were_seeing", "What we're seeing"),
    ("the_science_simply", "The science, simply"),
    ("your_plan", "Your plan"),
    ("when_to_see_a_doctor", "When to see a doctor"),
    ("next_steps", "Your next steps"),
]

RED_FLAGS = [
    "unexplained weight loss", "chest pain", "breathlessness", "severe pain",
    "persistent pain", "fainting", "self-harm", "self harm", "disordered eating",
    "gewichtsverlust", "brustschmerz", "atemnot", "ohnmacht", "selbstverletzung",
]


# ---------- GDPR: pseudonymise before the model sees anything ----------
_IDENTIFIER_KEYS = {"name", "full_name", "first_name", "last_name", "email",
                    "phone", "address", "dob", "date_of_birth"}


def pseudonymise(intake: dict, client_ref: str) -> dict:
    """Return a copy of the intake with direct identifiers removed/replaced."""
    def scrub(obj):
        if isinstance(obj, dict):
            return {k: ("<redacted>" if k.lower() in _IDENTIFIER_KEYS else scrub(v))
                    for k, v in obj.items()}
        if isinstance(obj, list):
            return [scrub(x) for x in obj]
        return obj
    out = scrub(intake or {})
    out["client_ref"] = client_ref
    return out


def has_red_flag(intake: dict) -> bool:
    blob = json.dumps(intake or {}, ensure_ascii=False).lower()
    # explicit tick-list wins
    flags = (intake or {}).get("red_flags") or (intake or {}).get("safety", {}).get("red_flags")
    if isinstance(flags, list) and any(f and str(f).lower() not in ("none", "keine", "none of the above") for f in flags):
        return True
    return any(rf in blob for rf in RED_FLAGS)


def _lang(intake: dict) -> str:
    l = str((intake or {}).get("language", "") or (intake or {}).get("a", {}).get("language", "")).lower()
    return "de" if l.startswith("de") else "es" if l.startswith("es") else "en"


# ---------- public entry points ----------
def meeting_prep(intake: dict) -> str:
    """A short summary so Desiree walks into the call prepared."""
    a = intake or {}
    goal = _first(a, ["goal", "main_goal", "a.goal"]) or "—"
    why = _first(a, ["why_now", "why", "a.why_now"]) or "—"
    tried = _first(a, ["tried", "what_tried", "a.tried"]) or "—"
    scales = _scales(a)
    flag = "  ⚠ RED FLAG present — open the report with a doctor referral." if has_red_flag(a) else ""
    lines = [
        "MEETING PREP",
        f"• Main goal: {goal}",
        f"• Why now: {why}",
        f"• Already tried: {tried}",
        f"• Self-rated (1–5): {scales}",
        flag,
    ]
    return "\n".join(x for x in lines if x)


def draft_report(intake: dict, notes: str, client_ref: str) -> dict:
    """Return {'sections':[{key,title,body}], 'red_flag':bool, 'provider':...}."""
    provider = cfg.config().get("agent_provider", "stub")
    payload = pseudonymise(intake, client_ref)
    red = has_red_flag(intake)
    if provider == "claude_cli" and shutil.which("claude"):
        try:
            return _claude_cli(payload, notes, red, _lang(intake))
        except Exception as e:  # pragma: no cover - falls back safely
            out = _stub(payload, notes, red, _lang(intake))
            out["provider"] = f"stub (claude_cli failed: {e})"
            return out
    return _stub(payload, notes, red, _lang(intake))


# ---------- stub provider (offline, deterministic) ----------
def _stub(payload: dict, notes: str, red: bool, lang: str) -> dict:
    goal = _first(payload, ["goal", "main_goal"]) or "feeling like yourself again"
    scales = _scales(payload)
    note_line = (notes or "").strip()
    secs = []
    doctor = ("Because your intake shows something worth checking, please see your doctor "
              "before we go further. ") if red else ""
    body = {
        "starting_point": f"{doctor}You came to Auralis wanting: {goal}. This report gathers what you shared "
                          f"into a few honest observations and a realistic first plan — education and guidance "
                          f"for your wellbeing, a companion to (never a replacement for) your doctor's care.",
        "what_were_seeing": f"A few themes stand out from your intake"
                            + (f" and our conversation ({note_line})" if note_line else "")
                            + f". Your self-ratings ({scales}) point to where small, steady changes will help most. "
                              f"These are patterns, not a diagnosis.",
        "the_science_simply": "When meals are irregular and low in protein, energy and mood tend to swing; "
                             "steadier meals and protected rest help the nervous system recover. Where the "
                             "evidence is mixed we say so plainly — we prefer 'may support' to 'will fix'.",
        "your_plan": "1) A steadier, protein- and fibre-rich breakfast within an hour of waking. "
                    "2) One small protected pause each day. 3) Gently even out the longest gaps between meals. "
                    "Two or three changes, sequenced — never overwhelming.",
        "when_to_see_a_doctor": ("Please check in with your GP about anything acute or persistent"
                                + (" — and given your intake, soon" if red else "")
                                + ". Nothing here diagnoses or treats a condition; in an emergency call 112. "
                                  "This guidance supports your medical care, it never replaces it."),
        "next_steps": "You have everything to begin the first two steps this week. If you'd like company and "
                     "structure, The Bloom (six guided weeks) builds on this plan together. Book the review "
                     "call whenever you're ready.",
    }
    for key, title in SECTIONS:
        secs.append({"key": key, "title": title, "body": body[key]})
    return {"sections": secs, "red_flag": red, "provider": "stub", "language": lang,
            "charts": _chart_data(payload)}


# ---------- claude CLI provider (Pro/Max subscription) ----------
def _claude_cli(payload: dict, notes: str, red: bool, lang: str) -> dict:
    prompt = _build_prompt(payload, notes, red, lang)
    # Claude Code headless print-mode; auth = the signed-in subscription
    proc = subprocess.run(
        ["claude", "-p", prompt, "--output-format", "text"],
        capture_output=True, text=True, timeout=180,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip()[:200] or "claude cli error")
    data = _extract_json(proc.stdout)
    secs = []
    for key, title in SECTIONS:
        body = (data.get(key) or "").strip()
        secs.append({"key": key, "title": title, "body": body})
    return {"sections": secs, "red_flag": red, "provider": "claude_cli",
            "language": lang, "charts": _chart_data(payload)}


def _build_prompt(payload: dict, notes: str, red: bool, lang: str) -> str:
    sys = (cfg.ROOT.parent / "handover/customer-journey-kit/claude/report-engine-system-prompt.md")
    sys_text = sys.read_text(encoding="utf-8") if sys.exists() else ""
    schema = ", ".join(k for k, _ in SECTIONS)
    return (
        f"{sys_text}\n\n"
        f"You are drafting a report. Output ONLY a JSON object with these string keys: {schema}. "
        f"Write in language '{lang}'. Educational, never diagnostic. "
        f"{'A RED FLAG is present — OPEN with a clear doctor referral. ' if red else ''}"
        f"Here is the pseudonymised intake and the coach's call notes:\n\n"
        f"INTAKE:\n{json.dumps(payload, ensure_ascii=False, indent=2)}\n\n"
        f"CALL NOTES:\n{notes or '(none)'}\n"
    )


def _extract_json(text: str) -> dict:
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        raise ValueError("no JSON in model output")
    return json.loads(m.group(0))


# ---------- helpers ----------
def _first(d: dict, keys):
    for k in keys:
        cur = d
        for part in k.split("."):
            cur = cur.get(part) if isinstance(cur, dict) else None
        if cur:
            return cur if isinstance(cur, str) else str(cur)
    return None


def _scales(d: dict):
    keys = ["energy", "sleep", "stress", "digestion"]
    b = d.get("b", d)
    out = []
    for k in keys:
        v = b.get(k) if isinstance(b, dict) else None
        if v is not None:
            out.append(f"{k} {v}")
    return ", ".join(out) if out else "not provided"


def _chart_data(d: dict) -> dict:
    b = d.get("b", d)
    data = {}
    for k in ["energy", "sleep", "stress", "digestion"]:
        v = (b or {}).get(k)
        try:
            data[k] = max(0, min(5, int(v)))
        except (TypeError, ValueError):
            pass
    return data
