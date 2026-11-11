/* ---------- live missions ----------
Spacecraft in flight, from JPL Horizons trajectories (flyby/fetch_missions.py, missions_tracks.json, loaded when the view
opens) and a hand-curated registry of facts with their sources (atlas3d/missions_registry.json, embedded). Each probe is a
marker at its position on the date shown; its path is solid where it has flown and dashed where Horizons holds the plan.
Selecting a probe opens its card and lets the camera follow it, like a body. The page never extends a trajectory beyond
the span Horizons holds: where it ends, the card says so. */
const LIVE_REG = JSON.parse(document.getElementById('live-data').textContent);
const LIVE = { tracks: null, loading: null, group: new THREE.Group(), items: {}, lastJd: null };
scene.add(LIVE.group); LIVE.group.visible = false;
Object.assign(state, { live: false });
const LIVE_ON = 0x4fd6e8, LIVE_SEL = 0xf2b84b;
const liveId = id => 'm:' + id, liveOf = key => LIVE_REG.missions.find(m => liveId(m.id) === key);
for (const m of LIVE_REG.missions) BY[liveId(m.id)] = { id: liveId(m.id), name: m.name, type: 'mission', mission: m };
const jdOfIso = s => jdOf(Date.parse((s.length === 7 ? s + '-01' : s.length === 4 ? s + '-07-01' : s) + 'T00:00:00Z'));
const liveFmt = s => s ? (s.length === 4 ? s : s.length === 7 ? new Date(s + '-01T00:00:00Z').toLocaleString('en', { month: 'long', year: 'numeric', timeZone: 'UTC' }) : s) : '';
function liveAt(t, jd) {                                 // position (AU) on the track at jd, or null outside the span
  if (jd < t.jd0 || jd > t.last_jd) return null;
  const u = (jd - t.jd0) / t.step_days, i = Math.min(t.n - 2, Math.floor(u)), f = u - i, x = t.xyz;
  return [0, 1, 2].map(k => x[3 * i + k] + f * (x[3 * (i + 1) + k] - x[3 * i + k]));
}
async function liveLoad() {
  if (LIVE.tracks) return LIVE.tracks;
  if (!LIVE.loading) LIVE.loading = fetch('missions_tracks.json').then(r => { if (!r.ok) throw new Error(r.status); return r.json(); });
  LIVE.tracks = await LIVE.loading;
  for (const m of LIVE_REG.missions) {
    const t = LIVE.tracks.tracks[m.id]; if (!t) continue;
    const pts = new Float32Array(t.n * 3);
    for (let i = 0; i < t.n; i++) { const v = S([t.xyz[3 * i], t.xyz[3 * i + 1], t.xyz[3 * i + 2]]); pts[3 * i] = v.x; pts[3 * i + 1] = v.y; pts[3 * i + 2] = v.z; }
    const g1 = new THREE.BufferGeometry(), g2 = new THREE.BufferGeometry();
    g1.setAttribute('position', new THREE.BufferAttribute(pts, 3)); g2.setAttribute('position', new THREE.BufferAttribute(pts.slice(), 3));
    const flown = new THREE.Line(g1, new THREE.LineBasicMaterial({ color: LIVE_ON, transparent: true, opacity: 0.7 }));
    const plan = new THREE.Line(g2, new THREE.LineDashedMaterial({ color: LIVE_ON, transparent: true, opacity: 0.55, dashSize: 0.25, gapSize: 0.18 }));
    plan.computeLineDistances();
    const dot = new THREE.Mesh(new THREE.SphereGeometry(0.07, 12, 8), new THREE.MeshBasicMaterial({ color: LIVE_ON }));
    const glowS = new THREE.Sprite(new THREE.SpriteMaterial({ map: glowTexture('rgba(150,240,255,0.9)', 'rgba(80,200,240,0)'), blending: THREE.AdditiveBlending, depthWrite: false, transparent: true }));
    glowS.scale.set(0.35, 0.35, 1); dot.add(glowS);
    LIVE.group.add(flown, plan, dot);
    LIVE.items[m.id] = { t, flown, plan, dot };
    if (!labels[liveId(m.id)]) makeLabel(liveId(m.id), m.short || m.name, false).classList.add('live');
  }
  return LIVE.tracks;
}
function liveUpdate(force) {
  if (!state.live || !LIVE.tracks || (!force && LIVE.lastJd === state.jd)) return;
  LIVE.lastJd = state.jd;
  for (const m of LIVE_REG.missions) {
    const it = LIVE.items[m.id]; if (!it) continue;
    // overview: a tail of half a year behind and ahead of each probe; a selected probe shows its whole path in gold
    const t = it.t, i = Math.max(0, Math.min(t.n - 1, Math.floor((state.jd - t.jd0) / t.step_days)));
    const anySel = state.sel && state.sel.startsWith('m:'), sel = state.sel === liveId(m.id), col = sel ? LIVE_SEL : LIVE_ON;
    const tail = sel ? t.n : Math.max(2, Math.round(180 / t.step_days)), a = Math.max(0, i - tail);
    it.flown.geometry.setDrawRange(a, state.jd < t.jd0 ? 0 : i - a + 1); it.plan.geometry.setDrawRange(Math.min(i, t.n - 1), Math.min(tail, t.n - i));
    it.flown.material.color.setHex(col); it.plan.material.color.setHex(col); it.dot.material.color.setHex(col);
    it.flown.material.opacity = sel ? 1 : anySel ? 0.18 : 0.75; it.plan.material.opacity = sel ? 0.9 : anySel ? 0.12 : 0.5;
    const p = liveAt(t, state.jd);
    it.dot.visible = !!p;
    if (p) { const v = S(p); it.dot.position.copy(v); pos3[liveId(m.id)] = v; } else delete pos3[liveId(m.id)];
  }
}
(function liveLoop() { liveUpdate(false); requestAnimationFrame(liveLoop); })();
function liveNext(m) {                                   // the next planned event from the date shown
  const until = e => jdOfIso(e.date) + (e.date.length === 7 ? 30 : e.date.length === 4 ? 365 : 0);   // a month or a year counts until its end
  const ev = (m.events || []).filter(e => e.date && until(e) >= state.jd).sort((a, b) => jdOfIso(a.date) - jdOfIso(b.date));
  return ev[0] || null;
}
function liveList() {
  const rows = LIVE_REG.missions.map(m => ({ m, n: liveNext(m), t: LIVE.tracks && LIVE.tracks.tracks[m.id] }))
    .sort((a, b) => (a.n ? jdOfIso(a.n.date) : Infinity) - (b.n ? jdOfIso(b.n.date) : Infinity));
  const days = d => { const x = Math.round(jdOfIso(d) - state.jd); return x > 730 ? `in ${(x / 365.25).toFixed(1)} years` : x > 1 ? `in ${x} days` : 'now'; };
  return `<div><h2>Live missions</h2><p class="caveat">Spacecraft in flight on ${isoOf(state.jd)}, sorted by their next event. Paths from JPL Horizons (fetched ${esc(LIVE.tracks ? LIVE.tracks.fetched : '…')}): solid where the probe has flown, dashed where the plan lies ahead. Click a probe for its card.</p></div>
    <div class="res">${rows.map(({ m, n, t }) => `<div class="r live"><div class="head"><span class="name">${esc(m.name)}</span><span class="vt">${esc((m.agencies || []).join(', '))}</span></div>
      <div class="meta">${n ? `${esc(n.what)}${n.body ? ' · ' + esc(n.body) : ''} · ${esc(liveFmt(n.date))} (${days(n.date)})` : esc(m.status || '')}${t ? '' : ' · no trajectory in Horizons'}</div>
      <div class="list"><button type="button" data-live="${esc(m.id)}">Show</button></div></div>`).join('')}</div>
    <p class="caveat">Mission facts from the agencies' pages (links on each card). ${esc(LIVE_REG.note || '')}</p>`;
}
function liveCard(b) {
  const m = b.mission, t = LIVE.tracks && LIVE.tracks.tracks[m.id];
  const ev = (m.events || []).slice().sort((a, c) => jdOfIso(a.date) - jdOfIso(c.date));
  const endTxt = t ? (t.last_jd < jdOfIso('2099-12-31') ? `The trajectory in Horizons runs to ${isoOf(t.last_jd)}; the map shows nothing beyond.` : '') : 'Horizons holds no trajectory for this probe, so the map cannot show it.';
  const cmp = MP && MP.bodies.includes(m.launch_body) && (m.targets || []).some(x => MP.bodies.includes(x));
  return `<div><h2>${esc(m.name)}</h2><p class="caveat">${esc((m.agencies || []).join(', '))} · ${esc(m.status || '')}${m.status_as_of ? ' (as of ' + esc(m.status_as_of) + ')' : ''}</p></div>
    <p>${esc(m.purpose || '')}</p>
    <div class="kv"><span>Launch</span><b>${esc(liveFmt(m.launch_date))} from ${esc(BY[m.launch_body] ? BY[m.launch_body].name : m.launch_body || '')}</b>
      <span>Destination</span><b>${esc((m.target_names || m.targets || []).join(', '))}</b>
      <span>Path</span><b>${t ? `${isoOf(t.jd0)} to ${isoOf(t.last_jd)}` : 'not available'}</b></div>
    ${endTxt ? `<p class="caveat">${esc(endTxt)}</p>` : ''}
    <div><h3>Events</h3><div class="res">${ev.map(e => `<div class="r ${e.status === 'planned' ? 'planned' : ''}"><div class="head"><span class="name">${esc(e.what)}${e.body ? ' · ' + esc(e.body) : ''}</span><span class="vt">${esc(liveFmt(e.date))}</span></div>
      <div class="list">${t && jdOfIso(e.date) >= t.jd0 && jdOfIso(e.date) <= t.last_jd ? `<button type="button" data-livego="${esc(e.date)}">Go to this date</button>` : ''}${e.source ? `<a href="${esc(e.source)}" target="_blank" rel="noopener">source</a>` : ''}</div></div>`).join('')}</div></div>
    <div class="list">${t ? `<button type="button" id="liveFrame">Show the whole path</button><button type="button" id="liveRide">Ride along</button>` : ''}${cmp ? `<button type="button" id="liveCmp">This trip in solmaps, from ${isoOf(state.jd)}</button>` : ''}</div>
    ${cmp ? `<p class="caveat">The probe flies with ${esc(m.propulsion_note || 'its own engines and flybys')}; solmaps' transfer data assumes short burns at both ends, so the comparison shows what a direct trip would cost.</p>` : ''}
    <div><h3>Sources</h3><div class="list">${(m.sources || []).map(u => `<a href="${esc(u)}" target="_blank" rel="noopener">${esc(u.replace(/^https?:\/\/(www\.)?/, '').split('/')[0])}</a>`).join(' ')}</div></div>
    <p class="caveat">Trajectory: JPL Horizons, spacecraft ${esc(m.horizons_id || '–')}. Plans change after course corrections; the page refreshes the paths now and then.</p>
    <button type="button" id="liveBack">All live missions</button>`;
}
function liveFrame(m) {                                  // camera on the whole path
  const it = LIVE.items[m.id]; if (!it) return;
  it.flown.geometry.computeBoundingSphere(); const bs = it.flown.geometry.boundingSphere.clone();
  const a = it.flown.geometry.attributes.position.array; let c = new THREE.Vector3(), R = 0; const n = a.length / 3;
  for (let i = 0; i < n; i++) c.add(new THREE.Vector3(a[3 * i], a[3 * i + 1], a[3 * i + 2])); c.divideScalar(n);
  for (let i = 0; i < n; i++) R = Math.max(R, c.distanceTo(new THREE.Vector3(a[3 * i], a[3 * i + 1], a[3 * i + 2])));
  state.follow = null; controls.target.copy(c); camera.position.copy(c.clone().add(new THREE.Vector3(0, R * 1.3 + 4, R * 1.6 + 6)));
}
function liveRide(m) {
  const it = LIVE.items[m.id]; if (!it) return;
  const t = it.t, samples = []; for (let i = 0; i < t.n; i += Math.max(1, Math.round(5 / t.step_days))) samples.push([t.jd0 + i * t.step_days, t.xyz[3 * i], t.xyz[3 * i + 1], t.xyz[3 * i + 2]]);
  const start = Math.max(t.jd0, Math.min(state.jd, t.last_jd - 30)), stops = (m.events || []).filter(e => e.body_id && BY[e.body_id] && e.date).map(e => ({ id: e.body_id, jd: jdOfIso(e.date), fly: /flyby|swing-?by|gravity assist/i.test(e.what) }))
    .filter(s => s.jd >= start && s.jd <= t.last_jd);
  const ship = shipMesh(LIVE_ON); flightGroup.add(ship);
  const f = { from: m.launch_body, to: (m.targets || [])[0] || m.launch_body, name: m.name, dv: 0, jdDep: start, tof: t.last_jd - start, samples, ship, line: { material: { opacity: 1 } }, stops, live: true };
  state.flights.push(f); state.sel = null; renderPanel(); ride([f]);
}
function liveCompare(m) {                              // the same trip in solmaps' data, starting on the date shown
  const to = (m.targets || []).find(x => NODES12.some(n => n.id === x)) || (m.targets || []).find(x => MP.bodies.includes(x)); if (!to) return;
  if (NODES12.some(n => n.id === to) && NODES12.some(n => n.id === m.launch_body)) {
    if (!state.tradeView) $('btnTrade').click();
    $('xFrom').value = m.launch_body; $('xTo').value = to; $('xStart').value = isoOf(state.jd); $('xFrom').dispatchEvent(new Event('change'));
  } else routesFrom(m.launch_body).then(() => { const r = routeList.find(x => x.site === to); if (r) { state.hl = r.key; state.hlScroll = true; routeKey = ''; updateRoutes(); renderPanel(); } });
}
function bindLive() {
  const P = $('panel');
  P.querySelectorAll('[data-live]').forEach(el => el.addEventListener('click', () => liveSelect(el.dataset.live)));
  P.querySelectorAll('[data-livego]').forEach(el => el.addEventListener('click', () => setJD(jdOfIso(el.dataset.livego))));
  const sel = state.sel && BY[state.sel] && BY[state.sel].type === 'mission' ? BY[state.sel].mission : null;
  if (sel) {
    const f = P.querySelector('#liveFrame'); if (f) f.addEventListener('click', () => liveFrame(sel));
    const r = P.querySelector('#liveRide'); if (r) r.addEventListener('click', () => liveRide(sel));
    const c = P.querySelector('#liveCmp'); if (c) c.addEventListener('click', () => liveCompare(sel));
  }
  const back = P.querySelector('#liveBack'); if (back) back.addEventListener('click', () => { state.sel = null; state.follow = null; renderPanel(); });
}
async function liveSet(on) {
  state.live = on; $('btnLive').setAttribute('aria-pressed', on); LIVE.group.visible = on;
  if (on) {
    openPanel(true); state.journey = false; $('btnJourney').setAttribute('aria-pressed', false);
    const now = jdOf(Math.min(Date.now(), DAY1)); if (Math.abs(state.jd - now) > 0.5) setJD(now);   // live means the real date
    try { await liveLoad(); } catch (e) { $('panel').innerHTML = `<p class="caveat">The trajectories could not be loaded (${esc(e.message)}).</p>`; return; }
    liveUpdate(true); state.sel = null; renderPanel();
  } else {
    for (const m of LIVE_REG.missions) delete pos3[liveId(m.id)];
    if (state.sel && state.sel.startsWith('m:')) { state.sel = null; state.follow = null; }
    renderPanel();
  }
}
async function liveSelect(id) { if (!state.live) await liveSet(true); liveUpdate(true); select(liveId(id)); }
$('btnLive').addEventListener('click', () => liveSet(!state.live));
