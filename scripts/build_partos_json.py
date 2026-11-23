"""Babies born alive, died within 24 hours and stillborn, from the INE deliveries file (MNP partos).

One record per delivery with up to six babies; each baby has CLASIFn:
  3 = born alive and lived more than 24 hours, 1 = born alive and died within 24 hours,
  2 = late fetal death (stillborn).
Counts are national (no provinces), by mother's country of birth and by mother's age group
(for all mothers, mothers born in Spain and mothers born abroad).

Reads the 2016+ layout (2015, 2025...), the 1996 layout (2006: mother's nationality instead of
country of birth) and the 1980-95 layout (1985, 1995: no origin at all), detected from the record length.

Years already in the output file are kept, so years can be added one at a time.

Usage:
    python build_partos_json.py <md_MNPpartos_YYYY.txt> <out.json> [--layout dr_MNPpartos_2016.json]
"""
import argparse
import json
import os
from collections import Counter

DEFAULT_LAYOUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'dr_MNPpartos_2016.json')
AGE_GROUPS = ['<20', '20–24', '25–29', '30–34', '35–39', '40–44', '45+']
SPAIN = '108'
KIND = {'3': 0, '1': 1, '2': 2}  # -> [alive past 24 h, died within 24 h, stillborn]


def age_group(a):
    return 0 if a < 20 else 6 if a >= 45 else (a - 20) // 5 + 1


def continent(code):
    if code == SPAIN:
        return 'es'
    return {'1': 'eu', '2': 'af', '3': 'am', '4': 'as'}.get(code[:1])  # Oceania / blank: none


# Older layouts, 1-based (position, length). Each baby is a 12-character block; `clasif` and `alive`
# are offsets inside it. From the INE design documents "disreg partos80-95" and "disreg partos96".
OLD = {
    # 1980-95 (119 characters): no nationality or country of birth; up to 5 babies
    '1980': {'year': (12, 2), 'multi': (14, 1), 'edadm': (108, 2), 'baby': 46, 'alive': 0, 'clasif': 11, 'slots': 5, 'origin': None},
    # 1996+ (184 characters): mother's nationality (NACMAD) at 179, after a 7th baby block the document lists
    '1996': {'year': (8, 4), 'multi': (16, 1), 'edadm': (58, 2), 'baby': 71, 'alive': 1, 'clasif': 11, 'slots': 7, 'origin': (179, 3)},
}


def reader(first_line, dr):
    """Return (layout name, basis of origin, function line -> (year, multiplicity, mother age, origin code, [(clasif, alive)]))."""
    width = len(first_line.rstrip('\r\n'))
    if width <= 190:
        L = OLD['1980' if width <= 130 else '1996']
        f = lambda ln, p: ln[p[0] - 1:p[0] - 1 + p[1]].strip()

        def read(ln):
            y = f(ln, L['year'])
            m = f(ln, L['multi'])
            babies = []
            for i in range(min(int(m) if m.isdigit() and int(m) else 1, L['slots'])):
                b = L['baby'] - 1 + 12 * i
                babies.append((ln[b + L['clasif']:b + L['clasif'] + 1].strip(), ln[b + L['alive']:b + L['alive'] + 1]))
            return ('19' + y if len(y) == 2 else y), len(babies), f(ln, L['edadm']), f(ln, L['origin']) if L['origin'] else None, babies
        return ('1980' if width <= 130 else '1996'), ('none' if width <= 130 else 'nationality'), read

    pos = {v['name']: (v['position'] - 1, v['length']) for v in dr['layout']}
    get = lambda ln, k: ln[pos[k][0]:pos[k][0] + pos[k][1]].strip()

    def read(ln):
        m = int(get(ln, 'MULTIPLI') or 1)
        return get(ln, 'ANIOPAR'), m, get(ln, 'EDADM'), get(ln, 'PAISNXM'), \
            [(get(ln, f'CLASIF{i}'), get(ln, f'NACVN{i}')) for i in range(1, min(m, 6) + 1)]
    return '2016', 'birth', read


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('src')
    ap.add_argument('out')
    ap.add_argument('--layout', default=DEFAULT_LAYOUT)
    a = ap.parse_args()

    dr = json.load(open(a.layout, encoding='utf-8'))
    with open(a.src, encoding='latin-1') as fh:
        first = next(ln for ln in fh if ln.strip())
    layout, basis, read = reader(first, dr)

    groups = {k: [0, 0, 0] for k in ('all', 'es', 'ab', 'eu', 'af', 'am', 'as')}
    age = {k: [[0, 0, 0] for _ in AGE_GROUPS] for k in ('all', 'es', 'ab')}
    years, deliveries, unknown, bad = Counter(), 0, 0, 0
    with open(a.src, encoding='latin-1') as fh:
        for ln in fh:
            if not ln.strip():
                continue
            deliveries += 1
            year, mult, edadm, m, babies = read(ln)
            years[year] += 1
            cont = continent(m) if m else None
            origin = None if not m else 'es' if m == SPAIN else 'ab'
            ag = age_group(int(edadm))
            for clasif, alive in babies:
                k = KIND.get(clasif)
                if k is None:  # no classification: fall back on born alive (1) / dead (2), alive assumed past 24 h
                    bad += 1
                    k = 2 if alive == '2' else 0 if alive == '1' else None
                    if k is None:
                        continue
                targets = [groups['all'], age['all'][ag]]
                if origin:
                    targets += [groups[origin], age[origin][ag]]
                elif basis != 'none':
                    unknown += 1
                if cont and cont != 'es':
                    targets.append(groups[cont])
                for t in targets:
                    t[k] += 1

    year = years.most_common(1)[0][0]
    try:
        out = json.load(open(a.out, encoding='utf-8'))
    except (OSError, ValueError):
        out = {}
    out[year] = {'deliveries': deliveries, 'ageGroups': AGE_GROUPS, 'groups': groups, 'age': age, 'layout': layout,
                 'basis': basis, 'unknownOrigin': unknown, 'unclassified': bad}
    out = dict(sorted(out.items(), reverse=True))
    json.dump(out, open(a.out, 'w', encoding='utf-8'), separators=(',', ':'))
    g = groups['all']
    print(f'{a.out}: {year} ({layout} layout, origin by {basis}): {deliveries:,} deliveries; {g[0]:,} alive past 24 h, '
          f'{g[1]:,} died within 24 h, {g[2]:,} stillborn; origin unknown for {unknown:,} babies; {bad} without classification')


if __name__ == '__main__':
    main()
