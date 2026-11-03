# Computation status: what solmaps has computed, what runs and what waits. Writes site/status.json and site/status.html.
# Reads the local data files and, over SSH, the Mac Mini's queue logs and result counts (if the Mini is reachable;
# otherwise the last known Mini state from site/status.json). Run on the host: python3 site/status.py
import glob, html, json, os, pathlib, re, subprocess, sys, time

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = pathlib.Path(os.environ.get('SOLMAPS_DATA', ROOT / 'data'))   # where data/daily lives
sys.path.insert(0, str(ROOT))
from engine.conventions import HELIO, SITES, PLACES

DAYS = 27089                                       # 2026-11-01 to 2100-12-31
LAMBERT_PER_DAY = 112                              # 100 flight times plus up to 12 refinement solutions

def mini():
    """queue logs and result counts from the Mac Mini, or None"""
    cmd = ('cd ~/solmaps && for q in queue.log queue2.log; do echo "== $q"; cat $q 2>/dev/null; done; '
           'echo "== counts"; for f in flyby/run3_*.log flyby/q2_*.log; do echo "$(basename $f) $(grep -c "^{" $f)"; done; '
           'echo "== lt"; python3 -c "import json;print(len(json.load(open(\'data/lowthrust_atlas.json\'))))" 2>/dev/null || echo 0; '
           'echo "== screen"; ls ~/solmaps-screen/data/screen 2>/dev/null | grep -c "^unit_[0-9]*.npz$"; '
           'echo "== screenlog"; tail -1 ~/solmaps-screen/screen.log 2>/dev/null; '
           'echo "== daily"; ls ~/solmaps-daily/data/daily 2>/dev/null | grep -c "^[a-z0-9]*.npz$"; '
           'echo "== dailyrun"; pgrep -f run_daily_mini.sh > /dev/null && echo running || echo stopped')
    try:
        out = subprocess.run(['ssh', '-o', 'ConnectTimeout=8', '-o', 'BatchMode=yes', 'bjoernmacmini', cmd],
                             capture_output=True, text=True, timeout=60).stdout
    except Exception:
        return None
    if '== counts' not in out:
        return None
    sec, cur = {}, None
    for line in out.splitlines():
        if line.startswith('== '):
            cur = line[3:]; sec[cur] = []
        elif cur:
            sec[cur].append(line)
    jobs = {}
    for q in ('queue.log', 'queue2.log'):
        for line in sec.get(q, []):
            m = re.match(r'(\S+ \S+) (start|end) (\S+)(?: \(attempt \d+\)| exit (\d+))?', line)
            if m:
                j = jobs.setdefault(m.group(3), {'queue': 1 if q == 'queue.log' else 2})
                if m.group(2) == 'start':
                    j['started'] = m.group(1)
                else:
                    j['ended'], j['exit'] = m.group(1), int(m.group(4) or 1)
    counts = dict(l.rsplit(' ', 1) for l in sec.get('counts', []) if ' ' in l)
    return {'jobs': jobs, 'counts': {k: int(v) for k, v in counts.items()}, 'lowthrust_rows': int((sec.get('lt') or ['0'])[0] or 0),
            'screen_units': int((sec.get('screen') or ['0'])[0] or 0), 'screen_log': (sec.get('screenlog') or [''])[0],
            'daily_done': int((sec.get('daily') or ['0'])[0] or 0), 'daily_running': (sec.get('dailyrun') or [''])[0] == 'running',
            'checked': time.strftime('%Y-%m-%d %H:%M')}

