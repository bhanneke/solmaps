/* ---------- mission planner ----------
A mission is a ship, a start, a list of stops (stay, cargo, refuelling, how the ship arrives) and an optional return.
Legs between bodies come from the transfer data: every stored option for every tenth departure day, as flight time and
the two excess speeds (planner files on Hugging Face, loaded per route when a mission needs it). The planner prices both
ends of every leg itself and carries the ship's mass through every burn with the rocket equation.

Search: for every stop and arrival date it keeps the most propellant the ship can have left (with fixed dry mass and
cargo, more propellant at the same place and date never hurts: any later burn sequence that works with less also works
with more). Waiting at a stop is free. Dates run on the data's 10-day grid.

Ends of a leg, per body (engine/conventions.py PARKING: GM and parking-orbit radius):
  low orbit      circular parking orbit; burn sqrt(v^2 + 2mu/r) - sqrt(mu/r) (Oberth)
  loose orbit    an orbit that just stays bound, periapsis at the parking radius; burn sqrt(v^2 + 2mu/r) - sqrt(2mu/r)
  atmosphere     aerocapture at Earth and Mars up to the excess speed the flyby search allows, then a 0.1 km/s trim burn
  small bodies   rendezvous: the burn equals the excess speed
At the start the rocket can bring the ship to low orbit (the ship pays the departure), to escape (the ship pays the excess
speed without Oberth gain) or supply the whole departure (the ship pays nothing). Electric ships fly continuous-thrust
legs, which this version does not plan yet. */
const MP = JSON.parse(document.getElementById('mission-data').textContent);
const G0 = 9.80665, MP_CACHE = new Map();
const MP_HUB = MP.hub;
Object.assign(state, { mView: false, mRes: null });
const mpName = id => (BY[id] ? BY[id].name : id).replace(/\s*\(.*\)/, '');
const mpPark = id => MP.parking[id] || null;
function mpBurnDep(id, vinf, from) {                   // from: 'orbit' | 'loose' | 'escape' | 'launcher' | 'surface-less'
  const p = mpPark(id);
  if (from === 'launcher') return 0;
  if (!p || from === 'escape') return vinf;
  const vc2 = p.mu / p.r, ve2 = 2 * p.mu / p.r;
  return from === 'loose' ? Math.sqrt(vinf * vinf + ve2) - Math.sqrt(ve2) : Math.sqrt(vinf * vinf + ve2) - Math.sqrt(vc2);
}
function mpBurnArr(id, vinf, how) {                    // how: 'orbit' | 'loose' | 'aero'; returns [km/s, state after]
  const p = mpPark(id);
  if (!p) return [vinf, 'rest'];
  if (how === 'aero' && MP.aero[id] && vinf <= MP.aero[id].vinf_max) return [MP.aero[id].trim, 'orbit'];
  if (how === 'aero') how = 'orbit';                   // too fast to brake in the atmosphere: an engine burn instead
  const vc2 = p.mu / p.r, ve2 = 2 * p.mu / p.r;
  return how === 'loose' ? [Math.sqrt(vinf * vinf + ve2) - Math.sqrt(ve2), 'loose'] : [Math.sqrt(vinf * vinf + ve2) - Math.sqrt(vc2), 'orbit'];
}
async function mpRoute(a, b) {
  const key = a + '_' + b;
  if (!MP_CACHE.has(key)) MP_CACHE.set(key, fetch(`${MP_HUB}/${key}.bin`).then(r => { if (!r.ok) throw new Error(`no leg data for ${key} (${r.status})`); return r.arrayBuffer(); }).then(buf => new Uint16Array(buf)));
  return MP_CACHE.get(key);
}
const hohmannDays = (a, b) => { const sa = x => +(BY[x] && BY[x].orbit ? BY[x].orbit.semi_major_axis_au : 1); const at = (sa(a) + sa(b)) / 2; return Math.PI * Math.sqrt(at ** 3 / K2); };

