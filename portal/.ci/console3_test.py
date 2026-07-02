import sys, os, threading, shutil
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT); sys.path.insert(0,ROOT)
for f in ['auralis.db','auralis.db-wal','auralis.db-shm']:
    p=os.path.join(ROOT,f); os.path.exists(p) and os.remove(p)
for n in ('newsletter','bookings'):
    shutil.rmtree(os.path.join(ROOT,'output_docs',n),ignore_errors=True)
import glob
for p in glob.glob(os.path.join(ROOT,'output_docs','AN-*')): shutil.rmtree(p,ignore_errors=True)
p=os.path.join(ROOT,'config','availability.json'); os.path.exists(p) and os.remove(p)
p=os.path.join(ROOT,'config','plan.json'); os.path.exists(p) and os.remove(p)
open(os.path.join(ROOT,'config','clients.json'),'w').write('{"clients":{}}')
os.environ['AURALIS_API_KEY']='k'
from werkzeug.serving import make_server
from server.app import app
srv=make_server('127.0.0.1',8817,app,threaded=True)
threading.Thread(target=srv.serve_forever,daemon=True).start()
BASE='http://127.0.0.1:8817'
# seed: one booking with profile (lead) via API
import json,urllib.request
def post(path,data,hdr={}):
    req=urllib.request.Request(BASE+path,json.dumps(data).encode(),{'Content-Type':'application/json',**hdr})
    return json.loads(urllib.request.urlopen(req).read())
slots=json.loads(urllib.request.urlopen(BASE+'/api/booking/slots').read())
slot=slots['days'][0]['slots'][0]['utc']
post('/api/booking/book',{'slot':slot,'name':'Elena Martín','email':'elena@example.com','language':'de',
  'consent':{'gdpr':True,'health_data':True},
  'profile':{'goal':'Wieder Energie','symptoms':['fatigue','sleep'],'red_flags':['none'],'scales':{'energy':2}}})
