from playwright.sync_api import sync_playwright
CHROME='/opt/pw-browsers/chromium-1194/chrome-linux/chrome'
with sync_playwright() as p:
    b=p.chromium.launch(executable_path=CHROME, args=['--no-sandbox','--disable-gpu','--disable-dev-shm-usage'])
    pg=b.new_page(); pg.set_content('<h1 id=x>hi</h1>')
    print('launch ok, text=', pg.text_content('#x'))
    b.close()
print('done')
