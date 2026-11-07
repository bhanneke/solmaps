"""The file reproduces itself: random options solved at the stored flight time must give the stored speeds and revolutions.
Run in the container from /work: python tests/audit_self.py
"""
# The file reproduces itself: random options solved at the stored flight time must give the stored speeds and revolutions.
import math, random, sys
sys.path.insert(0, '/work/flyby'); sys.path.insert(0, '/work')
import numpy as np, pykep as pk, bodies
from engine import daily
from engine.conventions import HELIO
atlas = bodies.load_atlas(); random.seed(17); worst = 0; revbad = 0; n = 0; over = 0
for _ in range(3000):
    a = random.choice(HELIO); f = np.load(f'/work/data/daily/{a}.npz'); i = random.randrange(29); d = random.randrange(27089); j = random.randrange(10); b = str(f['targets'][i])
    T = float(f['tof'][i, d, j])
    if T != T:
        continue
    A, B = bodies.body(a, atlas), bodies.body(b, atlas); t0 = daily.JD0 + d - 2451544.5; ra, va = A.eph(t0); rb, vb = B.eph(t0 + T); v = f['vinf'][i, d, j].astype(float); r = int(f['revs'][i, d, j])
    l = pk.lambert_problem(r0=ra, r1=rb, tof=T * 86400, mu=pk.MU_SUN, multi_revs=10000)
    e, q = min((abs(math.dist(x, va) / 1000 - v[0]) + abs(math.dist(y, vb) / 1000 - v[1]), k) for k, (x, y) in enumerate(zip(l.v0, l.v1)))
    worst = max(worst, e); n += 1; revbad += (q + 1) // 2 != r; over += T > daily.TOF_MAX
print(f'{n} random options: largest speed difference {worst:.2e} km/s, wrong revolution count {revbad}, flights over 100 years {over}')
