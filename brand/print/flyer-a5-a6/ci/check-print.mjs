#!/usr/bin/env node
/**
 * Print-geometry and content checks for the Auralis Natura flyers.
 *
 * Usage:  node check-print.mjs <designDir> [--warn-dpi] [--json]
 *
 * Exits non-zero when any blocking check fails. See ../README.md ("CI") for
 * why each check exists — every one maps to a bug that occurred or nearly did.
 */
import { chromium } from '@playwright/test';
import { createServer } from 'node:http';
import { readFile, readdir, stat } from 'node:fs/promises';
import { extname, join, resolve } from 'node:path';
import { createRequire } from 'node:module';

const require = createRequire(import.meta.url);
const argv = process.argv.slice(2);
const DESIGN = resolve(argv[0] ?? '../design');
const WARN_DPI = argv.includes('--warn-dpi');
const AS_JSON = argv.includes('--json');
const SPEC = JSON.parse(await readFile(new URL('./spec.json', import.meta.url), 'utf8'));

const MM_PER_PT = 25.4 / 72;
const results = [];
const record = (level, check, page, msg) => results.push({ level, check, page, msg });
const pass = (c, p, m) => record('pass', c, p, m);
const fail = (c, p, m) => record('fail', c, p, m);
const warn = (c, p, m) => record('warn', c, p, m);

/* ------------------------------------------------------------------ server */
const MIME = { '.html':'text/html', '.js':'text/javascript', '.css':'text/css',
  '.png':'image/png', '.jpg':'image/jpeg', '.woff2':'font/woff2', '.json':'application/json' };

const server = createServer(async (req, res) => {
  try {
    const p = join(DESIGN, decodeURIComponent(new URL(req.url, 'http://x').pathname));
    const body = await readFile(p);
    res.writeHead(200, { 'content-type': MIME[extname(p)] ?? 'application/octet-stream' });
    res.end(body);
  } catch { res.writeHead(404).end('not found'); }
});
await new Promise(r => server.listen(0, r));
const ORIGIN = `http://127.0.0.1:${server.address().port}`;

/* ------------------------------------------------------------------- probe */
/** Runs in the page. Returns measured geometry for every artboard, in mm. */
const PROBE = () => {
  const out = [];
  const pages = [...document.querySelectorAll('section.page')];
  for (const sec of pages) {
    const r = sec.getBoundingClientRect();
    // px-per-mm derived from the page box itself, so zoom is irrelevant
    const probe = document.createElement('div');
    probe.style.cssText = 'position:absolute;width:100mm;height:100mm;visibility:hidden';
    sec.appendChild(probe);
    const pxPerMm = probe.getBoundingClientRect().width / 100;
    probe.remove();
    const mm = v => +(v / pxPerMm).toFixed(2);

    const art = [...sec.querySelectorAll(':scope > div')].find(d =>
      /height:\s*\d+(\.\d+)?mm/.test(d.getAttribute('style') || '') &&
      parseFloat(d.style.height) > 100);

    const smallest = [...sec.querySelectorAll('*')].reduce((acc, el) => {
      if (!el.textContent?.trim() || el.children.length) return acc;
      const fs = parseFloat(getComputedStyle(el).fontSize);
      return fs && fs < acc.px ? { px: fs, text: el.textContent.trim().slice(0, 40) } : acc;
    }, { px: Infinity, text: '' });

    const imgs = [...sec.querySelectorAll('img')].map(i => ({
      src: i.getAttribute('src'),
      naturalW: i.naturalWidth, naturalH: i.naturalHeight,
      placedWmm: mm(i.getBoundingClientRect().width),
      placedHmm: mm(i.getBoundingClientRect().height),
    }));

    const qrs = [...sec.querySelectorAll('svg[role="img"]')].map(s => {
      const b = s.getBoundingClientRect();
      return { label: s.getAttribute('aria-label'), sizeMm: mm(b.width),
               viewBox: s.getAttribute('viewBox'),
               shapeRendering: s.getAttribute('shape-rendering'),
               html: s.outerHTML };
    });

    // package rows: flex rows whose last child is a price-looking string
    const rows = [...sec.querySelectorAll('div')].filter(d =>
      /align-items:\s*baseline/.test(d.getAttribute('style') || ''));
    const prices = rows.map(d => d.lastElementChild?.textContent?.trim()).filter(Boolean);

    out.push({
      label: sec.getAttribute('data-screen-label') || '(unlabelled)',
      pageMm: [mm(r.width), mm(r.height)],
      art: art ? {
        wMm: mm(art.getBoundingClientRect().width),
        hMm: mm(art.getBoundingClientRect().height),
        leftMm: mm(art.getBoundingClientRect().left - r.left),
        topMm: mm(art.getBoundingClientRect().top - r.top),
        overflowPx: art.scrollHeight - art.clientHeight,
      } : null,
      smallestPt: smallest.px === Infinity ? null : smallest.px / (pxPerMm * (25.4 / 72)),
      smallestText: smallest.text,
      imgs, qrs, prices, rowCount: rows.length,
    });
  }
  return out;
};

