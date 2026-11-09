# Bodies for solmaps: planets and Pluto from JPL DE440 (to about 2150); small bodies from JPL Horizons states, or SBDB
# elements where no Horizons file exists.
import json, math
import pykep as pk

PLANETS = ('mercury', 'venus', 'earth', 'mars', 'jupiter', 'saturn', 'uranus', 'neptune', 'pluto')
NAIF = {'mercury': 'MERCURY BARYCENTER', 'venus': 'VENUS BARYCENTER', 'earth': 'EARTH BARYCENTER',
        'mars': 'MARS BARYCENTER', 'jupiter': 'JUPITER BARYCENTER', 'saturn': 'SATURN BARYCENTER',
        'uranus': 'URANUS BARYCENTER', 'neptune': 'NEPTUNE BARYCENTER', 'pluto': 'PLUTO BARYCENTER'}
# pykep's jpl_lp table has no Pluto: GM (m^3/s^2) and radius (m) from the NASA NSSDC Pluto fact sheet
PHYS_EXTRA = {'pluto': (8.696e11, 1.1883e6)}

_DE_CACHE = {}
def _de440(name):
    """One DE440 object per planet and process: the SPICE kernel loads once per worker, not on every hand-over."""
    if name not in _DE_CACHE:
        _DE_CACHE[name] = pk.udpla.de440s(NAIF[name], 'ECLIPJ2000', 'SUN')
    return _DE_CACHE[name]

# pykep's de440s converts MJD2000 to ephemeris time as if it were UTC (offset of 2000-01-01 00:00 UTC); every date in
# solmaps is TDB, as in the Horizons files. Without this correction the planets ran 64.184 s (TDB - UTC in 2000) ahead
# of the small bodies, about 2,000 km along Earth's orbit (found 2026-10-31 by comparing DE440 with Horizons).
TDB_FIX = 64.184 / 86400
DE440_END = 54750.0                                   # MJD2000 2149-11-24: switch to the Horizons files before the kernel ends
_LATE = {}
def _late(name):
    if name not in _LATE:
        _LATE[name] = HorizonsBody('planet_' + name)
    return _LATE[name]

def coverage_end(name):
    """last MJD2000 with positions for a body (Horizons files end early for some small bodies, Bennu in 2135)"""
    if name in PLANETS:
        return _late(name).t1
    return HorizonsBody(name).t1 if small_body_horizons_available(name) else float('inf')

class DE440Planet:
    """Heliocentric DE440 positions with the physical constants that flybys need.

    The small DE440 kernel shipped with pykep holds planet-system barycentres only. Earth's entry is
    the Earth-Moon barycentre, which lies about 4,700 km from Earth's centre; for heliocentric legs
    that offset is negligible. Mass, radius and safe flyby radius come from pykep's jpl_lp planets.
    """
    def __init__(self, name):
        self.name = name
        self.de = None
        if name in PHYS_EXTRA:
            self.mu_self, self.radius = PHYS_EXTRA[name]; self.safe = 1.1 * self.radius
        else:
            ref = pk.planet(pk.udpla.jpl_lp(name))
            self.mu_self, self.radius, self.safe = ref.get_mu_self(), ref.get_radius(), ref.get_safe_radius()
    def __getstate__(self):
        # pygmo copies problems into worker processes; the SPICE kernel must be loaded again there
        state = dict(self.__dict__); state['de'] = None
        return state
    def eph(self, mjd2000):
        if mjd2000 > DE440_END:                      # pykep's de440s ends in 2150: Horizons barycentre states (DE441)
            return _late(self.name).eph(mjd2000)
        if self.de is None:
            self.de = _de440(self.name)
        return self.de.eph(mjd2000 - TDB_FIX)
    def acc(self, mjd2000):
        """heliocentric acceleration (m/s^2): the Sun's gravity at the body; low-thrust gradients need it"""
        r = self.eph(mjd2000)[0]
        n = (r[0] ** 2 + r[1] ** 2 + r[2] ** 2) ** 1.5
        return [-pk.MU_SUN * x / n for x in r]
    def get_name(self):
        return self.name
    def get_mu_central_body(self):
        return pk.MU_SUN
    def get_mu_self(self):
        return self.mu_self
    def get_radius(self):
        return self.radius
    def get_safe_radius(self):
        return self.safe

