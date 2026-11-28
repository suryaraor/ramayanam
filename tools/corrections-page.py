"""Finds the PDF page of every spelling correction and writes the corrections page.

Reads tools/corrections.json (written by tools/proofread.py), prints a copy of each part with
a tiny marker next to every corrected word, reads the markers back with poppler's pdftotext to
get page numbers, then writes corrections/index.html. The published PDFs are not touched.

    python tools/corrections-page.py
"""
import html
import importlib.util
import json
import re
import subprocess
import tempfile
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location('build_pdfs', ROOT / 'tools' / 'build-pdfs.py')
bp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bp)


def find_pages(part, entries, exe, tmp):
    paras = bp.paragraphs(ROOT / 'sources' / f'{part}.docx')
    used = defaultdict(set)   # marker positions per paragraph (in the original text)
    inserts = defaultdict(list)
    for n, c in enumerate(entries):
        if c['para'] >= len(paras):
            continue
        t = paras[c['para']]
        spots = [m.start() for m in re.finditer(rf'(?<![ఀ-౿]){re.escape(c["new"])}(?![ఀ-౿])', t)]             or [m.start() for m in re.finditer(re.escape(c['new']), t)] or [0]
        i = next((x for x in spots if x not in used[c['para']]), spots[0])
        used[c['para']].add(i)
        inserts[c['para']].append((i, n))
    for pi, marks in inserts.items():
        t = paras[pi]
        for i, n in sorted(marks, reverse=True):
            t = t[:i] + f'{n}' + t[i:]
        paras[pi] = t
    title, en = bp.books().get(part, (part, ''))
    page = Path(tmp) / f'{part}.html'
    page.write_text(bp.page_html(title, en, bp.body_html(paras, title)), encoding='utf8')
    pdf = Path(tmp) / f'{part}.pdf'
    subprocess.run([exe, '--headless=new', '--disable-gpu', '--no-pdf-header-footer', '--run-all-compositor-stages-before-draw',
                    '--virtual-time-budget=20000', f'--user-data-dir={Path(tmp) / "profile"}', f'--print-to-pdf={pdf}', page.as_uri()],
                   check=True, capture_output=True, timeout=300)
    text = subprocess.run(['pdftotext', '-enc', 'UTF-8', str(pdf), '-'], check=True, capture_output=True).stdout.decode('utf8', 'replace')
    found = {}
    for pno, ptxt in enumerate(text.split('\f'), start=1):
        for m in re.finditer(r'#(\d+)#', ptxt):
            found.setdefault(int(m.group(1)), pno)
    for n, c in enumerate(entries):
        c['page'] = found.get(n)
    for c in entries:   # markers that overlapped another: use the page of a neighbour in the same paragraph
        if not c['page']:
            near = sorted((abs(x['para'] - c['para']), x['para'] > c['para'], x['page']) for x in entries if x['page'])
            c['page'] = near[0][2] if near else None


