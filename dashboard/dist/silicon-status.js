// GARDA-chip status for the dashboard, from the same layout facts the GDSII
// explorer shows (site/GDSII/assets/layout.json, built from the hardened run's
// metrics by tools/gdsii_site.py), so the two sites can never disagree.
// Renders its own English or Indonesian copy and re-renders on a language switch.
const SOURCE = 'https://wlmoi.github.io/GARDA/GDSII/assets/layout.json';
// the same values, for when the fetch fails (offline, Pages not deployed yet)
const FALLBACK = { klayout_drc_errors: 0, lvs_errors: 0, route_drc_errors: 0, antenna_violating_nets: 0, setup_ws_typ_ns: 0.36, setup_ws_slow_ns: -7.69, stdcells: 31305, macros: 10 };
const esc = s => String(s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const id = () => document.documentElement.lang === 'id';
let current = FALLBACK, isLive = false;

function render(ev, live) {
  current = ev; isLive = live;
  const I = id(), n = v => v.toLocaleString(I ? 'id-ID' : 'en-US');
  const sign = v => (v > 0 ? '+' : '') + n(v);
  const err = v => I ? `${v} error` : `${v} errors`;
  const checks = [
    [I ? 'RTL: PRISM + TinyQV, testbench cocotb' : 'RTL: PRISM + TinyQV, cocotb testbench', 'pass', I ? 'Ada di repo' : 'In repo'],
    [I ? `Sintesis: ${n(ev.stdcells)} sel, ${ev.macros} makro` : `Synthesis: ${n(ev.stdcells)} cells, ${ev.macros} macros`, 'pass', I ? 'Selesai' : 'Done'],
    [I ? 'Place and route, DRC router' : 'Place and route, router DRC', ev.route_drc_errors === 0 ? 'pass' : 'running', err(ev.route_drc_errors)],
    [I ? 'KLayout DRC (deck lengkap)' : 'KLayout DRC (full deck)', ev.klayout_drc_errors === 0 ? 'pass' : 'running', err(ev.klayout_drc_errors)],
    [I ? 'LVS, layout vs netlist' : 'LVS, layout vs netlist', ev.lvs_errors === 0 ? 'pass' : 'running', err(ev.lvs_errors)],
    ['Antenna', ev.antenna_violating_nets === 0 ? 'pass' : 'running', I ? `${ev.antenna_violating_nets} net` : `${ev.antenna_violating_nets} nets`],
    [I ? 'Timing setup, corner tipikal' : 'Setup timing, typical corner', ev.setup_ws_typ_ns >= 0 ? 'pass' : 'running', `${sign(ev.setup_ws_typ_ns)} ns`],
    [I ? 'Timing setup, corner lambat' : 'Setup timing, slow corner', ev.setup_ws_slow_ns >= 0 ? 'pass' : 'running', I ? `${sign(ev.setup_ws_slow_ns)} ns, belum terpenuhi` : `${sign(ev.setup_ws_slow_ns)} ns, not met`],
    [I ? 'Pengajuan tapeout' : 'Tapeout submission', 'not_run', I ? 'Belum tercatat' : 'Not recorded'],
    [I ? 'Silikon terfabrikasi' : 'Fabricated silicon', 'not_run', I ? 'Belum' : 'Not yet'],
  ];
  const box = document.getElementById('tt-checks');
  if (box) {
    box.dataset.i18nSkip = '';
    box.innerHTML = checks.map(([label, status, result]) =>
      `<div class="tt-check" data-status="${status}" role="listitem"><span class="tt-check-label">${esc(label)}</span><strong class="tt-check-result">${esc(result)}</strong></div>`).join('');
    box.dataset.source = live ? 'live' : 'fallback';
  }
  const res = document.getElementById('chip-result');
  if (res) { res.dataset.i18nSkip = ''; res.textContent = `DRC ${ev.klayout_drc_errors} / LVS ${ev.lvs_errors}`; }
  const st = document.getElementById('chip-status');
  if (st) {
    const ok = ev.klayout_drc_errors === 0 && ev.lvs_errors === 0;
    st.dataset.i18nSkip = '';
    st.textContent = ok ? (I ? 'LAYOUT LOLOS SIGN-OFF' : 'LAYOUT SIGNED OFF') : (I ? 'SIGN-OFF BELUM SELESAI' : 'SIGN-OFF OPEN');
    st.className = `status-pill ${ok ? 'verified' : 'note'}`;
  }
}

render(FALLBACK, false);
document.addEventListener('garda-language', () => setTimeout(() => render(current, isLive), 0));
fetch(SOURCE, { cache: 'no-cache' })
  .then(r => (r.ok ? r.json() : Promise.reject(r.status)))
  .then(d => { if (d && d.evidence) render(d.evidence, true); })
  .catch(() => {});
