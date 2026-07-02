import sys, os, threading
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT); sys.path.insert(0,ROOT)
for f in ['auralis.db','auralis.db-wal','auralis.db-shm']:
    p=os.path.join(ROOT,f); os.path.exists(p) and os.remove(p)
open(os.path.join(ROOT,'config','clients.json'),'w').write('{"clients":{}}')
os.environ['AURALIS_API_KEY']='k'
from werkzeug.serving import make_server
from server.app import app
srv=make_server('127.0.0.1',8815,app,threaded=True)
threading.Thread(target=srv.serve_forever,daemon=True).start()
from playwright.sync_api import sync_playwright
CHROME='/opt/pw-browsers/chromium-1194/chrome-linux/chrome'
with sync_playwright() as pw:
    b=pw.chromium.launch(executable_path=CHROME,args=['--no-sandbox'])
    pg=b.new_page(viewport={'width':720,'height':1050},device_scale_factor=2)
    pg.goto('http://127.0.0.1:8815/book',wait_until='networkidle'); pg.wait_for_timeout(700)
    pg.click('button[data-lang="de"]'); pg.wait_for_timeout(250)
    pg.click('.day >> nth=0'); pg.wait_for_timeout(350)
    pg.screenshot(path='/tmp/booking-page.png')
    pg.click('.slot >> nth=0'); pg.wait_for_timeout(300)
    pg.screenshot(path='/tmp/booking-details.png')
    b.close()
srv.shutdown()
print('shots saved')