/* ------------------------------------------------------------------- checks */
const browser = await chromium.launch();
const ctx = await browser.newContext({ viewport: { width: 1400, height: 1000 }, deviceScaleFactor: 2 });
const jsqrSrc = await readFile(require.resolve('jsqr/dist/jsQR.js'), 'utf8').catch(() => null);

for (const f of SPEC.files) {
  const page = await ctx.newPage();
  const consoleErrors = [];
  page.on('console', m => m.type() === 'error' && consoleErrors.push(m.text()));
  await page.goto(`${ORIGIN}/${encodeURIComponent(f.file)}`, { waitUntil: 'networkidle' });
  await page.waitForSelector('section.page', { timeout: 15000 });
  await page.waitForTimeout(1500); // let doc-page paginate and fonts settle

  const data = await page.evaluate(PROBE);
  const tag = f.file;

  if (consoleErrors.length) fail('console', tag, consoleErrors.slice(0, 3).join(' | '));

  // 0 — page count
  data.length === f.pages
    ? pass('pagecount', tag, `${data.length} pages`)
    : fail('pagecount', tag, `expected ${f.pages} pages, found ${data.length}`);

  const offsets = new Set();
  const boxes = new Set();

  for (const p of data) {
    const id = `${tag} :: ${p.label}`;
    if (!p.art) { fail('artboard', id, 'no artboard found'); continue; }

    // 1 — zero overflow
    p.art.overflowPx === 0
      ? pass('overflow', id, 'no overflow')
      : fail('overflow', id, `content overflows artboard by ${p.art.overflowPx}px — copy is being clipped`);

    // 2 — registration: collect page box + artboard offset
    boxes.add(p.pageMm.join('x'));
    offsets.add(`${p.art.leftMm}/${p.art.topMm}`);

    // 3 — trim + bleed
    if (f.artboardMm) {
      const [w, h] = f.artboardMm;
      const okW = Math.abs(p.art.wMm - w) < 0.5, okH = Math.abs(p.art.hMm - h) < 0.5;
      okW && okH
        ? pass('bleed', id, `artboard ${p.art.wMm}×${p.art.hMm}mm`)
        : fail('bleed', id, `artboard ${p.art.wMm}×${p.art.hMm}mm, expected ${w}×${h}mm (trim + 2×${SPEC.bleedMm}mm bleed)`);
    }

    // 4 — type floor
    if (p.smallestPt != null) {
      p.smallestPt >= SPEC.minTypePt - 0.05
        ? pass('typefloor', id, `smallest ${p.smallestPt.toFixed(1)}pt`)
        : fail('typefloor', id, `${p.smallestPt.toFixed(1)}pt is below the ${SPEC.minTypePt}pt floor — "${p.smallestText}"`);
    }

    for (const im of p.imgs) {
      // 5 — offline safety
      /^https?:/i.test(im.src)
        ? fail('offline', id, `remote image ${im.src} — will not render on a machine without network`)
        : pass('offline', id, `local asset ${im.src}`);

      // 6 — resolution
      if (im.naturalW && im.placedWmm) {
        const dpi = im.naturalW / (im.placedWmm / 25.4);
        const msg = `${im.src} → ${Math.round(dpi)} dpi at ${im.placedWmm}mm`;
        if (dpi >= SPEC.minDpi) pass('dpi', id, msg);
        else (WARN_DPI ? warn : fail)('dpi', id, `${msg} (min ${SPEC.minDpi})`);
      }
    }

    // 7a — QR structure + decode
    for (const q of p.qrs) {
      q.shapeRendering === 'crispEdges'
        ? pass('qr-render', id, 'crispEdges set')
        : fail('qr-render', id, 'QR missing shape-rendering="crispEdges" — module edges will antialias');
      const vb = (q.viewBox || '').split(/\s+/).map(Number);
      vb[0] <= -4 && vb[1] <= -4
        ? pass('qr-quietzone', id, `quiet zone ${-vb[0]} modules`)
        : fail('qr-quietzone', id, `quiet zone ${-vb[0]} modules, ISO minimum is 4`);
    }
  }

  if (jsqrSrc) {
    const decoded = await page.evaluate(async (src) => {
      const s = document.createElement('script'); s.textContent = src; document.head.appendChild(s);
      const out = [];
      for (const svg of document.querySelectorAll('svg[role="img"]')) {
        const N = 600;
        const blob = new Blob([new XMLSerializer().serializeToString(svg)], { type: 'image/svg+xml' });
        const url = URL.createObjectURL(blob);
        const img = await new Promise(r => { const i = new Image(); i.onload = () => r(i); i.onerror = () => r(null); i.src = url; });
        if (!img) { out.push(null); continue; }
        const c = document.createElement('canvas'); c.width = c.height = N;
        const g = c.getContext('2d');
        g.fillStyle = '#fff'; g.fillRect(0, 0, N, N);
        g.drawImage(img, 0, 0, N, N);
        const d = g.getImageData(0, 0, N, N);
        out.push(window.jsQR(d.data, N, N)?.data ?? null);
        URL.revokeObjectURL(url);
      }
      return out;
    }, jsqrSrc);

    decoded.forEach((payload, i) => {
      const id = `${tag} :: QR #${i + 1}`;
      if (!payload) { warn('qr-decode', id, 'could not decode (rasterisation issue, not necessarily a defect)'); return; }
      payload.replace(/^https?:\/\//, '').replace(/\/$/, '') === SPEC.expectedQrPayload
        ? pass('qr-decode', id, `→ ${payload}`)
        : fail('qr-decode', id, `points at "${payload}", expected "${SPEC.expectedQrPayload}"`);
    });
  } else {
    warn('qr-decode', tag, 'jsqr not installed — skipping payload decode (npm install)');
  }

  // 2 — registration verdict
  boxes.size === 1
    ? pass('registration', tag, `all pages ${[...boxes][0]}mm`)
    : fail('registration', tag, `page boxes differ: ${[...boxes].join(', ')} — front/back will not align on the sheet`);
  offsets.size === 1
    ? pass('registration', tag, `artboard offset ${[...offsets][0]}mm on every page`)
    : fail('registration', tag, `artboard offsets differ: ${[...offsets].join(', ')} — this is the front/back misalignment bug`);

  // 7b — content parity across languages
  const backs = data.filter(p => p.rowCount >= SPEC.packageRowsPerBack);
  if (backs.length) {
    const counts = new Set(backs.map(p => p.rowCount));
    counts.size === 1
      ? pass('parity', tag, `${[...counts][0]} package rows in every language`)
      : fail('parity', tag, `package row counts differ across languages: ${[...counts].join(', ')}`);

    const numeric = backs.map(p => p.prices.map(s => (s.match(/\d+/g) || []).join(',')).join('|'));
    new Set(numeric).size === 1
      ? pass('parity', tag, `prices identical across languages (${numeric[0]})`)
      : fail('parity', tag, `prices differ across languages: ${[...new Set(numeric)].join('  vs  ')}`);
  }

  await page.close();
}

await browser.close();
server.close();

/* ------------------------------------------------------------------ report */
const fails = results.filter(r => r.level === 'fail');
const warns = results.filter(r => r.level === 'warn');

if (AS_JSON) {
  console.log(JSON.stringify({ pass: results.filter(r => r.level === 'pass').length,
                               warn: warns.length, fail: fails.length, results }, null, 2));
} else {
  const byCheck = {};
  for (const r of results) (byCheck[r.check] ??= []).push(r);
  for (const [check, rs] of Object.entries(byCheck)) {
    const f = rs.filter(r => r.level === 'fail').length;
    const w = rs.filter(r => r.level === 'warn').length;
    const mark = f ? '\u001b[31mFAIL\u001b[0m' : w ? '\u001b[33mWARN\u001b[0m' : '\u001b[32m ok \u001b[0m';
    console.log(`[${mark}] ${check.padEnd(14)} ${rs.length - f - w}/${rs.length} passed`);
    for (const r of rs) if (r.level !== 'pass') console.log(`         ${r.level.toUpperCase()} ${r.page}: ${r.msg}`);
  }
  console.log(`\n${results.length - fails.length - warns.length} passed · ${warns.length} warnings · ${fails.length} failures`);
}

process.exit(fails.length ? 1 : 0);
