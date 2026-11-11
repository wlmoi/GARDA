// GARDA Judge Mode: one tap starts a hands-free guided tour (about 76 s) that drives
// the page's real simulations (robot view, Parallel16 clock, safety gate) through
// their own controls, then puts every control back the way the visitor left it.
const $ = (selector, root = document) => root.querySelector(selector);
const reduced = matchMedia('(prefers-reduced-motion: reduce)');
const clamp = (v, lo = 0, hi = 1) => Math.min(hi, Math.max(lo, v));
const ease = t => (t < .5 ? 2 * t * t : 1 - (-2 * t + 2) ** 2 / 2);
const text = selector => ($(selector)?.textContent || '').replace(/\s+/g, ' ').trim();
const SEP = '<i class="ic-chip" aria-hidden="true"></i>'; // chip icon instead of a middle dot
const isId = () => document.documentElement.lang === 'id';
const UI = {
  pause: ['Pause tour', 'Jeda tur'], resume: ['Resume tour', 'Lanjutkan tur'], replayTour: ['Replay tour', 'Putar ulang tur'],
  replay: ['Replay', 'Ulang'], prev: ['Previous chapter', 'Bab sebelumnya'], next: ['Next chapter', 'Bab berikutnya'],
  exit: ['Exit judge mode', 'Keluar dari mode juri'], chapters: ['Tour chapters', 'Bab tur'], chapter: ['Chapter', 'Bab'],
  region: ['GARDA judge mode tour', 'Tur mode juri GARDA'], fab: ['Watch GARDA in Action: start the hands-free tour', 'Lihat GARDA beraksi: mulai tur otomatis'],
  fabText: ['Watch in action', 'Lihat beraksi'], complete: ['Tour complete', 'Tur selesai'],
  doneTitle: ['AI computes. Hardware checks.', 'AI menghitung. Hardware memeriksa.'],
  doneText: ['That was GARDA in 76 seconds. Replay it, or close the tour and try every simulation yourself.', 'Itulah GARDA dalam 76 detik. Putar ulang, atau tutup tur dan coba sendiri setiap simulasinya.'],
  cycle: ['Cycle', 'Siklus'], range: ['LiDAR range', 'Jarak LiDAR'], permitted: ['PERMITTED', 'DIIZINKAN'], blocked: ['BLOCKED', 'DIBLOKIR'],
};
const t = key => UI[key][isId() ? 1 : 0];
const L = (step, key) => (isId() && step.id ? step.id[key] : step[key]);
const fmt = ms => { const s = Math.max(0, Math.round(ms / 1000)); return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`; };

function fire(el, type) { el.dispatchEvent(new Event(type, { bubbles: true })); }
function setValue(selector, value, type = 'input') {
  const el = $(selector);
  if (el && String(el.value) !== String(value)) { el.value = value; fire(el, type); }
}
function setFault(id, on) {
  const el = $(`[data-fault="${id}"]`);
  if (el && el.checked !== on) { el.checked = on; fire(el, 'input'); }
}
const isPressed = selector => $(selector)?.getAttribute('aria-pressed') === 'true';
function stopRobot() { if (isPressed('#robot-play')) $('#robot-play').click(); }
function stopClock() { if (isPressed('#clock-play')) $('#clock-play').click(); }
function startRobot(scenario) {
  stopRobot();
  setValue('#robot-platform', 'drone', 'change');
  setValue('#robot-playback', 'motion', 'change');
  const select = $('#robot-scenario');
  if (!select) return;
  select.value = scenario; fire(select, 'change'); // change always rewinds to the start
  $('#robot-play')?.click();
}
function resetGate() {
  document.querySelectorAll('[data-fault]').forEach(el => setFault(el.dataset.fault, false));
  setValue('#candidate-w', 4);
  setValue('#candidate-v', 12);
}

const FAULTS = ['all conditions valid', 'reset active', 'emergency stop', 'protective stop', 'system not ready', 'invalid costmap',
  'invalid configuration', 'arithmetic fault', 'watchdog timeout', 'result incomplete or invalid', 'command over v/omega limit', 'command change over delta limit'];
const FAULTS_ID = ['semua kondisi valid', 'reset aktif', 'emergency stop', 'protective stop', 'sistem belum siap', 'costmap tidak valid',
  'konfigurasi tidak valid', 'fault aritmetika', 'watchdog timeout', 'hasil belum lengkap atau tidak valid', 'perintah melewati batas v/omega', 'perubahan perintah melewati batas delta'];
function gateLive() {
  const code = Number((text('#fault-reason').match(/Fault\s+(\d+)/) || [])[1] || 0);
  const enabled = text('#permit-value') === '1';
  const verdict = enabled ? `<b class="is-pass">${t('permitted')}</b>` : `<b class="is-block">${t('blocked')}</b>${SEP}fault ${code}, ${(isId() ? FAULTS_ID : FAULTS)[code] || ''}`;
  return { html: `AI v <b>${text('#candidate-value')}</b> → motor_enable <b class="${enabled ? 'is-pass' : 'is-block'}">${text('#permit-value')}</b>${SEP}${verdict}`, state: enabled ? 'pass' : 'block' };
}
const robotLive = () => ({ html: `${text('#robot-status')}${SEP}${t('range')} <b>${text('#lidar-distance')}</b>`, state: /stopped|E-stop/i.test(text('#robot-status')) ? 'block' : '' });

const STEPS = [
  { id: { label: 'Pembuka', title: 'Physical AI untuk drone. Diawasi ketat oleh GARDA.', text: 'AI di perangkat mengusulkan setiap gerakan. Gerbang hardware terpisah memutuskan apakah motor boleh bergerak.' },
    label: 'Intro', title: 'Physical AI for drones. Kept in check by GARDA.', dur: 7000, target: '#hero', focus: '.portal-copy', align: 'top',
    text: 'AI on the device proposes every move. A separate hardware gate decides whether the motors may act.' },
  { id: { label: 'Sensor', title: 'Pemindaian sensor', text: 'Drone LiDAR terbang di jalur inspeksinya. Data jarak langsung masuk ke GARDA, tanpa server di tengahnya.' },
    label: 'Sensing', title: 'Sensor scanning', dur: 10000, target: '#robot-demo', focus: '.robot-stage',
    text: 'A LiDAR drone flies its inspection route. Range data goes straight into GARDA, with no server in the loop.',
    at: { 700: () => startRobot('avoid') }, live: robotLive },
  { id: { label: 'Inferensi', title: 'Inferensi AI di hardware', text: '16 jalur MAC menjalankan jaringan saraf dalam 3.556 siklus: 71,12 µs pada 50 MHz. RTL cocok dengan seluruh 236 uji referensi.' },
    label: 'Inference', title: 'AI inference in hardware', dur: 12000, target: '#clock-explorer', focus: '.clock-panel', anchor: '.clock-stats', align: 'top',
    text: '16 MAC lanes run the neural network in 3,556 cycles: 71.12 µs at 50 MHz. The RTL matches all 236 reference tests.',
    enter: () => { stopRobot(); stopClock(); setValue('#clock-slider', 0); },
    tick: ms => setValue('#clock-slider', Math.round(ease(clamp((ms - 700) / 10300)) * 3556)),
    live: () => ({ html: `${t('cycle')} <b>${text('#clock-number')}</b>${SEP}${text('#clock-layer')}${SEP}<b>${text('#clock-time')}</b>` }) },
  { id: { label: 'Rintangan', title: 'Rintangan terdeteksi', text: 'Sebuah rintangan menghalangi jalur. Jarak LiDAR turun dan drone berhenti sebelum menabrak.' },
    label: 'Obstacle', title: 'Obstacle detected', dur: 8000, target: '#robot-demo', focus: '.robot-stage',
    text: 'An obstacle blocks the path. LiDAR range drops and the drone stops short instead of pressing on.',
    at: { 700: () => startRobot('obstacle') }, live: robotLive },
  { id: { label: 'Gerbang', title: 'Intervensi keselamatan hardware', text: 'Kini AI meminta kecepatan di atas batas 20. Gerbang menolak: motor_enable turun ke 0.' },
    label: 'Safety gate', title: 'Hardware safety intervention', dur: 11000, target: '#gate-demo', focus: '#gate-result', anchor: '.gate-sliders',
    text: 'The AI now asks for more speed than the limit of 20 allows. The gate refuses: motor_enable drops to 0.',
    enter: () => { stopRobot(); resetGate(); },
    tick: ms => setValue('#candidate-v', Math.round(12 + ease(clamp((ms - 1800) / 5200)) * 14)), live: gateLive },
  { id: { label: 'E-stop', title: 'Emergency stop', text: 'Perintah aman kembali, jadi motor boleh jalan. Lalu operator menekan E-stop dan gerbang memutus motor_enable, apa pun permintaan AI.' },
    label: 'E-stop', title: 'Emergency stop', dur: 9000, target: '#gate-demo', focus: '#gate-result', anchor: '.gate-sliders',
    text: 'A safe command is back, so the motors may run. Then the operator hits E-stop and the gate cuts motor_enable, whatever the AI says.',
    enter: () => { resetGate(); }, at: { 3800: () => setFault('estop', true) }, live: gateLive },
  { id: { label: 'Verifikasi', title: 'Terverifikasi, siklus demi siklus', text: 'Inti neural cocok di seluruh 708 keluaran. Model gerbang dan Verilog-nya sepakat pada 3.084 vektor yang mencakup 12 fault.' },
    label: 'Verification', title: 'Verified, cycle by cycle', dur: 10000, target: '#verification', focus: '.verification-table-wrap tbody tr:first-child',
    text: 'The neural core matches all 708 outputs. The gate model and its Verilog agree on 3,084 vectors covering 12 faults.',
    enter: () => { const wrap = $('.verification-table-wrap'); if (wrap) wrap.scrollLeft = 0; },
    at: { 4800: () => refocus('.verification-table-wrap tbody tr:nth-child(4)') },
    tick: ms => { const wrap = $('.verification-table-wrap'); if (wrap && wrap.scrollWidth > wrap.clientWidth + 4) wrap.scrollLeft = ease(clamp((ms - 2500) / 5000)) * (wrap.scrollWidth - wrap.clientWidth); } },
  { id: { label: 'Dampak', title: 'Siapa yang diuntungkan', text: 'Unit PLN, operator drone dan integrator robot mendapat penghindaran di perangkat, keputusan yang dapat diaudit, dan penghentian yang tak bisa dibatalkan AI.' },
    label: 'Impact', title: 'Who benefits', dur: 9000, target: '#solution', focus: '.stakeholder-grid',
    text: 'PLN units, drone operators and robot integrators get on-device avoidance, auditable decisions and a stop the AI cannot override.' }
];
const TOTAL = STEPS.reduce((sum, s) => sum + s.dur, 0);
const ICON = {
  play: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M8 5.5v13l10.5-6.5z"/></svg>',
  pause: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M7 5h3.5v14H7zM13.5 5H17v14h-3.5z"/></svg>',
  prev: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 6h2v12H6zM20 6v12L9.5 12z"/></svg>',
  next: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M16 6h2v12h-2zM4 6v12l10.5-6z"/></svg>',
  replay: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 5a7 7 0 1 1-6.6 4.7l1.9.6A5 5 0 1 0 12 7v3L7.5 6 12 2z"/></svg>',
  close: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6.4 5 12 10.6 17.6 5 19 6.4 13.4 12l5.6 5.6-1.4 1.4-5.6-5.6L6.4 19 5 17.6l5.6-5.6L5 6.4z"/></svg>'
};

// ---------- HUD ----------
const hud = document.createElement('section');
hud.className = 'judge-hud';
hud.hidden = true;
hud.dataset.i18nSkip = ''; // the tour localizes its own copy (see T below)
hud.setAttribute('aria-label', 'GARDA judge mode tour');
hud.innerHTML = `
  <div class="judge-progress" role="group" aria-label="Tour chapters">${STEPS.map((s, i) => `<button type="button" class="judge-seg" data-index="${i}" aria-label="Chapter ${i + 1}: ${s.label}" title="${s.label}"><span></span></button>`).join('')}</div>
  <div class="judge-body">
    <div class="judge-copy" aria-live="polite" aria-atomic="true">
      <p class="judge-kicker"><span class="judge-count"></span><span class="judge-time"></span></p>
      <h2 class="judge-title"></h2>
      <p class="judge-text"></p>
    </div>
    <p class="judge-live" aria-hidden="true"></p>
  </div>
  <div class="judge-controls">
    <button type="button" class="judge-btn" data-judge="prev" aria-label="Previous chapter">${ICON.prev}</button>
    <button type="button" class="judge-btn judge-btn-main" data-judge="toggle" aria-label="Pause tour">${ICON.pause}</button>
    <button type="button" class="judge-btn" data-judge="next" aria-label="Next chapter">${ICON.next}</button>
    <button type="button" class="judge-btn judge-btn-text" data-judge="replay" aria-label="Replay tour from the start">${ICON.replay}<span>Replay</span></button>
    <button type="button" class="judge-btn judge-btn-exit" data-judge="exit" aria-label="Exit judge mode">${ICON.close}</button>
  </div>`;
document.body.appendChild(hud);

const fab = document.createElement('button');
fab.type = 'button';
fab.className = 'judge-fab';
fab.dataset.i18nSkip = '';
fab.dataset.judgeStart = '';
fab.hidden = true;
fab.setAttribute('aria-label', 'Watch GARDA in Action: start the hands-free tour');
fab.innerHTML = `${ICON.play}<span>Watch in action</span>`;

function relabel() {
  hud.setAttribute('aria-label', t('region'));
  hud.querySelector('.judge-progress').setAttribute('aria-label', t('chapters'));
  hud.querySelectorAll('.judge-seg').forEach((seg, i) => { const l = L(STEPS[i], 'label'); seg.setAttribute('aria-label', `${t('chapter')} ${i + 1}: ${l}`); seg.title = l; });
  hud.querySelector('[data-judge="prev"]').setAttribute('aria-label', t('prev'));
  hud.querySelector('[data-judge="next"]').setAttribute('aria-label', t('next'));
  hud.querySelector('[data-judge="replay"]').setAttribute('aria-label', t('replayTour'));
  hud.querySelector('[data-judge="replay"] span').textContent = t('replay');
  hud.querySelector('[data-judge="exit"]').setAttribute('aria-label', t('exit'));
  fab.setAttribute('aria-label', t('fab'));
  fab.querySelector('span').textContent = t('fabText');
}
relabel();
// switching language mid-tour updates the copy in place, without restarting the chapter
document.addEventListener('garda-language', () => setTimeout(() => {
  relabel();
  if (!active) return;
  if (done) { ui.count.textContent = t('complete'); ui.title.textContent = t('doneTitle'); ui.text.textContent = t('doneText'); }
  else { const step = STEPS[index]; ui.count.innerHTML = `${String(index + 1).padStart(2, '0')} / ${String(STEPS.length).padStart(2, '0')}${SEP}${L(step, 'label')}`; ui.title.textContent = L(step, 'title'); ui.text.textContent = L(step, 'text'); ui.toggle.setAttribute('aria-label', playing ? t('pause') : t('resume')); }
}, 0));
document.body.appendChild(fab);

const ui = {
  segs: [...hud.querySelectorAll('.judge-seg')], count: $('.judge-count', hud), time: $('.judge-time', hud),
  title: $('.judge-title', hud), text: $('.judge-text', hud), live: $('.judge-live', hud),
  toggle: $('[data-judge="toggle"]', hud), copy: $('.judge-copy', hud)
};

// ---------- engine ----------
let active = false, playing = false, done = false, index = 0, elapsed = 0, last = 0, raf = 0;
let fired = new Set(), saved = null, focused = null, autoPaused = false, wakeLock = null, realign = 0;

function snapshot() {
  const val = s => $(s)?.value;
  return { platform: val('#robot-platform'), playback: val('#robot-playback'), scenario: val('#robot-scenario'), progress: val('#robot-progress'),
    clock: val('#clock-slider'), v: val('#candidate-v'), w: val('#candidate-w'), faults: [...document.querySelectorAll('[data-fault]')].map(el => [el.dataset.fault, el.checked]),
    scrollY: window.scrollY };
}
function restore(state) {
  if (!state) return;
  stopRobot(); stopClock();
  setValue('#robot-platform', state.platform, 'change');
  setValue('#robot-playback', state.playback, 'change');
  const select = $('#robot-scenario'); if (select) { select.value = state.scenario; fire(select, 'change'); }
  setValue('#robot-progress', state.progress);
  setValue('#clock-slider', state.clock);
  state.faults.forEach(([id, on]) => setFault(id, on));
  setValue('#candidate-w', state.w); setValue('#candidate-v', state.v);
  const wrap = $('.verification-table-wrap'); if (wrap) wrap.scrollLeft = 0;
}

function topInset() {
  const bar = $('.topbar');
  if (!bar) return 0;
  const pos = getComputedStyle(bar).position;
  return pos === 'fixed' || pos === 'sticky' ? Math.max(0, bar.getBoundingClientRect().bottom) : 0;
}
function scrollToStep(step, behavior) {
  const el = $(step.focus) || $(step.target);
  if (!el) return;
  const top = topInset() + 12, bottom = hud.getBoundingClientRect().height + 16;
  const band = window.innerHeight - top - bottom, box = el.getBoundingClientRect();
  const anchor = step.anchor && $(step.anchor), lead = anchor?.getBoundingClientRect();
  let y;
  if (lead && box.bottom - lead.top <= band) {
    // the anchor (e.g. the sliders) and the focus (e.g. the result) fit together: frame both, centred
    y = window.scrollY + lead.top - top - Math.max(0, (band - (box.bottom - lead.top)) / 2);
  } else {
    y = window.scrollY + box.top - top;
    if (step.align !== 'top' && box.height < band) y -= (band - box.height) / 2;
  }
  window.scrollTo({ top: Math.max(0, Math.round(y)), behavior: behavior || (reduced.matches ? 'auto' : 'smooth') });
}

function setFocus(step) {
  focused?.classList.remove('judge-focus');
  focused = $(step.focus) || $(step.target);
  focused?.classList.add('judge-focus');
}

// move the spotlight to another element within the current chapter
function refocus(selector) {
  if (!$(selector)) return;
  const step = { ...STEPS[index], focus: selector, anchor: null, align: undefined };
  setFocus(step); scrollToStep(step);
}

function enterStep(i) {
  index = clamp(i, 0, STEPS.length - 1); elapsed = 0; fired = new Set(); done = false;
  const step = STEPS[index];
  hud.classList.remove('is-done');
  ui.count.innerHTML = `${String(index + 1).padStart(2, '0')} / ${String(STEPS.length).padStart(2, '0')}${SEP}${L(step, 'label')}`;
  ui.title.textContent = L(step, 'title');
  ui.text.textContent = L(step, 'text');
  ui.live.innerHTML = ''; ui.live.className = 'judge-live';
  ui.copy.classList.remove('is-in'); void ui.copy.offsetWidth; ui.copy.classList.add('is-in');
  step.enter?.();
  setFocus(step);
  scrollToStep(step);
  // second pass after smooth scrolling: lazy content or pinned sections can shift layout
  clearTimeout(realign);
  realign = setTimeout(() => { if (active && STEPS[index] === step) { const el = $(step.focus) || $(step.target); const off = el ? Math.abs(el.getBoundingClientRect().top - topInset()) : 0; if (off > window.innerHeight * .6) scrollToStep(step, 'auto'); } }, 1100);
  paint();
}

function paint() {
  const before = STEPS.slice(0, index).reduce((sum, s) => sum + s.dur, 0);
  ui.segs.forEach((seg, i) => {
    const fill = i < index || done ? 1 : i === index ? clamp(elapsed / STEPS[i].dur) : 0;
    seg.firstElementChild.style.transform = `scaleX(${fill})`;
    seg.classList.toggle('is-current', i === index && !done);
    seg.toggleAttribute('aria-current', i === index && !done);
  });
  ui.time.textContent = `${fmt(done ? TOTAL : before + elapsed)} / ${fmt(TOTAL)}`;
  // some widgets rewrite their own className (the gate result does), so keep the highlight on
  if (focused && !done && !focused.classList.contains('judge-focus')) focused.classList.add('judge-focus');
  const live = !done && STEPS[index].live?.();
  if (live) { if (ui.live.innerHTML !== live.html) ui.live.innerHTML = live.html; ui.live.className = `judge-live ${live.state ? 'is-' + live.state : ''}`; }
}

function frame(now) {
  raf = requestAnimationFrame(frame);
  const dt = Math.min(100, now - (last || now)); last = now;
  if (!playing || done) return;
  elapsed += dt;
  const step = STEPS[index];
  for (const [at, fn] of Object.entries(step.at || {})) if (elapsed >= Number(at) && !fired.has(at)) { fired.add(at); fn(); }
  step.tick?.(elapsed);
  if (elapsed >= step.dur) { if (index < STEPS.length - 1) enterStep(index + 1); else finish(); }
  paint();
}

function setPlaying(on) {
  playing = on && !done;
  hud.classList.toggle('is-paused', !playing && !done);
  ui.toggle.innerHTML = playing ? ICON.pause : ICON.play;
  ui.toggle.setAttribute('aria-label', playing ? t('pause') : done ? t('replayTour') : t('resume'));
  if (!playing) { stopRobot(); stopClock(); }
  else if (STEPS[index].at) { // resume a robot chapter: replay its scripted action
    const shot = Object.keys(STEPS[index].at).find(at => fired.has(at));
    if (shot) STEPS[index].at[shot]();
  }
  lockScreen(playing);
}

async function lockScreen(on) {
  try {
    if (on && 'wakeLock' in navigator && !wakeLock) { wakeLock = await navigator.wakeLock.request('screen'); wakeLock.addEventListener('release', () => { wakeLock = null; }); }
    if (!on && wakeLock) { await wakeLock.release(); wakeLock = null; }
  } catch { wakeLock = null; }
}

function finish() {
  done = true; playing = false; elapsed = 0;
  focused?.classList.remove('judge-focus'); focused = null;
  restore(saved);
  hud.classList.add('is-done'); hud.classList.remove('is-paused');
  ui.count.textContent = t('complete');
  ui.title.textContent = t('doneTitle');
  ui.text.textContent = t('doneText');
  ui.live.innerHTML = ''; ui.live.className = 'judge-live';
  ui.toggle.innerHTML = ICON.replay; ui.toggle.setAttribute('aria-label', t('replayTour'));
  lockScreen(false);
  paint();
}

function start() {
  if (!active) { saved = snapshot(); }
  active = true;
  document.documentElement.classList.add('judge-active');
  document.querySelector('.mobile-menu-toggle[aria-expanded="true"]')?.click();
  hud.hidden = false; fab.hidden = true;
  syncPad();
  if (!raf) { last = 0; raf = requestAnimationFrame(frame); }
  enterStep(0);
  setPlaying(true);
  ui.toggle.focus({ preventScroll: true });
}

function exit() {
  if (!active) return;
  active = false; playing = false; done = false;
  cancelAnimationFrame(raf); raf = 0; clearTimeout(realign);
  focused?.classList.remove('judge-focus'); focused = null;
  restore(saved); saved = null;
  hud.hidden = true;
  document.documentElement.classList.remove('judge-active');
  document.documentElement.style.removeProperty('--judge-hud-h');
  lockScreen(false);
  updateFab();
  if (location.hash === '#judge') history.replaceState(null, '', location.pathname + location.search);
}

// ---------- wiring ----------
hud.addEventListener('click', event => {
  const seg = event.target.closest('.judge-seg');
  if (seg) { enterStep(Number(seg.dataset.index)); setPlaying(true); return; }
  const action = event.target.closest('[data-judge]')?.dataset.judge;
  if (action === 'toggle') { if (done) { saved = snapshot(); enterStep(0); setPlaying(true); } else setPlaying(!playing); }
  if (action === 'next') { if (index < STEPS.length - 1 && !done) { enterStep(index + 1); setPlaying(true); } else finish(); }
  if (action === 'prev') { enterStep(done ? STEPS.length - 1 : elapsed > 2500 ? index : index - 1); setPlaying(true); }
  if (action === 'replay') { if (done) saved = snapshot(); enterStep(0); setPlaying(true); }
  if (action === 'exit') exit();
});
document.addEventListener('click', event => {
  if (event.target.closest('[data-judge-start]')) { event.preventDefault(); start(); }
});
document.addEventListener('keydown', event => {
  if (!active || event.target.closest('input, select, textarea')) return;
  if (event.key === 'Escape') { exit(); }
  else if (event.key === ' ' && !event.target.closest('button, a, summary')) { event.preventDefault(); if (!done) setPlaying(!playing); }
  else if (event.key === 'ArrowRight' && event.target.closest('.judge-hud')) { enterStep(index + 1); setPlaying(true); }
  else if (event.key === 'ArrowLeft' && event.target.closest('.judge-hud')) { enterStep(index - 1); setPlaying(true); }
});
document.addEventListener('visibilitychange', () => {
  if (!active || done) return;
  if (document.hidden && playing) { autoPaused = true; setPlaying(false); }
  else if (!document.hidden && autoPaused) { autoPaused = false; setPlaying(true); }
});

function syncPad() { document.documentElement.style.setProperty('--judge-hud-h', `${Math.ceil(hud.getBoundingClientRect().height)}px`); }
new ResizeObserver(() => { if (active) syncPad(); }).observe(hud);

// Floating launcher appears once the hero (and its big button) has scrolled away.
let heroVisible = true;
function updateFab() { fab.hidden = active || heroVisible; }
const hero = $('#hero');
if (hero && 'IntersectionObserver' in window) {
  new IntersectionObserver(entries => { heroVisible = entries[entries.length - 1].isIntersecting; updateFab(); }, { threshold: 0.05 }).observe(hero);
}

// Deep link for judges (QR codes, slides): …/#judge or ?judge=1 starts the tour.
if (location.hash === '#judge' || new URLSearchParams(location.search).has('judge')) {
  window.addEventListener('load', () => setTimeout(start, 600), { once: true });
}
window.gardaJudge = { start, exit, get state() { return { active, playing, done, index, elapsed, total: TOTAL, steps: STEPS.length }; } };