# the Mini queues as planned (flyby/run_queue_mini.sh, run_queue_mini2.sh); problems per job from the measured run times
QUEUE = [
    ('ceres:earth,mars', 'Flyby search, returns from Ceres', 1), ('vesta:earth,mars', 'Flyby search, returns from Vesta', 1),
    ('psyche:earth,mars', 'Flyby search, returns from Psyche', 1), ('jupiter:earth,mars', 'Flyby search, returns from Jupiter', 1),
    ('earth:jupiter,saturn,mercury', 'Flyby search rerun, Earth to Jupiter, Saturn, Mercury', 1),
    ('earth:ceres,vesta,psyche', 'Flyby search rerun, Earth to Ceres, Vesta, Psyche', 1),
    ('mars:jupiter,saturn', 'Flyby search rerun, Mars to Jupiter, Saturn', 1), ('mars:ceres,vesta,psyche', 'Flyby search rerun, Mars to the belt', 1),
    ('flyby_mars', 'Flyby search, Mars to Earth, Venus, Mercury', 2), ('flyby_earth', 'Flyby search, Earth to Mars, Venus, Eros, Bennu, Ryugu', 2),
    ('flyby_saturn', 'Flyby search, Saturn to Earth, Mars', 2), ('cyclers', 'Earth–Mars cyclers, 2027–2097', 2),
    ('lowthrust', 'Low-thrust atlas: electric ship, 132 routes, every two-year window', 2), ('trajectories', 'Sampled trajectories for every flyby result', 2),
]

def build():
    prev = json.load(open(ROOT / 'site' / 'status.json')) if (ROOT / 'site' / 'status.json').exists() else {}
    m = mini() or prev.get('mini')
    mm = m or {}
    eph = [p.stem for p in (ROOT / 'flyby' / 'horizons').glob('*.json')]
    rows = [
        {'group': 'Positions', 'name': 'Daily JPL Horizons states: 21 small bodies to 2205, planets 2140–2205',
         'done': len(eph), 'total': 30, 'unit': 'bodies', 'where': 'make ephemeris; archived with each data release'},
        {'group': 'Direct transfers', 'name': 'On the maps now: daily transfers for 30 bodies, 2026–2100, one revolution around the Sun at most, '
         '100 flight times per day', 'state': 'done', 'since': '2026-10-31',
         'note': '870 routes, about 2.6 billion Lambert solutions; the maps show 132 routes between 12 sites, every tenth day'},
        {'group': 'Direct transfers', 'name': 'For data release v0.1: every number of revolutions, flights up to 100 years on every route, '
         '740 flight times per day', 'done': mm.get('daily_done', 0), 'total': len(HELIO), 'unit': 'origins (29 routes each)',
         'note': ('running, about 3.6 hours per origin' if mm.get('daily_running') else 'not running') +
                 '. Then an audit, the documentation and the release on Zenodo and Hugging Face.'},
    ]
    jobs = (m or {}).get('jobs', {})
    for key, label, q in QUEUE:
        j = jobs.get(key) or jobs.get(key.replace(',', '_').replace(':', '_'), {})
        restarted = j.get('started', '') >= j.get('ended', '')                # a newer start after a failed end
        state = 'done' if j.get('exit') == 0 and j.get('ended') and not restarted else 'running' if j.get('started') and (restarted or not j.get('ended')) else 'failed, retrying' if j.get('ended') else 'queued'
        log = ('run3_' + key.replace(':', '_').replace(',', '_') if q == 1 else 'q2_' + key) + '.log'
        n = (m or {}).get('counts', {}).get(log)
        group = 'Cyclers' if 'cycler' in label else 'Low thrust' if 'Low-thrust' in label else 'Flyby routes'
        rows.append({'group': group, 'name': label, 'state': state, 'since': j.get('started', ''),
                     'note': f'{n:,} searches finished' if n and state != 'queued' else ''})
    sl = (m or {}).get('screen_log', '')
    sstate = ('running since ' + sl[:16]) if ' start ' in sl else 'finished' if 'finished' in sl \
        else 'paused until the transfer data run finishes' if mm.get('daily_running') else ('stopped ' + sl[:16]) if sl else ''
    rows.append({'group': 'Catalogue screening', 'name': 'Every object of the JPL Small-Body Database (1,580,428 bound orbits) against Earth, Mars '
                 'and Ceres, both directions, every 10 days to 2100', 'done': (m or {}).get('screen_units', 0), 'total': 791,
                 'unit': 'work units of 2,000 objects', 'note': (sstate + '; ' if sstate else '') +
                 'near-Earth objects first, then by brightness; two-body orbits, for ranking'})
    open_pairs = len(HELIO) * (len(HELIO) - 1) - 52
    rows.append({'group': 'Open for contributors', 'name': 'Flyby search for the remaining body pairs (36 two-year windows each)',
                 'done': 0, 'total': open_pairs, 'unit': 'pairs', 'note': 'work units and verification in preparation'})
    st = {'built': time.strftime('%Y-%m-%d %H:%M'), 'mini': m, 'rows': rows}
    json.dump(st, open(ROOT / 'site' / 'status.json', 'w'), indent=1)
    return st

