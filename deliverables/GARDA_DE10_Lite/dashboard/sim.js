// GARDA Physical AI simulator view. All values come from /api/physai (FPGA or bit-exact model).
"use strict";
let TOKEN = document.querySelector('meta[name="garda-token"]').content;
const $ = (s) => document.querySelector(s);
const $$ = (s) => [...document.querySelectorAll(s)];
const C = {lime: "#B7FF35", blue: "#315CFF", soft: "#93ACFF", cyan: "#4FE3FF", violet: "#B48CFF", red: "#FF5364", amber: "#FFBD59",
  white: "#F7F9FF", muted: "#A8B6D4", grid: "#16204a", border: "#29365B", bg: "#050817"};
let S = null, lastStep = -1, backend = "model", inputs = "golden";
const disp = {x: 1, y: 2.5, th: 0, g: [0, 0, 0], r: [0, 0, 0]};   // eased display state
const wheelAng = [0, 0, 0, 0];
let wave = 0;                                                      // 0..1 progress of the inference wave

async function api(path, body, retried = false) {
  const opt = body === undefined ? {cache: "no-store"} : {method: "POST", headers: {"Content-Type": "application/json", "X-GARDA-Token": TOKEN}, body: JSON.stringify(body)};
  const r = await fetch(path, opt);
  if (r.status === 403 && body !== undefined && !retried) {
    const m = (await (await fetch("/sim.html", {cache: "no-store"})).text()).match(/name="garda-token" content="([^"]+)"/);
    if (m) { TOKEN = m[1]; return api(path, body, true); }
  }
  return r.json();
}
function msg(t, cls = "") { const m = $("#msg"); m.textContent = t; m.className = "msg " + cls; }

// ------------------------------------------------------------ polling
async function poll() {
  try { S = await api("/api/physai"); } catch { msg("Bridge offline: start the GARDA Control Center", "err"); return; }
  const live = S.backend === "fpga" && S.running;
  if (S.running) {                                   // mirror the real run state in the buttons
    backend = S.backend; inputs = S.inputs;
    $$("#segBackend button").forEach((b) => b.classList.toggle("on", b.dataset.v === backend));
    $$("#segInputs button").forEach((b) => b.classList.toggle("on", b.dataset.v === inputs));
  }
  $("#prov").textContent = S.running ? S.provenance : (S.uart && S.uart.state === "FPGA RESPONDING" ? "FPGA READY · STOPPED" : "SOFTWARE SIMULATION");
  $("#prov").className = "prov " + (live ? "live" : "sim");
  $("#nnWhere").textContent = S.backend === "fpga" ? "on the DE10-Lite FPGA" : "bit-exact model";
  $("#sensorSrc").textContent = S.inputs === "lidar" ? "virtual LiDAR (experimental)" : `golden frame ${S.frame}`;
  $("#btnRun").textContent = S.running ? "❚❚ STOP" : "▶ START";
  $("#btnRun").classList.toggle("running", S.running);
  if (S.error) msg(S.error, "err");
  if (S.step !== lastStep && S.running) { lastStep = S.step; wave = 0.001; }
  renderGate(); renderStats(); drawSensors(); drawSpark();
}
setInterval(poll, 100);

// ------------------------------------------------------------ gate / stats
function renderGate() {
  const sh = $("#shield"), ul = $("#reasons");
  const estop = S.reasons.some((r) => r.startsWith("E-STOP"));
  if (!S.running && !S.step) { sh.className = "shield"; $("#shieldTxt").textContent = "IDLE"; ul.innerHTML = "<li>press START</li>"; }
  else if (S.permit) { sh.className = "shield ok"; $("#shieldTxt").textContent = "PASS"; ul.innerHTML = '<li class="good">all checks passed</li><li>clamped to −1.00…+0.99</li>'; }
  else { sh.className = "shield block"; $("#shieldTxt").textContent = "BLOCK"; ul.innerHTML = (S.reasons.length ? S.reasons : ["result not ready"]).map((r) => `<li class="bad">${r}</li>`).join("") + "<li>command forced to 0</li>"; }
  $("#estopOverlay").hidden = !(estop && S.step > 0);
  const flowing = S.running && S.permit;
  $("#flow1").className = "flow" + (S.running ? " live" : "");
  $("#flow2").className = "flow" + (S.running ? " live" : "");
  $("#flow3").className = "flow" + (flowing ? " live" : S.running ? " cut" : "");
}
function renderStats() {
  $("#sHz").textContent = S.running ? `${S.hz.toFixed(1)} /s` : "–";
  $("#sExact").textContent = S.exact_total ? `${S.exact_ok}/${S.exact_total}` : "–";
  $("#sExact").style.color = S.exact_total && S.exact_ok === S.exact_total ? C.lime : S.exact_total ? C.red : "";
  const mhz = S.backend === "fpga" && S.uart && S.uart.ident ? S.uart.ident.clock_hz / 1e6 : 45;
  $("#sLat").textContent = S.cycles ? `${(S.cycles / mhz).toFixed(0)} µs` : "–";
  $("#sStep").textContent = S.step;
}

