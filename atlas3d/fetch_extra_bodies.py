"""Orbital elements of the bodies in the transfer data that the resource atlas does not list (Pallas, Hygiea, the Trojans and
others), for drawing them in the 3D atlas. Source: JPL Small-Body Database API, full precision, heliocentric ecliptic J2000,
the same source and layout as the atlas entries for Vesta and Psyche. Writes atlas3d/extra_bodies.json. Run on the host:
    python3 atlas3d/fetch_extra_bodies.py
"""
import json, pathlib, re, sys, time, urllib.request
ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from engine.conventions import HELIO

atlas = {b['id'] for b in json.load(open(ROOT / 'atlas' / 'atlas_dataset.json'))['bodies']}
small = json.load(open(ROOT / 'engine' / 'small_bodies.json'))['bodies']
out = []
for k in [h for h in HELIO if h not in atlas]:
    url = f'https://ssd-api.jpl.nasa.gov/sbdb.api?sstr={k}&full-prec=1'
    d = json.load(urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'solmaps-atlas'}), timeout=60))
    el = {e['name']: e['value'] for e in d['orbit']['elements']}
    a, e, i = float(el['a']), float(el['e']), float(el['i'])
    short = small[k]['short']; m = re.match(r'^\d+ \((.+)\)$', short)   # '341843 (2008 EV5)' -> '2008 EV5'
    out.append({'id': k, 'name': m.group(1) if m else short, 'type': 'asteroid', 'parent': 'Sun', 'class': small[k].get('class'),
                'orbit': {'source': url, 'verification': 'fetched', 'table': 'JPL Small-Body Database API (full precision), heliocentric ecliptic J2000',
                          'semi_major_axis_au': a, 'eccentricity': e, 'inclination_deg': i,
                          'elements': {'a_au': a, 'e': e, 'i_deg': i, 'node_deg': float(el['om']), 'arg_peri_deg': float(el['w']),
                                       'M_deg': float(el['ma']), 'epoch_jd_tdb': float(d['orbit']['epoch'])}},
                'note': 'listed for its transfers; the resource atlas has no entry for it'})
    print(k, small[k]['short'], round(a, 3), round(e, 3), round(i, 1)); time.sleep(0.5)
json.dump({'fetched': time.strftime('%Y-%m-%d'), 'bodies': out}, open(ROOT / 'atlas3d' / 'extra_bodies.json', 'w'), indent=1)
print(len(out), 'bodies')
