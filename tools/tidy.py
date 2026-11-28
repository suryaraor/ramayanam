"""Fixes spacing and punctuation in the Word files in sources/ and records the changes.

    python tools/tidy.py          # fix sources/*.docx, add word fixes to tools/corrections.json
    python tools/tidy.py --dry    # only show what would change

What it fixes:
  * a space after every full stop and comma (రాముని పంపుము.రాముడు -> రాముని పంపుము. రాముడు)
  * no space before a full stop or comma (చెప్పెను . -> చెప్పెను.)
  * a doubled full stop (సదా.. -> సదా.)
  * full stops in the middle of a sentence (పసి బాలుని. అంత -> పసి బాలుని అంత)
  * two words typed without a space between them (జనులతోకళకళ -> జనులతో కళకళ)
  * a few misspelt words (విభాండాకుని -> విభాండకుని)

Word-level fixes are listed on the corrections page with their page numbers; the punctuation
fixes are only counted (tools/tidy-summary.json), as there are hundreds of them.
The text is edited across Word's formatting runs, so a fix works even when a word or a
full stop sits in a different run from its neighbour.
"""
import difflib
import html
import json
import re
import sys
import zipfile
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TE = '[ఀ-౿]'

# Two words written as one. Checked by hand: compounds and words with a suffix attached
# (వెళ్ళిపోయెను, రామునితో, అక్కడనుండి) are correct Telugu and are left alone.
SPLITS = {
    'కిరాతుడాకామ': 'కిరాతుడా కామ',
    'అనిపలికెను': 'అని పలికెను',
    'యుద్ధముచేసిఉందురు': 'యుద్ధము చేసి ఉందురు',
    'చూచిఇట్లని': 'చూచి ఇట్లని',
    'వచ్చినీవు': 'వచ్చి నీవు',
    'నిన్నునీవు': 'నిన్ను నీవు',
    'వచ్చిఇట్లని': 'వచ్చి ఇట్లని',
    'వద్దకువచ్చి': 'వద్దకు వచ్చి',
    'మాటలువిని': 'మాటలు విని',
    'గురించిచెప్పెను': 'గురించి చెప్పెను',
    'అనిపలికి': 'అని పలికి',
    'వెళ్ళివారి': 'వెళ్ళి వారి',
    'అనినుడివెను': 'అని నుడివెను',
    'యనిఅడిగెను': 'యని అడిగెను',
    'వారినివిభీషణుడు': 'వారిని విభీషణుడు',
    'మునిచెప్పెను': 'ముని చెప్పెను',
    'యుద్ధముచేసెను': 'యుద్ధము చేసెను',
    'మాటవిని': 'మాట విని',
    'రామునితోరామా': 'రామునితో రామా',
    'విన్నఇంద్రజిత్తు': 'విన్న ఇంద్రజిత్తు',
    'పిదపదివ్య': 'పిదప దివ్య',
    'మీరులేని': 'మీరు లేని',
    'అనిఅంగదుడు': 'అని అంగదుడు',
    'పుత్రుడుమిక్కిలి': 'పుత్రుడు మిక్కిలి',
    'చెప్పినమాటలు': 'చెప్పిన మాటలు',
    'నన్నుపరాక్రమ': 'నన్ను పరాక్రమ',
    'వధించితనను': 'వధించి తనను',
    'అదిచూచి': 'అది చూచి',
    'వారువిశ్వా': 'వారు విశ్వా',
    'పిదపవిశ్వా': 'పిదప విశ్వా',
    'పాటుభార్య': 'పాటు భార్య',
    'చేరినలుగురు': 'చేరి నలుగురు',
    'అగ్నితనకు': 'అగ్ని తనకు',
    'విధంగామాట': 'విధంగా మాట',
    'పిమ్మటబ్రహ్మ': 'పిమ్మట బ్రహ్మ',
    'నిన్నురాజ్యము': 'నిన్ను రాజ్యము',
    'చూచివిశ్వామిత్ర': 'చూచి విశ్వామిత్ర',
    'లక్ష్మణులువిశ్వామిత్ర': 'లక్ష్మణులు విశ్వామిత్ర',
    'వచ్చిమనకు': 'వచ్చి మనకు',
    'తిరిగివెళ్ళెను': 'తిరిగి వెళ్ళెను',
    'అనివేడుకొనెను': 'అని వేడుకొనెను',
    'విశ్వామిత్రుడుశపించెను': 'విశ్వామిత్రుడు శపించెను',
    'నున్నశివ': 'నున్న శివ',
    'మరొకభార్య': 'మరొక భార్య',
    'మునులుభయపడి': 'మునులు భయపడి',
    'తెలుసుకొనిఇచ్చటికి': 'తెలుసుకొని ఇచ్చటికి',
    'సుమంత్రునిచూచి': 'సుమంత్రుని చూచి',
    'సుగ్రీవుడుభయంతో': 'సుగ్రీవుడు భయంతో',
    'కలుగునుఅని': 'కలుగును అని',
    'వచ్చినిలిచి': 'వచ్చి నిలిచి',
    'సముద్రుడుమరియు': 'సముద్రుడు మరియు',
    'అనితెలిపిరి': 'అని తెలిపిరి',
    'రూపముపొంది': 'రూపము పొంది',
    'అదిమొదలు': 'అది మొదలు',
    'అనిపేరు': 'అని పేరు',
    'వివరించితిరిగి': 'వివరించి తిరిగి',
    'చేసితూర్పు': 'చేసి తూర్పు',
    'వలనఆకలి': 'వలన ఆకలి',
    'లక్ష్మణులతోఇట్లని': 'లక్ష్మణులతో ఇట్లని',
    'వెళ్ళిసగర': 'వెళ్ళి సగర',
    'మొదటికోరిక': 'మొదటి కోరిక',
    'ఇతరదేవతలను': 'ఇతర దేవతలను',
    'రాజుగానీకు': 'రాజుగా నీకు',
    'నిన్నుఅందరి': 'నిన్ను అందరి',
    'పాలనచేసెను': 'పాలన చేసెను',
    'తపస్సుచేస్తూ': 'తపస్సు చేస్తూ',
    'నగరమునురావణునితో': 'నగరమును రావణునితో',
    'తననుచంపడానికి': 'తనను చంపడానికి',
    'పిదపమునుల': 'పిదప మునుల',
    'బడినరీతిగా': 'బడిన రీతిగా',
    'వస్త్రములనుధరించి': 'వస్త్రములను ధరించి',
    'వరములనుకోరెను': 'వరములను కోరెను',
    'ప్రసిద్ధిపొందెను': 'ప్రసిద్ధి పొందెను',
    'విడిచివెళ్ళు': 'విడిచి వెళ్ళు',
    'సేవలుచేసిన': 'సేవలు చేసిన',
    'సమృద్ధిగాఉన్న': 'సమృద్ధిగా ఉన్న',
    'ధైర్యముచెప్పెను': 'ధైర్యము చెప్పెను',
    'సీతలేదని': 'సీత లేదని',
    'అనురాక్షసి': 'అను రాక్షసి',
    'తనకుసహాయ': 'తనకు సహాయ',
    'నుడివెనుఎంతటి': 'నుడివెను ఎంతటి',
    'అడవిఇంత': 'అడవి ఇంత',
    'వస్తున్నఆకాశ': 'వస్తున్న ఆకాశ',
    'వచనములనువిన్న': 'వచనములను విన్న',
    'నన్నుబంధించి': 'నన్ను బంధించి',
    'నిన్నుఎదిరించి': 'నిన్ను ఎదిరించి',
    'వెంటరాగా': 'వెంట రాగా',
    'నిన్నురక్షించ': 'నిన్ను రక్షించ',
    'గారిభవనమునకు': 'గారి భవనమునకు',
    'అపరాధముచేసి': 'అపరాధము చేసి',
    'ఫలములనుశరణు': 'ఫలములను శరణు',
    'అనుమతితోరాముడు': 'అనుమతితో రాముడు',
    'గురిచూచి': 'గురి చూచి',
    'మరణించుటమేలు': 'మరణించుట మేలు',
    'వచ్చుచున్నసీతాదేవిని': 'వచ్చుచున్న సీతాదేవిని',
    'సెలవుతీసికొని': 'సెలవు తీసికొని',
    'పోగావిశ్వామిత్రుడు': 'పోగా విశ్వామిత్రుడు',
    'పైకెత్తియెక్కు': 'పైకెత్తి యెక్కు',
    'సేవచేయుటకు': 'సేవ చేయుటకు',
    'సేవచేయుచు': 'సేవ చేయుచు',
    'పడుచున్నభరతునికి': 'పడుచున్న భరతునికి',
    'జటాయువుకుభయంకరమైన': 'జటాయువుకు భయంకరమైన',
    'ఎక్కడఉన్నది': 'ఎక్కడ ఉన్నది',
    'సశరీరముగాస్వర్గము': 'సశరీరముగా స్వర్గము',
    'గురించిశతానందుడు': 'గురించి శతానందుడు',
    'దినముఉత్తర': 'దినము ఉత్తర',
    'పూర్వంఎందరో': 'పూర్వం ఎందరో',
    'మునులకునమస్కరించిరి': 'మునులకు నమస్కరించిరి',
    'అప్పటినుండినీవు': 'అప్పటినుండి నీవు',
    'తెప్పించిగంగను': 'తెప్పించి గంగను',
    'ప్రాప్తికైపుత్ర': 'ప్రాప్తికై పుత్ర',
    'లేనిచోయజ్ఞమునకు': 'లేనిచో యజ్ఞమునకు',
    'వెదికిననూఒక్క': 'వెదికిననూ ఒక్క',
    'వంతుడురాజర్షి': 'వంతుడు రాజర్షి',
    'రావణునిశరీరం': 'రావణుని శరీరం',
    'బంధించినపిదప': 'బంధించిన పిదప',
    'తీరినతరువాత': 'తీరిన తరువాత',
    'చూచిచెట్ల': 'చూచి చెట్ల',
    'పరికించిచూచి': 'పరికించి చూచి',
    'ఆకాశంలోతిరుగుతున్న': 'ఆకాశంలో తిరుగుతున్న',
    'గాయములన్నీత్వరగా': 'గాయములన్నీ త్వరగా',
    'భూదేవినినీవు': 'భూదేవిని నీవు',
    'వేదవిచారముచేసి': 'వేదవిచారము చేసి',
    'చేయండనిచెప్పి': 'చేయండని చెప్పి',
    'బలాలతోపంపెను': 'బలాలతో పంపెను',
    'ప్రతీకారముగాతాను': 'ప్రతీకారముగా తాను',
    'నిర్మితములైసకల': 'నిర్మితములై సకల',
    'కిరాతుడైసకల': 'కిరాతుడై సకల',
    'హిమవత్పర్వతముపైతపస్సు': 'హిమవత్పర్వతముపై తపస్సు',
    'అభిప్రాయమునుకోరెను': 'అభిప్రాయమును కోరెను',
    'దాహముతోబాధ': 'దాహముతో బాధ',
    'భస్మరాసులనుగంగా': 'భస్మరాసులను గంగా',
    'రథునికుమారుడు': 'రథుని కుమారుడు',
    'కనబడుతున్నవీరుడు': 'కనబడుతున్న వీరుడు',
    'యేడవదైనగంగ': 'యేడవదైన గంగ',
    'నెరవేర్చుటకుసిద్ధముగా': 'నెరవేర్చుటకు సిద్ధముగా',
    'భీతితోపెక్కు': 'భీతితో పెక్కు',
    'కోరుకున్నప్పుడుమరణము': 'కోరుకున్నప్పుడు మరణము',
    'వెంబడించివెళ్లెను': 'వెంబడించి వెళ్లెను',
    'శత్రుఘ్నుడునుమరొక': 'శత్రుఘ్నుడును మరొక',
    'అనంగుడనిపేరు': 'అనంగుడని పేరు',
    'సంభారాలన్నివెంటబెట్టుకొని': 'సంభారాలన్ని వెంటబెట్టుకొని',
    'వలెనన్నముందుగా': 'వలెనన్న ముందుగా',
    'సభలోనున్నవీరుల': 'సభలోనున్న వీరుల',
    'రావణుడనుకొనిబిగ్గరగా': 'రావణుడనుకొని బిగ్గరగా',
    'జేసినపుణ్య': 'జేసిన పుణ్య',
    'రోముడుజన్మించెను': 'రోముడు జన్మించెను',
    'విషాదమునకులోనై': 'విషాదమునకు లోనై',
    'గాంభీర్యముచూపించి': 'గాంభీర్యము చూపించి',
    'కాపలానున్నత్రిజట': 'కాపలానున్న త్రిజట',
    'తెలుసుకొన్నదానవులు': 'తెలుసుకొన్న దానవులు',
    'సుగ్రీవునిపైకోపం': 'సుగ్రీవునిపై కోపం',
    'బ్రాహ్మణోత్తములకువిరివిగా': 'బ్రాహ్మణోత్తములకు విరివిగా',
    'ఋత్విజులతోనుఋషులతోనువిశ్వా': 'ఋత్విజులతోను ఋషులతోను విశ్వా',
    'ఇంకాపెద్దగాపెంచెను': 'ఇంకా పెద్దగా పెంచెను',
    'జనులతోకళకళ': 'జనులతో కళకళ',
}

