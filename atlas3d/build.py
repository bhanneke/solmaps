import json, pathlib
here = pathlib.Path(__file__).parent
root = here.parent
j = lambda o: json.dumps(o, ensure_ascii=False, separators=(',', ':')).replace('</', '<\\/')
data = json.load(open(root / 'atlas' / 'atlas_dataset.json'))
extra = json.load(open(here / 'extra_bodies.json'))['bodies']          # atlas3d/fetch_extra_bodies.py: Pallas, the Trojans, ...
data['bodies'] += [b for b in extra if b['id'] not in {x['id'] for x in data['bodies']}]
data['transfer_bodies'] = [n['id'] for n in json.load(open(root / 'network' / 'network30.json'))['nodes']] if (root / 'network' / 'network30.json').exists() else []
net = json.load(open(root / 'network' / 'network.json'))
flyby = []
for p in sorted((root / 'flyby').glob('routes2_*.json')):
    flyby += json.load(open(p))
paths = {}
for p in sorted((root / 'flyby').glob('paths_*.json')):
    paths.update(json.load(open(p)))
for r in flyby:                                   # the optimiser's sampled trajectory, where trajectories.py made one
    key = f"{r.get('origin', 'earth')}|{r['target']}|{r['launch_mjd2000']}|{'-'.join(r['seq'])}"
    if key in paths:
        r['path'] = paths[key]
    r.pop('x', None)
html = (here / 'solar3d_template.html').read_text()
# stations of the best refuelling sets (k = 1..5), with their transfers to each other and to the sites
pairs = json.load(open(root / 'stations' / 'pairs.json'))
stn = json.load(open(root / 'stations' / 'stations.json'))
sets = [s['stations'] for s in stn['network']['sets']]
keep = sorted(set(c for s in sets for c in s))
pos = {n['index']: i for i, n in enumerate(pairs['nodes'])}
sub = [pos[c] for c in keep]
stj = {'epoch_jd': pairs['epoch_jd'], 'step_days': pairs['step_days'], 'sites': pairs['sites'],
       'nodes': [pairs['nodes'][i] for i in sub], 'sets': [[keep.index(c) for c in s] for s in sets],
       'nn': {k: [[pairs['node_node'][k][i][j] for j in sub] for i in sub] for k in ('cost', 'tof')},
       'ns': {k: [pairs['node_site'][k][i] for i in sub] for k in ('cost', 'tof')},
       'sn': {k: [[row[i] for i in sub] for row in pairs['site_node'][k]] for k in ('cost', 'tof')}}
html = html.replace('/*ATLAS_DATA*/', j(data)).replace('/*NET*/', j(net)).replace('/*FLYBY*/', j(flyby)).replace('/*ENGINE*/', (root / 'network' / 'engine.js').read_text()).replace('/*STNJ*/', j(stj))
# mission planner: its own script and data (parking orbits, aerocapture limits as flyby/routes3.AERO, ship presets)
import sys; sys.path.insert(0, str(root))
from engine.conventions import PARKING, HELIO
from engine.ship import PRESETS
pidx = json.load(open(root / 'network' / 'planner' / 'index.json')) if (root / 'network' / 'planner' / 'index.json').exists() else {'jd0': 2461345.5, 'step_days': 10, 'dates': 2709, 'k': 10}
mission = {'hub': 'https://huggingface.co/datasets/Deep-Space-Strategy/solmaps-transfers/resolve/main/planner/v0.1',
           'jd0': pidx['jd0'], 'step_days': pidx['step_days'], 'dates': pidx['dates'], 'k': pidx['k'], 'bodies': list(HELIO),
           'parking': {k: {'mu': v['mu'], 'r': v['r'], 'label': v['label']} for k, v in PARKING.items()},
           'aero': {'earth': {'vinf_max': 6.0, 'trim': 0.1}, 'mars': {'vinf_max': 7.0, 'trim': 0.1}}, 'a_continuous': 4e-3,
           'presets': {k: v.to_dict() for k, v in PRESETS.items()}}
html = html.replace('/*MISSION_DATA*/', j(mission)).replace('/*MISSION_JS*/', (here / 'mission.js').read_text())
(here / 'solar-system-3d.html').write_text(html)
print('built', len(html), 'bytes;', len(flyby), 'flyby routes;', sum('path' in r for r in flyby), 'with sampled trajectories')
