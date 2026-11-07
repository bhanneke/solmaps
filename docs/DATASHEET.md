# solmaps transfer data v0.1: datasheet

Release candidate. Every number names the script that produced it. The Zenodo DOI follows with the release.

## Motivation

The dataset lists what it costs to travel between 30 bodies of the solar system for every day from 1 November 2026 to
31 December 2100, with flights of up to 100 years. It serves strategy research on settling the solar system (Deep Space
Strategy): which places lie close to each other in cost and time, and how that changes from day to day over the century.
Björn Hanneke (Goethe University Frankfurt) created it with the solmaps engine; no funding body commissioned it.

## Composition

**Bodies (30).** The eight planets and Pluto; Ceres, Vesta, Psyche, Pallas, Hygiea, Themis and Juno in the main belt; the
near-Earth asteroids Eros, Bennu, Ryugu, Apophis, Didymos, Itokawa, 2008 EV5, 1996 FG3 and Nereus; the Jupiter Trojans
Eurybates, Polymele, Leucus, Orus and Patroclus. Nine moons and Earth–Moon L1 share their planet's heliocentric legs; the
engine prices them from the same data (`engine/conventions.py`). "Earth" in this dataset means the Earth–Moon barycentre.

**Identifiers.** Files name planets, Pluto, Ceres, Vesta and Psyche in lower case and the other bodies by asteroid number:

| ID | Body | ID | Body | ID | Body |
| --- | --- | --- | --- | --- | --- |
| `2` | Pallas | `433` | Eros | `25143` | Itokawa |
| `3` | Juno | `3548` | Eurybates | `65803` | Didymos |
| `10` | Hygiea | `4660` | Nereus | `99942` | Apophis |
| `24` | Themis | `11351` | Leucus | `101955` | Bennu |
| `617` | Patroclus | `15094` | Polymele | `162173` | Ryugu |
| `21900` | Orus | `175706` | 1996 FG3 | `341843` | 2008 EV5 |

**Instances.** One record per ordered pair of bodies (870), departure day (27,089) and transfer option (up to 10): a Pareto
set of flight time against cost, from the fastest to the cheapest option that day.

**Files.** The release holds Parquet and npz, one file per origin. Parquet has one row per option (`engine/export_parquet.py`):

| Column | Meaning | Unit, type |
| --- | --- | --- |
| `origin`, `target` | departure and arrival body (IDs above) | text |
| `departure` | departure date, TDB | date |
| `option` | position in the day's set; 0 is the fastest | integer |
| `flight_days` | flight time | days, float32 |
| `vinf_departure_kms`, `vinf_arrival_kms` | excess speed relative to the departure and the arrival body | km/s, float32 |
| `revolutions` | full revolutions around the Sun | count, uint16 |
| `closest_to_sun_au` | closest distance to the Sun on the arc | AU, float32 |

The engine reads the same values from `<origin>.npz`, with arrays of shape (targets, days, options): `tof`, `vinf` (with a
last axis for departure and arrival), `revs`, `sun_au`, plus `targets`, `jd0` (2461345.5, TDB) and `step` (1 day). `tof` holds
NaN where a day has fewer than 10 options.

**From speed to cost.** The files hold excess speeds, so users can price other end states without recomputing. The dataset's
own choice of options uses this cost, summed over both ends (`engine/conventions.py`). At ten bodies an Oberth burn connects
to a parking orbit, √(v∞² + 2μ/r) − √(μ/r):

