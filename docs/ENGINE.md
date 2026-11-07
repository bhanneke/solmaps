# solmaps routing engine

The engine finds the itineraries a given ship can fly between two sites within a departure window, with arrival
dates, fuel use and delivered payload. It combines precomputed transfer alternatives with ship
calculations at query time and refines trajectories on demand.

## Architecture

| Layer | Module | When it runs | What it holds |
| --- | --- | --- | --- |
| End states | `engine/conventions.py` | always | how a ship leaves and enters each node: parking orbit, rendezvous or Earth–Moon L1 |
| Transfer alternatives | `engine/alternatives.py` | `make data`, 30 s | per route and departure date up to six Lambert transfers that trade flight time against cost |
| Ships | `engine/ship.py` | per query | dry mass, payload, fuel capacity, thrust, specific impulse; rocket equation per burn |
| Journeys | `engine/journey.py` | per query, under a second | chronological multi-leg journeys with waiting, deadline and refuelling |
| Low thrust | `engine/lowthrust.py` | on request, 10–60 s | continuous-thrust transfers with changing mass |
| Refinement cache | `engine/refine.py` | on request | exact impulsive transfers at a given date; low-thrust transfers; stored under `data/cache/` |
| Service and page | `engine/api.py`, `engine/ui/index.html` | `make serve` | compare ships on one trip |

## Conventions

Every transfer has a heliocentric part and planet-side parts, and the engine keeps them apart. The excess speeds (v∞) at both ends describe the heliocentric leg. The planet-side burn turns a parking orbit into the departure
hyperbola, or the arrival hyperbola into a parking orbit:

Δv = √(v∞² + 2μ/r) − √(μ/r).

| Node | End state |
| --- | --- |
| Earth, Venus, Mars | circular orbit 300 km above the surface |
| Mercury | 200 km |
| Ceres | 50 km |
| Jupiter, Saturn, Uranus, Neptune | circular orbit at the distance of Callisto, Titan, Titania and Triton |
| Pluto | 100 km |
| Vesta, Psyche and the other 18 asteroids | rendezvous: the burn equals v∞ |
| Earth–Moon L1 | the cheaper of a burn at L1 and a drop to a 300 km perigee with a perigee burn; 3.77 km/s to or from low Earth orbit |
| Moon, Europa, Ganymede, Callisto, Titan, Enceladus, Triton | low orbit around the moon (100 km; Titan 1,000 km, Enceladus 50 km) |
| Phobos, Deimos | rendezvous with the moon |

**Moons** share their planet's heliocentric legs. Arriving at a moon, the planetocentric hyperbola reaches the moon's
orbit radius a with speed √(v∞² + 2μₚ/a); the ship meets the moon with the difference to the moon's speed √(μₚ/a) (the
sum for retrograde Triton) and captures into low orbit in one Oberth burn, √(v_rel² + 2μₘ/r) − √(μₘ/r). Inside one planet
system the engine connects places directly: a Hohmann ellipse around the planet between the two orbit radii, with an
Oberth escape or capture at each moon. Low Earth orbit to low lunar orbit comes to 3.93 km/s in 5 days (standard
budgets: about 4.0 km/s); Earth–Moon L1 to low lunar orbit 0.68 km/s. Without gravity assists from other moons, the
costs at the outer moons are upper bounds: real missions tour the moons to lower them. GM, radius and orbit radius come
from JPL SSD's satellite tables.

The network, the flyby search, the station precompute and the engine import these values from one module. A test
compares them with the JavaScript engine's values (`network/nodes.js`).

## Places and daily data

