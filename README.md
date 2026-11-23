# Nacimientos en España · 1975, 1985, 1995, 2006, 2015, 2025

Interactive dashboard of every live birth registered in Spain in 1975, 1985, 1995, 2006, 2015 and 2025, built from INE microdata. Filter by year, mother's origin and province of residence. A second page follows a set of indicators through every year from 1975 to 2025.

**Live pages:** https://gwenywere.github.io/nacimientos/ (yearly dashboard) · https://gwenywere.github.io/nacimientos/trends.html (1975–2025)

## What it shows

- Children per woman (total fertility rate) by mother's country of birth and continent
- Age of mother and father, also by continent of birth
- Birth order, caesarean, preterm and low birth weight by mother's age
- Twins and multiple births by mother's age; complications by mother's age and origin
- Born alive, died within 24 hours and stillborn, by mother's origin and age (deliveries file; no origin for 1985 and 1995, nationality for 2006)
- Births per day by month; gestation × birth weight
- Boys per 100 girls, by birth order and mother's origin
- Time between the wedding and a married mother's first birth
- Mothers born abroad who hold Spanish nationality, by country of birth (2015, 2025)
- Interactive province map (births, mother's age, caesarean, preterm, mother born abroad, both parents born abroad, mixed couples)
- Mothers' countries of birth, marital status, and couples where the parents come from different countries

The trends page (`trends.html`) has one point per year, 1975–2025: live births, children per woman, parents' mean age (and mother's age at the first child), stillbirths and deaths within 24 hours (from 1980), boys per 100 girls, births outside marriage, mothers from abroad (nationality from 1996, country of birth from 2007), birth order, mothers under 20 and aged 40+, multiple births, and preterm / low weight / caesarean. Hovering a year highlights it in every chart.

Quirks in the yearly files show up there as they are: caesareans fall to about 18% in 2008–09 (likely incomplete recording), 2007 has four points more first children and a dip in fathers' age, and in 2007–08 the mother's country of birth is filled in only when it is not Spain (a blank counts as Spain). The 1975–79 deliveries files hold multiple deliveries only, so stillbirths start in 1980.

## Sources

- **Births:** [INE, Movimiento Natural de la Población — microdata of births](https://ine.es/dyngs/INEbase/es/operacion.htm?c=Estadistica_C&cid=1254736177007&menu=resultados&idp=1254735573002#_tabs-1254736195443). One record per live birth.
- **Women by age and country of birth** (for children per woman): [INE, Estadística Continua de Población, table 56939](https://www.ine.es/jaxiT3/Tabla.htm?t=56939), via INE's public API. For 1975, 1985 and 1995, women by age only, from [table 56934](https://www.ine.es/jaxiT3/Tabla.htm?t=56934), since table 56939 starts in 2002.
- **Stillbirths and deaths within 24 hours:** INE, Movimiento Natural de la Población — microdata of deliveries (*partos*), one record per delivery with every baby, including those born dead.
- **Province boundaries:** simplified from [GADM](https://gadm.org) level 2.

INE data are published under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). Figures computed here (especially children per woman) can differ slightly from INE's published indicators.

### Differences between years

| | 2015, 2025 | 2006 | 1985, 1995 |
|---|---|---|---|
| Record layout | INE 2016+ layout (~200 characters) | INE "anonimizado desde 1996" layout (85 characters) | INE anonymised layout for 1980–1995 (68 characters) |
| Parents' origin | Country of birth | Nationality only | Not recorded: no origin filter, children per woman for all women only |
| Caesarean | Recorded | Not recorded | Not recorded |
| Marital status | Married / single / separated or divorced / widowed | Married / not married | Married / not married |
| Months since the previous child | Recorded | Recorded | Worked out from the previous child's month and year of birth |

The 1985 and 1995 record layout comes from INE's design document for the 1980–1995 late fetal deaths file (*disreg mft80-95*), which the births files `NACIA85` and `NACIA95` share field for field. In 1985, weeks of pregnancy are missing for 42% of births and birth weight for 18%.

1975 uses INE's 1975–1979 layout (*disreg nac 75-79*, 50 characters): no weeks of pregnancy, birth weight, caesarean or origin; marital status is the baby's legitimacy (legitimate = married). Previous children dated December 1974 are heaped (22,443 against 6,000–8,000 in nearby months), so that date is treated as unknown in the time since the previous child.

## Files

| File | Contents |
|---|---|
| `index.html` | The yearly dashboard (plain HTML + [D3](https://d3js.org) from a CDN); `index.html?year=1985` opens a given year |
| `trends.html` | The 1975–2025 trends page |
| `trends.json` | One set of indicators per year, 1975–2025 |
| `data.json`, `data-2015.json`, `data-2006.json`, `data-1995.json`, `data-1985.json`, `data-1975.json` | Aggregated births by mother's origin × province (2025, 2015, 2006; 1995, 1985 and 1975 by province only) |
| `tfr.json` | Children per woman by group |
| `partos.json` | Babies born alive, died within 24 hours and stillborn, by mother's origin and age (from the deliveries file, by year) |
| `provinces.geo.json` | Simplified province shapes, keyed by INE province code |
| `scripts/` | Scripts that build the files above |

The raw microdata are not included (≈ 25 GB unpacked for every year). Download them from the INE page above, or with `download_ine_mnp.py`, which reads the year links from that page.

## Rebuilding the data

Python 3 only, no extra packages.

```bash
# births: one JSON per year (the script detects the 1975, 1980, 1996 or 2016+ layout from the record length)
python scripts/build_nacimientos_json.py md_MNPnacim_2025.txt data.json
python scripts/build_nacimientos_json.py "Anonimizado Nacimientos sin causa.A2015" data-2015.json
python scripts/build_nacimientos_json.py "NACIMIENTOS 2006" data-2006.json
python scripts/build_nacimientos_json.py NACIA95 data-1995.json
python scripts/build_nacimientos_json.py NACIA85 data-1985.json
python scripts/build_nacimientos_json.py NACIA75 data-1975.json

# children per woman (downloads women by age from INE's API)
python scripts/build_tfr.py tfr.json 2025=data.json 2015=data-2015.json 2006=data-2006.json 1995=data-1995.json 1985=data-1985.json 1975=data-1975.json

# born alive / died within 24 h / stillborn, from the deliveries file (keeps years already in partos.json)
python scripts/build_partos_json.py md_MNPpartos_2025.txt partos.json
python scripts/build_partos_json.py "Anonimizado Partos sin causa.A2015" partos.json
python scripts/build_partos_json.py "PARTOS 2006" partos.json
python scripts/build_partos_json.py PARTOS.A1995.ANONIMI partos.json
python scripts/build_partos_json.py PARTOS.A1985.ANONIMI partos.json

# trends 1975-2025: reads every births and deliveries file in the folder the INE zips were unpacked into,
# and women by age on 1 July of each year from INE's API (about 15 minutes with 3 processes)
python scripts/build_trends.py ../data/nacimientos trends.json
python scripts/build_trends.py ../data/nacimientos trends.json --years 2026   # add one year later on

# map shapes from a GADM level-2 GeoJSON of Spain
python scripts/build_provinces_geo.py gadm41_ESP_2.json provinces.geo.json
```

To view locally, serve the folder (the page loads its JSON files, so opening `index.html` directly won't work):

```bash
python -m http.server 8000   # then open http://localhost:8000
```
