"""How far the planets bend the two-body arcs of the daily data: sampled arcs integrated with the Sun and eight planets, no correction burns.
The origin stays off for the first 30 days and the target for the last 30 (the patched conic covers those phases); softening 10,000 km.
Prints the miss at arrival and the arrival velocity shift. Run in the container from /work: python tests/audit_nbody.py
"""
import sys, math, time
sys.path.insert(0, '/work/flyby'); sys.path.insert(0, '/work')
import numpy as np, pykep as pk, bodies
from scipy.integrate import solve_ivp
from engine.conventions import planet_side_arr
from engine import daily
D = '/work/data/daily'; J0 = 2461345.5; atlas = bodies.load_atlas(); MU = pk.MU_SUN; AU = pk.AU
GM = {'venus': 3.24859e14, 'earth': 4.03503e14, 'mars': 4.2828e13, 'jupiter': 1.26712e17, 'saturn': 3.79406e16, 'uranus': 5.7945e15, 'neptune': 6.8365e15}
pl = {n: bodies.body(n, atlas) for n in GM}
EPS2 = (1e7) ** 2; LIMIT = 90.0
class Stop(Exception):
    pass
def pick(a, b, maxy=None):
    f = np.load(f'{D}/{a}.npz'); i = [str(x) for x in f['targets']].index(b); T = f['tof'][i].astype(float); V = f['vinf'][i].astype(float)
    c = np.where(np.isnan(T), np.inf, planet_side_arr(a, V[..., 0])[0] + planet_side_arr(b, V[..., 1])[0])
    if maxy:
        c = np.where(T > maxy * 365.25, np.inf, c)
    d, k = np.unravel_index(np.argmin(c), c.shape)
    return int(d), T[d, k], V[d, k], int(f['revs'][i, d, k]), float(c[d, k])
for a, b, maxy in [('earth', 'jupiter', 4), ('earth', 'saturn', 7), ('earth', 'mars', 10), ('earth', 'mars', None), ('10', '24', None), ('earth', 'jupiter', None)]:
    d, tof, v, rev, cost = pick(a, b, maxy); A, B = bodies.body(a, atlas), bodies.body(b, atlas); t0 = J0 + d - 2451544.5
    ra, va = A.eph(t0); rb, vb = B.eph(t0 + tof); Tt = tof * 86400
    l = pk.lambert_problem(r0=ra, r1=rb, tof=Tt, mu=MU, multi_revs=10000)
    w0, w1 = min(zip(l.v0, l.v1), key=lambda s: abs(math.dist(s[0], va) / 1000 - v[0]) + abs(math.dist(s[1], vb) / 1000 - v[1]))
    start = time.time(); best = {n: math.inf for n in GM}
    def rhs(t, y):
        if time.time() - start > LIMIT:
            raise Stop(f't={t/86400/365.25:.1f}y')
        r = y[:3]; acc = -MU * r / np.linalg.norm(r) ** 3; tt = t0 + t / 86400
        for n, p in pl.items():
            if (n == a and t < 30 * 86400) or (n == b and t > Tt - 30 * 86400):
                continue
            s = np.array(p.eph(tt)[0]); dd = s - r; d2 = dd @ dd
            best[n] = min(best[n], d2)
            acc = acc + GM[n] * (dd / (d2 + EPS2) ** 1.5 - s / np.linalg.norm(s) ** 3)
        if not np.all(np.isfinite(acc)):
            raise Stop('NaN')
        return np.concatenate([y[3:], acc])
    tag = f'{a}>{b} limit {maxy}y dep day {d} tof {tof/365.25:.2f}y revs {rev} cost {cost:.2f} vinf {v[0]:.2f}/{v[1]:.2f}'
    try:
        s = solve_ivp(rhs, (0, Tt), np.concatenate([ra, w0]), method='DOP853', rtol=1e-9, atol=1.0, max_step=5 * 86400.0)
        miss = np.linalg.norm(s.y[:3, -1] - np.array(rb)) / 1000
        dv = np.linalg.norm(s.y[3:, -1] - np.array(w1)) / 1000
        print(f'{tag}: miss {miss:,.0f} km ({miss/(AU/1000):.3f} AU), arrival velocity shift {dv:.3f} km/s, closest pass seen at solver steps (million km) ' +
              str({n: round(math.sqrt(x) / 1e9, 2) for n, x in best.items()}) + f', {time.time()-start:.0f}s', flush=True)
    except Stop as e:
        print(f'{tag}: STOPPED at {e}, closest so far {({n: round(math.sqrt(x)/1e9,2) for n,x in best.items()})}', flush=True)
