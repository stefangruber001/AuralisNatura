import sys, os, threading
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT); sys.path.insert(0,ROOT)
import shutil
for f in ['auralis.db','auralis.db-wal','auralis.db-shm']:
    p=os.path.join(ROOT,f); os.path.exists(p) and os.remove(p)
for d in ['output_docs']:
    for n in os.listdir(os.path.join(ROOT,d)) if os.path.isdir(os.path.join(ROOT,d)) else []:
        if n.startswith('AN-') or n=='bookings': shutil.rmtree(os.path.join(ROOT,d,n),ignore_errors=True)
p=os.path.join(ROOT,'config','availability.json'); os.path.exists(p) and os.remove(p)
open(os.path.join(ROOT,'config','clients.json'),'w').write('{"clients":{}}')
os.environ['AURALIS_API_KEY']='k'
from werkzeug.serving import make_server
from server.app import app
srv=make_server('127.0.0.1',8816,app,threaded=True)
threading.Thread(target=srv.serve_forever,daemon=True).start()
BASE='http://127.0.0.1:8816'
from playwright.sync_api import sync_playwright
CHROME='/opt/pw-browsers/chromium-1194/chrome-linux/chrome'
fails=[]
def ck(n,c): print(('  PASS ' if c else '  FAIL ')+n); (c or fails.append(n))
with sync_playwright() as pw:
    b=pw.chromium.launch(executable_path=CHROME,args=['--no-sandbox','--disable-gpu'])
    # ── 1) booking wizard with wellbeing profile ──
    pg=b.new_page(viewport={'width':520,'height':1000},device_scale_factor=2)
    errs=[]; pg.on('pageerror',lambda e:errs.append(str(e)))
    pg.goto(BASE+'/book',wait_until='networkidle'); pg.wait_for_timeout(500)
    pg.click('button[data-lang="de"]'); pg.wait_for_timeout(200)
    pg.click('.day >> nth=0'); pg.wait_for_timeout(250)
    pg.click('.slot >> nth=0'); pg.wait_for_timeout(250)
    ck('step2 contact shown', pg.is_visible('#stepWho'))
    pg.fill('#bn','Elena Martín'); pg.fill('#be','elena@example.com')
    pg.click('text=Weiter'); pg.wait_for_timeout(250)
    ck('step3 wellbeing shown', pg.is_visible('#stepYou'))
    # chips
    pg.click('#symChips .chip >> nth=0')  # fatigue
    pg.click('#symChips .chip >> nth=1')  # sleep
    pg.fill('#pg','Wieder Energie für meine Tage.')
    pg.select_option('#ps','months')
    pg.screenshot(path='/tmp/c2-book-you.png')
    # safety gate first: try confirm without flags
    pg.click('#confirmBtn'); pg.wait_for_timeout(250)
    ck('red-flag question enforced', pg.is_visible('#stepYou') and 'Sicherheitsfrage' in pg.text_content('#err3'))
    pg.click('#flagChips .chip >> nth=0')  # none
    pg.click('#confirmBtn'); pg.wait_for_timeout(250)
    ck('consent enforced', 'Einwilligung' in pg.text_content('#err3'))
    pg.check('#bc'); pg.click('#confirmBtn'); pg.wait_for_timeout(1400)
    ck('booking confirmed', pg.is_visible('#stepDone'))
    ck('wizard no js errors', not errs) or print('   ',errs)
    pg.close()
    # ── 2) console: journey kanban shows the lead with pre-intake ──
    pg=b.new_page(viewport={'width':1440,'height':900},device_scale_factor=2)
    errs2=[]; pg.on('pageerror',lambda e:errs2.append(str(e)))
    pg.goto(BASE+'/staff',wait_until='networkidle')
    pg.fill('#key','k'); pg.click('text=Unlock'); pg.wait_for_timeout(800)
    ck('journey board shown', pg.locator('.board').count()==1)
    ck('lead card visible', 'Elena Martín' in pg.text_content('.board'))
    ck('pre-intake marker on card', '📋' in pg.text_content('.krd'))
    pg.screenshot(path='/tmp/c2-journey.png')
    # advance lead -> call via the arrow
    pg.once('dialog', lambda d: d.dismiss())
    pg.click('.krd .adv'); pg.wait_for_timeout(600)
    ck('card advanced to Erstgespräch', 'Erstgespräch' in pg.text_content('.col.hot:nth-child(2)'))
    # ── 3) client detail: pre-intake + package + credentials button ──
    pg.click('.krd >> nth=0'); pg.wait_for_timeout(700)
    ck('kunden tab active', pg.locator('.tab.on[data-tab="kunden"]').count()==1)
    ck('pre-intake card shown', 'Vorab-Angaben' in pg.text_content('#detail'))
    ck('credentials button present', 'Zugangsdaten senden' in pg.text_content('#detail'))
    pg.select_option('#pkgSel','bloom'); pg.click('text=Speichern'); pg.wait_for_timeout(500)
    pg.screenshot(path='/tmp/c2-kunde.png')
    # ── 4) dashboard renders KPIs ──
    pg.click('button[data-tab="dash"]'); pg.wait_for_timeout(700)
    t=pg.text_content('#view')
    ck('dashboard tiles', 'Umsatz gesamt' in t and 'Buchungen' in t)
    ck('funnel shown', 'Funnel' in t)
    ck('chart shown', pg.locator('.chart').count()==1)
    pg.screenshot(path='/tmp/c2-dash.png')
    # ── 5) termine + stammdaten + system tabs still work ──
    pg.click('button[data-tab="termine"]'); pg.wait_for_timeout(500)
    ck('termine shows booking', 'Elena' in pg.text_content('#view'))
    pg.click('button[data-tab="stamm"]'); pg.wait_for_timeout(400)
    ck('stammdaten renders', 'NIF' in pg.text_content('#view'))
    pg.click('button[data-tab="system"]'); pg.wait_for_timeout(400)
    ck('system renders', 'Agent' in pg.text_content('#view'))
    ck('console no js errors', not errs2) or print('   ',errs2)
    b.close()
srv.shutdown()
print('CONSOLE2 E2E '+('ALL PASSED' if not fails else 'FAILED: '+str(fails)))
sys.exit(1 if fails else 0)
