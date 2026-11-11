// GARDA FPGA Control Center front end. Talks only to the local bridge (same origin).
"use strict";
let TOKEN = document.querySelector('meta[name="garda-token"]').content;
const $ = (s) => document.querySelector(s);
const $$ = (s) => [...document.querySelectorAll(s)];
const STEP_META = {
  connect_uart: ["Connect UART", "Open the serial port at 115200 baud, 8N1.", "Membuka port serial 115200 baud, 8N1."],
  identify: ["Identify the FPGA", "Ask the chip who it is. Only a CRC-valid GARDA signature counts as a live FPGA.", "Menanyakan identitas chip. Hanya tanda tangan GARDA dengan CRC valid yang dihitung."],
  safe_reset: ["Safe reset", "Return the hardware to its power-on safe state: motors off, nothing configured.", "Mengembalikan hardware ke kondisi aman: motor mati, belum dikonfigurasi."],
  crc_test: ["Corrupted-message test", "Send a message with a wrong checksum. GARDA must ignore it and lock out until reset.", "Mengirim pesan dengan checksum salah. GARDA harus menolak dan mengunci sampai reset."],
  neural: ["Sensor data and neural inference", "Send 24 sensor values; the on-chip neural network (24-64-64-4) must reproduce the reference outputs bit for bit.", "Mengirim 24 nilai sensor; neural network di chip harus menghasilkan output referensi persis sama."],
  planner: ["Plan a motion", "Upload a 128x128 cost map, lock the speed limits and let 4 hardware tiles score 512 trajectories.", "Mengunggah peta 128x128, mengunci batas kecepatan, lalu 4 tile hardware menilai 512 lintasan."],
  safety_gate: ["Hardware safety intervention", "While motion is permitted, an E-stop fires. The capture register shows when motor permission was removed.", "Saat gerak diizinkan, E-stop dipicu. Register capture mencatat kapan izin motor dicabut."],
  estop: ["E-stop behaviour", "A host E-stop latches: motors stay at zero until a deliberate reset.", "E-stop dari host terkunci: motor tetap nol sampai reset yang disengaja."],
  watchdog: ["Link-loss watchdog", "If the computer goes silent, GARDA stops the motors on its own.", "Jika komputer berhenti mengirim, GARDA menghentikan motor sendiri."],
  summary: ["Verification summary", "All results above were checked automatically.", "Semua hasil di atas diperiksa otomatis."],
};
const SIM_STEPS = ["identify", "neural", "planner", "safety_gate", "crc_test", "safe_reset", "estop", "watchdog", "summary"];
const FAULT_TEXT = {0: "All checks passed. Command passed to motors", 1: "Reset active", 2: "Emergency stop", 3: "Protective stop",
  4: "Not ready / command contract violated", 5: "No valid fresh map", 6: "Configuration not locked", 7: "Rollout arithmetic fault",
  8: "Deadline or command lease expired", 9: "Result not ready yet", 10: "Speed limit exceeded", 11: "Acceleration limit exceeded"};
// DE10-Lite JP1 GPIO -> FPGA pin (manual table 3-7)
const GPIO_PIN = ["V10","W10","V9","W9","V8","W8","V7","W7","W6","V5","W5","AA15","AA14","W13","W12","AB13","AB12","Y11","AB11","W11",
  "AB10","AA10","AA9","Y8","AA8","Y7","AA7","Y6","AA6","Y5","AA5","Y4","AB3","Y3","AB2","AA2"];

let monitorBusy = false;
let S = null, source = "live", replay = null, judgeOpen = false, tick = 0;
let termFilter = "all", termPaused = false, expanded = new Set(), lastFrameSeq = 0, scanned = null, pendingSeq = null;

async function api(path, body, retried = false) {
  const opt = body === undefined ? {} : {method: "POST", headers: {"Content-Type": "application/json", "X-GARDA-Token": TOKEN}, body: JSON.stringify(body)};
  const r = await fetch(path, opt);
  if (r.status === 403 && body !== undefined && !retried) {
    // The bridge was restarted and issued a new per-launch token: re-read it from our own origin.
    const html = await (await fetch("/", {cache: "no-store"})).text();
    const m = html.match(/name="garda-token" content="([^"]+)"/);
    if (m) { TOKEN = m[1]; return api(path, body, true); }
  }
  return r.json();
}
function toast(text, cls = "") {
  const t = document.createElement("div");
  t.className = "toast " + cls; t.textContent = text;
  $("#toasts").append(t);
  setTimeout(() => t.remove(), cls === "err" ? 9000 : 5000);
}
const hex2 = (n) => (n ?? 0).toString(16).toUpperCase().padStart(2, "0");
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;"}[c]));

