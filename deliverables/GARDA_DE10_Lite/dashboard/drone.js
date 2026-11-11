// GARDA Drone Simulator: an inspection drone photographs SUTET 500 kV components. The AI wants every photo as
// close as possible, so it aims straight at the object; the GARDA reflex stops it exactly 1.2 m (centre) /
// 0.6 m (airframe) from any structure. The reflex runs only while the GARDA FPGA answers over UART (or in the
// labelled no-FPGA simulation mode). KEY1 / SW3 / host E-stop on the board are read live and hold the drone.
import * as THREE from "./vendor/three.module.min.js";

let TOKEN = document.querySelector('meta[name="garda-token"]').content;
const $ = (s) => document.querySelector(s);
const SAFE = 1.2, LOOK = 0.8, AIRFRAME = 0.6, STOP_D = 0.8;
const COL = {lime: 0x9aff00, red: 0xff3b5c, amber: 0xffb020, sky: 0x1e8fe0, white: 0xffffff, arc: 0xbfe6ff};

// ------------------------------------------------------------------ bridge to the FPGA
async function api(path, body, retried = false) {
  const opt = body === undefined ? {cache: "no-store"} : {method: "POST", headers: {"Content-Type": "application/json", "X-GARDA-Token": TOKEN}, body: JSON.stringify(body)};
  const r = await fetch(path, opt);
  if (r.status === 403 && body !== undefined && !retried) {
    const m = (await (await fetch("/drone.html", {cache: "no-store"})).text()).match(/name="garda-token" content="([^"]+)"/);
    if (m) { TOKEN = m[1]; return api(path, body, true); }
  }
  return r.json();
}
const hw = {bridge: false, checked: false, uart: "PORT NOT FOUND", fpgaOk: false, hold: null, misses: 0, seqRunning: false};
async function pollState() {
  try {
    const s = await api("/api/state");
    hw.bridge = hw.checked = true; hw.uart = s.uart.state; hw.seqRunning = s.sequence.running;
    if (hw.uart !== "FPGA RESPONDING" && !hw.seqRunning) hw.fpgaOk = false;
  } catch { hw.bridge = false; hw.checked = true; hw.fpgaOk = false; }
}
let pollBusy = false;                                   // backpressure: never queue requests behind a slow link
async function pollFpga() {
  if (pollBusy || !hw.bridge || hw.uart !== "FPGA RESPONDING" || hw.seqRunning) return;
  pollBusy = true;
  try {
    const r = await api("/api/command", {name: "ext_status"});
    if (!r.ok) throw new Error(r.error);
    const v = r.value, reasons = [];
    if (v & 2) reasons.push("KEY1 ditekan");
    if (v & 1) reasons.push("E-stop dari host");
    if (v >> 8 & 1) reasons.push("SW3 protective stop");
    if (v >> 3 & 1) reasons.push("watchdog");
    if (v >> 7 & 1) reasons.push("SW2 not ready");
    hw.hold = reasons.length ? reasons.join(" · ") : null;
    hw.fpgaOk = true; hw.misses = 0;
  } catch { if (++hw.misses >= 3) hw.fpgaOk = false; }
  finally { pollBusy = false; }
}
setInterval(pollState, 1000); setInterval(pollFpga, 250); pollState();

// ------------------------------------------------------------------ renderer / scene
const canvas = $("#scene");
const renderer = new THREE.WebGLRenderer({canvas, antialias: true});
renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
renderer.toneMapping = THREE.ACESFilmicToneMapping; renderer.toneMappingExposure = 1.1;
renderer.outputColorSpace = THREE.SRGBColorSpace;
renderer.shadowMap.enabled = true; renderer.shadowMap.type = THREE.PCFSoftShadowMap;
const scene = new THREE.Scene();
scene.fog = new THREE.Fog(0x3a2f6a, 110, 420);
const camera = new THREE.PerspectiveCamera(52, 1, 0.1, 1500);
function resize() { renderer.setSize(innerWidth, innerHeight, false); camera.aspect = innerWidth / innerHeight; camera.updateProjectionMatrix(); }
addEventListener("resize", resize); resize();

scene.add(new THREE.Mesh(new THREE.SphereGeometry(900, 32, 16), new THREE.ShaderMaterial({
  side: THREE.BackSide, depthWrite: false, fog: false,
  uniforms: {top: {value: new THREE.Color(0x00005c)}, mid: {value: new THREE.Color(0x3b2a86)}, hor: {value: new THREE.Color(0xf29a6e)}},
  vertexShader: "varying vec3 vp; void main(){ vp = position; gl_Position = projectionMatrix * modelViewMatrix * vec4(position,1.0); }",
  fragmentShader: "uniform vec3 top,mid,hor; varying vec3 vp; void main(){ float h = normalize(vp).y; vec3 c = h > 0.1 ? mix(mid, top, smoothstep(0.1, 0.6, h)) : mix(hor, mid, smoothstep(-0.04, 0.1, h)); gl_FragColor = vec4(c, 1.0); }",
})));
scene.add(new THREE.HemisphereLight(0xa8b8ff, 0x3a2a1a, 0.85));
const sun = new THREE.DirectionalLight(0xffc3a0, 1.9);
sun.castShadow = true; sun.shadow.mapSize.set(2048, 2048); sun.shadow.bias = -0.0005;
Object.assign(sun.shadow.camera, {left: -45, right: 45, top: 45, bottom: -45, near: 10, far: 450});
scene.add(sun, sun.target);
const rnd = (() => { let s = 7; return () => (s = (s * 16807) % 2147483647) / 2147483647; })();

