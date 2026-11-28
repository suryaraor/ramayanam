/* Offline support.
 *
 * - The app shell (HTML, CSS, JS, PDF.js) is precached on install, so the site
 *   opens with no connection.
 * - Every issue a reader opens is saved by the page into the "mag-issues" cache
 *   (see saveOffline() in js/app.js). This worker serves those PDFs from the
 *   cache, including the byte-range requests PDF.js makes.
 * - Fonts and PDF.js font data from CDNs are cached the first time they load.
 *
 * Bump VERSION whenever a shell file changes so readers pick up the update.
 */
const VERSION = 'r12';
const SHELL = `ram-shell-${VERSION}`;
const RUNTIME = 'ram-runtime';
const ISSUES = 'ram-parts';

const SHELL_FILES = [
  './',
  'index.html',
  'css/style.css',
  'js/app.js',
  'js/books.js',
  'vendor/pdfjs/pdf.min.mjs',
  'vendor/pdfjs/pdf.worker.min.mjs',
];

self.addEventListener('install', (e) => {
  e.waitUntil((async () => {
    const c = await caches.open(SHELL);
    await c.addAll(SHELL_FILES.map((f) => new Request(f, { cache: 'reload' })));
    await self.skipWaiting();
  })());
});

self.addEventListener('activate', (e) => {
  e.waitUntil((async () => {
    for (const k of await caches.keys()) {
      if (k.startsWith('ram-shell-') && k !== SHELL) await caches.delete(k);
    }
    await self.clients.claim();
  })());
});

self.addEventListener('fetch', (e) => {
  const req = e.request;
  if (req.method !== 'GET') return;
  const url = new URL(req.url);

  if (url.origin === location.origin) {
    if (/\.pdf$/i.test(url.pathname)) { e.respondWith(servePdf(req)); return; }
    if (req.mode === 'navigate') { e.respondWith(networkFirst(req, SHELL, 'index.html')); return; }
    if (url.pathname.endsWith('/magazines.json')) { e.respondWith(networkFirst(req, RUNTIME)); return; }
    e.respondWith(staleWhileRevalidate(req, SHELL));
    return;
  }

  // Google Fonts and PDF.js cmaps / standard fonts
  if (/^(fonts\.googleapis\.com|fonts\.gstatic\.com|cdn\.jsdelivr\.net)$/.test(url.hostname)) {
    e.respondWith(staleWhileRevalidate(req, RUNTIME));
  }
});

async function networkFirst(req, cacheName, fallbackPath) {
  const cache = await caches.open(cacheName);
  try {
    const res = await fetch(req);
    if (res.ok) cache.put(req.mode === 'navigate' ? 'index.html' : req, res.clone());
    return res;
  } catch (err) {
    const hit = await cache.match(req, { ignoreSearch: true })
      || (fallbackPath && await cache.match(fallbackPath));
    if (hit) return hit;
    throw err;
  }
}

async function staleWhileRevalidate(req, cacheName) {
  const cache = await caches.open(cacheName);
  const hit = await cache.match(req, { ignoreSearch: true });
  const net = fetch(req).then((res) => {
    if (res.ok || res.type === 'opaque') cache.put(req, res.clone());
    return res;
  }).catch(() => null);
  if (hit) return hit;
  return (await net) || Response.error();
}

/* Serve a saved issue from the cache, answering Range requests with 206. */
async function servePdf(req) {
  const cache = await caches.open(ISSUES);
  const hit = await cache.match(req.url);
  if (!hit) return fetch(req);

  const range = req.headers.get('range');
  if (!range) return hit;

  const blob = await hit.blob();
  const size = blob.size;
  const m = /^bytes=(\d*)-(\d*)$/.exec(range.trim());
  if (!m) return hit;
  let start, end;
  if (m[1] === '') { start = Math.max(0, size - Number(m[2])); end = size - 1; }  // suffix range
  else { start = Number(m[1]); end = m[2] === '' ? size - 1 : Math.min(Number(m[2]), size - 1); }
  if (start >= size || start > end) {
    return new Response(null, { status: 416, headers: { 'Content-Range': `bytes */${size}` } });
  }
  return new Response(blob.slice(start, end + 1), {
    status: 206,
    headers: {
      'Content-Type': 'application/pdf',
      'Content-Length': String(end - start + 1),
      'Content-Range': `bytes ${start}-${end}/${size}`,
      'Accept-Ranges': 'bytes',
    },
  });
}
