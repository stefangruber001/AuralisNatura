#!/usr/bin/env python3
"""The availability editor's suggestion logic, run against the real staff.html.

Extracts the functions out of the page and executes them in node, so the test
exercises the shipped source rather than a copy that can drift from it.
Skips cleanly when node is unavailable.

  python3 portal/tests/test_availability_ui.py
"""
import pathlib, re, shutil, subprocess, sys, tempfile, os

HTML = pathlib.Path(__file__).resolve().parents[1] / "web" / "staff.html"

if not shutil.which("node"):
    print("SKIP: node not installed")
    sys.exit(0)

s = HTML.read_text(encoding="utf-8")


def grab(name: str) -> str:
    """The whole function body, by brace matching — regex loses nested braces."""
    i = s.index(f"function {name}(")
    depth, j = 0, s.index("{", i)
    while True:
        if s[j] == "{":
            depth += 1
        elif s[j] == "}":
            depth -= 1
            if depth == 0:
                return s[i:j + 1]
        j += 1


HARNESS = """
const WD_KEYS=['mon','tue','wed','thu','fri','sat','sun'];
let AV; let __toast; const toast=m=>{__toast=m}; const renderAvWeek=()=>{};
"""
ASSERTS = """
const eq=(a,b,n)=>{const x=JSON.stringify(a),y=JSON.stringify(b);
  console.log((x===y?'  ok   ':'  FAIL ')+n+(x===y?'':`\\n         got ${x}\\n        want ${y}`));
  if(x!==y)process.exitCode=1;};

AV={windows:{mon:[],tue:[],wed:[],thu:[],fri:[],sat:[],sun:[]},overrides:{}};
eq(sugFor('tue'),[],'Monday empty -> nothing is suggested anywhere');
eq(sugFor('mon'),[],'Monday itself never suggests');

AV.windows.mon=['14:00-17:00','09:30-12:00']; sortWin('mon');
eq(AV.windows.mon,['09:30-12:00','14:00-17:00'],'windows sort chronologically');
eq(sugFor('tue'),['09:30-12:00','14:00-17:00'],'Tuesday offers exactly Monday');
eq(sugFor('mon'),[],'Monday still suggests nothing once filled');

AV.windows.wed=['09:30-12:00'];
eq(sugFor('wed'),['14:00-17:00'],'a day offers only what it lacks');

copyMonToWeek();
eq(AV.windows.sun,['09:30-12:00','14:00-17:00'],'copy fills an empty day');
eq(AV.windows.wed,['09:30-12:00','14:00-17:00'],'copy never duplicates');
// five empty days x 2 windows, plus the one Wednesday was missing.
eq(__toast,'11 Zeitfenster übernommen — noch nicht gespeichert.','copy counts what it added');
copyMonToWeek();
eq(__toast,'Alle Tage haben Montags Zeiten bereits.','a second copy is a no-op');

AV.windows.thu=['08:00-10:00'];
eq(sugForDate('2026-08-13',[]),['08:00-10:00'],'a Thursday offers the Thursday pattern');
eq(sugForDate('2026-08-13',['08:00-10:00']),[],'an already-present window is not re-offered');
AV.windows.sat=[];
eq(sugForDate('2026-08-15',[]),['09:30-12:00','14:00-17:00'],'a free Saturday falls back to Monday');

AV.windows.mon=[]; copyMonToWeek();
eq(__toast,'Montag ist noch leer.','copy with an empty Monday warns instead of clearing');
"""

assert "PRESETS" not in s, "the fixed Vormittag/Nachmittag/Abend presets are back"
src = HARNESS + "\n".join(grab(n) for n in
                          ("sugFor", "sortWin", "sugForDate", "copyMonToWeek")) + ASSERTS

f = tempfile.NamedTemporaryFile("w", suffix=".mjs", delete=False, encoding="utf-8")
f.write(src); f.close()
r = subprocess.run(["node", f.name], capture_output=True, text=True)
os.unlink(f.name)
print(r.stdout.rstrip() or r.stderr[:800])
if r.returncode:
    print("\nFAILED"); sys.exit(1)
print("\nall availability-UI checks passed")
