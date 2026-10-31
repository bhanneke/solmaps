"""Vectorised Lambert solver: many transfers at once with numpy (universal variables, single revolution, prograde).

The same formulation as the JavaScript solver in network/engine.js (Curtis, Orbital Mechanics for Engineering Students,
algorithm 5.2): for each problem, bisection on the universal variable z between the hyperbolic and the one-revolution
limit, all problems advancing together as arrays. Prograde means motion about the +z axis of the frame (the ecliptic
pole); transfers within 0.06 degrees of 0 or 180 degrees have no defined plane and come back as not solved.

    v1, v2, ok = lambert(r1, r2, tof, mu)        # r1, r2: [N, 3]; tof: [N]; same length units for r and mu

Speed (2026-11-01): about 250,000 transfers per second on one core, against about 420,000 for pykep's compiled solver
called one at a time from Python. It does not replace pykep; it is an independent, numpy-only second solver for checks
and tests, with the same answers to 1e-10 (tests/test_vlambert.py). Bisection with 64 steps; safeguarded Newton steps
were no faster on arrays and converged less reliably near the bracket ends.
"""
import numpy as np

def _stumpff(z):
    """C(z), S(z) with series near zero (where the closed forms lose precision)"""
    C = np.empty_like(z); S = np.empty_like(z)
    small = np.abs(z) < 1e-3
    pos, neg = (z > 0) & ~small, (z < 0) & ~small
    zs = z[small]
    C[small] = 0.5 - zs / 24 + zs * zs / 720
    S[small] = 1 / 6 - zs / 120 + zs * zs / 5040
    sp = np.sqrt(z[pos])
    C[pos] = (1 - np.cos(sp)) / z[pos]
    S[pos] = (sp - np.sin(sp)) / sp ** 3
    sn = np.sqrt(-z[neg])
    C[neg] = (np.cosh(sn) - 1) / -z[neg]
    S[neg] = (np.sinh(sn) - sn) / sn ** 3
    return C, S

def lambert(r1, r2, tof, mu, iterations=64):
    r1 = np.asarray(r1, np.float64); r2 = np.asarray(r2, np.float64); tof = np.asarray(tof, np.float64)
    R1, R2 = np.linalg.norm(r1, axis=1), np.linalg.norm(r2, axis=1)
    cosd = np.clip(np.einsum('ij,ij->i', r1, r2) / (R1 * R2), -1, 1)
    dnu = np.arccos(cosd)
    retro = np.cross(r1, r2)[:, 2] < 0
    dnu = np.where(retro, 2 * np.pi - dnu, dnu)                      # prograde about the +z axis
    ok = np.abs(np.sin(dnu)) >= 1e-3
    A = np.sin(dnu) * np.sqrt(R1 * R2 / np.maximum(1 - np.cos(dnu), 1e-300))
    sq = np.sqrt(mu)

    def y_of(z, sel=slice(None)):
        C, S = _stumpff(z)
        return R1[sel] + R2[sel] + A[sel] * (z * S - 1) / np.sqrt(C), C, S

    def F(z, sel=slice(None)):
        y, C, S = y_of(z, sel)
        yy = np.maximum(y, 0)
        return (yy / C) ** 1.5 * S + A[sel] * np.sqrt(yy) - sq * tof[sel], y, C, S

    n = len(tof)
    lo = np.full(n, -400.0); hi = np.full(n, 4 * np.pi ** 2 - 1e-6)
    # very fast hyperbolic transfers need a lower bound below -400: extend it where F(lo) > 0
    for _ in range(4):
        up = F(lo)[0] > 0
        if not up.any():
            break
        lo = np.where(up, lo * 4, lo)                               # down to -102,400 (cosh stays finite)
    # where y < 0 at the lower bound (A > 0), move the bound up to the root of y first
    y_lo = y_of(lo)[0]
    fix = y_lo < 0
    if fix.any():
        a, b = lo[fix], hi[fix]
        bad = y_of(b, fix)[0] < 0
        for _ in range(iterations):
            m = (a + b) / 2
            neg = y_of(m, fix)[0] < 0
            a = np.where(neg, m, a); b = np.where(neg, b, m)
        lo[fix] = b
        ok[np.flatnonzero(fix)[bad]] = False
    ok &= (F(lo)[0] <= 0) & (F(hi)[0] >= 0)
    for _ in range(iterations):                                     # F rises monotonically with z: bisection
        m = (lo + hi) / 2
        below = F(m)[0] < 0
        lo = np.where(below, m, lo); hi = np.where(below, hi, m)
    z = (lo + hi) / 2
    y, C, S = y_of(z)
    f = 1 - y / R1
    g = A * np.sqrt(np.maximum(y, 0) / mu)
    gd = 1 - y / R2
    with np.errstate(divide='ignore', invalid='ignore'):
        v1 = (r2 - f[:, None] * r1) / g[:, None]
        v2 = (gd[:, None] * r2 - r1) / g[:, None]
    ok &= np.isfinite(v1).all(axis=1) & np.isfinite(v2).all(axis=1) & (y > 0)
    return v1, v2, ok
