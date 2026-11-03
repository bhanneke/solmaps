"""The computation jobs of solmaps, split into work units that anyone can run, submit and verify (python -m contrib).

Each job lists its units, the command that computes one unit inside the solmaps container, the files the unit writes,
and how a second run of the same unit is compared with the first:
  arrays  numerical results; deterministic code, so two runs agree to rounding (the tolerance allows for different
          processors and maths libraries)
  optimum an optimiser with random starts (the flyby search): a second run confirms a result when it finds an
          equally cheap or cheaper route in every case, within the tolerance
"""
import itertools

HELIO = ['earth', 'venus', 'mercury', 'mars', 'ceres', 'vesta', 'psyche', '433', '101955', '162173', 'jupiter', 'saturn',
         'uranus', 'neptune', 'pluto', '2', '10', '24', '3', '99942', '65803', '25143', '341843', '175706', '4660', '3548',
         '15094', '11351', '21900', '617']                    # engine/conventions.py HELIO (kept here: no imports needed)
WINDOWS = list(range(2027, 2098, 2))                        # two-year launch windows of the flyby search
FLY = '8 1000 60 6 3'                                        # flyby search budget: islands, generations, population, evolves, starts

class Job:
    def __init__(self, id, title, units, cmd, files, compare, tol, note=''):
        self.id, self.title, self.units, self.cmd, self.files, self.compare, self.tol, self.note = id, title, units, cmd, files, compare, tol, note

def flyby_job(id, title, pairs, note=''):
    units = [f'{o}-{t}-{y}' for o, t in pairs for y in WINDOWS]
    def cmd(u):
        o, t, y = u.split('-'); return ['python', 'flyby/routes3.py', o, t, y, y] + FLY.split()
    def files(u):
        o, t, y = u.split('-'); return [f'flyby/routes3_{o}_{t}_{y}_{y}.json']
    return Job(id, title, units, cmd, files, 'optimum', 0.05, note)

# flyby pairs in the maintainers' queues (flyby/run_queue_mini*.sh); every other pair of the 30 bodies is open
QUEUED = {'flyby-returns': [(o, t) for o in ('ceres', 'vesta', 'psyche', 'jupiter') for t in ('earth', 'mars')],
          'flyby-earth': [('earth', t) for t in ('jupiter', 'saturn', 'mercury', 'ceres', 'vesta', 'psyche', 'mars', 'venus', '433', '101955', '162173')],
          'flyby-mars': [('mars', t) for t in ('jupiter', 'saturn', 'ceres', 'vesta', 'psyche', 'earth', 'venus', 'mercury')],
          'flyby-saturn': [('saturn', t) for t in ('earth', 'mars')]}
COVERED = {p for v in QUEUED.values() for p in v}
OTHER = [(o, t) for o, t in itertools.permutations(HELIO, 2) if (o, t) not in COVERED]

JOBS = [
    Job('transfers', 'Daily transfer options between 30 bodies, 2026–2100, every number of revolutions, flights up to 100 years',
        HELIO, lambda u: ['python', '-m', 'engine.daily', 'origin', u, '8'], lambda u: [f'data/daily/{u}.npz'], 'arrays', 1e-6,
        'one unit = every route from one body: 29 routes, 27,089 days each'),
    Job('screening', 'Every asteroid and comet of the JPL Small-Body Database against Earth, Mars and Ceres, both directions, every day to 2100',
        [f'{u:04d}' for u in range(791)], lambda u: ['python', '-m', 'engine.screen', '4', str(int(u)), str(int(u))],
        lambda u: [f'data/screen_daily/unit_{u}.npz'], 'arrays', 1e-3, 'one unit = 2,000 objects; two-body orbits, for ranking'),
    flyby_job('flyby-returns', 'Flyby search: returns to Earth and Mars from Ceres, Vesta, Psyche and Jupiter', QUEUED['flyby-returns']),
    flyby_job('flyby-earth', 'Flyby search: from Earth to the planets, the belt and the near-Earth asteroids', QUEUED['flyby-earth']),
    flyby_job('flyby-mars', 'Flyby search: from Mars to the planets and the belt', QUEUED['flyby-mars']),
    flyby_job('flyby-saturn', 'Flyby search: from Saturn to Earth and Mars', QUEUED['flyby-saturn']),
    flyby_job('flyby-other', f'Flyby search: every other pair of the 30 bodies ({len(OTHER)} pairs)', OTHER,
              'one unit = one pair and one two-year window'),
    Job('cyclers', 'Earth–Mars cyclers, 2027–2097', ['all'], lambda u: ['python', 'flyby/cyclers.py', '2027', '2097', '8', '2000', '30', '6'],
        lambda u: ['flyby/cyclers_2027_2097.json'], 'optimum', 0.05, 'one unit: the whole scan'),
    Job('lowthrust', 'Low-thrust atlas: an electric ship on every site pair and two-year window', ['all'],
        lambda u: ['python', '-m', 'engine.lt_atlas'], lambda u: ['data/lowthrust_atlas.json'], 'arrays', 1e-3, 'one unit: the whole atlas'),
]
BY_ID = {j.id: j for j in JOBS}
