"""Contribute computing to solmaps: run a work unit, verify someone else's, submit the result.

Inside the solmaps container, from the repository root (/work):
  python -m contrib list                          jobs, units, what is done and verified
  python -m contrib setup                         fetch the exact inputs of the published runs (ephemeris files, catalogue)
  python -m contrib run JOB [UNIT]                compute a unit (without UNIT: an open one)
  python -m contrib verify JOB [UNIT]             recompute a finished unit and compare it with the published result
  python -m contrib submit                        send results and receipts as a pull request to the contributions dataset

Every run writes a receipt (contrib/out/JOB/UNIT/receipt.json): the checksum of the result, a short summary, the code
commit and the library versions. Two runs of the same unit that agree within the job's tolerance verify it.
"""
import hashlib, json, os, platform, random, shutil, subprocess, sys, time, urllib.request
sys.path.insert(0, '/work'); sys.path.insert(0, '/work/flyby')
from contrib.jobs import JOBS, BY_ID

ROOT = '/work'
REPO = os.environ.get('SOLMAPS_CONTRIB_REPO', 'Deep-Space-Strategy/solmaps-contrib')   # Hugging Face dataset
PROGRESS = os.environ.get('SOLMAPS_PROGRESS', 'https://bhanneke.github.io/solmaps/progress.json')
OUT = f'{ROOT}/contrib/out'

def progress():
    try:
        return json.load(urllib.request.urlopen(PROGRESS, timeout=20))
    except Exception:
        return {}

# ---------- canonical checksums and comparisons ----------
def load(path):
    if path.endswith('.npz'):
        import numpy as np
        with np.load(path, allow_pickle=False) as d:
            return {k: d[k] for k in sorted(d.files)}
    return json.load(open(path))

def checksum(obj):
    h = hashlib.sha256()
    if isinstance(obj, dict) and obj and all(hasattr(v, 'dtype') for v in obj.values()):
        for k, v in obj.items():
            h.update(f'{k}|{v.dtype.str}|{v.shape}|'.encode()); h.update(v.tobytes())
    else:
        h.update(json.dumps(obj, sort_keys=True, separators=(',', ':')).encode())
    return h.hexdigest()

def compare_arrays(new, ref, tol):
    """largest difference over the numeric content; NaN where the other has a number counts as a difference"""
    import numpy as np
    worst = 0.0
    def num(a, b):
        nonlocal worst
        a, b = np.asarray(a, float), np.asarray(b, float)
        if a.shape != b.shape:
            worst = float('inf'); return
        nan = np.isnan(a) != np.isnan(b)
        if nan.any():
            worst = float('inf'); return
        ok = np.isfinite(a) & np.isfinite(b)
        if ok.any():
            worst = max(worst, float(np.max(np.abs(a[ok] - b[ok]))))
    def walk(a, b):
        if isinstance(a, dict) and isinstance(b, dict):
            for k in set(a) | set(b):
                if k not in a or k not in b:
                    num([0], [1e300]) if k not in ('seconds', 'built', 'started') else None
                elif k not in ('seconds', 'built', 'started'):
                    walk(a[k], b[k])
        elif isinstance(a, list) and isinstance(b, list):
            if len(a) != len(b):
                num([0], [1e300]); return
            for x, y in zip(a, b):
                walk(x, y)
        elif hasattr(a, 'dtype') or isinstance(a, (int, float)):
            if hasattr(a, 'dtype') and a.dtype.kind not in 'fiub':
                if not (a == b).all():
                    num([0], [1e300])
            else:
                num(a, b)
    walk(new, ref)
    return {'max_difference': worst, 'agrees': worst <= tol}

def compare_optimum(new, ref, tol):
    """per route and window: the second run confirms when it is as cheap or cheaper (within tol)"""
    key = lambda r: (r.get('target'), r.get('bin'), '-'.join(r.get('seq', [])), r.get('arrival'), r.get('origin'))
    R = {key(r): r for r in ref}; out = {'confirmed': 0, 'improved': 0, 'not_reached': 0, 'missing': 0}
    for r in new:
        q = R.get(key(r))
        if q is None:
            out['missing'] += 1
        elif r['dv'] < q['dv'] - tol:
            out['improved'] += 1
        elif r['dv'] <= q['dv'] + tol:
            out['confirmed'] += 1
        else:
            out['not_reached'] += 1
    out['agrees'] = out['not_reached'] == 0 and out['missing'] == 0
    return out