The engine knows 40 places: 30 bodies with their own heliocentric legs (`conventions.HELIO`: the planets and Pluto, Ceres,
Vesta, Psyche, Pallas, Hygiea, Themis, Juno, nine near-Earth asteroids, five Jupiter Trojans), nine moons and Earth–Moon L1.
`engine/daily.py` computes transfer alternatives for all 870 ordered pairs of the 30 bodies for every day from
2026-11-01 to 2100-12-31. It solves Lambert's problem for up to 740 flight times (406 routes hold 740, 402 hold 700, 62 hold 100) in three log-spaced parts: 100 from 0.3 to 2.5
Hohmann times (at least 10 days), 40 more up to three orbits of the faster body, and 600 more up to 100 years. For each
flight time it solves every number of revolutions around the Sun the flight time allows and keeps the cheapest; Earth to
Venus reaches 125 revolutions and Mercury to Venus 267 in 100 years. It then refines the three cheapest local minima of the single-revolution
cost over the first part, and the cheapest local minima of the overall cost in each part (three, three and five), by two
rounds of halving. It keeps a Pareto set of at most ten options per day: always the fastest, the cheapest and the cheapest
at or below each flight-time limit (classic flights, 10 and 30 years), the other slots spread in log flight time. Each
route and day needs up to 796 Lambert problems, at most 18.8 billion in all. Slow autonomous cargo makes the long flights worth listing: the cost of a long flight
rises and falls with every synodic period, and its valleys often lie well below any short transfer.

The grid density follows from measurements. With 40 flight times the daily data missed a narrow valley next to the 180°
transfer singularity on Psyche to Mercury by 8.5 km/s; with 60 long-flight points the stored cheapest option lay a median
0.10 km/s above the valleys of long flights. `engine/repair_daily.py` then improves the first run in two steps. The repair tries
the flight times of neighbouring days and those with the same arrival date, refines locally, drops arcs inside the Sun and stores
the closest approach. The last stage solves every option again at its stored 32-bit flight time, keeps flights within 100 years
and scans 4,000 flight times on days more than 0.5 km/s above both neighbours. Run them in this order, in the container from /work:

    python -m engine.repair_daily OUT_REPAIRED [procs]
    REPAIR_SRC=FIRST_RUN python -m engine.repair_daily final OUT_REPAIRED OUT_FINAL [procs]

The audits (`tests/audit_daily.py`, `tests/audit_repair.py`, `tests/grid_error.py`, `tests/audit_cheap_routes.py`) found no
impossible value in 235.7 million option records. Against a fine scan on 1,000 random route-dates, the stored cheapest option lies
a median 0.000 km/s above the optimum, within 0.05 km/s on 97.1% and within 0.093 km/s on 99% of them; the largest gap was 0.60
km/s. 2,474 route-days still stand more than 0.5 km/s above both neighbours; a denser scan closed more than half the spike on 18 of
50 tested. On 48 routes the cheapest transfer lies far below the earlier single-revolution data's best launch window, because long
flights with many revolutions wait for the phasing; an independent Sun-only integration of 336 of these records reaches the target
within a median 0.1 km. `docs/DATASHEET.md` documents the released dataset and its limits.

**Positions.** Planets and Pluto come from DE440 through pykep until 2149 and from JPL Horizons barycentre states (DE441)
afterwards. Small bodies come from daily JPL Horizons states to 2205, interpolated with cubic Hermite polynomials.
Bennu's Horizons solution ends on 2135-09-30, after its close Earth approach; the engine skips arrivals after a body's
ephemeris ends and raises an error for any date outside it. The ephemeris files are not in git (`make ephemeris`); each
data release archives the exact copies.

**Two corrections (2026-10-31).** pykep's DE440 interface reads dates as UTC, while every date in solmaps is TDB, as in
the Horizons files. The planets ran 64.184 s ahead of the small bodies, about 2,000 km along Earth's orbit; with the
correction DE440 and Horizons agree within 10 m. The earlier 10-day Horizons interpolation missed the true positions by
up to 304 km for Eros, 1,300 km for Ryugu and 8,700 km for Bennu near their Earth encounters; daily states remove that.

**A second Lambert solver.** `engine/vlambert.py` solves many transfers at once with numpy (universal variables,
bisection, single revolution, prograde). On 20,000 random transfers from 10 days to 100 years across 0.3 to 40 AU it
returns the same velocities as pykep within 4e-10 (relative) and solves the same set. It is no faster than pykep's
compiled solver (about 250,000 against 420,000 transfers per second on one core), so pykep stays in production and the
numpy solver serves as an independent check. Positions are the cheaper half of the work: two-body positions for all
1.58 million catalogue orbits at one date take 0.76 s.

**Independent checks of the transfer data.** On 400 random published entries: the stored costs reproduce within
0.0055 km/s; integrating each chosen transfer with scipy (two-body, DOP853) lands a median 43 m and at most 9.5 km from
the target; a separate universal-variable Lambert solver (`network/engine.js`) gives the same departure velocities
within 7 µm/s. `tests/test_daily.py` repeats a recheck on every daily run.

