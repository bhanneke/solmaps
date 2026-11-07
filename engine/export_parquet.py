"""Export the daily transfer data to Parquet for the data release: one file per origin, one row per transfer option.

Columns: origin, target (text), departure (date), option (0 = fastest of that day), flight_days, vinf_departure_kms,
vinf_arrival_kms (excess speeds relative to the departure and arrival body), revolutions (full revolutions around the Sun),
closest_to_sun_au (closest distance to the Sun on the arc).
A check reads every file back and compares it value by value with its .npz. Run in the container from /work:
    python -m engine.export_parquet OUT_FOLDER [origin ...]
"""
import datetime as dt, json, os, sys
import numpy as np, pyarrow as pa, pyarrow.parquet as pq

SRC = '/work/data/daily'
D0 = dt.date(2026, 11, 1)                                   # JD 2461345.5

def export(origin, out):
    d = np.load(f'{SRC}/{origin}.npz'); targets = [str(t) for t in d['targets']]
    T, V, R = d['tof'], d['vinf'], d['revs']
    n_t, n_d, k = T.shape; ok = ~np.isnan(T)
    it, id_, io = np.nonzero(ok)
    epoch = (D0 - dt.date(1970, 1, 1)).days
    table = pa.table({
        'origin': pa.DictionaryArray.from_arrays(pa.array(np.zeros(len(it), np.int8)), pa.array([origin])),
        'target': pa.DictionaryArray.from_arrays(pa.array(it.astype(np.int8)), pa.array(targets)),
        'departure': pa.array((id_ + epoch).astype(np.int32), pa.int32()).cast(pa.date32()),
        'option': pa.array(io.astype(np.int8)),
        'flight_days': pa.array(T[ok]),
        'vinf_departure_kms': pa.array(V[..., 0][ok]),
        'vinf_arrival_kms': pa.array(V[..., 1][ok]),
        'revolutions': pa.array(R[ok]),
        'closest_to_sun_au': pa.array(d['sun_au'][ok]),
    })
    path = f'{out}/{origin}.parquet'
    pq.write_table(table, path + '.tmp', compression='zstd', compression_level=9, row_group_size=2_000_000)
    os.replace(path + '.tmp', path)
    back = pq.read_table(path)                               # read back and compare value by value
    assert back.num_rows == int(ok.sum())
    for col, ref in (('flight_days', T[ok]), ('vinf_departure_kms', V[..., 0][ok]), ('vinf_arrival_kms', V[..., 1][ok]), ('revolutions', R[ok]), ('closest_to_sun_au', d['sun_au'][ok])):
        assert np.array_equal(back[col].to_numpy(), ref), col
    assert np.array_equal(back['departure'].cast(pa.int32()).to_numpy(), (id_ + epoch).astype(np.int32))
    return {'origin': origin, 'rows': back.num_rows, 'bytes': os.path.getsize(path)}

if __name__ == '__main__':
    out = sys.argv[1]; os.makedirs(out, exist_ok=True)
    origins = sys.argv[2:] or sorted(f[:-4] for f in os.listdir(SRC) if f.endswith('.npz') and not f.endswith('.tmp.npz'))
    rows = []
    for o in origins:
        rows.append(export(o, out)); print(rows[-1], flush=True)
    print('rows', sum(r['rows'] for r in rows), 'bytes', sum(r['bytes'] for r in rows))
