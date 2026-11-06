"""Catalogue screening (engine/screen.py): Kepler's equation at high eccentricity, and the compiled kernel against numpy and pykep."""
import math, os, pathlib, sys
ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / 'flyby'))
import numpy as np
import pytest
from engine import screen

def test_kepler_converges_at_every_eccentricity():
    M = np.linspace(-np.pi, np.pi, 4001, endpoint=False)[None, :]
    for e in (0.0, 0.3, 0.9, 0.97, 0.98, 0.99, 0.995, 0.999, 0.9999, 0.99999):
        E = screen.kepler_E(M, np.array([[e]]))
        assert np.abs(E - e * np.sin(E) - M).max() < 1e-11, e

def test_two_body_period():
    a = 2.5; el = {k: np.array([v]) for k, v in dict(a=a, e=0.98, i=10.0, om=20.0, w=30.0, ma=40.0, epoch=screen.JD0).items()}
    P = 2 * math.pi / (screen.K_GAUSS * a ** -1.5); r, v = screen.two_body_states(el, np.array([screen.JD0, screen.JD0 + P]))
    assert np.linalg.norm(r[0, 0] - r[0, 1]) < 1e3 and np.linalg.norm(v[0, 0] - v[0, 1]) < 1e-3   # back after one period, within 1 km and 1 mm/s

def test_flight_times_stay_on_the_grid():
    for a in (0.5, 1.0, 3.0, 40.0, 300.0, 1e5):
        for hub in screen.HUBS:
            s = screen.tof_steps(a, screen.HUB_A[hub])
            assert ((s >= 3) & (s <= screen.TOF_MAX_STEPS)).all()

@pytest.mark.skipif(not os.path.exists(screen.FORTRAN) or not (ROOT / 'data' / 'sbdb' / 'catalog.npz').exists() or not (ROOT / 'flyby' / 'horizons' / '2.json').exists(),
                    reason='needs make fortran, the catalogue and the ephemeris')
def test_kernel_matches_numpy_and_pykep(tmp_path):
    """the same five catalogue objects through both paths; on small samples the stored values agree exactly, and the
    cheapest transfer of the kernel is a real one"""
    pk = pytest.importorskip('pykep')
    cat = dict(np.load(ROOT / 'data' / 'sbdb' / 'catalog.npz')); ids = screen.plan_units(cat)[0][:5]; el = {k: cat[k][ids] for k in ('a', 'e', 'i', 'om', 'w', 'ma', 'epoch')}
    old = screen.OUT, screen.HUBFILE, screen.FORTRAN; screen.OUT, screen.HUBFILE = str(tmp_path), str(tmp_path / 'hubs.bin')
    try:
        hub = screen.hub_states(); screen._init(hub); hub.tofile(screen.HUBFILE)
        F = np.load(screen.unit_fortran(1, el, cat['spkid'][ids], str(tmp_path / 'f.npz')))
        screen.FORTRAN = '/nonexistent'; N = np.load(screen.unit((2, el, cat['spkid'][ids])))
    finally:
        screen.OUT, screen.HUBFILE, screen.FORTRAN = old
    assert np.array_equal(F['best'], N['best'], equal_nan=True) and np.array_equal(F['year_min'], N['year_min'], equal_nan=True)
    c, k, s, vd, va = F['best'][0, 0, 0]; k, s = int(k), int(s)                            # object 0, Earth, hub to object
    jd = screen.JD0 + screen.STEP * np.arange(screen.N_T); r, v = screen.two_body_states({x: el[x][:1] for x in el}, jd)
    l = pk.lambert_problem(r0=hub[0, k, :3].tolist(), r1=r[0, k + s].tolist(), tof=s * screen.STEP * screen.DAY_S, mu=screen.MU_SUN, multi_revs=0)
    assert math.dist(l.v0[0], hub[0, k, 3:]) / 1000 == pytest.approx(float(vd), abs=1e-4) and math.dist(l.v1[0], v[0, k + s]) / 1000 == pytest.approx(float(va), abs=1e-4)