// ------------------------------------------------------------ safety + flow
function safetyFromFrames(frames) {
  let st = null, cmd = null, ext = null, nn = null;
  for (let i = frames.length - 1; i >= 0; i--) {
    const f = frames[i];
    if (f.kind && f.kind !== "frame") continue;
    const d = f.decoded;
    if (!st && f.motor_enable !== undefined && f.fault !== undefined) st = {motor_enable: !!f.motor_enable, fault_code: f.fault, host_estop: !!f.host_estop};
    if (!d) continue;
    if (!st && d.fault_code !== undefined && d.motor_enable !== undefined) st = d;
    if (!cmd && d.v !== undefined) cmd = d;
    if (!cmd && d.v_before !== undefined && !d.measuring) cmd = {v: d.v_before, omega: d.omega_before};
    if (!ext && d.host_estop !== undefined) ext = d;
    if (!nn && d.done !== undefined && d.value !== undefined) nn = d;
    if (st && cmd && ext && nn) break;
  }
  return {st, cmd, ext, nn};
}
function renderSafety(frames, label) {
  const {st, cmd, ext, nn} = safetyFromFrames(frames);
  const box = $("#safety");
  renderFlow(st, nn, frames);
  if (!st) {
    box.className = "safety s-unknown"; $("#safetyWord").textContent = "NO DATA YET"; $("#safetyIcon").textContent = "?";
    $("#safetyReason").textContent = source === "live" ? "Connect the UART. The state shown here is read from the FPGA, never assumed." : "Waiting for the replay to start.";
    ["#sfFault", "#sfV", "#sfW"].forEach((s) => ($(s).textContent = "--")); $("#sfSource").textContent = label;
    $("#vgaPreview").src = "assets/vga_stopped.png"; renderMirror(null, null); return;
  }
  const estop = st.fault_code === 2 || (ext && (ext.host_estop || ext.key_estop));
  let cls = "s-stop", word = "MOTOR STOPPED", icon = "■", img = "vga_stopped";
  if (st.motor_enable) { cls = "s-permit"; word = "MOTION PERMITTED"; icon = "▶"; img = "vga_permitted"; }
  else if (estop) { cls = "s-estop"; word = "E-STOP ACTIVE"; icon = "!"; img = "vga_estop"; }
  else if (st.fault_code === 3) { word = "PROTECTIVE STOP"; icon = "‖"; }
  box.className = "safety " + cls; $("#safetyWord").textContent = word; $("#safetyIcon").textContent = icon;
  $("#safetyReason").textContent = FAULT_TEXT[st.fault_code] || `Fault ${st.fault_code}`;
  $("#sfFault").textContent = hex2(st.fault_code);
  $("#sfV").textContent = cmd ? cmd.v : "--"; $("#sfW").textContent = cmd ? (cmd.omega > 0 ? "+" : "") + cmd.omega : "--";
  $("#sfSource").textContent = label;
  const want = `assets/${img}.png`;
  if (!$("#vgaPreview").src.endsWith(want)) $("#vgaPreview").src = want;
  renderMirror(st, ext);
}
function renderFlow(st, nn, frames) {
  const recent = frames.slice(-40);
  const has = (name) => recent.some((f) => f.op_name === name && f.result === "OK");
  const set = (id, cls) => ($(id).className = "flow-node " + (cls || ""));
  set("#fnSensor", has("NN_LOAD") || has("MAP_WRITE") ? "on" : "");
  set("#fnNeural", nn ? (nn.fault ? "stop" : nn.busy ? "busy" : nn.done ? "on" : "") : "");
  set("#fnPlanner", st ? (st.busy ? "busy" : st.done || st.motor_enable ? "on" : "") : "");
  const gateStop = st && !st.motor_enable && st.fault_code !== undefined;
  set("#fnGate", st ? (st.motor_enable ? "on" : "stop") : "");
  set("#fnMotor", st && st.motor_enable ? "on" : st ? "stop" : "");
  $("#fnMotorSub").textContent = st && st.motor_enable ? "PERMITTED" : st ? `held at zero · fault ${st.fault_code}` : "no data";
  const links = $$(".flow-link");
  links.forEach((l, i) => (l.className = "flow-link " + (i === 3 && gateStop ? "cut" : st && (i < 3 || st.motor_enable) ? "live" : "")));
}

