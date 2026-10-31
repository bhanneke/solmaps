"""Fetch transfer maps from the JPL Small-Body Mission-Design API (mode M) for an external check of the transfer data.

For each object: Earth-departure and object-arrival excess speeds over launch dates 2027-2035 and flight times 30-1500
days, every 10 days. Saved as tests/external/mdesign_<id>.json with the request URL and the date of the fetch.
Run on the host (network access): python3 tests/external/fetch_mdesign.py
"""
import json, pathlib, time, urllib.parse, urllib.request
HERE = pathlib.Path(__file__).resolve().parent
OBJECTS = ['433', '101955', '162173', '99942', '65803', '25143', '341843', '4660', '1', '4']
MJD0 = 61406                                       # 2027-01-01

if __name__ == '__main__':
    for des in OBJECTS:
        q = {'des': des, 'mjd0': MJD0, 'span': 3000, 'tof-min': 30, 'tof-max': 1500, 'step': 10}
        url = 'https://ssd-api.jpl.nasa.gov/mdesign.api?' + urllib.parse.urlencode(q)
        d = json.load(urllib.request.urlopen(url, timeout=300))
        if 'error' in d or 'vinf_dep' not in d:
            print(des, 'no map:', str(d)[:150]); continue
        keep = {k: d[k] for k in ('object', 'dep_date', 'tof', 'vinf_dep', 'vinf_arr') if k in d}
        keep.update({'source': url, 'fetched': time.strftime('%Y-%m-%d')})
        json.dump(keep, open(HERE / f'mdesign_{des}.json', 'w'))
        print(des, d['object'].get('fullname'), 'grid', len(d['tof']), 'x', len(d['dep_date']), '| orbit', d['object'].get('orbit_id'))
        time.sleep(2)
