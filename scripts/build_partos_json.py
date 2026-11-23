"""Babies born alive, died within 24 hours and stillborn, from the INE deliveries file (MNP partos).

One record per delivery with up to six babies; each baby has CLASIFn:
  3 = born alive and lived more than 24 hours, 1 = born alive and died within 24 hours,
  2 = late fetal death (stillborn).
Counts are national (no provinces), by mother's country of birth and by mother's age group
(for all mothers, mothers born in Spain and mothers born abroad).

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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('src')
    ap.add_argument('out')
    ap.add_argument('--layout', default=DEFAULT_LAYOUT)
    a = ap.parse_args()

    dr = json.load(open(a.layout, encoding='utf-8'))
    pos = {v['name']: (v['position'] - 1, v['length']) for v in dr['layout']}
    get = lambda ln, k: ln[pos[k][0]:pos[k][0] + pos[k][1]].strip()

    groups = {k: [0, 0, 0] for k in ('all', 'es', 'ab', 'eu', 'af', 'am', 'as')}
    age = {k: [[0, 0, 0] for _ in AGE_GROUPS] for k in ('all', 'es', 'ab')}
    years, deliveries, unknown, bad = Counter(), 0, 0, 0
    with open(a.src, encoding='latin-1') as fh:
        for ln in fh:
            if not ln.strip():
                continue
            deliveries += 1
            years[get(ln, 'ANIOPAR')] += 1
            m = get(ln, 'PAISNXM')
            cont = continent(m) if m else None
            origin = None if not m else 'es' if m == SPAIN else 'ab'
            ag = age_group(int(get(ln, 'EDADM')))
            for i in range(1, int(get(ln, 'MULTIPLI') or 1) + 1):
                k = KIND.get(get(ln, f'CLASIF{i}'))
                if k is None:
                    bad += 1
                    continue
                targets = [groups['all'], age['all'][ag]]
                if origin:
                    targets += [groups[origin], age[origin][ag]]
                else:
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
    out[year] = {'deliveries': deliveries, 'ageGroups': AGE_GROUPS, 'groups': groups, 'age': age,
                 'unknownOrigin': unknown, 'unclassified': bad}
    json.dump(out, open(a.out, 'w', encoding='utf-8'), separators=(',', ':'))
    g = groups['all']
    print(f'{a.out}: {year}: {deliveries:,} deliveries; {g[0]:,} alive past 24 h, {g[1]:,} died within 24 h, '
          f'{g[2]:,} stillborn; origin unknown for {unknown:,} babies; {bad} unclassified')


if __name__ == '__main__':
    main()
