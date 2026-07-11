import sys, os, threading
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT); sys.path.insert(0,ROOT)
for f in ['auralis.db','auralis.db-wal','auralis.db-shm']:
    p=os.path.join(ROOT,f); os.path.exists(p) and os.remove(p)
p=os.path.join(ROOT,'config','availability.json'); os.path.exists(p) and os.remove(p)
open(os.path.join(ROOT,'config','clients.json'),'w').write('{"clients":{}}')
os.environ['AURALIS_API_KEY']='k'
from werkzeug.serving import make_server
from server.app import app
srv=make_server('127.0.0.1',5059,app,threaded=True)
threading.Thread(target=srv.serve_forever,daemon=True).start()
BASE='http://127.0.0.1:5059'
from playwright.sync_api import sync_playwright
CHROME='/opt/pw-browsers/chromium-1194/chrome-linux/chrome'
fails=[]
def ck(n,c): print(('  PASS ' if c else '  FAIL ')+n); (c or fails.append(n))
with sync_playwright() as pw:
    b=pw.chromium.launch(executable_path=CHROME,args=['--no-sandbox','--disable-gpu'])
    pg=b.new_page(viewport={'width':480,'height':900},device_scale_factor=2)
    errs=[]; pg.on('pageerror',lambda e:errs.append(str(e)))
    pg.goto(BASE+'/book',wait_until='networkidle'); pg.wait_for_timeout(600)
    ck('days rendered', pg.locator('.day').count()>0)
    pg.click('.day >> nth=0'); pg.wait_for_timeout(300)
    ck('slots shown', pg.locator('.slot').count()>0)
    pg.click('.slot >> nth=0'); pg.wait_for_timeout(300)
    ck('details step shown', pg.is_visible('#stepWho'))
    pg.fill('#bn','Elena Martín'); pg.fill('#be','elena@example.com')
    pg.select_option('#bl','de')
    pg.click('#stepWho .btn:not(.ghost)'); pg.wait_for_timeout(300)
    ck('pre-intake step shown', pg.is_visible('#stepYou'))
    pg.fill('#bo','Freue mich!')
    # safety-flag gate first
    pg.click('#confirmBtn'); pg.wait_for_timeout(300)
    ck('flags enforced', pg.is_visible('#stepYou') and len(pg.text_content('#err3').strip())>0)
    pg.click('#flagChips .chip >> nth=0'); pg.wait_for_timeout(150)   # "none of these"
    # consent gate second
    pg.click('#confirmBtn'); pg.wait_for_timeout(300)
    ck('consent enforced', pg.is_visible('#stepYou'))
    pg.check('#bc'); pg.click('#confirmBtn'); pg.wait_for_timeout(1200)
    ck('confirmation shown', pg.is_visible('#stepDone'))
    ck('when displayed', len(pg.text_content('#doneWhen').strip())>4)
    ck('no js errors', len(errs)==0) or print('   errs:',errs)
    # screenshots for the founder
    pg.screenshot(path='/tmp/book_done.png')
    pg2=b.new_page(viewport={'width':480,'height':900},device_scale_factor=2)
    pg2.goto(BASE+'/book',wait_until='networkidle'); pg2.wait_for_timeout(500)
    pg2.click('.day >> nth=1'); pg2.wait_for_timeout(300)
    pg2.screenshot(path='/tmp/book_slots.png')
    # language toggle
    pg2.click('button[data-lang="de"]'); pg2.wait_for_timeout(200)
    ck('DE toggle works', 'Wähle' in pg2.text_content('#stepTime'))
    b.close()
srv.shutdown()
os.path.exists(p) and os.remove(p)
print('BOOK UI '+('ALL PASSED' if not fails else 'FAILED: '+str(fails)))
sys.exit(1 if fails else 0)
