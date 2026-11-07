"""Why a route-day came out dearer than in the first run: the old cheapest option lay at the 100-year end, passed through the Sun, or neither.
Run in the container from /work with the first run mounted at /before and the final data at /after: python tests/audit_dearer.py
"""
# Why is a route-day dearer in the final data than in the first run? The old cheapest option: beyond the limit or at it, through the Sun, or neither.
import math, sys, json
sys.path.insert(0, '/work/flyby'); sys.path.insert(0, '/work')
import numpy as np, pykep as pk, bodies
from engine import daily
from engine.repair_daily import closest_to_sun, R_SUN
from engine.conventions import HELIO, planet_side_arr
atlas = bodies.load_atlas()
def cost(a, b, T, V):
    T, V = T.astype(float), V.astype(float); return np.where(np.isnan(T), np.inf, planet_side_arr(a, V[..., 0])[0] + planet_side_arr(b, V[..., 1])[0])
rows = []
for a in HELIO:
    o, n = np.load(f'/before/{a}.npz'), np.load(f'/after/{a}.npz')
    for i, b in enumerate(n['targets']):
        b = str(b); c0, c1 = cost(a, b, o['tof'][i], o['vinf'][i]), cost(a, b, n['tof'][i], n['vinf'][i]); m0, m1 = c0.min(1), c1.min(1)
        for d in np.flatnonzero(np.isfinite(m0) & np.isfinite(m1) & (m1 > m0 + 1e-3)):
            j = int(c0[d].argmin()); rows.append((float(m1[d] - m0[d]), a, b, int(d), float(o['tof'][i, d, j]), o['vinf'][i, d, j].astype(float), int(o['revs'][i, d, j])))
print(len(rows), 'dearer route-days'); g = np.array([r[0] for r in rows])
print(f'size km/s: median {np.median(g):.4f}, 90% {np.percentile(g, 90):.3f}, 99% {np.percentile(g, 99):.3f}, max {g.max():.3f}; over 0.01 {(g > .01).sum()}, over 0.1 {(g > .1).sum()}, over 1 {(g > 1).sum()}')
lim = [r for r in rows if r[4] >= daily.TOF_MAX * 0.995]; rest = [r for r in rows if r[4] < daily.TOF_MAX * 0.995]; print('old option at the 100-year end of the grid:', len(lim))
random_rest = rest; sun = 0; other = []
for gap, a, b, d, T, V, R in random_rest:
    A, B = bodies.body(a, atlas), bodies.body(b, atlas); t0 = daily.JD0 + d - 2451544.5; ra, va = A.eph(t0); rb, vb = B.eph(t0 + T)
    l = pk.lambert_problem(r0=ra, r1=rb, tof=T * 86400, mu=pk.MU_SUN, multi_revs=10000)
    q = min(range(len(l.v0)), key=lambda q: abs(math.dist(l.v0[q], va) / 1000 - V[0]) + abs(math.dist(l.v1[q], vb) / 1000 - V[1]))
    if closest_to_sun(ra, l.v0[q], rb, l.v1[q], pk.MU_SUN, (q + 1) // 2) <= R_SUN:
        sun += 1
    else:
        other.append((round(gap, 3), a, b, d, round(T, 1)))
print('old option through the Sun:', sun); print('neither:', len(other), 'of which over 0.1 km/s:', sum(1 for x in other if x[0] > .1)); print('largest:', sorted(other, reverse=True)[:10])
