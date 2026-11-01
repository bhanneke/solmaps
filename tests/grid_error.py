"""How far the daily data's cheapest transfer lies above the true single-revolution optimum (probe, not a test).

For random route-dates: scan 3,000 log-spaced flight times over the same range (every number of revolutions), refine the best by golden-section
search, and compare with the cheapest stored alternative (own end states). Run in the container after engine.daily:
    python tests/grid_error.py [samples]
"""
import math, random, sys
sys.path.insert(0, '/work/flyby'); sys.path.insert(0, '/work')
import numpy as np, pykep as pk, bodies
from engine import daily
from engine.conventions import planet_side_dv, HELIO

def main(n=300):
    atlas = bodies.load_atlas(); random.seed(5); excess = []
    for _ in range(n):
        a = random.choice(HELIO); f = np.load(f'/work/data/daily/{a}.npz')
        i = random.randrange(len(f['targets'])); b = str(f['targets'][i]); k = random.randrange(27089)
        T, V = f['tof'][i, k], f['vinf'][i, k].astype(float)
        stored = min((planet_side_dv(a, v[0]) + planet_side_dv(b, v[1]) for t, v in zip(T, V) if t == t), default=math.inf)
        A, B = bodies.body(a, atlas), bodies.body(b, atlas); end = bodies.coverage_end(b)
        t0 = 2461345.5 + k - 2451544.5; ra, va = A.eph(t0)
        def cost(t):
            if t0 + t > end:
                return math.inf
            rb, vb = B.eph(t0 + t)
            try:
                l = pk.lambert_problem(r0=ra, r1=rb, tof=t * 86400, mu=pk.MU_SUN, multi_revs=daily.MAX_REVS)
            except Exception:
                return math.inf
            return min(planet_side_dv(a, math.dist(w0, va) / 1000) + planet_side_dv(b, math.dist(w1, vb) / 1000)
                       for w0, w1 in zip(l.v0, l.v1))                  # every number of revolutions, as in engine/daily.py
        g = daily.tof_grid(daily.semi_major_axis(a), daily.semi_major_axis(b))
        ts = np.geomspace(g[0], g[-1], 3000); cs = [cost(t) for t in ts]; j = int(np.argmin(cs))
        lo, hi = ts[max(j - 1, 0)], ts[min(j + 1, len(ts) - 1)]
        for _ in range(40):                                   # golden-section refinement
            m1, m2 = hi - 0.618 * (hi - lo), lo + 0.618 * (hi - lo)
            if cost(m1) < cost(m2):
                hi = m2
            else:
                lo = m1
        best = min(cs[j], cost((lo + hi) / 2))
        if math.isfinite(best) and math.isfinite(stored):
            excess.append(stored - best)
    e = np.array(excess)
    print(f'{len(e)} route-dates: stored cheapest minus fine-scan optimum, km/s')
    for q in (50, 90, 95, 99):
        print(f'  {q}th percentile {np.percentile(e, q):.4f}')
    print(f'  largest {e.max():.3f}; share within 0.05 km/s {np.mean(e <= 0.05) * 100:.1f}%; within 0.5 km/s {np.mean(e <= 0.5) * 100:.1f}%')

if __name__ == '__main__':
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 300)
