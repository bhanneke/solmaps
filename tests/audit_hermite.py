"""Mid-day interpolation error of the small-body ephemerides. Cubic Hermite error grows with the fourth power of the step, so
interpolating over two days and comparing with the stored state at the middle gives 16 times the error of the one-day files.
Prints that estimate per body, in metres. Run in the container from /work: python tests/audit_hermite.py
"""
import json, os
import numpy as np
AU = 149597870.7e3
D = '/work/flyby/horizons'; out = []
for f in sorted(os.listdir(D)):
    if not f.endswith('.json'):
        continue
    r = np.asarray(json.load(open(f'{D}/{f}'))['rows'], float)
    if len(r) < 3 or abs(r[1, 0] - r[0, 0] - 1) > 1e-9:
        continue
    a, m, b = r[:-2], r[1:-1], r[2:]; h = 2.0
    p = 0.5 * (a[:, 1:4] + b[:, 1:4]) + h / 8 * (a[:, 4:7] - b[:, 4:7])            # Hermite at s = 0.5
    e = np.linalg.norm(p - m[:, 1:4], axis=1) * AU / 16; i = int(e.argmax())
    out.append((float(e.max()), float(np.median(e)), f[:-5], float(m[i, 0])))
for x in sorted(out, reverse=True):
    print(f'{x[2]:10s} median {x[1]:10.3f} m  largest {x[0]:12.1f} m  at JD {x[3]:.1f}')
