# solmaps roadmap

Development follows user journeys; new computation results flow in on the side. Order agreed with Björn Hanneke on
2026-11-11 and 2026-11-15. Done items move to the last section with their date.

## Next, in this order

1. **Curious visitor.** A guided tour on the first visit (the solar system, one route, a ride past a flyby planet, the
   network, live missions, then "plan your own"); plain explanations, with the speed change (Δv) and reference values
   (Moon, Mars, Pallas) where numbers appear; the mission planner and the trade-offs view usable on a phone.
2. **Electric ships in the mission planner,** from the low-thrust atlas (four reference accelerations, scaled to the ship).
3. **Business-case analyst.** Start from a resource and a budget, get ranked candidate bodies with a round-trip mission
   each, and supply runs as a timetable (tonnes per year to a destination).
4. **Strategy researcher.** An analysis view over 2026–2100: reach within a budget, temporal betweenness, chokepoints and
   inflection dates, per body and scenario, with CSV export.
5. **Data release v0.2** (after Björn's go): the screening of 1.58 million small bodies, the first flyby routes, the
   low-thrust atlas; datasheet and audits as for v0.1.

## Mission planner, further

- Slingshot legs from the flyby search, as each origin finishes.
- Exact departure days for the chosen mission instead of the 10-day grid.
- Moons and Earth–Moon L1 as stops (all 40 places).
- Crew limits as hard limits: time in weightlessness, peak acceleration.

## Data and computation

- Flyby search for the 841 remaining routes: first run until about mid-January 2027 (compute host, with the laptop at
  night); second and third independent runs of every window until about mid-2027, all runs kept for verification.
- A view of the screening: the cheapest asteroids and comets to reach from Earth, Mars or Ceres, and when.
- Live missions: refresh the trajectories from JPL Horizons regularly.
- The Hugging Face query example on the Data page, once that service answers reliably.

## Science and engine, longer term

- Waiting horizons of 5 and 10 years in the journey planner; the network beyond 2100.
- Up to three and four flybys, with Saturn as a flyby planet and sequences pruned with the Tisserand graph.
- Station siting as a selection problem (QUBO), tested against classical and quantum solvers.
- Lessons for teaching (launch windows, the rocket equation, slingshots): not scheduled.

## Done

- 2026-11-09 Data release v0.1 (Zenodo DOI 10.5281/zenodo.24030357, Hugging Face).
- 2026-11-10 3D atlas with all 30 bodies; Display menu with reach per body; mission planner (impulsive legs).
- 2026-11-11 Live missions (17 spacecraft, JPL Horizons); Data page and daily network snapshots; documentation check.
- 2026-11-12 Technical page brought up to date; three independent flyby runs per window decided.
- 2026-11-14 Overnight flyby runs on the laptop (automatic, mains power only); Trips with a single destination.
