"""Repair pass over the daily transfer data (engine/daily.py): neighbouring days' flight times and the Sun.

Cost valleys of long flights are narrow and move smoothly from day to day, so a fixed grid of flight times misses one on
single days: 1,210 route-days sat more than 2 km/s above both neighbours. Per route and day the pass solves
  - the flight times stored for that day,
  - the flight times stored for the days up to WINDOW away, both unchanged and shifted to the same arrival date,
  - flight times just around the day's cheapest options,
keeps the cheapest solution over all revolutions at each flight time, and thins the Pareto front as engine/daily.py does.
Solutions whose arc passes inside the Sun are left out. Every kept option records its closest approach to the Sun.
PASSES rounds carry a good flight time further along the route. Output per origin: as engine/daily.py plus
  sun_au [n, date, K]   closest distance to the Sun on the arc, AU (float32)

Run: python -m engine.repair_daily OUT_FOLDER [procs] [origin ...]   (in the solmaps-env container, from /work)
Then: python -m engine.repair_daily final REPAIRED_FOLDER OUT_FOLDER [procs]   (every option solved at its stored flight time)
"""
import math, os, sys, time
from multiprocessing import Pool
sys.path.insert(0, '/work/flyby'); sys.path.insert(0, '/work')
import numpy as np

from engine import daily
from engine.conventions import HELIO, planet_side_dv

SPIKE, SCAN = 0.5, 4000                                      # the last stage: km/s above both neighbours, flight times scanned
WINDOW, PASSES, REFINE, R_SUN = 2, 2, 3, 6.957e8            # days either side, rounds, options refined per day, solar radius in metres
SRC = os.environ.get('REPAIR_SRC', daily.OUT)

def closest_to_sun(r1, v1, r2, v2, mu, revs):
    """closest distance to the Sun on an arc, metres: the perihelion if the arc passes it, else the nearer end"""
    n1, n2 = math.hypot(*r1), math.hypot(*r2)
    rv1 = r1[0] * v1[0] + r1[1] * v1[1] + r1[2] * v1[2]; rv2 = r2[0] * v2[0] + r2[1] * v2[1] + r2[2] * v2[2]
    if not (revs > 0 or (rv1 < 0 and rv2 > 0)):
        return min(n1, n2)
    hx, hy, hz = r1[1] * v1[2] - r1[2] * v1[1], r1[2] * v1[0] - r1[0] * v1[2], r1[0] * v1[1] - r1[1] * v1[0]
    h2 = hx * hx + hy * hy + hz * hz
    en = (v1[0] * v1[0] + v1[1] * v1[1] + v1[2] * v1[2]) / 2 - mu / n1
    return (h2 / mu) / (1 + math.sqrt(max(0.0, 1 + 2 * en * h2 / (mu * mu))))

