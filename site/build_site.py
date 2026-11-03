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
    'atlas.html': root / 'atlas' / 'solar-system-atlas.html',
    'growth-map.html': root / 'network' / 'solar-system-growth-map.html',
    'solar-system-3d.html': root / 'atlas3d' / 'solar-system-3d.html',
    'station-siting.html': root / 'stations' / 'station-siting.html',
}
for name, src in pages.items():
    (docs / name).write_text(wrap(src.read_text()))
shutil.copy(root / 'site' / 'page.css', docs / 'page.css')
for p in sorted((root / 'network').glob('network_*.json')):     # longer flight-time limits, loaded by the pages on request
    shutil.copy(p, docs / p.name)
if (root / 'site' / 'progress.json').exists():
    shutil.copy(root / 'site' / 'progress.json', docs / 'progress.json')     # read by python -m contrib
(docs / '.nojekyll').write_text('')          # serve the files as they are
for p in sorted(docs.iterdir()):
    print(f'{p.name:24s} {p.stat().st_size:>10,d} bytes')