// ------------------------------------------------------------------ terrain ("tanah")
function terrainH(x, z) {
  const hills = Math.min(1, Math.max(0, (Math.abs(x) - 26) / 45));
  const n = (Math.sin(x * 0.021) + Math.sin(z * 0.017 + 1.3)) * 4 + Math.sin(x * 0.05 + z * 0.04) * 2.2 + Math.sin(x * 0.11 - z * 0.09) * 0.9;
  return hills * (n + 7) + 0.18 * Math.sin(x * 0.55 + 1.1) * Math.sin(z * 0.47) + 0.1 * Math.sin(x * 1.3 + z * 0.9);
}
function grainTexture() {
  const c = document.createElement("canvas"); c.width = c.height = 256;
  const g = c.getContext("2d"), img = g.createImageData(256, 256);
  for (let i = 0; i < 256 * 256; i++) { const v = 200 + Math.random() * 55 - (Math.random() < 0.04 ? 70 : 0); img.data.set([v, v * 0.97, v * 0.92, 255], i * 4); }
  g.putImageData(img, 0, 0);
  const t = new THREE.CanvasTexture(c); t.wrapS = t.wrapT = THREE.RepeatWrapping; t.repeat.set(140, 140); t.colorSpace = THREE.SRGBColorSpace; return t;
}
const TOWERS = [-120, 0, 120];
{
  const geo = new THREE.PlaneGeometry(900, 900, 240, 240); geo.rotateX(-Math.PI / 2);
  const pos = geo.attributes.position, cols = new Float32Array(pos.count * 3);
  const soil = new THREE.Color(0x6b5238), dry = new THREE.Color(0x7d7a3e), green = new THREE.Color(0x40632c), gravel = new THREE.Color(0x77716a), c = new THREE.Color();
  for (let i = 0; i < pos.count; i++) {
    const x = pos.getX(i), z = pos.getZ(i), y = terrainH(x, z); pos.setY(i, y);
    const n = 0.5 + 0.5 * Math.sin(x * 0.13 + Math.sin(z * 0.07) * 2) * Math.cos(z * 0.11);
    c.copy(soil).lerp(dry, n).lerp(green, Math.min(1, Math.max(0, y / 9 + 0.25 * Math.sin(x * 0.03 + z * 0.05))));
    if (TOWERS.some((tz) => Math.hypot(x, z - tz) < 9)) c.lerp(gravel, 0.75);
    if (Math.abs(x - 22) < 3) c.copy(gravel).multiplyScalar(1.1);                   // access road
    cols.set([c.r, c.g, c.b], i * 3);
  }
  geo.setAttribute("color", new THREE.BufferAttribute(cols, 3)); geo.computeVertexNormals();
  const ground = new THREE.Mesh(geo, new THREE.MeshStandardMaterial({vertexColors: true, map: grainTexture(), roughness: 0.98}));
  ground.receiveShadow = true; scene.add(ground);
  const tuft = new THREE.InstancedMesh(new THREE.ConeGeometry(0.09, 0.55, 3), new THREE.MeshStandardMaterial({color: 0x5f7d34, roughness: 1}), 7000);
  const rock = new THREE.InstancedMesh(new THREE.DodecahedronGeometry(0.45, 0), new THREE.MeshStandardMaterial({color: 0x7c766e, roughness: 0.95, flatShading: true}), 360);
  const trunk = new THREE.InstancedMesh(new THREE.CylinderGeometry(0.18, 0.28, 3, 6), new THREE.MeshStandardMaterial({color: 0x4a3524, roughness: 1}), 160);
  const crown = new THREE.InstancedMesh(new THREE.ConeGeometry(2.2, 6, 7), new THREE.MeshStandardMaterial({color: 0x2f4d26, roughness: 1, flatShading: true}), 160);
  const m = new THREE.Matrix4(), q = new THREE.Quaternion(), s = new THREE.Vector3(), p = new THREE.Vector3();
  const free = (x, z) => Math.abs(x - 22) > 3.5 && !TOWERS.some((tz) => Math.hypot(x, z - tz) < 7);
  for (let i = 0; i < 7000; i++) {
    let x, z; do { x = (rnd() - 0.5) * 220; z = (rnd() - 0.5) * 260; } while (!free(x, z));
    q.setFromAxisAngle(new THREE.Vector3(rnd() - 0.5, 1, rnd() - 0.5).normalize(), rnd() * 0.4);
    const k = 0.6 + rnd() * 1.1; m.compose(p.set(x, terrainH(x, z) + 0.2 * k, z), q, s.set(k, k, k)); tuft.setMatrixAt(i, m);
  }
  for (let i = 0; i < 360; i++) {
    let x, z; do { x = (rnd() - 0.5) * 200; z = (rnd() - 0.5) * 240; } while (!free(x, z));
    q.setFromEuler(new THREE.Euler(rnd() * 3, rnd() * 3, rnd() * 3)); const k = 0.4 + rnd() * 1.4;
    m.compose(p.set(x, terrainH(x, z) + 0.1, z), q, s.set(k, k * 0.7, k)); rock.setMatrixAt(i, m);
  }
  for (let i = 0; i < 160; i++) {
    const a = rnd() * Math.PI * 2, r = 45 + rnd() * 130, x = Math.cos(a) * r, z = Math.sin(a) * r * 1.4;
    if (Math.abs(x) < 30) { i--; continue; }
    const k = 0.8 + rnd() * 0.9, y = terrainH(x, z);
    m.compose(p.set(x, y + 1.5 * k, z), q.identity(), s.set(k, k, k)); trunk.setMatrixAt(i, m);
    m.compose(p.set(x, y + 5.5 * k, z), q.identity(), s.set(k, k, k)); crown.setMatrixAt(i, m);
  }
  [tuft, rock, trunk, crown].forEach((im) => { im.receiveShadow = true; scene.add(im); });
  rock.castShadow = crown.castShadow = true;
  const mountainMat = new THREE.MeshStandardMaterial({color: 0x2a2150, roughness: 1, flatShading: true});
  for (let i = 0; i < 26; i++) {
    const a = (i / 26) * Math.PI * 2, r = 300 + (i % 3) * 50, h = 50 + ((i * 37) % 60);
    const mo = new THREE.Mesh(new THREE.ConeGeometry(60 + (i % 4) * 15, h, 6), mountainMat);
    mo.position.set(Math.cos(a) * r, h / 2 - 4, Math.sin(a) * r); mo.rotation.y = i; scene.add(mo);
  }
}

// ------------------------------------------------------------------ SUTET 500 kV towers + twin-bundle conductors
const H = 34, LEVELS = [{y: 24, l: 6.5}, {y: 28, l: 7.5}, {y: 32, l: 5.5}], INS = 1.8, SAG = 6, BUNDLE = 0.22;
const towerHalf = (y) => THREE.MathUtils.lerp(3.4, 0.8, Math.min(1, y / H));
const steel = new THREE.LineBasicMaterial({color: 0xd0d6ea});
const steelMesh = new THREE.MeshStandardMaterial({color: 0xaeb6c8, metalness: 0.6, roughness: 0.45});
const insMat = new THREE.MeshStandardMaterial({color: 0xa9ecff, emissive: 0x1e8fe0, emissiveIntensity: 0.3, roughness: 0.25, metalness: 0.1});
const concrete = new THREE.MeshStandardMaterial({color: 0x8d8a84, roughness: 0.95});
const beacons = [];
function strut(a, b, r, mat) {
  const d = new THREE.Vector3().subVectors(b, a), m = new THREE.Mesh(new THREE.CylinderGeometry(r, r, d.length(), 6), mat);
  m.position.copy(a).addScaledVector(d, 0.5); m.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), d.normalize()); return m;
}
function buildTower(z0) {
  const g = new THREE.Group(), pts = [], o = new THREE.Vector3(0, 0, z0), P = (v) => pts.push(v.clone().add(o));
  const corner = (y, i) => { const h = towerHalf(y), s = [[1, 1], [1, -1], [-1, -1], [-1, 1]][i]; return new THREE.Vector3(s[0] * h, y, s[1] * h); };
  const lv = []; for (let y = 0; y <= H + 0.01; y += H / 12) lv.push(y);
  for (let k = 0; k < lv.length - 1; k++) for (let i = 0; i < 4; i++) {
    const a = corner(lv[k], i), b = corner(lv[k + 1], i), c = corner(lv[k], (i + 1) % 4), d = corner(lv[k + 1], (i + 1) % 4);
    P(a); P(c); P(a); P(d); P(c); P(b);
    const mid = a.clone().lerp(d, 0.5); P(mid); P(a.clone().lerp(b, 0.5)); P(mid); P(c.clone().lerp(d, 0.5));
  }
  for (let i = 0; i < 4; i++) g.add(strut(corner(0, i).add(o), corner(H, i).add(o), 0.09, steelMesh));
  for (const L of LEVELS) {
    const h = towerHalf(L.y);
    for (const s of [-1, 1]) {
      const tip = new THREE.Vector3(s * L.l, L.y, 0);
      for (const zz of [-0.9, 0.9]) { P(new THREE.Vector3(s * h, L.y, zz)); P(tip); P(new THREE.Vector3(s * h, L.y - 1.8, zz)); P(tip); }
      for (let t = 0.25; t < 1; t += 0.25) { const x = s * (h + (L.l - h) * t); P(new THREE.Vector3(x, L.y, -0.9 * (1 - t))); P(new THREE.Vector3(x, L.y, 0.9 * (1 - t))); }
      for (let k = 0; k < 12; k++) {                                           // insulator: 12 glass discs
        const disc = new THREE.Mesh(new THREE.CylinderGeometry(0.17, 0.17, 0.05, 14), insMat);
        disc.position.set(s * L.l, L.y - 0.12 - k * (INS - 0.25) / 12, z0); g.add(disc);
      }
      const yoke = new THREE.Mesh(new THREE.BoxGeometry(0.1, 0.06, BUNDLE * 2 + 0.1), steelMesh); yoke.position.set(s * L.l, L.y - INS, z0); g.add(yoke);
    }
  }
  for (const s of [-1, 1]) { P(new THREE.Vector3(s * 0.8, H, 0)); P(new THREE.Vector3(s * 1.6, H + 4, 0)); P(new THREE.Vector3(s * 1.6, H + 4, 0)); P(new THREE.Vector3(0, H + 2, 0)); }
  g.add(new THREE.LineSegments(new THREE.BufferGeometry().setFromPoints(pts), steel));
  for (let i = 0; i < 4; i++) {
    const c = corner(0, i), f = new THREE.Mesh(new THREE.BoxGeometry(1.4, 1.0, 1.4), concrete);
    f.position.set(c.x, 0.3, c.z + z0); f.castShadow = f.receiveShadow = true; g.add(f);
  }
  const beacon = new THREE.Mesh(new THREE.SphereGeometry(0.22, 12, 8), new THREE.MeshBasicMaterial({color: 0xff2030}));
  beacon.position.set(0, H + 2.3, z0); g.add(beacon); beacons.push(beacon);
  const sign = new THREE.Mesh(new THREE.BoxGeometry(0.04, 0.7, 0.9), new THREE.MeshStandardMaterial({color: 0xffd21a, emissive: 0x332600}));
  sign.position.set(towerHalf(3) + 0.05, 3, z0); g.add(sign);
  return g;
}
TOWERS.forEach((z) => scene.add(buildTower(z)));
function condY(L, z) { const tt = THREE.MathUtils.clamp((z - Math.floor(z / 120) * 120) / 120, 0, 1); return L.y - INS - SAG * 4 * tt * (1 - tt); }
const wireMat = new THREE.MeshStandardMaterial({color: 0x9fb0d8, emissive: 0x2a46ff, emissiveIntensity: 0.45, metalness: 0.7, roughness: 0.35});
for (const L of LEVELS) for (const s of [-1, 1]) {
  for (const dz of [-BUNDLE, BUNDLE]) {
    const pts = []; for (let z = -240; z <= 240; z += 3) pts.push(new THREE.Vector3(s * L.l + dz, condY(L, z), z));
    scene.add(new THREE.Mesh(new THREE.TubeGeometry(new THREE.CatmullRomCurve3(pts), 320, 0.045, 6), wireMat));
  }
  for (let z = -234; z <= 234; z += 12) if (z % 120) {
    const sp = new THREE.Mesh(new THREE.BoxGeometry(BUNDLE * 2 + 0.08, 0.05, 0.05), steelMesh); sp.position.set(s * L.l, condY(L, z), z); scene.add(sp);
  }
}
for (const s of [-1, 1]) {
  const pts = []; for (let z = -240; z <= 240; z += 4) { const tt = THREE.MathUtils.clamp((z - Math.floor(z / 120) * 120) / 120, 0, 1); pts.push(new THREE.Vector3(s * 1.6, H + 4 - 12 * tt * (1 - tt), z)); }
  scene.add(new THREE.Mesh(new THREE.TubeGeometry(new THREE.CatmullRomCurve3(pts), 240, 0.03, 5), steelMesh));
}
function dTower(p) {
  let d = 1e9;
  for (const z0 of TOWERS) {
    const hd = Math.hypot(p.x, p.z - z0), r = towerHalf(Math.max(0, Math.min(H, p.y))) * 1.15;
    const dy = p.y > H + 4 ? p.y - H - 4 : (p.y < 0 ? -p.y : 0);
    d = Math.min(d, dy > 0 ? Math.hypot(Math.max(hd - r, 0), dy) : hd - r);
    for (const L of LEVELS) { const cx = THREE.MathUtils.clamp(p.x, -L.l, L.l); d = Math.min(d, Math.hypot(p.x - cx, p.y - L.y, p.z - z0) - 0.5); }
  }
  return d;
}
function nearestConductor(p) {
  let best = {d: 1e9, x: 0, y: 0};
  for (const L of LEVELS) for (const s of [-1, 1]) {
    const x = s * L.l, y = condY(L, p.z), d = Math.hypot(p.x - x, p.y - y) - BUNDLE - 0.05;
    if (d < best.d) best = {d, x, y};
  }
  return best;
}
const sdf = (p) => Math.min(dTower(p), nearestConductor(p).d);
const _e = new THREE.Vector3();
function sdfGrad(p) {
  const h = 0.04, d = sdf(p);
  const n = new THREE.Vector3(sdf(_e.set(p.x + h, p.y, p.z)) - sdf(_e.set(p.x - h, p.y, p.z)),
    sdf(_e.set(p.x, p.y + h, p.z)) - sdf(_e.set(p.x, p.y - h, p.z)), sdf(_e.set(p.x, p.y, p.z + h)) - sdf(_e.set(p.x, p.y, p.z - h))).normalize();
  return {d, n};
}

