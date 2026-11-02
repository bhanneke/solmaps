# Release audit: the routes whose cheapest transfer undercuts the single-revolution data by more than 0.3 km/s (bodies on
# nearly the same orbit). For each route the cheapest record over all days and six random days: recompute the Lambert
# solution, match the stored speeds, and integrate the departure state independently (scipy DOP853) to the arrival date.
# Run in the container from /work after tests/audit_daily.py: python tests/audit_cheap_routes.py
import sys, math, random
sys.path.insert(0, '/work/flyby'); sys.path.insert(0, '/work')
import numpy as np, pykep as pk, bodies
from scipy.integrate import solve_ivp
from engine.conventions import planet_side_arr
atlas = bodies.load_atlas(); MU = pk.MU_SUN
def f(t, y):
    r = y[:3]; return np.concatenate([y[3:], -MU * r / np.linalg.norm(r) ** 3])
random.seed(4)
import json
routes = [(x['origin'], x['target']) for x in json.load(open('/work/data/daily/audit.json'))['routes'] if x['below_floor_days'] > 0]
results = []
for a, b in routes:
    F = np.load(f'/work/data/daily/{a}.npz'); i = list(F['targets']).index(b)
    T, V, R = F['tof'][i].astype(float), F['vinf'][i].astype(float), F['revs'][i]
    c = np.where(np.isnan(T), np.inf, planet_side_arr(a, V[..., 0])[0] + planet_side_arr(b, V[..., 1])[0])
    A, B = bodies.body(a, atlas), bodies.body(b, atlas)
    dmin = int(np.unravel_index(np.argmin(c), c.shape)[0])
    for d in [dmin] + [random.randrange(27089) for _ in range(6)]:
        j = int(np.argmin(c[d]))
        if not np.isfinite(c[d, j]):
            continue
        t0 = 2461345.5 + d - 2451544.5; tof = T[d, j]
        ra, va = A.eph(t0); rb, vb = B.eph(t0 + tof)
        l = pk.lambert_problem(r0=ra, r1=rb, tof=tof * 86400, mu=MU, multi_revs=10000)
        sols = [(math.dist(w0, va) / 1000, math.dist(w1, vb) / 1000, w0, q) for q, (w0, w1) in enumerate(zip(l.v0, l.v1))]
        s = min(sols, key=lambda s: abs(s[0] - V[d, j, 0]) + abs(s[1] - V[d, j, 1]))
        match = abs(s[0] - V[d, j, 0]) + abs(s[1] - V[d, j, 1])
        y = solve_ivp(f, (0, tof * 86400), np.concatenate([ra, s[2]]), method='DOP853', rtol=1e-12, atol=1e-3).y[:, -1]
        miss = np.linalg.norm(y[:3] - np.array(rb)) / 1000
        results.append((a, b, tof / 365.25, R[d, j], c[d, j], match, miss))
r = np.array([x[2:] for x in results], float)
print(f'{len(results)} cheapest records on the {len(routes)} routes: flights {r[:, 0].min():.1f}-{r[:, 0].max():.1f} years, '
      f'revolutions up to {int(r[:, 1].max())}, costs {r[:, 2].min():.2f}-{r[:, 2].max():.2f} km/s')
print(f'stored speeds match a recomputed solution within: median {np.median(r[:, 3]):.4f}, max {r[:, 3].max():.4f} km/s')
print(f'independent integration reaches the target within: median {np.median(r[:, 4]):.1f} km, max {r[:, 4].max():.1f} km '
      f'(max relative to path length {np.max(r[:, 4] / (r[:, 0] * 365.25 * 86400 * 15)):.1e})')