// ------------------------------------------------------------ board mirror + JP1
const SEGS = {0: "abcdef", 1: "bc", 2: "abdeg", 3: "abcdg", 4: "bcfg", 5: "acdfg", 6: "acdefg", 7: "abc", 8: "abcdefg", 9: "abcdfg", 10: "abcefg", 11: "cdefg", 12: "adef", 13: "bcdeg", 14: "adefg", 15: "aefg"};
const SEGPATH = {a: "M8 4h20l-3 4H11z", b: "M30 6v20l-4-3V9z", c: "M30 32v20l-4-3V35z", d: "M8 54h20l-3-4H11z", e: "M6 32v20l4-3V35z", f: "M6 6v20l4-3V9z", g: "M9 29l3-3h12l3 3-3 3H12z"};
const digitSvg = (v) => `<svg class="digit" viewBox="0 0 36 58">${Object.entries(SEGPATH).map(([k, d]) => `<path d="${d}" class="${(SEGS[v] || "").includes(k) ? "seg-on" : "seg-off"}"/>`).join("")}</svg>`;
function renderSwitches(frames) {
  const f = [...frames].reverse().find((x) => x.op_name === "BOARD_IO" && x.decoded);
  if (!f) return;
  const d = f.decoded;
  const label = {0: "SW0 HEX page", 1: "SW1 LED test", 2: "SW2 NOT READY (safety)", 3: "SW3 PROTECTIVE STOP (safety)"};
  $("#switches").innerHTML = d.sw.map((v, i) => i).reverse().map((i) => `<i class="sw ${d.sw[i] ? "up" : ""} ${i === 2 || i === 3 ? "safety" : ""}" title="${label[i] || "SW" + i + " (no function)"}: ${d.sw[i] ? "UP" : "DOWN"}"></i>`).join("")
    + `<span class="key ${d.key1_released ? "" : "down"}">KEY1</span><span class="key ${d.key0_released ? "" : "down"}">KEY0</span>`;
}
function renderMirror(st, ext) {
  const f = st ? st.fault_code : 0, lf = ext ? ext.last_fault : 0;
  const cnt = (S && S.uart.counters.rx_frames) || 0;
  $("#hex").innerHTML = [f >> 4, f & 15, lf >> 4, lf & 15, (cnt >> 4) & 15, cnt & 15].map(digitSvg).join("");
  const recent = S && S.uart.last_rx && S.server_time - S.uart.last_rx < 0.6;
  const leds = [st && st.motor_enable, !!st, st && st.busy, st && st.done, f & 1, f & 2, f & 4, f & 8, ext && (ext.host_estop || ext.watchdog_trip), recent];
  $("#leds").innerHTML = leds.reverse().map((on, i) => `<i class="led ${on ? "on" : ""}" title="LEDR${9 - i}"></i>`).join("");
}
function pinMeta(n) {
  if (n === 11) return {cls: "v5", info: "Pin 11: 5 V supply. Do NOT connect the adapter's red wire."};
  if (n === 12) return {cls: "gnd", info: "Pin 12: GND for port A. Connect the USB-TTL adapter's black wire."};
  if (n === 30) return {cls: "gnd", info: "Pin 30: GND for port B. Connect Jetson Nano J41 pin 6 (GND)."};
  if (n === 29) return {cls: "v33", info: "Pin 29: 3.3 V supply."};
  const g = n <= 10 ? n - 1 : n <= 28 ? n - 3 : n - 5;
  const base = `Pin ${n}: GPIO_${g} (FPGA PIN_${GPIO_PIN[g]})`;
  if (n === 1) return {cls: "rx", tag: "A", info: `${base}. Port A RX (laptop). Connect the adapter TX, green wire.`};
  if (n === 2) return {cls: "tx", tag: "A", info: `${base}. Port A TX (laptop). Connect the adapter RX, white wire.`};
  if (n === 3) return {cls: "rx", tag: "B", info: `${base}. Port B RX (Jetson). Connect Jetson Nano J41 pin 8 (UART TXD).`};
  if (n === 4) return {cls: "tx", tag: "B", info: `${base}. Port B TX (Jetson). Connect Jetson Nano J41 pin 10 (UART RXD).`};
  return {cls: "", info: `${base}: unused, input with weak pull-up.`};
}
function drawJp1() {
  $("#jp1").innerHTML = Array.from({length: 40}, (_, i) => {
    const n = i + 1, m = pinMeta(n);
    return `<div class="pin ${m.cls}" data-pin="${n}" title="${esc(m.info)}">${[1, 2, 3, 4, 11, 12, 29, 30].includes(n) ? n : ""}${m.tag ? `<sup>${m.tag}</sup>` : ""}</div>`;
  }).join("");
  $$("#jp1 .pin").forEach((p) => p.addEventListener("mouseenter", () => ($("#pinInfo").textContent = pinMeta(+p.dataset.pin).info)));
}
function flashPins(kind) { $$(`#jp1 .pin.${kind}`).forEach((p) => { p.classList.remove("act"); void p.offsetWidth; p.classList.add("act"); }); }

