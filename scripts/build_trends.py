"""Year-by-year indicators, 1975 to the latest year, for the "Nacimientos 1975–2025" trends page.

Walks the folder the INE microdata zips were unpacked into (one folder per year and file, as
download_ine_mnp.py leaves them: "datos nacimientos 85", "datos_nacimientos11", "datos partos90",
"datos_partos16"...), reads every births file and every deliveries file, and writes one small JSON
with a handful of indicators per year. Record layouts (1975-79, 1980-95, 1996-2006, 2007+) are
detected from the record length by the same readers the yearly dashboards use.

Children per woman uses women by single year of age on 1 July of each year from INE table 56934
(through INE's public API), as build_tfr.py does for the yearly pages.

Usage:
    python build_trends.py <data/nacimientos folder> <out.json> [--years 1975-2025] [--jobs 3] [--no-tfr]
"""
import argparse
import json
import os
import re
from collections import Counter
from multiprocessing import Pool

from build_nacimientos_json import DEFAULT_LAYOUT as NAC_LAYOUT, SPAIN, continent, iter_rows
from build_partos_json import DEFAULT_LAYOUT as PAR_LAYOUT, KIND, reader as partos_reader
from build_tfr import AFRICA, ASIA, C_AMERICA, FOREIGN, N_AMERICA, OCEANIA, S_AMERICA, SPAIN_BP, SPAIN_NAT, TOTAL, fetch, fetch_total

SKIP = re.compile(r'leeme|\.(json|parquet|zip|docx?|xlsx?|pdf|identifier)$', re.I)


def find_files(root):
    """{('nacim' | 'partos', year): path}: the largest data file directly inside each year folder."""
    out = {}
    for d in sorted(os.listdir(root)):
        m = re.fullmatch(r'datos[ _](nacimientos|partos) ?(\d{2})', d.strip())
        full = os.path.join(root, d)
        if not m or not os.path.isdir(full):
            continue
        yy = int(m.group(2))
        year = 1900 + yy if yy >= 75 else 2000 + yy
        files = [os.path.join(full, f) for f in os.listdir(full)
                 if os.path.isfile(os.path.join(full, f)) and not SKIP.search(f)]
        if files:
            out[('nacim' if m.group(1) == 'nacimientos' else 'partos', year)] = max(files, key=os.path.getsize)
    return out


GROUPS = ('es', 'ab', 'eu', 'af', 'am', 'as')  # Spain, abroad, rest of Europe, Africa, Americas, Asia


def origin_groups(code, year):
    """Groups a mother's origin code falls in. In 2007-08 the country of birth is filled in only when it
    is not Spain, so a blank is Spain there; elsewhere a blank is unknown. Oceania counts in 'ab' only."""
    if code is None:
        return ()
    if not code:
        if str(year) not in ('2007', '2008'):
            return ()
        code = SPAIN
    if code == SPAIN:
        return ('es',)
    k = continent(code)
    return ('ab', k) if k and k != 'es' else ('ab',)


def births(path):
    dr = json.load(open(NAC_LAYOUT, encoding='utf-8'))
    fmt, rows = iter_rows(path, dr)
    acc = {g: (Counter(), Counter(), Counter()) for g in ('all',) + GROUPS}  # counts, mother's age, age at first child
    years = Counter()
    for r in rows:
        years[r['ANOPAR']] += 1
        # origin: country of birth where recorded (2007 on), else nationality (1996-2006), else none
        code = r['PAISNXM'] if r['PAISNXM'] is not None else r['PAISNACM']
        am = int(r['EDADM']) if r['EDADM'].isdigit() else None
        order = int(r['SORDENV']) if (r['SORDENV'] or '').isdigit() else 0
        for g in ('all',) + origin_groups(code, r['ANOPAR']):
            c, ageM, ageM1 = acc[g]
            c['n'] += 1
            if am:
                ageM[am] += 1
                if order == 1:
                    ageM1[am] += 1
            if r['EDADP'].isdigit():
                c['pN'] += 1
                c['pSum'] += int(r['EDADP'])
            if order:
                c['ordK'] += 1
                c['ord1'] += order == 1
                c['ord2'] += order == 2
                c['ord3'] += order >= 3
            c['boys'] += r['SEXO'] == '1'
            c['girls'] += r['SEXO'] == '6'
            c['mult'] += r['MULTIPLI'] not in ('', '1')
            if r['ECIVM'] in ('1', '2', '3', '4'):
                c['marK'] += 1
                c['unm'] += r['ECIVM'] != '1'
            if r['INTERSEM'] in ('1', '2'):
                c['preK'] += 1
                c['pre'] += r['INTERSEM'] == '2'
            if r['PESON'].isdigit():  # a few records have typos such as '34OO'
                c['wK'] += 1
                c['lbw'] += int(r['PESON']) < 2500
            if r['CESAREA'] in ('1', '2'):
                c['cesK'] += 1
                c['ces'] += r['CESAREA'] == '1'
            if g != 'all':
                continue
            if r['PAISNXM'] is not None and r['PAISNXM']:
                c['bornK'] += 1
                c['bornAb'] += r['PAISNXM'] != SPAIN
            if r['PAISNXM'] is not None:
                c['bornLay'] += 1
            if r['PAISNACM'] is not None and r['PAISNACM']:
                c['natK'] += 1
                c['natAb'] += r['PAISNACM'] != SPAIN
    return {'layout': fmt, 'fileYear': years.most_common(1)[0][0],
            'groups': {g: [dict(x) for x in v] for g, v in acc.items() if v[0]['n']},
            'basis': 'birth' if fmt == '2016' else 'nationality' if fmt == '1996' else None}


