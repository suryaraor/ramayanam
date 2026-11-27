"""Fixes spelling mistakes in the Word files in sources/ and records every change.

    python tools/proofread.py            # fix sources/*.docx, write tools/corrections.json
    python tools/build-pdfs.py           # rebuild the PDFs from the fixed files
    python tools/corrections-page.py     # find the page of each fix, write corrections/index.html

Each rule is a regular expression and its replacement. TE marks the edge of a Telugu word,
so a rule only touches whole words or the start of words, never the middle of a different word.
Corrections follow standard Telugu / Sanskrit spelling (e.g. రథ, అర్థ, నిష్ఠ, యుద్ధ, శత్రు).
"""
import json
import re
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TE = r'[ఀ-౿]'
S = rf'(?<!{TE})'          # start of a Telugu word
W = rf'{TE}*'              # rest of the word

# (pattern, replacement, short reason shown on the corrections page)
RULES = [
    # థ written as ధ
    (r'దశ(\s?)రధ', r'దశ\1రథ', 'రథ (థ)'),
    (r'భగీరధ', 'భగీరథ', 'రథ (థ)'),
    (r'బృహద్రధ', 'బృహద్రథ', 'రథ (థ)'),
    (rf'{S}(ధర్మ|చిత్ర|కీర్తి|మహా|సత్య)?(\s?)రధ(?!్య)', r'\1\2రథ', 'రథ (థ)'),
    (r'సారధ', 'సారథ', 'సారథి (థ)'),
    (r'క్రధన', 'క్రథన', 'క్రథనుడు (థ)'),
    (r'కధ', 'కథ', 'కథ (థ)'),
    (rf'{S}య[ధద]ా(\s?)త[ధ]', r'యథా\1తథ', 'యథాతథ (థ)'),
    (r'య[ధథ]ేచ్చ', 'యథేచ్ఛ', 'యథేచ్ఛ'),
    (rf'{S}యధ(?=ా|ో|ే)', 'యథ', 'యథా (థ)'),
    (rf'{S}తధ(?=ా|్య)', 'తథ', 'తథా (థ)'),
    (r'అన్యధా', 'అన్యథా', 'అన్యథా (థ)'),
    (r'యదార్ధ', 'యథార్థ', 'యథార్థ'),
    (r'మిధిల', 'మిథిల', 'మిథిల (థ)'),
    (r'మిధ్యా', 'మిథ్యా', 'మిథ్యా (థ)'),
    (r'మిధునా', 'మిథునా', 'మిథునా (థ)'),
    (r'అతిధి', 'అతిథి', 'అతిథి (థ)'),
    (r'ఆతిధ్య', 'ఆతిథ్య', 'ఆతిథ్యము (థ)'),
    (r'అతిథాన్ని', 'ఆతిథ్యాన్ని', 'ఆతిథ్యము'),
    (r'పృధు', 'పృథు', 'పృథువు (థ)'),
    # అర్థ / సమర్థ written with ధ
    (r'(సమర్|సామర్|పదార్|ప్రార్|వ్యర్|కృతార్|సిద్ధార్|అభ్యర్|నభ్యర్|అనర్|పరమార్|అంతరార్|నిరర్|సార్|తీర్|చతుర్|ధర్మార్|కామార్|విశేషార్)ధ', r'\1థ', 'అర్థ (థ)'),
    (r'(ార్)ధ(?=మై|ం|ియై|ినై)', r'\1థ', 'అర్థ (థ)'),
    (rf'{S}(న్న)?అర్ధ(?=ించ|ము |ము$| విశ్లేష| సాధక)', r'\1అర్థ', 'అర్థ (థ)'),
    (r'నన్నర్ధ', 'నన్నర్థ', 'అర్థ (థ)'),
    (r'కార్యార్ధ|కర్యార్ధ', 'కార్యార్థ', 'కార్యార్థ'),
    (r'శాప(\s?)నార్ధాలు', 'శాపనార్థాలు', 'శాపనార్థాలు (థ)'),
    (r'దుఃఖార్ధుల', 'దుఃఖార్తుల', 'దుఃఖార్తులు (ఆర్త)'),
    (r'సమర్డ', 'సమర్థ', 'సమర్థ (థ)'),
    (r'మర్ధించ', 'మర్దించ', 'మర్దించు (ద)'),
    (r'కర్ధమ', 'కర్దమ', 'కర్దముడు (ద)'),
    (r'శా?ర్ధూల', 'శార్దూల', 'శార్దూలము (ద)'),
    (r'అంతర్ధానయమొందెను', 'అంతర్ధానమొందెను', 'అదనపు అక్షరం'),
    # ఠ written as ట
    (r'వ(సి|శి|సీ)ష్ట', lambda m: 'వ' + ('సి' if m.group(1) == 'సీ' else m.group(1)) + 'ష్ఠ', 'వసిష్ఠ (ఠ)'),
    (r'నిష్ట(?!ూర)', 'నిష్ఠ', 'నిష్ఠ (ఠ)'),
    (r'(గరి|జ్యే|శ్రే|ప్రతి|అధి|ధిష్|ర్మి|పటి|బలి|ఉత్తి|అంగు)ష్ట', r'\1ష్ఠ', 'ఠ'),
    (r'ధిష్ట', 'ధిష్ఠ', 'అధిష్ఠించు (ఠ)'),
    (r'ద్రుష్టి|ధృష్టి', 'దృష్టి', 'దృష్టి'),
    (r'శ్రుష్టి', 'సృష్టి', 'సృష్టి'),
    # ధ్ధ written as ద్ద
    (r'యుద్ద', 'యుద్ధ', 'యుద్ధ (ధ)'),
    (r'సిద్ద', 'సిద్ధ', 'సిద్ధ (ధ)'),
    (r'వృద్ద్?ధ?', 'వృద్ధ', 'వృద్ధ (ధ)'),
    (r'సన్నద్ద', 'సన్నద్ధ', 'సన్నద్ధ (ధ)'),
    (r'బద్దమైన', 'బద్ధమైన', 'బద్ధ (ధ)'),
    (r'బుద్ది', 'బుద్ధి', 'బుద్ధి (ధ)'),
    (r'ప్రసిధ్ద్ధి', 'ప్రసిద్ధి', 'ప్రసిద్ధి'),
    (r'అవద్ద్యు', 'అవధ్యు', 'అవధ్యుడు'),
    # ఛ written as చ
    (r'పరిపప్రచ్చ', 'పరిపప్రచ్ఛ', 'ఛ'),
    (r'మ్లేచ్చ', 'మ్లేచ్ఛ', 'ఛ'),
    (r'యాదృచ్చిక', 'యాదృచ్ఛిక', 'ఛ'),
    (r'స్వచ్చ', 'స్వచ్ఛ', 'ఛ'),
    (r'తుచ్చ', 'తుచ్ఛ', 'ఛ'),
    (r'విచ్చిన్న', 'విచ్ఛిన్న', 'ఛ'),
    (rf'{S}యిచ్చగించ', 'యిచ్ఛగించ', 'ఛ'),
    # ష / శ / ఢ / త్రు
    (r'కల్మశ', 'కల్మష', 'కల్మషము (ష)'),
    (r'శతృ', 'శత్రు', 'శత్రు'),
    (r'ధృ[ఢడ]', 'దృఢ', 'దృఢ'),
    (rf'{S}ధృవ', 'ధ్రువ', 'ధ్రువ'),
    # names and words
    (rf'{S}భారత(?!ీయ)', 'భరత', 'భరతుడు'),
    (r'తపయస్వాధ్యాయ', 'తపఃస్వాధ్యాయ', 'తపః'),
    (r'నిర్వఘ్న', 'నిర్విఘ్న', 'నిర్విఘ్నము'),
    (r'భగవద్గుణలను', 'భగవద్గుణములను', 'గుణములను'),
    (r'బ్రహ్మస్త్ర', 'బ్రహ్మాస్త్ర', 'బ్రహ్మాస్త్రము'),
    (r'ఆగ్నేయాసత్ర', 'ఆగ్నేయాస్త్ర', 'అస్త్రము'),
    (r'(ప్ర)?దక్షణ', r'\1దక్షిణ', 'దక్షిణ'),
    (r'విభీషనుడ', 'విభీషణుడ', 'విభీషణుడు (ణ)'),
    (r'హనుమంతుడోక్క', 'హనుమంతుడొక్క', 'ఒక్కడు'),
    (r'ఇంద్రజితును', 'ఇంద్రజిత్తును', 'ఇంద్రజిత్తు'),
    (r'కబందు', 'కబంధు', 'కబంధుడు (ధ)'),
    (r'నికుంబిళ', 'నికుంభిల', 'నికుంభిల'),
    (r'కైకయి', 'కైకేయి', 'కైకేయి'),
    (r'శుభవచ్చనము', 'శుభవచనము', 'వచనము'),
]
COMPILED = [(re.compile(p), r, why) for p, r, why in RULES]
WORD = re.compile(rf'{TE}+')