// one search over the whole mission; launchWin [k0, k1] limits the first departure
async function mpPlan(m, launchWin) {
  const N = MP.dates, Kopt = MP.k, step = MP.step_days, ve = m.ship.isp * G0 / 1000;
  const legs = [];
  for (let i = 0; i + 1 < m.seq.length; i++) legs.push({ a: m.seq[i].id, b: m.seq[i + 1].id, data: await mpRoute(m.seq[i].id, m.seq[i + 1].id) });
  const kEnd = Math.min(N - 1, Math.floor((m.latest - MP.jd0) / step));
  // label: propellant (t) left on arrival at stop i at date index k, after that stop's cargo and refuelling
  let cur = new Float64Array(N).fill(-1), back = [];
  const k0 = Math.max(0, launchWin[0]), k1 = Math.min(kEnd, launchWin[1]);
  for (let k = k0; k <= k1; k++) cur[k] = m.ship.tank;  // full tank at the launch date
  let payload = m.seq[0].payload ?? m.ship.payload;
  let stateAt = m.start;                                // how the ship sits at the current stop
  for (let i = 0; i < legs.length; i++) {
    const L = legs[i], next = m.seq[i + 1], stay = Math.ceil((i === 0 ? 0 : m.seq[i].stay) / step);
    const capDays = m.crew && m.legYears ? m.legYears * 365.25 : Infinity;
    const nxt = new Float64Array(N).fill(-1), bk = new Int32Array(N * 3).fill(-1);
    // best label available for a departure at k: the best arrival at or before k - stay (waiting is free)
    let bestP = -1, bestK = -1;
    const dry = m.ship.dry, depState = i === 0 ? m.start : stateAt;
    const payNext = payload + (next.pickup || 0) - (next.deliver || 0);
    for (let k = 0; k <= kEnd; k++) {
      const a = k - stay; if (a >= 0 && cur[a] > bestP) { bestP = cur[a]; bestK = a; }
      if (bestP < 0 || (i === 0 && (k < k0 || k > k1))) continue;
      const pLaunch = i === 0 ? cur[k] : bestP, kFrom = i === 0 ? k : bestK; if (pLaunch < 0) continue;
      const m0 = dry + payload + pLaunch, base = k * Kopt * 3;
      for (let j = 0; j < Kopt; j++) {
        const tof = L.data[base + j * 3]; if (tof === 65535 || tof > capDays) continue;
        const vd = L.data[base + j * 3 + 1] / 100, va = L.data[base + j * 3 + 2] / 100;
        const k2 = k + Math.ceil(tof / step); if (k2 > kEnd) continue;
        const d1 = mpBurnDep(L.a, vd, depState), [d2] = mpBurnArr(L.b, va, next.how);
        const mAfter = m0 * Math.exp(-(d1 + d2) / ve); let p = mAfter - dry - payload; if (p < m.reserve) continue;
        if (next.refuel) p = m.ship.tank;
        if (p > nxt[k2]) { nxt[k2] = p; bk[k2 * 3] = kFrom; bk[k2 * 3 + 1] = k; bk[k2 * 3 + 2] = j; }
      }
    }
    back.push(bk); cur = nxt; payload = Math.max(0, payNext); stateAt = mpBurnArr(L.b, 0, next.how)[1];
  }
  // reconstruct every arrival date at the last stop: the Pareto set of end date against propellant left
  const ends = [];
  for (let k = 0; k <= kEnd; k++) if (cur[k] >= 0) ends.push({ k, p: cur[k] });
  return { legs, back, ends, step };
}
function mpTrace(m, plan, kLast) {                    // the legs of the mission that ends at kLast
  const out = []; let k = kLast;
  for (let i = plan.legs.length - 1; i >= 0; i--) {
    const bk = plan.back[i], kFrom = bk[k * 3], kDep = bk[k * 3 + 1], j = bk[k * 3 + 2];
    out.unshift({ i, kArr: k, kDep, j, kFromArr: kFrom }); k = kFrom;
  }
  return out;
}
// the mission sheet: every phase with date, burn, propellant and mass, recomputed forward from the traced legs
function mpSheet(m, plan, kLast) {
  const tr = mpTrace(m, plan, kLast), ve = m.ship.isp * G0 / 1000, step = plan.step, rows = [];
  let p = m.ship.tank, payload = m.seq[0].payload ?? m.ship.payload, st = m.start, dvSum = 0, minMass = Infinity, lastArr = 0;
  const jd = k => MP.jd0 + k * step;
  tr.forEach((t, n) => {
    const L = plan.legs[t.i], next = m.seq[t.i + 1], base = t.kDep * MP.k * 3 + t.j * 3;
    const tof = L.data[base], vd = L.data[base + 1] / 100, va = L.data[base + 2] / 100;
    if (n > 0) rows.push({ date: lastArr, phase: `stay at ${mpName(L.a)}`, days: jd(t.kDep) - lastArr, note: m.seq[t.i].stay ? `at least ${m.seq[t.i].stay} days` : '' });   // real dates; the search runs on the 10-day grid
    const m0 = m.ship.dry + payload + p, d1 = mpBurnDep(L.a, vd, st), m1 = m0 * Math.exp(-d1 / ve);
    rows.push({ date: jd(t.kDep), phase: `departure from ${mpName(L.a)} (${st === 'launcher' ? 'rocket supplies it' : st === 'escape' ? 'from escape' : st === 'loose' ? 'loose orbit' : st === 'rest' ? 'at rest' : MP.parking[L.a] ? MP.parking[L.a].label : 'at rest'})`, dv: d1, used: m0 - m1, mass: m1, vinf: vd });
    rows.push({ date: jd(t.kDep), phase: `transfer to ${mpName(L.b)}`, days: tof, note: `excess speed ${vd.toFixed(2)} → ${va.toFixed(2)} km/s` });
    const [d2, after] = mpBurnArr(L.b, va, next.how), m2 = m1 * Math.exp(-d2 / ve);
    const howTxt = !MP.parking[L.b] ? 'rendezvous' : next.how === 'aero' && MP.aero[L.b] && va <= MP.aero[L.b].vinf_max ? 'braking in the atmosphere, then trim' : next.how === 'loose' ? 'into a loose orbit' : 'into ' + MP.parking[L.b].label;
    rows.push({ date: jd(t.kDep) + tof, phase: `arrival at ${mpName(L.b)} (${howTxt})`, dv: d2, used: m1 - m2, mass: m2 });
    dvSum += d1 + d2; t.dv = d1 + d2; minMass = Math.min(minMass, m2); p = m2 - m.ship.dry - payload;
    const notes = [];
    if (next.deliver) { payload -= next.deliver; notes.push(`deliver ${next.deliver} t`); }
    if (next.pickup) { payload += next.pickup; notes.push(`take on ${next.pickup} t`); }
    if (next.refuel) { notes.push(`refuel ${(m.ship.tank - p).toFixed(1)} t`); p = m.ship.tank; }
    if (notes.length) rows.push({ date: jd(t.kDep) + tof, phase: notes.join(', '), mass: m.ship.dry + payload + p });
    st = after; lastArr = jd(t.kDep) + tof;
  });
  const start = jd(tr[0].kDep), end = rows[rows.length - 1].date, used = rows.reduce((a, r) => a + (r.used || 0), 0);
  const gmax = m.ship.thrust / (minMass * 1000) / G0;
  return { rows, start, end, dvSum, used, left: p, years: (end - start) / 365.25, gmax, tr };
}
const MP_PRESETS = MP.presets;
function mpReadForm() {
  const v = id => $(id).value, n = id => parseFloat($(id).value);
  const ship = { dry: n('mDry'), payload: n('mPay'), tank: n('mTank'), thrust: n('mThrust') * 1000, isp: n('mIsp') };
  const seq = [{ id: v('mFrom'), payload: ship.payload }];
  for (const r of document.querySelectorAll('#mStops .mstop')) seq.push({ id: r.querySelector('[data-f=body]').value, stay: +r.querySelector('[data-f=stay]').value || 0,
    how: r.querySelector('[data-f=how]').value, deliver: +r.querySelector('[data-f=deliver]').value || 0, pickup: +r.querySelector('[data-f=pickup]').value || 0, refuel: r.querySelector('[data-f=refuel]').checked });
  if ($('mReturn').checked) seq.push({ id: v('mFrom'), stay: 0, how: v('mRetHow'), deliver: 0, pickup: 0, refuel: false, back: true });
  const jdOfDate = s => jdOf(Date.parse(s + 'T00:00:00Z'));
  return { ship, seq, start: v('mStart'), crew: $('mCrew').checked, legYears: n('mLegYears') || 0, reserve: n('mReserve') || 0,
           earliest: jdOfDate(v('mEarliest')), latest: jdOfDate(v('mLatest')) };
}
function mpValidate(m) {
  if (m.seq.length < 2) return 'Add at least one stop.';
  for (let i = 0; i + 1 < m.seq.length; i++) if (m.seq[i].id === m.seq[i + 1].id) return `Two stops in a row at ${mpName(m.seq[i].id)}.`;
  if (!(m.ship.dry > 0 && m.ship.tank > 0 && m.ship.isp > 0)) return 'The ship needs a dry mass, a tank and an exhaust speed.';
  if (m.ship.thrust > 0 && m.ship.thrust / ((m.ship.dry + m.ship.payload + m.ship.tank) * 1000) < MP.a_continuous)
    return 'This ship accelerates with less than 4 mm/s² at full mass: an electric ship. It flies continuous-thrust legs, which the planner adds next (the low-thrust atlas is computing).';
  if (!(m.latest > m.earliest)) return 'The latest end must come after the earliest launch.';
  return '';
}
const mpFmtDate = jd => isoOf(jd);
const mpFmtDays = d => d >= 730 ? (d / 365.25).toFixed(1) + ' years' : Math.round(d) + ' days';
async function mpRun() {
  const m = mpReadForm(), err = mpValidate(m);
  $('mOut').innerHTML = ''; $('mMsg').textContent = err || 'Loading the legs and searching…';
  if (err) return;
  try {
    const kA = Math.max(0, Math.floor((m.earliest - MP.jd0) / MP.step_days)), kB = Math.floor((m.latest - MP.jd0) / MP.step_days);
    const plan = await mpPlan(m, [kA, kB]);
    if (!plan.ends.length) { $('mMsg').textContent = 'No mission fits: the tank runs out or the dates do not allow the stays. Try a bigger tank, aerocapture, refuelling or a later end.'; state.mRes = null; return; }
    const cheapest = plan.ends.reduce((a, b) => b.p > a.p ? b : a), earliest = plan.ends[0];
    // the best mission per launch year, for the alternatives strip
    const years = [];
    for (let y = new Date(msOf(m.earliest)).getUTCFullYear(); y <= new Date(msOf(m.latest)).getUTCFullYear(); y++) {
      const a = Math.max(kA, Math.floor((jdOf(Date.UTC(y, 0, 1)) - MP.jd0) / MP.step_days)), b = Math.min(kB, Math.floor((jdOf(Date.UTC(y + 1, 0, 1)) - MP.jd0) / MP.step_days) - 1);
      if (a > b) continue; const pl = await mpPlan(m, [a, b]); if (!pl.ends.length) { years.push({ y, ok: false }); continue; }
      const best = pl.ends.reduce((u, v) => v.p > u.p ? v : u); years.push({ y, ok: true, p: best.p, end: MP.jd0 + best.k * MP.step_days, plan: pl, k: best.k });
    }
    // trade-offs: each later return that leaves at least 0.5 t more propellant than every earlier one
    const front = []; let best = -1;
    for (const e of plan.ends) if (e.p > best + 0.5 || front.length === 0) { front.push(e); best = e.p; }
    state.mRes = { m, plan, cheapest, earliest, years, front, pick: 'earliest' };
    $('mMsg').textContent = ''; mpDraw();
  } catch (e) { $('mMsg').textContent = 'Search failed: ' + e.message; }
}
function mpDraw() {
  const R = state.mRes; if (!R) return;
  const pk = R.pick === 'earliest' ? R.earliest : R.pick && R.pick.startsWith('k') ? { k: +R.pick.slice(1) } : R.pick && R.pick.startsWith('y') ? (() => { const y = R.years.find(x => 'y' + x.y === R.pick); return y && y.ok ? { k: y.k, plan: y.plan } : R.cheapest; })() : R.cheapest;
  const plan = pk.plan || R.plan, S = mpSheet(R.m, plan, pk.k); R.sheet = S;
  const fmt = (x, d = 2) => x == null ? '' : x.toFixed(d);
  const kpi = (l, v) => `<div class="kpi"><span>${l}</span><b>${v}</b></div>`;
  const warn = [];
  if (R.m.crew && S.gmax > 4) warn.push(`peak acceleration ${S.gmax.toFixed(1)} g, above 4 g for a crew`);
  if (R.m.crew && S.years > 3) warn.push(`${S.years.toFixed(1)} years away from Earth: radiation and weightlessness need shielding and rotation`);
  const yrs = R.years.map(y => `<button type="button" class="myr" data-pick="y${y.y}" aria-pressed="${R.pick === 'y' + y.y}" ${y.ok ? '' : 'disabled'} title="${y.ok ? `launch ${y.y}: ${y.p.toFixed(1)} t of propellant left, back ${mpFmtDate(y.end)}` : 'no mission launching this year'}"><span style="height:${y.ok ? Math.max(4, 40 * y.p / R.m.ship.tank) : 2}px"></span>${String(y.y).slice(2)}</button>`).join('');
  $('mOut').innerHTML = `
    <h3>Back by … with this much propellant left</h3>
    <div class="list mfront">${R.front.slice(0, 10).map(e => { const sh = mpSheet(R.m, R.plan, e.k); return `<button type="button" data-pick="k${e.k}" aria-pressed="${R.pick === 'k' + e.k || (R.pick === 'earliest' && e.k === R.earliest.k)}">${mpFmtDate(sh.end)} · ${mpFmtDays(sh.end - sh.start)} · ${e.p.toFixed(1)} t left</button>`; }).join('')}</div>
    <p class="caveat">The first entry returns earliest; each later one leaves at least 0.5 t more propellant, mostly by waiting for better launch windows or flying longer arcs.</p>
    <div class="list"><button type="button" id="mFly">Fly along in 3D</button><button type="button" id="mCsv">Export CSV</button><button type="button" id="mJson">Export JSON</button></div>
    <div class="kpis">${kpi('Launch', mpFmtDate(S.start))}${kpi('End', mpFmtDate(S.end))}${kpi('Duration', mpFmtDays(S.end - S.start))}${kpi('Total Δv', fmt(S.dvSum) + ' km/s')}${kpi('Propellant used', fmt(S.used, 1) + ' t')}${kpi('Left in the tank', fmt(S.left, 1) + ' of ' + R.m.ship.tank + ' t')}${kpi('Peak acceleration', S.gmax.toFixed(2) + ' g')}</div>
    ${warn.length ? `<p class="caveat warn">${warn.map(esc).join('; ')}.</p>` : ''}
    <div class="twrap"><table class="ttab"><thead><tr><th>Date</th><th>Phase</th><th>Δv km/s</th><th>Propellant t</th><th>Mass after t</th><th>Duration</th><th></th></tr></thead><tbody>
      ${S.rows.map(r => `<tr><td class="num">${mpFmtDate(r.date)}</td><td>${esc(r.phase)}</td><td class="num">${fmt(r.dv)}</td><td class="num">${fmt(r.used, 1)}</td><td class="num">${fmt(r.mass, 1)}</td><td class="num">${r.days != null ? mpFmtDays(r.days) : ''}</td><td>${esc(r.note || '')}</td></tr>`).join('')}
    </tbody></table></div>
    <h3>Best mission by launch year</h3><div class="myrs" role="group" aria-label="Launch years">${yrs}</div>
    <p class="caveat">Bar height: propellant left at the end. Dates follow the transfer data's 10-day grid; each leg is the stored option on that date, priced at both ends for this ship. Departures and arrivals are impulsive burns; flybys and electric legs come in the next steps.</p>`;
}
function mpCsv() {
  const S = state.mRes && state.mRes.sheet; if (!S) return;
  const lines = [['date', 'phase', 'dv_kms', 'propellant_t', 'mass_after_t', 'duration_days', 'note'].join(',')].concat(S.rows.map(r => [mpFmtDate(r.date), `"${r.phase}"`, r.dv ?? '', r.used ?? '', r.mass ?? '', r.days ?? '', `"${r.note || ''}"`].join(',')));
  mpSave('mission.csv', lines.join('\n'), 'text/csv');
}
function mpSave(name, text, type) { const a = document.createElement('a'); a.href = URL.createObjectURL(new Blob([text], { type })); a.download = name; a.click(); setTimeout(() => URL.revokeObjectURL(a.href), 1000); }
function mpFly() {
  const R = state.mRes; if (!R || !R.sheet) return;
  const plan = R.pick && R.pick.startsWith('y') ? (R.years.find(x => 'y' + x.y === R.pick) || {}).plan || R.plan : R.plan;
  const fs = [], skipped = [];
  for (const t of R.sheet.tr) {
    const L = plan.legs[t.i], base = t.kDep * MP.k * 3 + t.j * 3, tof = L.data[base], jdDep = MP.jd0 + t.kDep * MP.step_days;
    const el = solveArc(L.a, L.b, jdDep, tof);
    if (!el) { skipped.push(`${mpName(L.a)} to ${mpName(L.b)}`); continue; }
    const f = launch({ key: 'mission', from: L.a, to: L.b, name: mpName(L.b), dv: t.dv || 0, jdDep, tof, el }); if (f) fs.push(f);
  }
  if (state.mView) $('btnMission').click();
  if (fs.length) { setJD(fs[0].jdDep); ride(fs); }
  if (skipped.length) setTimeout(() => alert(`Not drawn (the arc circles the Sun more than once): ${skipped.join(', ')}`), 50);
}
function mpStopRow(s = {}) {
  const opts = sel => MP.bodies.map(id => `<option value="${id}" ${id === sel ? 'selected' : ''}>${esc(mpName(id))}</option>`).join('');
  const d = document.createElement('div'); d.className = 'mstop';
  d.innerHTML = `<label>Stop <select data-f="body">${opts(s.id || 'mars')}</select></label><label>Stay, days <input data-f="stay" type="number" min="0" step="10" value="${s.stay ?? 30}"></label>
    <label>Arrive <select data-f="how"><option value="orbit">into low orbit</option><option value="loose">into a loose orbit</option><option value="aero">braking in the atmosphere</option></select></label>
    <label>Deliver, t <input data-f="deliver" type="number" min="0" step="1" value="${s.deliver ?? 0}"></label><label>Take on, t <input data-f="pickup" type="number" min="0" step="1" value="${s.pickup ?? 0}"></label>
    <label class="mchk"><input data-f="refuel" type="checkbox" ${s.refuel ? 'checked' : ''}> refuel here</label><button type="button" data-f="del" aria-label="Remove this stop">✕</button>`;
  if (s.how) d.querySelector('[data-f=how]').value = s.how;
  d.querySelector('[data-f=del]').addEventListener('click', () => d.remove());
  return d;
}
function mpPreset(name) {
  const p = MP_PRESETS[name]; if (!p) return;
  $('mDry').value = p.dry_kg / 1000; $('mPay').value = p.payload_kg / 1000; $('mTank').value = p.fuel_capacity_kg / 1000; $('mThrust').value = p.thrust_n / 1000; $('mIsp').value = p.isp_s;
}
function mpInit() {
  $('mPreset').innerHTML = Object.keys(MP_PRESETS).map(k => `<option value="${k}">${esc(k)}</option>`).join('') + '<option value="">own values</option>';
  $('mPreset').addEventListener('change', e => mpPreset(e.target.value)); $('mPreset').value = 'hydrolox tug'; mpPreset('hydrolox tug');
  for (const id of ['mDry', 'mPay', 'mTank', 'mThrust', 'mIsp']) $(id).addEventListener('input', () => { $('mPreset').value = ''; });
  const fill = () => { const v = $('mFrom').value; $('mFrom').innerHTML = MP.bodies.map(id => `<option value="${id}">${esc(mpName(id))}</option>`).join(''); $('mFrom').value = v || 'earth'; };
  fill(); MP.refill = fill;
  $('mStops').append(mpStopRow({ id: 'mars', stay: 500, how: 'aero' }));
  $('mAdd').addEventListener('click', () => $('mStops').append(mpStopRow({ id: 'ceres', stay: 30 })));
  $('mEarliest').value = isoOf(jdOf(TODAY)); $('mLatest').value = '2045-12-31';
  $('mPlan').addEventListener('click', mpRun);
  $('mOut').addEventListener('click', e => {
    const b = e.target.closest('[data-pick]'); if (b) { state.mRes.pick = b.dataset.pick; mpDraw(); return; }
    if (e.target.id === 'mFly') mpFly(); else if (e.target.id === 'mCsv') mpCsv();
    else if (e.target.id === 'mJson') mpSave('mission.json', JSON.stringify({ mission: state.mRes.m, sheet: state.mRes.sheet.rows.map(r => ({ ...r, date: mpFmtDate(r.date) })) }, null, 1), 'application/json');
  });
  $('btnMission').addEventListener('click', () => {
    state.mView = !state.mView; $('btnMission').setAttribute('aria-pressed', state.mView); $('missionView').hidden = !state.mView;
    if (state.mView) { for (const [b, on] of [['btnTable', state.tableView], ['btnNet3', state.net3d], ['btnNet', state.netView], ['btnTrade', state.tradeView]]) if (on) $(b).click(); MP.refill(); }
    $('btnAtlas').setAttribute('aria-pressed', !state.netView && !state.net3d && !state.tableView && !state.tradeView && !state.mView);
  });
  for (const id of ['btnAtlas', 'btnNet', 'btnNet3', 'btnTable', 'btnTrade']) $(id).addEventListener('click', () => { if (state.mView && id !== 'btnMission') { state.mView = false; $('btnMission').setAttribute('aria-pressed', false); $('missionView').hidden = true; } }, true);
}
mpInit();