// ------------------------------------------------------------------ detailed inspection drone (Matrice-4T style)
function rounded(w, h, r) {
  const s = new THREE.Shape(), x = -w / 2, y = -h / 2;
  s.moveTo(x + r, y); s.lineTo(x + w - r, y); s.quadraticCurveTo(x + w, y, x + w, y + r); s.lineTo(x + w, y + h - r);
  s.quadraticCurveTo(x + w, y + h, x + w - r, y + h); s.lineTo(x + r, y + h); s.quadraticCurveTo(x, y + h, x, y + h - r);
  s.lineTo(x, y + r); s.quadraticCurveTo(x, y, x + r, y); return s;
}
function slab(w, d, h, r, mat, bevel = 0.02) {
  const g = new THREE.ExtrudeGeometry(rounded(w, d, r), {depth: h, bevelEnabled: true, bevelThickness: bevel, bevelSize: bevel, bevelSegments: 3, curveSegments: 6});
  g.rotateX(-Math.PI / 2); g.translate(0, -h / 2, 0); return new THREE.Mesh(g, mat);
}
const M = {
  shell: new THREE.MeshStandardMaterial({color: 0xaab0b8, roughness: 0.55, metalness: 0.1}),
  cover: new THREE.MeshStandardMaterial({color: 0xc6cad1, roughness: 0.45, metalness: 0.1}),
  dark: new THREE.MeshStandardMaterial({color: 0x2a2d33, roughness: 0.55, metalness: 0.35}),
  carbon: new THREE.MeshStandardMaterial({color: 0x17191d, roughness: 0.4, metalness: 0.2}),
  metal: new THREE.MeshStandardMaterial({color: 0x8c929c, roughness: 0.3, metalness: 0.85}),
  glass: new THREE.MeshStandardMaterial({color: 0x0b1424, roughness: 0.08, metalness: 0.9, emissive: 0x0a2a55, emissiveIntensity: 0.6}),
  orange: new THREE.MeshStandardMaterial({color: 0xff7a1a, emissive: 0x7a2a00, roughness: 0.5}),
};
function blade() {
  const s = new THREE.Shape();
  s.moveTo(0, -0.016); s.bezierCurveTo(0.08, -0.03, 0.17, -0.022, 0.235, -0.008); s.quadraticCurveTo(0.245, 0, 0.235, 0.008);
  s.bezierCurveTo(0.16, 0.016, 0.07, 0.024, 0, 0.018); s.lineTo(0, -0.016);
  const g = new THREE.ExtrudeGeometry(s, {depth: 0.005, bevelEnabled: true, bevelThickness: 0.0015, bevelSize: 0.0015, bevelSegments: 1, curveSegments: 10});
  g.rotateX(-Math.PI / 2);
  const b = new THREE.Group(), m = new THREE.Mesh(g, M.carbon); m.rotation.x = 0.16; b.add(m);
  const tip = new THREE.Mesh(new THREE.BoxGeometry(0.032, 0.007, 0.018), M.orange); tip.position.set(0.222, 0.002, 0); b.add(tip);
  return b;
}
function buildDrone(ghost = false) {
  const g = new THREE.Group(), parts = [];
  const add = (m, x, y, z) => { m.position.set(x, y, z); g.add(m); parts.push(m); return m; };
  add(slab(0.56, 0.3, 0.12, 0.09, M.shell, 0.03), 0, 0, 0);                                   // fuselage
  add(slab(0.44, 0.24, 0.04, 0.08, M.cover, 0.02), -0.02, 0.085, 0);                          // top cover
  add(new THREE.Mesh(new THREE.SphereGeometry(0.15, 24, 14), M.shell), 0.25, 0, 0).scale.set(0.55, 0.5, 0.95);   // nose
  for (const z of [-0.075, 0.075]) {                                                          // forward vision sensors
    add(new THREE.Mesh(new THREE.CylinderGeometry(0.022, 0.022, 0.012, 16), M.glass), 0.322, 0.02, z).rotation.z = Math.PI / 2;
    add(new THREE.Mesh(new THREE.TorusGeometry(0.024, 0.005, 6, 16), M.dark), 0.326, 0.02, z).rotation.y = Math.PI / 2;
  }
  for (const z of [-0.16, 0.16]) add(new THREE.Mesh(new THREE.CylinderGeometry(0.018, 0.018, 0.01, 14), M.glass), 0.05, 0.02, z).rotation.x = Math.PI / 2;
  for (let i = 0; i < 6; i++) add(new THREE.Mesh(new THREE.BoxGeometry(0.012, 0.008, 0.16), M.dark), -0.1 - i * 0.022, 0.112, 0);   // vents
  add(new THREE.Mesh(new THREE.CylinderGeometry(0.07, 0.08, 0.05, 28), M.cover), -0.05, 0.14, 0);                                   // RTK module
  add(new THREE.Mesh(new THREE.SphereGeometry(0.07, 24, 10, 0, Math.PI * 2, 0, Math.PI / 2), M.cover), -0.05, 0.165, 0);
  add(slab(0.16, 0.2, 0.09, 0.04, M.dark, 0.012), -0.3, 0.01, 0);                                                                     // battery
  for (let i = 0; i < 4; i++) add(new THREE.Mesh(new THREE.BoxGeometry(0.008, 0.07, 0.024), M.carbon), -0.385, 0.01, -0.06 + i * 0.04);   // grip ridges
  add(new THREE.Mesh(new THREE.BoxGeometry(0.05, 0.02, 0.18), M.dark), 0.2, -0.085, 0);                                               // gimbal yoke
  for (const z of [-0.085, 0.085]) add(new THREE.Mesh(new THREE.BoxGeometry(0.03, 0.09, 0.012), M.dark), 0.2, -0.13, z);
  add(slab(0.13, 0.15, 0.11, 0.03, M.dark, 0.012), 0.21, -0.165, 0);                                                                  // sensor head
  [[0.035, 0.03, 0.03, M.glass], [-0.036, 0.03, 0.026, M.glass], [0.035, -0.027, 0.022, M.carbon], [-0.036, -0.03, 0.012, M.glass]].forEach(([z, y, r, mat]) => {
    add(new THREE.Mesh(new THREE.CylinderGeometry(r, r * 1.08, 0.03, 20), mat), 0.29, -0.165 + y, z).rotation.z = Math.PI / 2;   // wide, zoom, thermal, laser
    add(new THREE.Mesh(new THREE.TorusGeometry(r * 1.1, 0.004, 6, 20), M.metal), 0.304, -0.165 + y, z).rotation.y = Math.PI / 2;
  });
  const props = [], leds = [];
  [[1, 0.62], [1, -0.62], [-1, 2.52], [-1, -2.52]].forEach(([sx, ang]) => {
    const start = new THREE.Vector3(sx * 0.17, 0.02, Math.sign(ang) * 0.1), end = new THREE.Vector3(Math.cos(ang) * 0.58, 0.055, Math.sin(ang) * 0.58);
    const arm = strut(start, end, 0.026, M.shell); g.add(arm); parts.push(arm);
    add(new THREE.Mesh(new THREE.CylinderGeometry(0.034, 0.034, 0.05, 14), M.dark), start.x, 0.02, start.z);   // fold hinge
    add(new THREE.Mesh(new THREE.CylinderGeometry(0.052, 0.058, 0.07, 22), M.dark), end.x, 0.06, end.z);       // motor
    for (let k = 0; k < 12; k++) {
      const a = k / 12 * Math.PI * 2;
      add(new THREE.Mesh(new THREE.BoxGeometry(0.004, 0.05, 0.014), M.metal), end.x + Math.cos(a) * 0.058, 0.06, end.z + Math.sin(a) * 0.058).rotation.y = -a;
    }
    add(new THREE.Mesh(new THREE.CylinderGeometry(0.046, 0.046, 0.022, 22), M.metal), end.x, 0.105, end.z);
    const leg = strut(new THREE.Vector3(end.x, 0.03, end.z), new THREE.Vector3(end.x * 1.04, -0.15, end.z * 1.04), 0.011, M.cover); g.add(leg); parts.push(leg);
    add(new THREE.Mesh(new THREE.SphereGeometry(0.018, 10, 8), M.dark), end.x * 1.04, -0.155, end.z * 1.04);
    const prop = new THREE.Group(); prop.position.set(end.x, 0.125, end.z);
    prop.add(new THREE.Mesh(new THREE.CylinderGeometry(0.022, 0.022, 0.02, 14), M.metal));
    for (const r of [0, Math.PI]) { const b = blade(); b.rotation.y = r; prop.add(b); }
    const disc = new THREE.Mesh(new THREE.CircleGeometry(0.245, 40), new THREE.MeshBasicMaterial({color: 0xd6dcff, transparent: true, opacity: 0, side: THREE.DoubleSide, depthWrite: false}));
    disc.rotation.x = -Math.PI / 2; prop.add(disc); prop.userData.disc = disc;
    g.add(prop); props.push(prop); parts.push(prop);
    const led = new THREE.Mesh(new THREE.SphereGeometry(0.016, 8, 6), new THREE.MeshBasicMaterial({color: sx > 0 ? 0x33ff66 : 0xff3355}));
    led.position.set(end.x, 0.015, end.z); g.add(led); leds.push(led);
  });
  if (ghost) g.traverse((o) => { if (o.isMesh) o.material = new THREE.MeshBasicMaterial({color: 0xffffff, transparent: true, opacity: 0.18, depthWrite: false}); });
  else g.traverse((o) => { if (o.isMesh) o.castShadow = true; });
  Object.assign(g.userData, {props, leds, parts});
  g.scale.setScalar(2.0);
  return g;
}
const drone = buildDrone(false), ghost = buildDrone(true);
scene.add(drone, ghost);
const navGlow = new THREE.PointLight(0x9aff00, 3, 8); drone.add(navGlow);