def clean(p):
    """Paragraph text exactly as tools/build-pdfs.py reads it ('' for paragraphs it skips)."""
    import html
    p = re.sub(r'<w:tab/>', ' ', p)
    p = re.sub(r'<w:br[^>]*/>', '\n', p)
    t = html.unescape(re.sub(r'<[^>]+>', '', p))
    t = re.sub(r'[ \u00a0]+', ' ', t).strip()
    return '' if t in {'', '.', '. .', '..'} else t


def word_at(text, i):
    a = i
    while a > 0 and re.match(TE, text[a - 1]):
        a -= 1
    b = i
    while b < len(text) and re.match(TE, text[b]):
        b += 1
    return text[a:b]


def fix_text(text, log, where):
    for rx, rep, why in COMPILED:
        out, last = [], 0
        for m in rx.finditer(text):
            new = m.expand(rep) if isinstance(rep, str) else rep(m)
            if new == m.group(0):
                continue
            a, b = m.start(), m.end()
            while a > 0 and re.match(TE, text[a - 1]):
                a -= 1
            while b < len(text) and re.match(TE, text[b]):
                b += 1
            old_word = text[a:b]
            out.append(text[last:m.start()])
            out.append(new)
            last = m.end()
            log.append({**where, 'old': old_word, 'why': why})
        if out:
            out.append(text[last:])
            text = ''.join(out)
    return text


