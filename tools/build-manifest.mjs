#!/usr/bin/env node
// Builds magazines.json (the list of parts) from every PDF in data/, in story order, with the names from js/books.js.
// Run locally with:  node tools/build-manifest.mjs
// It also writes a plain-HTML copy of the shelf into index.html (between the shelf markers), so the
// covers and links show even on older iPads and iPhones whose browser can't run js/app.js.
import { existsSync, readdirSync, readFileSync, statSync, writeFileSync } from 'node:fs';
import { execFileSync } from 'node:child_process';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const dataDir = path.join(root, 'data');
const { BOOKS } = await import(pathToFileURL(path.join(root, 'js', 'books.js')).href);

function titleFromName(name) {
  return name
    .replace(/\.pdf$/i, '')
    .replace(/[_-]+/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
    .replace(/\b\p{Ll}/gu, (c) => c.toUpperCase());
}

function publishedDate(rel, stat) {
  // Prefer the date the file was first committed; fall back to its modified time.
  try {
    const out = execFileSync('git', ['log', '--diff-filter=A', '--follow', '--format=%cI', '--', rel], { cwd: root, encoding: 'utf8', stdio: ['ignore', 'pipe', 'ignore'] })
      .trim().split('\n').filter(Boolean);
    if (out.length) return out[out.length - 1];
  } catch { /* not a git checkout */ }
  return stat.mtime.toISOString();
}

let files = [];
try {
  files = readdirSync(dataDir).filter((f) => /\.pdf$/i.test(f));
} catch { /* no data dir yet */ }

const magazines = files.map((name) => {
  const rel = `data/${name}`;
  const stat = statSync(path.join(dataDir, name));
  const b = BOOKS[name.replace(/\.pdf$/i, '')] || {};
  const base = name.replace(/\.pdf$/i, '');
  const counts = [...readFileSync(path.join(dataDir, name), 'latin1').matchAll(/\/Count (\d+)/g)].map((x) => +x[1]);
  const cover = existsSync(path.join(root, 'covers', `${base}.jpg`)) ? `covers/${base}.jpg` : '';
  return { file: rel, name, title: b.title || titleFromName(name), en: b.en || '', pages: counts.length ? Math.max(...counts) : 0, cover, size: stat.size, date: publishedDate(rel, stat) };
}).sort((a, b) => a.name.localeCompare(b.name, undefined, { numeric: true }));   // story order: 01, 02, ...

writeFileSync(path.join(root, 'magazines.json'), JSON.stringify({ generated: new Date().toISOString(), magazines }, null, 2) + '\n');
console.log(`magazines.json: ${magazines.length} part(s)`);
for (const m of magazines) console.log(`  - ${m.title}  (${m.file})`);

// Plain-HTML shelf for browsers that can't run the app (app.js replaces it when it runs)
const esc = (t) => String(t).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const mb = (b) => (b < 1048576 ? `${Math.round(b / 1024)} KB` : `${(b / 1048576).toFixed(1)} MB`);
const cards = magazines.map((m) => `        <li class="card"><a class="cover" href="${esc(m.file)}">${m.cover ? `<img src="${esc(m.cover)}" alt="">` : `<span class="cover-ph">${esc(m.title)}</span>`}</a>
          <div class="meta"><h3>${esc(m.title)}</h3><p class="sub">${[m.en, m.pages ? `${m.pages} పేజీలు` : '', mb(m.size)].filter(Boolean).map(esc).join(' · ')}</p>
          <div class="actions"><a class="btn primary" href="${esc(m.file)}"><span class="lbl">చదవండి</span></a></div></div></li>`).join('\n');
const indexPath = path.join(root, 'index.html');
const html = readFileSync(indexPath, 'utf8');
const next = html.replace(/(<!-- shelf:start -->)[\s\S]*?(<!-- shelf:end -->)/, `$1
${cards}
        $2`);
if (next !== html) writeFileSync(indexPath, next);