// ------------------------------------------------------------ terminal
const isPoll = (f) => ["STATUS", "EXT_STATUS"].includes(f.op_name) && !f.step;
function termRow(f, i) {
  const key = f.seq ?? `r${i}`;
  if (f.kind && f.kind !== "frame") return `<div class="term-row ev"><span>${f.seq ?? ""}</span><span>${tstr(f)}</span><span style="grid-column:3/-1">${esc(f.text)}</span></div>`;
  const ok = f.result === "OK";
  const dec = f.decoded ? Object.entries(f.decoded).filter(([k]) => k !== "fault_text").slice(0, 7).map(([k, v]) => `${k}=${typeof v === "boolean" ? (v ? 1 : 0) : v}`).join("  ") : (f.error || "");
  const count = f.count > 1 ? ` ×${f.count}` : "";
  const json = expanded.has(String(key)) ? `<div class="json">${esc(JSON.stringify(f.decoded ?? f, null, 1))}</div>` : "";
  return `<div class="term-row" data-k="${esc(key)}"><span>${f.seq ?? "·"}</span><span>${tstr(f)}</span><span>${esc(f.op_name)}${count}</span>
    <span class="tx">${esc(f.tx)}</span><span class="rx">${esc(f.rx || "-")}</span>
    <span class="${ok ? "ok-chip" : "bad-chip"}">${ok ? "CRC OK" : esc(f.result)}</span><span class="dec">${esc(dec)}${f.rtt_ms ? `  · ${f.rtt_ms} ms` : ""}</span>${json}</div>`;
}
function tstr(f) {
  if (f.t) return new Date(f.t * 1000).toLocaleTimeString([], {hour12: false});
  if (f.t_ns != null) return (f.t_ns / 1e6).toFixed(2) + " ms";
  return "";
}
let lastTermKey = "";
function renderTerminal(frames) {
  const last = frames.at(-1);
  if (last && last.seq && last.seq > lastFrameSeq) {
    if (lastFrameSeq) { flashPins("rx"); setTimeout(() => flashPins("tx"), 120); }
    lastFrameSeq = last.seq;
  }
  if (termPaused) return;
  let list = frames;
  if (termFilter === "nopoll") list = frames.filter((f) => !isPoll(f));
  if (termFilter === "err") list = frames.filter((f) => f.result && f.result !== "OK");
  const key = termFilter + list.length + ":" + (list.at(-1)?.seq ?? list.at(-1)?.t_ns ?? "") + [...expanded].join();
  if (key === lastTermKey) return;
  lastTermKey = key;
  const t = $("#terminal");
  const stick = t.scrollTop + t.clientHeight >= t.scrollHeight - 30;
  t.innerHTML = list.slice(-150).map(termRow).join("") || `<div class="term-row ev"><span style="grid-column:1/-1">No frames yet.</span></div>`;
  if (stick) t.scrollTop = t.scrollHeight;
  $("#logCount").textContent = `${frames.filter((f) => !f.kind || f.kind === "frame").length} frames`;
}
$("#terminal").addEventListener("click", (e) => {
  const row = e.target.closest(".term-row[data-k]"); if (!row) return;
  const k = row.dataset.k; expanded.has(k) ? expanded.delete(k) : expanded.add(k); lastTermKey = "";
  renderTerminal(replay ? replay.shown : S ? S.log : []);
});
$$("#termFilter button").forEach((b) => (b.onclick = () => { $$("#termFilter button").forEach((x) => x.classList.toggle("on", x === b)); termFilter = b.dataset.f; lastTermKey = ""; renderTerminal(replay ? replay.shown : S ? S.log : []); }));
$("#termPause").onclick = () => { termPaused = !termPaused; $("#termPause").textContent = termPaused ? "▶ Resume" : "❚❚ Pause"; lastTermKey = ""; };

