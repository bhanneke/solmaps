# solmaps

solmaps computes what it costs to travel between places in the solar system on any day until 2100, and draws the maps
that follow from it. It is the open map and route engine of [Deep Space Strategy](https://bhanneke.github.io/deep-space-strategy/),
which studies where humanity should build in the solar system, and in which order.

Maps and documentation: https://bhanneke.github.io/solmaps/ · computation status: https://bhanneke.github.io/solmaps/status.html

## What it computes

- Daily transfer alternatives between 30 bodies (planets, Pluto, 18 asteroids including near-Earth asteroids and Jupiter
  Trojans), every day from November 2026 to 2100, flights up to 100 years: about 2.6 billion Lambert solutions. Nine
  moons and Earth–Moon L1 share their planet's legs; 40 places in all.
- Flyby (slingshot) routes with an evolutionary optimiser, Earth–Mars cyclers, low-thrust transfers with an
  independent check, station siting, and chronological journeys for ships with fuel, payload and refuelling.
- The JPL Small-Body Database catalogue (1,582,717 objects) as the basis for screening every asteroid and comet.

Positions come from JPL DE440 and daily JPL Horizons states. The checks include NASA NHATS round trips (asteroid legs
within 0.001 km/s), an independent integrator and a second Lambert solver; `docs/ENGINE.md` lists them with the models,
assumptions and limits.

## Contents

| Folder | What it holds |
| --- | --- |
| `engine/` | Routing engine: end-state conventions, daily precompute (`daily.py`), transfer alternatives, ships, journeys, low thrust, refinement cache, comparison service (`docs/ENGINE.md`) |
| `flyby/` | Bodies (DE440, JPL Horizons), ephemeris and catalogue fetchers, flyby search, cyclers, trajectories, compute queues |
| `atlas/` | Resource atlas: verified dataset (`atlas_dataset.json`, every entry with evidence level and source) and its map |
| `atlas3d/` | The 3D atlas: routes, slingshots, journeys, round trips, network views |
| `network/` | Growth map and the JavaScript transfer engine used by the pages |
| `stations/` | Station siting: candidate orbits, objectives, station-to-station edges |
| `surrogate/` | Route dataset generator and a first learned surrogate |
| `env/` | Pinned container (ESA pykep, pygmo, heyoka) |
| `tests/` | Test suite (`make test`) and external checks |
| `site/` | Start page, documentation, status page and `build_site.py`, which writes the public site into `docs/` |

## Build from a fresh checkout

Needs Docker, Python 3 and Node. All orbital computation runs in the pinned container (`env/Dockerfile`).

```sh
make image      # build the container
make ephemeris  # fetch daily JPL Horizons states (small bodies to 2205, planets 2140-2205; about 200 MB, not in git)
make data       # daily transfer alternatives, then the files the pages use
make test       # test suite
make serve      # ship comparison page at http://localhost:8077/
make site       # public pages into docs/
```

`make data` computes the daily data for all 30 bodies (about an hour on 12 cores, 450 MB in `data/daily/`) and
derives the files the pages use from it.

## Citing

Zenodo archives every release with a DOI; `CITATION.cff` gives the citation.

## Licence

Code: MIT (`LICENSE`). Data and documentation: CC BY 4.0 (`LICENSE-DATA.md`). pykep, used in the container, is MPL-2.0.