# Full stops in the middle of a sentence (the sentence goes on after them)
EXTRA_STOPS = [
    ('పసి బాలుని. అంత', 'పసి బాలుని అంత'),
    ('చూడలేదు. ఈ. మృగమును', 'చూడలేదు. ఈ మృగమును'),
    ('నక్షత్రము పునర్వసు. నక్షత్రమున', 'నక్షత్రము పునర్వసు నక్షత్రమున'),
    ('జరిపించుననియు. ఆ యాగ', 'జరిపించుననియు, ఆ యాగ'),
]

WORDS = [
    (r'విభాండాక', 'విభాండక', 'విభాండకుడు'),
    (r'లంఘించదానికి', 'లంఘించడానికి', 'లంఘించడానికి'),
    (r'(?<![ఀ-౿])ఆఅ(?= )', 'ఆ', 'అదనపు అక్షరం'),
]

SPLIT_WHY = 'రెండు పదాల మధ్య ఖాళీ'
STOP_WHY = 'అనవసరమైన పూర్ణ విరామం'
VOWEL_IN_WORD = re.compile(r'(?<=[ఀ-౿])(?<!్)([అ-ఊఎ-ఔ])')   # a vowel letter inside a word starts a new word


def word_at(text, a, b):
    while a > 0 and re.match(TE, text[a - 1]):
        a -= 1
    while b < len(text) and re.match(TE, text[b]):
        b += 1
    return text[a:b]