def join_split_words(p, log, where):
    """A word split across two formatting runs: move the whole word into the first run, then fix it."""
    for _ in range(20):
        runs = list(re.finditer(r'(<w:t(?: [^>]*)?>)([^<]*)(</w:t>)', p))
        texts = [r.group(2) for r in runs]
        joined = ''.join(texts)
        hit = None
        for rx, rep, why in COMPILED:
            for m in rx.finditer(joined):
                new = m.expand(rep) if isinstance(rep, str) else rep(m)
                if new != m.group(0):
                    hit = m
                    break
            if hit:
                break
        if not hit:
            return p
        # widen to the whole word, find the runs it covers
        a, b = hit.start(), hit.end()
        while a > 0 and re.match(TE, joined[a - 1]):
            a -= 1
        while b < len(joined) and re.match(TE, joined[b]):
            b += 1
        starts, pos = [], 0
        for t in texts:
            starts.append(pos)
            pos += len(t)
        first = max(i for i, st in enumerate(starts) if st <= a)
        last = max(i for i, st in enumerate(starts) if st < b) if b > 0 else first
        if first == last:   # not split after all
            return p
        moved = joined[a:b]
        new_texts = texts[:]
        new_texts[first] = texts[first][:a - starts[first]] + moved
        for i in range(first + 1, last + 1):
            cut = max(0, b - starts[i])
            new_texts[i] = texts[i][cut:] if i == last else ''
        new_texts[first] = new_texts[first][:len(new_texts[first]) - len(moved)] + fix_text(moved, log, where)
        out, prev = [], 0
        for r, t in zip(runs, new_texts):
            out.append(p[prev:r.start(2)])
            out.append(t)
            prev = r.end(2)
        out.append(p[prev:])
        p = ''.join(out)
    return p


def main():
    corrections = []
    for docx in sorted((ROOT / 'sources').glob('[0-9][0-9]-*.docx')):
        z = zipfile.ZipFile(docx)
        files = {n: z.read(n) for n in z.namelist()}
        xml = files['word/document.xml'].decode('utf8')
        body_start = xml.index('<w:body>')
        pi = -1
        log = []

        def fix_para(pm):
            nonlocal pi
            p = pm.group(0)
            if clean(p):
                pi += 1
            where = {'part': docx.stem, 'para': pi}
            p = re.sub(r'(<w:t(?: [^>]*)?>)([^<]*)(</w:t>)',
                       lambda t: t.group(1) + fix_text(t.group(2), log, where) + t.group(3), p)
            return join_split_words(p, log, where)

        new_body = re.sub(r'<w:p[ >].*?</w:p>', fix_para, xml[body_start:], flags=re.S)
        new_xml = xml[:body_start] + new_body
        # several rules can touch one word: keep one entry per word, showing the fully fixed word
        merged = {}
        for c in log:
            c['old'] = c['old'].strip()
            k = (c['para'], c['old'])
            if k in merged:
                merged[k]['count'] += 1
            else:
                merged[k] = {**c, 'count': 1}
        log = []
        for c in merged.values():
            c['new'] = fix_text(c['old'], [], {})
            if c['new'] != c['old']:
                log.append(c)
        if log and '--dry' not in sys.argv:
            files['word/document.xml'] = new_xml.encode('utf8')
            tmp = docx.with_suffix('.tmp')
            with zipfile.ZipFile(tmp, 'w', zipfile.ZIP_DEFLATED) as out:
                for n, data in files.items():
                    out.writestr(z.getinfo(n), data)
            z.close()
            tmp.replace(docx)
        print(f'{docx.stem}: {len(log)} corrections')
        corrections += log
    old = []
    path = ROOT / 'tools' / 'corrections.json'
    if path.exists() and '--fresh' not in sys.argv:
        old = json.loads(path.read_text(encoding='utf8'))
    if '--dry' in sys.argv:
        from collections import Counter
        for (o, n), k in sorted(Counter((c['old'], c['new']) for c in corrections).items(), key=lambda x: -x[1]):
            print(f'{k:4} {o} -> {n}')
        return
    path.write_text(json.dumps(old + corrections, ensure_ascii=False, indent=1), encoding='utf8')


if __name__ == '__main__':
    main()
