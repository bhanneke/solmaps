# solmaps transfer data v0.1: datasheet

DRAFT. Values marked TBD come from the finished run; every other number names the script that produced it.

## Motivation

The dataset lists what it costs to travel between 30 bodies of the solar system for every day from 1 November 2026 to
31 December 2100. It serves strategy research on settling the solar system (Deep Space Strategy): which places are
close to each other in cost and time, and how that changes from day to day over the century. Björn Hanneke (Goethe
University Frankfurt) created it with the solmaps engine; no funding body commissioned it.

## Composition

**Bodies (30).** The eight planets and Pluto; Ceres, Vesta, Psyche, Pallas, Hygiea, Themis and Juno in the main belt;
the near-Earth asteroids Eros, Bennu, Ryugu, Apophis, Didymos, Itokawa, 2008 EV5, 1996 FG3 and Nereus; the Jupiter
Trojans Eurybates, Polymele, Leucus, Orus and Patroclus. Nine moons and Earth–Moon L1 share their planet's
heliocentric legs; the engine prices them from the same data (`engine/conventions.py`).

**Instances.** One record per ordered pair of bodies (870), departure day (27,089) and transfer option (up to 10): a
Pareto set of flight time against cost, from the fastest to the cheapest option that day.

**Fields** (one file per origin body, `data/daily/<origin>.npz`; Parquet in the release):

| Field | Meaning | Unit, type |
| --- | --- | --- |
| `targets` | destination bodies | text |
| `tof` | flight time of each option | days, float32; NaN where a day has fewer than 10 options |
| `vinf` | excess speed relative to the departure body and to the arrival body | km/s, float16 (0.004 km/s resolution at 5 km/s) |
| `revs` | full revolutions around the Sun on the way | count, uint16 |
| `jd0`, `step` | first departure (Julian date, TDB) and step | 2461345.5, 1 day |

The files hold excess speeds; a cost follows from the end states: an Oberth burn from or into a parking orbit,
√(v∞² + 2μ/r) − √(μ/r), or the excess speed itself at bodies too small to orbit (`engine/conventions.py`, documented in
`docs/ENGINE.md`). Keeping speeds lets users price other end states without recomputing.

**Size.** TBD files, TBD GB compressed; about 2.36 billion option records (870 × 27,089 × 10, some empty).

## How solmaps computed the data

- **Positions.** Planets and Pluto: JPL DE440 through pykep until 2149, JPL Horizons barycentre states (DE441)
  afterwards; the two agree within 10 m (`flyby/bodies.py`). Small bodies: daily JPL Horizons state vectors
  2026–2205, fetched on 2026-10-31 (`flyby/fetch_horizons.py`), cubic Hermite interpolation between days. Bennu's
  Horizons solution ends on 2135-09-30; the data has no arrival at Bennu after that day.
- **Transfers.** For each pair and day: Lambert's problem (pykep, prograde) for 160 flight times, 100 log-spaced from 0.3
  Hohmann times to the longer of 2.5 Hohmann times and three orbits of the faster body, then 60 more to 100 years; every
  number of revolutions around the Sun the flight time allows, the cheapest kept; the three cheapest local minima
  refined; the Pareto set thinned to 10 options (`engine/daily.py`). TBD billion Lambert problems; TBD hours on 12 cores.
- **Time scale.** All dates are TDB. pykep's DE440 interface reads dates as UTC; solmaps corrects the 64.184 s offset
  (found during this work, `flyby/bodies.py`).
- **Environment.** Pinned container (`env/Dockerfile`: pykep 3.0.0, numpy 2.5.4, Python 3.14); code at commit TBD.

## Quality

| Check | Result | Script |
| --- | --- | --- |
| JPL Small-Body Mission-Design maps, 10 bodies, launches 2027–2035, 305,000 cells | JPL's solution is among solmaps' solutions in 97.7–99.98% of cells (arrival within 0.003 km/s, departure within 0.03 km/s); all within 0.07 km/s | `tests/external/check_mdesign.py` |
| NASA NHATS round trips, 7 trajectories | asteroid arrival and departure speeds within 0.001 km/s; Earth departure within 0.012 km/s (Earth's centre against the Earth–Moon barycentre) | `tests/test_nhats.py` |
| Second Lambert solver (numpy), 20,000 random transfers | same velocities within 4e-10 (relative) | `tests/test_vlambert.py` |
| Independent integration (scipy DOP853) of 400 transfers | arrival a median 43 m and at most 9.5 km from the target | `tests/harness/audit_network.py` |
| Lowest cost over all dates against the single-revolution data | unchanged within 0.00–0.18 km/s; no day undercuts it by more than 0.3 km/s | TBD script |
| Impossible values (negative or missing speeds, unordered options) | none (Earth origin; TBD all origins) | TBD script |
| Grid resolution against a 3,000-point scan with refinement | TBD (single-revolution data: median 0.0015 km/s, 99% within 0.27 km/s) | `tests/grid_error.py` |

## Known limits

- **Two-body arcs.** Each transfer is a Keplerian arc around the Sun. Over decades the planets' pull bends it; for flights
  longer than about 10 years the data idealises the path, and a real ship would need small correction burns. Departure and arrival speeds are
  exact for the arc; the path in between is not.
- **Impulsive burns, no gravity assists.** Flyby routes and low-thrust transfers form separate solmaps datasets.
- **Prograde transfers only.** Retrograde transfers are always far more expensive between these bodies.
- **Choice of solution.** For each flight time the data keeps the cheapest total of the two excess speeds as priced at
  each body's own end state. Mission-design tools often keep the lowest launch energy instead (JPL's maps do); both
  solutions exist, this dataset lists one.
- **Grid.** Daily departures and 160 flight times; narrow cost valleys next to the 180° transfer geometry can fall
  between grid points (see Quality).
- **Moons and L1** take their planet's options; the cheapest option for a moon can differ slightly from the
  cheapest for its planet.

## Uses

Intended: comparing places, dates and routes; network analysis over time; strategy studies and games built on travel
costs; teaching. Not intended: mission design without higher-fidelity tools (for example NASA GMAT); anything military.

## Distribution and licence

Zenodo (DOI TBD) and Hugging Face (`Deep-Space-Strategy/solmaps-transfers`); data under CC BY 4.0, code under MIT. Each
release archives the exact ephemeris files it used.

## Maintenance

Björn Hanneke maintains the dataset (hanneke@wiwi.uni-frankfurt.de; issues at github.com/bhanneke/solmaps). New
versions add bodies and correct errors; each version keeps its own DOI.

## Sources to cite

- Park, R. S., Folkner, W. M., Williams, J. G., & Boggs, D. H. (2021). The JPL Planetary and Lunar Ephemerides DE440 and
  DE441. The Astronomical Journal, 161(3), 105.
- JPL Horizons system and JPL Small-Body Database, NASA/JPL Solar System Dynamics (ssd.jpl.nasa.gov).
- Izzo, D. (2015). Revisiting Lambert's problem. Celestial Mechanics and Dynamical Astronomy, 121, 1–15 (pykep's solver).
- ESA pykep, version 3.0.0 (github.com/esa/pykep).
