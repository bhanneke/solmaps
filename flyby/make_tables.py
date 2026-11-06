# Position tables for the compiled flyby fitness (engine/fortran/flyby_fit.f90): every body [t0, h, ...] in row 0, then
# [x, y, z, vx, vy, vz] in m and m/s. Small bodies keep their daily JPL Horizons rows; planets every quarter day from flyby/bodies.py.
# Output: data/flyby_tables/<name>.npy, one per body, not in git. Run in the container from /work: python flyby/make_tables.py [name ...]
import os, sys
sys.path.insert(0, '/work/flyby'); sys.path.insert(0, '/work')
import numpy as np, pykep as pk
import bodies
from engine.conventions import HELIO

OUT = os.environ.get('FLYBY_TABLES', '/work/data/flyby_tables')
T0, T1, H = 9000.0, 73000.0, 0.25                            # MJD2000: 2024 to 2199

def make(name, atlas):
    path = f'{OUT}/{name}.npy'
    if os.path.exists(path):
        return path
    if name in bodies.PLANETS:
        B = bodies.body(name, atlas); ts = np.arange(T0, T1, H); t0, h = T0, H; tab = np.empty((len(ts), 6))
        for i, t in enumerate(ts):
            r, v = B.eph(float(t)); tab[i, :3], tab[i, 3:] = r, v
    else:
        rows = np.asarray(bodies.HorizonsBody(name).rows); t0, h = rows[0, 0] - 2451544.5, rows[1, 0] - rows[0, 0]
        tab = np.column_stack([rows[:, 1:4] * pk.AU, rows[:, 4:7] * pk.AU / 86400.0])
    np.save(path + '.tmp.npy', np.vstack([[t0, h, 0, 0, 0, 0], tab])); os.replace(path + '.tmp.npy', path)
    return path

if __name__ == '__main__':
    os.makedirs(OUT, exist_ok=True); atlas = bodies.load_atlas()
    for n in sys.argv[1:] or HELIO:
        print(make(n, atlas), flush=True)
