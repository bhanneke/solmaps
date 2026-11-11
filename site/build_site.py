# Build the public site into docs/ for GitHub Pages: the three tools plus the landing page and documentation.
import pathlib, shutil, subprocess, sys

root = pathlib.Path(__file__).resolve().parent.parent
docs = root / 'docs'
docs.mkdir(exist_ok=True)

for script in ('atlas/build.py', 'network/build.py', 'atlas3d/build.py', 'stations/build.py'):
    subprocess.run([sys.executable, str(root / script)], check=True)

def wrap(html):
    # artifact pages are written without a document skeleton; standalone hosting needs one
    head = ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover"></head><body>\n')
    return head + html + '\n</body></html>\n'

pages = {
    'index.html': root / 'site' / 'index.html',
    'how-it-works.html': root / 'site' / 'how-it-works.html',
    'technical.html': root / 'site' / 'technical.html',
    'status.html': root / 'site' / 'status.html',
    'contribute.html': root / 'site' / 'contribute.html',
    'data.html': root / 'site' / 'data.html',
    'atlas.html': root / 'atlas' / 'solar-system-atlas.html',
    'growth-map.html': root / 'network' / 'solar-system-growth-map.html',
    'solar-system-3d.html': root / 'atlas3d' / 'solar-system-3d.html',
    'station-siting.html': root / 'stations' / 'station-siting.html',
}
for name, src in pages.items():
    (docs / name).write_text(wrap(src.read_text()))
shutil.copy(root / 'site' / 'page.css', docs / 'page.css')
if (root / 'network' / 'options').is_dir():                     # every option per route, for the trade-off view
    shutil.copytree(root / 'network' / 'options', docs / 'options', dirs_exist_ok=True)
if (root / 'atlas3d' / 'missions_tracks.json').exists():
    shutil.copy(root / 'atlas3d' / 'missions_tracks.json', docs / 'missions_tracks.json')   # live missions, loaded by the 3D atlas on request
for p in sorted((root / 'network').glob('network_*.json')) + sorted((root / 'network').glob('network30*.json')):
    shutil.copy(p, docs / p.name)                               # longer flight-time limits and all 30 bodies, loaded by the pages on request
if (root / 'site' / 'progress.json').exists():
    shutil.copy(root / 'site' / 'progress.json', docs / 'progress.json')     # read by python -m contrib
(docs / '.nojekyll').write_text('')          # serve the files as they are
for p in sorted(docs.iterdir()):
    print(f'{p.name:24s} {p.stat().st_size:>10,d} bytes')
# the documentation check runs with every build (GitHub Actions also runs it, when the account can run workflows)
check = subprocess.run([sys.executable, str(root / 'tests' / 'check_docs.py')], capture_output=True, text=True)
print(check.stdout.strip())
if check.returncode:
    print('DOCUMENTATION OUT OF DATE: fix the errors above before publishing (tests/check_docs.py)')
