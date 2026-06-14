from playwright.sync_api import sync_playwright
import sys
url = "file://" + sys.argv[1]
prefix = sys.argv[2]
ids = sys.argv[3].split(",")
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width":1200,"height":900}, device_scale_factor=2)
    pg.goto(url, wait_until="networkidle")
    pg.add_style_tag(content=".reveal{opacity:1!important;transform:none!important}")
    pg.wait_for_timeout(700)
    for i in ids:
        el = pg.query_selector("#" + i)
        if el:
            out = f"/home/claude/{prefix}_{i}.png"
            el.screenshot(path=out)
            print("shot:", out)
        else:
            print("MISSING:", i)
    b.close()
