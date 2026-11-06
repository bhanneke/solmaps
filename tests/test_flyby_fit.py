"""Compiled flyby fitness (engine/fortran/flyby_fit.f90) against the Python model of flyby/routes3.py, on random trajectories."""
import os, pathlib, sys
ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / 'flyby'))
import numpy as np
import pytest
pk = pytest.importorskip('pykep')
LIB, TAB = ROOT / 'engine' / 'fortran' / 'flyby_fit.so', ROOT / 'data' / 'flyby_tables'
pytestmark = pytest.mark.skipif(not (LIB.exists() and (TAB / 'earth.npy').exists()), reason='run make fortran first')

@pytest.mark.parametrize('seq,arrival', [(['earth', 'mars', 'jupiter'], 'capture'), (['ceres', 'mars', 'earth'], 'aero'), (['earth', 'venus', 'earth', 'mars', '433'], 'capture'), (['mercury', 'venus', 'earth'], 'capture')])
def test_kernel_matches_python(seq, arrival):
    os.environ['FLYBY_FIT_LIB'], os.environ['FLYBY_TABLES'] = str(LIB), str(TAB)
    import routes3
    routes3.FIT_LIB, routes3.TABLES = str(LIB), str(TAB)
    t0 = [pk.epoch('2031-01-01').mjd2000, pk.epoch('2033-01-01').mjd2000]; u = routes3.Route(seq, t0, arrival)
    lo, hi = np.array(u.get_bounds()[0]), np.array(u.get_bounds()[1]); rng = np.random.default_rng(2)
    X = rng.uniform(lo, hi, (2000, len(lo)))
    py = np.array([u.python_fitness(x)[0] for x in X]); fo = np.array([u.fitness(x)[0] for x in X]); assert u.fast
    both = (py < 999) & (fo < 999); assert np.abs(py - fo)[both].max() < 0.2     # anywhere, also at absurd speeds near the Sun
    best = X[np.argmin(py)]                                # then where the search works: a short descent, and its surroundings
    for _ in range(3000):
        c = np.clip(best + rng.normal(0, 0.02, len(lo)) * (hi - lo), lo, hi)
        if u.python_fitness(c)[0] < u.python_fitness(best)[0]:
            best = c
    N = np.clip(best + rng.normal(0, 0.003, (2000, len(lo))) * (hi - lo), lo, hi)
    py = np.array([u.python_fitness(x)[0] for x in N]); fo = np.array([u.fitness(x)[0] for x in N]); near = (py < 999) & (fo < 999)
    print(f'{"-".join(seq)}: best {u.python_fitness(best)[0]:.3f} km/s; around it |diff| median {np.median(np.abs(py - fo)[near]):.1e}, max {np.abs(py - fo)[near].max():.1e}')
    assert np.abs(py - fo)[near].max() < 1e-3