def tidy(text, log, counts):
    # words
    for pat, rep, why in WORDS:
        def w(m, rep=rep, why=why, text=text):
            old = word_at(text, m.start(), m.end())
            log.append({'old': old, 'new': old.replace(m.group(0), rep), 'why': why})
            return rep
        text = re.sub(pat, w, text)
    for old, new in EXTRA_STOPS:
        rx = r'[ \u00a0]+'.join(map(re.escape, old.split(' ')))
        if re.search(rx, text):
            text = re.sub(rx, new, text)
            o = re.search(rf'{TE}+\.(?= )', old.replace('చూడలేదు. ', '')).group(0)
            log.append({'old': o, 'new': o[:-1], 'why': STOP_WHY})

    def split(m):
        old = m.group(0)
        new = SPLITS.get(old)
        if new is None:
            new = VOWEL_IN_WORD.sub(r' \1', old)
        if new != old:
            log.append({'old': old, 'new': new, 'why': SPLIT_WHY})
        return new
    text = re.sub(rf'{TE}+', split, text)

    # punctuation
    def sub(pat, rep, name):
        nonlocal text
        text, n = re.subn(pat, rep, text)
        counts[name] += n
    sub(r'(?<!\.)\.\.(?!\.)', '.', 'doubled full stop')
    sub(r'(?<=[ఀ-౿)”"]) +(?=[.,](?!\.))', '', 'space before full stop or comma')
    sub(r'\.(?=[ఀ-౿“"(])', '. ', 'space after full stop')
    sub(r',(?=[^\s\d,])', ', ', 'space after comma')
    return text