def write_page(corr):
    names = bp.books()
    by_part = defaultdict(list)
    for c in corr:
        by_part[c['part']].append(c)
    total = sum(c.get('count', 1) for c in corr)
    sections, toc = [], []
    spath = ROOT / 'tools' / 'tidy-summary.json'
    punct = json.loads(spath.read_text(encoding='utf8')) if spath.exists() else {}
    labels = {'space after full stop': 'spaces added after a full stop', 'space after comma': 'spaces added after a comma',
              'space before full stop or comma': 'spaces removed before a full stop or comma', 'doubled full stop': 'doubled full stops'}
    for part in sorted(by_part):
        title, en = names.get(part, (part, ''))
        rows = sorted(by_part[part], key=lambda c: (c.get('page') or 9999, c['para']))
        n = sum(c.get('count', 1) for c in rows)
        toc.append(f'<li><a href="#{part}">{html.escape(title)}</a> <span class="n">{n}</span></li>')
        body = []
        for c in rows:
            cnt = f' <span class="x">×{c["count"]}</span>' if c.get('count', 1) > 1 else ''
            body.append(f'<tr><td class="pg">{c.get("page") or "–"}</td><td class="old">{html.escape(c["old"])}</td>'
                        f'<td class="arrow">→</td><td class="new">{html.escape(c["new"])}{cnt}</td><td class="why">{html.escape(c["why"])}</td></tr>')
        pdf = f'../data/{part}.pdf'
        pn = punct.get(part, {})
        extra = ', '.join(f'{pn[k]} {v}' for k, v in labels.items() if pn.get(k))
        extra = f'<p class="punct">Punctuation, not listed below: {extra}.</p>' if extra else ''
        sections.append(f'''<section id="{part}"><h2>{html.escape(title)} <span class="en">{html.escape(en)} · {n} corrections</span></h2>
<p class="open"><a href="../#read={html.escape('data/' + part + '.pdf')}">Open this part</a> · <a href="{pdf}">PDF</a></p>
{extra}
<table><thead><tr><th>Page</th><th>Was</th><th></th><th>Now</th><th>Rule</th></tr></thead><tbody>
{chr(10).join(body)}
</tbody></table></section>''')
    out = ROOT / 'corrections' / 'index.html'
    out.parent.mkdir(exist_ok=True)
    out.write_text(f'''<!doctype html>
<html lang="te"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Spelling corrections · శ్రీమద్రామాయణము</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+Telugu:wght@400;600&family=Ramabhadra&display=swap" rel="stylesheet">
<style>
:root {{ --paper:#f6ecdc; --card:#fbf8f2; --ink:#1d1a16; --ink2:#5d554a; --rule:#d6cbb8; --accent:#c25a0c; --old:#b42318; --new:#1a7f37; }}
@media (prefers-color-scheme: dark) {{ :root {{ --paper:#16130f; --card:#1f1b16; --ink:#f1ebe0; --ink2:#b1a796; --rule:#3a3329; --accent:#ea8a42; --old:#ff8a80; --new:#7ee2a8; }} }}
* {{ box-sizing: border-box; }}
body {{ margin:0; background:var(--paper); color:var(--ink); font:16px/1.6 "Noto Sans Telugu","Nirmala UI",system-ui,sans-serif; }}
.wrap {{ max-width:900px; margin:0 auto; padding:28px 16px 60px; }}
a {{ color:var(--accent); }}
h1 {{ font-family:Ramabhadra,"Noto Sans Telugu",sans-serif; font-weight:400; color:var(--accent); font-size:clamp(28px,7vw,44px); margin:8px 0 4px; line-height:1.3; }}
.lede {{ color:var(--ink2); margin:0 0 18px; }}
.toc {{ list-style:none; padding:0; margin:0 0 24px; display:flex; flex-wrap:wrap; gap:8px; }}
.toc li {{ background:var(--card); border:1px solid var(--rule); border-radius:999px; padding:4px 12px; }}
.toc a {{ text-decoration:none; }} .n {{ color:var(--ink2); font-size:13px; margin-left:4px; }}
section {{ background:var(--card); border:1px solid var(--rule); border-radius:12px; padding:16px; margin:0 0 22px; }}
h2 {{ font-family:Ramabhadra,"Noto Sans Telugu",sans-serif; font-weight:400; margin:0; font-size:22px; line-height:1.4; }}
h2 .en {{ display:block; font-family:system-ui,sans-serif; font-size:13px; color:var(--ink2); }}
.open {{ margin:4px 0 10px; font-size:14px; }}
table {{ width:100%; border-collapse:collapse; font-size:15px; }}
th {{ text-align:left; font:600 12px system-ui,sans-serif; color:var(--ink2); text-transform:uppercase; letter-spacing:.06em; border-bottom:1px solid var(--rule); padding:6px 6px; }}
td {{ padding:6px; border-bottom:1px solid var(--rule); vertical-align:top; }}
tr:last-child td {{ border-bottom:0; }}
.pg {{ font:600 14px system-ui,sans-serif; color:var(--ink2); width:3.2em; }}
.old {{ color:var(--old); text-decoration:line-through; text-decoration-thickness:1px; }}
.new {{ color:var(--new); font-weight:600; }}
.arrow {{ color:var(--ink2); width:1.2em; }}
.why {{ color:var(--ink2); font-size:13px; }}
.punct {{ color:var(--ink2); font:13px/1.5 system-ui,sans-serif; margin:0 0 10px; }}
.x {{ font:500 12px system-ui,sans-serif; color:var(--ink2); }}
@media (max-width:560px) {{ .why {{ display:none; }} th:last-child {{ display:none; }} }}
</style></head><body><div class="wrap">
<p><a href="../">← శ్రీమద్రామాయణము</a></p>
<h1>అక్షర దోషాల సవరణలు</h1>
<p class="lede">Spelling corrections · {total} fixes across {len(by_part)} parts. Page numbers are the page numbers printed at the bottom of each PDF page.</p>
<ul class="toc">{''.join(toc)}</ul>
{chr(10).join(sections)}
</div></body></html>
''', encoding='utf8')
    print(f'corrections/index.html: {total} fixes')


def main():
    path = ROOT / 'tools' / 'corrections.json'
    corr = json.loads(path.read_text(encoding='utf8'))
    by_part = defaultdict(list)
    for c in corr:
        by_part[c['part']].append(c)
    exe = bp.browser()
    with tempfile.TemporaryDirectory() as tmp:
        for part, entries in sorted(by_part.items()):
            find_pages(part, entries, exe, tmp)
            missing = sum(1 for c in entries if not c.get('page'))
            print(f'{part}: {len(entries)} entries, {missing} without a page')
    path.write_text(json.dumps(corr, ensure_ascii=False, indent=1), encoding='utf8')
    write_page(corr)


if __name__ == '__main__':
    main()
