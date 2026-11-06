"""Release audit of the repair pass (engine/repair_daily.py) against the data before it, over every route and day.

Reports spikes (cheapest option more than a threshold above both neighbouring days), the change of the cheapest and of the
classic option, the fastest option, arcs through the Sun, and Pareto order. Writes audit_repair.json next to the repaired data.
Run in the container: python tests/audit_repair.py BEFORE_FOLDER AFTER_FOLDER
"""
import json, sys
sys.path.insert(0, '/work'); sys.path.insert(0, '/work/flyby')
import numpy as np
from engine import daily
from engine.conventions import HELIO, planet_side_arr
R_SUN_AU = 6.957e8 / 149597870700.0

def cost(a, b, T, V):
    T, V = T.astype(float), V.astype(float)
    return np.where(np.isnan(T), np.inf, planet_side_arr(a, V[..., 0])[0] + planet_side_arr(b, V[..., 1])[0])
def spikes(m, x):
    return (m[1:-1] > m[:-2] + x) & (m[1:-1] > m[2:] + x) & np.isfinite(m[1:-1])

def main(before, after):
    tot = dict(routes=0, days=0, records=0, unordered=0, rising=0, spikes2_before=0, spikes2_after=0, spikes05_before=0, spikes05_after=0, cheaper_001=0, cheaper_05=0, dearer_001=0,
               classic_dearer_001=0, classic_lost=0, fastest_slower_days=0, days_lost=0, inside_sun=0, within_10_radii=0)
    worst = dict(gain=(0, ''), dearer=(0, ''), classic=(0, ''), spike=(0, '')); left = []
    for a in HELIO:
        o, n = np.load(f'{before}/{a}.npz'), np.load(f'{after}/{a}.npz')
        assert list(o['targets']) == list(n['targets'])
        for i, b in enumerate(n['targets']):
            b = str(b); T0, V0, T1, V1, S = o['tof'][i], o['vinf'][i], n['tof'][i], n['vinf'][i], n['sun_au'][i]
            c0, c1 = cost(a, b, T0, V0), cost(a, b, T1, V1); m0, m1 = c0.min(1), c1.min(1); fin = np.isfinite(m0) & np.isfinite(m1); d = (m1 - m0)[fin]
            hi = daily.tof_grid(daily.semi_major_axis(a), daily.semi_major_axis(b))[daily.NTOF - 1] * 1.0001
            k0, k1 = np.where(T0 > hi, np.inf, c0).min(1), np.where(T1 > hi, np.inf, c1).min(1); kf = np.isfinite(k0) & np.isfinite(k1); dk = (k1 - k0)[kf]
            ok = np.isfinite(T1); both = ok[:, 1:] & ok[:, :-1]
            tot['routes'] += 1; tot['days'] += len(m1); tot['records'] += int(ok.sum())
            tot['unordered'] += int(np.where(both, np.diff(T1.astype(float), axis=1) <= 0, False).sum()); tot['rising'] += int(np.where(both, np.diff(c1, axis=1) > 1e-3, False).sum())
            s2, s05 = spikes(m1, 2), spikes(m1, 0.5)
            tot['spikes2_before'] += int(spikes(m0, 2).sum()); tot['spikes2_after'] += int(s2.sum()); tot['spikes05_before'] += int(spikes(m0, .5).sum()); tot['spikes05_after'] += int(s05.sum())
            tot['cheaper_001'] += int((d < -0.001).sum()); tot['cheaper_05'] += int((d < -0.5).sum()); tot['dearer_001'] += int((d > 0.001).sum())
            tot['classic_dearer_001'] += int((dk > 0.001).sum()); tot['classic_lost'] += int((np.isfinite(k0) & ~np.isfinite(k1)).sum())
            tot['days_lost'] += int((np.isfinite(m0) & ~np.isfinite(m1)).sum())
            f0, f1 = np.nanmin(T0.astype(float), axis=1), np.nanmin(T1.astype(float), axis=1) if ok.any() else None
            tot['fastest_slower_days'] += int((f1 > f0 + 1e-3).sum())
            tot['inside_sun'] += int((S[ok] <= R_SUN_AU).sum()); tot['within_10_radii'] += int((S[ok] <= 10 * R_SUN_AU).sum())
            lab = f'{a}>{b}'
            if len(d):
                if d.min() < worst['gain'][0]: worst['gain'] = (float(d.min()), lab)
                if d.max() > worst['dearer'][0]: worst['dearer'] = (float(d.max()), lab)
            if len(dk) and dk.max() > worst['classic'][0]: worst['classic'] = (float(dk.max()), lab)
            if s2.any():
                gap = (m1[1:-1] - np.maximum(m1[:-2], m1[2:]))[s2]; left.append((float(gap.max()), lab, int(s2.sum())))
                if gap.max() > worst['spike'][0]: worst['spike'] = (float(gap.max()), lab)
    json.dump({'totals': tot, 'worst': worst, 'spikes_left': sorted(left, reverse=True)}, open(f'{after}/audit_repair.json', 'w'), indent=1)
    print(json.dumps(tot, indent=0)); print('worst', worst); print('routes with spikes left', len(left), sorted(left, reverse=True)[:8])

if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
