"""Run every example of site/data.html against the published files, so the Data page cannot go stale unnoticed.
Blocks marked data-test="js" run with node, "python" with this interpreter (pandas and pyarrow needed: run in the solmaps
container), "curl" with curl; a curl failure only warns, since Hugging Face runs that service. Needs the internet.
    python3 tests/check_data_examples.py         (on the host: node, curl, and Python in a throwaway python:3.12-slim
                                                  container when pandas is not installed)
"""
import html, pathlib, re, shutil, subprocess, sys, tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
page = (ROOT / 'site' / 'data.html').read_text()
blocks = [(k, html.unescape(c)) for k, c in re.findall(r'<pre data-test="(\w+)"><code>(.*?)</code></pre>', page, re.S)]
only_js = '--js' in sys.argv
errors, warnings, ran = [], [], 0
for kind, code in blocks:
    if only_js and kind != 'js':
        continue
    with tempfile.TemporaryDirectory() as d:
        if kind == 'js':
            if not shutil.which('node'):
                warnings.append('node not found; JavaScript example skipped'); continue
            f = pathlib.Path(d) / 'ex.mjs'; f.write_text(code); cmd = ['node', str(f)]
        elif kind == 'python':
            f = pathlib.Path(d) / 'ex.py'; f.write_text(code); cmd = [sys.executable, str(f)]
            try:
                import pandas, pyarrow  # noqa: F401
            except ImportError:      # a clean user environment instead: pandas and pyarrow from pip, in a throwaway container
                cmd = ['docker', 'run', '--rm', '-v', f'{d}:/t:ro', 'python:3.12-slim', 'sh', '-c', 'pip install -q pandas pyarrow 2>/dev/null && python /t/ex.py']
        else:
            cmd = ['sh', '-c', code + ' --fail --silent --show-error']
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=600); ran += 1
        out = (r.stdout + r.stderr).strip().splitlines()
        if r.returncode:
            (warnings if kind == 'curl' else errors).append(f'{kind} example failed: {" | ".join(out[-3:])[:300]}')
        else:
            print(f'{kind} example ok: {(out[0] if out else "")[:160]}')
for w in warnings:
    print('warning:', w)
for e in errors:
    print('error:', e)
print(f'{ran} examples run, {len(errors)} errors, {len(warnings)} warnings')
sys.exit(1 if errors else 0)
