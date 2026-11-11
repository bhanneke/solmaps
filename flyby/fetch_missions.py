"""Trajectories of spacecraft in flight for the Live missions view of the 3D atlas, from JPL Horizons: heliocentric
positions (AU, ecliptic J2000, the same frame as flyby/fetch_horizons.py) from launch to the end of the trajectory Horizons
holds, at most to 2100. Daily steps; every ten days for flights longer than 30 years (Voyager, New Horizons).

The mission facts (names, dates, events, sources) live in atlas3d/missions_registry.json, curated by hand from the
agencies' pages; this script reads the Horizons IDs from it, asks Horizons for each trajectory's span, and writes
atlas3d/missions_tracks.json with the positions and the date of the fetch. Run on the host:
    python3 flyby/fetch_missions.py
"""
import datetime, json, pathlib, re, sys, time, urllib.parse, urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
REG = ROOT / 'atlas3d' / 'missions_registry.json'
OUT = ROOT / 'atlas3d' / 'missions_tracks.json'
API = 'https://ssd.jpl.nasa.gov/api/horizons.api?'
MON = {m: i + 1 for i, m in enumerate(['JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN', 'JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC'])}

def query(params):
    u = API + urllib.parse.urlencode({'format': 'text', **params})
    for attempt in range(4):
        try:
            return urllib.request.urlopen(urllib.request.Request(u, headers={'User-Agent': 'solmaps-fetch'}), timeout=180).read().decode()
        except Exception:
            time.sleep(5 * (attempt + 1))
    raise RuntimeError('Horizons did not answer')

def vectors(hid, start, stop, step):
    return query({'COMMAND': f"'{hid}'", 'OBJ_DATA': 'NO', 'MAKE_EPHEM': 'YES', 'EPHEM_TYPE': 'VECTORS', 'CENTER': "'500@10'",
                  'REF_PLANE': "'ECLIPTIC'", 'REF_SYSTEM': "'ICRF'", 'OUT_UNITS': "'AU-D'", 'VEC_TABLE': "'1'", 'CSV_FORMAT': "'YES'",
                  'START_TIME': f"'{start}'", 'STOP_TIME': f"'{stop}'", 'STEP_SIZE': f"'{step}'"})

def span(hid):
    """first and last date of the trajectory, from Horizons' own 'no ephemeris prior to / after' messages"""
    a = re.search(r'prior to A\.D\. (\d{4})-([A-Z]{3})-(\d{2}) (\d\d:\d\d)', vectors(hid, '1960-01-01', '1960-01-02', '1 d'))
    b = re.search(r'after A\.D\. (\d{4})-([A-Z]{3})-(\d{2}) (\d\d:\d\d)', vectors(hid, '2150-01-01', '2150-01-02', '1 d'))
    iso = lambda m: f'{m.group(1)}-{MON[m.group(2)]:02d}-{m.group(3)} {m.group(4)}'
    return (iso(a) if a else None), (iso(b) if b else '2100-01-01 00:00')

def main():
    reg = json.load(open(REG)); out = {'fetched': time.strftime('%Y-%m-%d'), 'frame': 'heliocentric ecliptic J2000, AU', 'source': 'JPL Horizons', 'tracks': {}}
    for m in reg['missions']:
        hid = m.get('horizons_id')
        if not hid:
            continue
        t0, t1 = span(hid)
        if not t0:
            print(m['id'], 'no span from Horizons'); continue
        t0 = (datetime.datetime.strptime(t0, '%Y-%m-%d %H:%M') + datetime.timedelta(hours=1)).strftime('%Y-%m-%d %H:%M')   # an hour after the first state
        if t1 > '2100-01-01':
            t1 = '2100-01-01 00:00'
        years = int(t1[:4]) - int(t0[:4])
        step = '10 d' if years > 30 else '1 d'
        t = vectors(hid, t0, t1, step)
        body = t.split('$$SOE')[1].split('$$EOE')[0] if '$$SOE' in t else ''
        jd, xyz = [], []
        for line in body.strip().splitlines():
            f = [x.strip() for x in line.split(',')]
            if len(f) >= 5:
                jd.append(float(f[0])); xyz += [round(float(f[2]), 6), round(float(f[3]), 6), round(float(f[4]), 6)]
        if not jd:
            print(m['id'], 'no states'); continue
        out['tracks'][m['id']] = {'horizons_id': hid, 'jd0': jd[0], 'step_days': round(jd[1] - jd[0], 6) if len(jd) > 1 else 1, 'n': len(jd),
                                  'last_jd': jd[-1], 'xyz': xyz}
        print(f"{m['id']:16s} {hid:>6s} {t0} to {t1}, {len(jd)} states every {step}", flush=True); time.sleep(1)
    json.dump(out, open(OUT, 'w'), separators=(',', ':'))
    print('wrote', OUT, round(OUT.stat().st_size / 1e6, 2), 'MB')

if __name__ == '__main__':
    main()
