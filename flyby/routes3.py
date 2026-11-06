# Flyby routes, third run. Changes against routes.py (second run):
#  - sequences generated for every origin-target pair: up to two flybys of Venus, Earth, Mars or Jupiter, kept when a
#    Tisserand-style energy screen puts them within SCREEN km/s of the direct route, plus the hand-made lists of runs 1-2
#  - small bodies on perturbed JPL Horizons orbits (bodies.py), planets on DE440
#  - leg flight times up to 2.5 Hohmann times (was 1.9)
#  - optimiser: ring-connected population search, then basin hopping on the best routes (optimizer_study*.py);
#    three independent runs per problem, twelve for two-flyby sequences; the spread is stored; interrupted runs resume
#  - arrival excess speed stored for every route; arrivals at Earth and Mars in two variants: propulsive capture into the
#    parking orbit, and aerocapture (assumed limits below)
#  - the full decision vector stored, so the pages can draw the optimiser's own trajectory
# Usage: python routes3.py ORIGIN TARGET[,TARGET] FIRST LAST ISLANDS GENS POP EVOLVES STARTS  (study setting: 8 1000 60 6 3)
import ctypes, json, math, os, sys, time, itertools
sys.path.insert(0, '/work/flyby')
import numpy as np
import pykep as pk, pygmo as pg
import bodies
from routes import PARK, park_burn, A, SEQS as OLD_SEQS

ATLAS = bodies.load_atlas()
FIT_LIB = os.environ.get('FLYBY_FIT_LIB', '/work/engine/fortran/flyby_fit.so')        # make fortran
TABLES = os.environ.get('FLYBY_TABLES', '/work/data/flyby_tables')                    # flyby/make_tables.py
OUT_OF_RANGE = 999.0
MU_SUN_KM = 1.32712440018e11
AU_KM = 149597870.7
FLYBY_BODIES = ['venus', 'earth', 'mars', 'jupiter']
SCREEN, MAX_SEQS = 2.0, 8
# Aerocapture assumptions (solmaps, to be checked against published studies): the ship brakes in the atmosphere when its
# arrival excess speed stays within the limit, then raises its periapsis with a small burn; above the limit it first
# brakes the excess at periapsis.
AERO = {'earth': {'vinf_max': 6.0, 'trim': 0.1}, 'mars': {'vinf_max': 7.0, 'trim': 0.1}}

def hohmann_days(a1, a2):
    return math.pi * math.sqrt(((a1 + a2) / 2) ** 3 / 2.9591220828e-4)

def leg_bounds(p, q):
    if p == q:                                    # resonant return to the same body
        per = 365.25 * A[p] ** 1.5
        return [0.8 * per, 2.2 * per]
    t = hohmann_days(A[p], A[q])
    return [max(30, 0.3 * t), min(5000, 2.5 * t)]

# ---- Tisserand-style screen (coplanar circular orbits, patched conics) ----
def vcirc(a):
    return math.sqrt(MU_SUN_KM / (a * AU_KM))

def leg_arrival_vinf(p, q, vinf):
    """excess speed at q after leaving p with excess speed vinf along p's orbital velocity (outward) or against it (inward);
    None if that orbit does not reach q"""
    rp, rq = A[p] * AU_KM, A[q] * AU_KM
    v = vcirc(A[p]) + (vinf if rq > rp else -vinf)
    eps = v * v / 2 - MU_SUN_KM / rp
    h = rp * v
    vq2 = 2 * (eps + MU_SUN_KM / rq)
    if vq2 <= 0:
        return None
    vt = h / rq
    if vt * vt > vq2 + 1e-9:
        return None
    vr = math.sqrt(max(vq2 - vt * vt, 0))
    return math.hypot(vt - vcirc(A[q]), vr)

def hohmann_vinf(p, q):
    a1, a2 = A[p], A[q]
    if a1 == a2:
        return 0.0
    at = (a1 + a2) / 2
    v1 = math.sqrt(MU_SUN_KM * (2 / (a1 * AU_KM) - 1 / (at * AU_KM)))
    return abs(v1 - vcirc(a1))

def screen_cost(seq):
    """rough energy cost of a sequence: departure burn, extra speed each flyby cannot supply, arrival burn"""
    cost = 0.0
    v = hohmann_vinf(seq[0], seq[1]) if seq[0] != seq[1] else 1.0
    cost += park_burn(v, seq[0])
    for i in range(1, len(seq)):
        p, q = seq[i - 1], seq[i]
        if p == q:                                 # resonant leg keeps the excess speed
            continue
        need = hohmann_vinf(p, q)
        if v < need:                               # a manoeuvre supplies what the flyby cannot
            cost += need - v; v = need
        arr = leg_arrival_vinf(p, q, v)
        if arr is None:
            return math.inf
        v = arr
    return cost + park_burn(v, seq[-1])