def summary(job, data):
    import numpy as np
    try:
        if job.id == 'transfers':
            return {'routes': int(data['tof'].shape[0]), 'options': int(np.isfinite(data['tof']).sum())}
        if job.id == 'screening':
            return {'objects': int(len(data['spkid'])), 'cheapest_kms': float(np.nanmin(data['best'][..., 0]))}
        if isinstance(data, list):
            dv = [r['dv'] for r in data if isinstance(r, dict) and 'dv' in r]
            return {'records': len(data), 'cheapest_kms': min(dv) if dv else None}
    except Exception:
        pass
    return {}

def environment():
    env = {'python': platform.python_version(), 'machine': platform.machine()}
    for m in ('numpy', 'pykep', 'pygmo', 'scipy'):
        try:
            env[m] = __import__(m).__version__
        except Exception:
            pass
    try:
        env['commit'] = subprocess.run(['git', '-C', ROOT, 'rev-parse', 'HEAD'], capture_output=True, text=True).stdout.strip() or os.environ.get('SOLMAPS_COMMIT', '')
    except Exception:
        env['commit'] = os.environ.get('SOLMAPS_COMMIT', '')
    return env

# ---------- commands ----------
def pick(job, mode):
    """an open unit (run) or a finished one with the fewest receipts (verify), chosen at random among the candidates
    so that several contributors rarely collide; the maintainers' queues work from the front, contributors from the back"""
    p = progress().get(job.id, {}); done = set(p.get('done', [])); n = p.get('receipts', {})
    if mode == 'run':
        cand = [u for u in job.units if u not in done][-50:]
    else:
        cand = sorted((u for u in job.units if u in done), key=lambda u: n.get(u, 0))[:50]
    if not cand:
        sys.exit(f'no unit to {mode} in {job.id}')
    return random.choice(cand)

def compute(job, unit):
    for f in job.files(unit):
        if os.path.exists(f'{ROOT}/{f}'):
            sys.exit(f'{f} exists already; move it away to compute this unit again')
    t = time.time()
    cmd = job.cmd(unit); print('running:', ' '.join(cmd), flush=True)
    subprocess.run(cmd, cwd=ROOT, check=True, env={**os.environ, 'PYTHONPATH': f'{ROOT}:{ROOT}/flyby'})
    return time.time() - t

def receipt(job, unit, seconds, extra=None):
    files, objs = [], []
    for f in job.files(unit):
        obj = load(f'{ROOT}/{f}'); objs.append(obj)
        files.append({'path': f, 'sha256': checksum(obj), 'bytes': os.path.getsize(f'{ROOT}/{f}')})
    r = {'job': job.id, 'unit': unit, 'files': files, 'summary': summary(job, objs[0]) if objs else {},
         'environment': environment(), 'seconds': round(seconds), 'created': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}
    if extra:
        r.update(extra)
    d = f'{OUT}/{job.id}/{unit}'; os.makedirs(d, exist_ok=True)
    name = f'{d}/receipt-{r["created"].replace(":", "")}.json'
    json.dump(r, open(name, 'w'), indent=1)
    return r, name

def cmd_list():
    p = progress()
    for j in JOBS:
        q = p.get(j.id, {}); done, ver = len(q.get('done', [])), sum(1 for v in q.get('receipts', {}).values() if v >= 2)
        print(f'{j.id:14s} {len(j.units):6d} units  done {done:6d}  verified {ver:6d}  {j.title}')

def cmd_setup():
    from huggingface_hub import snapshot_download
    snapshot_download(REPO, repo_type='dataset', allow_patterns=['inputs/*'], local_dir=f'{ROOT}/contrib/inputs')
    shutil.copytree(f'{ROOT}/contrib/inputs/inputs/horizons', f'{ROOT}/flyby/horizons', dirs_exist_ok=True)
    os.makedirs(f'{ROOT}/data/sbdb', exist_ok=True)
    shutil.copy(f'{ROOT}/contrib/inputs/inputs/catalog.npz', f'{ROOT}/data/sbdb/catalog.npz')
    print('inputs ready: flyby/horizons, data/sbdb/catalog.npz')

