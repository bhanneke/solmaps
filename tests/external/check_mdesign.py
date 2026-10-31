"""Compare solmaps transfers with the JPL Small-Body Mission-Design maps (fetched by fetch_mdesign.py), cell by cell.

For every launch date and flight time of each map: solmaps' Earth (DE440, Earth-Moon barycentre) and object (daily JPL
Horizons states) positions and pykep's Lambert solutions with up to 5 revolutions (prograde). JPL lists one solution per
cell: it picks the lowest Earth-departure speed (and does not always list multi-revolution ones), solmaps the lowest
total. The check therefore asks whether JPL's pair of excess speeds (departure, arrival) is one of solmaps' solutions:
within 0.03 km/s at departure (JPL departs from Earth's centre, solmaps from the Earth-Moon barycentre, 4,700 km away)
and 0.003 km/s at arrival. Run in the container: python tests/external/check_mdesign.py
"""
import json, math, pathlib, sys
HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent / 'flyby'))
import numpy as np, pykep as pk, bodies
OBJECTS = ['433', '101955', '162173', '99942', '65803', '25143', '341843', '4660', '1', '4']
TOL_DEP, TOL_ARR = 0.03, 0.003

def compare(des, atlas, E):
    d = json.load(open(HERE / f'mdesign_{des}.json'))
    B = bodies.body({'1': 'ceres', '4': 'vesta'}.get(des, des), atlas)
    dep = np.array(d['dep_date'], float); tof = np.array(d['tof'], float)
    jdep = np.array(d['vinf_dep'], float); jarr = np.array(d['vinf_arr'], float)       # [tof, launch date]
    found, cells, dev_dep, dev_arr, misses, miss_dev = 0, 0, [], [], [], []
    for j, mjd in enumerate(dep):
        t0 = mjd + 2400000.5 - 2451544.5
        r0, v0 = E.eph(t0)
        for i, T in enumerate(tof):
            if not (np.isfinite(jdep[i, j]) and jdep[i, j] < 20 and jarr[i, j] < 20):
                continue
            cells += 1
            r1, v1 = B.eph(t0 + T)
            try:
                l = pk.lambert_problem(r0=r0, r1=r1, tof=T * 86400.0, mu=pk.MU_SUN, multi_revs=5)
            except Exception:
                misses.append((mjd, T)); continue
            sols = [(math.dist(a, v0) / 1000, math.dist(b, v1) / 1000) for a, b in zip(l.v0, l.v1)]
            dd, da = min(((abs(s[0] - jdep[i, j]), abs(s[1] - jarr[i, j])) for s in sols), key=lambda x: x[0] / TOL_DEP + x[1] / TOL_ARR)
            if dd <= TOL_DEP and da <= TOL_ARR:
                found += 1; dev_dep.append(dd); dev_arr.append(da)
            else:
                misses.append((mjd, T)); miss_dev.append((dd, da))
    md = np.array(miss_dev) if miss_dev else np.zeros((1, 2))
    return {'object': d['object']['fullname'], 'cells': cells, 'found': found, 'dep_median': float(np.median(dev_dep)),
            'arr_median': float(np.median(dev_arr)), 'misses': misses[:3],
            'miss_dep_median': float(np.median(md[:, 0])), 'miss_arr_median': float(np.median(md[:, 1])), 'miss_arr_max': float(md[:, 1].max())}

def run():
    atlas = bodies.load_atlas(); E = bodies.body('earth', atlas); out = []
    for des in OBJECTS:
        r = compare(des, atlas, E); out.append(r)
        print(f"{r['object'][:24]:24s} {r['cells']:6d} cells | JPL's solution among ours in {100 * r['found'] / r['cells']:.2f}% | "
              f"matched: departure median {r['dep_median']:.4f}, arrival median {r['arr_median']:.5f} km/s | misses: closest departure {r['miss_dep_median']:.3f}, arrival {r['miss_arr_median']:.4f} (max {r['miss_arr_max']:.2f})", flush=True)
    return out

if __name__ == '__main__':
    run()
