"""The vectorised Lambert solver (engine/vlambert.py) against pykep on random transfers across the solar system."""
import pathlib, sys
ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import numpy as np
import pytest
pk = pytest.importorskip('pykep')
from engine.vlambert import lambert

AU, DAY, MU = 149597870700.0, 86400.0, 1.32712440018e20

def problems(n, seed):
    rng = np.random.default_rng(seed)
    def pos():
        r = np.exp(rng.uniform(np.log(0.3), np.log(40), n)) * AU
        th = rng.uniform(0, 2 * np.pi, n); inc = rng.normal(0, 0.15, n)
        return np.stack([r * np.cos(th), r * np.sin(th), r * np.sin(inc)], 1)
    return pos(), pos(), np.exp(rng.uniform(np.log(10), np.log(100 * 365.25), n)) * DAY   # 10 days to 100 years

def test_matches_pykep():
    r1, r2, tof = problems(3000, 7)
    v1, v2, ok = lambert(r1, r2, tof, MU)
    assert ok.all()                                  # every one of these has a single-revolution prograde solution
    worst = 0.0
    for i in range(len(tof)):
        l = pk.lambert_problem(r0=r1[i], r1=r2[i], tof=tof[i], mu=MU)
        for mine, ref in ((v1[i], l.v0[0]), (v2[i], l.v1[0])):
            worst = max(worst, np.linalg.norm(mine - np.array(ref)) / np.linalg.norm(ref))
    assert worst < 1e-8

def test_undefined_plane_is_declined():
    """opposite positions (180 degrees) leave the transfer plane undefined"""
    r1 = np.array([[AU, 0.0, 0.0]]); r2 = np.array([[-1.5 * AU, 0.0, 0.0]])
    assert not lambert(r1, r2, np.array([250 * DAY]), MU)[2][0]

def test_hohmann_case():
    """Earth to Mars distance, 180 degrees minus a hair, Hohmann time: departure speed close to the Hohmann value"""
    a = (1.0 + 1.524) / 2 * AU
    t = np.pi * np.sqrt(a ** 3 / MU)
    ang = np.radians(179.0)
    r1 = np.array([[AU, 0.0, 0.0]]); r2 = np.array([[1.524 * AU * np.cos(ang), 1.524 * AU * np.sin(ang), 0.0]])
    v1, _, ok = lambert(r1, r2, np.array([t]), MU)
    v_hohmann = np.sqrt(MU * (2 / AU - 1 / a))
    assert ok[0] and abs(np.linalg.norm(v1[0]) - v_hohmann) / v_hohmann < 0.01
