"""Finds the PDF page of every spelling correction and writes the corrections page.

Reads tools/corrections.json (written by tools/proofread.py), prints a copy of each part with
a tiny marker next to every corrected word, reads the markers back with poppler's pdftotext to
get page numbers, then writes corrections/index.html. The published PDFs are not touched.

    python tools/corrections-page.py ["what changed in this version"]

Entries without a 'version' become a new version in tools/versions.json, shown first on the page.
"""
import html
import importlib.util
import json
import re
import subprocess
import tempfile
import sys
from collections import Counter, defaultdict
from datetime import date
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


VERSIONS = ROOT / 'tools' / 'versions.json'
LABELS = {'space after full stop': 'spaces added after a full stop', 'space after comma': 'spaces added after a comma',
          'space before full stop or comma': 'spaces removed before a full stop or comma', 'doubled full stop': 'doubled full stops',
          'space before punctuation removed': 'spaces removed before ? ! ) and quote marks',
          'quote mark facing the wrong way': 'quote marks turned the right way', 'quote mark corrected': 'quote marks turned the right way at the end of a quotation',
          'straight quote made curly': 'straight quotes made curly', 'space inside quote marks removed': 'spaces removed inside quote marks',
          'space added outside quote marks': 'spaces added outside quote marks', 'dash made consistent': 'dashes made consistent',
          'double space': 'double spaces made single'}


def new_version(corr, note):
    """Entries without a version become a new version; its punctuation is what tidy-summary gained since the last one."""
    versions = json.loads(VERSIONS.read_text(encoding='utf8')) if VERSIONS.exists() else []
    fresh = [c for c in corr if not c.get('version')]
    spath = ROOT / 'tools' / 'tidy-summary.json'
    total = json.loads(spath.read_text(encoding='utf8')) if spath.exists() else {}
    seen = defaultdict(Counter)
    for v in versions:
        for part, d in v.get('punct', {}).items():
            seen[part].update(d)
    punct = {}
    for part, d in total.items():
        gained = {k: n - seen[part][k] for k, n in d.items() if n - seen[part][k] > 0}
        if gained:
            punct[part] = gained
    if not fresh and not punct:
        return versions
    vid = f'v{len(versions) + 1}'
    for c in fresh:
        c['version'] = vid
    versions.append({'id': vid, 'date': date.today().isoformat(), 'commit': '', 'title': note or 'Corrections', 'punct': punct})
    VERSIONS.write_text(json.dumps(versions, ensure_ascii=False, indent=1), encoding='utf8')
    print(f'new version {vid}: {len(fresh)} entries')
    return versions


def table(rows):
    body = []
    for c in sorted(rows, key=lambda c: (c.get('page') or 9999, c['para'])):
        cnt = f' <span class="x">×{c["count"]}</span>' if c.get('count', 1) > 1 else ''
        body.append(f'<tr><td class="pg">{c.get("page") or "–"}</td><td class="old">{html.escape(c["old"])}</td>'
                    f'<td class="arrow">→</td><td class="new">{html.escape(c["new"])}{cnt}</td><td class="why">{html.escape(c["why"])}</td></tr>')
    return ('<table><thead><tr><th>Page</th><th>Was</th><th></th><th>Now</th><th>Rule</th></tr></thead><tbody>\n'
            + '\n'.join(body) + '\n</tbody></table>')


def write_page(corr, versions):
    names = bp.books()
    total = sum(c.get('count', 1) for c in corr)
    sections, toc = [], []
    for v in reversed(versions):   # newest first
        rows = [c for c in corr if c.get('version') == v['id']]
        n = sum(c.get('count', 1) for c in rows)
        when = date.fromisoformat(v['date']).strftime('%d %b %Y').lstrip('0')
        commit = f' · <code>{html.escape(v["commit"])}</code>' if v.get('commit') else ''
        latest = ' <span class="latest">Latest</span>' if v is versions[-1] else ''
        toc.append(f'<li><a href="#{v["id"]}">{v["id"]}</a> <span class="n">{when} · {n}</span></li>')
        by_part = defaultdict(list)
        for c in rows:
            by_part[c['part']].append(c)
        parts = []
        for part in sorted(set(by_part) | set(v.get('punct', {}))):
            title, en = names.get(part, (part, ''))
            pn = v.get('punct', {}).get(part, {})
            extra = ', '.join(f'{pn[k]} {lab}' for k, lab in LABELS.items() if pn.get(k))
            extra = f'<p class="punct">Punctuation, not listed: {extra}.</p>' if extra else ''
            pr = by_part.get(part, [])
            count = sum(c.get('count', 1) for c in pr)
            link = html.escape('data/' + part + '.pdf')
            parts.append(f'<details class="part" open><summary><span class="pt">{html.escape(title)}</span> '
                         f'<span class="en">{html.escape(en)} · {count} corrections</span> <a class="open" href="../#read={link}">Open</a></summary>\n'
                         f'{extra}\n{table(pr) if pr else ""}</details>')
        sections.append(f'<section id="{v["id"]}" class="ver"><header class="vh"><span class="vid">{v["id"]}</span>{latest}\n'
                        f'<h2>{html.escape(v["title"])}</h2><p class="vm">{when} · {n} corrections{commit}</p></header>\n'
                        + '\n'.join(parts) + '</section>')
    extra = ''
    pr = ROOT / 'tools' / 'read-progress.json'
    if pr.exists():
        st = json.loads(pr.read_text(encoding='utf8'))
        fin = [names.get(k, (k, ''))[0] for k in st.get('finished', [])]
        now = names.get(st['part'], (st['part'], ''))[0] if st.get('part') else ''
        extra += ('<section class="ver"><h2>పూర్తి పఠనం (Careful read-through)</h2><p class="vm">'
                  + f'{len(fin)} of 6 parts read word by word'
                  + (': ' + html.escape(', '.join(fin)) if fin else '')
                  + (f'. Now reading {html.escape(now)}, from page {st["page"]}.' if now else '. All parts read.') + '</p></section>')
    dpath = ROOT / 'tools' / 'doubts.json'
    doubts = json.loads(dpath.read_text(encoding='utf8')) if dpath.exists() else []
    if doubts:
        rows = ''.join(f'<tr><td class="pg">{d.get("page") or "–"}</td><td>{html.escape(names.get(d["part"], (d["part"], ""))[0])}</td>'
                       f'<td>{html.escape(d["word"])}</td><td class="why">{html.escape(d.get("note", ""))}</td></tr>'
                       for d in doubts)
        extra += ('<section class="ver" id="doubts"><h2>సందేహాలు (Words to check, not changed)</h2>'
                  "<p class=\"vm\">Words that may be wrong but could be the author's choice. They are left as written.</p>"
                  '<table><thead><tr><th>Page</th><th>Part</th><th>Word</th><th>Why</th></tr></thead><tbody>' + rows + '</tbody></table></section>')
    out = ROOT / 'corrections' / 'index.html'
    out.parent.mkdir(exist_ok=True)
    out.write_text(PAGE.format(total=total, nver=len(versions), toc=''.join(toc), sections=extra + '\n'.join(sections)), encoding='utf8')
    print(f'corrections/index.html: {total} fixes, {len(versions)} versions')