## Transfer alternatives

For each ordered pair of the 12 sites and each departure date (every 10 days, November 2026 to 2100), the precompute
solves Lambert's problem for 40 flight times: the network's 30 values (0.3–1.8 Hohmann times) plus 10 longer ones up to
2.5 Hohmann times. It keeps the transfers that are best for some trade-off of arrival date against cost (a Pareto front), thinned to six.
The cheapest alternative equals the network value whenever it flies within the network's flight-time grid. In a third
of the sampled route-dates, a flight longer than the network's limit costs less, by a median of 4.6 km/s, mostly on
dates between launch windows.

## Ships and mass accounting

A ship's mass is dry mass plus payload plus fuel. Every burn obeys the rocket equation for the current mass,
m_after = m_before · exp(−Δv / (Isp · g0)), and a burn is infeasible when the fuel on board does not cover it. A leg
has two burns: the departure burn on the ship's mass at departure, then the arrival burn on the lighter ship. Thrust
gives the burn duration; when a burn lasts longer than a tenth of the parking-orbit period, the result carries a
warning, because the impulsive model ignores the losses of long burns.

The four presets use rounded generic values for illustration:

| Preset | Dry t | Payload t | Fuel t | Thrust | Isp s | Full-tank capacity |
| --- | --- | --- | --- | --- | --- | --- |
| methalox tug | 12 | 20 | 200 | 2 MN | 370 | 7.2 km/s |
| hydrolox tug | 10 | 10 | 100 | 400 kN | 450 | 7.9 km/s |
| nuclear thermal | 25 | 20 | 60 | 300 kN | 900 | 7.5 km/s |
| solar-electric cargo | 8 | 20 | 30 | 10 N | 2,500 | 16.7 km/s |

## Journeys

The search runs on a time-expanded graph. A partial journey (label) holds its node, its arrival date, the fuel on
board and the fuel loaded so far. From a label the ship may leave on any network date within a waiting limit (default
1,100 days) on any transfer alternative. A leg leaves no earlier than the ship's arrival. The ship refills to capacity
at nodes that supply propellant and that the query allows: Earth, Earth–Moon L1, Mars, Ceres, Bennu, Ryugu. The ship
stops only there. The deadline applies to each leg's actual arrival time. The search drops a label when another label at
the same node arrived no later, holds at least as much fuel and has loaded no more. The result lists every journey on
the Pareto front of arrival date, fuel loaded and fuel left. For each journey, `max_payload` finds the largest payload
that fits the same legs and refuels.

The departure window covers the network dates inside it. The engine re-derives each returned itinerary burn by burn with the
ship model and checks that fuel passes from leg to leg.

## Any engine

The transfer costs in the network, the alternatives and the station data come from planet positions and Lambert's
problem. No engine enters them. The engine enters through two numbers, exhaust speed and thrust:

- **Exhaust speed** (Isp × g₀) turns Δv into fuel through the rocket equation. The engine applies it per burn at query
  time; the growth map and the station page take any Isp from 200 to 20,000 s. The station page interpolates its
  fuel-saved score between 41 precomputed exhaust speeds from 2 to 200 km/s (largest error 0.03 percentage points).
- **Thrust** decides the flight model, transfer by transfer. The engine label (chemical, nuclear, electric) plays no
  part, so a future engine falls into the right model by its numbers.
  - *At each planet* (`conventions.planet_side_plan`): one Oberth burn when the escape burn lasts at most a tenth of
    the parking-orbit period; a longer burn splits into up to 50 perigee passes with the same Δv, and the ship spends
    the time of the intermediate orbits (a 510 t ship with 1 MN needs three passes and 9 hours from low Earth orbit);
    beyond 50 passes the ship spirals out (Edelbaum) and then makes an impulse of v∞ at the edge of the sphere of
    influence. Pass and spiral time count in the journey's dates.
  - *Between planets*: a short-burn leg counts only when its heliocentric impulses (after a spiral, or at a small body)
    last at most 5% of the flight (`journey.IMPULSIVE_SHARE`). Ships below 4 mm/s² at full mass
    (`Ship.low_thrust`) also get continuous-thrust legs; at that acceleration a 6 km/s transfer burns for 5% of a year
    or more. Stronger ships burn for hours to days against flights of months, and segments of weeks cannot describe
    such burns, so they fly short-burn legs only.