// overlays: safety bubble, distance beam, LiDAR, trail, inspection scan cone + target rings
const bubble = new THREE.Mesh(new THREE.SphereGeometry(SAFE, 40, 20), new THREE.MeshBasicMaterial({color: COL.lime, transparent: true, opacity: 0.12, wireframe: true, depthWrite: false}));
const beamGeo = new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(), new THREE.Vector3()]);
const beam = new THREE.Line(beamGeo, new THREE.LineBasicMaterial({color: COL.lime}));
const hitDot = new THREE.Mesh(new THREE.SphereGeometry(0.12, 12, 8), new THREE.MeshBasicMaterial({color: COL.lime}));
scene.add(bubble, beam, hitDot);
const RAYS = 18, rayPos = new Float32Array(RAYS * 6), rayGeo = new THREE.BufferGeometry();
rayGeo.setAttribute("position", new THREE.BufferAttribute(rayPos, 3));
const rays = new THREE.LineSegments(rayGeo, new THREE.LineBasicMaterial({color: COL.sky, transparent: true, opacity: 0.16, blending: THREE.AdditiveBlending, depthWrite: false}));
const TRAIL = 260, trailPos = new Float32Array(TRAIL * 3), trailGeo = new THREE.BufferGeometry();
trailGeo.setAttribute("position", new THREE.BufferAttribute(trailPos, 3));
const trail = new THREE.Line(trailGeo, new THREE.LineBasicMaterial({color: COL.lime, transparent: true, opacity: 0.75}));
scene.add(rays, trail);
const coneGeo = new THREE.ConeGeometry(0.5, 1, 32, 1, true); coneGeo.translate(0, -0.5, 0);
const scanCone = new THREE.Mesh(coneGeo, new THREE.MeshBasicMaterial({color: COL.lime, transparent: true, opacity: 0.16, side: THREE.DoubleSide, blending: THREE.AdditiveBlending, depthWrite: false, depthTest: false}));
scanCone.renderOrder = 5;
const scanLight = new THREE.PointLight(0xffffff, 0, 10);
scene.add(scanCone, scanLight);

// particles + electric arcs + debris
function points(n, color, size, opacity, blending = THREE.AdditiveBlending) {
  const pos = new Float32Array(n * 3), geo = new THREE.BufferGeometry(); geo.setAttribute("position", new THREE.BufferAttribute(pos, 3));
  const pts = new THREE.Points(geo, new THREE.PointsMaterial({color, size, transparent: true, opacity, blending, depthWrite: false}));
  scene.add(pts); return {pos, geo, pts, vel: Array.from({length: n}, () => new THREE.Vector3())};
}
const wind = points(1800, 0xe2e8ff, 0.14, 0.45);
for (let i = 0; i < 1800; i++) wind.pos.set([(rnd() - 0.5) * 120, rnd() * 50, (rnd() - 0.5) * 120], i * 3);
const sparks = points(260, 0xffd27a, 0.28, 0), smoke = points(160, 0x8c8a96, 1.4, 0, THREE.NormalBlending);
const arcs = Array.from({length: 4}, () => {
  const geo = new THREE.BufferGeometry(); geo.setAttribute("position", new THREE.BufferAttribute(new Float32Array(14 * 3), 3));
  const l = new THREE.Line(geo, new THREE.LineBasicMaterial({color: COL.arc, transparent: true, opacity: 0, blending: THREE.AdditiveBlending, depthWrite: false})); scene.add(l); return l;
});
const arcLight = new THREE.PointLight(0x9fd8ff, 0, 40); scene.add(arcLight);
const debris = [];

