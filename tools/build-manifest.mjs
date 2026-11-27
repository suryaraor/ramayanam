#!/usr/bin/env node
// Builds magazines.json (the list of parts) from every PDF in data/, in story order, with the names from js/books.js.
// Run locally with:  node tools/build-manifest.mjs
// The GitHub Actions workflow runs it automatically on every push.
import { readdirSync, statSync, writeFileSync } from 'node:fs';
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
  return { file: rel, name, title: b.title || titleFromName(name), en: b.en || '', size: stat.size, date: publishedDate(rel, stat) };
}).sort((a, b) => a.name.localeCompare(b.name, undefined, { numeric: true }));   // story order: 01, 02, ...

writeFileSync(path.join(root, 'magazines.json'), JSON.stringify({ generated: new Date().toISOString(), magazines }, null, 2) + '\n');
console.log(`magazines.json: ${magazines.length} part(s)`);
for (const m of magazines) console.log(`  - ${m.title}  (${m.file})`);
