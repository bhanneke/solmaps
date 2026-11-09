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
(here / 'solar-system-3d.html').write_text(html)
print('built', len(html), 'bytes;', len(flyby), 'flyby routes;', sum('path' in r for r in flyby), 'with sampled trajectories')