// ------------------------------------------------------------ steps / judge
function renderSteps(seq) {
  const ol = $("#steps");
  if (!seq || !seq.steps || !seq.steps.length) { ol.innerHTML = `<li class="empty">Press a button above to run a sequence.</li>`; $("#seqResult").textContent = ""; $("#progress").hidden = true; return; }
  ol.innerHTML = seq.steps.map((s) => `<li class="${s.status}"><b>${esc(s.title)}</b><span class="ex">${esc(s.explain)}</span><span class="dt">${esc(s.detail || (s.status === "running" ? "running…" : ""))}</span></li>`).join("");
  const r = $("#seqResult");
  r.textContent = seq.running ? `${seq.name} · running` : seq.result ? `${seq.name} · ${seq.result}` : "";
  r.className = "pill " + (seq.running ? "warn" : seq.result === "PASS" ? "good" : seq.result ? "bad" : "");
  const pr = $("#progress");
  if (seq.progress && seq.running) { pr.hidden = false; pr.firstElementChild.style.width = (100 * seq.progress.done) / seq.progress.total + "%"; pr.lastElementChild.textContent = `${seq.progress.label}: ${seq.progress.done} / ${seq.progress.total}`; }
  else pr.hidden = true;
  $("#btnAbort").hidden = !seq.running || !!replay;   // replays cannot be aborted on hardware
  if (judgeOpen) renderJudge(seq);
  if (pendingSeq && !seq.running && seq.result && seq.started && seq.started > pendingSeq) {
    toast(`${seq.name}: ${seq.result}${seq.trace_file ? " · trace saved " + seq.trace_file : ""}`, seq.result === "PASS" ? "ok" : "err");
    pendingSeq = null;
  }
}
function renderJudge(seq) {
  const steps = seq.steps || [];
  let cur = steps.findIndex((s) => s.status === "running");
  if (cur < 0) cur = !seq.running ? steps.length - 1 : Math.max(0, steps.findIndex((s) => s.status === "pending") - 1);
  const s = steps[Math.max(cur, 0)];
  if (!s) return;
  $("#judgeCount").textContent = `STEP ${cur + 1} / ${steps.length}`;
  $("#judgeTitle").textContent = s.title; $("#judgeExplain").textContent = s.explain; $("#judgeExplainId").textContent = s.explain_id || "";
  const st = $("#judgeStatus");
  st.className = "judge-status " + s.status;
  st.textContent = {pass: "✓ VERIFIED", fail: "✕ FAILED", running: "● IN PROGRESS", pending: "…", skipped: "SKIPPED"}[s.status] || s.status;
  if (!seq.running && seq.result) st.textContent += `  ·  SEQUENCE ${seq.result}`;
  $("#judgeDetail").textContent = s.detail || "";
  $("#judgeDots").innerHTML = steps.map((x) => `<i class="${x.status}"></i>`).join("");
  $("#judgeMode").textContent = modeLabel(); $("#judgeMode").className = "mode " + modeClass();
}