PAGE = '''<!doctype html>
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
.toc li {{ background:var(--card); border:1px solid var(--rule); border-radius:999px; padding:4px 12px; font:600 14px system-ui,sans-serif; }}
.toc a {{ text-decoration:none; }} .n {{ color:var(--ink2); font-weight:400; font-size:13px; margin-left:4px; }}
.ver {{ background:var(--card); border:1px solid var(--rule); border-radius:12px; padding:16px; margin:0 0 22px; scroll-margin-top:12px; }}
.vh {{ border-bottom:1px solid var(--rule); padding-bottom:10px; margin-bottom:6px; }}
.vid {{ font:700 13px system-ui,sans-serif; letter-spacing:.04em; background:var(--ink); color:var(--paper); border-radius:6px; padding:2px 8px; }}
.latest {{ font:600 12px system-ui,sans-serif; color:var(--accent); border:1px solid var(--accent); border-radius:99px; padding:1px 8px; margin-left:6px; }}
h2 {{ font-family:system-ui,sans-serif; font-weight:600; margin:8px 0 2px; font-size:18px; line-height:1.4; }}
.vm {{ margin:0; color:var(--ink2); font:13px system-ui,sans-serif; }}
code {{ font:12px ui-monospace,Consolas,monospace; }}
.part {{ border-top:1px solid var(--rule); padding:8px 0; }}
.vh + .part {{ border-top:0; }}
.part summary {{ cursor:pointer; display:flex; flex-wrap:wrap; align-items:baseline; gap:4px 10px; }}
.pt {{ font-family:Ramabhadra,"Noto Sans Telugu",sans-serif; font-size:19px; }}
.part .en {{ font:13px system-ui,sans-serif; color:var(--ink2); }}
.part .open {{ font:13px system-ui,sans-serif; margin-left:auto; }}
table {{ width:100%; border-collapse:collapse; font-size:15px; margin-top:6px; }}
th {{ text-align:left; font:600 12px system-ui,sans-serif; color:var(--ink2); text-transform:uppercase; letter-spacing:.06em; border-bottom:1px solid var(--rule); padding:6px; }}
td {{ padding:6px; border-bottom:1px solid var(--rule); vertical-align:top; }}
tr:last-child td {{ border-bottom:0; }}
.pg {{ font:600 14px system-ui,sans-serif; color:var(--ink2); width:3.2em; font-variant-numeric:tabular-nums; }}
.old {{ color:var(--old); text-decoration:line-through; text-decoration-thickness:1px; }}
.new {{ color:var(--new); font-weight:600; }}
.arrow {{ color:var(--ink2); width:1.2em; }}
.why {{ color:var(--ink2); font-size:13px; }}
.punct {{ color:var(--ink2); font:13px/1.5 system-ui,sans-serif; margin:6px 0; }}
.x {{ font:500 12px system-ui,sans-serif; color:var(--ink2); }}
@media (max-width:560px) {{ .why {{ display:none; }} th:last-child {{ display:none; }} }}
</style></head><body><div class="wrap">
<p><a href="../">← శ్రీమద్రామాయణము</a></p>
<h1>అక్షర దోషాల సవరణలు</h1>
<p class="lede">Spelling corrections · {total} fixes in {nver} versions, newest first. Page numbers are the page numbers printed at the bottom of each page of the current PDFs.</p>
<ul class="toc">{toc}</ul>
{sections}
</div></body></html>
'''


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
    versions = new_version(corr, ' '.join(x for x in sys.argv[1:] if not x.startswith('--')) or None)
    path.write_text(json.dumps(corr, ensure_ascii=False, indent=1), encoding='utf8')
    write_page(corr, versions)


if __name__ == '__main__':
    main()