// ------------------------------------------------------------ small canvases
function drawSensors() {
  const cv = $("#cvSensor"), x = cv.getContext("2d"), w = cv.width, h = cv.height;
  x.clearRect(0, 0, w, h);
  const cx = w / 2, cy = h / 2, r0 = 14, rMax = h / 2 - 6;
  x.strokeStyle = C.grid; x.lineWidth = 1;
  [0.5, 1].forEach((f) => { x.beginPath(); x.arc(cx, cy, r0 + (rMax - r0) * f, 0, Math.PI * 2); x.stroke(); });
  S.sensors.forEach((v, i) => {
    const a = -Math.PI / 2 + (i * 2 * Math.PI) / 24, m = Math.max(-1, Math.min(1, v / 256));
    const len = r0 + (rMax - r0) * (m + 1) / 2;
    x.strokeStyle = m > 0.3 ? C.amber : C.cyan; x.lineWidth = 5; x.lineCap = "round";
    x.globalAlpha = 0.35 + 0.65 * Math.min(1, wave * 3 + 0.2);
    x.beginPath(); x.moveTo(cx + Math.cos(a) * r0, cy + Math.sin(a) * r0); x.lineTo(cx + Math.cos(a) * len, cy + Math.sin(a) * len); x.stroke();
  });
  x.globalAlpha = 1; x.fillStyle = C.soft; x.font = "10px monospace"; x.textAlign = "center"; x.fillText("24", cx, cy + 3);
}
const LAYERS = [12, 10, 10, 4];
function drawNet() {
  const cv = $("#cvNet"), x = cv.getContext("2d"), w = cv.width, h = cv.height;
  x.clearRect(0, 0, w, h);
  const pos = LAYERS.map((n, l) => Array.from({length: n}, (_, i) => [14 + (l * (w - 40)) / (LAYERS.length - 1), 8 + ((i + 0.5) * (h - 16)) / n]));
  for (let l = 0; l < LAYERS.length - 1; l++) {
    const lit = wave > 0 && wave * 4 > l && wave * 4 < l + 1.6;
    x.strokeStyle = lit ? "#93acff88" : "#1c2654"; x.lineWidth = lit ? 1.1 : 0.6;
    pos[l].forEach((a) => pos[l + 1].forEach((b) => { x.beginPath(); x.moveTo(a[0], a[1]); x.lineTo(b[0], b[1]); x.stroke(); }));
  }
  pos.forEach((layer, l) => layer.forEach((p, i) => {
    let col = "#2c3a6e";
    if (l === 3) { const v = (S ? S.raw[i] ?? 0 : 0) / 256; col = i < 3 ? (v >= 0 ? C.lime : C.violet) : "#2c3a6e"; }
    else if (wave > 0 && Math.abs(wave * 4 - l) < 0.8) col = C.soft;
    x.fillStyle = col; x.beginPath(); x.arc(p[0], p[1], l === 3 ? 6 : 3.2, 0, Math.PI * 2); x.fill();
    if (l === 3 && i < 3) { x.fillStyle = C.muted; x.font = "10px monospace"; x.fillText(["Vx", "Vy", "ω"][i], p[0] + 10, p[1] + 3); }
  }));
}
function drawGauge(el, gated, raw, color) {
  const cv = el.querySelector("canvas"), x = cv.getContext("2d"), w = cv.width, h = cv.height;
  x.clearRect(0, 0, w, h);
  const cx = w / 2, cy = h - 18, r = 82, ang = (v) => Math.PI + ((Math.max(-1, Math.min(1, v)) + 1) / 2) * Math.PI;
  x.lineCap = "round"; x.lineWidth = 14; x.strokeStyle = "#1a2350";
  x.beginPath(); x.arc(cx, cy, r, Math.PI, 2 * Math.PI); x.stroke();
  x.strokeStyle = color; x.shadowColor = color; x.shadowBlur = 14;
  x.beginPath(); x.arc(cx, cy, r, ang(0), ang(gated), gated < 0); x.stroke(); x.shadowBlur = 0;
  x.strokeStyle = "#ffffff55"; x.lineWidth = 2;                                   // raw marker
  const ra = ang(raw); x.beginPath(); x.moveTo(cx + Math.cos(ra) * (r - 12), cy + Math.sin(ra) * (r - 12)); x.lineTo(cx + Math.cos(ra) * (r + 12), cy + Math.sin(ra) * (r + 12)); x.stroke();
  const na = ang(gated); x.strokeStyle = C.white; x.lineWidth = 3;               // needle
  x.beginPath(); x.moveTo(cx, cy); x.lineTo(cx + Math.cos(na) * (r - 20), cy + Math.sin(na) * (r - 20)); x.stroke();
  x.fillStyle = C.white; x.beginPath(); x.arc(cx, cy, 5, 0, Math.PI * 2); x.fill();
  x.fillStyle = C.muted; x.font = "10px monospace"; x.textAlign = "center";
  x.fillText("-1.00", cx - r, cy + 14); x.fillText("+0.99", cx + r, cy + 14); x.fillText("0", cx, cy - r - 10);
  el.querySelector("strong").textContent = (gated >= 0 ? "+" : "") + gated.toFixed(2);
  el.querySelector("strong").style.color = S && S.permit ? color : C.red;
  el.querySelector("small").textContent = `raw ${(raw >= 0 ? "+" : "") + raw.toFixed(2)}`;
}
function drawSpark() {
  const cv = $("#spark"), x = cv.getContext("2d"), w = cv.width, h = cv.height, hs = S.history;
  x.clearRect(0, 0, w, h);
  x.strokeStyle = C.grid; x.lineWidth = 1;
  [0.25, 0.5, 0.75].forEach((f) => { x.beginPath(); x.moveTo(0, h * f); x.lineTo(w, h * f); x.stroke(); });
  hs.forEach((e, i) => { if (!e.permit) { x.fillStyle = "#ff536422"; x.fillRect((i / 120) * w, 0, w / 120 + 1, h); } });
  [C.lime, C.cyan, C.violet].forEach((col, k) => {
    ["raw", "gated"].forEach((key) => {
      x.strokeStyle = col; x.lineWidth = key === "gated" ? 2 : 1; x.setLineDash(key === "raw" ? [4, 4] : []); x.globalAlpha = key === "raw" ? 0.5 : 1;
      x.beginPath();
      hs.forEach((e, i) => { const px = (i / 120) * w, py = h / 2 - (e[key][k] / 256) * (h / 2 - 6); i ? x.lineTo(px, py) : x.moveTo(px, py); });
      x.stroke();
    });
  });
  x.setLineDash([]); x.globalAlpha = 1;
}

