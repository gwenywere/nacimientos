"""Children per woman (total fertility rate) by mother's country of birth / nationality.

Births by mother's single year of age come from the data.json files made by
build_nacimientos_json.py. Women by single year of age come from INE table 56939
(Estadística Continua de Población: women by age, nationality and birthplace grouping),
downloaded through INE's public API.

TFR = sum over ages 15..49 of births(age) / women(age). Births to mothers under 15
count at 15 and over 49 at 49. "Rest of Europe" = all foreign-born (or foreign) women
minus Africa, the Americas, Asia and Oceania, because the EU/non-EU split only starts in 2012.

Usage:
    python build_tfr.py out.json 2025=data.json 2015=data-2015.json 2006=data-2006.json
"""
import json
import re
import sys
import urllib.request
from datetime import datetime, timezone

API = 'https://servicios.ine.es/wstempus/js/ES/DATOS_TABLA/56939?nult=100&tv=18:453&tv=141:{nat}&tv=431:{bp}'
TOTAL = '16420'
# INE value ids (same ids are used for nationality and birthplace groupings)
SPAIN_BP, SPAIN_NAT, FOREIGN = '274511', '21386', '274512'
AFRICA, N_AMERICA, C_AMERICA, S_AMERICA, ASIA, OCEANIA = '9947', '292919', '292918', '16435', '9966', '16438'
# population date per year: mid-year where available; 2025 only has 1 January
POP_DATE = {'2006': '2006-07-01', '2015': '2015-07-01', '2025': '2025-01-01'}
# the 2006 births file has nationality only, so 2006 uses women by nationality
BASIS = {'2006': 'nationality'}


def fetch(code, by_nat):
    url = API.format(nat=code if by_nat else TOTAL, bp=TOTAL if by_nat else code)
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (data-client)'})
    data = json.loads(urllib.request.urlopen(req, timeout=180).read().decode('utf-8'))
    out = {}
    for s in data:
        m = re.search(r'Mujeres\. (\d+) años?\.', s['Nombre'])
        if m:
            out[int(m.group(1))] = {
                datetime.fromtimestamp(x['Fecha'] / 1000 + 7200, timezone.utc).strftime('%Y-%m-%d'): x['Valor'] for x in s['Data']}
    return out


def main():
    out_path, pairs = sys.argv[1], [a.split('=', 1) for a in sys.argv[2:]]
    cache = {}
    get = lambda code, by_nat: cache.setdefault((code, by_nat), fetch(code, by_nat))
    result = {}
    for year, path in pairs:
        by_nat = BASIS.get(year) == 'nationality'
        date = POP_DATE[year]
        P = lambda code: {a: v.get(date, 0) for a, v in get(code, by_nat).items()}
        plus = lambda *xs: {a: sum(x[a] for x in xs) for a in xs[0]}
        foreign, africa, americas, asia, oceania = P(FOREIGN), P(AFRICA), plus(P(N_AMERICA), P(C_AMERICA), P(S_AMERICA)), P(ASIA), P(OCEANIA)
        pops = {
            'all': {a: v.get(date, 0) for a, v in get(TOTAL, False).items()},
            'es': P(SPAIN_NAT if by_nat else SPAIN_BP), 'ab': foreign,
            'eu': {a: foreign[a] - africa[a] - americas[a] - asia[a] - oceania[a] for a in foreign},
            'af': africa, 'am': americas, 'as': asia,
        }
        d = json.load(open(path, encoding='utf-8'))
        m0, sl = d['meta']['mAge'][0], d['slices']
        births = {'all': sl['all|ES']['ageM'], 'ab': sl['ab|ES']['ageM'], **{k: sl['all|ES']['ageMc'][k] for k in ('es', 'eu', 'af', 'am', 'as')}}
        groups = {}
        for g, pop in pops.items():
            b = [0] * 35
            for i, c in enumerate(births[g]):
                b[min(max(i + m0, 15), 49) - 15] += c
            rates = [b[a - 15] / pop[a] if pop.get(a) else 0 for a in range(15, 50)]
            groups[g] = {
                'tfr': round(sum(rates), 3), 'births': sum(births[g]), 'women': round(sum(pop.get(a, 0) for a in range(15, 50))),
                'meanAge': round(sum((a + 0.5) * r for a, r in zip(range(15, 50), rates)) / sum(rates), 1),
            }
        result[year] = {'popDate': date, 'basis': 'nationality' if by_nat else 'birth', 'groups': groups}
        print(year, {g: v['tfr'] for g, v in groups.items()})
    json.dump(result, open(out_path, 'w', encoding='utf-8'), separators=(',', ':'))


if __name__ == '__main__':
    main()
