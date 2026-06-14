from playwright.sync_api import sync_playwright
import sys

src = sys.argv[1]
out = sys.argv[2]
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page()
    pg.goto("file://" + src, wait_until="networkidle")
    # ensure web fonts are fully loaded before printing
    pg.evaluate("document.fonts.ready")
    pg.wait_for_timeout(1200)
    pg.pdf(
        path=out,
        format="A4",
        print_background=True,
        margin={"top": "6mm", "bottom": "6mm", "left": "6mm", "right": "6mm"},
        prefer_css_page_size=False,
    )
    b.close()
print("PDF written:", out)
