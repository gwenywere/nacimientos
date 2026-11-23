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

from build_nacimientos_json import DEFAULT_LAYOUT as NAC_LAYOUT, SPAIN, iter_rows
from build_partos_json import DEFAULT_LAYOUT as PAR_LAYOUT, KIND, reader as partos_reader
from build_tfr import fetch_total

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


def births(path):
    dr = json.load(open(NAC_LAYOUT, encoding='utf-8'))
    fmt, rows = iter_rows(path, dr)
    c = Counter()
    ageM, ageM1 = Counter(), Counter()
    years = Counter()
    for r in rows:
        years[r['ANOPAR']] += 1
        c['n'] += 1
        am = int(r['EDADM']) if r['EDADM'].isdigit() else None
        order = int(r['SORDENV']) if (r['SORDENV'] or '').isdigit() else 0
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
        if r['PAISNXM'] is not None and r['PAISNXM']:
            c['bornK'] += 1
            c['bornAb'] += r['PAISNXM'] != SPAIN
        if r['PAISNXM'] is not None:
            c['bornLay'] += 1
        if r['PAISNACM'] is not None and r['PAISNACM']:
            c['natK'] += 1
            c['natAb'] += r['PAISNACM'] != SPAIN
    return {'layout': fmt, 'fileYear': years.most_common(1)[0][0], 'c': dict(c),
            'ageM': dict(ageM), 'ageM1': dict(ageM1)}


def partos(path):
    dr = json.load(open(PAR_LAYOUT, encoding='utf-8'))
    with open(path, encoding='latin-1') as fh:
        first = next(ln for ln in fh if ln.strip())
    if len(first.rstrip('\r\n')) < 40:  # 1975-79: multiple deliveries only, no use here
        return None
    _, _, read = partos_reader(first, dr)
    k3, years = [0, 0, 0], Counter()
    with open(path, encoding='latin-1') as fh:
        for ln in fh:
            if not ln.strip():
                continue
            try:
                year, _, _, _, babies = read(ln)
            except ValueError:  # malformed record
                continue
            years[year] += 1
            for clasif, alive in babies:
                k = KIND.get(clasif)
                if k is None:
                    k = 2 if alive == '2' else 0 if alive == '1' else None
                if k is not None:
                    k3[k] += 1
    return {'fileYear': years.most_common(1)[0][0], 'k': k3}


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
            c = Counter(b['c'])
            ageM = Counter({int(k): v for k, v in b['ageM'].items()})
            ageM1 = Counter({int(k): v for k, v in b['ageM1'].items()})
            y.update({
                'layout': b['layout'], 'births': c['n'],
                'meanAgeM': mean(ageM), 'meanAgeM1': mean(ageM1),
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
                # 2007-08 files fill the mother's country of birth only when it is not Spain: blank = Spain there
                'abroadBirth': share(c['bornAb'], c['bornK']) if c['bornK'] > 0.5 * c['n']
                else share(c['bornAb'], c['n']) if c['bornLay'] and c['bornAb'] > 0.05 * c['n'] else None,
                'abroadNat': share(c['natAb'], c['natK']) if c['natK'] > 0.5 * c['n'] else None,
                '_ageM': {str(k): v for k, v in sorted(ageM.items())},
            })
        if r.get('partos'):
            alive, died, still = r['partos']['k']
            y.update({'babies': alive + died + still, 'stillborn': still, 'died24': died,
                      'stillRate': round(1000 * still / (alive + died + still), 2),
                      'died24Rate': round(1000 * died / (alive + died), 2)})
        out[str(year)] = y

    if not a.no_tfr:
        for year, y in sorted(out.items()):
            if str(lo) <= year <= str(hi) and '_ageM' in y:
                date = f'{year}-07-01'
                pop = fetch_total(date)
                if not pop:
                    date = f'{year}-01-01'
                    pop = fetch_total(date)
                y['tfr'], y['popDate'] = tfr({int(k): v for k, v in y['_ageM'].items()}, pop), date
                print(year, 'children per woman', y['tfr'], flush=True)

    meta = {'source': 'INE, Movimiento Natural de la Población (anonymised microdata); women by age: INE table 56934',
            'layouts': {'1975': '1975–1979', '1980': '1980–1995', '1996': '1996–2006', '2016': '2007 onwards'}}
    years = {k: {kk: vv for kk, vv in v.items()} for k, v in sorted(out.items())}
    with open(a.out, 'w', encoding='utf-8') as f:
        json.dump({'meta': meta, 'years': years}, f, ensure_ascii=False, separators=(',', ':'))
    print(f'{a.out}: {len(years)} years')


if __name__ == '__main__':
    main()