## Continuous thrust

A continuous-thrust transfer has three phases, reported separately:

1. **Departure.** From a parking orbit to escape, either one Oberth burn of √(2μ/r) − √(μ/r) or a slow tangential
   spiral, whose velocity change equals the circular speed of the parking orbit (Edelbaum): 7.73 km/s from 300 km
   above Earth. Time and fuel follow from thrust and mass flow. At small bodies the ship starts at rest relative to
   the body. The departure window bounds the start of this phase.
2. **Heliocentric leg.** pykep's Sims–Flanagan transcription (`sf_pl2pl`) finds the route from several random starts.
   Its throttle profile seeds pykep's zero-order-hold model (`zoh_pl2pl`): thrust constant in magnitude and direction
   within each of 24 segments (48 from 1 mm/s² up), integrated with the heyoka Taylor integrator together with the falling mass,
   dm/dt = −|T|/ve. IPOPT maximises the arrival mass subject to position, velocity and mass continuity. SLSQP stalls on
   this problem. The search starts from the four cheapest two-impulse (Lambert) transfers in the window, with up to
   two revolutions, and then from random throttles scaled so that the first guess spends about 10 km/s; with full
   random throttles, a high-thrust ship starts on an escape orbit from the Sun and the propagation returns NaN.
   Above 0.5 mm/s² the engine also solves a reference ship with 0.25 mm/s² and starts a refinement from its
   solution with the throttles scaled down (continuation). The stronger ship can fly that profile exactly, so its
   result is never worse than the weaker ship's. The solver accepts constraint violations up to 1e-8 in its units
   (1.5 km, 0.3 mm/s); scaling a profile to another thrust level adds about 5e-9 of round-off.
3. **Capture.** The reverse burn or spiral into the destination's parking orbit; none at small bodies.

**Alternatives.** The comparison service solves each continuous-thrust query under up to six flight-time caps (the
time to the deadline times 1, 0.6, 0.4, 0.25, 0.15 and 0.1, at least 60 days) and keeps the options where each slower
one saves at least 0.5% fuel.

The zero-order-hold problem needs a non-zero range for the excess speeds at both ends. The engine allows up to
3 m/s, which the solution uses as free velocity: about 0.1% of a typical transfer, and reported with every result.

### Checks

The independent check integrates the solution's thrust profile with scipy's DOP853 integrator: two-body gravity plus
thrust, mass falling by |T|/ve. This code is separate from pykep's propagators. The check compares the end of the
integration with the arrival planet and with the optimiser's final mass. Earth to Mars, departures January to
November 2029, a 40 t ship with 10 N at Isp 2,500 s:

| Segments | Flight | Fuel | Best Sims–Flanagan fuel | Position error | Velocity error | Mass error |
| --- | --- | --- | --- | --- | --- | --- |
| 24 | 950 d | 8,335 kg | 8,265 kg | 0.41 km | 0.00004 m/s | 0.00002 kg |
| 48 | 979 d | 8,248 kg | 8,313 kg | 0.26 km | 0.00003 m/s | < 0.00001 kg |

The two transcriptions agree within 1% on fuel. With Sims–Flanagan alone (impulses at segment midpoints), the same
check showed errors of 8.6 million km at 24 segments, 2.4 million km at 48 and 0.28 million km at 96. That pattern of
discretisation error is why the engine refines in the continuous model.

Two faults in the engine surfaced at high thrust (fixed 2026-10-31). First, pykep applies throttle × maximum thrust ×
direction and allows the direction vector below unit length. The engine normalised that vector when it handed the
thrust profile to the check, which added thrust on partly throttled segments; the check error grew with thrust (1.2 km
at 500 N, 16 km at 2 kN, 47 km at 5 kN). With pykep's own vectors, the 500 N leg checks to 0.08 km and the 2 kN legs
to 0.2 km. Second, the engine recorded the check without acting on it. One solution the optimiser called feasible
missed Mars by 16,564 km in the check and burned 301 kg more fuel than its thrust needed. A leg now counts only when
the check confirms it: arrival within 100 km of the target and the final mass within 1 kg.