| Body | μ (km³/s²) | Orbit radius r (km) | | Body | μ (km³/s²) | Orbit radius r (km) |
| --- | --- | --- | --- | --- | --- | --- |
| Earth | 398,600.4 | 6,678 | | Jupiter | 126,686,534 | 1,882,700 (Callisto's distance) |
| Venus | 324,858.6 | 6,352 | | Saturn | 37,931,187 | 1,221,900 (Titan's distance) |
| Mercury | 22,031.8 | 2,640 | | Uranus | 5,793,939 | 436,298 (Titania's distance) |
| Mars | 42,828.4 | 3,696 | | Neptune | 6,836,529 | 354,800 (Triton's distance) |
| Pluto | 869.6 | 1,288 | | Ceres | 62.63 | 520 |

At the other 20 bodies the cost equals the excess speed, which neglects their gravity. Those options suit a rendezvous; the
stored set need not contain the best option for a different end state.

**Size.** 30 Parquet files, 2.96 GB; 30 npz files, 2.7 GB. 235,673,510 option records out of at most 870 × 27,089 × 10 =
235,674,300; a few days have fewer than 10 options.

## How solmaps computed the data

- **Positions.** Planets and Pluto: JPL DE440 through pykep until 2149, JPL Horizons barycentre states (DE441) afterwards
  (`flyby/bodies.py`). Small bodies: daily JPL Horizons state vectors 2026–2205, fetched on 2026-10-31
  (`flyby/fetch_horizons.py`), with cubic Hermite interpolation between days. Bennu's Horizons solution ends in 2135; the
  latest arrival at Bennu in the data falls on 2135-09-28.
- **First run.** For each pair and day: Lambert's problem (pykep, prograde) over three log-spaced parts of flight time: 100
  values from 0.3 to 2.5 Hohmann times (at least 10 days), 40 more up to three orbits of the faster body, and 600 more up to
  100 years. The grid holds 740 values on 406 routes and 700 on 402, where three orbits of the faster body lie below 2.5 Hohmann times and the second part falls away; 62 routes keep only the
  first 100 because 2.5 Hohmann times already reach 100 years. For each flight time solmaps
  solves every number of revolutions around the Sun the flight time allows and keeps the cheapest. It then refines the
  cheapest local minima by two rounds of halving and thins the Pareto set to 10 options per day. It always keeps the fastest
  option, the cheapest option and the cheapest at or below each flight-time limit: classic flights (2.5 Hohmann times), 10
  years and 30 years (`engine/daily.py`).
- **Repair.** A pass over all routes tries the flight times of the two neighbouring days and those with the same arrival date,
  refines locally, drops arcs that pass inside the Sun and records the closest approach (`engine/repair_daily.py`).
- **Last stage.** Solves every option again at exactly its stored 32-bit flight time, so the file reproduces itself. It keeps
  flights within 100 years and scans 4,000 flight times on days that stand more than 0.5 km/s above both neighbours (3,309
  route-days). "Fastest" therefore means the shortest flight time the search tried; the lowest grid value bounds it from below.
- **Time scale.** All dates are TDB. pykep's DE440 interface reads dates as UTC; solmaps corrects the 64.184 s offset (found
  during this work, `flyby/bodies.py`).
- **Environment.** Pinned container (`env/Dockerfile`: pykep 3.0.0, numpy 2.5.4, Python 3.14). Commits of
  github.com/bhanneke/solmaps: first run `adfd502`, repair `628eba2`, last stage `0455ea4`.

## Quality

| Check | Result | Script |
| --- | --- | --- |
| JPL Small-Body Mission-Design maps, 10 bodies, launches 2027–2035, 294,875 cells; tests solver and ephemerides at JPL's grid points, independent of the stored file | JPL's solution counts as found when departure lies within 0.03 km/s and arrival within 0.003 km/s: 97.7–99.98% of cells per body. In the remaining cells the arrival speed stays within 0.07 km/s; departure can differ further, because JPL keeps the lowest launch energy | `tests/external/check_mdesign.py` |
| NASA NHATS round trips, 7 trajectories | asteroid arrival and departure speeds within 0.0015 km/s; Earth departure within 0.012 km/s (Earth's centre against the barycentre) | `tests/test_nhats.py` |
| Second Lambert solver (numpy), 3,000 random single-revolution transfers | same velocities within 1e-8 (relative) | `tests/test_vlambert.py` |
| Impossible values (negative or missing speeds, unordered options, a slower option dearer than a faster one), all records | none | `tests/audit_daily.py` |
| The file reproduces itself: 3,000 random options solved again at their stored flight time | largest speed difference 6.7e-6 km/s; revolution count right on all; no flight over 100 years | `tests/audit_self.py` |
| Repair against the first run, 23,567,430 route-days, cheapest option per day | cheaper by more than 0.001 km/s on 13,484,817 and by more than 0.5 km/s on 70,259; largest gain 20.2 km/s (Mercury to Pallas). No route-day lost a solution | `tests/audit_repair.py` |
| Repair, same comparison, route-days that became dearer | 172 by more than 0.001 km/s. On 29 the first run used an arc through the Sun (largest 0.30 km/s, Pallas to Pluto); the other 143 stay at or below 0.08 km/s. Classic flights dearer by more than 0.001 km/s on 29 route-days | `tests/audit_repair.py`, `tests/audit_dearer.py` |
| Against the earlier single-revolution data, which stored 16-bit speeds and had no Sun filter | dearer by more than 0.02 km/s on 846 route-days, classic flights by more than 0.035 km/s on 28 | `tests/audit_daily.py` |
| Routes far below the earlier data's best launch window | 48 routes undercut it by more than 0.3 km/s, many between bodies on nearly the same orbit, others not (Mercury to Apophis, Ceres to Itokawa, Pallas to Patroclus, routes to Neptune). 336 of their cheapest records (flights 1.3–100 years, up to 171 revolutions) match a recomputed solution, and an independent integration (scipy DOP853, Sun only) reaches the target within a median 0.1 km and at most 1,223 km | `tests/audit_cheap_routes.py` |
| Grid resolution: cheapest stored option against a fine scan, 1,000 random route-dates | median 0.000 km/s above the optimum; 90% within 0.013, 95% within 0.027, 99% within 0.093, largest 0.604; 97.1% within 0.05 km/s | `tests/grid_error.py` |
| Ephemeris join: DE440 against the DE441 planet files, 2140–2149 | within 5.1 m at whole days | `tests/audit_join.py` |
| Reproducibility: all 29 routes from Mars through each stage | bit-identical (first run on two machines; repair and last stage repeated from their input) | `engine/daily.py`, `engine/repair_daily.py` |

## Known limits

- **Two-body arcs.** Each transfer is a Keplerian arc around the Sun, and the planets pull on a real ship. Six sampled arcs,
  integrated with the Sun and eight planets and no corrections, miss the target by 0.03–0.72 AU and arrive with a velocity
  shifted by 0.65–12.9 km/s (2.9 to 95 years of flight, `tests/audit_nbody.py`). A real flight would need a guided trajectory
  and propellant for it; the data has no budget for that and solmaps has not measured its size. Departure and arrival speeds
  belong to the arc. They give a mapping of relative cost across places and dates, with flights of decades as the most idealised
  part.
- **Very close passes of the Sun.** The data removes arcs inside the Sun's radius and nothing else: 5,148,062 records pass within
  10 solar radii, and the closest stays 0.0047 AU from the Sun's centre. `closest_to_sun_au` lets users set their own limit.
- **Narrow cost valleys.** Near transfer angles of 0° and 180°, and where a solution with another revolution first appears, cost
  can change by kilometres per second within a thousandth of a day (one Earth to Bennu option: 19.08 km/s at −0.01 d, 7.07 at
  its flight time, 19.09 at +0.001 d). Such options need timing to seconds, and 32-bit storage resolves flight times to 0.004
  days at 100 years.
- **Remaining spikes.** After the last stage 2,474 route-days on 207 routes stand more than 0.5 km/s above both neighbours, 119
  of them more than 2 km/s; the largest is 7.79 km/s (1996 FG3 to Pluto). A scan of 20,000 flight times on 50 of them (the 25
  largest, 25 random) closes more than half the spike on 18 and leaves the others. The median gap to that scan is 0.09 km/s, the
  largest 4.05 km/s (`tests/audit_spikes.py`). These days make up 0.01% of all route-days. Check the days around any isolated value.
- **Grid.** Daily departures and a finite list of flight times. The stored cheapest option need not be the true optimum: see the
  grid and spike figures.
- **Interpolated positions.** Flight times end between whole days, where the files interpolate. The median error per small body
  stays at or below 42 m. It grows in close planetary encounters: about 3,100 km for Apophis at its April 2029 Earth
  pass and 290 km for Bennu in 2135 (estimates, `tests/audit_hermite.py`). After 2149 Mercury's interpolated position differs by
  up to 20 km mid-day, Venus's by up to 180 m.
- **Small-body orbits.** The data takes each Horizons solution as given. These solutions carry their own uncertainty, which grows
  over the century for near-Earth asteroids with close encounters; the data does not propagate it.
- **Impulsive burns, no gravity assists.** Flyby routes and low-thrust transfers form separate solmaps datasets.
- **Prograde transfers only.** Retrograde transfers are always far more expensive between these bodies.
- **Choice of solution.** For each flight time the data keeps the solution with the lowest cost as defined above. Mission-design
  tools often keep the lowest launch energy instead (JPL's maps do).
- **Moons and L1** take their planet's options; the cheapest option for a moon can differ from the cheapest for its planet.

## Uses

Intended: comparing places, dates and routes; network analysis over time; strategy studies and games built on travel costs;
teaching. Not intended: mission design without higher-fidelity tools (for example NASA GMAT); anything military.

## Distribution and licence

Zenodo (DOI TBD) and Hugging Face (`Deep-Space-Strategy/solmaps-transfers`). Data under CC BY 4.0 and code under MIT
(`LICENSE-DATA.md`, `LICENSE`). JPL ephemerides and small-body data keep NASA/JPL's terms; the release archives the exact
ephemeris files it used (211 MB). Please cite as: Björn Hanneke, solmaps transfer data v0.1, Zenodo, DOI TBD.

## Maintenance

Björn Hanneke maintains the dataset (hanneke@wiwi.uni-frankfurt.de; issues at github.com/bhanneke/solmaps). New versions add
bodies and correct errors; each version keeps its own DOI.

## Sources to cite

- Park, R. S., Folkner, W. M., Williams, J. G., & Boggs, D. H. (2021). The JPL Planetary and Lunar Ephemerides DE440 and
  DE441. The Astronomical Journal, 161(3), 105.
- JPL Horizons system and JPL Small-Body Database, NASA/JPL Solar System Dynamics (ssd.jpl.nasa.gov).
- Izzo, D. (2015). Revisiting Lambert's problem. Celestial Mechanics and Dynamical Astronomy, 121, 1–15 (pykep's solver).
- ESA pykep, version 3.0.0 (github.com/esa/pykep).
