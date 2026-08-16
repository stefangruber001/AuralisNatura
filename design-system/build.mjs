/* Builds the distributable: one ESM bundle + one stylesheet.
   React stays external so a host app supplies it. */
import * as esbuild from 'esbuild';
import { mkdirSync, copyFileSync, readFileSync, writeFileSync } from 'node:fs';
import { execSync } from 'node:child_process';

mkdirSync('dist', { recursive: true });

await esbuild.build({
  entryPoints: ['src/index.tsx'],
  bundle: true,
  format: 'esm',
  target: 'es2020',
  jsx: 'automatic',
  external: ['react', 'react-dom', 'react/jsx-runtime'],
  outfile: 'dist/index.js',
  loader: { '.css': 'empty' },
  logLevel: 'info',
});

/* Flatten the stylesheet: tokens first, then the production component CSS.
   The site references the seal by relative path; a distributable stylesheet
   cannot, so it is inlined as a data URI and the bundle becomes self-contained. */
const tokens = readFileSync('src/styles/tokens.css', 'utf8');
let comps = readFileSync('src/styles/components.css', 'utf8');

/* Inline each referenced image ONCE as a token, then point every rule at it — the
   artwork is referenced several times, so embedding it per-rule multiplied the
   stylesheet. Add a row here whenever the site starts referencing a new image. */
const ASSETS = [
  { href: 'images/logo-emblem.png',    file: 'assets/logo-emblem.png',    v: '--seal-img' },
  { href: 'images/card-seal-gold.png', file: 'assets/card-seal-gold.png', v: '--card-seal-img' },
];
const sealVar = ':root{' + ASSETS.map(a => {
  const b64 = readFileSync(a.file).toString('base64');
  comps = comps.replaceAll(`url("${a.href}")`, `var(${a.v})`);
  return `${a.v}:url("data:image/png;base64,${b64}")`;
}).join(';') + '}\n';

const stillRelative = comps.match(/url\("(?!data:)[^"]+"\)/g);
if (stillRelative) {
  throw new Error('[build] unresolved asset reference(s): ' + [...new Set(stillRelative)].join(', '));
}

writeFileSync('dist/auralis.css', tokens + '\n' + sealVar + comps);

try {
  execSync('npx tsc -p tsconfig.json', { stdio: 'inherit' });
} catch {
  console.warn('[build] type declarations skipped (tsc unavailable)');
}
console.log('[build] dist/index.js + dist/auralis.css ready');
