'use strict';
const $ = s => document.querySelector(s);
const hex = (n, w = 2) => n.toString(16).toUpperCase().padStart(w, '0');
const C = { blue: '#315CFF', lime: '#B7FF35', red: '#FF5364', amber: '#FFBD59', mut: '#9aa6d6', line: '#26336e' };
const S = { packets: [], sel: null, proto: null, mode: 'NONE', state: {}, vectors: [], tab: 'dec', anims: [], clock: 0, paused: false, speed: 1,
  lastTxEnd: 0, hot: {}, safety: {}, respondedLive: false, steps: {}, nEvents: 0, tl: [] };
const STEP_NAMES = ['1 Status request (op 7)', '2 ROM read vs reference (op 8)', '3 NN test vector 0 vs reference (ops 10-13)', '4 Safety gate readout (ops 7, 14)', '5 E-stop confirmation (KEY1, operator-assisted)'];

async function api(path, body) {
  const r = await fetch(path, body === undefined ? {} : { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
  const j = await r.json(); if (!r.ok) throw new Error(j.error || r.statusText); return j;
}

// ---------------- diagram (real hierarchy: garda_uart_top > garda_uart_protocol > rx/tx, garda_top, garda_neural_core)
const NS = 'http://www.w3.org/2000/svg';
const BLOCKS = [ // id, label, sublabel, x, y, w, h, live?
  ['host', 'HOST PC', 'pyserial', 14, 125, 100, 60, true], ['usb', 'USB-to-UART', 'bridge', 150, 130, 96, 50, true],
  ['rx', 'garda_uart_rx', '8N1 sampler', 300, 52, 118, 46], ['prot', 'garda_uart_protocol', 'frame + CRC8, opcode/payload regs', 440, 52, 150, 46],
  ['dec', 'garda_uart_top', 'payload_ok + op decode', 612, 52, 130, 46], ['core', 'garda_top / neural_core', 'DWA planner + safety gate / NN', 612, 196, 150, 56],
  ['mux', 'response mux', 'garda_uart_top', 448, 202, 120, 46], ['enc', 'out_frame / response_sample', 'garda_uart_protocol', 300, 202, 130, 46], ['tx', 'garda_uart_tx', '8N1 shifter', 790, 202, 110, 46]];
const PATH_TX = ['host', 'usb', 'rx', 'prot', 'dec', 'core'];
const PATH_RX = ['core', 'mux', 'enc', 'tx', 'usb', 'host'];
function center(id) { const b = BLOCKS.find(b => b[0] === id); return [b[3] + b[5] / 2, b[4] + b[6] / 2]; }
function drawDiagram() {
  const svg = $('#diagram'); svg.innerHTML = '';
  const el = (t, a, txt) => { const e = document.createElementNS(NS, t); for (const k in a) e.setAttribute(k, a[k]); if (txt) e.textContent = txt; svg.appendChild(e); return e; };
  el('rect', { x: 270, y: 14, width: 676, height: 300, rx: 14, fill: '#0d1a55', stroke: C.blue, 'stroke-width': 2 });
  el('text', { x: 284, y: 34, fill: C.mut }, 'DE10 board · Cyclone V FPGA');
  el('text', { x: 560, y: 34, fill: C.amber }, 'dashed blocks: explanatory, not live telemetry');
  const all = [...PATH_TX, ...PATH_RX];
  for (let i = 0; i < PATH_TX.length - 1; i++) el('line', { x1: center(PATH_TX[i])[0], y1: center(PATH_TX[i])[1], x2: center(PATH_TX[i + 1])[0], y2: center(PATH_TX[i + 1])[1], stroke: C.line, 'stroke-width': 2 });
  for (let i = 0; i < PATH_RX.length - 1; i++) el('line', { x1: center(PATH_RX[i])[0], y1: center(PATH_RX[i])[1], x2: center(PATH_RX[i + 1])[0], y2: center(PATH_RX[i + 1])[1], stroke: C.line, 'stroke-width': 2, 'stroke-dasharray': '4 4' });
  BLOCKS.forEach(([id, l, sub, x, y, w, h, live]) => {
    const hot = S.hot[id];
    el('rect', { x, y, width: w, height: h, rx: 8, fill: hot ? hot.c + '33' : '#101942', stroke: hot ? hot.c : (live ? C.mut : C.blue), 'stroke-width': hot ? 3 : 1.5, 'stroke-dasharray': live ? '' : '5 3' });
    el('text', { x: x + w / 2, y: y + h / 2 - 2, 'text-anchor': 'middle', 'font-weight': 700 }, l);
    el('text', { x: x + w / 2, y: y + h / 2 + 12, 'text-anchor': 'middle', fill: C.mut, 'font-size': 9 }, sub);
  });
  el('text', { x: 20, y: 215, fill: C.mut, 'font-size': 10 }, 'TX line →  FPGA RX pin');
  el('text', { x: 20, y: 230, fill: C.mut, 'font-size': 10 }, '← RX line  FPGA TX pin');
  for (const a of S.anims) { // packet dots
    const p = a.pos; if (!p) continue;
    el('circle', { cx: p[0], cy: p[1], r: 8, fill: a.c, stroke: '#fff', 'stroke-width': 1.5 });
    el('text', { x: p[0], y: p[1] - 13, 'text-anchor': 'middle', fill: a.c, 'font-size': 10 }, a.label);
  }
}
function enqueueAnim(path, color, label) {
  const start = Math.max(S.clock, S.lastTxEnd); const dur = 2400; S.lastTxEnd = start + dur + 150;
  S.anims.push({ path, c: color, label, start, dur, pos: null });
}
let last = performance.now();
function frame(now) {
  const dt = now - last; last = now;
  if (!S.paused) S.clock += dt * S.speed;
  S.hot = {};
  S.anims = S.anims.filter(a => S.clock < a.start + a.dur);
  for (const a of S.anims) {
    const t = (S.clock - a.start) / a.dur; if (t < 0) { a.pos = null; continue; }
    const n = a.path.length - 1, f = Math.min(t, 0.9999) * n, i = Math.floor(f), u = f - i;
    const p0 = center(a.path[i]), p1 = center(a.path[i + 1]);
    a.pos = [p0[0] + (p1[0] - p0[0]) * u, p0[1] + (p1[1] - p0[1]) * u];
    S.hot[a.path[Math.round(f)]] = { c: a.c };
  }
  drawDiagram(); drawWave(); requestAnimationFrame(frame);
}

// ---------------- event handling
function tlClass(e) { return e.validation === 'fail' ? 'tl-fail' : e.validation === 'warn' ? 'tl-warn' : e.validation === 'ok' ? 'tl-ok' : (e.type.startsWith('TX') ? 'tl-tx' : ''); }
function handle(e) {
  S.nEvents++;
  const t0 = S.tl.length ? S.tl[0].ts : e.ts; S.tl.push(e); if (S.tl.length > 400) S.tl.shift();
  const tl = $('#timeline'), d = document.createElement('div'); d.className = tlClass(e);
  d.textContent = `+${((e.ts - t0) * 1000).toFixed(1).padStart(9)} ms  #${e.id} ${e.type}${e.request_id ? ' r' + e.request_id : ''} [${e.source}/${e.mode}]${e.raw ? ' ' + e.raw : ''}${e.note ? ' — ' + e.note : ''}${e.verified === false ? ' (inferred/simulated)' : ''}`;
  tl.appendChild(d); while (tl.childElementCount > 400) tl.firstChild.remove(); tl.scrollTop = tl.scrollHeight;
  switch (e.type) {
    case 'TX_STARTED': addPacket(e, 'HOST→FPGA', 'tx'); enqueueAnim(PATH_TX, C.blue, e.decoded?.op_name || 'TX'); break;
    case 'FRAME_DECODED': {
      const ok = e.validation === 'ok'; addPacket(e, 'FPGA→HOST', ok ? 'ok' : 'fail');
      if (ok && S.mode === 'LIVE') S.respondedLive = true;
      enqueueAnim(PATH_RX, ok ? C.lime : C.red, ok ? 'RESP' : 'BAD'); gateFrom(e); break;
    }
    case 'COMMAND_TIMEOUT': addPacket(e, 'FPGA→HOST', 'fail'); enqueueAnim(PATH_RX.slice(0, 2), C.red, 'TIMEOUT'); break;
    case 'ESTOP_CONFIRMED': enqueueAnim(PATH_RX, C.red, 'E-STOP'); break;
    case 'DEMO_STEP': demoStep(e); break;
    case 'DEMO_SUMMARY': showSummary(e.decoded); break;
    case 'PORT_OPENED': case 'PORT_CLOSED': case 'PORT_ERROR': case 'TRACE_LOADED': refreshState(); break;
  }
  if (e.type === 'TX_STARTED' || e.type === 'FRAME_DECODED' || e.type === 'COMMAND_TIMEOUT') renderList();
}
function addPacket(e, dir, cls) {
  const raw = e.raw ? e.raw.split(' ').map(h => parseInt(h, 16)) : [];
  S.packets.push({ id: e.id, rid: e.request_id, dir, cls, raw, dec: e.decoded, ts: e.ts, type: e.type, mode: e.mode, note: e.note });
  if (S.packets.length > 600) S.packets.shift();
  if (!S.sel || S.follow !== false) S.sel = S.packets[S.packets.length - 1].id;
}
function renderList() {
  const p = $('#plist'), t0 = (S.packets.slice(-120)[0] || {}).ts || 0; p.innerHTML = '';
  S.packets.slice(-120).forEach(k => {
    const d = document.createElement('div'); d.className = k.cls + (k.id === S.sel ? ' sel' : '');
    d.innerHTML = `<span>+${(k.ts - t0).toFixed(3)}s</span><span>${k.dir.startsWith('HOST') ? 'TX' : 'RX'}</span><span>${k.dec?.op_name || k.type} ${k.raw.map(b => hex(b)).join(' ')}</span>`;
    d.onclick = () => { S.sel = k.id; S.follow = false; renderList(); }; p.appendChild(d);
  });
  p.scrollTop = p.scrollHeight; renderDetail();
}
function pairOf(k) { return S.packets.filter(x => x.rid && x.rid === k.rid); }
function renderDetail() {
  const k = S.packets.find(x => x.id === S.sel), el = $('#detail'); if (!k) { el.textContent = 'Select a packet.'; return; }
  if (S.tab === 'hex') {
    el.innerHTML = `<div>${k.raw.map(b => `<span class="hexb">${hex(b)}</span>`).join('') || '(no bytes)'}</div><pre>${k.raw.map((b, i) => `[${i}] 0x${hex(b)}  ${b.toString(2).padStart(8, '0')}`).join('\n')}</pre>`; return;
  }
  const d = k.dec || {}, rows = [];
  const add = (a, b, c = '') => rows.push(`<tr><td>${a}</td><td class="${c}">${b}</td></tr>`);
  const rr = pairOf(k), req = rr.find(x => x.dir.startsWith('HOST')), rsp = rr.find(x => !x.dir.startsWith('HOST'));
  add('time', new Date(k.ts * 1000).toISOString()); add('direction', k.dir); add('mode', k.mode, k.mode === 'LIVE' ? 'ok-t' : 'warn-t');
  add('length', k.raw.length + ' bytes'); add('request id', k.rid ?? '-');
  if (d.opcode !== undefined) add('command', `${d.opcode} ${d.op_name}`);
  if (d.payload !== undefined) add('payload', `0x${hex(d.payload, 8)} (${d.payload}) little-endian`), add('payload_ok (RTL rule)', d.payload_ok ? 'yes' : 'NO — RTL would latch sticky fault', d.payload_ok ? 'ok-t' : 'fail-t');
  if (d.data !== undefined) { add('data', `0x${hex(d.data, 8)} (${d.data})`); for (const [kk, v] of Object.entries(d.fields || {})) add('· ' + kk, String(v)); }
  if (d.crc_tx !== undefined) { add('CRC transmitted', '0x' + hex(d.crc_tx)); add('CRC calculated', '0x' + hex(d.crc_calc)); add('CRC check', d.crc_ok ? 'VALID' : 'ERROR', d.crc_ok ? 'ok-t' : 'fail-t'); }
  if (d.errors?.length) add('errors', d.errors.join('; '), 'fail-t');
  if (d.rtt_us !== undefined) add('host round-trip', `${d.rtt_us.toFixed(0)} µs (host-side, includes USB latency; RTL cycles are separate)`);
  if (d.received !== undefined) add('timeout', `received ${d.received}/8 bytes`, 'fail-t');
  if (req && rsp && k.dir.startsWith('FPGA')) add('request↔response', `r${k.rid} opcode ${req.dec?.opcode} → echo ${rsp.dec?.opcode}`, req.dec?.opcode === rsp.dec?.opcode ? 'ok-t' : 'fail-t');
  add('sequence number', 'not supported by protocol v1 (one outstanding request)');
  if (k.note) add('note', k.note, 'warn-t');
  el.innerHTML = `<table>${rows.join('')}</table>`;
}
document.querySelectorAll('.tabs [data-t]').forEach(b => b.onclick = () => { S.tab = b.dataset.t; document.querySelectorAll('.tabs [data-t]').forEach(x => x.classList.toggle('on', x === b)); renderDetail(); });

// ---------------- safety panel (only values the FPGA actually reported)
function gateFrom(e) {
  const d = e.decoded; if (!d?.valid) return;
  if (d.opcode === 14) { S.safety.v = d.fields.v_command; S.safety.w = d.fields.omega_command; }
  else if (d.opcode === 16) S.safety.last = d.fields.last_fault;
  else if (d.opcode === 7) { Object.assign(S.safety, { enable: d.fields.enable, busy: d.fields.busy, done: d.fields.done, fc: d.fields.fault_code, why: d.fields.fault_reason, pf: d.fields.protocol_fault }); }
  S.safety.mode = e.mode; renderSafety(); renderIO();
}
function renderSafety() {
  const s = S.safety, est = s.fc === 2, seen = s.fc !== undefined;
  const cell = (t, v, bad) => `<div class="cell ${bad ? 'bad' : ''}"><small>${t}</small><b>${v}</b></div>`;
  $('#safety').innerHTML = `<div class="safegrid">
    ${cell('Proposed AI motion', 'not exposed over UART', false)}
    ${cell('Hardware safety state', seen ? (s.enable ? 'motor_enable = 1' : 'motor_enable = 0') + ` · fault ${s.fc}` : 'read status (op 7)', seen && !s.enable)}
    ${cell('Final permitted motion', s.v === undefined ? 'read op 14' : `v=${s.v}, ω=${s.w}`, est)}
    ${cell('E-stop (KEY1)', !seen ? 'unknown' : est ? 'ASSERTED → motion forced to 0' : 'not asserted', est)}
    ${cell('Watchdog / lease', !seen ? 'unknown' : s.fc === 8 ? 'EXPIRED (fault 8)' : 'no expiry reported (lease 20 ms)', s.fc === 8)}
    ${cell('Fault reason', seen ? s.why : '—', seen && s.fc !== 0)}</div>
    <div class="chain"><span>AI proposes <i>(internal, unobserved)</i></span>→<span>Safety gate checks (priority list, RTL)</span>→<span class="${est ? 'est' : ''}">${est ? 'PERMITTED = 0 (E-STOP)' : 'permit / reject per fault code'}</span></div>
    <div class="help">${s.mode ? 'Source: ' + s.mode + ' responses. ' : ''}E-stop is the physical KEY1 input; there is no UART command to trigger it. Values appear only after real reads. Run actuator tests with actuators disconnected.</div>
    <div class="row"><button id="rdSafe">Read safety now (ops 7, 14, 16)</button></div>`;
  $('#rdSafe').onclick = async () => { for (const o of [7, 14, 16]) await send(o, 0).catch(err); };
}

// ---------------- board I/O (switches, keys, LEDs)
// LEDs follow the RTL: LED = {fault[3:0], done, busy, rst_n, enable}, all derived from the last status response (op 7).
// Physical inputs cannot be driven over UART: in SIMULATION they are controls, in LIVE they are read-back indicators
// inferred from fault_code (2=KEY1, 3=SW3, 4=SW2 or UART fault). SW0/SW1 are not used by garda_uart_top.
S.io = { sw: [0, 0, 0, 0], key0: false, key1: false };
function ioSim() { return S.mode === 'SIMULATION'; }
function renderIO() {
  const s = S.safety, fc = s.fc, seen = fc !== undefined, sim = ioSim();
  const led = [[0, 'enable', s.enable, 'g'], [1, 'rst_n', seen, 'g'], [2, 'busy', s.busy, 'g'], [3, 'done', s.done, 'g'], ...[0, 1, 2, 3].map(i => [4 + i, 'F' + i, seen && ((fc >> i) & 1), ''])];
  $('#leds').innerHTML = led.map(([i, n, on, k]) => `<div class="led ${k} ${on ? 'on' : ''} ${seen ? '' : 'u'}" title="LED${i} ${n}"><i></i>LED${i}<br>${n}</div>`).join('');
  const infer = [false, false, seen && fc === 4, seen && fc === 3];
  $('#sws').innerHTML = [0, 1, 2, 3].map(i => `<div class="tgl ${(sim ? S.io.sw[i] : infer[i]) ? 'on' : ''} ${sim ? '' : 'inf'} ${i < 2 ? 'unused' : ''}" title="${['unused by garda_uart_top', 'unused by garda_uart_top', 'SW2: inhibits ready (fault 4)', 'SW3: protective stop (fault 3)'][i]}"><button data-i="${i}" aria-label="SW${i}"></button>SW${i}${i < 2 ? '<br>unused' : ''}</div>`).join('');
  $('#key1').classList.toggle('on', sim ? S.io.key1 : seen && fc === 2); $('#key0').classList.toggle('on', sim && S.io.key0);
  ['#key0', '#key1'].forEach(k => $(k).classList.toggle('inf', !sim));
  $('#ioNote').textContent = sim ? 'SIMULATION: clickable, drives the software model' : S.mode === 'LIVE' ? 'LIVE: indicators inferred from FPGA status; operate the physical board' : 'connect first';
  $('#ioHelp').textContent = sim ? 'Click switches; hold KEY1 for E-stop; KEY0 resets (clears sticky fault). Each change triggers real ops 7 and 14 so the safety panel updates.'
    : 'A dashed control is read-back only: the host cannot press board inputs over UART. Flip SW2/SW3 or hold KEY1 on the board and watch the fault code and LEDs update (enable auto-read). SW2 vs a UART fault both show fault 4. LED1 (rst_n) is assumed high whenever the FPGA answers.';
  document.querySelectorAll('#sws button').forEach(b => b.onclick = async () => {
    if (!sim) return flash('Physical input: use the real switch on the board. This indicator only reads it back.');
    const i = +b.dataset.i; S.io.sw[i] ^= 1; await pushIO({ sw: S.io.sw });
  });
}
function flash(t) { $('#ioHelp').innerHTML = `<span class="warn-t">${t}</span>`; }
async function pushIO(body) {
  try { await api('/api/sim/io', body); await send(7, 0); await send(14, 0); } catch (e) { err(e); } renderIO();
}
function keyBind(id, field) {
  const b = $(id), down = async e => { e.preventDefault(); if (!ioSim()) return flash('Physical input: press the real key on the board.'); S.io[field] = true; await pushIO(field === 'key1' ? { key1: true } : { key0: true }); };
  const up = async () => { if (!ioSim() || !S.io[field]) return; S.io[field] = false; await pushIO(field === 'key1' ? { key1: false } : { key0: false }); };
  b.addEventListener('pointerdown', down); b.addEventListener('pointerup', up); b.addEventListener('pointerleave', up);
}
keyBind('#key0', 'key0'); keyBind('#key1', 'key1');
let pollBusy = false;
setInterval(async () => {
  if (!$('#poll').checked || pollBusy || document.hidden || !S.state.connected || S.mode === 'RECORDED' || S.state.demo?.state === 'running') return;
  pollBusy = true; try { await api('/api/send', { op: 7, payload: 0 }); } catch (e) { } pollBusy = false;
}, 500);

// ---------------- demo
function demoStep(e) {
  const d = e.decoded || {}; if (!d.name) return;
  if (d.state === 'start') S.steps[d.name] = { v: 'cur' }; else if (d.state === 'done') S.steps[d.name] = { v: d.verdict, detail: d.detail };
  else if (d.state === 'prompt') $('#banner').hidden = false, $('#banner').className = '', $('#banner').textContent = e.note;
  const done = Object.values(S.steps).filter(x => x.v !== 'cur').length;
  $('#progBar').style.width = (done / STEP_NAMES.length * 100) + '%'; $('#progTxt').textContent = `${done}/${STEP_NAMES.length}`;
  $('#steps').innerHTML = STEP_NAMES.map(n => { const s = S.steps[n]; return `<li class="${s ? s.v : ''}">${n.replace(/^\d /, '')}${s && s.v !== 'cur' ? ` — <b>${s.v}</b>: ${s.detail || ''}` : s ? ' …' : ''}</li>`; }).join('');
}
function showSummary(d) {
  const c = d.summary || {}; $('#progTxt').textContent = d.state;
  $('#verdict').innerHTML = `<span class="${d.overall === 'PASS' ? 'ok-t' : d.overall === 'FAIL' ? 'fail-t' : 'warn-t'}">Verdict (${d.mode}): ${d.overall}</span> — ` +
    Object.entries(c).map(([k, v]) => `${k}: ${v}`).join(', ') + (d.mode === 'SIMULATION' ? ' — SOFTWARE SIMULATION, NOT HARDWARE EVIDENCE' : '');
}
$('#demoBtn').onclick = async () => {
  S.steps = {}; $('#verdict').textContent = ''; $('#steps').innerHTML = ''; $('#progBar').style.width = '0';
  try { await api('/api/demo/start', {}); }
  catch (e) { banner(`${e.message}<br><button id="goSim" class="b-sim">Run clearly-labelled SIMULATION demo instead</button>`, ''); $('#goSim').onclick = async () => { await api('/api/connect', { mode: 'SIMULATION' }); await api('/api/demo/start', {}); }; }
};
$('#dPause').onclick = () => { S.paused = true; };      // UI only: serial acquisition and the backend keep running
$('#dResume').onclick = () => { S.paused = false; };
$('#dReplay').onclick = () => $('#demoBtn').click();
$('#dStop').onclick = () => api('/api/demo/stop', {});

// ---------------- connection / modes
function banner(html, cls) { const b = $('#banner'); b.hidden = !html; b.className = cls || ''; b.innerHTML = html || ''; }
async function refreshState() {
  const s = await api('/api/state'); S.state = s; S.mode = s.mode; const b = $('#modeBadge');
  const map = { LIVE: ['live', S.respondedLive ? 'LIVE HARDWARE · FPGA responding' : 'LIVE PORT OPEN · FPGA not yet verified'], SIMULATION: ['sim', 'SIMULATION · NO FPGA'], RECORDED: ['rec', 'RECORDED TRACE'], NONE: ['none', 'LIVE HARDWARE UNAVAILABLE · not connected'] };
  const [c, t] = map[s.mode] || map.NONE; b.className = 'badge ' + c; b.textContent = t; renderIO();
  if (s.mode === 'SIMULATION') banner('SIMULATION: software-generated protocol model. Nothing here is a measurement from an FPGA.', 'sim');
  else if (s.mode === 'RECORDED') banner(`RECORDED TRACE replay. Original provenance: mode=${s.provenance?.mode || '?'} — ${s.provenance?.note || ''}`, 'rec');
  else if (s.mode === 'NONE' && !$('#banner').innerHTML.includes('goSim')) banner('LIVE HARDWARE UNAVAILABLE. Select a serial port and press Connect LIVE, or choose Simulation / Recorded trace (both clearly labelled).', '');
  else if (s.mode === 'LIVE') banner('', '');
  if (!s.pyserial) $('#btnLive').title = 'pyserial is not installed';
}
async function loadPorts() {
  const ps = await api('/api/ports'); const sel = $('#port');
  sel.innerHTML = ps.length ? ps.map(p => `<option value="${p.device}">${p.device} — ${p.description}</option>`).join('') : '<option value="">no serial ports found</option>';
}
$('#refresh').onclick = loadPorts;
$('#btnLive').onclick = () => api('/api/connect', { mode: 'LIVE', port: $('#port').value, baud: 115200 }).then(() => { S.respondedLive = false; refreshState(); }).catch(e => { banner(e.message, ''); });
$('#btnSim').onclick = () => api('/api/connect', { mode: 'SIMULATION' }).then(refreshState).catch(err);
$('#btnDisc').onclick = () => api('/api/disconnect', {}).then(refreshState);
$('#btnTrace').onclick = () => api('/api/replay', { name: $('#trace').value, speed: S.speed }).catch(err);
$('#speed').onchange = e => { S.speed = parseFloat(e.target.value); };
$('#clr').onclick = async () => { await api('/api/clear', {}); S.packets = []; S.sel = null; $('#timeline').innerHTML = ''; renderList(); };
function err(e) { $('#labOut').innerHTML = `<span class="fail-t">${e.message}</span>`; }
document.querySelectorAll('.panel h2').forEach(h => h.onclick = () => h.parentElement.classList.toggle('col'));

// ---------------- command lab
async function send(op, payload) {
  const r = await api('/api/send', { op, payload }); const x = r.response;
  $('#labOut').innerHTML = r.timeout ? `<span class="fail-t">TIMEOUT: ${r.raw || 'no bytes'} — sticky fault possible, press KEY0</span>` :
    `<span class="${x.valid ? 'ok-t' : 'fail-t'}">${x.valid ? 'valid response' : 'INVALID: ' + x.errors.join('; ')}</span> ${JSON.stringify(x.fields)} · RTT ${r.rtt_us.toFixed(0)} µs`;
  return r;
}
async function initLab() {
  S.proto = await api('/api/protocol');
  $('#op').innerHTML = Object.entries(S.proto.opcodes).map(([k, v]) => `<option value="${k}">${k} ${v[0]}</option>`).join('');
  const help = () => { const o = S.proto.opcodes[$('#op').value]; $('#opHelp').textContent = `payload: ${o[1]} · response: ${o[2]}`; }; $('#op').onchange = help; help();
  $('#send').onclick = () => send(+$('#op').value, Number($('#payload').value)).catch(err);
  const c = S.proto.caps;
  $('#unsup').innerHTML = [[c.nn_features_74, '74-feature input: disabled — deployed RTL exposes the 24-input neural core (ops 10–12) only'],
    [c.estop_command, 'Trigger E-stop over UART: disabled — E-stop is the physical KEY1 input; observe it via status fault 2'],
    [c.reset_command, 'Reset safety state over UART: disabled — sticky faults clear only with physical KEY0']].filter(x => !x[0]).map(x => `<div>⛔ ${x[1]}</div>`).join('');
  S.vectors = await api('/api/vectors');
  $('#vec').innerHTML = S.vectors.slice(0, 100).map(v => `<option value="${v.id}">test vector ${v.id}</option>`).join('');
  $('#feat').innerHTML = Array.from({ length: 24 }, (_, i) => `<input data-i="${i}" value="0" title="feature ${i}, signed Q8.8 raw">`).join('');
  const load = () => { const v = S.vectors[+$('#vec').value]; document.querySelectorAll('#feat input').forEach((el, i) => el.value = v.inputs[i]); };
  $('#loadVec').onclick = load; load();
  $('#runNN').onclick = async () => {
    const ins = [...document.querySelectorAll('#feat input')].map(e => parseInt(e.value, 10) & 0xFFFF);
    try {
      for (let i = 0; i < 24; i++) await api('/api/send', { op: 10, payload: i + ins[i] * 256 });
      await api('/api/send', { op: 11, payload: 0 }); let r;
      for (let k = 0; k < 100; k++) { r = await api('/api/send', { op: 12, payload: 0 }); if (r.response?.fields?.done) break; await new Promise(z => setTimeout(z, 20)); }
      if (!r.response?.fields?.done) throw new Error('NN did not report done');
      const out = []; for (let i = 0; i < 4; i++) out.push((await api('/api/send', { op: 12, payload: i })).response.fields.result_q8_8);
      const lat = (await api('/api/send', { op: 13, payload: 0 })).response.fields.count, v = S.vectors[+$('#vec').value];
      const same = JSON.stringify(ins.map(x => x > 32767 ? x - 65536 : x)) === JSON.stringify(v.inputs);
      $('#nnOut').innerHTML = `outputs (Q8.8 raw): ${out.join(', ')} · RTL latency ${lat} cycles` + (same ? ` · reference ${v.expected.join(', ')} → <b class="${JSON.stringify(out) === JSON.stringify(v.expected) ? 'ok-t' : 'fail-t'}">${JSON.stringify(out) === JSON.stringify(v.expected) ? 'MATCH' : 'MISMATCH'}</b>` : ' · inputs edited: no reference available');
    } catch (e) { err(e); }
  };
  const tr = await api('/api/traces'); $('#trace').innerHTML = tr.map(t => `<option>${t}</option>`).join('') || '<option value="">no traces</option>';
}

// ---------------- waveform (DECODED RECONSTRUCTION)
const W = { x0: 0, span: null, cursor: null, paused: false, byte: null };
function wavesFor() {
  const k = S.packets.find(x => x.id === S.sel); if (!k) return null;
  const pr = pairOf(k), tx = (k.rid ? pr.find(x => x.dir.startsWith('HOST')) : k), rx = k.rid ? pr.find(x => !x.dir.startsWith('HOST')) : null;
  const t = tx ? UartWave.build(tx.raw, 115200, 0) : null, off = t ? t.end : 0, r = rx ? UartWave.build(rx.raw, 115200, off) : null;
  return { t, r, end: r ? r.end : (t ? t.end : 1) };
}
function drawWave() {
  const cv = $('#wave'); if (!cv.offsetParent) return; const g = cv.getContext('2d'), w = wavesFor(); g.clearRect(0, 0, cv.width, cv.height);
  g.fillStyle = C.mut; g.font = '12px system-ui';
  if (!w || (!w.t && !w.r)) { g.fillText('No packet selected. Send a command to reconstruct its UART frames.', 20, 40); return; }
  const span = W.span || w.end * 1.02, x2 = t => (t - W.x0) / span * cv.width; $('#wInfo').textContent = `view ${W.x0.toFixed(0)}–${(W.x0 + span).toFixed(0)} µs · 8.68 µs/bit · 86.8 µs/byte`;
  [[w.t, 60, C.blue, 'TX (host→FPGA)'], [w.r, 150, C.lime, 'RX (FPGA→host)']].forEach(([wf, y, col, name]) => {
    g.fillStyle = C.mut; g.fillText(name, 6, y - 50); if (!wf) { g.fillText('(no response bytes)', 6, y); return; }
    const hi = y - 22, lo = y + 14; g.strokeStyle = col; g.lineWidth = 2; g.beginPath();
    let lvl = 1; g.moveTo(x2(wf.frames[0].t0 - 40), hi); g.lineTo(x2(wf.frames[0].t0), hi);
    wf.frames.forEach(f => { f.bits.forEach((b, i) => { const xa = x2(f.t0 + i * wf.bitUs), xb = x2(f.t0 + (i + 1) * wf.bitUs); g.lineTo(xa, b ? hi : lo); g.lineTo(xb, b ? hi : lo); }); });
    g.lineTo(x2(wf.end + 40), hi); g.stroke();
    wf.frames.forEach(f => {
      const xa = x2(f.t0), xb = x2(f.t1), sel = W.byte && W.byte.t === wf && W.byte.i === f.idx;
      g.strokeStyle = sel ? '#fff' : C.line; g.lineWidth = 1; g.strokeRect(xa, hi - 14, xb - xa, lo - hi + 28);
      g.fillStyle = col; g.fillText(hex(f.byte), xa + 3, hi - 18);
      if ((xb - xa) / 10 > 24) f.bits.forEach((b, i) => { g.fillStyle = C.mut; g.fillText(i === 0 ? 'S' : i === 9 ? 'P' : 'D' + (i - 1), x2(f.t0 + (i + .25) * wf.bitUs), lo + 24); g.strokeStyle = '#1d2a66'; g.beginPath(); g.moveTo(x2(f.t0 + i * wf.bitUs), hi - 12); g.lineTo(x2(f.t0 + i * wf.bitUs), lo + 12); g.stroke(); });
    });
  });
  if (W.cursor !== null) { g.strokeStyle = C.amber; g.beginPath(); g.moveTo(x2(W.cursor), 0); g.lineTo(x2(W.cursor), cv.height); g.stroke(); if (!W.paused) { W.cursor += w.end / 240 * S.speed; if (W.cursor > w.end) W.cursor = null; } }
}
const wspan = () => W.span || (wavesFor()?.end || 1000) * 1.02;
$('#zin').onclick = () => { W.span = wspan() / 1.6; }; $('#zout').onclick = () => { W.span = wspan() * 1.6; };
$('#pl').onclick = () => { W.x0 -= wspan() * .2; }; $('#pr').onclick = () => { W.x0 += wspan() * .2; };
$('#wpause').onclick = () => { W.paused = !W.paused; $('#wpause').textContent = W.paused ? 'Resume' : 'Pause'; };
$('#wreplay').onclick = () => { W.cursor = 0; W.paused = false; };
$('#wave').onclick = ev => {
  const cv = $('#wave'), w = wavesFor(); if (!w) return; const r = cv.getBoundingClientRect(), t = W.x0 + (ev.clientX - r.left) / r.width * wspan(), y = (ev.clientY - r.top) / r.height * cv.height;
  const wf = y < 110 ? w.t : w.r; const f = wf?.frames.find(f => t >= f.t0 && t < f.t1); W.byte = f ? { t: wf, i: f.idx } : null;
  if (f) $('#wInfo').textContent = `byte ${f.idx} = 0x${hex(f.byte)} bits(start,D0..D7,stop)=${f.bits.join('')} · ${f.t0.toFixed(1)}–${f.t1.toFixed(1)} µs`;
};

// ---------------- boot
(async function () {
  drawDiagram(); $('#diagNote').textContent = 'animation is slowed for viewing; real timestamps and RTT are in the inspector';
  renderSafety(); renderIO(); await initLab().catch(err); await loadPorts().catch(() => { }); await refreshState();
  const es = new EventSource('/events'); es.onmessage = m => handle(JSON.parse(m.data));
  setInterval(refreshState, 3000); requestAnimationFrame(frame);
})();