def cmd_run(job, unit):
    unit = unit or pick(job, 'run')
    secs = compute(job, unit)
    r, name = receipt(job, unit, secs)
    print(json.dumps(r['summary']), '\nreceipt:', name, '\nnext: python -m contrib submit')

def fetch_reference(job, unit):
    from huggingface_hub import hf_hub_download
    refs = []
    for f in job.files(unit):
        refs.append(hf_hub_download(REPO, f'results/{job.id}/{unit}/{os.path.basename(f)}', repo_type='dataset'))
    return refs

def cmd_verify(job, unit, ref_paths=None):
    unit = unit or pick(job, 'verify')
    refs = ref_paths or fetch_reference(job, unit)
    for f in job.files(unit):                            # the unit's output paths must be free for the recomputation
        if os.path.exists(f'{ROOT}/{f}'):
            os.replace(f'{ROOT}/{f}', f'{ROOT}/{f}.before-verify')
    secs = compute(job, unit)
    results = []
    for f, ref in zip(job.files(unit), refs):
        new, old = load(f'{ROOT}/{f}'), load(ref)
        c = compare_arrays(new, old, job.tol) if job.compare == 'arrays' else compare_optimum(new, old, job.tol)
        c.update(file=f, reference_sha256=checksum(old), identical=checksum(new) == checksum(old)); results.append(c)
    ok = all(c['agrees'] for c in results)
    r, name = receipt(job, unit, secs, {'verifies': results, 'agrees': ok})
    print(json.dumps(results, indent=1), '\nverdict:', 'agrees' if ok else 'DIFFERS', '\nreceipt:', name, '\nnext: python -m contrib submit')

def cmd_submit():
    from huggingface_hub import HfApi, CommitOperationAdd
    api = HfApi(); user = api.whoami()['name']; ops = []
    for job_id in sorted(os.listdir(OUT)) if os.path.isdir(OUT) else []:
        for unit in sorted(os.listdir(f'{OUT}/{job_id}')):
            d = f'{OUT}/{job_id}/{unit}'
            for rc in sorted(x for x in os.listdir(d) if x.startswith('receipt-')):
                r = json.load(open(f'{d}/{rc}')); r['contributor'] = user
                tmp = f'{d}/{rc}.signed'; json.dump(r, open(tmp, 'w'), indent=1)
                ops.append(CommitOperationAdd(f'receipts/{job_id}/{unit}/{user}-{rc}', tmp))
                if 'verifies' not in r:                          # first runs also send the result itself
                    for f in r['files']:
                        ops.append(CommitOperationAdd(f'results/{job_id}/{unit}/{os.path.basename(f["path"])}', f'{ROOT}/{f["path"]}'))
    if not ops:
        sys.exit('nothing to submit: run or verify a unit first')
    pr = api.create_commit(REPO, operations=ops, repo_type='dataset', create_pr=True,
                           commit_message=f'Contribution from {user}: {len([o for o in ops if "/receipts/" in "/" + o.path_in_repo])} receipts')
    print('pull request:', pr.pr_url)
    shutil.move(OUT, f'{OUT}-submitted-{time.strftime("%Y%m%d%H%M%S")}')

if __name__ == '__main__':
    a = sys.argv[1:]
    if not a or a[0] in ('-h', '--help', 'help'):
        print(__doc__); sys.exit()
    if a[0] == 'list':
        cmd_list()
    elif a[0] == 'setup':
        cmd_setup()
    elif a[0] == 'submit':
        cmd_submit()
    elif a[0] in ('run', 'verify') and len(a) >= 2 and a[1] in BY_ID:
        (cmd_run if a[0] == 'run' else cmd_verify)(BY_ID[a[1]], a[2] if len(a) > 2 else None)
    else:
        sys.exit(__doc__)
