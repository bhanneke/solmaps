"""Contributor tool (python -m contrib): job registry, checksums and the two comparisons that verify a second run."""
import pathlib, sys
ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import numpy as np
from contrib.jobs import JOBS, BY_ID, OTHER, COVERED, HELIO
import contrib.__main__ as c

def test_registry():
    assert len({j.id for j in JOBS}) == len(JOBS)
    for j in JOBS:
        assert len(set(j.units)) == len(j.units) and j.units
        u = j.units[-1]
        assert j.cmd(u)[0] == 'python' and all(f.startswith(('data/', 'flyby/')) for f in j.files(u))
    assert len(OTHER) + len(COVERED) == len(HELIO) * (len(HELIO) - 1)
    assert BY_ID['screening'].files('0007') == ['data/screen_daily/unit_0007.npz']

def test_checksum_is_canonical():
    a = {'x': np.arange(4.0), 'y': np.array([1, 2], np.int16)}
    b = {'y': np.array([1, 2], np.int16), 'x': np.arange(4.0)}
    assert c.checksum(dict(sorted(a.items()))) == c.checksum(dict(sorted(b.items())))
    assert c.checksum([{'b': 1, 'a': 2}]) == c.checksum([{'a': 2, 'b': 1}])

def test_compare_arrays():
    ref = {'best': np.array([1.0, np.nan, 3.0]), 'names': np.array(['a', 'b'])}
    assert c.compare_arrays({'best': np.array([1.0, np.nan, 3.0 + 1e-7]), 'names': np.array(['a', 'b'])}, ref, 1e-6)['agrees']
    assert not c.compare_arrays({'best': np.array([1.0, np.nan, 3.1]), 'names': np.array(['a', 'b'])}, ref, 1e-6)['agrees']
    assert not c.compare_arrays({'best': np.array([1.0, 2.0, 3.0]), 'names': np.array(['a', 'b'])}, ref, 1e-6)['agrees']   # NaN pattern
    assert not c.compare_arrays({'best': np.array([1.0, np.nan, 3.0]), 'names': np.array(['a', 'c'])}, ref, 1e-6)['agrees']

def test_compare_optimum():
    r = lambda dv, seq='earth-mars-ceres': {'target': 'ceres', 'bin': '2027-2028', 'seq': seq.split('-'), 'arrival': 'capture', 'origin': 'earth', 'dv': dv}
    ref = [r(9.0), r(10.0, 'earth-venus-ceres')]
    ok = c.compare_optimum([r(9.02), r(9.5, 'earth-venus-ceres')], ref, 0.05)
    assert ok['agrees'] and ok['confirmed'] == 1 and ok['improved'] == 1
    bad = c.compare_optimum([r(9.2), r(10.0, 'earth-venus-ceres')], ref, 0.05)
    assert not bad['agrees'] and bad['not_reached'] == 1