// ------------------------------------------------------------ arena
function drawArena() {
  const cv = $("#arena"), box = cv.getBoundingClientRect();
  if (cv.width !== Math.round(box.width * devicePixelRatio)) { cv.width = Math.round(box.width * devicePixelRatio); cv.height = Math.round(box.height * devicePixelRatio); }
  const x = cv.getContext("2d"), W = cv.width, H = cv.height;
  x.fillStyle = C.bg; x.fillRect(0, 0, W, H);
  if (!S) return;
  const A = S.arena, sc = Math.min((W - 40) / A.w, (H - 40) / A.h), ox = (W - A.w * sc) / 2, oy = (H - A.h * sc) / 2;
  const P = (px, py) => [ox + px * sc, oy + (A.h - py) * sc];
  // floor grid
  x.strokeStyle = C.grid; x.lineWidth = 1;
  for (let gx = 0; gx <= A.w; gx += 0.5) { const [a, b] = P(gx, 0), [c, d] = P(gx, A.h); x.beginPath(); x.moveTo(a, b); x.lineTo(c, d); x.stroke(); }
  for (let gy = 0; gy <= A.h; gy += 0.5) { const [a, b] = P(0, gy), [c, d] = P(A.w, gy); x.beginPath(); x.moveTo(a, b); x.lineTo(c, d); x.stroke(); }
  x.strokeStyle = C.border; x.lineWidth = 3; x.strokeRect(ox, oy, A.w * sc, A.h * sc);
  // obstacles
  const t = performance.now() / 1000;
  A.obstacles.forEach(([qx, qy, r], i) => {
    const [a, b] = P(qx, qy), g = x.createRadialGradient(a, b, r * sc * 0.2, a, b, r * sc * 1.6);
    g.addColorStop(0, "#ff536455"); g.addColorStop(1, "transparent");
    x.fillStyle = g; x.beginPath(); x.arc(a, b, r * sc * 1.6, 0, Math.PI * 2); x.fill();
    x.fillStyle = "#2a1020"; x.strokeStyle = C.red; x.lineWidth = 2 + Math.sin(t * 2 + i);
    x.beginPath(); x.arc(a, b, r * sc, 0, Math.PI * 2); x.fill(); x.stroke();
  });
  // trail
  const tr = S.trail;
  for (let i = 1; i < tr.length; i++) {
    const [a, b] = P(tr[i - 1][0], tr[i - 1][1]), [c, d] = P(tr[i][0], tr[i][1]);
    x.strokeStyle = `rgba(183,255,53,${(i / tr.length) * 0.8})`; x.lineWidth = 3 * (i / tr.length) + 0.5;
    x.beginPath(); x.moveTo(a, b); x.lineTo(c, d); x.stroke();
  }
  // eased pose
  const [px, py, pth] = S.pose;
  disp.x += (px - disp.x) * 0.18; disp.y += (py - disp.y) * 0.18;
  let dth = pth - disp.th; dth = Math.atan2(Math.sin(dth), Math.cos(dth)); disp.th += dth * 0.18;
  const [rx, ry] = P(disp.x, disp.y);
  // LiDAR rays
  if (S.rays && S.rays.length) {
    S.rays.forEach((d, i) => {
      const a = disp.th + (i * 2 * Math.PI) / 24, [hx, hy] = P(disp.x + Math.cos(a) * d, disp.y + Math.sin(a) * d);
      const near = d < 0.8;
      x.strokeStyle = near ? "#ffbd5988" : "#4fe3ff44"; x.lineWidth = 1.2;
      x.beginPath(); x.moveTo(rx, ry); x.lineTo(hx, hy); x.stroke();
      x.fillStyle = near ? C.amber : C.cyan; x.beginPath(); x.arc(hx, hy, 3, 0, Math.PI * 2); x.fill();
    });
  }
  // robot
  const bodyW = 0.5 * sc, bodyL = 0.6 * sc;
  x.save(); x.translate(rx, ry); x.rotate(-disp.th);
  const glow = S.permit ? C.lime : S.step ? C.red : C.soft;
  x.shadowColor = glow; x.shadowBlur = 24;
  x.fillStyle = "#101942"; x.strokeStyle = glow; x.lineWidth = 3;
  roundRect(x, -bodyL / 2, -bodyW / 2, bodyL, bodyW, 10); x.fill(); x.stroke(); x.shadowBlur = 0;
  [[-1, -1], [1, -1], [-1, 1], [1, 1]].forEach(([sx, sy], k) => {               // mecanum wheels
    x.save(); x.translate(sx * bodyL * 0.34, sy * bodyW * 0.62);
    x.fillStyle = "#1b2550"; roundRect(x, -bodyL * 0.13, -bodyW * 0.12, bodyL * 0.26, bodyW * 0.24, 4); x.fill();
    x.strokeStyle = Math.abs(S.wheels[k]) > 0.2 ? C.lime : "#3a4670"; x.lineWidth = 2;
    const off = (wheelAng[k] % 1) * bodyL * 0.08;
    for (let j = -2; j <= 2; j++) { const xx = j * bodyL * 0.05 + off; x.beginPath(); x.moveTo(xx - 4, -bodyW * 0.1); x.lineTo(xx + 4, bodyW * 0.1); x.stroke(); }
    x.restore();
  });
  x.fillStyle = glow; x.beginPath(); x.moveTo(bodyL / 2 + 10, 0); x.lineTo(bodyL / 2 - 4, -8); x.lineTo(bodyL / 2 - 4, 8); x.fill();   // heading
  x.fillStyle = C.white; x.font = `700 ${Math.max(10, sc * 0.09)}px Montserrat, sans-serif`; x.textAlign = "center"; x.fillText("GARDA", 0, 4);
  // velocity vector (body frame) and omega arc
  const vx = disp.g[0], vy = disp.g[1], w = disp.g[2];
  if (Math.hypot(vx, vy) > 0.02) {
    x.strokeStyle = C.lime; x.fillStyle = C.lime; x.lineWidth = 4;
    const ex = vx * bodyL * 1.2, ey = -vy * bodyL * 1.2;
    x.beginPath(); x.moveTo(0, 0); x.lineTo(ex, ey); x.stroke();
    const a = Math.atan2(ey, ex); x.beginPath(); x.moveTo(ex, ey); x.lineTo(ex - 12 * Math.cos(a - 0.4), ey - 12 * Math.sin(a - 0.4)); x.lineTo(ex - 12 * Math.cos(a + 0.4), ey - 12 * Math.sin(a + 0.4)); x.fill();
  }
  if (Math.abs(w) > 0.02) {
    x.strokeStyle = C.violet; x.lineWidth = 3;
    x.beginPath(); x.arc(0, 0, bodyL * 0.75, 0, -w * Math.PI * 0.9, w > 0); x.stroke();
  }
  x.restore();
}
function roundRect(x, a, b, w, h, r) { x.beginPath(); x.moveTo(a + r, b); x.arcTo(a + w, b, a + w, b + h, r); x.arcTo(a + w, b + h, a, b + h, r); x.arcTo(a, b + h, a, b, r); x.arcTo(a, b, a + w, b, r); x.closePath(); }

