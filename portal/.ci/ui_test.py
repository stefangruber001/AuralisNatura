import sys, os, threading
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT); sys.path.insert(0, ROOT)
# clean db
for f in ['auralis.db','auralis.db-wal','auralis.db-shm']:
    p=os.path.join(ROOT,f);  os.path.exists(p) and os.remove(p)
open(os.path.join(ROOT,'config','clients.json'),'w').write('{"clients":{}}')
os.environ['AURALIS_API_KEY']='dev-staff-key-change-me'

from werkzeug.serving import make_server
from server.app import app
PORT=5058
srv=make_server('127.0.0.1',PORT,app,threaded=True)
threading.Thread(target=srv.serve_forever,daemon=True).start()
BASE=f'http://127.0.0.1:{PORT}'

tc=app.test_client()
r=tc.post('/api/clients',headers={'X-Auralis-Key':'dev-staff-key-change-me'},json={'name':'Elena Martín','email':'elena@example.com','language':'en'})
CID=r.get_json()['client_id']; PWD=r.get_json()['password']; print('seeded',CID)

from playwright.sync_api import sync_playwright
CHROME='/opt/pw-browsers/chromium-1194/chrome-linux/chrome'
fails=[]
def ck(n,c): print(('  PASS ' if c else '  FAIL ')+n); (c or fails.append(n))
with sync_playwright() as p:
    b=p.chromium.launch(executable_path=CHROME,args=['--no-sandbox','--disable-gpu','--disable-dev-shm-usage'])
    pg=b.new_page(); errs=[]; pg.on('pageerror',lambda e:errs.append(str(e)))
    pg.goto(BASE+'/portal',wait_until='networkidle')
    pg.fill('#cid',CID); pg.fill('#pw',PWD); pg.click('button:has-text("Sign in")'); pg.wait_for_timeout(400)
    ck('login->intake',pg.is_visible('#intake'))
    pg.fill('[data-k="goal"]','more energy'); pg.fill('[data-k="why_now"]','tired'); pg.select_option('[data-k="language"]','en')
    pg.click('#next'); pg.wait_for_timeout(120)
    pg.click('[data-scale="energy"] button:nth-child(2)'); pg.click('[data-scale="stress"] button:nth-child(4)')
    pg.click('#next'); pg.wait_for_timeout(100); pg.fill('[data-k="symptoms"]','crash'); pg.click('#next'); pg.wait_for_timeout(100)
    pg.check('#flagNone'); pg.click('#next'); pg.wait_for_timeout(100)
    pg.check('#c1'); pg.check('#c2'); pg.click('#next'); pg.wait_for_timeout(500)
    ck('portal thanks',pg.is_visible('#thanks')); ck('portal no-js-errors',len(errs)==0) or print('   portal errs:',errs)
    sp=b.new_page(); serr=[]; sp.on('pageerror',lambda e:serr.append(str(e))); sp.on('dialog',lambda d:d.accept())
    sp.goto(BASE+'/staff',wait_until='networkidle'); sp.fill('#key','dev-staff-key-change-me'); sp.click('button:has-text("Unlock")'); sp.wait_for_timeout(400)
    sp.click('.cl .n'); sp.wait_for_timeout(400); ck('staff prep shown',sp.is_visible('text=Meeting prep'))
    sp.fill('#notes','warm'); sp.click('button:has-text("Save notes")'); sp.wait_for_timeout(250)
    sp.click('button:has-text("Draft report with the agent")'); sp.wait_for_timeout(500)
    n=sp.locator('[data-si]').count(); ck('draft 6 sections',n==6)
    if n==6:
        sp.fill('[data-si="0"]',sp.input_value('[data-si="0"]')+' [edited]'); sp.check('#approve')
        sp.click('button:has-text("Generate report + email draft")')
        st='review'
        for _ in range(30):
            sp.wait_for_timeout(700)
            st=tc.get('/api/client/'+CID,headers={'X-Auralis-Key':'dev-staff-key-change-me'}).get_json()['record']['stage']
            if st in ('sent','done'): break
        print('   server stage after generate:',st)
        ck('stage sent',st in ('sent','done'))
        pdf=os.path.join(ROOT,'output_docs',CID,'report','report.pdf')
        ck('report.pdf produced',os.path.exists(pdf) and os.path.getsize(pdf)>10000)
        import glob
        ck('email .eml drafted',bool(glob.glob(os.path.join(ROOT,'output_docs',CID,'sent','*.eml'))))
    ck('staff no-js-errors',len(serr)==0) or print('   staff errs:',serr)
    b.close()
srv.shutdown()
print('\n'+('UI E2E ALL PASSED' if not fails else 'FAILED: '+str(fails)))
sys.exit(1 if fails else 0)