def sequences(origin, target):
    seqs = [[origin, target]]
    for n in (1, 2):
        for fb in itertools.product(FLYBY_BODIES, repeat=n):
            s = [origin, *fb, target]
            if sum(a == b for a, b in zip(s, s[1:])) > 1:      # at most one resonant return per route
                continue
            if any(s[i] == s[j] for i in range(len(s)) for j in range(i + 2, len(s))):   # no loops such as A-B-A
                continue
            seqs.append(s)
    direct = screen_cost([origin, target])
    kept = sorted((s for s in seqs[1:] if screen_cost(s) <= direct + SCREEN), key=screen_cost)
    old = [s for s in OLD_SEQS.get(origin, {}).get(target, []) if len(s) > 2]
    out = [[origin, target]]
    for s in old + kept:
        if s not in out and len(out) < MAX_SEQS:
            out.append(s)
    return out

# ---- optimisation ----
class Route:
    """departure burn from the origin's parking orbit + deep-space manoeuvres + arrival (capture or aerocapture), km/s"""
    def __init__(self, seq, t0, arrival):
        self.seq, self.origin, self.target, self.arrival = seq, seq[0], seq[-1], arrival
        base = dict(seq=[bodies.body(n, ATLAS) for n in seq], t0=t0, tof=[leg_bounds(a, b) for a, b in zip(seq, seq[1:])],
                    vinf=[0.5, 12.0], add_vinf_dep=False, tof_encoding='direct')
        self.with_arr = pk.trajopt.mga_1dsm(add_vinf_arr=True, **base)          # DSMs + arrival excess speed
        self.no_arr = pk.trajopt.mga_1dsm(add_vinf_arr=False, **base)           # DSMs only
        self.fast = None
    def __getstate__(self):                           # the compiled kernel is set up again in each worker
        s = dict(self.__dict__); s['fast'] = None
        return s
    def setup_fast(self):
        """the compiled fitness (engine/fortran/flyby_fit.f90), about ten times faster through pygmo; False if not built"""
        if not (os.path.exists(FIT_LIB) and all(os.path.exists(f'{TABLES}/{n}.npy') for n in self.seq)):
            self.fast = False
            return
        lib = ctypes.CDLL(FIT_LIB); D, I, dp, ip = ctypes.c_double, ctypes.c_int, ctypes.POINTER(ctypes.c_double), ctypes.POINTER(ctypes.c_int)
        tabs = [np.load(f'{TABLES}/{n}.npy', mmap_mode='r') for n in self.seq]; off, k = [], 0
        for t in tabs:
            off.append(k); k += t[1:].size
        big = np.concatenate([np.asarray(t[1:]).ravel() for t in tabs]); off = np.array(off, np.int32); nt = np.array([len(t) - 1 for t in tabs], np.int32)
        ts = np.array([t[0, 0] for t in tabs], float); hs = np.array([t[0, 1] for t in tabs], float); ph = [bodies.body(n, ATLAS) for n in self.seq]
        mu = np.array([getattr(b, 'mu_self', 0.0) for b in ph], float); rad = np.array([getattr(b, 'radius', 0.0) for b in ph], float)
        def park(n):
            return PARK.get(n, (0.0, 0.0))
        (m0, r0), (m1, r1) = park(self.origin), park(self.target); aero = self.arrival == 'aero'
        lim, trim = (AERO[self.target]['vinf_max'], AERO[self.target]['trim']) if aero else (0.0, 0.0)
        x = np.zeros(len(self.no_arr.get_bounds()[0])); out = np.zeros(3)
        args = (I(len(self.seq)), I(len(x)), I(1), x.ctypes.data_as(dp), big.ctypes.data_as(dp), off.ctypes.data_as(ip), nt.ctypes.data_as(ip), ts.ctypes.data_as(dp), hs.ctypes.data_as(dp),
                mu.ctypes.data_as(dp), rad.ctypes.data_as(dp), D(m0), D(r0), D(m1), D(r1), I(int(aero)), D(lim), D(trim), D(pk.MU_SUN), out.ctypes.data_as(dp))
        self.fast = (lib.flyby_fitness, args, x, out, big, off, nt, ts, hs, mu, rad)      # keeps the arrays alive
    def parts(self, x):
        dsm = self.no_arr.fitness(x)[0] / 1000.0
        vinf_arr = self.with_arr.fitness(x)[0] / 1000.0 - dsm
        return dsm, vinf_arr
    def arrive(self, vinf_arr):
        t = self.target
        if self.arrival == 'aero':
            lim = AERO[t]['vinf_max']
            excess = park_burn(vinf_arr, t) - park_burn(lim, t) if vinf_arr > lim else 0.0   # brake the excess at periapsis
            return excess + AERO[t]['trim']
        return park_burn(vinf_arr, t)                # capture into the parking orbit, or rendezvous at a small body
    def fitness(self, x):
        if self.fast is None:
            self.setup_fast()
        if self.fast:
            f, args, xv, out = self.fast[:4]
            xv[:] = x; f(*args)
            return [float(out[0])]
        return self.python_fitness(x)
    def python_fitness(self, x):
        try:
            dsm, vinf_arr = self.parts(x)
            return [park_burn(x[3] / 1000.0, self.origin) + dsm + self.arrive(vinf_arr)]
        except Exception as e:
            if 'INSUFFDATA' in str(e) or 'only valid' in str(e):
                return [OUT_OF_RANGE]
            raise
    def get_bounds(self):
        return self.no_arr.get_bounds()