def repair_route(args):
    import pykep as pk, bodies
    a, b, T0, V0, R0 = args
    atlas = bodies.load_atlas(); A, B = bodies.body(a, atlas), bodies.body(b, atlas); end_b = bodies.coverage_end(b)
    classic = daily.tof_grid(daily.semi_major_axis(a), daily.semi_major_axis(b))[daily.NTOF - 1]
    n, K = T0.shape; T = T0.astype(np.float64); dates = daily.JD0 + np.arange(n); out = None; dropped = 0
    for _ in range(PASSES):
        tof, vinf, revs, sun = np.full((n, K), np.nan, np.float32), np.full((n, K, 2), np.nan, np.float32), np.zeros((n, K), np.uint16), np.full((n, K), np.nan, np.float32)
        for d in range(n):
            t0 = dates[d] - 2451544.5; ra, va = A.eph(t0)
            Ts, cost, vd, vr, NR, S = [], [], [], [], [], []; seen = set()
            def solve(x):
                nonlocal dropped
                if x in seen or x <= 0 or t0 + x > end_b:
                    return
                seen.add(x); rb, vb = B.eph(t0 + x)
                try:
                    l = pk.lambert_problem(r0=ra, r1=rb, tof=x * 86400.0, mu=pk.MU_SUN, multi_revs=daily.MAX_REVS)
                except Exception:
                    return
                best = None
                for q, (w0, w1) in enumerate(zip(l.v0, l.v1)):
                    dd = math.dist(w0, va) / 1000; rr = math.dist(w1, vb) / 1000; c = planet_side_dv(a, dd) + planet_side_dv(b, rr)
                    if best is not None and c >= best[2]:
                        continue
                    rm = closest_to_sun(ra, w0, rb, w1, pk.MU_SUN, (q + 1) // 2)
                    if rm <= R_SUN:                                             # through the Sun: no flight
                        dropped += 1; continue
                    best = (dd, rr, c, (q + 1) // 2, rm)
                if best:
                    Ts.append(x); vd.append(best[0]); vr.append(best[1]); cost.append(best[2]); NR.append(best[3]); S.append(best[4])
            for e in range(max(0, d - WINDOW), min(n, d + WINDOW + 1)):
                for t in T[e][~np.isnan(T[e])]:
                    solve(float(t))                                             # the same flight time
                    if e != d:
                        solve(float(t) + (e - d))                               # the same arrival date
            if not Ts:
                continue
            for q in np.argsort(cost)[:REFINE]:                                 # around the cheapest: the valley can be days wide
                x0 = Ts[q]
                for f in (0.003, 0.001, 0.0003):
                    solve(x0 * (1 - f)); solve(x0 * (1 + f))
            for i, p in enumerate(daily.pareto_thin(np.array(Ts), np.array(cost), vd, vr, classic=classic)):
                tof[d, i] = Ts[p]; vinf[d, i, 0] = vd[p]; vinf[d, i, 1] = vr[p]; revs[d, i] = NR[p]; sun[d, i] = S[p] / pk.AU
        T = tof.astype(np.float64); out = (tof, vinf, revs, sun)
    return (a, b, *out, dropped)

def final_route(args):
    """the last stage: every option solved again at exactly its stored 32-bit flight time, so the file reproduces itself. The
    cost can jump by kilometres per second within a thousandth of a day where a solution with one more revolution first
    exists, so a value solved at an unrounded time need not hold at the stored one. Flights stay within 100 years, and days
    more than SPIKE km/s above both neighbours also get a scan of SCAN flight times and those of the days around them."""
    import pykep as pk, bodies
    from engine.conventions import planet_side_arr
    a, b, T0, V0 = args
    atlas = bodies.load_atlas(); A, B = bodies.body(a, atlas), bodies.body(b, atlas); end_b = bodies.coverage_end(b)
    g = daily.tof_grid(daily.semi_major_axis(a), daily.semi_major_axis(b)); classic = g[daily.NTOF - 1]; scan = np.float32(np.geomspace(g[0], daily.TOF_MAX, SCAN))
    n, K = T0.shape; C = np.where(np.isnan(T0), np.inf, planet_side_arr(a, V0[..., 0].astype(float))[0] + planet_side_arr(b, V0[..., 1].astype(float))[0]); m = C.min(1)
    spike = np.zeros(n, bool); spike[1:-1] = (m[1:-1] > m[:-2] + SPIKE) & (m[1:-1] > m[2:] + SPIKE)
    tof, vinf, revs, sun = np.full((n, K), np.nan, np.float32), np.full((n, K, 2), np.nan, np.float32), np.zeros((n, K), np.uint16), np.full((n, K), np.nan, np.float32)
    for d in range(n):
        cand = T0[d][~np.isnan(T0[d])]
        if spike[d]:
            near = T0[max(0, d - 7):min(n, d + 8)]; cand = np.concatenate([cand, near[~np.isnan(near)], scan])
        t0 = daily.JD0 + d - 2451544.5; ra, va = A.eph(t0)
        Ts, cost, vd, vr, NR, S = [], [], [], [], [], []
        for x in sorted(set(float(v) for v in cand)):               # 32-bit values, exactly as stored
            if x <= 0 or x > daily.TOF_MAX or t0 + x > end_b:
                continue
            rb, vb = B.eph(t0 + x)
            try:
                l = pk.lambert_problem(r0=ra, r1=rb, tof=x * 86400.0, mu=pk.MU_SUN, multi_revs=daily.MAX_REVS)
            except Exception:
                continue
            best = None
            for q, (w0, w1) in enumerate(zip(l.v0, l.v1)):
                dd = math.dist(w0, va) / 1000; rr = math.dist(w1, vb) / 1000; c = planet_side_dv(a, dd) + planet_side_dv(b, rr)
                if best is not None and c >= best[2]:
                    continue
                rm = closest_to_sun(ra, w0, rb, w1, pk.MU_SUN, (q + 1) // 2)
                if rm > R_SUN:
                    best = (dd, rr, c, (q + 1) // 2, rm)
            if best:
                Ts.append(x); vd.append(best[0]); vr.append(best[1]); cost.append(best[2]); NR.append(best[3]); S.append(best[4])
        if Ts:
            for i, p in enumerate(daily.pareto_thin(np.array(Ts), np.array(cost), vd, vr, classic=classic)):
                tof[d, i] = Ts[p]; vinf[d, i, 0] = vd[p]; vinf[d, i, 1] = vr[p]; revs[d, i] = NR[p]; sun[d, i] = S[p] / pk.AU
    return (a, b, tof, vinf, revs, sun, int(spike.sum()))

def main_final(src, out, procs=6):
    os.makedirs(out, exist_ok=True); t = time.time()
    for a in HELIO:
        if os.path.exists(f'{out}/{a}.npz'):
            continue
        d = np.load(f'{src}/{a}.npz'); targets = [str(x) for x in d['targets']]
        with Pool(procs, maxtasksperchild=4) as p:
            res = {r[1]: r for r in p.imap_unordered(final_route, [(a, b, d['tof'][i], d['vinf'][i]) for i, b in enumerate(targets)])}
        np.savez_compressed(f'{out}/{a}.tmp.npz', targets=np.array(targets), jd0=daily.JD0, step=1.0, k=daily.K,
                            tof=np.stack([res[x][2] for x in targets]), vinf=np.stack([res[x][3] for x in targets]),
                            revs=np.stack([res[x][4] for x in targets]), sun_au=np.stack([res[x][5] for x in targets]))
        os.replace(f'{out}/{a}.tmp.npz', f'{out}/{a}.npz')
        print(f'{a} done, {time.time() - t:.0f} s, spike days scanned {sum(r[6] for r in res.values())}', flush=True)

def main(out, procs=8, origins=None):
    os.makedirs(out, exist_ok=True); t = time.time()
    for a in origins or HELIO:
        if os.path.exists(f'{out}/{a}.npz'):
            continue
        d = np.load(f'{SRC}/{a}.npz'); targets = [str(x) for x in d['targets']]
        jobs = [(a, b, d['tof'][i], d['vinf'][i], d['revs'][i]) for i, b in enumerate(targets)]
        with Pool(procs, maxtasksperchild=4) as p:              # workers restart, so memory stays low
            res = {r[1]: r for r in p.imap_unordered(repair_route, jobs)}
        np.savez_compressed(f'{out}/{a}.tmp.npz', targets=np.array(targets), jd0=daily.JD0, step=1.0, k=daily.K,
                            tof=np.stack([res[x][2] for x in targets]), vinf=np.stack([res[x][3] for x in targets]),
                            revs=np.stack([res[x][4] for x in targets]), sun_au=np.stack([res[x][5] for x in targets]))
        os.replace(f'{out}/{a}.tmp.npz', f'{out}/{a}.npz')
        print(f'{a} done, {time.time() - t:.0f} s, solutions through the Sun left out {sum(r[6] for r in res.values())}', flush=True)

if __name__ == '__main__':
    x = sys.argv[1:]
    if x[0] == 'final':                                     # python -m engine.repair_daily final REPAIRED_FOLDER OUT_FOLDER [procs]
        main_final(x[1], x[2], int(x[3]) if len(x) > 3 else 6)
    else:
        main(x[0], int(x[1]) if len(x) > 1 else 8, x[2:] or None)
