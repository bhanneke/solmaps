# Computation status: every solmaps job (contrib/jobs.py) with its work units, what is done, what runs and what is
# verified. Writes site/status.json, site/progress.json (read by python -m contrib to pick open units) and site/status.html.
# Reads the maintainers' compute queues over SSH (if reachable; otherwise the last known state from site/status.json)
# and the receipts in the contributions dataset on Hugging Face. Run on the host: python3 site/status.py
import html, json, os, pathlib, subprocess, sys, time, urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from contrib.jobs import JOBS, WINDOWS, QUEUED

CONTRIB = os.environ.get('SOLMAPS_CONTRIB_REPO', 'Deep-Space-Strategy/solmaps-contrib')
HOST = os.environ.get('SOLMAPS_QUEUE_HOST', 'bjoernmacmini')        # the maintainers' compute host (never shown on the page)
# the maintainers' queue jobs (flyby/run_flyby_mini.sh) and the registry job each belongs to
QUEUE = {'returns_ceres': 'flyby-returns', 'returns_vesta': 'flyby-returns', 'returns_psyche': 'flyby-returns', 'returns_jupiter': 'flyby-returns',
         'earth_outer': 'flyby-earth', 'earth_belt': 'flyby-earth', 'earth_near': 'flyby-earth', 'mars_outer': 'flyby-mars', 'mars_belt': 'flyby-mars',
         'mars_inner': 'flyby-mars', 'saturn_back': 'flyby-saturn', 'cyclers': 'cyclers', 'lowthrust': 'lowthrust'}

def queues():
    """job states, finished units and running jobs on the compute host, or None"""
    py = ("import json,glob\n"
          "for f in glob.glob('flyby/routes3_*.json'):\n"
          "  try:\n    rs=json.load(open(f))\n  except Exception:\n    continue\n"
          "  for r in rs: print('FLY',r.get('origin'),r.get('target'),r.get('bin'))\n")
    cmd = ('cd ~/solmaps-flyby && for q in queue.log; do echo "== $q"; cat $q 2>/dev/null; done; '
           f'echo "== fly"; python3 -c "{py}" 2>/dev/null | sort -u; '
           'echo "== screen"; ls ~/solmaps-screen/data/screen_daily 2>/dev/null | grep "^unit_[0-9]*.npz$"; '
           'echo "== screenlog"; tail -1 ~/solmaps-screen/screen.log 2>/dev/null; '
           'echo "== daily"; ls ~/solmaps-daily/data/daily 2>/dev/null | grep "^[a-z0-9]*.npz$"; '
           'echo "== dailyrun"; pgrep -f run_daily_mini.sh > /dev/null && echo running || echo stopped')
    try:
        out = subprocess.run(['ssh', '-o', 'ConnectTimeout=8', '-o', 'BatchMode=yes', HOST, cmd], capture_output=True, text=True, timeout=120).stdout
    except Exception:
        return None
    if '== fly' not in out:
        return None
    sec, cur = {}, None
    for line in out.splitlines():
        if line.startswith('== '):
            cur = line[3:]; sec[cur] = []
        elif cur:
            sec[cur].append(line)
    states = {}
    for q in ('queue.log',):
        for line in sec.get(q, []):
            p = line.split()
            if len(p) >= 4 and p[2] in ('start', 'end'):
                j = states.setdefault(p[3], {})
                j['started' if p[2] == 'start' else 'ended'] = p[0] + ' ' + p[1]
                if p[2] == 'end':
                    j['exit'] = int(p[-1]) if p[-1].lstrip('-').isdigit() else 1
    for j in states.values():
        restarted = j.get('started', '') >= j.get('ended', '')
        j['state'] = 'done' if j.get('exit') == 0 and j.get('ended') and not restarted else 'running' if j.get('started') else 'queued'
    fly = [l.split()[1:] for l in sec.get('fly', []) if l.startswith('FLY')]
    done = {'transfers': [l[:-4] for l in sec.get('daily', [])], 'screening': [l[5:9] for l in sec.get('screen', [])],
            'flyby': sorted({f'{o}-{t}-{b[:4]}' for o, t, b in fly if b})}
    return {'states': states, 'done': done, 'screen_log': (sec.get('screenlog') or [''])[0],
            'daily_running': (sec.get('dailyrun') or [''])[0] == 'running', 'checked': time.strftime('%Y-%m-%d %H:%M')}

def receipts():
    """agreeing receipts per job and unit in the contributions dataset ({} while it does not exist)"""
    try:
        tree = json.load(urllib.request.urlopen(f'https://huggingface.co/api/datasets/{CONTRIB}/tree/main/receipts?recursive=true', timeout=30))
    except Exception:
        return {}
    out = {}
    for f in tree:
        p = f.get('path', '').split('/')
        if f.get('type') == 'file' and len(p) == 4:
            out.setdefault(p[1], {}).setdefault(p[2], 0); out[p[1]][p[2]] += 1
    return out