TOKEN = re.compile(r'(<w:t(?: [^>]*)?>)([^<]*)(</w:t>)|<w:tab/>|<w:br[^>]*/>')


def fix_para(p, log, counts):
    toks = list(TOKEN.finditer(p))
    if not toks:
        return p
    pieces, owner = [], []
    for k, t in enumerate(toks):
        s = html.unescape(t.group(2)) if t.group(1) else ('\t' if t.group(0) == '<w:tab/>' else '\n')
        pieces.append(s)
        owner += [k] * len(s)
    old = ''.join(pieces)
    new = tidy(old, log, counts)
    if new == old:
        return p
    is_text = [bool(t.group(1)) for t in toks]

    def text_owner(i):   # the run that receives text inserted at position i
        for j in (i, i - 1, i + 1, i - 2):
            if 0 <= j < len(owner) and is_text[owner[j]]:
                return owner[j]
        return next(k for k, x in enumerate(is_text) if x)
    out = [''] * len(toks)
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, old, new, autojunk=False).get_opcodes():
        if op == 'equal':
            for i in range(i1, i2):
                out[owner[i]] += old[i]
        elif op in ('replace', 'insert'):
            if op == 'replace':
                for i in range(i1, i2):
                    if not is_text[owner[i]]:
                        out[owner[i]] += old[i]   # never drop a tab or line break
            out[text_owner(i1)] += new[j1:j2]
    res, prev = [], 0
    for k, t in enumerate(toks):
        res.append(p[prev:t.start()])
        if is_text[k]:
            tag = t.group(1)
            if out[k] != out[k].strip() and 'xml:space' not in tag:
                tag = tag[:-1] + ' xml:space="preserve">'
            res.append(tag + html.escape(out[k], quote=False) + t.group(3))
        else:
            res.append(t.group(0))
        prev = t.end()
    res.append(p[prev:])
    return ''.join(res)


