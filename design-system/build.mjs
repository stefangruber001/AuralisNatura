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

const seal = readFileSync('assets/logo-emblem.png').toString('base64');
/* Inline the seal ONCE as a token, then point every rule at it — the artwork is
   referenced three times, so embedding it per-rule tripled the stylesheet. */
const sealVar = `:root{--seal-img:url("data:image/png;base64,${seal}")}\n`;
comps = comps.replace(/url\("images\/logo-emblem\.png"\)/g, 'var(--seal-img)');

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