def page(st):
    e = html.escape
    trs = []
    for r in st['rows']:
        if 'total' in r:
            pct = 100 * r['done'] / r['total'] if r['total'] else 0
            prog = (f'<div class="bar" role="img" aria-label="{pct:.0f}% done"><span style="width:{pct:.1f}%"></span></div>'
                    f'<span class="num">{r["done"]:,} of {r["total"]:,} {e(r["unit"])}</span>')
        else:
            prog = f'<span class="state {r["state"].split(",")[0]}">{e(r["state"])}</span>' + (f' <span class="num">since {e(r["since"])}</span>' if r.get('since') else '')
        extra = ''.join(f'<div class="note">{e(r[k])}</div>' for k in ('note', 'where') if r.get(k))
        trs.append(f'<tr><td>{e(r["group"])}</td><td>{e(r["name"])}{extra}</td><td>{prog}</td></tr>')
    mini_line = (f'Running jobs last checked {e(st["mini"]["checked"])}.' if st.get('mini') else 'The running jobs could not be checked.')
    return f'''<title>Computation status</title>
<meta name="description" content="What solmaps has computed, what runs now and what waits for contributors.">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Saira+Condensed:wght@600;700&family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400&display=swap">
<link rel="stylesheet" href="page.css">
<style>
.bar{{height:8px;border-radius:4px;background:var(--rule,#2a3448);overflow:hidden;margin:4px 0}}.bar span{{display:block;height:100%;background:#f2b84b;border-radius:4px}}
.num{{font-family:"IBM Plex Mono",monospace;font-size:12.5px;color:var(--dim,#8d99b0)}}.note{{font-size:12.5px;color:var(--dim,#8d99b0);margin-top:2px}}
.state{{font-size:12.5px;padding:1px 7px;border-radius:9px;border:1px solid currentColor}}.state.done{{color:#5cc28a}}.state.running{{color:#f2b84b}}.state.queued{{color:#8d99b0}}.state.failed{{color:#e0645a}}
</style>
<main>
  <p><a href="https://bhanneke.github.io/deep-space-strategy/">Deep Space Strategy</a> · <a href="index.html">solmaps</a> · <a href="how-it-works.html">How solmaps works</a> · <a href="technical.html">Technical documentation</a></p>
  <h1>Computation status</h1>
  <p class="lede">What solmaps has computed, what runs now and what waits. Updated {e(st["built"])}. {mini_line}</p>
  <p>This page is a snapshot: it changes when the site is rebuilt, usually once or twice a day while computations run.</p>
  <div class="tablewrap"><table>
    <thead><tr><th>Area</th><th>Dataset</th><th>Progress</th></tr></thead>
    <tbody>
      {chr(10).join(trs)}
    </tbody>
  </table></div>
  <p>Finished datasets go to Zenodo and Hugging Face with every release, with checksums and the exact ephemeris files used.</p>
</main>'''

if __name__ == '__main__':
    st = build()
    (ROOT / 'site' / 'status.html').write_text(page(st))
    for r in st['rows']:
        print(f"{r['group'][:22]:22s} {r['name'][:70]:70s} {r.get('state') or str(r['done']) + '/' + str(r['total'])}")
