"""Build the data.json summary used by the "Nacimientos <year>" dashboards.

Reads an INE MNP births microdata file (fixed width, 2016+ record layout, which
also fits the 2015 file) and writes per-origin x per-province aggregates.

Usage:
    python build_nacimientos_json.py <microdata.txt> <out.json> [--layout dr.json]
"""
import argparse
import os
import json
from collections import Counter, defaultdict

DEFAULT_LAYOUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'dr_MNPnacim_2016.json')  # INE record layout
AGE_GROUPS = ['<20', '20–24', '25–29', '30–34', '35–39', '40–44', '45+']
W_EDGES = list(range(750, 5001, 250))
WEEKS = (22, 43)
INT_BIN, INT_MAX = 6, 180
WED_MAX = 60  # months
SPAIN = '108'
TOP_COUNTRIES, TOP_PARENT = 15, 10


def age_group(a):
    if a < 20:
        return 0
    if a >= 45:
        return 6
    return (a - 20) // 5 + 1


def wbin(w):
    b = 0
    while b < len(W_EDGES) and w >= W_EDGES[b]:
        b += 1
    return b


CONTINENTS = ['es', 'eu', 'af', 'am', 'as']  # Spain, rest of Europe, Africa, Americas, Asia (Oceania/unknown left out)


def continent(code):
    if not code:
        return None
    if code == SPAIN:
        return 'es'
    return {'1': 'eu', '2': 'af', '3': 'am', '4': 'as'}.get(code[0])


