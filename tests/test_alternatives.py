"""Transfer alternatives: the cheapest reproduces the network; every set is a true trade-off of time against cost."""
import json, pathlib, sys
ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / 'flyby'))
import numpy as np, pytest

ALT = ROOT / 'data' / 'alternatives.npz'; NET = ROOT / 'network' / 'network.json'
pytestmark = pytest.mark.skipif(not (ALT.exists() and NET.exists()), reason='run make data first')

@pytest.fixture(scope='module')
def alts():
    from engine.data import Alternatives
    return Alternatives(ALT)

def test_cheapest_alternative_reproduces_the_network(alts):
    """The alternatives' flight-time grid holds the network's 30 values plus longer ones (to 2.5 Hohmann times). So the
    cheapest alternative never costs more than the network, and equals it when it flies within the network's grid."""
    import math
    from engine.alternatives import tof_grid
    net = json.load(open(NET))
    a_of = {}
    import bodies, network2
    atlas = bodies.load_atlas(str(ROOT / 'atlas' / 'atlas_dataset.json'))
    worst_within, cheaper = 0.0, []
    for r in net['routes']:
        hi = tof_grid(network2.mean_a(r['from'], atlas), network2.mean_a(r['to'], atlas))[29]
        for k in range(0, net['meta']['n'], 37):
            if r['dep'][k] is None:
                continue
            opts = alts.options(r['from'], r['to'], k)
            o = min(opts, key=lambda o: sum(alts.priced(o, r['from'], r['to'])))
            best, ref = sum(alts.priced(o, r['from'], r['to'])), r['dep'][k] + r['arr'][k]
            assert best <= ref + 0.011
            if o['tof'] <= hi * (1 + 1e-6):
                worst_within = max(worst_within, abs(best - ref))
            else:
                cheaper.append(ref - best)
    assert worst_within <= 0.011                            # the network rounds each burn to 0.01 km/s
    print(f'longer flights cheaper in {len(cheaper)} sampled route-dates, median saving {sorted(cheaper)[len(cheaper)//2]:.2f} km/s')

def test_alternatives_trade_time_against_cost(alts):
    for pair in ('earth>mars', 'mars>ceres', 'earth>jupiter', 'ceres>earth'):
        a, b = pair.split('>')
        for k in range(0, alts.n_dates, 101):
            opts = alts.options(a, b, k)
            assert 1 <= len(opts) <= 10
            costs = [sum(alts.priced(o, a, b)) for o in opts]
            tofs = [o['tof'] for o in opts]
            assert tofs == sorted(tofs)
            assert all(c1 > c2 - 1e-6 for c1, c2 in zip(costs, costs[1:]))   # slower is never dearer

def test_regression_earth_mars_november_2026(alts):
    # first network date: the cheapest Earth-Mars transfer costs 5.68 km/s (technical docs, launch windows)
    opts = alts.options('earth', 'mars', 0)
    assert min(sum(alts.priced(o, 'earth', 'mars')) for o in opts) == pytest.approx(5.68, abs=0.02)

def test_l1_departure_prices_the_same_heliocentric_leg(alts):
    o = alts.options('earth', 'mars', 0)[-1]
    leo, _ = alts.priced(o, 'earth', 'mars'); l1, _ = alts.priced(o, 'eml1', 'mars')
    assert l1 < leo                                         # the heliocentric leg is shared; only the end state differs