def init_pool():
    """pygmo runs Python problems in a process pool, one worker per core by default; each worker holds pykep, the DE440
    kernel and the Horizons data (~200 MB). SOLMAPS_POOL caps the pool so a run fits a small Docker VM."""
    import os
    n = int(os.environ.get('SOLMAPS_POOL', '0'))
    if n:
        pg.mp_island.init_pool(n)

def solve(seq, t0, arrival, islands, gens, pop, evolves, seed):
    """Two stages (optimizer_study*.py, setting E): a population search on islands connected in a ring finds the region,
    then monotonic basin hopping with compass search refines the five best routes of every island."""
    udp = Route(seq, t0, arrival)
    prob = pg.problem(udp)
    archi = pg.archipelago(n=islands, t=pg.ring(), algo=pg.algorithm(pg.sade(gen=gens, variant=6, variant_adptv=2, memory=True)),
                           prob=prob, pop_size=pop, seed=seed)
    for _ in range(evolves):
        archi.evolve(); archi.wait_check()
    refine = pg.archipelago()
    for i, isl in enumerate(archi):
        src = isl.get_population()
        top = sorted(range(len(src)), key=lambda j: src.get_f()[j][0])[:5]
        p = pg.population(prob, 0, seed=seed + 1000 + i)
        for j in top:
            p.push_back(src.get_x()[j], src.get_f()[j])
        inner = pg.algorithm(pg.compass_search(max_fevals=10000, start_range=0.05, stop_range=1e-6))
        refine.push_back(algo=pg.algorithm(pg.mbh(inner, stop=5, perturb=0.05, seed=seed + 2000 + i)), pop=p)
    for _ in range(2):
        refine.evolve(); refine.wait_check()
    best = min((isl.get_population() for isl in refine), key=lambda q: q.champion_f[0])
    x = best.champion_x; f = udp.python_fitness(x)[0]        # the stored value always comes from the Python model
    tofs = [x[5]] + [x[9 + 4 * (i - 1)] for i in range(1, len(seq) - 1)]
    enc = [float(x[0])]
    for d in tofs:
        enc.append(enc[-1] + float(d))
    dsm, vinf_arr = udp.parts(x) if f < OUT_OF_RANGE else (None, None)
    return {'seq': seq, 'arrival': arrival, 'dv': round(float(f), 3), 'launch_mjd2000': round(float(x[0]), 2),
            'encounters_mjd2000': [round(e, 3) for e in enc], 'x': [float(v) for v in x],
            'vinf_dep': round(float(x[3]) / 1000, 3), 'dep_burn': round(park_burn(x[3] / 1000, seq[0]), 3),
            'dsm': None if dsm is None else round(dsm, 3), 'vinf_arr': None if vinf_arr is None else round(vinf_arr, 3),
            'tof_days': round(float(sum(tofs)), 1), 'arrival_mjd2000': round(enc[-1], 2)}

def main():
    init_pool()
    origin, targets = sys.argv[1], sys.argv[2].split(',')
    first, last = int(sys.argv[3]), int(sys.argv[4])
    budget = dict(islands=int(sys.argv[5]), gens=int(sys.argv[6]), pop=int(sys.argv[7]), evolves=int(sys.argv[8]))
    starts = int(sys.argv[9]) if len(sys.argv) > 9 else 3
    width, out = 2, []
    tag = f'{origin}_{"_".join(targets)}_{first}_{last}'
    path = f'/work/flyby/routes3_{tag}.json'
    import os
    if os.path.exists(path):                      # resume an interrupted run
        out = json.load(open(path))
    done = {(r['target'], r['bin'], '-'.join(r['seq']), r['arrival']) for r in out}
    for tgt in targets:
        seqs = sequences(origin, tgt)
        print('sequences', origin, tgt, ['-'.join(s) for s in seqs], flush=True)
        for y in range(first, last + 1, width):
            t0 = [pk.epoch(f'{y}-01-01').mjd2000, pk.epoch(f'{y + width}-01-01').mjd2000]
            for seq in seqs:
                for arrival in (['capture', 'aero'] if tgt in AERO else ['capture']):
                    if (tgt, f'{y}-{y + width - 1}', '-'.join(seq), arrival) in done:
                        continue
                    t = time.time()
                    # optimizer_study*.log: three independent runs, five for two-flyby sequences (the least reliable)
                    n = starts + (9 if len(seq) > 3 else 0)      # two-flyby sequences: 12 starts beat 5 on five of six test routes
                    runs = [solve(seq, t0, arrival, seed=y * 100 + k, **budget) for k in range(n)]
                    r = min(runs, key=lambda s: s['dv'])
                    r.update(origin=origin, target=tgt, bin=f'{y}-{y + width - 1}', feasible=bool(r['dv'] < OUT_OF_RANGE),
                             starts_dv=[s['dv'] for s in runs], seconds=round(time.time() - t, 1))
                    out.append(r)
                    print(json.dumps({k: v for k, v in r.items() if k != 'x'}), flush=True)
            json.dump(out, open(path, 'w'), indent=1)

if __name__ == '__main__':
    main()