// ------------------------------------------------------------------ inspection mission
// Every target sits ON the structure. The AI wants a close-up, so it aims straight at the component:
// without GARDA it flies into it; with GARDA it stops at the 1.2 m line and photographs from there.
const L0 = LEVELS[0], L1 = LEVELS[1], L2 = LEVELS[2];
const TASKS = [
  {name: "Konduktor fasa bawah", sub: "foto klem spacer kabel 500 kV", p: new THREE.Vector3(-L0.l, condY(L0, -24), -24)},
  {name: "Isolator fasa tengah", sub: "cek 12 piringan isolator", p: new THREE.Vector3(-L1.l, L1.y - INS / 2, 0)},
  {name: "Badan menara", sub: "cek baut & korosi", p: new THREE.Vector3(towerHalf(18), 18, 0)},
  {name: "Travers atas", sub: "cek ujung travers kanan", p: new THREE.Vector3(L2.l, L2.y, 0)},
  {name: "Lampu aviasi", sub: "cek lampu merah puncak", p: new THREE.Vector3(0, H + 2.3, 0)},
];
const HOME = new THREE.Vector3(-26, 18, -34), SCAN_T = 3.0;
const rings = TASKS.map(() => {
  const r = new THREE.Mesh(new THREE.TorusGeometry(0.7, 0.05, 8, 40), new THREE.MeshBasicMaterial({color: COL.amber, transparent: true, opacity: 0.0, depthWrite: false}));
  scene.add(r); return r;
});
const sim = {running: false, p: HOME.clone(), v: new THREE.Vector3(), task: 0, status: TASKS.map(() => "todo"), round: 1, scanT: 0, limitT: 0, taskT: 0,
  yaw: 0, fixes: 0, crashes: 0, shocks: 0, photos: 0, state: "idle", crashT: 0, crashKind: "", contact: new THREE.Vector3(), strongWind: false, simMode: false,
  cam: 0, d: 99, lastFix: false, holdReason: null, t: 0, vAI: new THREE.Vector3(), trailN: 0, flashT: 0};
const target = () => (sim.task < TASKS.length ? TASKS[sim.task].p : HOME);
function clearDebris() { debris.forEach((d) => scene.remove(d.mesh)); debris.length = 0; }
function resetFlight() {
  sim.p.copy(HOME); sim.v.set(0, 0, 0); sim.task = 0; sim.status = TASKS.map(() => "todo"); sim.scanT = sim.limitT = sim.taskT = 0;
  sim.state = sim.running ? "safe" : "idle"; sim.trailN = 0;
  drone.visible = true; drone.rotation.set(0, 0, 0); clearDebris(); sparks.pts.material.opacity = 0; smoke.pts.material.opacity = 0;
  arcs.forEach((a) => (a.material.opacity = 0)); arcLight.intensity = 0;
}
const noise = (t, s) => Math.sin(t * 0.7 + s) * 0.6 + Math.sin(t * 1.9 + s * 3.1) * 0.3 + Math.sin(t * 4.3 + s * 1.7) * 0.1;
function windAt(t) {
  const base = sim.strongWind ? 4.2 : 1.3, gust = sim.strongWind ? 2.8 : 0.9, m = base + gust * (0.5 + 0.5 * noise(t, 1.3));
  return new THREE.Vector3(Math.cos(0.3 + 0.4 * noise(t * 0.3, 7)), 0.08 * noise(t, 4), Math.sin(0.3 + 0.4 * noise(t * 0.3, 7)) * 0.4).normalize().multiplyScalar(m);
}
const gardaActive = () => hw.fpgaOk || sim.simMode;
function gardaGate(p, vcmd, w) {                         // the reflex: never cut into the 1.2 m boundary
  const {d, n} = sdfGrad(p), v = vcmd.clone(), approach = -vcmd.clone().add(w).dot(n);
  let st = "safe";
  if (d < SAFE) { if (approach > 0) v.addScaledVector(n, approach); v.addScaledVector(n, (SAFE - d) * 2.2); st = "fix"; }
  else if (approach > 0 && d - SAFE < approach * LOOK) { v.addScaledVector(n, approach - (d - SAFE) / LOOK); st = "fix"; }
  if (d < STOP_D) { v.copy(n).multiplyScalar(1.6).sub(w); st = "stop"; }    // "Ragu? Henti": back off
  return {v, st, d, n};
}
function breakApart(strength) {
  drone.updateMatrixWorld(true);
  drone.userData.parts.forEach((part) => {
    const pos = new THREE.Vector3(), quat = new THREE.Quaternion(), scl = new THREE.Vector3();
    part.matrixWorld.decompose(pos, quat, scl);
    const mesh = part.clone(true); mesh.position.copy(pos); mesh.quaternion.copy(quat); mesh.scale.copy(scl);
    mesh.traverse((o) => { if (o.isMesh) { o.castShadow = true; o.material = o.material.clone(); if (sim.crashKind === "shock" && o.material.color) o.material.color.multiplyScalar(0.4); } });
    scene.add(mesh);
    const out = pos.clone().sub(sim.p).normalize();
    debris.push({mesh, v: out.multiplyScalar(strength * (0.6 + rnd())).add(new THREE.Vector3((rnd() - 0.5) * 2, rnd() * 3, (rnd() - 0.5) * 2)),
      w: new THREE.Vector3((rnd() - 0.5) * 12, (rnd() - 0.5) * 12, (rnd() - 0.5) * 12), rest: false});
  });
  drone.visible = false;
}
function startCrash(kind) {
  sim.state = "crash"; sim.crashKind = kind; sim.crashT = 0; sim.crashes++; if (kind === "shock") sim.shocks++;
  if (sim.task < TASKS.length) sim.status[sim.task] = "fail";
  for (let i = 0; i < 260; i++) { sparks.pos.set([sim.p.x, sim.p.y, sim.p.z], i * 3); sparks.vel[i].set((rnd() - 0.5) * 16, rnd() * 10 - 2, (rnd() - 0.5) * 16); }
  sparks.pts.material.opacity = 1;
  const f = $("#flash"); f.className = "flash on" + (kind === "shock" ? " shock" : ""); setTimeout(() => (f.className = "flash"), kind === "shock" ? 900 : 450);
  if (kind !== "shock") breakApart(4);
}
function updateCrash(dt) {
  sim.crashT += dt;
  if (sim.crashKind === "shock" && sim.crashT < 1.0) {                       // stuck on the live conductor, arcing
    arcs.forEach((a, k) => {
      const at = a.geometry.attributes.position, from = sim.contact, to = sim.p;
      for (let i = 0; i < 14; i++) {
        const t = i / 13, amp = 0.45 * Math.sin(Math.PI * t);
        at.setXYZ(i, from.x + (to.x - from.x) * t + (rnd() - 0.5) * amp, from.y + (to.y - from.y) * t + (rnd() - 0.5) * amp + k * 0.05, from.z + (to.z - from.z) * t + (rnd() - 0.5) * amp);
      }
      at.needsUpdate = true; a.material.opacity = rnd() > 0.25 ? 1 : 0.2;
    });
    arcLight.position.copy(sim.contact); arcLight.intensity = 40 + rnd() * 120;
    drone.position.copy(sim.p).add(new THREE.Vector3((rnd() - 0.5) * 0.08, (rnd() - 0.5) * 0.08, (rnd() - 0.5) * 0.08));
    if (rnd() < 0.3) for (let i = 0; i < 20; i++) { const j = Math.floor(rnd() * 260); sparks.pos.set([sim.contact.x, sim.contact.y, sim.contact.z], j * 3); sparks.vel[j].set((rnd() - 0.5) * 12, rnd() * 6, (rnd() - 0.5) * 12); }
  } else if (sim.crashKind === "shock" && drone.visible) {                  // then it falls apart
    arcs.forEach((a) => (a.material.opacity = 0)); arcLight.intensity = 0; breakApart(6);
    for (let i = 0; i < 160; i++) { smoke.pos.set([sim.p.x, sim.p.y, sim.p.z], i * 3); smoke.vel[i].set((rnd() - 0.5) * 1.5, 0.6 + rnd() * 1.6, (rnd() - 0.5) * 1.5); }
    smoke.pts.material.opacity = 0.55;
  }
  for (let i = 0; i < 260; i++) {
    sparks.vel[i].y -= 9.8 * dt;
    sparks.pos[i * 3] += sparks.vel[i].x * dt; sparks.pos[i * 3 + 1] += sparks.vel[i].y * dt; sparks.pos[i * 3 + 2] += sparks.vel[i].z * dt;
  }
  sparks.geo.attributes.position.needsUpdate = true; sparks.pts.material.opacity = Math.max(0, 1 - sim.crashT / 2.2);
  const wx = windAt(sim.t).x * 0.4;
  for (let i = 0; i < 160; i++) { smoke.pos[i * 3] += (smoke.vel[i].x + wx) * dt; smoke.pos[i * 3 + 1] += smoke.vel[i].y * dt; smoke.pos[i * 3 + 2] += smoke.vel[i].z * dt; }
  smoke.geo.attributes.position.needsUpdate = true; smoke.pts.material.opacity = Math.max(0, smoke.pts.material.opacity - dt * 0.08);
  for (const d of debris) {
    if (d.rest) continue;
    d.v.y -= 9.8 * dt; d.mesh.position.addScaledVector(d.v, dt);
    d.mesh.rotation.x += d.w.x * dt; d.mesh.rotation.y += d.w.y * dt; d.mesh.rotation.z += d.w.z * dt;
    const gy = terrainH(d.mesh.position.x, d.mesh.position.z) + 0.06;
    if (d.mesh.position.y < gy) { d.mesh.position.y = gy; d.v.y *= -0.32; d.v.x *= 0.6; d.v.z *= 0.6; d.w.multiplyScalar(0.55); if (Math.abs(d.v.y) < 0.4) d.rest = true; }
  }
  if (sim.crashT > 5.5) resetFlight();
}
function nextTask(result) {
  if (sim.task < TASKS.length) sim.status[sim.task] = result;
  sim.task++; sim.scanT = sim.limitT = sim.taskT = 0;
  if (sim.task > TASKS.length) { sim.task = 0; sim.round++; sim.status = TASKS.map(() => "todo"); }   // back home -> next round
}
function step(dt) {
  sim.t += dt;
  const w = windAt(sim.t);
  for (let i = 0; i < 1800; i++) {
    let x = wind.pos[i * 3] + w.x * dt * 3, y = wind.pos[i * 3 + 1] + w.y * dt * 3, z = wind.pos[i * 3 + 2] + w.z * dt * 3;
    if (x - sim.p.x > 60) x -= 120; if (x - sim.p.x < -60) x += 120; if (z - sim.p.z > 60) z -= 120; if (z - sim.p.z < -60) z += 120;
    wind.pos[i * 3] = x; wind.pos[i * 3 + 1] = y; wind.pos[i * 3 + 2] = z;
  }
  wind.geo.attributes.position.needsUpdate = true; wind.pts.material.opacity = sim.strongWind ? 0.75 : 0.38;
  if (sim.flashT > 0) sim.flashT = Math.max(0, sim.flashT - dt);
  if (sim.state === "crash") { updateCrash(dt); return; }
  if (!sim.running) { sim.vAI.set(0, 0, 0); return; }

  // 02 AI: fly straight at the inspection target (wants the closest possible photo), or home after the last task
  const tgt = target(), toT = tgt.clone().sub(sim.p), dist = toT.length(), home = sim.task >= TASKS.length;
  sim.taskT += dt;
  if (sim.scanT > 0) sim.vAI.set(0, 0, 0);                  // hovering while the gimbal photographs
  else sim.vAI.copy(toT).multiplyScalar(Math.min(4.6, dist * 0.9) / Math.max(dist, 1e-3));
  if (home && dist < 2) nextTask("done");

  // 03 gate
  let vcmd = sim.vAI.clone(), st = "unguarded";
  sim.holdReason = hw.fpgaOk ? hw.hold : null;
  if (sim.holdReason) { vcmd = w.clone().multiplyScalar(-1); st = "hold"; }
  else if (gardaActive()) { const g = gardaGate(sim.p, vcmd, w); vcmd = g.v; st = g.st; }
  if (st === "fix" || st === "stop") { sim.limitT += dt; if (!sim.lastFix) sim.fixes++; sim.lastFix = true; } else { sim.lastFix = false; sim.limitT = Math.max(0, sim.limitT - dt * 0.5); }

  // inspection: photograph when close (AI: < 0.9 m) or when GARDA holds the drone at the safe line within 3.2 m
  if (!home && sim.scanT === 0 && st !== "hold" && (dist < 0.9 || (dist < 3.2 && sim.limitT > 0.5))) sim.scanT = 0.001;
  if (sim.scanT > 0 && st !== "hold") {
    sim.scanT += dt;
    if (sim.scanT >= SCAN_T) { sim.photos++; sim.flashT = 0.25; nextTask("done"); }
  }
  if (!home && sim.taskT > 16 && sim.scanT === 0) nextTask("skip");

  // 04 motors
  sim.v.lerp(vcmd.clone().add(w), Math.min(1, dt * 3.4));
  sim.p.addScaledVector(sim.v, dt);
  const gnd = terrainH(sim.p.x, sim.p.z) + 2; if (sim.p.y < gnd) sim.p.y = gnd;
  const cond = nearestConductor(sim.p), dTw = dTower(sim.p);
  sim.d = Math.min(cond.d, dTw); sim.state = sim.scanT > 0 && st === "safe" ? "scan" : st;
  if (cond.d < AIRFRAME) { sim.contact.set(cond.x, cond.y, sim.p.z); startCrash("shock"); }   // touched a live 500 kV conductor
  else if (dTw < AIRFRAME) startCrash("impact");
}

