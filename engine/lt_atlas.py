"""Low-thrust atlas (precompute), two scenarios.

edges (default, since 2026-11-10): the heliocentric leg alone, from the origin's edge (escape, zero excess speed) to the
target's edge (arrival with zero excess speed), for four reference ships that differ only in their initial acceleration
(LEVELS, mm/s2) at one exhaust speed (ISP). For a given acceleration and exhaust speed the trajectory and the propellant
share do not depend on the ship's absolute mass, so the mission planner scales these legs to any electric ship and adds
the planet ends (rocket-supplied escape, spirals, burns, aerocapture) itself. Output: data/lowthrust_edges.json, one row
per pair, window and level (levels in ascending order, each seeded with the weaker level's leg), with the propellant share, flight time, equivalent speed change and the independent check.
Flight-time bounds: 0.5 to 4 Hohmann times (at most 4,000 days); electric legs often take longer than impulsive ones.

spirals (the first atlas): the 'solar-electric cargo' preset with full spirals from and into 300 km parking orbits at both
ends, data/lowthrust_atlas.json. That scenario leaves most planet-to-planet routes infeasible, because the two spirals
alone cost up to 15 km/s of the ship's 16.7 km/s.

Resumable. Run in the solmaps-env container, from /work:  python -m engine.lt_atlas [edges|spirals] [processes]
"""
import json, math, os, sys, time
sys.path.insert(0, '/work/flyby'); sys.path.insert(0, '/work')

from engine.conventions import SITES
from engine.ship import PRESETS
from engine import refine

K2 = 2.9591220828e-4
A = {'earth': 1.0, 'venus': 0.723, 'mercury': 0.387, 'mars': 1.524, 'ceres': 2.77, 'vesta': 2.36, 'psyche': 2.92,
     '433': 1.458, '101955': 1.126, '162173': 1.191, 'jupiter': 5.20, 'saturn': 9.54}

def mjd(year):
    return (year - 2000) * 365.25 - 0.5

LEVELS = (0.05, 0.1, 0.2, 0.4)   # mm/s2 at the start of the leg: Dawn began near 0.08, the cargo preset at 0.17
ISP = 2500.0                      # s, exhaust speed 24.5 km/s (gridded ion engine class)
M0 = 10000.0                      # kg; any value gives the same shares

def edge_legs(args):
    """one pair and window, the reference ships in ascending acceleration. A stronger engine can fly what a weaker one
    flies (same exhaust speed and mass: throttles scaled down), so each level also refines the previous feasible level's
    leg as a start; without that the search missed legs a weaker ship had found (Mars to Jupiter: feasible at 0.05 mm/s2,
    not at 0.1)."""
    from engine import lowthrust as LT
    from engine.ship import Ship
    a, b, y, levels = args
    tH = math.pi * math.sqrt(((A[a] + A[b]) / 2) ** 3 / K2)
    tof, t0b = (max(60, 0.5 * tH), min(4000, 4 * tH)), (mjd(y), mjd(y + 2))
    rows, prev = [], None
    for a_mm in sorted(levels):
        ship = Ship(f'reference {a_mm} mm/s2', dry_kg=0.3 * M0, payload_kg=0.0, fuel_capacity_kg=0.7 * M0, thrust_n=a_mm * 1e-3 * M0,
                    isp_s=ISP, propulsion='electric')
        nseg = LT.segments(ship, M0); t = time.time(); err = ''; leg = None
        try:
            leg = LT.heliocentric(a, b, ship, M0, t0b, tof, 0.0, 0.0, nseg, 8, 1)
            if prev is not None and prev['nseg'] == nseg:
                x = ([prev['t0_mjd2000'], prev['mf_kg']] + list(prev['vinf_dep_vec_ms']) + list(prev['vinf_arr_vec_ms'])
                     + [c / ship.thrust_n for T in prev['thrust_n'] for c in T] + [prev['tof_days']])
                c = LT.zero_order_hold({'x': x, 'nseg': nseg}, a, b, ship, M0, t0b, tof, 0.0, 0.0)
                if c is not None and (leg is None or c['mf_kg'] > leg['mf_kg']):
                    c['found_by'] = f"continuation from {prev['accel']} mm/s2"; leg = c
        except Exception as e:                       # one failing leg must not end the atlas
            err = f'{type(e).__name__}: {e}'[:200]
        row = {'origin': a, 'target': b, 'window': f'{y}-{y + 1}', 'accel_mm_s2': a_mm, 'isp_s': ISP, 'feasible': leg is not None,
               'error': err, 'seconds': round(time.time() - t, 1)}
        if leg:
            leg['accel'] = a_mm; prev = leg
            row.update(propellant_share=leg['fuel_kg'] / M0, days=leg['tof_days'], depart_mjd2000=leg['t0_mjd2000'],
                       dv_equivalent_kms=leg['dv_equivalent_kms'], max_throttle=leg['max_throttle'],
                       check_km=leg['check']['position_error_km'], found_by=leg.get('found_by'))
        rows.append(row)
    return rows