def build():
    prev = json.load(open(ROOT / 'site' / 'status.json')) if (ROOT / 'site' / 'status.json').exists() else {}
    q = queues() or prev.get('queues') or {}
    rc = receipts()
    rows, progress = [], {}
    for job in JOBS:
        units = set(job.units)
        if job.id.startswith('flyby'):
            mine = [u for u in q.get('done', {}).get('flyby', []) if u in units]
        elif job.id in ('cyclers', 'lowthrust'):
            mine = ['all'] if q.get('states', {}).get(job.id, {}).get('state') == 'done' else []
        else:
            mine = [u for u in q.get('done', {}).get(job.id, []) if u in units]
        theirs = rc.get(job.id, {})
        done = sorted(set(mine) | set(theirs))
        count = {u: (1 if u in mine else 0) + theirs.get(u, 0) for u in done}
        verified = sum(1 for n in count.values() if n >= 2)
        runs = [q.get('states', {}).get(k, {}).get('state', 'queued') for k, j in QUEUE.items() if j == job.id]   # planned jobs count as queued
        if job.id == 'flyby-other':                  # second queue (flyby/run_more_mini.sh): one job per origin, other_<origin>
            runs = [s['state'] for k, s in q.get('states', {}).items() if k.startswith('other_')] or ['queued']
        if job.id == 'transfers':
            state = 'done' if len(done) >= len(units) else 'running' if q.get('daily_running') else 'queued'
        elif job.id == 'screening':
            sl = q.get('screen_log', '')
            state = 'done' if len(done) >= len(units) else 'running' if ' start ' in sl else 'queued'
        elif runs:
            state = 'running' if 'running' in runs else 'done' if all(s == 'done' for s in runs) and len(done) >= len(units) else 'queued'
        else:
            state = 'open for contributors'
        rows.append({'id': job.id, 'name': job.title, 'note': job.note, 'state': state, 'done': len(done), 'total': len(units), 'verified': verified})
        progress[job.id] = {'done': done, 'receipts': count}
    st = {'built': time.strftime('%Y-%m-%d %H:%M'), 'queues': q, 'rows': rows}
    json.dump(st, open(ROOT / 'site' / 'status.json', 'w'), indent=1)
    json.dump(progress, open(ROOT / 'site' / 'progress.json', 'w'), separators=(',', ':'))
    return st

def page(st):
    e = html.escape
    trs = []
    for r in st['rows']:
        pct = 100 * r['done'] / r['total'] if r['total'] else 0
        cls = 'done' if r['state'] == 'done' else 'running' if r['state'] == 'running' else 'queued'
        prog = (f'<div class="bar" role="img" aria-label="{pct:.0f}% done"><span style="width:{pct:.1f}%"></span></div>'
                f'<span class="num">{r["done"]:,} of {r["total"]:,} unit{"" if r["total"] == 1 else "s"}</span> <span class="state {cls}">{e(r["state"])}</span>')
        trs.append(f'<tr id="{r["id"]}"><td>{e(r["name"])}<div class="note">{e(r["note"])}</div></td><td>{prog}</td>'
                   f'<td class="num">{r["verified"]:,}</td><td><a href="contribute.html#{r["id"]}">Run or verify</a></td></tr>')
    checked = st.get('queues', {}).get('checked')
    when = f'Updated {e(st["built"])}' + (f'; running jobs checked {e(checked)}.' if checked else '.')
    return f'''<title>Computation status</title>
<meta name="description" content="What solmaps has computed, what runs now, what is verified, and how to contribute a work unit.">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Saira+Condensed:wght@600;700&family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400&display=swap">
<link rel="stylesheet" href="page.css">
<style>
.bar{{height:8px;border-radius:4px;background:var(--rule,#2a3448);overflow:hidden;margin:4px 0}}.bar span{{display:block;height:100%;background:#f2b84b;border-radius:4px}}
.num{{font-family:"IBM Plex Mono",monospace;font-size:12.5px;color:var(--dim,#8d99b0)}}.note{{font-size:12.5px;color:var(--dim,#8d99b0);margin-top:2px}}
.state{{font-size:12px;padding:1px 7px;border-radius:9px;border:1px solid currentColor;white-space:nowrap}}.state.done{{color:#5cc28a}}.state.running{{color:#f2b84b}}.state.queued{{color:#8d99b0}}
.call{{border:1px solid #f2b84b;border-radius:8px;padding:10px 14px}}
</style>
<main>
  <p><a href="https://bhanneke.github.io/deep-space-strategy/">Deep Space Strategy</a> · <a href="index.html">solmaps</a> · <a href="how-it-works.html">How solmaps works</a> · <a href="technical.html">Technical documentation</a></p>
  <h1>Computation status</h1>
  <p class="lede call">Anyone with Docker can help: from data release v0.1 on, pick a job below, compute one of its work units with a single command, or recompute a finished unit to verify it (<a href="contribute.html">how to contribute</a>).</p>
  <p>{when} The page is a snapshot of the latest site build. A unit counts as verified once two independent runs agree.</p>
  <div class="tablewrap"><table>
    <thead><tr><th>Job</th><th>Progress</th><th>Verified units</th><th></th></tr></thead>
    <tbody>
      {chr(10).join(trs)}
    </tbody>
  </table></div>
  <p>Inputs: daily JPL Horizons states for 21 small bodies to 2205 and the planets from 2140 to 2205, and the JPL Small-Body Database catalogue; every data release archives the exact files. Finished datasets go to Zenodo and Hugging Face with every release, with checksums.</p>
</main>'''

if __name__ == '__main__':
    st = build()
    (ROOT / 'site' / 'status.html').write_text(page(st))
    for r in st['rows']:
        print(f"{r['id']:14s} {r['done']:6d}/{r['total']:<6d} verified {r['verified']:<5d} {r['state']}")
