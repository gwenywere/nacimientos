# Nacimientos en España · 1985, 1995, 2006, 2015, 2025

Interactive dashboard of every live birth registered in Spain in 1985, 1995, 2006, 2015 and 2025, built from INE microdata. Filter by year, mother's origin and province of residence.

**Live page:** https://gwenywere.github.io/nacimientos/

## What it shows

- Children per woman (total fertility rate) by mother's country of birth and continent
- Age of mother and father, also by continent of birth
- Birth order, caesarean, preterm and low birth weight by mother's age
- Twins and multiple births by mother's age; complications by mother's age and origin
- Births per day by month; gestation × birth weight
- Boys per 100 girls, by birth order and mother's origin
- Time between the wedding and a married mother's first birth
- Mothers born abroad who hold Spanish nationality, by country of birth (2015, 2025)
- Interactive province map (births, mother's age, caesarean, preterm, mother born abroad, both parents born abroad, mixed couples)
- Mothers' countries of birth, marital status, and couples where the parents come from different countries

## Sources

- **Births:** [INE, Movimiento Natural de la Población — microdata of births](https://ine.es/dyngs/INEbase/es/operacion.htm?c=Estadistica_C&cid=1254736177007&menu=resultados&idp=1254735573002#_tabs-1254736195443). One record per live birth.
- **Women by age and country of birth** (for children per woman): [INE, Estadística Continua de Población, table 56939](https://www.ine.es/jaxiT3/Tabla.htm?t=56939), via INE's public API. For 1985 and 1995, women by age only, from [table 56934](https://www.ine.es/jaxiT3/Tabla.htm?t=56934), since table 56939 starts in 2002.
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

## Files

| File | Contents |
|---|---|
| `index.html` | The page (plain HTML + [D3](https://d3js.org) from a CDN) |
| `data.json`, `data-2015.json`, `data-2006.json`, `data-1995.json`, `data-1985.json` | Aggregated births by mother's origin × province (2025, 2015, 2006; 1995 and 1985 by province only) |
| `tfr.json` | Children per woman by group |
| `provinces.geo.json` | Simplified province shapes, keyed by INE province code |
| `scripts/` | Scripts that build the files above |

The raw microdata are not included (≈ 700 MB). Download them from the INE page above.

## Rebuilding the data

Python 3 only, no extra packages.

```bash
# births: one JSON per year (the script detects the 1980, 1996 or 2016+ layout from the record length)
python scripts/build_nacimientos_json.py md_MNPnacim_2025.txt data.json
python scripts/build_nacimientos_json.py "Anonimizado Nacimientos sin causa.A2015" data-2015.json
python scripts/build_nacimientos_json.py "NACIMIENTOS 2006" data-2006.json
python scripts/build_nacimientos_json.py NACIA95 data-1995.json
python scripts/build_nacimientos_json.py NACIA85 data-1985.json

# children per woman (downloads women by age from INE's API)
python scripts/build_tfr.py tfr.json 2025=data.json 2015=data-2015.json 2006=data-2006.json 1995=data-1995.json 1985=data-1985.json

# map shapes from a GADM level-2 GeoJSON of Spain
python scripts/build_provinces_geo.py gadm41_ESP_2.json provinces.geo.json
```

To view locally, serve the folder (the page loads its JSON files, so opening `index.html` directly won't work):

```bash
python -m http.server 8000   # then open http://localhost:8000
```