def small_body(bid, atlas):
    el = {b['id']: b for b in atlas['bodies']}[bid]['orbit']['elements']
    ep = pk.epoch(el['epoch_jd_tdb'] - 2451544.5)
    elem = [el['a_au'] * pk.AU, el['e'], math.radians(el['i_deg']), math.radians(el['node_deg']),
            math.radians(el['arg_peri_deg']), math.radians(el['M_deg'])]
    return pk.planet(pk.udpla.keplerian(ep, elem, pk.MU_SUN, bid, [-1, -1, -1], pk.el_type.KEP_M))

HORIZONS_DIR = '/work/flyby/horizons'
AU_M, DAY_S = pk.AU, 86400.0
# GM (m^3/s^2) and radius (m) for flyby bookkeeping; the small bodies are never flyby bodies in solmaps
SMALL_PHYS = {'ceres': (6.263e10, 470e3), 'vesta': (1.729e10, 262e3), 'psyche': (1.53e9, 113e3)}

class HorizonsBody:
    """Perturbed JPL Horizons states (daily since 2026-10-31), cubic Hermite interpolation of position and velocity.

    Horizons integrates each small body with planetary perturbations, so its positions stay accurate over the
    decades the network covers; two-body motion from fixed elements drifts. Same pykep interface as DE440Planet.
    """
    def __init__(self, name):
        import numpy as np
        d = json.load(open(f'{HORIZONS_DIR}/{name}.json'))
        self.name, self.rows = name, np.asarray(d['rows'], dtype=np.float64)   # 3.7 MB per daily body; lists took ~15 MB
        self.t0, self.h = self.rows[0][0] - 2451544.5, self.rows[1][0] - self.rows[0][0]
        self.t1 = self.rows[-1][0] - 2451544.5
        self.mu_self, self.radius = SMALL_PHYS.get(name, (1.0, 1e3))
    def eph(self, mjd2000):
        if mjd2000 != mjd2000:                     # NaN from an optimiser's trial point: an invalid state it discards, as for the planets
            nan = float('nan'); return [nan] * 3, [nan] * 3
        if not self.t0 <= mjd2000 <= self.t1:
            raise ValueError(f'{self.name}: no Horizons states for MJD2000 {mjd2000:.1f} (covered {self.t0:.0f}-{self.t1:.0f})')
        u = (mjd2000 - self.t0) / self.h
        i = min(max(int(math.floor(u)), 0), len(self.rows) - 2)
        s = u - i
        a, b = self.rows[i], self.rows[i + 1]
        h00, h10, h01, h11 = 2*s**3 - 3*s**2 + 1, s**3 - 2*s**2 + s, -2*s**3 + 3*s**2, s**3 - s**2
        d00, d10, d01, d11 = 6*s**2 - 6*s, 3*s**2 - 4*s + 1, -6*s**2 + 6*s, 3*s**2 - 2*s
        r = [h00*a[1+k] + h10*self.h*a[4+k] + h01*b[1+k] + h11*self.h*b[4+k] for k in range(3)]
        v = [(d00*a[1+k] + d10*self.h*a[4+k] + d01*b[1+k] + d11*self.h*b[4+k]) / self.h for k in range(3)]
        return [x * AU_M for x in r], [x * AU_M / DAY_S for x in v]
    def acc(self, mjd2000):
        """heliocentric acceleration (m/s^2): the Sun's gravity at the body; low-thrust gradients need it"""
        r = self.eph(mjd2000)[0]
        n = (r[0] ** 2 + r[1] ** 2 + r[2] ** 2) ** 1.5
        return [-pk.MU_SUN * x / n for x in r]
    def get_name(self):
        return self.name
    def get_mu_central_body(self):
        return pk.MU_SUN
    def get_mu_self(self):
        return self.mu_self
    def get_radius(self):
        return self.radius
    def get_safe_radius(self):
        return self.radius * 1.1

def small_body_horizons_available(name):
    import os
    return os.path.exists(f'{HORIZONS_DIR}/{name}.json')

_cache = {}
def body(name, atlas):
    if name not in _cache:
        if name in PLANETS:
            _cache[name] = pk.planet(DE440Planet(name))
        elif small_body_horizons_available(name):
            _cache[name] = pk.planet(HorizonsBody(name))
        else:
            _cache[name] = small_body(name, atlas)
    return _cache[name]

def load_atlas(path='/work/atlas/atlas_dataset.json'):
    return json.load(open(path))
