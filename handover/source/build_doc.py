#!/usr/bin/env python3
"""
Auralis Natura — portable document builder.
Wraps a body-HTML fragment with the shared <head> (fonts, meta) + doc_base.css +
foot, base64-injects the brand seal for {{SEAL}} tokens, and writes a finished,
self-contained HTML file.

Paths resolve relative to this script, so it runs anywhere:
  - CSS  : <this dir>/doc_base.css            (source/)
  - SEAL : <this dir>/../assets/seal_320_opt.png
  - OUT  : <this dir>/../deliverables/        (created if missing)

Usage:
  python3 source/build_doc.py source/doc2_body.html "02-Business-Plan.html" "Business Plan" "Meta description."
"""
import base64, sys, os

HERE = os.path.dirname(os.path.abspath(__file__))           # .../source
ROOT = os.path.dirname(HERE)                                 # project root
CSS_PATH  = os.path.join(HERE, 'doc_base.css')
SEAL_PATH = os.path.join(ROOT, 'assets', 'seal_320_opt.png')
OUT_DIR   = os.path.join(ROOT, 'deliverables')

CSS  = open(CSS_PATH, 'r', encoding='utf-8').read()
SEAL = "data:image/png;base64," + base64.b64encode(open(SEAL_PATH, 'rb').read()).decode('ascii')

HEAD = '''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<script>document.documentElement.className+=' js';</script>
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>__TITLE__ — Auralis Natura</title>
<meta name="description" content="__DESC__" />
<link rel="icon" type="image/png" href="{{SEAL}}" />
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Fraunces:ital,opsz,wght@0,9..144,300..600;1,9..144,300..500&family=Hanken+Grotesk:wght@300;400;500;600;700&family=IBM+Plex+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>__CSS__</style>
</head>
<body>
'''
FOOT = '''
</body>
</html>'''

def build(body_path, out_name, title, desc):
    body = open(body_path, 'r', encoding='utf-8').read()
    html = HEAD.replace('__TITLE__', title).replace('__DESC__', desc).replace('__CSS__', CSS) + body + FOOT
    html = html.replace('{{SEAL}}', SEAL)
    os.makedirs(OUT_DIR, exist_ok=True)
    out = os.path.join(OUT_DIR, out_name)
    open(out, 'w', encoding='utf-8').write(html)
    leftover = html.count('{{SEAL}}') + html.count('__CSS__') + html.count('__TITLE__') + html.count('__DESC__')
    print(f"OK  {out_name}: {len(html):,} chars  |  leftover tokens: {leftover}  ->  {out}")

if __name__ == '__main__':
    if len(sys.argv) != 5:
        print('Usage: python3 build_doc.py <body.html> <out_name.html> "<Title>" "<Description>"')
        sys.exit(1)
    build(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4])
