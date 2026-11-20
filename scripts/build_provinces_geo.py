"""Simplify a province GeoJSON for the web map (provinces.geo.json).

Input: a GeoJSON of Spain's 52 provinces whose properties include the INE province
code in `CC_2` (GADM level 2 has this). Output: MultiPolygons with feature id = INE
code, Douglas-Peucker simplified, coordinates rounded to 3 decimals, islets under
~40 km2 dropped (Ceuta and Melilla kept in full detail).

Usage:
    python build_provinces_geo.py provinces_input.json provinces.geo.json
"""
import json
import sys


def simplify(pts, tol):
    """Douglas-Peucker on a list of [x, y]."""
    if len(pts) < 3:
        return pts
    keep = [False] * len(pts)
    keep[0] = keep[-1] = True
    stack = [(0, len(pts) - 1)]
    while stack:
        a, b = stack.pop()
        ax, ay = pts[a]
        bx, by = pts[b]
        dx, dy = bx - ax, by - ay
        length2 = (dx * dx + dy * dy) or 1e-18
        best, best_i = -1, None
        for i in range(a + 1, b):
            px, py = pts[i]
            t = max(0, min(1, ((px - ax) * dx + (py - ay) * dy) / length2))
            qx, qy = ax + t * dx - px, ay + t * dy - py
            d = qx * qx + qy * qy
            if d > best:
                best, best_i = d, i
        if best_i is not None and best > tol * tol:
            keep[best_i] = True
            stack += [(a, best_i), (best_i, b)]
    return [p for p, k in zip(pts, keep) if k]


def area(ring):
    return abs(sum(ring[i][0] * ring[i - 1][1] - ring[i - 1][0] * ring[i][1] for i in range(len(ring)))) / 2


def main():
    src, out = sys.argv[1], sys.argv[2]
    features = []
    for f in json.load(open(src, encoding='utf-8'))['features']:
        code = f['properties']['CC_2']
        tiny = code in ('51', '52')  # Ceuta, Melilla
        g = f['geometry']
        polys = g['coordinates'] if g['type'] == 'MultiPolygon' else [g['coordinates']]
        tol = 0.002 if tiny else 0.012
        kept = []
        for poly in polys:
            if not tiny and area(poly[0]) < 0.004:
                continue
            rings = []
            for i, ring in enumerate(poly):
                s = [[round(x, 3), round(y, 3)] for x, y in simplify(ring, tol)]
                if len(s) >= 4 and (i == 0 or area(s) > 0.004):
                    rings.append(s)
            if rings:
                kept.append(rings)
        features.append({'type': 'Feature', 'id': code, 'properties': {}, 'geometry': {'type': 'MultiPolygon', 'coordinates': kept}})
    json.dump({'type': 'FeatureCollection', 'features': features}, open(out, 'w'), separators=(',', ':'))
    print(f'{out}: {len(features)} provinces')


if __name__ == '__main__':
    main()