def partos(path):
    dr = json.load(open(PAR_LAYOUT, encoding='utf-8'))
    with open(path, encoding='latin-1') as fh:
        first = next(ln for ln in fh if ln.strip())
    if len(first.rstrip('\r\n')) < 40:  # 1975-79: multiple deliveries only, no use here
        return None
    _, _, read = partos_reader(first, dr)
    k3 = {g: [0, 0, 0] for g in ('all',) + GROUPS}
    years = Counter()
    with open(path, encoding='latin-1') as fh:
        for ln in fh:
            if not ln.strip():
                continue
            try:
                year, _, _, code, babies = read(ln)
            except ValueError:  # malformed record
                continue
            years[year] += 1
            targets = [k3[g] for g in ('all',) + origin_groups(code, year)]
            for clasif, alive in babies:
                k = KIND.get(clasif)
                if k is None:
                    k = 2 if alive == '2' else 0 if alive == '1' else None
                if k is not None:
                    for t in targets:
                        t[k] += 1
    return {'fileYear': years.most_common(1)[0][0], 'k': k3['all'], 'kO': {g: v for g, v in k3.items() if g != 'all' and sum(v)}}


def indicators(c, ageM, ageM1):
    """The per-year numbers for one group of births."""
    c, ageM, ageM1 = Counter(c), Counter({int(k): v for k, v in ageM.items()}), Counter({int(k): v for k, v in ageM1.items()})
    return {
        'births': c['n'], 'meanAgeM': mean(ageM), 'meanAgeM1': mean(ageM1),
        'meanAgeP': round(c['pSum'] / c['pN'], 2) if c['pN'] else None,
        'sexRatio': round(100 * c['boys'] / c['girls'], 2) if c['girls'] else None,
        'unmarried': share(c['unm'], c['marK']),
        'multiple': share(c['mult'], c['n']),
        'preterm': share(c['pre'], c['preK']),
        'lowWeight': share(c['lbw'], c['wK']) if c['wK'] > 0.5 * c['n'] else None,
        'caesarean': share(c['ces'], c['cesK']) if c['cesK'] > 0.5 * c['n'] else None,
        'order': [share(c['ord1'], c['ordK']), share(c['ord2'], c['ordK']), share(c['ord3'], c['ordK'])],
        'teen': share(sum(v for k, v in ageM.items() if k < 20), c['n']),
        'over40': share(sum(v for k, v in ageM.items() if k >= 40), c['n']),
    }


def partos_rates(k):
    alive, died, still = k
    if not alive + died + still:
        return {}
    return {'babies': alive + died + still, 'stillborn': still, 'died24': died,
            'stillRate': round(1000 * still / (alive + died + still), 2),
            'died24Rate': round(1000 * died / (alive + died), 2) if alive + died else None}


def work(job):
    kind, year, path = job
    return kind, year, (births if kind == 'nacim' else partos)(path)


def mean(counter):
    n = sum(counter.values())
    return round(sum(a * v for a, v in counter.items()) / n, 2) if n else None  # completed years, as on the yearly pages


def share(a, b, nd=2):
    return round(100 * a / b, nd) if b else None


def tfr(ageM, pop):
    b = [0] * 35
    for a, v in ageM.items():
        b[min(max(a, 15), 49) - 15] += v
    rates = [b[a - 15] / pop[a] if pop.get(a) else 0 for a in range(15, 50)]
    return round(sum(rates), 3)


POP_ORIGIN_FROM = 2002  # INE table 56939 (women by age and nationality / country of birth) starts in 2002


