// GARDA-chip status for the dashboard, from the same layout facts the GDSII
// explorer shows (site/GDSII/assets/layout.json, built from the hardened run's
// metrics by tools/gdsii_site.py), so the two sites can never disagree.
const SOURCE = 'https://wlmoi.github.io/GARDA/GDSII/assets/layout.json';
// the same values, for when the fetch fails (offline, Pages not deployed yet)
const FALLBACK = { klayout_drc_errors: 0, lvs_errors: 0, route_drc_errors: 0, antenna_violating_nets: 0, setup_ws_typ_ns: 0.36, setup_ws_slow_ns: -7.69, stdcells: 31305, macros: 10 };
const esc = s => String(s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

function render(ev, live) {
  const sign = n => (n > 0 ? '+' : '') + n;
  const checks = [
    ['RTL: PRISM + TinyQV, cocotb testbench', 'pass', 'In repo'],
    [`Synthesis: ${ev.stdcells.toLocaleString('en-US')} cells, ${ev.macros} macros`, 'pass', 'Done'],
    ['Place and route, router DRC', ev.route_drc_errors === 0 ? 'pass' : 'running', `${ev.route_drc_errors} errors`],
    ['KLayout DRC (full deck)', ev.klayout_drc_errors === 0 ? 'pass' : 'running', `${ev.klayout_drc_errors} errors`],
    ['LVS, layout vs netlist', ev.lvs_errors === 0 ? 'pass' : 'running', `${ev.lvs_errors} errors`],
    ['Antenna', ev.antenna_violating_nets === 0 ? 'pass' : 'running', `${ev.antenna_violating_nets} nets`],
    ['Setup timing, typical corner', ev.setup_ws_typ_ns >= 0 ? 'pass' : 'running', `${sign(ev.setup_ws_typ_ns)} ns`],
    ['Setup timing, slow corner', ev.setup_ws_slow_ns >= 0 ? 'pass' : 'running', `${sign(ev.setup_ws_slow_ns)} ns, not met`],
    ['Tapeout submission', 'not_run', 'Not recorded'],
    ['Fabricated silicon', 'not_run', 'Not yet'],
  ];
  const box = document.getElementById('tt-checks');
  if (box) box.innerHTML = checks.map(([label, status, result]) =>
    `<div class="tt-check" data-status="${status}" role="listitem"><span class="tt-check-label">${esc(label)}</span><strong class="tt-check-result">${esc(result)}</strong></div>`).join('');
  const res = document.getElementById('chip-result');
  if (res) res.textContent = `DRC ${ev.klayout_drc_errors} / LVS ${ev.lvs_errors}`;
  const st = document.getElementById('chip-status');
  if (st) {
    const ok = ev.klayout_drc_errors === 0 && ev.lvs_errors === 0;
    st.textContent = ok ? 'LAYOUT SIGNED OFF' : 'SIGN-OFF OPEN';
    st.className = `status-pill ${ok ? 'verified' : 'note'}`;
  }
  if (box) box.dataset.source = live ? 'live' : 'fallback';
}

render(FALLBACK, false);
fetch(SOURCE, { cache: 'no-cache' })
  .then(r => (r.ok ? r.json() : Promise.reject(r.status)))
  .then(d => { if (d && d.evidence) render(d.evidence, true); })
  .catch(() => {});