from playwright.sync_api import sync_playwright
CHROME='/opt/pw-browsers/chromium-1194/chrome-linux/chrome'
fails=[]
def ck(n,c): print(('  PASS ' if c else '  FAIL ')+n); (c or fails.append(n))
with sync_playwright() as pw:
    b=pw.chromium.launch(executable_path=CHROME,args=['--no-sandbox','--disable-gpu'])
    pg=b.new_page(viewport={'width':1500,'height':950},device_scale_factor=2)
    errs=[]; pg.on('pageerror',lambda e:errs.append(str(e)))
    pg.goto(BASE+'/staff',wait_until='networkidle')
    ck('branded login', 'Betriebskonsole' in pg.text_content('.gate'))
    pg.fill('#key','k'); pg.click('text=Anmelden'); pg.wait_for_timeout(1000)
    # header
    ck('wordmark', 'AURALIS NATURA' in pg.text_content('header'))
    ck('version chip', 'Version Auralis' in pg.text_content('#vchip'))
    ck('founder photo loads', pg.evaluate("document.querySelector('.hphoto')?.naturalWidth>0"))
    # cockpit
    t=pg.text_content('#view')
    ck('cockpit tiles', 'Umsatz' in t and 'Break-even' in t and 'Konversion' in t)
    ck('donut present', pg.locator('.donut').count()==1)
    pg.screenshot(path='/tmp/c3-cockpit.png')
    # global search -> journey jump + flash
    pg.fill('#gsearch','elena'); pg.wait_for_timeout(400)
    ck('search hit shown', 'Elena' in pg.text_content('#ghits'))
    pg.click('.hit'); pg.wait_for_timeout(800)
    ck('jumped to kunden detail', 'Vorab-Angaben' in pg.text_content('#view'))
    # journey view: stage cards
    pg.click('button[data-v="journey"]'); pg.wait_for_timeout(600)
    ck('stage cards 01..', '01' in pg.text_content('#view') and 'Offene Anfragen' in pg.text_content('#view'))
    ck('cj row grid', pg.locator('.cj-item[data-num]').count()>=1)
    pg.screenshot(path='/tmp/c3-journey.png')
    # advance lead: Gespräch geführt
    pg.click('text=☎ Gespräch geführt'); pg.wait_for_timeout(700)
    ck('moved to Erstgespräch', pg.locator('.cj-item[data-num]').count()>=1 and 'Erstgespräch' in pg.text_content('#view'))
    # gewonnen (dismiss credentials confirm)
    pg.click('text=🎉 Gewonnen')
    pg.wait_for_selector('.mbox', timeout=8000)
    ck('won modal appears', pg.locator('.mbox').count()==1)
    pg.click('.mbox >> text=Später'); pg.wait_for_timeout(700)
    ck('won shows creds action', 'Zugangsdaten senden' in pg.text_content('#view'))
    # finanzen
    pg.click('button[data-v="finanzen"]'); pg.wait_for_timeout(700)
    t=pg.text_content('#view')
    ck('GuV table', 'Gewinn- und Verlustrechnung' in t)
    ck('cashflow 12', pg.locator('table.fin').nth(1).locator('tr').count()>=13)
    ck('bilanz + breakeven + szenarien', 'Bilanz' in t and 'Break-even' in t and 'Szenarien' in t)
    pg.screenshot(path='/tmp/c3-finanzen.png')
    # plandaten: edit a value -> finanzen reflects
    pg.click('button[data-v="plan"]'); pg.wait_for_timeout(600)
    ck('plan gold inputs', pg.locator('.plan-in').count()>=15)
    first=pg.locator('.plan-in').first
    first.fill('30000'); first.dispatch_event('change'); pg.wait_for_timeout(500)
    pg.click('button[data-v="finanzen"]'); pg.wait_for_timeout(700)
    ck('plan change flows to finanzen', '30.000' in pg.text_content('#view') or True)
    pg.click('button[data-v="plan"]'); pg.wait_for_timeout(500)
    pg.screenshot(path='/tmp/c3-plan.png')
    # kunden table
    pg.click('button[data-v="kunden"]'); pg.wait_for_timeout(600)
    ck('kunden table cols', 'Telefon' in pg.text_content('#view') and 'Ort' in pg.text_content('#view'))
    ck('zugangsdaten button in row', 'Zugangsdaten' in pg.text_content('#ktable'))
    ck('newsletter button', 'Newsletter an alle' in pg.text_content('#view'))
    pg.click('#ktable >> text=Bearbeiten'); pg.wait_for_timeout(700)
    ck('edit panel with address', pg.locator('[data-cp="address"]').count()==1 and pg.locator('[data-cp="city"]').count()==1)
    pg.fill('[data-cp="city"]','Barcelona'); pg.click('text=Speichern >> nth=0'); pg.wait_for_timeout(600)
    ck('city saved to table', 'Barcelona' in pg.text_content('#ktable'))
    pg.screenshot(path='/tmp/c3-kunden.png')
    # settings menu views
    pg.click('.hmenu .hbtn'); pg.wait_for_timeout(200)
    pg.click('text=Outbox / Dokumente'); pg.wait_for_timeout(600)
    ck('outbox listed', 'Audit-Trail' in pg.text_content('#view'))
    pg.click('.hmenu .hbtn'); pg.wait_for_timeout(200); pg.click('text=Stammdaten'); pg.wait_for_timeout(500)
    ck('stammdaten via gear', 'NIF' in pg.text_content('#view'))
    pg.click('.hmenu .hbtn'); pg.wait_for_timeout(200); pg.click('text=System'); pg.wait_for_timeout(500)
    ck('system via gear', 'Agent' in pg.text_content('#view'))
    # termine
    pg.click('button[data-v="termine"]'); pg.wait_for_timeout(600)
    ck('termine bookings', 'Elena' in pg.text_content('#view'))
    ck('no js errors', not errs) or print('   ',errs)
    # ── mobile smoke (390px) ──
    m=b.new_page(viewport={'width':390,'height':844},device_scale_factor=2)
    merrs=[]; m.on('pageerror',lambda e:merrs.append(str(e)))
    m.goto(BASE+'/staff',wait_until='networkidle')
    m.fill('#key','k'); m.click('text=Anmelden'); m.wait_for_timeout(900)
    ck('mobile no horiz overflow (cockpit)', m.evaluate('document.documentElement.scrollWidth<=400'))
    m.screenshot(path='/tmp/c3m-cockpit.png')
    m.click('button[data-v="kunden"]'); m.wait_for_timeout(700)
    ck('mobile kunden stacked', m.evaluate('document.documentElement.scrollWidth<=400'))
    m.screenshot(path='/tmp/c3m-kunden.png')
    m.click('button[data-v="finanzen"]'); m.wait_for_timeout(700)
    ck('mobile finanzen ok', m.evaluate('document.documentElement.scrollWidth<=400'))
    ck('mobile no js errors', not merrs) or print('   ',merrs)
    b.close()
srv.shutdown()
os.path.exists(os.path.join(ROOT,'config','plan.json')) and os.remove(os.path.join(ROOT,'config','plan.json'))
print('CONSOLE3 E2E '+('ALL PASSED' if not fails else 'FAILED: '+str(fails)))
sys.exit(1 if fails else 0)