def origin_tfr(y, year, get):
    """Children per woman by mother's origin, on the same basis as the births (nationality or country of birth).
    Women from table 56939; "rest of Europe" = all foreign minus Africa, Americas, Asia and Oceania, as in build_tfr.py."""
    by_nat = y['originBasis'] == 'nationality'
    dates = next(iter(get(TOTAL, False).values()))
    date = f'{year}-07-01' if f'{year}-07-01' in dates else f'{year}-01-01'
    P = lambda code: {a: v.get(date, 0) for a, v in get(code, by_nat).items()}
    foreign, africa, asia, oceania = P(FOREIGN), P(AFRICA), P(ASIA), P(OCEANIA)
    n, c, s = P(N_AMERICA), P(C_AMERICA), P(S_AMERICA)
    americas = {a: n[a] + c[a] + s[a] for a in n}
    pops = {'es': P(SPAIN_NAT if by_nat else SPAIN_BP), 'ab': foreign, 'af': africa, 'am': americas, 'as': asia,
            'eu': {a: foreign[a] - africa[a] - americas[a] - asia[a] - oceania[a] for a in foreign}}
    return {g: tfr({int(k): v for k, v in y['_ageO'][g].items()}, pops[g]) for g in pops if g in y['_ageO']} | {'popDate': date}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('root')
    ap.add_argument('out')
    ap.add_argument('--years', default='1975-2100')
    ap.add_argument('--jobs', type=int, default=3)
    ap.add_argument('--no-tfr', action='store_true', help='keep the children-per-woman values already in out.json')
    a = ap.parse_args()
    lo, _, hi = a.years.partition('-')
    lo, hi = int(lo), int(hi or lo)

    files = find_files(a.root)
    jobs = sorted(((k, y, p) for (k, y), p in files.items() if lo <= y <= hi), key=lambda j: -os.path.getsize(j[2]))
    try:
        old = json.load(open(a.out, encoding='utf-8'))['years']
    except (OSError, ValueError, KeyError):
        old = {}
    raw = {}
    with Pool(a.jobs) as pool:
        for kind, year, res in pool.imap_unordered(work, jobs):
            raw.setdefault(year, {})[kind] = res
            note = '' if res is None else f" (file says {res['fileYear']})" if str(res['fileYear']) != str(year) else ''
            print(f'{kind:6} {year}{note}', flush=True)

    out = dict(old)
    for year in sorted(raw):
        r = raw[year]
        y = dict(old.get(str(year), {}))
        if 'nacim' in r:
            b = r['nacim']
            G = b['groups']
            c = Counter(G['all'][0])
            y.update(indicators(*G['all']))
            y.update({
                'layout': b['layout'],
                # 2007-08 files fill the mother's country of birth only when it is not Spain: blank = Spain there
                'abroadBirth': share(c['bornAb'], c['bornK']) if c['bornK'] > 0.5 * c['n']
                else share(c['bornAb'], c['n']) if c['bornLay'] and c['bornAb'] > 0.05 * c['n'] else None,
                'abroadNat': share(c['natAb'], c['natK']) if c['natK'] > 0.5 * c['n'] else None,
                '_ageM': {str(k): v for k, v in sorted(G['all'][1].items(), key=lambda kv: int(kv[0]))},
                '_ageO': {g: {str(k): v for k, v in sorted(G[g][1].items(), key=lambda kv: int(kv[0]))} for g in GROUPS if g in G},
                'originBasis': b['basis'],
                # the same indicators for each origin group (1996 on: nationality to 2006, country of birth from 2007)
                'o': {g: indicators(*G[g]) for g in GROUPS if g in G} or None,
            })
        if r.get('partos'):
            y.update(partos_rates(r['partos']['k']))
            if r['partos']['kO'] and y.get('o'):
                for g, k in r['partos']['kO'].items():
                    if g in y['o']:
                        y['o'][g].update(partos_rates(k))
        out[str(year)] = y

    cache = {}
    get = lambda code, by_nat: cache.setdefault((code, by_nat), fetch(code, by_nat))
    if not a.no_tfr:
        for year, y in sorted(out.items()):
            if str(lo) <= year <= str(hi) and '_ageM' in y:
                date = f'{year}-07-01'
                pop = fetch_total(date)
                if not pop:
                    date = f'{year}-01-01'
                    pop = fetch_total(date)
                y['tfr'], y['popDate'] = tfr({int(k): v for k, v in y['_ageM'].items()}, pop), date
                y['tfrO'] = origin_tfr(y, year, get) if int(year) >= POP_ORIGIN_FROM and y.get('_ageO') else None
                print(year, 'children per woman', y['tfr'], y['tfrO'] or '', flush=True)

    meta = {'source': 'INE, Movimiento Natural de la Población (anonymised microdata); women by age: INE table 56934',
            'layouts': {'1975': '1975–1979', '1980': '1980–1995', '1996': '1996–2006', '2016': '2007 onwards'}}
    years = {k: {kk: vv for kk, vv in v.items()} for k, v in sorted(out.items())}
    with open(a.out, 'w', encoding='utf-8') as f:
        json.dump({'meta': meta, 'years': years}, f, ensure_ascii=False, separators=(',', ':'))
    print(f'{a.out}: {len(years)} years')


if __name__ == '__main__':
    main()