// ------------------------------------------------------------------ visuals
const camState = {yaw: -0.6, pitch: 0.2, dist: 8.5, drag: null};
canvas.addEventListener("pointerdown", (e) => (camState.drag = [e.clientX, e.clientY]));
addEventListener("pointerup", () => (camState.drag = null));
addEventListener("pointermove", (e) => {
  if (!camState.drag) return;
  camState.yaw -= (e.clientX - camState.drag[0]) * 0.005; camState.pitch = THREE.MathUtils.clamp(camState.pitch + (e.clientY - camState.drag[1]) * 0.004, -0.15, 1.2);
  camState.drag = [e.clientX, e.clientY];
});
canvas.addEventListener("wheel", (e) => (camState.dist = THREE.MathUtils.clamp(camState.dist * (1 + e.deltaY * 0.001), 4, 70)), {passive: true});
const camLook = new THREE.Vector3(), camPos = new THREE.Vector3(), UP = new THREE.Vector3(0, -1, 0);
let tick = 0;
function visuals(dt, now) {
  const crash = sim.state === "crash";
  if (!crash) {
    drone.position.copy(sim.p);
    if (sim.scanT > 0) { const tg = target(); const want = Math.atan2(-(tg.z - sim.p.z), tg.x - sim.p.x); sim.yaw += Math.atan2(Math.sin(want - sim.yaw), Math.cos(want - sim.yaw)) * Math.min(1, dt * 3); }
    else if (Math.hypot(sim.v.x, sim.v.z) > 0.3) { const tgt = Math.atan2(-sim.v.z, sim.v.x); sim.yaw += Math.atan2(Math.sin(tgt - sim.yaw), Math.cos(tgt - sim.yaw)) * Math.min(1, dt * 2.5); }
    const fwd = sim.v.x * Math.cos(sim.yaw) - sim.v.z * Math.sin(sim.yaw), side = sim.v.x * Math.sin(sim.yaw) + sim.v.z * Math.cos(sim.yaw);
    drone.rotation.set(side * 0.05, sim.yaw, -fwd * 0.06, "YXZ");
  }
  const spin = (sim.running && !crash ? 60 : 6) * dt;
  drone.userData.props.forEach((p, i) => { p.rotation.y += i % 2 ? spin : -spin; p.userData.disc.material.opacity = sim.running && !crash ? 0.14 : 0; });
  const blinkOn = Math.floor(now / (sim.state === "hold" ? 160 : 700)) % 2 === 0;
  drone.userData.leds.forEach((l) => (l.visible = blinkOn));
  beacons.forEach((b) => (b.visible = Math.floor(now / 900) % 2 === 0));
  navGlow.color.setHex(sim.state === "hold" || sim.state === "stop" ? COL.red : sim.state === "fix" ? COL.amber : COL.lime);
  ghost.visible = sim.running && !crash && sim.scanT === 0;
  ghost.position.copy(sim.p).addScaledVector(sim.vAI, 0.9); ghost.rotation.copy(drone.rotation);
  ghost.userData.props.forEach((p) => (p.rotation.y += spin));
  const blocked = sim.state === "fix" || sim.state === "stop";
  ghost.traverse((o) => { if (o.isMesh) o.material.color.setHex(blocked ? COL.red : 0xffffff); });
  // nearest structure
  const {d, n} = sdfGrad(sim.p), near = sim.p.clone().addScaledVector(n, -Math.max(d, 0)), show = d < 8 && !crash;
  beam.visible = hitDot.visible = show;
  if (show) { beamGeo.attributes.position.setXYZ(0, sim.p.x, sim.p.y, sim.p.z); beamGeo.attributes.position.setXYZ(1, near.x, near.y, near.z); beamGeo.attributes.position.needsUpdate = true; hitDot.position.copy(near); }
  beam.material.color.setHex(d < SAFE ? COL.red : d < SAFE * 2 ? COL.amber : COL.lime); hitDot.material.color.copy(beam.material.color);
  bubble.position.copy(sim.p); bubble.visible = gardaActive() && !crash;
  bubble.material.color.setHex(sim.scanT > 0 ? COL.lime : d < SAFE * 1.4 ? COL.red : COL.lime);
  bubble.material.opacity = THREE.MathUtils.clamp(0.24 - d * 0.03, 0.04, 0.22) * (0.75 + 0.25 * Math.sin(now / 110)); bubble.rotation.y += dt * 0.6;
  // inspection: gimbal scan cone + target rings
  const tg = target(), scanning = sim.scanT > 0 && !crash;
  scanCone.visible = scanning;
  if (scanning) {
    const gim = sim.p.clone().add(new THREE.Vector3(0, -0.3, 0)), dir = tg.clone().sub(gim), len = dir.length();
    scanCone.position.copy(gim); scanCone.quaternion.setFromUnitVectors(UP, dir.normalize());
    scanCone.scale.set(len * 0.45, len, len * 0.45);
    scanCone.material.opacity = 0.22 + 0.1 * Math.sin(now / 90);
  }
  scanLight.position.copy(tg); scanLight.intensity = sim.flashT > 0 ? 60 * sim.flashT / 0.25 : 0;
  rings.forEach((r, i) => {
    const st = sim.status[i], active = i === sim.task && sim.running && !crash;
    r.position.copy(TASKS[i].p); r.lookAt(camera.position);
    r.material.color.setHex(st === "done" ? COL.lime : st === "fail" ? COL.red : st === "skip" ? 0x9fa9e8 : COL.amber);
    r.material.opacity = active ? 0.55 + 0.4 * Math.sin(now / 160) : st === "done" ? 0.7 : st === "todo" ? 0.18 : 0.45;
    r.scale.setScalar(active ? 1 + 0.15 * Math.sin(now / 160) + (scanning ? 0.4 : 0) : 0.8);
  });
  rays.visible = !crash;
  if (++tick % 3 === 0 && !crash) {
    for (let i = 0; i < RAYS; i++) {
      const a = (i / RAYS) * Math.PI * 2 + now / 3000, el = (i % 4 - 1.5) * 0.18;
      const dr = new THREE.Vector3(Math.cos(a) * Math.cos(el), Math.sin(el), Math.sin(a) * Math.cos(el)), q = new THREE.Vector3();
      let t = 0.6; for (let k = 0; k < 30 && t < 9; k++) { q.copy(sim.p).addScaledVector(dr, t); const s = sdf(q); if (s < 0.12) break; t += Math.max(0.25, s * 0.9); }
      rayPos.set([sim.p.x, sim.p.y, sim.p.z, sim.p.x + dr.x * t, sim.p.y + dr.y * t, sim.p.z + dr.z * t], i * 6);
    }
    rayGeo.attributes.position.needsUpdate = true;
  }
  if (sim.running && !crash && tick % 2 === 0) {
    trailPos.copyWithin(0, 3); trailPos.set([sim.p.x, sim.p.y, sim.p.z], (TRAIL - 1) * 3); sim.trailN = Math.min(TRAIL, sim.trailN + 1);
    trailGeo.setDrawRange(TRAIL - sim.trailN, sim.trailN); trailGeo.attributes.position.needsUpdate = true;
  }
  sun.position.set(sim.p.x - 90, 70, sim.p.z - 130); sun.target.position.copy(sim.p);
  let focus = sim.p;                                       // crash: frame the contact point, then the falling debris
  if (crash && debris.length) { focus = new THREE.Vector3(); debris.forEach((d) => focus.add(d.mesh.position)); focus.divideScalar(debris.length); focus.y += 1; }
  if (sim.cam === 0) {
    camLook.lerp(focus, Math.min(1, dt * 4));
    const yaw = sim.yaw + Math.PI + camState.yaw * 0.8, dd = camState.dist * (crash ? 1.25 : 1);
    camPos.set(focus.x + Math.cos(yaw) * dd * Math.cos(camState.pitch), focus.y + dd * Math.sin(camState.pitch) + 1, focus.z - Math.sin(yaw) * dd * Math.cos(camState.pitch));
    camPos.y = Math.max(camPos.y, terrainH(camPos.x, camPos.z) + 1.2);
    camera.position.lerp(camPos, Math.min(1, dt * 2.2)); camera.lookAt(camLook);
  } else if (sim.cam === 1) {
    const a = now / 14000 + camState.yaw;
    camera.position.lerp(new THREE.Vector3(Math.cos(a) * 58, 30 + camState.pitch * 30, Math.sin(a) * 58), Math.min(1, dt * 1.5));
    camLook.lerp(new THREE.Vector3(focus.x * 0.5, 22, focus.z * 0.5), Math.min(1, dt * 2)); camera.lookAt(camLook);
  } else {
    const f = new THREE.Vector3(Math.cos(sim.yaw), -0.08, -Math.sin(sim.yaw));
    camera.position.copy(sim.p).addScaledVector(f, 0.8).add(new THREE.Vector3(0, -0.25, 0)); camera.lookAt(sim.p.clone().addScaledVector(f, 10));
  }
}

