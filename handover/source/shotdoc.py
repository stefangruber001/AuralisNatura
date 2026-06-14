from playwright.sync_api import sync_playwright
import sys
url = "file://" + sys.argv[1]
out = sys.argv[2]
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width":1200,"height":900}, device_scale_factor=2)
    pg.goto(url, wait_until="networkidle")
    pg.add_style_tag(content=".reveal{opacity:1!important;transform:none!important}")
    pg.wait_for_timeout(900)
    pg.screenshot(path=out, full_page=True)
    b.close()
print("shot:",out)