def new_slice(m_len, p_len, n_marital=4):
    nb = len(W_EDGES) + 1
    nw = WEEKS[1] - WEEKS[0] + 1
    mix = lambda: {u: {'k': 0, 'd': 0, 'ab': 0, 'dir': [0, 0, 0], 'esM': Counter(), 'esP': Counter()} for u in ('all', 'mar', 'unm')}
    return {
        'n': 0, 'ageM': [0] * m_len, 'ageP': [0] * p_len,
        'ageMc': {k: [0] * m_len for k in CONTINENTS}, 'agePc': {k: [0] * p_len for k in CONTINENTS}, 'first': 0, 'ces': 0, 'pre': 0, 'mult': 0,
        'married': 0, 'lbw': 0, 'wKnown': 0, 'month': [0] * 12,
        'byAge': {k: [0] * 7 for k in ('n', 'ces', 'pre', 'lbw', 'wKnown', 'mult', 'cmp')} | {'order': [[0] * 7 for _ in range(4)]},
        'heat': [[0] * nb for _ in range(nw)], 'interval': [0] * (INT_MAX // INT_BIN + 1),
        'marital': [0] * n_marital, 'mixed': {'birth': mix(), 'nat': mix()}, 'countries': Counter(),
        'cmp': 0,
        # complications by mother's continent x age group
        'cmpC': {k: {'n': [0] * 7, 'cmp': [0] * 7} for k in CONTINENTS},
        # [boys, girls]
        'sex': {'all': [0, 0], 'order': [[0, 0] for _ in range(4)], 'cont': {k: [0, 0] for k in CONTINENTS}},
        # first births to married mothers: months from wedding to birth (0..WED_MAX, last bin = more than WED_MAX)
        'wed': [0] * (WED_MAX + 2), 'wedNo': 0,
        # mothers born abroad who hold Spanish nationality; CUANNACM: when they got it
        'natEs': {'n': 0, 'later': 0, 'birth': 0}, 'countriesEs': Counter(),
    }


FIELDS_2016 = ('ANOPAR', 'MESPAR', 'PROREM', 'MULTIPLI', 'CESAREA', 'INTERSEM', 'SEMANAS', 'EDADM', 'EDADP',
               'ECIVM', 'PAISNXM', 'PAISNXP', 'PAISNACM', 'PAISNACP', 'PESON', 'INIHA', 'SORDENV',
               'SEXO', 'NORMA', 'MESMAT', 'ANIOMAT', 'NACIOEM', 'CUANNACM')
# INE "diseño anonimizado de nacimientos desde 1996" (85-char records, used up to 2006).
# Maps the old fields onto the 2016+ names; None = not recorded in that layout.
LAYOUT_1996 = {'ANOPAR': (8, 4), 'MESPAR': (6, 2), 'PROREM': (30, 2), 'MULTIPLI': (16, 1), 'INTERSEM': (17, 1),
               'SEMANAS': (12, 2), 'EDADM': (58, 2), 'EDADP': (67, 2), 'CAS': (40, 1), 'PAISNACM': (80, 3),
               'PAISNACP': (83, 3), 'PESON': (72, 4), 'INIHA': (64, 3), 'SORDENV': (32, 2),
               'SEXO': (69, 1), 'NORMA': (18, 1), 'MESMAT': (42, 2), 'ANIOMAT': (44, 4)}
# INE anonymised file 1980-1995 (68-char records; the design document ships with the late fetal deaths file,
# whose layout the births file shares). No nationality or country of birth for either parent; years have 2 digits.
LAYOUT_1980 = {'SEMANAS': (8, 2), 'MESPAR': (10, 2), 'ANOPAR': (12, 2), 'MULTIPLI': (14, 1), 'INTERSEM': (15, 1),
               'NORMA': (16, 1), 'PROREM': (26, 2), 'SORDENV': (28, 2), 'MESHAN': (30, 2), 'ANOHAN': (32, 2),
               'CAS': (34, 1), 'MESMAT': (36, 2), 'ANIOMAT': (38, 2), 'SEXO': (47, 1), 'PESON': (49, 4),
               'EDADM': (59, 2), 'EDADP': (67, 2)}
# INE anonymised births 1975-1979 (50-char records, "disreg nac 75-79"). No weeks, weight, caesarean or origin;
# marital status is the baby's legitimacy (LEGI); yes/no flags use 1 / 6.
LAYOUT_1975 = {'MESPAR': (6, 2), 'ANOPAR': (8, 2), 'SEXO': (10, 1), 'LEGI': (11, 1), 'MULTIPLI': (14, 1),
               'MATURI': (15, 1), 'NOD': (16, 1), 'MESMAT': (24, 2), 'ANIOMAT': (26, 2), 'SORDENV': (28, 2),
               'MESHAN': (30, 2), 'ANOHAN': (32, 2), 'PROREM': (37, 2), 'EDADM': (45, 2), 'EDADP': (47, 2)}
MARITAL_2016 = ['Married', 'Single', 'Separated or divorced', 'Widowed']
MARITAL_1996 = ['Married', 'Not married']


def iter_rows(src, dr):
    """Return (layout_name, iterator of row dicts). Detects the layout from the record length
    and streams the file, so a whole year never has to sit in memory."""
    with open(src, encoding='latin-1') as fh:
        head = [ln.rstrip('\r\n') for _, ln in zip(range(1000), fh) if ln.strip()]
    width = max(len(ln) for ln in head)

    def lines():
        with open(src, encoding='latin-1') as fh:
            for ln in fh:
                if ln.strip():
                    yield ln.rstrip('\r\n')

    if width <= 55:
        flag = lambda v: {'1': '1', '6': '2'}.get(v, '')  # 1 = yes / normal, 6 = no / not normal -> 1 / 2

        def conv(ln):
            r = {k: ln[p - 1:p - 1 + n].strip() for k, (p, n) in LAYOUT_1975.items()}
            r['ANOPAR'] = '19' + r['ANOPAR']
            r['ANIOMAT'] = '19' + r['ANIOMAT'] if r['ANIOMAT'] not in ('', '00') else ''
            r['EDADP'] = '' if r['EDADP'] in ('', '00', '99') else r['EDADP']
            r['SEMANAS'] = r['PESON'] = ''
            r['INTERSEM'], r['NORMA'] = flag(r.pop('MATURI')), flag(r.pop('NOD'))
            r['ECIVM'] = flag(r.pop('LEGI'))  # legitimate birth = mother married
            mh, ah = r.pop('MESHAN'), r.pop('ANOHAN')
            r['INIHA'] = ''
            # December of the year before is heaped (in 1975, 22,443 previous children "born" 12/74 against
            # 6,000-8,000 in nearby months): treated as a filler for an unknown date and left out
            filler = mh == '12' and ah.isdigit() and 1900 + int(ah) == int(r['ANOPAR']) - 1
            if mh.isdigit() and ah.isdigit() and 1 <= int(mh) <= 12 and not filler:
                d = (int(r['ANOPAR']) * 12 + int(r['MESPAR'])) - ((1900 + int(ah)) * 12 + int(mh))
                r['INIHA'] = str(d) if d > 0 else ''
            r['CESAREA'] = None
            for k in ('PAISNXM', 'PAISNXP', 'PAISNACM', 'PAISNACP', 'NACIOEM', 'CUANNACM'):
                r[k] = None
            return r
        return '1975', map(conv, lines())
    if width <= 70:
        def conv(ln):
            r = {k: ln[p - 1:p - 1 + n].strip() for k, (p, n) in LAYOUT_1980.items()}
            r['ANOPAR'] = '19' + r['ANOPAR']
            r['ANIOMAT'] = '19' + r['ANIOMAT'] if r['ANIOMAT'] not in ('', '00') else ''
            r['SEMANAS'] = '' if r['SEMANAS'] in ('', '00') else r['SEMANAS']
            r['EDADP'] = '' if r['EDADP'] in ('', '00', '99') else r['EDADP']
            r['PESON'] = '' if r['PESON'] in ('', '0', '0000') else r['PESON']
            # months since the previous live-born child, from its birth month/year (the file's own
            # interval field is in whole years and counts from the wedding)
            mh, ah = r.pop('MESHAN'), r.pop('ANOHAN')
            r['INIHA'] = ''
            if mh.isdigit() and ah.isdigit() and 1 <= int(mh) <= 12 and ah != '00':
                d = (int(r['ANOPAR']) * 12 + int(r['MESPAR'])) - ((1900 + int(ah)) * 12 + int(mh))
                r['INIHA'] = str(d) if d > 0 else ''
            r['ECIVM'] = r.pop('CAS')  # 1 married, 2 not married
            r['CESAREA'] = None
            for k in ('PAISNXM', 'PAISNXP', 'PAISNACM', 'PAISNACP', 'NACIOEM', 'CUANNACM'):
                r[k] = None
            return r
        return '1980', map(conv, lines())
    if width <= 90:
        def conv(ln):
            r = {k: ln[p - 1:p - 1 + n].strip() for k, (p, n) in LAYOUT_1996.items()}
            r['SEMANAS'] = '' if r['SEMANAS'] in ('', '00') else r['SEMANAS']
            r['EDADP'] = '' if r['EDADP'] in ('', '99') else r['EDADP']
            r['PESON'] = '' if r['PESON'] in ('', '0', '0000') else r['PESON']
            r['INIHA'] = '' if r['INIHA'] in ('', '999') else r['INIHA']
            r['ECIVM'] = r.pop('CAS')  # 1 married, 2 not married
            r['CESAREA'] = None
            r['PAISNXM'] = r['PAISNXP'] = None
            r['NACIOEM'] = r['CUANNACM'] = None
            return r
        return '1996', map(conv, lines())
    pos = {v['name']: (v['position'] - 1, v['length']) for v in dr['layout']}
    return '2016', ({k: ln[pos[k][0]:pos[k][0] + pos[k][1]].strip() for k in FIELDS_2016} for ln in lines())


def read_rows(src, dr):
    """Return (rows, layout_name)."""
    fmt, it = iter_rows(src, dr)
    return list(it), fmt


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('src')
    ap.add_argument('out')
    ap.add_argument('--layout', default=DEFAULT_LAYOUT)
    a = ap.parse_args()

    dr = json.load(open(a.layout, encoding='utf-8'))

    rows, fmt = read_rows(a.src, dr)
    year = Counter(r['ANOPAR'] for r in rows).most_common(1)[0][0]
    m_ages = [int(r['EDADM']) for r in rows if r['EDADM']]
    p_ages = [int(r['EDADP']) for r in rows if r['EDADP']]
    mAge, pAge = [min(m_ages), max(m_ages)], [min(p_ages), max(p_ages)]
    provinces = {k: v for k, v in dr['codelists']['TPROV'].items() if k.isdigit() and 1 <= int(k) <= 52}

    old = fmt in ('1996', '1980', '1975')
    has_origin = fmt not in ('1980', '1975')  # the 1975-95 layouts record neither nationality nor country of birth
    ORIG = 'PAISNACM' if old else 'PAISNXM'  # 1996 layout has nationality only
    ORIG_P = 'PAISNACP' if old else 'PAISNXP'
    marital_labels = MARITAL_1996 if old else MARITAL_2016
    slices = defaultdict(lambda: new_slice(mAge[1] - mAge[0] + 1, pAge[1] - pAge[0] + 1, len(marital_labels)))
    missing = Counter()
    for r in rows:
        if not r['SEMANAS']:
            missing['weeks'] += 1
        if not r['PESON']:
            missing['weight'] += 1
        if not r['EDADP']:
            missing['fatherAge'] += 1
        prov = r['PROREM']
        if prov not in provinces:
            missing['residesAbroad'] += 1
        origins = ['all', 'es' if r[ORIG] == SPAIN else 'ab'] if has_origin else ['all']
        targets = [slices[f'{o}|{p}'] for o in origins for p in (['ES', prov] if prov in provinces else ['ES'])]

        am = int(r['EDADM'])
        ag = age_group(am)
        order = int(r['SORDENV'] or 0)
        w = int(r['PESON']) if r['PESON'] else None
        wk = int(r['SEMANAS']) if r['SEMANAS'] else None
        married = r['ECIVM'] == '1'
        contM, contP = continent(r[ORIG]), continent(r[ORIG_P])
        mult = r['MULTIPLI'] not in ('', '1')
        cmp = r['NORMA'] == '2'
        boy = r['SEXO'] == '1'
        sx = 0 if boy else 1 if r['SEXO'] == '6' else None
        wed = None  # months from wedding to a married mother's first birth
        if married and order == 1:
            if r['MESMAT'].isdigit() and r['ANIOMAT'].isdigit() and 1 <= int(r['MESMAT']) <= 12:
                d = (int(r['ANOPAR']) * 12 + int(r['MESPAR'])) - (int(r['ANIOMAT']) * 12 + int(r['MESMAT']))
                wed = d if d >= 0 else None  # a wedding after the birth is a recording error
            else:
                wed = 'no'
        bornAbroad = not old and r[ORIG] not in ('', SPAIN)
        esNat = bornAbroad and r['NACIOEM'] == '1'
        for s in targets:
            s['n'] += 1
            s['ageM'][am - mAge[0]] += 1
            if contM:
                s['ageMc'][contM][am - mAge[0]] += 1
            if r['EDADP']:
                s['ageP'][int(r['EDADP']) - pAge[0]] += 1
                if contP:
                    s['agePc'][contP][int(r['EDADP']) - pAge[0]] += 1
            s['first'] += order == 1
            s['ces'] += r['CESAREA'] == '1'
            s['pre'] += r['INTERSEM'] == '2'
            s['mult'] += mult
            s['cmp'] += cmp
            s['married'] += married
            s['month'][int(r['MESPAR']) - 1] += 1
            b = s['byAge']
            b['n'][ag] += 1
            b['ces'][ag] += r['CESAREA'] == '1'
            b['pre'][ag] += r['INTERSEM'] == '2'
            b['mult'][ag] += mult
            b['cmp'][ag] += cmp
            if contM:
                s['cmpC'][contM]['n'][ag] += 1
                s['cmpC'][contM]['cmp'][ag] += cmp
            if sx is not None:
                s['sex']['all'][sx] += 1
                if order:
                    s['sex']['order'][min(order, 4) - 1][sx] += 1
                if contM:
                    s['sex']['cont'][contM][sx] += 1
            if wed == 'no':
                s['wedNo'] += 1
            elif wed is not None:
                s['wed'][min(wed, WED_MAX + 1)] += 1
            if esNat:
                s['natEs']['n'] += 1
                s['natEs']['later'] += r['CUANNACM'] == '2'
                s['natEs']['birth'] += r['CUANNACM'] == '1'
                s['countriesEs'][r[ORIG]] += 1
            if order:
                b['order'][min(order, 4) - 1][ag] += 1
            if w is not None:
                s['wKnown'] += 1
                s['lbw'] += w < 2500
                b['wKnown'][ag] += 1
                b['lbw'][ag] += w < 2500
            if w is not None and wk is not None:
                s['heat'][min(max(wk, WEEKS[0]), WEEKS[1]) - WEEKS[0]][wbin(w)] += 1
            if order > 1 and r['INIHA'] and int(r['INIHA']) > 0:
                s['interval'][min(int(r['INIHA']), INT_MAX) // INT_BIN] += 1
            if r['ECIVM']:
                s['marital'][int(r['ECIVM']) - 1] += 1
            for key, cm, cp in (('birth', 'PAISNXM', 'PAISNXP'), ('nat', 'PAISNACM', 'PAISNACP')):
                m, p = r[cm], r[cp]
                if not (m and p):  # also skips fields the layout lacks (None)
                    continue
                for u in ('all', 'mar' if married else 'unm'):
                    g = s['mixed'][key][u]
                    g['k'] += 1
                    g['ab'] += m != SPAIN and p != SPAIN  # both parents foreign (same or different country)
                    if m != p:
                        g['d'] += 1
                        if m == SPAIN:
                            g['dir'][0] += 1
                            g['esM'][p] += 1
                        elif p == SPAIN:
                            g['dir'][1] += 1
                            g['esP'][m] += 1
                        else:
                            g['dir'][2] += 1
            if has_origin and r[ORIG] != SPAIN:  # blank (not recorded) ends up in countriesOther
                s['countries'][r[ORIG] or '_unknown'] += 1

    used = set()
    out_slices = {}
    for o in ('all', 'es', 'ab') if has_origin else ('all',):
        for p in ['ES'] + sorted(provinces):
            s = slices[f'{o}|{p}']
            unknown = s['countries'].pop('_unknown', 0)
            top = s['countries'].most_common(TOP_COUNTRIES)
            s['countriesOther'] = sum(s['countries'].values()) - sum(v for _, v in top) + unknown
            s['countries'] = dict(top)
            s['countriesEs'] = {c: s['countriesEs'][c] for c in s['countries']}
            used.update(s['countries'])
            for key in ('birth', 'nat'):
                for g in s['mixed'][key].values():
                    for side in ('esM', 'esP'):
                        g[side] = [[c, v] for c, v in g[side].most_common(TOP_PARENT)]
                        used.update(c for c, _ in g[side])
            out_slices[f'{o}|{p}'] = s

    meta = {
        'year': int(year), 'n': len(rows), 'provinces': provinces,
        'countries': {**{'155': 'Serbia y Montenegro'}, **dr['codelists']['TPAIS']},  # 155: pre-2006 code
        'ageGroups': AGE_GROUPS, 'mAge': mAge, 'pAge': pAge, 'weeks': list(WEEKS), 'wEdges': W_EDGES,
        'intBin': INT_BIN, 'intMax': INT_MAX, 'wedMax': WED_MAX, 'layout': fmt, 'marital': marital_labels,
        'avail': {'ces': not old, 'birthCountry': not old, 'natEs': not old, 'origin': has_origin}, 'missing': {k: missing[k] for k in ('weeks', 'weight', 'fatherAge', 'residesAbroad')},
    }
    with open(a.out, 'w', encoding='utf-8') as f:
        json.dump({'meta': meta, 'slices': out_slices}, f, ensure_ascii=False, separators=(',', ':'))
    print(f'{a.out}: {len(rows):,} births, year {year}')


if __name__ == '__main__':
    main()