**More thrust never costs more.** `tests/test_accel_sweep.py` checks this on Earth to Mars, 2029 (40 t ship, Isp
4,000 s): the equivalent Δv may not rise with the acceleration, and no result may exceed the best two-impulse
transfer in the window (8.264 km/s; a ship with continuous thrust can phase and spread its burns, which is why it
needs less). Before the Lambert starts and the continuation, the search ended in local optima:

| Initial acceleration | Before | After |
| --- | --- | --- |
| 0.25 mm/s² | 5.712 km/s | 5.712 km/s |
| 1 mm/s² | 6.826 km/s | 5.671 km/s |
| 2 mm/s² | 6.700 km/s | 5.671 km/s |
| 3.5 mm/s² | none found | 5.671 km/s |

From 1 mm/s² on, the result equals the reference ship's solution at 48 segments: IPOPT does not improve on that start,
so stronger ships do not yet exploit their extra thrust. The results err on the side of cost.

**One grid for all exhaust speeds?** At a fixed initial acceleration, the equivalent Δv of a heliocentric leg barely
depends on the exhaust speed: 5.739, 5.731 and 5.723 km/s at Isp 2,000, 4,000 and 10,000 s and 0.25 mm/s²
(`tests/probe_dv_vs_ve.py`). Fuel then follows from the rocket equation, and a grid over acceleration alone, from
0.05 to 4 mm/s², would serve every continuous-thrust engine. That grid is the next precomputation.

## Earlier review findings, checked against the code (2026-10-31)

| Finding | Verdict | Change |
| --- | --- | --- |
| Inconsistent Ceres arrival conventions | Confirmed: the second flyby run priced Ceres as a rendezvous, the network as capture into a 50 km orbit | One conventions module for every component; the flyby reruns (routes3) use it |
| Independent inbound and outbound hub scoring | Confirmed in the growth map and in the station evaluation | Onward legs leave after the arrival. Earth–Moon L1 leverage 52–84% with slingshots (was 57–90%); station fuel saved 70% for L1 (was 82%) |
| Low thrust approximated by a speed multiplier | Not found; the code had no low-thrust model, only exhaust speeds applied to impulsive Δv | Continuous-thrust model above |
| Only the minimum Δv per date | Confirmed | Transfer alternatives |

## Build and test

```sh
make image      # pinned container: base image by digest, conda and pip packages by version
make data       # network to 2100 and transfer alternatives (under a minute)
make test       # 39 tests, about 40 s
make serve      # comparison page at http://localhost:8077/
make pairs site # station edges and the public pages into docs/
```

The tests cover:
- the conventions in every component, including the JavaScript engine
- the rocket equation and fuel limits
- the alternatives against the network
- journey chronology, deadlines, refuelling, departure windows and maximum payload
- the low-thrust check, mass consistency, throttle bound, spiral formula and the agreement of the two transcriptions
- the cache, the service and its input validation

## Limits

- Impulsive legs are two-body Lambert arcs from the daily data (the pages use every tenth day); the refinement cache
  refines one transfer at an exact date on request. The planets pull on a real ship: six sampled arcs integrated with
  all planets and no corrections miss the target by 0.03 to 0.72 AU (`tests/audit_nbody.py`), so a real flight needs a guided
  trajectory, and the costs compare places and dates.
- The journey search treats each heliocentric leg independently of the next. Slingshot routes are not yet edges of the
  journey graph, and planetary flybys appear only in the flyby search.
- Continuous-thrust transfers cover one leg between two sites. These ships are not part of the multi-leg journey
  search. The spiral uses Edelbaum's formula, without eclipses or the third-body effect of the Moon.
- The spiral model counts perigee passes at full mass, with equal steps in perigee speed and one orbit between burns; the last
  pass carries the whole excess speed. A spiralling ship has no short route between low Earth orbit and L1.
- From 1 mm/s² on, continuous-thrust results equal the 0.25 mm/s² reference solution: correct, possibly costlier than
  the true optimum for the stronger ship.
- No finite-burn losses for chemical ships, only the warning; no aerocapture in the engine yet (the cargo planner in
  the 3D atlas assumes it up to 6 km/s, an unsourced assumption).
- The result list of a journey query can hold near-identical journeys 10 days apart; a thinning step would make it easier to read.
- Ship presets are illustrative.
