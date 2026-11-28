"""Writes the text the review page shows: one JSON file per part under review/, with every
paragraph's index in the Word source, its kind (heading, verse, ...) and its PDF page.

Pages come from printing a copy of each part with an invisible marker at the start of every
paragraph and reading the markers back with poppler's pdftotext (same trick as corrections-page.py).

    python tools/review-data.py [out_dir]
"""
import importlib.util
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location('build_pdfs', ROOT / 'tools' / 'build-pdfs.py')
bp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bp)

orig_kind = bp.kind
bp.kind = lambda t: orig_kind(bp.MARK.sub('', t))   # markers must not change how a paragraph is classified


def pages_for(key, paras, exe, tmp):
    marked = [f'{i}' + t for i, t in enumerate(paras)]
    title, en = bp.books().get(key, (key, ''))
    page = Path(tmp) / f'{key}.html'
    page.write_text(bp.page_html(title, en, bp.body_html(marked, title)), encoding='utf8')
    pdf = Path(tmp) / f'{key}.pdf'
    subprocess.run([bp.browser(), '--headless=new', '--disable-gpu', '--no-pdf-header-footer', '--run-all-compositor-stages-before-draw',
                    '--virtual-time-budget=20000', f'--user-data-dir={Path(tmp) / "profile"}', f'--print-to-pdf={pdf}', page.as_uri()],
                   check=True, capture_output=True, timeout=300)
    text = subprocess.run(['pdftotext', '-enc', 'UTF-8', str(pdf), '-'], check=True, capture_output=True).stdout.decode('utf8', 'replace')
    found = {}
    for pno, ptxt in enumerate(text.split('\f'), start=1):
        for m in re.finditer(r'#(\d+)#', ptxt):
            found.setdefault(int(m.group(1)), pno)
    out, last = [], 1
    for i in range(len(paras)):
        last = found.get(i, last)
        out.append(last)
    return out


def main():
    dest = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / 'review'
    dest.mkdir(parents=True, exist_ok=True)
    names = bp.books()
    index = []
    with tempfile.TemporaryDirectory() as tmp:
        for docx in sorted(bp.SRC.glob('[0-9][0-9]-*.docx')):
            key = docx.stem
            paras = bp.paragraphs(docx)
            pages = pages_for(key, paras, bp.browser(), tmp)
            title, en = names.get(key, (key, ''))
            rows = [{'i': i, 'k': orig_kind(t), 'p': pages[i], 't': t} for i, t in enumerate(paras) if t.strip()]
            (dest / f'{key}.json').write_text(json.dumps({'part': key, 'title': title, 'en': en, 'paras': rows},
                                                         ensure_ascii=False, separators=(',', ':')), encoding='utf8')
            index.append({'part': key, 'title': title, 'en': en, 'pages': max(pages)})
            print(key, len(rows), 'paragraphs,', max(pages), 'pages')
    (dest / 'parts.json').write_text(json.dumps(index, ensure_ascii=False, indent=1), encoding='utf8')


if __name__ == '__main__':
    main()