def main_edges(procs=4, out='/work/data/lowthrust_edges.json', pairs=None, years=None, levels=LEVELS):
    from multiprocessing import Pool
    rows = json.load(open(out)) if os.path.exists(out) else []
    done = {(r['origin'], r['target'], r['window'], r['accel_mm_s2']) for r in rows}
    pairs = pairs or [(a, b) for a in SITES for b in SITES if a != b]
    todo = [(a, b, y, tuple(lv for lv in levels if (a, b, f'{y}-{y + 1}', lv) not in done))
            for a, b in pairs for y in (years or range(2027, 2098, 2))]
    todo = [t for t in todo if t[3]]
    print(f'{len(todo)} pair-windows to compute, {len(rows)} legs done', flush=True)
    with Pool(procs, maxtasksperchild=20) as p:
        for res in p.imap_unordered(edge_legs, todo):
            for row in res:
                rows.append(row); print(json.dumps(row), flush=True)
            json.dump(rows, open(out + '.tmp', 'w')); os.replace(out + '.tmp', out)

def main(out='/work/data/lowthrust_atlas.json'):
    if os.environ.get('SOLMAPS_POOL'):
        import pygmo as pg
        pg.mp_island.init_pool(int(os.environ['SOLMAPS_POOL']))
    ship = PRESETS['solar-electric cargo']
    rows = json.load(open(out)) if os.path.exists(out) else []
    done = {(r['origin'], r['target'], r['window']) for r in rows}
    for a in SITES:
        for b in SITES:
            if a == b:
                continue
            tH = math.pi * math.sqrt(((A[a] + A[b]) / 2) ** 3 / K2)
            tof = (max(60, 0.5 * tH), min(4000, 3 * tH))
            for y in range(2027, 2098, 2):
                key = (a, b, f'{y}-{y + 1}')
                if key in done:
                    continue
                t = time.time()
                r = refine.lowthrust_transfer(a, b, ship, (mjd(y), mjd(y + 2)), tof)
                leg = r.get('leg') or {}
                row = {'origin': a, 'target': b, 'window': key[2], 'feasible': bool(r.get('feasible')), 'reason': r.get('reason', ''),
                       'fuel_kg': r.get('fuel_kg'), 'days': (r['arrive_mjd2000'] - r['depart_mjd2000']) if leg else None,
                       'depart_mjd2000': r.get('depart_mjd2000'), 'check_km': leg.get('check', {}).get('position_error_km'),
                       'seconds': round(time.time() - t, 1)}
                rows.append(row)
                print(json.dumps(row), flush=True)
                json.dump(rows, open(out + '.tmp', 'w')); os.replace(out + '.tmp', out)

if __name__ == '__main__':
    mode = sys.argv[1] if len(sys.argv) > 1 else 'edges'
    if mode == 'spirals':
        main()
    else:
        main_edges(int(sys.argv[2]) if len(sys.argv) > 2 else 4)