// ------------------------------------------------------------ cards
function lightStates(sel, active, badSet, busySet) {
  $$(sel + " li").forEach((li) => {
    const on = li.dataset.s === active;
    li.className = on ? "on" + (badSet.includes(active) ? " bad" : "") + (busySet.includes(active) ? " busy" : "") : "";
  });
}
function pill(id, cls, text) { const p = $(id); p.className = "tpill " + cls; p.lastChild.textContent = text; }
function renderCards() {
  lightStates("#fpgaStates", S.fpga.state, ["PROGRAMMING FAILED", "BOARD DISCONNECTED"], ["PROGRAMMING"]);
  $("#fpgaDetail").textContent = S.fpga.detail || "";
  lightStates("#uartStates", S.uart.state, ["TIMEOUT / CRC ERROR", "PORT NOT FOUND"], ["CONNECTING"]);
  const fs = S.fpga.state;
  pill("#pillJtag", fs.includes("SUCCESSFUL") || fs === "READY TO PROGRAM" ? "ok" : fs.includes("FAILED") || fs === "BOARD DISCONNECTED" ? "bad" : "warn", " " + fs);
  const us = S.uart.state;
  pill("#pillUart", us === "FPGA RESPONDING" ? "ok" : us.includes("TIMEOUT") || us === "PORT NOT FOUND" ? "bad" : "warn", " " + us);
  const e = S.engineering;
  pill("#pillBuild", e.release ? "ok" : e.timing_met === false ? "bad" : "warn", e.release ? " RELEASE BUILD" : e.programming_file ? " NOT SIGN-OFF" : " NO BUILD");
  const c = S.uart.counters;
  $("#cTx").textContent = c.tx_frames; $("#cRx").textContent = c.rx_frames; $("#cTo").textContent = c.timeouts; $("#cCrc").textContent = c.crc_errors;
  const last = [...S.log].reverse().find((f) => f.rtt_ms);
  $("#rtt").textContent = last ? `RTT ${last.rtt_ms} ms` : "";
  const sel = $("#portSelect"), cur = sel.value;
  const opts = S.uart.ports.map((p) => `<option value="${esc(p.device)}">${esc(p.device)} · ${esc(p.description)}</option>`).join("");
  if (sel.dataset.k !== opts) { sel.innerHTML = opts || `<option value="">no serial port found</option>`; sel.dataset.k = opts; if (cur) sel.value = cur; }
  $("#btnConnect").textContent = S.uart.connected ? "Disconnect" : "Connect";
  const id = S.uart.ident;
  const corners = e.timing_corners ? Object.entries(e.timing_corners).map(([k, v]) => `${k.replace("1200mV ", "")}: ${v.setup >= 0 ? "+" : ""}${v.setup} ns`).join(" · ") : "-";
  const rows = [["FPGA device", e.device], ["Programming file", e.programming_file || "none built"], ["Build ID (file)", e.build_id || "-"],
    ["Build ID (FPGA)", id ? id.build_id + (id.build_id === e.build_id ? "  ✓ matches file" : "  ≠ file") : "not read yet"],
    ["Build time (UTC)", e.build_time_utc || "-"], ["Quartus", e.quartus_version || "-"],
    ["Core clock", id ? `${id.clock_hz / 1e6} MHz (read from FPGA)` : e.clock_hz ? `${e.clock_hz / 1e6} MHz` : "-"], ["Fmax worst corner", e.fmax_mhz ? `${e.fmax_mhz} MHz` : "-"],
    ["Logic elements", e.logic_elements || "-"], ["Memory bits", e.memory_bits || "-"], ["9-bit multipliers", e.multipliers || "-"],
    ["Setup slack", corners], ["UART", id ? `${id.baud} baud (divisor ${id.clks_per_bit}), 8N1, CRC-8 0x07` : `${S.uart.baud} baud, 8N1, CRC-8 0x07`],
    ["Last packet", last ? `${last.op_name}: ${last.result}` : "-"], ["SOF SHA-256", e.sof_sha256 ? e.sof_sha256.slice(0, 16) + "…" : "-"]];
  $("#eng").innerHTML = rows.map(([k, v]) => `<dt>${k}</dt><dd>${esc(v)}</dd>`).join("");
  const tp = $("#timingPill");
  tp.textContent = e.timing_met == null ? "no build report" : e.timing_met ? "TIMING MET" : `TIMING NOT MET${e.worst_slack_ns != null ? ` (${e.worst_slack_ns} ns)` : ""}`;
  tp.className = "pill " + (e.timing_met ? "good" : e.timing_met == null ? "" : "bad");
  const running = S.sequence.running;
  $("#btnProgramOnly").disabled = $("#btnProgram").disabled = running || !e.programming_file;
  ["#btnDemo", "#btnJudge", "#btnReset"].forEach((b) => ($(b).disabled = running && source === "live"));
  $$(".quick button").forEach((b) => (b.disabled = !S.uart.connected || running));
  const ts = $("#traceSelect");
  const topts = S.traces.map((t) => `<option>${t}</option>`).join("");
  if (ts.dataset.k !== topts) { ts.innerHTML = topts || "<option value=''>no recorded hardware trace yet</option>"; ts.dataset.k = topts; }
}
function modeLabel() { return source === "sim" ? "SOFTWARE SIMULATION" : source === "recorded" ? "RECORDED HARDWARE TRACE" : S && S.uart.state === "FPGA RESPONDING" ? "LIVE HARDWARE" : "LIVE · NOT CONNECTED"; }
function modeClass() { return source === "sim" ? "mode-sim" : source === "recorded" ? "mode-recorded" : S && S.uart.state === "FPGA RESPONDING" ? "mode-live" : "mode-offline"; }

