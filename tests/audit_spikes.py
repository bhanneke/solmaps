"""Route-days more than 0.5 km/s above both neighbours, and how much of the spike a scan of 20,000 flight times closes on 50 of them.
Run in the container from /work: python tests/audit_spikes.py
"""
import math, sys, random
sys.path.insert(0, '/work/flyby'); sys.path.insert(0, '/work')
import numpy as np, pykep as pk, bodies
from engine import daily
from engine.repair_daily import closest_to_sun, R_SUN
from engine.conventions import HELIO, planet_side_arr, planet_side_dv
atlas = bodies.load_atlas()
def cost(a, b, T, V):
    T, V = T.astype(float), V.astype(float); return np.where(np.isnan(T), np.inf, planet_side_arr(a, V[..., 0])[0] + planet_side_arr(b, V[..., 1])[0])
sp = []; cnt = {}
for a in HELIO:
    f = np.load(f'/work/data/daily/{a}.npz')
    for i, b in enumerate(f['targets']):
        b = str(b); m = cost(a, b, f['tof'][i], f['vinf'][i]).min(1); h = np.minimum(m[1:-1] - m[:-2], m[1:-1] - m[2:]); h[~np.isfinite(h)] = 0
        for d in np.flatnonzero(h > 0.5):
            sp.append((float(h[d]), a, b, int(d) + 1, float(m[d + 1])))
sp.sort(reverse=True); print('spike days >0.5:', len(sp), 'routes', len({(s[1], s[2]) for s in sp}))
random.seed(5); pick = sp[:25] + random.sample(sp[25:], 25); low = []
for h, a, b, d, m in pick:
    A, B = bodies.body(a, atlas), bodies.body(b, atlas); t0 = daily.JD0 + d - 2451544.5; ra, va = A.eph(t0); end = bodies.coverage_end(b); g = daily.tof_grid(daily.semi_major_axis(a), daily.semi_major_axis(b)); best = math.inf
    for x in np.geomspace(g[0], daily.TOF_MAX, 20000):
        if t0 + x > end:
            continue
        rb, vb = B.eph(t0 + x)
        try:
            l = pk.lambert_problem(r0=ra, r1=rb, tof=x * 86400, mu=pk.MU_SUN, multi_revs=daily.MAX_REVS)
        except Exception:
            continue
        for q, (w0, w1) in enumerate(zip(l.v0, l.v1)):
            c = planet_side_dv(a, math.dist(w0, va) / 1000) + planet_side_dv(b, math.dist(w1, vb) / 1000)
            if c < best and closest_to_sun(ra, w0, rb, w1, pk.MU_SUN, (q + 1) // 2) > R_SUN:
                best = c
    low.append((m - best, h))
e = np.array([x[0] for x in low]); hs = np.array([x[1] for x in low]); print(f'{len(e)} spike days, 20,000-point scan: stored minus scan: median {np.median(e):.4f}, max {e.max():.3f}; scan closes more than half of the spike on {(e > hs / 2).sum()}')
print('largest spikes', [(round(s[0], 2), s[1], s[2]) for s in sp[:6]])
