"""Is the documentation up to date with the code? Standard library only; run from the repository root:
    python3 tests/check_docs.py
Exit 1 on any error (warnings do not fail). The GitHub workflow .github/workflows/docs-check.yml runs it on every push
and every Monday. Each check compares the documents with something the code itself defines, so a new view, command or
count shows up here until a document describes it.

Documents: README.md, docs/ENGINE.md, docs/DATASHEET.md, site/*.html (the sources of the public pages).
"""
import json, pathlib, re, sys, time

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
DOCS = ['README.md', 'docs/ENGINE.md', 'docs/DATASHEET.md'] + sorted(str(p.relative_to(ROOT)) for p in (ROOT / 'site').glob('*.html'))
TEXT = {d: (ROOT / d).read_text(errors='ignore') for d in DOCS}
ALL = '\n'.join(TEXT.values())
errors, warnings = [], []
err = lambda m: errors.append(m)
warn = lambda m: warnings.append(m)
plain = lambda t: re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', t))

# 1. every view and menu of the 3D atlas appears in How it works
atlas = (ROOT / 'atlas3d' / 'solar3d_template.html').read_text()
seg = re.search(r'aria-label="View">(.*?)</div>', atlas, re.S)
views = re.findall(r'<button[^>]*>([^<]+)</button>', seg.group(1)) if seg else []
if not views:
    err('could not read the view buttons of atlas3d/solar3d_template.html')
how = plain(TEXT['site/how-it-works.html']).lower().replace('-', ' ')
for v in views + ['Trips', 'Display', 'Bodies', 'Live missions']:
    if v.lower().replace('-', ' ') not in how:
        err(f'how-it-works.html does not describe the 3D atlas view or menu "{v}"')

# 2. every engine command and every mode of engine.daily and engine.lt_atlas appears in README.md or docs/ENGINE.md
eng = TEXT['README.md'] + TEXT['docs/ENGINE.md']
mods = set()
for p in list((ROOT / 'engine').glob('*.py')):
    s = p.read_text(errors='ignore')
    if "__name__ == '__main__'" in s:
        mods.add('engine.' + p.stem)
for m in sorted(mods):
    if m not in eng and m.split('.')[1] + '.py' not in eng:
        err(f'{m} has a command line but neither README.md nor docs/ENGINE.md mentions it')
for mod in ('daily', 'lt_atlas'):
    s = (ROOT / 'engine' / f'{mod}.py').read_text()
    for mode in sorted(set(re.findall(r"sys\.argv\[1\] == '(\w+)'", s)) | set(re.findall(r"mode == '(\w+)'", s))):
        if f'engine.{mod} {mode}' not in eng:
            err(f'"python -m engine.{mod} {mode}" is not documented in README.md or docs/ENGINE.md')

# 3. statements about the whole network match the code (partial counts such as "406 routes hold 740" are not checked)
from engine.conventions import HELIO, SITES
nb, ns = len(HELIO), len(SITES)
ok = {nb, nb * (nb - 1), ns, ns * (ns - 1)}
pats = [r'(?:between|connects|network of|all)\s+(\d[\d,]*)\s+(?:bodies|planets and asteroids|sites)',
        r'(\d[\d,]*)\s+(?:directed\s+|ordered\s+)?routes\s+between',
        r'(\d[\d,]*)\s+(?:bodies|sites)\s*,\s*(?:\d[\d,]*)\s+(?:directed\s+)?routes']
for d, t in TEXT.items():
    for pat in pats:
        for num in re.findall(pat, plain(t), re.I):
            if int(num.replace(',', '')) not in ok:
                err(f'{d}: "{num}" in a statement about the whole network fits none of the counts the code defines ({sorted(ok)})')

# 4. one Lambert count and one DOI everywhere
for d, t in TEXT.items():
    for x in re.findall(r'([\d.]+) billion Lambert', plain(t)):
        if x != '18.8':
            err(f'{d}: "{x} billion Lambert" (the data needs at most 23,567,430 x 796 = 18.8 billion)')
dois = set(re.findall(r'10\.5281/zenodo\.\d+', ALL + (ROOT / 'CITATION.cff').read_text()))
if len(dois) > 1:
    err(f'more than one Zenodo DOI in the documents: {sorted(dois)}')

# 5. phrasings that were wrong once must not come back
for line in (ROOT / 'tests' / 'stale_phrases.txt').read_text().splitlines():
    ph = line.split('#')[0].strip()
    if not ph:
        continue
    for d, t in TEXT.items():
        if ph.lower() in plain(t).lower():
            err(f'{d}: outdated phrase "{ph}"')

# 6. links between the pages resolve (targets in site/ or the built docs/), with their anchors
for d in DOCS:
    if not d.startswith('site/'):
        continue
    for href in re.findall(r'href="([^"]+)"', TEXT[d]):
        if href.startswith(('http', 'mailto:', '#', 'javascript:')) or '${' in href:
            continue
        f, _, anchor = href.partition('#')
        target = next((q for q in (ROOT / 'site' / f, ROOT / 'docs' / f) if q.exists()), None)
        if target is None:
            err(f'{d}: link to {href} has no target in site/ or docs/')
        elif anchor and target.suffix == '.html' and f'id="{anchor}"' not in target.read_text(errors='ignore') and 'route=' not in anchor and 'body=' not in anchor:
            err(f'{d}: link to {href}: no element with id "{anchor}"')

# 7. the status page is recent
st = ROOT / 'site' / 'status.json'
if st.exists():
    built = json.loads(st.read_text()).get('built', '')
    try:
        age = (time.time() - time.mktime(time.strptime(built[:10], '%Y-%m-%d'))) / 86400
        if age > 14:
            warn(f'the status page was built {age:.0f} days ago (python3 site/status.py, then the site build)')
    except ValueError:
        warn('site/status.json has no build date')

for w in warnings:
    print('warning:', w)
for e in errors:
    print('error:', e)
print(f'{len(errors)} errors, {len(warnings)} warnings, {len(DOCS)} documents checked')
sys.exit(1 if errors else 0)