// ------------------------------------------------------------ replay (sim / recorded)
function startReplay(trace, kind) {
  stopReplay();
  const isSim = kind === "sim";
  const steps = (isSim ? SIM_STEPS.map((id) => ({id})) : trace.steps).map((s) => ({id: s.id, title: STEP_META[s.id]?.[0] || s.title, explain: STEP_META[s.id]?.[1] || s.explain,
    explain_id: STEP_META[s.id]?.[2] || s.explain_id, status: "pending", detail: "", final: s.status, finalDetail: s.detail}));
  replay = {frames: trace.frames.filter((f) => isSim || f.kind === "frame" || f.kind === "connect"), shown: [], steps, idx: 0, isSim, trace,
    seq: {name: isSim ? "SOFTWARE SIMULATION REPLAY" : "RECORDED HARDWARE TRACE", running: true, steps}};
  const b = $("#replayBanner");
  b.hidden = false; b.className = "replay-banner " + (isSim ? "sim" : "rec");
  b.textContent = isSim ? `SOFTWARE SIMULATION · ${trace.source} · ${trace.simulator} · ${trace.checks_total} checks ${trace.result}. Not an FPGA measurement.`
                        : `RECORDED HARDWARE TRACE · captured ${trace.recorded_utc} on ${trace.port} · FPGA build ${trace.fpga_build_id} · replay of a past run, not live.`;
  stepReplay();
}
function stepReplay() {
  const r = replay; if (!r) return;
  if (r.idx >= r.frames.length) {
    r.steps.forEach((s) => { s.status = r.isSim ? "pass" : s.final; s.detail = r.isSim ? s.detail : s.finalDetail; });
    if (r.isSim) r.steps.find((s) => s.id === "summary").detail = `${r.trace.checks.filter((c) => c.ok).length}/${r.trace.checks_total} automated checks passed in the RTL simulation`;
    r.seq.running = false; r.seq.result = r.trace.result;
    renderSteps(r.seq); return;
  }
  const f = r.frames[r.idx++];
  r.shown.push(f);
  if (r.isSim) {
    const i = r.steps.findIndex((s) => s.id === f.step);
    r.steps.forEach((s, k) => { if (k < i && s.status !== "pass") s.status = "pass"; });
    if (i >= 0) { r.steps[i].status = "running"; r.steps[i].detail = `${f.step_name}${f.count > 1 ? " ×" + f.count : ""} → ${f.result}${f.decoded && f.decoded.fault_code !== undefined ? ", fault " + f.decoded.fault_code : ""}`; }
  }
  flashPins("rx"); setTimeout(() => flashPins("tx"), 120);
  renderTerminal(r.shown); renderSafety(r.shown, r.isSim ? "RTL simulation" : "recorded trace"); renderSteps(r.seq);
  r.timer = setTimeout(stepReplay, f.count > 1 ? 900 : judgeOpen ? 650 : 280);
}
function stopReplay() { if (replay && replay.timer) clearTimeout(replay.timer); replay = null; $("#replayBanner").hidden = true; lastTermKey = ""; }
function setSource(src) {
  $$(".seg button").forEach((x) => x.classList.toggle("on", x.dataset.src === src));
  source = src; $("#traceSelect").hidden = source !== "recorded"; stopReplay();
}

// ------------------------------------------------------------ polling
async function poll() {
  try { S = await api("/api/state"); } catch { pill("#pillJtag", "bad", " BRIDGE OFFLINE"); return; }
  renderCards();
  $("#modeBadge").textContent = modeLabel(); $("#modeBadge").className = "mode " + modeClass();
  if (source === "live") {
    renderTerminal(S.log); renderSafety(S.log, S.uart.state === "FPGA RESPONDING" ? "live FPGA" : "no live data");
    renderSwitches(S.log);
    renderSteps(S.sequence);
    if (++tick % 2 === 0 && !monitorBusy && $("#monitor").checked && S.uart.state === "FPGA RESPONDING" && !S.sequence.running) {
      const v2 = (S.uart.ident || {}).interface_version >= 2;
      monitorBusy = true;
      api("/api/command", {name: (v2 ? ["status", "board_io", "status", "ext_status", "status", "board_io"] : ["status", "status", "ext_status"])[tick % (v2 ? 6 : 3)]}).finally(() => (monitorBusy = false));
    }
  }
}

