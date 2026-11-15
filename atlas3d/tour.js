/* ---------- guided tour ----------
Six short steps through the real views on the first visit (the browser remembers that it ran; the "?" button brings it
back). Each step sets the page up itself and the next step undoes it, so a visitor can leave at any point. Numbers in the
texts come from the transfer data: best classic launch window 2026-2100 from a 300 km Earth orbit. */
const TOUR_KEY = 'solmaps.toured';
const TOUR = { i: -1, box: null };
function tourClean() {                                   // back to the plain atlas between steps
  if (state.ride) endRide();
  for (const f of [...state.flights]) dropFlight(f);
  if (state.netView) $('btnNet').click();
  if (state.net3d) $('btnNet3').click();
  if (state.mView) $('btnMission').click();
  if (state.live) liveSet(false);
  controls.autoRotate = false; state.hl = null; state.routeOther = ''; state.routeFrom = ''; routeKey = ''; updateRoutes();
}
const TOUR_STEPS = [
  { title: 'The solar system as a network', text: 'solmaps shows what it costs to travel between 30 planets and asteroids, for every day until 2100. The planets keep moving, so the price of a trip changes every day.',
    go() { tourClean(); state.journey = false; $('btnJourney').setAttribute('aria-pressed', false); state.routeFrom = ''; routeKey = ''; updateRoutes(); openPanel(false); resetView(); controls.autoRotate = true; controls.autoRotateSpeed = 1.6; } },
  { title: 'One route: Earth to Mars', text: 'Every trip needs a speed change, Δv, that the engines must deliver: the more km/s, the more fuel. Earth to Mars costs 5.7 km/s in its best launch windows, Pallas 13.5.',
    async go() { tourClean(); await routesFrom('earth'); state.routeOther = 'mars'; fillRouteOther(); routeKey = ''; updateRoutes(); renderPanel(); openPanel(innerWidth > 820); camera.position.set(0, 20, 31); controls.target.set(0, 0, 0); } },
  { title: 'A slingshot past Mars', text: 'Flying close past a planet bends the path without fuel. This ship on its way to Vesta swings by Mars and saves fuel that way. The camera rides along.',
    go() { tourClean(); openPanel(false);
      const f = FBR.filter(r => (r.origin || 'earth') === 'earth' && r.target === 'vesta' && r.feasible && r.seq.length === 3 && r.seq[1] === 'mars').sort((a, b) => a.dv - b.dv)[0];
      const fl = f && launchSling({ fly: f, flyPath: flybyPath(f) }); if (!fl) return;
      ride([fl]); const m = fl.stops.find(s => s.id === 'mars'); if (m) setJD(m.jd - 60); } },
  { title: 'The network', text: 'Here the distance from the centre is the earliest arrival from Earth, the direction is where each body is today. Some places are close in time, others are years away.',
    go() { tourClean(); $('btnNet').click(); openPanel(false); } },
  { title: 'Live missions', text: 'Real spacecraft in flight right now, such as Psyche, Lucy and Hera, on their paths from NASA\'s JPL Horizons. Click one for its story.',
    async go() { tourClean(); resetView(); await liveSet(true); openPanel(innerWidth > 820); } },
  { title: 'Your turn', text: 'Plan a mission with your own ship, pick a destination and its launch windows, or explore freely.', final: true,
    go() { tourClean(); resetView(); openPanel(false); } },
];
function tourShow() {
  const s = TOUR_STEPS[TOUR.i], n = TOUR_STEPS.length;
  TOUR.box.innerHTML = `<div class="tstep">${TOUR.i + 1} of ${n}</div><h3>${esc(s.title)}</h3><p>${esc(s.text)}</p>
    <div class="list">${s.final ? `<button type="button" data-tour="plan" class="primary">Plan a mission</button><button type="button" data-tour="pick">Pick a destination</button><button type="button" data-tour="end">Explore freely</button>`
      : `${TOUR.i ? '<button type="button" data-tour="back">Back</button>' : ''}<button type="button" data-tour="next" class="primary">Next</button><button type="button" data-tour="end">Skip the tour</button>`}</div>`;
}
async function tourGo(i) { TOUR.i = i; tourShow(); try { await TOUR_STEPS[i].go(); } catch (e) { console.warn('tour step', i, e); } }
function tourEnd(after) {
  try { localStorage.setItem(TOUR_KEY, '1'); } catch (e) {}
  TOUR.box.hidden = true; TOUR.i = -1; tourClean(); controls.autoRotate = false;
  if (after === 'plan') $('btnMission').click();
  else if (after === 'pick') { routesFrom('earth'); openPanel(true); }
  else { resetView(); renderPanel(); }
}
function tourStart() { TOUR.box.hidden = false; tourGo(0); }
TOUR.box = document.createElement('div'); TOUR.box.id = 'tour'; TOUR.box.hidden = true; TOUR.box.setAttribute('role', 'dialog'); TOUR.box.setAttribute('aria-label', 'Guided tour');
document.body.appendChild(TOUR.box);
TOUR.box.addEventListener('click', e => {
  const b = e.target.closest('[data-tour]'); if (!b) return; const a = b.dataset.tour;
  if (a === 'next') tourGo(TOUR.i + 1); else if (a === 'back') tourGo(TOUR.i - 1); else tourEnd(a);
});
$('btnTour').addEventListener('click', tourStart);
let toured = false; try { toured = !!localStorage.getItem(TOUR_KEY); } catch (e) {}
if (!toured && location.hash.length <= 1) setTimeout(() => { if (TOUR.i < 0 && !state.sel && !state.journey) tourStart(); }, 2500);
