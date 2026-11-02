"""Release audit of the daily transfer data (engine/daily.py): sanity sweeps over every record, against the earlier
single-revolution data where it exists. Writes data/daily/audit.json and prints a summary.

Checks per origin and target:
  - impossible values: negative or missing excess speeds where a flight time exists, options not ordered by flight time,
    a slower option dearer than a faster one (more than the float16 storage allows)
  - floor: the lowest cost over all dates against the single-revolution data's lowest cost, and the share of days more
    than 0.3 km/s below that floor (a two-impulse transfer cannot beat the best launch window by much)
  - gain: how much cheaper the cheapest option per day became, and on how many days it became dearer
  - classic flights: the cheapest option up to 2.5 Hohmann times (the single-revolution data's grid) must not be dearer
    than the single-revolution data's cheapest by more than its float16 rounding (0.035 km/s)

Run in the container from /work: python tests/audit_daily.py
"""
import json, pathlib, sys
sys.path.insert(0, '/work'); sys.path.insert(0, '/work/flyby')
import numpy as np
from engine.conventions import HELIO, planet_side_arr
from engine import daily

NEW, OLD = pathlib.Path('/work/data/daily'), pathlib.Path('/work/data/daily_singlerev')

def cheapest(f, i, a, b):
    T, V = f['tof'][i].astype(float), f['vinf'][i].astype(float)
    c = np.where(np.isnan(T), np.inf, planet_side_arr(a, V[..., 0])[0] + planet_side_arr(b, V[..., 1])[0])
    return T, V, c

def main():
    rows, totals = [], {'records': 0, 'impossible': 0, 'below_floor_days': 0, 'dearer_days': 0, 'classic_dearer_days': 0, 'days': 0}
    for a in HELIO:
        new = np.load(NEW / f'{a}.npz'); old = np.load(OLD / f'{a}.npz') if (OLD / f'{a}.npz').exists() else None
        for i, b in enumerate(new['targets']):
            b = str(b)
            T, V, c = cheapest(new, i, a, b)
            ok = ~np.isnan(T)
            both = ok[:, 1:] & ok[:, :-1]
            neg = int((V[ok] < 0).sum() + np.isnan(V[..., 0][ok]).sum() + np.isnan(V[..., 1][ok]).sum())
            unordered = int(np.where(both, np.diff(T, axis=1) <= 0, False).sum())
            rising = int(np.where(both, np.diff(c, axis=1) > 0.02, False).sum())
            cn = c.min(1); row = {'origin': a, 'target': b, 'records': int(ok.sum()), 'impossible': neg + unordered + rising,
                                  'min_cost': float(cn.min()), 'median_daily_cost': float(np.median(cn[np.isfinite(cn)]))}
            if old is not None:
                co = cheapest(old, list(old['targets']).index(b), a, b)[2].min(1)
                fin = np.isfinite(cn) & np.isfinite(co)
                hi = daily.tof_grid(daily.semi_major_axis(a), daily.semi_major_axis(b))[daily.NTOF - 1]
                cc = np.where(T > hi * 1.0001, np.inf, c).min(1); fc = np.isfinite(cc) & np.isfinite(co)
                row.update({'min_cost_singlerev': float(co.min()), 'below_floor_days': int((cn[fin] < co.min() - 0.3).sum()),
                            'dearer_days': int((cn[fin] > co[fin] + 0.02).sum()), 'median_gain': float(np.median((co - cn)[fin])),
                            'days': int(fin.sum()),
                            'classic_dearer_days': int((cc[fc] > co[fc] + 0.035).sum()) + int((np.isfinite(co) & ~np.isfinite(cc)).sum())})
                for k in ('below_floor_days', 'dearer_days', 'classic_dearer_days', 'days'):
                    totals[k] += row[k]
            totals['records'] += row['records']; totals['impossible'] += row['impossible']
            rows.append(row)
    json.dump({'totals': totals, 'routes': rows}, open(NEW / 'audit.json', 'w'), indent=1)
    worst_floor = min(rows, key=lambda r: r.get('min_cost', 0) - r.get('min_cost_singlerev', r.get('min_cost', 0)))
    print(f"routes {len(rows)}, option records {totals['records']:,}, impossible values {totals['impossible']}")
    print(f"days below the single-revolution floor by > 0.3 km/s: {totals['below_floor_days']} of {totals['days']:,}; "
          f"days dearer than single-revolution by > 0.02 km/s: {totals['dearer_days']}; "
          f"classic flights dearer than single-revolution by > 0.035 km/s (or missing): {totals['classic_dearer_days']}")
    print(f"largest drop of the lowest cost: {worst_floor['origin']}>{worst_floor['target']} "
          f"{worst_floor.get('min_cost_singlerev', float('nan')):.2f} -> {worst_floor['min_cost']:.2f} km/s")

if __name__ == '__main__':
    main()
