"""Catalogue screening (tier B): every object of the JPL Small-Body Database against the hubs, both directions.

For each bound object of data/sbdb/catalog.npz and each hub (Earth, Mars, Ceres, with their parking-orbit end states;
the object end is a rendezvous), the screening solves Lambert's problem (pykep, single revolution, prograde) for every
10th day from 2026-11-01 to 2100 and 20 flight times, and keeps per hub and direction the cheapest transfer overall and
the cheapest per calendar year of departure.

Positions: hubs from DE440 and JPL Horizons (flyby/bodies.py); objects by two-body propagation of their SBDB elements
(osculating at the catalogue epoch, 2026). Two-body motion ignores the planets' pull and drifts over decades, so the
screening ranks objects; the full sites (engine/daily.py, daily Horizons states) give numbers for planning.
Flight times: 20 values from 0.3 to 2.5 Hohmann times (at least 30 days, at most 30 years), rounded to multiples of
10 days so that arrivals fall on the date grid and every position is computed once.

Work units of UNIT objects (near-Earth objects first, then by absolute magnitude, brightest first), one file each in
data/screen/, resumable. Run: python -m engine.screen [workers] [first_unit] [last_unit]   (in the container, from /work)
"""
import json, math, os, sys, time
from multiprocessing import Pool
sys.path.insert(0, '/work/flyby'); sys.path.insert(0, '/work')
import numpy as np

from engine.conventions import planet_side_arr

