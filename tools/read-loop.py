"""Careful read-through of the whole book, a few pages at a time (used by the proofreading loop).

    python tools/read-loop.py status            # where the read-through is
    python tools/read-loop.py next              # print the paragraphs of the next batch of pages
    python tools/read-loop.py done FIXES.json   # apply this batch's fixes, note doubtful words, move on

FIXES.json: {"fixes": [{"para": 12, "old": "...", "new": "...", "why": "..."}],
             "doubts": [{"para": 40, "word": "...", "note": "..."}]}
Each fix replaces one whole word only inside that paragraph of the Word file in sources/ (formatting kept).
Fixes go into tools/corrections.json without a version; doubtful words into tools/doubts.json.
When a part is finished, `done` prints PART FINISHED: then rebuild and publish (see SKILL-style steps in
README: build-pdfs.py, build-manifest.mjs, corrections-page.py "Full read: <part>").
"""
import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROGRESS = ROOT / 'tools' / 'read-progress.json'
CACHE = ROOT / 'tools' / 'read-data'
TE = 'ఀ-౿'
sys.path.insert(0, str(Path.home() / '.claude' / 'skills' / 'telugu-book-proofreader' / 'scripts'))
import telugu_proof as tp   # noqa: E402  (Word paragraph rewriting that keeps the runs' formatting)

spec = importlib.util.spec_from_file_location('build_pdfs', ROOT / 'tools' / 'build-pdfs.py')
bp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bp)

PARTS = sorted(p.stem for p in bp.SRC.glob('[0-9][0-9]-*.docx'))


def load(path, default):
    return json.loads(path.read_text(encoding='utf8')) if path.exists() else default


def save(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding='utf8')


def progress():
    return load(PROGRESS, {'part': PARTS[0], 'page': 1, 'per_run': 8, 'finished': [], 'runs': 0})


def part_data(part):
    f = CACHE / f'{part}.json'
    if not f.exists():   # paragraph text with page numbers, made once per part
        subprocess.run([sys.executable, str(ROOT / 'tools' / 'review-data.py'), str(CACHE)], check=True)
    return load(f, None)


def batch(pr):
    d = part_data(pr['part'])
    lo, hi = pr['page'], pr['page'] + pr['per_run'] - 1
    return d, [r for r in d['paras'] if lo <= r['p'] <= hi], lo, hi, max(r['p'] for r in d['paras'])


def bp_clean(t):
    t = re.sub(r'[  \t]+', ' ', t).strip()
    return t


def apply_fixes(part, fixes):
    src = bp.SRC / f'{part}.docx'
    tmp = src.with_suffix('.tmp.docx')
    want = {}
    for f in fixes:
        want.setdefault(f['para'], []).append(f)
    done = {}
    state = {'i': -1}

    def fn(t, _raw_index):
        c = bp_clean(t.replace('\n', ' '))
        if not c or c in {'.', '. .', '..'}:
            return t
        state['i'] += 1
        for f in want.get(state['i'], []):
            t, n = re.subn(f'(?<![{TE}]){re.escape(f["old"])}(?![{TE}])', f['new'], t)
            done[id(f)] = n
        return t
    tp.rewrite(src, tmp, fn)
    tmp.replace(src)
    return done


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'status'
    pr = progress()
    if cmd == 'status':
        d = part_data(pr['part']) if pr['part'] else None
        last = max(r['p'] for r in d['paras']) if d else 0
        print(json.dumps({**pr, 'part_pages': last}, ensure_ascii=False))
        return
    if not pr['part']:
        print('ALL PARTS FINISHED')
        return
    d, rows, lo, hi, last = batch(pr)
    if cmd == 'next':
        print(f'{pr["part"]} ({d["en"]}) pages {lo}-{min(hi, last)} of {last}')
        for r in rows:
            print(f'[{r["i"]}|p{r["p"]}|{r["k"]}] {r["t"]}')
        return
    if cmd == 'done':
        data = load(Path(sys.argv[2]), {}) if len(sys.argv) > 2 else {}
        fixes = [f for f in data.get('fixes', []) if f.get('old') and f.get('new') and f['old'] != f['new']]
        page_of = {r['i']: r['p'] for r in d['paras']}
        if fixes:
            done = apply_fixes(pr['part'], fixes)
            corr = load(ROOT / 'tools' / 'corrections.json', [])
            for f in fixes:
                n = done.get(id(f), 0)
                if not n:
                    print(f'NOT FOUND in paragraph {f["para"]}: {f["old"]}')
                    continue
                corr.append({'part': pr['part'], 'para': f['para'], 'old': f['old'], 'why': f.get('why', 'అక్షర దోషం'),
                             'count': n, 'new': f['new'], 'page': page_of.get(f['para'])})
                print(f'fixed: {f["old"]} -> {f["new"]} (paragraph {f["para"]}, x{n})')
            save(ROOT / 'tools' / 'corrections.json', corr)
        doubts = data.get('doubts', [])
        if doubts:
            all_d = load(ROOT / 'tools' / 'doubts.json', [])
            all_d += [{'part': pr['part'], 'para': x['para'], 'page': page_of.get(x['para']), 'word': x['word'],
                       'note': x.get('note', '')} for x in doubts]
            save(ROOT / 'tools' / 'doubts.json', all_d)
        pr['runs'] += 1
        pr['page'] = hi + 1
        if pr['page'] > last:
            pr['finished'].append(pr['part'])
            nxt = [p for p in PARTS if p not in pr['finished']]
            print(f'PART FINISHED: {pr["part"]}')
            pr['part'], pr['page'] = (nxt[0] if nxt else ''), 1
            for f in CACHE.glob('*.json'):   # pages shift after a rebuild; re-read them for the next part
                f.unlink()
        save(PROGRESS, pr)
        print('next:', pr['part'] or 'none', 'page', pr['page'])


if __name__ == '__main__':
    main()
