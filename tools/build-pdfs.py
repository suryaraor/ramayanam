"""Builds an easy-to-read PDF in data/ for every Word file in sources/ named NN-*.docx.

Each part gets a cover page, then the text set in a book-sized A5 page (fits a phone screen well),
a large Telugu font with roomy line spacing, centred verses, and page numbers. The Word files are
read only; they are never changed. Needs Python 3 and Google Chrome (or Microsoft Edge).

    python tools/build-pdfs.py                 # all parts
    python tools/build-pdfs.py 01-bala-kanda   # just one
"""
import html
import json
import re
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / 'sources'
OUT = ROOT / 'data'
BROWSERS = [
    r'C:\Program Files\Google\Chrome\Application\chrome.exe',
    r'C:\Program Files (x86)\Google\Chrome\Application\chrome.exe',
    r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',
    '/usr/bin/google-chrome', '/usr/bin/chromium', '/usr/bin/chromium-browser',
    '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
]


def books():
    """Titles from js/books.js (one line per part)."""
    text = (ROOT / 'js' / 'books.js').read_text(encoding='utf8')
    out = {}
    for key, title, en in re.findall(r"'([^']+)':\s*\{\s*title:\s*'([^']*)',\s*en:\s*'([^']*)'", text):
        out[key] = (title, en)
    return out


def paragraphs(docx):
    xml = zipfile.ZipFile(docx).read('word/document.xml').decode('utf8')
    body = xml.split('<w:body>', 1)[1]
    paras = []
    for p in re.findall(r'<w:p[ >].*?</w:p>', body, re.S):
        p = re.sub(r'<w:tab/>', ' ', p)
        p = re.sub(r'<w:br[^>]*/>', '\n', p)
        t = html.unescape(re.sub(r'<[^>]+>', '', p))
        t = re.sub(r'[ \u00a0]+', ' ', t).strip()
        if t and t not in {'.', '. .', '..'}:
            paras.append(t)
    return paras


CHANT = re.compile(r'^((జై\s*)?శ్రీ\s*రామ(్)?\s*)+$')


def kind(t):
    if CHANT.match(t):
        return 'chant'
    if len(t) < 45 and 'సమాప్త' in t:
        return 'end'
    if len(t) < 45 and re.search(r'కాండము|సర్గము', t):
        return 'h2'
    if len(t) < 30 and 'రామాయణ' in t:
        return 'eyebrow'
    if len(t) < 120 and not re.search(r'(\.|రి)\W*$', t):   # short lines that don't end like a prose sentence
        return 'verse'
    return 'p'


def body_html(paras, title):
    # Drop a leading heading that just repeats the cover, and stray text pasted after the very end.
    last_end = max((i for i, t in enumerate(paras) if kind(t) == 'end'), default=None)
    if last_end is not None:
        tail = paras[last_end + 1:]
        seen = ' '.join(paras[:last_end])
        keep = [t for t in tail if kind(t) == 'chant' or t[:60] not in seen]
        paras = paras[:last_end + 1] + keep
    out, verse = [], []

    def flush():
        if verse:
            out.append('<blockquote class="verse">' + '<br>'.join(html.escape(v) for v in verse) + '</blockquote>')
            verse.clear()

    first = True
    for t in paras:
        k = kind(t)
        if k == 'verse':
            verse.append(t)
            continue
        flush()
        e = html.escape(t)
        if k == 'h2':
            if first and t.replace(' ', '')[:6] == title.replace(' ', '')[:6]:
                first = False
                continue
            out.append(f'<h2>{e}</h2>')
        elif k == 'eyebrow':
            if not first:
                out.append(f'<p class="eyebrow">{e}</p>')
        elif k == 'end':
            out.append(f'<p class="end">{e}</p>')
        elif k == 'chant':
            out.append(f'<p class="chant">{e}</p>')
        else:
            out.append(f'<p>{e}</p>')
        first = False
    flush()
    return '\n'.join(out)