JD0, STEP, N_DEP = 2461345.5, 10.0, 2709                # departures 2026-11-01 to 2100-12-31, every 10 days
TOF_MAX_STEPS = int(30 * 365.25 // STEP)                # flights up to 30 years
N_T = N_DEP + TOF_MAX_STEPS + 1
HUBS = ['earth', 'mars', 'ceres']
NTOF, UNIT = 20, 2000
K_GAUSS = 0.01720209895                                 # AU^1.5/day
AU_M, DAY_S, MU_SUN = 149597870700.0, 86400.0, 1.32712440018e20
OUT = '/work/data/screen'
YEAR0 = 2026
YEARS = 2100 - YEAR0 + 1

def year_of_steps():
    jd = JD0 + STEP * np.arange(N_DEP)
    return np.floor((jd - 2451544.5) / 365.25 + 2000.0).astype(int) - YEAR0   # calendar year (approximate at the edges)

def two_body_states(el, jd):
    """heliocentric ecliptic position (m) and velocity (m/s) of each object at the times jd: [n, t, 3] each"""
    a, e, i, om, w, ma, ep = (el[k][:, None] for k in ('a', 'e', 'i', 'om', 'w', 'ma', 'epoch'))
    n_mot = K_GAUSS * a ** -1.5                          # rad/day
    M = np.radians(ma) + n_mot * (jd[None, :] - ep)
    E = M.copy()
    for _ in range(30):
        E -= (E - e * np.sin(E) - M) / (1 - e * np.cos(E))
    cE, sE = np.cos(E), np.sin(E)
    b = a * np.sqrt(1 - e * e)
    xp, yp = a * (cE - e), b * sE                       # perifocal position (AU)
    rr = a * (1 - e * cE)
    vxp, vyp = -a * n_mot * sE / (1 - e * cE), b * n_mot * cE / (1 - e * cE)   # AU/day
    I, O, W = np.radians(i), np.radians(om), np.radians(w)
    cO, sO, cI, sI, cW, sW = np.cos(O), np.sin(O), np.cos(I), np.sin(I), np.cos(W), np.sin(W)
    P = np.stack([cO * cW - sO * sW * cI, sO * cW + cO * sW * cI, sW * sI], -1)
    Q = np.stack([-cO * sW - sO * cW * cI, -sO * sW + cO * cW * cI, cW * sI], -1)
    r = (xp[..., None] * P + yp[..., None] * Q) * AU_M
    v = (vxp[..., None] * P + vyp[..., None] * Q) * AU_M / DAY_S
    return r, v

def hub_states():
    import bodies
    atlas = bodies.load_atlas()
    jd = JD0 + STEP * np.arange(N_T)
    out = np.zeros((len(HUBS), N_T, 6))
    for h, name in enumerate(HUBS):
        B = bodies.body(name, atlas)
        for k, t in enumerate(jd - 2451544.5):
            r, v = B.eph(float(t))
            out[h, k, :3], out[h, k, 3:] = r, v
    return out

HUB_A = {'earth': 1.0, 'mars': 1.524, 'ceres': 2.767}
_HUB = None
def _init(hub):
    global _HUB
    _HUB = hub

def tof_steps(a_obj, a_hub):
    tH = math.pi * math.sqrt(((a_obj + a_hub) / 2) ** 3 / 2.9591220828e-4)
    lo, hi = max(30.0, 0.3 * tH), min(30 * 365.25, 2.5 * tH)
    steps = np.unique(np.round(np.geomspace(lo, hi, NTOF) / STEP).astype(int))
    return steps[steps >= 3]

def unit(args):
    """screen one work unit: returns the path written"""
    import pykep as pk
    idx, el, spkid = args
    path = f'{OUT}/unit_{idx:04d}.npz'
    if os.path.exists(path):
        return path
    n = len(spkid); years = year_of_steps()
    jd = JD0 + STEP * np.arange(N_T)
    best = np.full((n, len(HUBS), 2, 5), np.nan)                  # cost, departure step, flight steps, vinf_dep, vinf_arr
    ymin = np.full((n, len(HUBS), 2, YEARS), np.inf, np.float32)
    lam = pk.lambert_problem
    for o in range(n):
        r_o, v_o = two_body_states({k: el[k][o:o + 1] for k in el}, jd)   # one object at a time keeps memory small
        ro, vo = r_o[0], v_o[0]
        if not np.isfinite(ro).all():
            continue
        for h, hub in enumerate(HUBS):
            Hr, Hv = _HUB[h, :, :3], _HUB[h, :, 3:]
            steps = tof_steps(el['a'][o], HUB_A[hub])
            for d in (0, 1):                                      # 0: hub -> object, 1: object -> hub
                R1, V1, R2, V2 = (Hr, Hv, ro, vo) if d == 0 else (ro, vo, Hr, Hv)
                vd = np.full((N_DEP, len(steps)), np.nan); va = np.full((N_DEP, len(steps)), np.nan)
                for k in range(N_DEP):
                    r1, v1 = R1[k], V1[k]
                    for j, s in enumerate(steps):
                        try:
                            l = lam(r0=r1, r1=R2[k + s], tof=s * STEP * DAY_S, mu=MU_SUN)
                        except Exception:
                            continue
                        a0, a1 = l.v0[0], l.v1[0]
                        vd[k, j] = math.dist(a0, v1); va[k, j] = math.dist(a1, V2[k + s])
                vd /= 1000; va /= 1000
                if d == 0:
                    cost = planet_side_arr(hub, vd)[0] + va
                else:
                    cost = vd + planet_side_arr(hub, va)[0]
                cost = np.where(np.isnan(cost), np.inf, cost)
                jbest = cost.argmin(axis=1); cbest = cost[np.arange(N_DEP), jbest]
                np.minimum.at(ymin[o, h, d], years, cbest.astype(np.float32))
                k = int(cbest.argmin())
                if np.isfinite(cbest[k]):
                    best[o, h, d] = (cbest[k], k, steps[jbest[k]], vd[k, jbest[k]], va[k, jbest[k]])
    ymin[~np.isfinite(ymin)] = np.nan
    np.savez_compressed(path + '.tmp.npz', spkid=spkid, best=best.astype(np.float32), year_min=ymin.astype(np.float16),
                        hubs=np.array(HUBS), jd0=JD0, step=STEP, year0=YEAR0)
    os.replace(path + '.tmp.npz', path)
    return path

def plan_units(cat):
    """order: near-Earth objects first, then by absolute magnitude H (brightest, so largest, first)"""
    ok = np.isfinite(cat['a']) & (cat['a'] > 0) & (cat['e'] < 1) & np.isfinite(cat['ma']) & np.isfinite(cat['epoch']) \
        & np.isfinite(cat['i']) & np.isfinite(cat['om']) & np.isfinite(cat['w'])
    idx = np.flatnonzero(ok)
    H = np.where(np.isfinite(cat['H'][idx]), cat['H'][idx], 99)
    order = idx[np.lexsort((H, ~cat['neo'][idx]))]
    return [order[s:s + UNIT] for s in range(0, len(order), UNIT)]

def main(workers=4, first=0, last=None):
    os.makedirs(OUT, exist_ok=True)
    cat = dict(np.load('/work/data/sbdb/catalog.npz'))
    units = plan_units(cat)
    last = len(units) - 1 if last is None else last
    json.dump({'units': len(units), 'unit_size': UNIT, 'objects': int(sum(len(u) for u in units)), 'hubs': HUBS,
               'jd0': JD0, 'step_days': STEP, 'departures': N_DEP, 'tof_count': NTOF, 'tof_max_years': 30,
               'started': time.strftime('%Y-%m-%d %H:%M')}, open(f'{OUT}/meta.json', 'w'), indent=1)
    t = time.time(); hub = hub_states()
    print(f'{len(units)} units of up to {UNIT} objects; hub states in {time.time() - t:.0f} s', flush=True)
    keys = ('a', 'e', 'i', 'om', 'w', 'ma', 'epoch')
    jobs = [(u, {k: cat[k][units[u]] for k in keys}, cat['spkid'][units[u]]) for u in range(first, last + 1)
            if not os.path.exists(f'{OUT}/unit_{u:04d}.npz')]
    with Pool(workers, initializer=_init, initargs=(hub,)) as p:
        for path in p.imap_unordered(unit, jobs):
            print(time.strftime('%Y-%m-%d %H:%M'), os.path.basename(path), f'{time.time() - t:.0f} s', flush=True)

if __name__ == '__main__':
    a = sys.argv[1:]
    main(int(a[0]) if a else 4, int(a[1]) if len(a) > 1 else 0, int(a[2]) if len(a) > 2 else None)