// ------------------------------------------------------------ frame loop
let lastT = performance.now();
function frame(now) {
  const dt = Math.min(0.05, (now - lastT) / 1000); lastT = now;
  if (S) {
    for (let k = 0; k < 3; k++) { disp.g[k] += (S.gated[k] / 256 - disp.g[k]) * 0.2; disp.r[k] += (S.raw[k] / 256 - disp.r[k]) * 0.2; }
    S.wheels.forEach((v, k) => { wheelAng[k] += v * dt * 0.15; const el = $(`#w${k} i`); el.style.transform = `rotate(${wheelAng[k] * 360}deg)`; $(`#w${k}`).classList.toggle("idle", Math.abs(v) < 0.2); });
    drawGauge($("#gVx"), disp.g[0], disp.r[0], C.lime); drawGauge($("#gVy"), disp.g[1], disp.r[1], C.cyan); drawGauge($("#gW"), disp.g[2], disp.r[2], C.violet);
    if (wave > 0) { wave += dt * 2.2; if (wave > 1) wave = 0; }
    ["#stSensor", "#stNeural", "#stGate", "#stWheels"].forEach((id, i) => $(id).classList.toggle("pulse", wave > 0 && wave * 4 >= i && wave * 4 < i + 1));
    drawNet();
  }
  drawArena();
  requestAnimationFrame(frame);
}
requestAnimationFrame(frame);