// ------------------------------------------------------------------ HUD
function chip(el, cls, txt) { el.className = "chip " + cls; el.querySelector("span").textContent = txt; }
function node(id, cls, b) { const n = $(id); n.className = "node " + cls; if (b !== undefined) n.querySelector("b").textContent = b; }
function hud() {
  const active = gardaActive();
  if (hw.fpgaOk) chip($("#chipFpga"), sim.holdReason ? "bad" : "on", sim.holdReason ? "FPGA: E-STOP AKTIF" : "FPGA GARDA TERHUBUNG");
  else if (hw.seqRunning) chip($("#chipFpga"), "warn", "MEMPROGRAM FPGA…");
  else chip($("#chipFpga"), "off", !hw.checked ? "MEMERIKSA FPGA…" : hw.bridge ? "FPGA TIDAK TERHUBUNG" : "BRIDGE OFFLINE");
  chip($("#chipGarda"), active ? (sim.simMode && !hw.fpgaOk ? "warn" : "on") : "off",
       active ? (sim.simMode && !hw.fpgaOk ? "REFLEKS GARDA: SIMULASI" : "REFLEKS GARDA AKTIF") : "REFLEKS GARDA NONAKTIF");
  const T = TASKS[Math.min(sim.task, TASKS.length - 1)], home = sim.task >= TASKS.length;
  const B = $("#banner"), set = (cls, t, s) => { B.className = "hud banner " + cls; $("#bannerTxt").textContent = t; $("#bannerSub").textContent = s; };
  if (sim.state === "crash" && sim.crashKind === "shock") set("crash", sim.crashT < 1 ? "⚡ KESETRUM 500 kV!" : "DRONE HANCUR", "Tanpa GARDA, AI mendekati kabel bertegangan untuk difoto dan menyentuhnya");
  else if (sim.state === "crash") set("crash", "TABRAKAN!", "Tanpa GARDA, AI menabrak menara saat mengejar foto close-up");
  else if (!sim.running) set("idle", "SIAP", active ? "Tekan MULAI MISI inspeksi" : "Hubungkan atau program FPGA untuk mengaktifkan refleks GARDA");
  else if (sim.state === "hold") set("stop", "E-STOP · DRONE DITAHAN", `Dari board: ${sim.holdReason}`);
  else if (sim.scanT > 0) set("safe", "📷 MEMOTRET " + T.name.toUpperCase(), active ? `${T.sub} · ${Math.max(0, sim.d).toFixed(2)} m dari struktur` : T.sub);
  else if (sim.state === "stop") set("stop", "HENTI 1 CLOCK", "Ragu? GARDA menghentikan gerak lalu mundur");
  else if (sim.state === "fix") set("fix", "GARDA MENGOREKSI", "AI ingin lebih dekat untuk foto: gerak dipotong tepat di batas 1,2 m");
  else if (home) set(active ? "safe" : "idle", "KEMBALI KE TITIK AWAL", `Putaran ${sim.round}: ${sim.status.filter((s) => s === "done").length}/${TASKS.length} komponen terdokumentasi`);
  else if (!active) set("idle", "AI TERBANG SENDIRI", `Menuju ${T.name.toLowerCase()} tanpa ada yang menjaga jarak`);
  else set("safe", "MENUJU " + T.name.toUpperCase(), `${T.sub} · GARDA menjaga jarak ≥ 1,2 m`);
  const live = sim.running && sim.state !== "crash";
  node("#nSensor", live ? "on" : ""); node("#nAI", live ? "on" : "");
  if (!active) node("#nGate", "dead", "Tidak aktif");
  else node("#nGate", sim.state === "fix" ? "fix" : sim.state === "stop" || sim.state === "hold" ? "stop" : live ? "on" : "",
            sim.state === "fix" ? "Mengoreksi" : sim.state === "stop" ? "Menghentikan" : sim.state === "hold" ? "E-STOP" : "Meloloskan");
  $("#gateSub").textContent = hw.fpgaOk ? "FPGA GARDA" : sim.simMode ? "simulasi" : "butuh FPGA";
  node("#nMotor", sim.state === "crash" || sim.state === "hold" ? "stop" : live ? (active ? "on" : "fix") : "",
       sim.state === "crash" ? "Jatuh" : sim.state === "hold" ? "Hover" : sim.scanT > 0 ? "Hover · foto" : live ? (active ? "Gerak aman" : "Tanpa pengaman") : "Siaga");
  $("#l1").className = "link" + (live ? " live" : ""); $("#l2").className = "link" + (live ? " live" : "");
  $("#l3").className = "link" + (live && active && sim.state !== "hold" ? " live" : live && !active ? " cut" : "");
  $("#distBar").style.width = `${THREE.MathUtils.clamp(sim.d / 5, 0, 1) * 100}%`;
  $("#distVal").textContent = sim.state === "crash" ? "—" : `${Math.max(0, sim.d).toFixed(2)} m`;
  $("#statFix").textContent = sim.fixes; $("#statPhoto").textContent = sim.photos; $("#statCrash").textContent = sim.crashes; $("#statShock").textContent = sim.shocks;
  $("#taskRound").textContent = `putaran ${sim.round}`;
  $("#tasks").innerHTML = TASKS.map((t, i) => {
    const s = sim.status[i], cur = i === sim.task && sim.running && s === "todo";
    const icon = s === "done" ? "✓" : s === "fail" ? "✕" : s === "skip" ? "–" : cur ? "◉" : "○";
    return `<li class="${cur ? "cur" : s}"><i>${icon}</i><span><b>${t.name}</b><small>${t.sub}</small></span></li>`;
  }).join("");
  $("#btnRun").textContent = sim.running ? "❚❚ JEDA MISI" : "▶ MULAI MISI";
  $("#btnWind").classList.toggle("on", sim.strongWind); $("#btnSim").classList.toggle("on", sim.simMode);
  $("#btnCam").textContent = ["🎥 KAMERA: IKUT", "🎥 KAMERA: ORBIT", "🎥 KAMERA: FPV"][sim.cam];
}