def main():
    from importlib.util import spec_from_file_location, module_from_spec
    spec = spec_from_file_location('proofread', ROOT / 'tools' / 'proofread.py')
    pr = module_from_spec(spec)
    spec.loader.exec_module(pr)
    dry = '--dry' in sys.argv
    corrections, summary = [], {}
    for docx in sorted((ROOT / 'sources').glob('[0-9][0-9]-*.docx')):
        z = zipfile.ZipFile(docx)
        files = {n: z.read(n) for n in z.namelist()}
        xml = files['word/document.xml'].decode('utf8')
        body = xml.index('<w:body>')
        counts, log, pi = Counter(), [], -1

        def para(m):
            nonlocal pi
            p = m.group(0)
            if pr.clean(p):
                pi += 1
            plog = []
            p = fix_para(p, plog, counts)
            log.extend({'part': docx.stem, 'para': pi, **c} for c in plog)
            return p
        new_xml = xml[:body] + re.sub(r'<w:p[ >].*?</w:p>', para, xml[body:], flags=re.S)
        merged = {}
        for c in log:
            k = (c['para'], c['old'], c['new'])
            merged.setdefault(k, {**c, 'count': 0})['count'] += 1
        log = list(merged.values())
        summary[docx.stem] = dict(counts)
        print(f'{docx.stem}: {len(log)} word fixes, {dict(counts)}')
        if dry:
            for c in log:
                print('   ', c['old'], '->', c['new'])
        corrections += log
        if not dry and (log or counts):
            files['word/document.xml'] = new_xml.encode('utf8')
            tmp = docx.with_suffix('.tmp')
            with zipfile.ZipFile(tmp, 'w', zipfile.ZIP_DEFLATED) as out:
                for n, data in files.items():
                    out.writestr(z.getinfo(n), data)
            z.close()
            tmp.replace(docx)
    if dry:
        return
    path = ROOT / 'tools' / 'corrections.json'
    old = json.loads(path.read_text(encoding='utf8')) if path.exists() else []
    path.write_text(json.dumps(old + corrections, ensure_ascii=False, indent=1), encoding='utf8')
    spath = ROOT / 'tools' / 'tidy-summary.json'
    prev = json.loads(spath.read_text(encoding='utf8')) if spath.exists() else {}
    for part, c in summary.items():
        for k, n in c.items():
            prev.setdefault(part, {})[k] = prev.get(part, {}).get(k, 0) + n
    spath.write_text(json.dumps(prev, ensure_ascii=False, indent=1), encoding='utf8')


if __name__ == '__main__':
    main()