CSS = """
@page { size: 148mm 210mm; margin: 15mm 14mm 17mm; @bottom-center { content: counter(page); font: 10pt 'Noto Sans Telugu', sans-serif; color: #9a7a55; } }
@page :first { margin: 0; @bottom-center { content: none; } }
html { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
body { margin: 0; font-family: 'Noto Sans Telugu', 'Nirmala UI', sans-serif; font-size: 14pt; line-height: 1.85; color: #2a1f14; }
.cover { height: 210mm; box-sizing: border-box; padding: 30mm 16mm 22mm; display: flex; flex-direction: column; align-items: center; justify-content: space-between; text-align: center;
  background: radial-gradient(120% 70% at 50% 18%, #ffd27a 0%, #f08a1c 42%, #b3400c 78%, #6e1d06 100%); color: #fff8ec; break-after: page; }
.cover .om { font-size: 34pt; line-height: 1; opacity: .9; }
.cover .series { font-family: 'Ramabhadra', 'Noto Sans Telugu', sans-serif; font-size: 25pt; letter-spacing: .02em; margin-top: 8mm; text-shadow: 0 1px 6px rgba(80,20,0,.35); }
.cover .rule { width: 34mm; height: 0; border-top: 1.5pt solid rgba(255,248,236,.75); margin: 7mm auto; }
.cover h1 { font-family: 'Ramabhadra', 'Noto Sans Telugu', sans-serif; font-weight: 400; font-size: 30pt; line-height: 1.45; margin: 0; text-shadow: 0 2px 10px rgba(80,20,0,.4); }
.cover .en { font-family: Georgia, serif; font-style: italic; font-size: 13pt; margin-top: 5mm; opacity: .92; }
.cover .bow { width: 46mm; opacity: .85; }
.cover .foot { font-size: 11pt; opacity: .9; }
h2 { font-family: 'Ramabhadra', 'Noto Sans Telugu', sans-serif; font-weight: 400; font-size: 21pt; color: #a8460c; text-align: center; margin: 4mm 0 6mm; break-before: page; break-after: avoid; }
h2:first-child { break-before: auto; }
.eyebrow { text-align: center; color: #9a7a55; font-size: 12pt; margin: 0; break-before: page; break-after: avoid; }
.eyebrow + h2 { break-before: auto; }
p { margin: 0 0 4.2mm; text-align: start; orphans: 2; widows: 2; }
.verse { margin: 5mm 2mm 6mm; padding: 3.5mm 4mm; border-left: 2.5pt solid #e5953a; background: #fdf3e3; color: #6b3410; font-size: 13.5pt; line-height: 1.8; text-align: center; break-inside: avoid; }
.end { text-align: center; font-family: 'Ramabhadra', 'Noto Sans Telugu', sans-serif; color: #a8460c; font-size: 16pt; margin: 9mm 0 3mm; }
.end::before { content: '❀  '; } .end::after { content: '  ❀'; }
.chant { text-align: center; color: #c06a1c; font-size: 12pt; letter-spacing: .03em; }
"""

BOW = """<svg class="bow" viewBox="0 0 120 40" fill="none" stroke="#fff8ec" stroke-width="2.2" stroke-linecap="round">
<path d="M10 36 C40 4, 80 4, 110 36"/><path d="M10 36 L110 36" stroke-width="1.2"/><path d="M60 38 L60 12"/><path d="M54 18 L60 10 L66 18"/></svg>"""


def page_html(title, en, body):
    return f"""<!doctype html><html lang="te"><head><meta charset="utf-8"><title>{html.escape(title)}</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+Telugu:wght@400;500&family=Ramabhadra&display=block" rel="stylesheet">
<style>{CSS}</style></head><body>
<section class="cover"><div><div class="om">ॐ</div><div class="series">శ్రీమద్రామాయణము</div></div>
<div><h1>{html.escape(title).replace(' · ', '<br>')}</h1><div class="rule"></div><div class="en">{html.escape(en)}</div></div>
<div>{BOW}<div class="foot">శ్రీ రామ జయ రామ జయ జయ రామ</div></div></section>
<main>{body}</main></body></html>"""


def browser():
    for b in BROWSERS:
        if Path(b).exists():
            return b
    sys.exit('Chrome or Edge not found; add its path to BROWSERS in tools/build-pdfs.py')


def main():
    only = sys.argv[1] if len(sys.argv) > 1 else ''
    names = books()
    OUT.mkdir(exist_ok=True)
    exe = browser()
    with tempfile.TemporaryDirectory() as tmp:
        for docx in sorted(SRC.glob('[0-9][0-9]-*.docx')):
            key = docx.stem
            if only and key != only:
                continue
            title, en = names.get(key, (key, ''))
            page = Path(tmp) / f'{key}.html'
            page.write_text(page_html(title, en, body_html(paragraphs(docx), title)), encoding='utf8')
            pdf = OUT / f'{key}.pdf'
            subprocess.run([exe, '--headless=new', '--disable-gpu', '--no-pdf-header-footer', '--run-all-compositor-stages-before-draw',
                            '--virtual-time-budget=20000', f'--user-data-dir={Path(tmp) / "profile"}', f'--print-to-pdf={pdf}', page.as_uri()],
                           check=True, capture_output=True, timeout=300)
            print(f'{pdf.name}  {pdf.stat().st_size // 1024} KB')


if __name__ == '__main__':
    main()