// ------------------------------------------------------------------ loop
let last = performance.now(), hudT = 0;
function frame(now) {
  const dt = Math.min(0.05, (now - last) / 1000); last = now;
  step(dt); visuals(dt, now);
  if ((hudT += dt) > 0.08) { hudT = 0; hud(); }
  renderer.render(scene, camera);
  requestAnimationFrame(frame);
}
camera.position.set(-34, 24, -44); camLook.copy(sim.p);
hud(); requestAnimationFrame(frame);

// ------------------------------------------------------------------ controls
function toast(t, cls = "") { const e = $("#toast"); e.textContent = t; e.className = "toast on " + cls; clearTimeout(e._t); e._t = setTimeout(() => (e.className = "toast"), 3500); }
$("#btnRun").onclick = () => { sim.running = !sim.running; if (sim.running && sim.state === "idle") sim.state = "safe"; };
$("#btnWind").onclick = () => { sim.strongWind = !sim.strongWind; toast(sim.strongWind ? "Angin kencang: hembusan mendorong drone ke arah SUTET" : "Angin normal"); };
$("#btnCam").onclick = () => { sim.cam = (sim.cam + 1) % 3; };
$("#btnSim").onclick = () => { sim.simMode = !sim.simMode; toast(sim.simMode ? "SIMULASI: refleks GARDA berjalan tanpa FPGA (hanya untuk latihan)" : "Mode simulasi mati: refleks butuh FPGA", sim.simMode ? "" : "ok"); };
addEventListener("keydown", async (e) => {
  if (e.target.closest("dialog")) return;
  if (e.code === "Space") { e.preventDefault(); $("#btnRun").click(); }
  if (e.key === "e" || e.key === "E") { const r = await api("/api/command", {name: "estop"}); toast(r.ok ? "E-stop host dikirim ke FPGA" : "E-stop tidak terkirim: tekan KEY1 di board", r.ok ? "ok" : "err"); }
  if (e.key === "r" || e.key === "R") { await api("/api/command", {name: "safe_reset"}); toast("Safe reset dikirim ke FPGA", "ok"); }
});
let scannedOk = false;
$("#btnProgram").onclick = async () => {
  const dlg = $("#dlg"); scannedOk = false; $("#dlgGo").disabled = true; $("#dlgMsg").textContent = "";
  $("#dlgTarget").className = "target"; $("#dlgTarget").textContent = "Memindai JTAG…"; dlg.showModal();
  try {
    const r = await api("/api/scan-jtag", {}), c = (r.jtag && r.jtag.cables) || [];
    scannedOk = c.length === 1 && c[0].devices.length === 1 && c[0].devices[0].idcode === "031050DD";
    $("#dlgTarget").textContent = scannedOk ? `✓ ${c[0].name}\n  ${c[0].devices[0].name} (DE10-Lite MAX 10)` : (r.jtag ? r.jtag.raw || r.jtag.state : r.error) + "\nProgram hanya diizinkan untuk tepat satu chip 10M50DA.";
    $("#dlgTarget").className = "target " + (scannedOk ? "ok" : "bad"); $("#dlgGo").disabled = !scannedOk;
  } catch { $("#dlgTarget").textContent = "Bridge offline: jalankan shortcut GARDA."; $("#dlgTarget").className = "target bad"; }
};
$("#dlg").addEventListener("close", async () => {
  if ($("#dlg").returnValue !== "go" || !scannedOk) return;
  const r = await api("/api/run", {sequence: "program", confirm_idcode: "031050DD"});
  if (!r.ok) return toast(r.error || "Program gagal dimulai", "err");
  toast("Memprogram FPGA…");
  const t0 = Date.now();
  const iv = setInterval(async () => {
    const s = (await api("/api/state")).sequence;
    if (s.running && Date.now() - t0 < 120000) return;
    clearInterval(iv);
    toast(s.result === "PASS" ? "FPGA terprogram: GARDA aktif di board (HEX menampilkan GArdA)" : "Program gagal: " + ((s.steps || []).find((x) => x.status === "fail") || {}).detail, s.result === "PASS" ? "ok" : "err");
  }, 800);
});

// URL options: ?sim=1 (labelled no-FPGA simulation), ?autostart=1, ?wind=1, ?cam=0|1|2, ?t=SECONDS (fast-forward)
const q = new URLSearchParams(location.search);
if (q.get("sim")) sim.simMode = true;
if (q.get("wind")) sim.strongWind = true;
if (q.get("cam")) sim.cam = +q.get("cam") % 3;
if (q.get("autostart")) { sim.running = true; sim.state = "safe"; }
if (q.get("t")) {
  const n = Math.min(4000, Math.round(+q.get("t") / 0.033));
  for (let i = 0; i < n; i++) { step(0.033); visuals(0.033, i * 33); }
  hud();
}