// ------------------------------------------------------------ actions
const port = () => $("#portManual").value.trim() || $("#portSelect").value;
async function runSeq(sequence, extra = {}) {
  setSource("live");
  pendingSeq = Date.now() / 1000 - 2;
  const r = await api("/api/run", {sequence, port: port(), baud: +$("#baudSelect").value, ...extra});
  toast(r.ok ? `${sequence.replace(/_/g, " ")} started` : r.error || "could not start", r.ok ? "" : "err");
}
async function openProgramDialog(sequence) {
  const d = $("#confirm"); d.dataset.seq = sequence;
  $("#cfTitle").textContent = sequence === "program" ? "Program the FPGA?" : "Program the FPGA and run the UART test?";
  $("#cfTarget").textContent = "Scanning the JTAG chain…"; $("#cfTarget").className = "cf-target";
  $("#cfGo").disabled = true; scanned = null;
  $("#cfFile").textContent = S ? S.engineering.programming_file : "-";
  $("#cfWarn").textContent = S && !S.engineering.release ? "Warning: this file is not a timing sign-off release build." : "";
  d.showModal();
  const r = await api("/api/scan-jtag", {});
  if (!r.ok) { $("#cfTarget").textContent = "Bridge error: " + (r.error || "no answer"); $("#cfTarget").className = "cf-target bad"; return; }
  const j = r.jtag || {};
  const cables = j.cables || [];
  const good = cables.length === 1 && cables[0].devices.length === 1 && cables[0].devices[0].idcode === "031050DD";
  $("#cfTarget").textContent = good ? `✓ ${cables[0].name}\n  ${cables[0].devices[0].name}  IDCODE 0x031050DD (DE10-Lite MAX 10)` : (j.raw || j.state || "no JTAG response") + "\n\nProgramming is refused unless exactly one 10M50DA is found.";
  $("#cfTarget").className = "cf-target " + (good ? "ok" : "bad");
  if (good) { scanned = "031050DD"; $("#cfGo").disabled = false; $("#cfGo").focus(); }
}
$("#confirm").addEventListener("close", () => {
  if ($("#confirm").returnValue === "go" && scanned) runSeq($("#confirm").dataset.seq, {confirm_idcode: scanned});
});
$("#btnProgramOnly").onclick = () => openProgramDialog("program");
$("#btnProgram").onclick = () => openProgramDialog("program_and_test");
$("#btnDemo").onclick = () => runSeq("demo");
$("#btnJudge").onclick = () => {
  judgeOpen = true; $("#judge").hidden = false;
  if (source === "live") runSeq("judge");
  else if (replay) startReplay(replay.trace, replay.isSim ? "sim" : "rec");
};
$("#judgeClose").onclick = () => { judgeOpen = false; $("#judge").hidden = true; };
document.addEventListener("keydown", (e) => { if (e.key === "Escape" && judgeOpen) $("#judgeClose").click(); });
$("#btnEstop").onclick = async () => { const r = await api("/api/command", {name: "estop"}); toast(r.ok ? "Host E-stop acknowledged by the FPGA" : "E-stop NOT acknowledged (" + r.error + "). Press KEY1 on the board.", r.ok ? "ok" : "err"); };
$("#btnReset").onclick = async () => { const r = await api("/api/command", {name: "safe_reset"}); toast(r.ok ? "Safe reset acknowledged" : "Safe reset frame sent; " + (r.error || ""), r.ok ? "ok" : ""); };
$("#btnScan").onclick = async () => { await api("/api/scan-jtag", {}); toast("JTAG chain scanned"); };
$("#btnAbort").onclick = () => api("/api/abort", {});
$$(".quick button").forEach((b) => (b.onclick = async () => { const r = await api("/api/command", {name: b.dataset.cmd}); if (!r.ok) toast(`${b.dataset.cmd}: ${r.error}`, "err"); }));
$("#btnConnect").onclick = async () => {
  if (S && S.uart.connected) { await api("/api/disconnect", {}); toast("UART disconnected"); return; }
  if (!port()) return toast("Choose or type a serial port", "err");
  const r = await api("/api/connect", {port: port(), baud: +$("#baudSelect").value});
  toast(r.ok ? (r.ident ? `FPGA responding · build ${r.ident.build_id}` : r.warning) : r.error, r.ok && r.ident ? "ok" : "err");
};
$$(".seg button").forEach((b) => (b.onclick = async () => {
  setSource(b.dataset.src);
  if (source === "sim") {
    const t = await api("/api/sim-trace");
    if (t.error) return toast(t.error, "err");
    startReplay(t, "sim");
  } else if (source === "recorded") {
    const name = $("#traceSelect").value;
    if (!name) return toast("No recorded hardware trace exists yet. Run a live demo first; nothing is invented.", "err");
    startReplay(await api("/api/hw-trace?name=" + encodeURIComponent(name)), "rec");
  }
  poll();
}));
$("#traceSelect").onchange = async () => { if (source === "recorded" && $("#traceSelect").value) startReplay(await api("/api/hw-trace?name=" + encodeURIComponent($("#traceSelect").value)), "rec"); };
drawJp1(); renderMirror(null, null); poll(); setInterval(poll, 600);
const want = new URLSearchParams(location.search).get("source");
if (want) document.querySelector(`.seg button[data-src="${want}"]`)?.click();