// ------------------------------------------------------------ controls
function seg(id, cb) { $$(`#${id} button`).forEach((b) => (b.onclick = () => { $$(`#${id} button`).forEach((x) => x.classList.toggle("on", x === b)); cb(b.dataset.v); })); }
seg("segBackend", (v) => { backend = v; msg(v === "fpga" ? "LIVE FPGA: inference and the safety gate run on the DE10-Lite" : "SIMULATION: bit-exact software model, no hardware"); });
seg("segInputs", (v) => { inputs = v; msg(v === "lidar" ? "Virtual LiDAR is experimental: the legacy model was not trained on this arena" : "Golden dataset: every output is checked bit for bit"); });
$("#btnRun").onclick = async () => {
  if (S && S.running) { await api("/api/physai/stop", {}); msg("stopped"); return; }
  const r = await api("/api/physai/start", {backend, inputs});
  msg(r.ok ? `running · ${backend === "fpga" ? "LIVE HARDWARE" : "SOFTWARE SIMULATION"}` : r.error, r.ok ? "ok" : "err");
};
$("#btnEstop").onclick = async () => { const r = await api("/api/physai/estop", {}); msg(r.ok ? "E-STOP sent: the safety gate forces Vx, Vy, ω to zero" : r.error, r.ok ? "ok" : "err"); };
$("#btnReset").onclick = async () => { await api("/api/physai/reset", {}); msg("safe reset: gate reopens after the next completed inference", "ok"); };
document.addEventListener("keydown", (e) => { if (e.code === "Space" && e.target === document.body) { e.preventDefault(); $("#btnEstop").click(); } });
const want = new URLSearchParams(location.search);
if (want.get("backend")) $(`#segBackend button[data-v="${want.get("backend")}"]`)?.click();
if (want.get("autostart")) setTimeout(() => $("#btnRun").click(), 600);
