"""DE440 against the Horizons (DE441) planet files, at whole and half days, in the overlap before 2149.
Run in the container from /work: python tests/audit_join.py
"""
# DE440 against the Horizons (DE441) planet files, at whole days and half days, in the overlap before 2149.
import json, sys
sys.path.insert(0, '/work/flyby'); sys.path.insert(0, '/work')
import numpy as np, pykep as pk, bodies
atlas = bodies.load_atlas()
for n in ('mercury', 'venus', 'earth', 'mars', 'jupiter', 'saturn', 'uranus', 'neptune', 'pluto'):
    P = bodies.DE440Planet(n) if hasattr(bodies, 'DE440Planet') else None
    r = np.asarray(json.load(open(f'/work/flyby/horizons/planet_{n}.json'))['rows'], float); t0, t1 = r[0, 0] - 2451544.5, r[-1, 0] - 2451544.5; h = r[1, 0] - r[0, 0]
    H = bodies.HorizonsBody(f'planet_{n}'); A = bodies.body(n, atlas); top = 54750.0
    days = np.arange(max(t0, 54750 - 3650), min(top, t1), 37.0)
    def gap(ts):
        return [np.linalg.norm(np.array(P.eph(float(t))[0]) - np.array(H.eph(float(t))[0])) for t in ts]
    w, m = gap(days), gap(days + 0.5)
    print(f'{n:8s} files from JD {r[0,0]:.1f} to {r[-1,0]:.1f}, step {h} d; whole days: median {np.median(w):.1f} m, max {max(w):.1f} m; half days: median {np.median(m):.1f} m, max {max(m):.1f} m', flush=True)
