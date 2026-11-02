"""Daily transfer alternatives (engine/daily.py): structure, Pareto order, an independent recheck, ephemeris coverage."""
import math, pathlib, random, sys
ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / 'flyby'))
import numpy as np
import pytest
pk = pytest.importorskip('pykep')
from engine.conventions import HELIO, planet_side_dv
from engine.daily import K, MAX_REVS

DAILY = ROOT / 'data' / 'daily'
FILES = sorted(p for p in DAILY.glob('*.npz') if not p.stem.endswith('.tmp')) if DAILY.exists() else []
pytestmark = pytest.mark.skipif(not FILES, reason='run python -m engine.daily first')

def test_structure():
    for p in FILES:
        with np.load(p) as d:
            assert list(d['targets']) == [b for b in HELIO if b != p.stem]
            assert d['tof'].shape == (len(HELIO) - 1, 27089, K) and d['vinf'].shape == (len(HELIO) - 1, 27089, K, 2)
            assert d['revs'].shape == d['tof'].shape and d['vinf'].dtype == np.float32
            assert float(d['jd0']) == 2461345.5 and float(d['step']) == 1.0

def test_alternatives_trade_time_for_cost():
    """within a day, stored alternatives get slower and cheaper (own end states)"""
    rng = np.random.default_rng(3)
    for p in FILES:
        with np.load(p) as d:
            for i in rng.choice(len(d['targets']), 4, replace=False):
                b = str(d['targets'][i])
                for k in rng.choice(27089, 25, replace=False):
                    T = d['tof'][i, k]; V = d['vinf'][i, k].astype(float); ok = ~np.isnan(T)
                    c = [planet_side_dv(p.stem, v[0]) + planet_side_dv(b, v[1]) for v in V[ok]]
                    assert np.all(np.diff(T[ok]) > 0)
                    assert all(x >= y - 1e-4 for x, y in zip(c, c[1:]))    # float32 storage

def test_independent_recheck_of_stored_alternatives():
    """recompute a random sample from the stored flight times with every number of revolutions: one solution must match
    the stored excess speeds (float32) and have the stored number of revolutions"""
    import bodies
    atlas = bodies.load_atlas(); random.seed(11); worst = 0.0
    for _ in range(60):
        p = random.choice(FILES)
        with np.load(p) as d:
            i = random.randrange(len(d['targets'])); k = random.randrange(27089); j = random.randrange(K)
            t, v, n = float(d['tof'][i, k, j]), d['vinf'][i, k, j].astype(float), int(d['revs'][i, k, j])
            b = str(d['targets'][i])
        if math.isnan(t):
            continue
        A, B = bodies.body(p.stem, atlas), bodies.body(b, atlas)
        t0 = 2461345.5 + k - 2451544.5
        ra, va = A.eph(t0); rb, vb = B.eph(t0 + t)
        l = pk.lambert_problem(r0=ra, r1=rb, tof=t * 86400, mu=pk.MU_SUN, multi_revs=MAX_REVS)
        sols = [(math.dist(w0, va) / 1000, math.dist(w1, vb) / 1000, (q + 1) // 2) for q, (w0, w1) in enumerate(zip(l.v0, l.v1))]
        vd, vr, revs = min(sols, key=lambda s: abs(s[0] - v[0]) + abs(s[1] - v[1]))
        assert revs == n
        worst = max(worst, abs(vd - v[0]) / max(1, vd), abs(vr - v[1]) / max(1, vr))
    assert worst < 1e-5                             # float32 storage

def test_no_arrival_after_the_ephemeris_ends():
    """Bennu's Horizons solution ends on 2135-09-30: no stored transfer may arrive later"""
    import bodies
    end = bodies.coverage_end('101955')
    for p in FILES:
        if p.stem == '101955':
            continue
        with np.load(p) as d:
            i = list(d['targets']).index('101955')
            arrive = (2461345.5 - 2451544.5) + np.arange(27089)[:, None] + d['tof'][i]
            assert np.nanmax(arrive) <= end
