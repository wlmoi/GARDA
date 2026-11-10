import * as THREE from './vendor/three.module.min.js';

// The package and board are explanatory models. RTL placement is deliberately
// independent of the FPGA fitter and of an ASIC place-and-route result.
const BG = '#0D1535';
const INK = '#F7F9FF';
const PALETTE = {
  control: '#315CFF', dwa: '#5B7FFF', memory: '#7C97FF', gate: '#B7FF35',
  neural: '#3B64FF', uart: '#7C97FF', tt: '#315CFF', default: '#5B7FFF',
};

const clamp = (n, min, max) => Math.max(min, Math.min(max, n));

function roundedShape(w, h, r = 3) {
  const s = new THREE.Shape();
  s.moveTo(-w / 2 + r, -h / 2);
  s.lineTo(w / 2 - r, -h / 2);
  s.quadraticCurveTo(w / 2, -h / 2, w / 2, -h / 2 + r);
  s.lineTo(w / 2, h / 2 - r);
  s.quadraticCurveTo(w / 2, h / 2, w / 2 - r, h / 2);
  s.lineTo(-w / 2 + r, h / 2);
  s.quadraticCurveTo(-w / 2, h / 2, -w / 2, h / 2 - r);
  s.lineTo(-w / 2, -h / 2 + r);
  s.quadraticCurveTo(-w / 2, -h / 2, -w / 2 + r, -h / 2);
  return s;
}

function wrapText(ctx, text, width, maxLines = 3) {
  const words = String(text).replace(/_/g, ' ').split(/\s+/);
  const lines = [];
  let line = '';
  words.forEach(word => {
    const next = line ? `${line} ${word}` : word;
    if (line && ctx.measureText(next).width > width) {
      lines.push(line);
      line = word;
    } else line = next;
  });
  if (line) lines.push(line);
  if (lines.length <= maxLines) return lines;
  const result = lines.slice(0, maxLines);
  result[maxLines - 1] = result[maxLines - 1].replace(/\s+\S*$/, '') + '…';
  return result;
}

function textureLabel(lines, { color = INK, size = 52, width = 1024,
  height = 256, background = null, align = 'center', mono = false } = {}) {
  const c = document.createElement('canvas');
  c.width = width;
  c.height = height;
  const ctx = c.getContext('2d');
  if (background) {
    ctx.fillStyle = background;
    ctx.fillRect(0, 0, width, height);
  }
  ctx.fillStyle = color;
  ctx.textAlign = align;
  ctx.textBaseline = 'middle';
  ctx.font = `600 ${size}px ${mono ? 'monospace' : 'Arial, sans-serif'}`;
  const all = Array.isArray(lines) ? lines : [lines];
  const leading = size * 1.25;
  all.forEach((line, i) => ctx.fillText(line,
    align === 'left' ? 32 : width / 2,
    height / 2 + (i - (all.length - 1) / 2) * leading, width - 48));
  const tex = new THREE.CanvasTexture(c);
  tex.colorSpace = THREE.SRGBColorSpace;
  tex.anisotropy = 4;
  return tex;
}

function disposeTree(root) {
  const geometries = new Set();
  const materials = new Set();
  const textures = new Set();
  root.traverse(obj => {
    if (obj.geometry) geometries.add(obj.geometry);
    const mats = Array.isArray(obj.material) ? obj.material : [obj.material];
    mats.filter(Boolean).forEach(mat => {
      materials.add(mat);
      Object.values(mat).forEach(value => {
        if (value && value.isTexture) textures.add(value);
      });
    });
  });
  geometries.forEach(x => x.dispose());
  materials.forEach(x => x.dispose());
  textures.forEach(x => x.dispose());
}

export class GardaScene {
  constructor(canvas, { onSelect = () => {}, onModeChange = () => {} } = {}) {
    this.canvas = canvas;
    this.onSelect = onSelect;
    this.onModeChange = onModeChange;
    this._mode = 'board';
    this._selected = null;
    this._exploded = false;
    this._autoRotate = false;
    this._disposed = false;
    this._blocks = [];
    this._pickables = [];
    this._blockMeshes = [];
    this._pointers = new Map();
    this._moving = false;
    this._lastInteraction = performance.now();
    this._orbit = { az: -.46, el: .83, radius: 165 };
    this._orbitGoal = { ...this._orbit };
    this._target = new THREE.Vector3(0, 4, 0);

    this.renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: false, powerPreference: 'high-performance' });
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    this.renderer.setClearColor(BG);
    this.renderer.outputColorSpace = THREE.SRGBColorSpace;
    this.renderer.toneMapping = THREE.ACESFilmicToneMapping;
    this.renderer.toneMappingExposure = 1.18;
    this.renderer.shadowMap.enabled = true;
    this.renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    this.scene = new THREE.Scene();
    this.scene.background = new THREE.Color(BG);
    this.camera = new THREE.PerspectiveCamera(38, 1, .1, 1200);
    this.raycaster = new THREE.Raycaster();
    this.pointer = new THREE.Vector2();

    const hemi = new THREE.HemisphereLight(0xffffff, 0x8ca6b9, 2.7);
    this.scene.add(hemi);
    const key = new THREE.DirectionalLight(0xffffff, 3.3);
    key.position.set(-60, 150, 80);
    key.castShadow = true;
    key.shadow.mapSize.set(2048, 2048);
    Object.assign(key.shadow.camera, { left: -120, right: 120, top: 110, bottom: -110, near: 10, far: 400 });
    key.shadow.normalBias = .18;
    key.shadow.bias = -.0002;
    key.shadow.radius = 5;
    this.scene.add(key);
    const rim = new THREE.DirectionalLight(0xc8e6ff, 1.8);
    rim.position.set(110, 45, -80);
    this.scene.add(rim);

    const ground = new THREE.Mesh(new THREE.PlaneGeometry(1200, 1200),
      new THREE.ShadowMaterial({ opacity: .14 }));
    ground.rotation.x = -Math.PI / 2;
    ground.position.y = -3;
    ground.receiveShadow = true;
    this.scene.add(ground);

    this.board = new THREE.Group();
    this.die = new THREE.Group();
    this.tt = new THREE.Group();
    this.scene.add(this.board, this.die, this.tt);
    this._buildBoard();
    this._rebuildLogic();
    this.die.visible = false;
    this.tt.visible = false;
    this._bindControls();
    this._resizeObserver = new ResizeObserver(() => this._resize());
    this._resizeObserver.observe(canvas.parentElement || canvas);
    this._resize();
    this._tick = this._tick.bind(this);
    this._raf = requestAnimationFrame(this._tick);
  }

  _mat(color, metalness = 0, roughness = .55) {
    return new THREE.MeshStandardMaterial({ color, metalness, roughness });
  }

  _box(parent, x, y, z, w, h, d, color, { metal = 0, roughness = .55, pick = null } = {}) {
    const mesh = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), this._mat(color, metal, roughness));
    mesh.position.set(x, y, z);
    mesh.castShadow = true;
    mesh.receiveShadow = true;
    parent.add(mesh);
    if (pick) {
      mesh.userData.selectId = pick;
      this._pickables.push(mesh);
    }
    return mesh;
  }

  _flatLabel(parent, text, x, y, z, w, d, opts = {}) {
    const tex = textureLabel(text, opts);
    const mesh = new THREE.Mesh(new THREE.PlaneGeometry(w, d),
      new THREE.MeshBasicMaterial({ map: tex, transparent: true, depthWrite: false, toneMapped: false, side: THREE.DoubleSide }));
    mesh.rotation.x = -Math.PI / 2;
    mesh.position.set(x, y, z);
    mesh.renderOrder = 2;
    parent.add(mesh);
    return mesh;
  }

  _silk(parent, text, x, z, w, d = 3, y = 1.66, opts = {}) {
    return this._flatLabel(parent, text, x, y, z, w, d,
      { color: '#e4eff3', size: 55, ...opts });
  }

  _buildBoard() {
    const root = this.board;
    const boardShape = roundedShape(110, 80, 4);
    const holes = [[-49, -34], [49, -34], [-49, 34], [49, 34]];
    holes.forEach(([x, z]) => {
      const hole = new THREE.Path();
      hole.absarc(x, -z, 2, 0, Math.PI * 2, true);
      boardShape.holes.push(hole);
    });
    const geom = new THREE.ExtrudeGeometry(boardShape, { depth: 1.6, bevelEnabled: false, curveSegments: 10 });
    geom.rotateX(-Math.PI / 2);
    const pcb = new THREE.Mesh(geom, this._mat('#185d8c', .16, .48));
    pcb.castShadow = true;
    pcb.receiveShadow = true;
    root.add(pcb);

    const gold = this._mat('#d9b567', .76, .27);
    holes.forEach(([x, z]) => {
      const ring = new THREE.Mesh(new THREE.RingGeometry(2, 3.1, 40), gold);
      ring.rotation.x = -Math.PI / 2;
      ring.position.set(x, 1.64, z);
      root.add(ring);
      const inner = new THREE.Mesh(new THREE.CylinderGeometry(2, 2, 1.5, 24, 1, true), gold);
      inner.position.set(x, .83, z);
      root.add(inner);
    });

    // Fine copper routes are an illustrative board texture, not a PCB netlist.
    const routeMaterial = new THREE.LineBasicMaterial({ color: '#8ab5cc', transparent: true, opacity: .25 });
    const routePts = [];
    for (let i = 0; i < 18; i++) {
      const p = -12 + i * 1.15;
      routePts.push(new THREE.Vector3(p, 1.63, -14), new THREE.Vector3(p, 1.63, -19 - (i % 4)),
        new THREE.Vector3(p, 1.63, -19 - (i % 4)), new THREE.Vector3(p + 13, 1.63, -23 - (i % 4)),
        new THREE.Vector3(p + 13, 1.63, -23 - (i % 4)), new THREE.Vector3(p + 13, 1.63, -28));
      routePts.push(new THREE.Vector3(-15, 1.63, p), new THREE.Vector3(-23, 1.63, p),
        new THREE.Vector3(-23, 1.63, p), new THREE.Vector3(-28, 1.63, p + 5));
    }
    root.add(new THREE.LineSegments(new THREE.BufferGeometry().setFromPoints(routePts), routeMaterial));

    // Cyclone V SoC. The ARM HPS is inside this package, not a separate chip.
    this._box(root, -7, 2.2, 0, 31.5, 1.2, 31.5, '#b7b2a2', { metal: .65 });
    this.fpga = this._box(root, -7, 4.05, 0, 29.2, 2.7, 29.2, '#303842', { roughness: .42, pick: '_fpga' });
    this._flatLabel(root, ['ALTERA', 'CYCLONE V', 'SoC'], -7, 5.42, -1.7, 22, 10,
      { color: '#c7cdd2', size: 53, height: 320 });
    this._flatLabel(root, ['10M50DAF484C7G', 'GARDA   |   FPGA MAX 10'], -7, 5.43, 7, 23, 5,
      { color: '#b4c3ce', size: 43, height: 200, mono: true });
    const pinMarker = new THREE.Mesh(new THREE.CircleGeometry(.72, 20), this._mat('#c7cdd2', .3));
    pinMarker.rotation.x = -Math.PI / 2;
    pinMarker.position.set(-19.2, 5.43, -12.2);
    root.add(pinMarker);

    const header = (x, z, count = 20, axis = 'x') => {
      const group = new THREE.Group();
      group.position.set(x, 0, z);
      if (axis === 'z') group.rotation.y = Math.PI / 2;
      root.add(group);
      const length = count * 2.54 + 2;
      this._box(group, 0, 5.4, 0, length, 7.5, 6.1, '#172126', { roughness: .7 });
      const socketMat = this._mat('#050b0e', 0, .8);
      const socketGeo = new THREE.BoxGeometry(1.48, .2, 1.48);
      const socket = new THREE.InstancedMesh(socketGeo, socketMat, count * 2);
      const pins = new THREE.InstancedMesh(new THREE.BoxGeometry(.53, 2.3, .53), gold, count * 2);
      const m = new THREE.Matrix4();
      let n = 0;
      for (let i = 0; i < count; i++) for (const side of [-1, 1]) {
        const px = (i - (count - 1) / 2) * 2.54;
        m.makeTranslation(px, 9.19, side * 1.27);
        socket.setMatrixAt(n, m);
        m.makeTranslation(px, 1.8, side * 1.27);
        pins.setMatrixAt(n++, m);
      }
      socket.castShadow = true;
      pins.castShadow = true;
      group.add(socket, pins);
    };
    header(-9, -31, 20);
    header(-9, 31, 20);
    header(25.5, 25, 8);
    header(29, -26, 5, 'z');
    this._silk(root, 'GPIO 0   |   40 PIN', -10, -25.7, 48, 2.6);
    this._silk(root, 'GPIO 1   |   40 PIN', -10, 25.7, 48, 2.6);

    // Ethernet shield can, black socket mouth and eight gold contacts.
    const rj = new THREE.Group();
    rj.position.set(43, 0, -2);
    root.add(rj);
    this._box(rj, 0, 9.5, 0, 22, 15.8, 18, '#b5c0c5', { metal: .9, roughness: .28 });
    this._box(rj, 11.1, 9, 0, .35, 10.5, 13.1, '#172127', { roughness: .8 });
    this._box(rj, 11.33, 6.2, 0, .18, 3.6, 8.2, '#050b0e');
    for (let i = 0; i < 8; i++) this._box(rj, 11.4, 11, (i - 3.5) * 1.12, .2, 3, .35, '#d8b26a', { metal: .8 });
    [-1, 1].forEach(side => this._box(rj, 11.39, 14.9, side * 6.1, .2, 1.4, 1.9, side === -1 ? '#74c959' : '#d3a33c'));
    this._silk(root, 'ETHERNET', 43, 12.1, 19, 2.2);

    const usbA = (x, z) => {
      this._box(root, x, 5.55, z, 16, 7.9, 13, '#b5bdc2', { metal: .9, roughness: .27 });
      this._box(root, x + 8.1, 5.6, z, .2, 5.4, 10.8, '#18212a');
      this._box(root, x + 8.3, 4.3, z, .2, 1.8, 9, '#bfc4c8', { metal: .4 });
      for (let i = 0; i < 4; i++) this._box(root, x + 8.46, 5.23, z + (i - 1.5) * 1.9, .12, .5, .7, '#d6b36c', { metal: .8 });
    };
    usbA(47, -22);
    this._silk(root, 'USB HOST', 42, -12.8, 18, 2.3);

    const microUSB = (x, z, rotation = 0) => {
      const group = new THREE.Group();
      group.position.set(x, 0, z);
      group.rotation.y = rotation;
      root.add(group);
      this._box(group, 0, 3.4, 0, 9, 3.7, 7.2, '#bdc8ce', { metal: .9, roughness: .23 });
      this._box(group, 4.58, 3.35, 0, .16, 2.1, 5.5, '#18212a');
      this._box(group, 4.69, 2.9, 0, .15, .55, 4.2, '#999f9f', { metal: .4 });
    };
    microUSB(49.5, -34);
    microUSB(-48.7, 29.3, Math.PI);
    this._silk(root, 'USB-BLASTER II', -37, 35.9, 24, 2.3);

    // HDMI on the FPGA side and its support IC.
    this._box(root, -48.3, 4.7, 8, 13.6, 6.2, 15.2, '#c0c8cc', { metal: .88, roughness: .28 });
    this._box(root, -55.2, 4.8, 8, .2, 3.8, 11.2, '#252a30');
    this._box(root, -55.35, 4.6, 8, .2, 1.4, 8.8, '#cab77d', { metal: .7 });
    this._silk(root, 'HDMI TX', -41, -1.8, 18, 2.4);
    this._ic(root, -32, 7, 12.5, 12.5, 'HDMI');
    this._ic(root, -36, 24, 13.2, 13.2, 'BLASTER');
    this._ic(root, 16.2, -15, 15, 10.8, 'DDR3');
    this._ic(root, 15.5, 4.4, 12, 9.7, 'DDR3');
    this._ic(root, -32, -16.3, 7, 6.5, 'FLASH');
    this._ic(root, 30, 14.5, 7.5, 7.5, 'PMIC');

    // Cylindrical 5 V barrel socket, with an actual hollow opening.
    this._box(root, -47, 4.8, -22, 13.6, 6.4, 10.5, '#1b2429');
    const barrel = new THREE.Mesh(new THREE.CylinderGeometry(5.3, 5.3, 13.7, 32, 1, true), this._mat('#171f24', .1, .42));
    barrel.rotation.z = Math.PI / 2;
    barrel.position.set(-48.5, 6.6, -22);
    barrel.castShadow = true;
    root.add(barrel);
    const mouth = new THREE.Mesh(new THREE.RingGeometry(3.4, 5.3, 32), this._mat('#161e22'));
    mouth.rotation.y = -Math.PI / 2;
    mouth.position.set(-55.4, 6.6, -22);
    root.add(mouth);
    const jackPin = new THREE.Mesh(new THREE.CylinderGeometry(.8, .8, 4.5, 12), gold);
    jackPin.rotation.z = Math.PI / 2;
    jackPin.position.set(-52.3, 6.6, -22);
    root.add(jackPin);
    this._silk(root, 'DC 5 V', -44, -31, 13, 2.5);

    // Surface-mount passives, a crystal, switches and user LEDs.
    const passives = [
      [-27, -25], [-31, -25], [-35, -25], [-25, -20], [-24, -15], [-24, -10],
      [12, 14], [17, 15], [22, 15], [19, -6], [23, -7], [32, -11],
      [-31, 18], [-26, 19], [-26, 22], [-30, 32], [34, 31], [35, 26],
    ];
    passives.forEach(([x, z], i) => {
      this._box(root, x, 2.2, z, i % 3 ? 2.4 : 3.2, 1.1, 1.4, i % 2 ? '#c8b28d' : '#36434b', { metal: .1 });
      [-1, 1].forEach(side => this._box(root, x + side * (i % 3 ? .95 : 1.35), 2.24, z, .45, 1.18, 1.44, '#bec5c8', { metal: .9 }));
    });
    this._box(root, -29, 2.8, -7, 5, 2.4, 3.1, '#cbd2d1', { metal: .85 });
    this._box(root, -39, 3.2, -7.3, 8, 3.2, 7.6, '#d2d4d2', { metal: .4 });
    for (let i = 0; i < 4; i++) this._box(root, -41.5 + i * 1.7, 5.05, -7.3, .8, .6, 3.8, '#f2f0dc');
    this._silk(root, 'MSEL', -39, -12.6, 10, 2);
    [-1, 1].forEach((side, i) => {
      const x = 35.6 + i * 6.7;
      this._box(root, x, 2.5, 22, 5.3, 1.8, 5.3, '#aeb6b8', { metal: .5 });
      const button = new THREE.Mesh(new THREE.CylinderGeometry(1.65, 1.65, 1.4, 20), this._mat('#eceee7'));
      button.position.set(x, 4.1, 22);
      button.castShadow = true;
      root.add(button);
      this._silk(root, `KEY${i}`, x, 17.5, 6, 1.9);
    });
    this._leds = [];
    for (let i = 0; i < 8; i++) {
      const led = this._box(root, 28 + i * 2.5, 2.2, 33, 1.6, 1.1, 2.5, i < 2 ? '#76d892' : '#72927e');
      led.material.emissive.set(i < 2 ? '#2eab67' : '#000000');
      led.material.emissiveIntensity = .35;
      this._leds.push(led);
    }
    this._silk(root, 'LED 0 1 2 3 4 5 6 7', 37, 29, 25, 2.1);
    this._silk(root, 'DE10-Lite', -6, 19, 38, 5.5, 1.67, { size: 66 });
    this._silk(root, 'TERASIC    |    iSeeDesignITB', -5, 23, 38, 2.2, 1.67, { size: 39 });
    this._silk(root, 'CYCLONE V SE', 8, -37.1, 25, 2.2);
  }

  _ic(parent, x, z, w, d, name) {
    this._box(parent, x, 2.9, z, w, 2.6, d, '#303c44', { roughness: .55 });
    const pins = Math.max(3, Math.floor(w / 1.4));
    for (let i = 0; i < pins; i++) {
      const xx = x - w / 2 + .8 + (w - 1.6) * i / (pins - 1);
      [-1, 1].forEach(side => this._box(parent, xx, 2.15, z + side * (d / 2 + .55), .55, .5, 1.25, '#a3b0b6', { metal: .7 }));
    }
    this._flatLabel(parent, name, x, 4.24, z, w * .85, d * .45,
      { color: '#a5b1b6', size: 44, height: 160 });
  }

  _rebuildLogic() {
    for (const root of [this.die, this.tt]) {
      disposeTree(root);
      root.clear();
    }
    this._pickables = this._pickables.filter(m => m.parent && this._isWithin(m, this.board));
    this._blockMeshes = [];
    const blocks = this._blocks;
    const isTT = b => b.group === 'tt' || /^tt[_-]/.test(b.name || b.module || b.id || '');
    let dieBlocks = blocks.filter(b => !isTT(b));
    if (!dieBlocks.length) dieBlocks = blocks;
    let ttBlocks = blocks.filter(isTT);
    if (!ttBlocks.length) ttBlocks = blocks.filter(b => b.group === 'neural' || /neural|mac|requant|rom|tt_um/i.test(`${b.id} ${b.name}`));
    if (!ttBlocks.length) ttBlocks = blocks.slice(0, 8);
    this._buildFloorplan(this.die, dieBlocks, false);
    this._buildFloorplan(this.tt, ttBlocks, true);
    this._applySelection();
    this._applyExplosion();
  }

  _isWithin(obj, root) {
    while (obj) {
      if (obj === root) return true;
      obj = obj.parent;
    }
    return false;
  }

  _buildFloorplan(root, blocks, tiny) {
    // A 3D explanatory package: this must never be mistaken for physical GDS.
    this._box(root, 0, 1.4, 0, 106, 3.1, 78, tiny ? '#e1e6eb' : '#dce5ec', { metal: .27, roughness: .48 });
    this._box(root, 0, 3.4, 0, 97, 1.4, 69, '#284b65', { metal: .44, roughness: .39 });
    this._box(root, 0, 4.3, 0, 92, .65, 64, tiny ? '#d8edf5' : '#d5e7f0', { metal: .23, roughness: .52 });

    // Peripheral bond pads emphasize the concept-package boundary.
    const padMat = this._mat('#c8ac69', .72, .3);
    const padGeo = new THREE.BoxGeometry(1.7, .35, 2.9);
    const padCount = 27;
    const pads = new THREE.InstancedMesh(padGeo, padMat, padCount * 4);
    const mat = new THREE.Matrix4();
    for (let i = 0; i < padCount; i++) {
      const x = (i - (padCount - 1) / 2) * 3.2;
      const z = (i - (padCount - 1) / 2) * 2.25;
      mat.makeTranslation(x, 4.16, -36.4); pads.setMatrixAt(i, mat);
      mat.makeTranslation(x, 4.16, 36.4); pads.setMatrixAt(padCount + i, mat);
      mat.makeRotationY(Math.PI / 2); mat.setPosition(-50.6, 4.16, z); pads.setMatrixAt(padCount * 2 + i, mat);
      mat.makeRotationY(Math.PI / 2); mat.setPosition(50.6, 4.16, z); pads.setMatrixAt(padCount * 3 + i, mat);
    }
    root.add(pads);
    this._flatLabel(root, tiny ? 'TinyTapeout  |  GARDA NEURAL' : 'GARDA  |  RTL ARCHITECTURE',
      0, 4.69, -28.6, 76, 4,
      { size: 49, color: '#25405b', height: 128 });
    this._flatLabel(root, 'CONCEPTUAL PLACEMENT', 0, 4.69, 29.1, 64, 2.1,
      { size: 37, color: '#58758a', height: 96, mono: true });

    if (!blocks.length) {
      this._flatLabel(root, ['GARDA', 'SELECT AN RTL CATALOG'], 0, 4.8, 0, 70, 18,
        { size: 55, color: '#48667b' });
      return;
    }

    const cols = blocks.length <= 4 ? 2 : blocks.length <= 9 ? 3 : blocks.length <= 16 ? 4 : 5;
    const rows = Math.ceil(blocks.length / cols);
    const usableW = 85, usableD = 48;
    const gutter = 1.9;
    const cellW = (usableW - gutter * (cols - 1)) / cols;
    const cellD = (usableD - gutter * (rows - 1)) / rows;
    blocks.forEach((b, i) => {
      const col = i % cols, row = Math.floor(i / cols);
      const itemsInRow = Math.min(cols, blocks.length - row * cols);
      const offset = (cols - itemsInRow) * (cellW + gutter) / 2;
      const x = -usableW / 2 + cellW / 2 + col * (cellW + gutter) + offset;
      const z = -usableD / 2 + cellD / 2 + row * (cellD + gutter) + .4;
      const groupName = typeof b.group === 'string' ? b.group : 'default';
      const color = b.color || PALETTE[groupName] || PALETTE.default;
      const height = /memory|rom|bank/i.test(`${groupName} ${b.id}`) ? 3.1 :
        /gate|security|safety/i.test(`${groupName} ${b.id}`) ? 4.8 : 3.7;
      const group = new THREE.Group();
      group.position.set(x, 4.68, z);
      group.userData.baseY = 4.68;
      group.userData.explode = 4 + (i % 3) * 2.4;
      root.add(group);
      const mesh = this._box(group, 0, height / 2, 0, cellW, height, cellD, color,
        { metal: .14, roughness: .47, pick: String(b.id) });
      mesh.userData.baseColor = new THREE.Color(color);
      mesh.userData.mode = tiny ? 'tt' : 'die';
      mesh.userData.block = b;
      const edges = new THREE.LineSegments(new THREE.EdgesGeometry(mesh.geometry),
        new THREE.LineBasicMaterial({ color: '#ffffff', transparent: true, opacity: .32 }));
      mesh.add(edges);
      const outline = new THREE.LineSegments(new THREE.EdgesGeometry(mesh.geometry),
        new THREE.LineBasicMaterial({ color: '#fd9d35', transparent: false, linewidth: 2, depthTest: false }));
      outline.scale.setScalar(1.013);
      outline.visible = false;
      outline.renderOrder = 7;
      mesh.add(outline);
      mesh.userData.outline = outline;
      this._blockMeshes.push(mesh);

      const title = b.title || b.name || b.module || b.id;
      const fontSize = blocks.length > 16 ? 45 : 48;
      const tmp = document.createElement('canvas').getContext('2d');
      tmp.font = `600 ${fontSize}px Arial, sans-serif`;
      const titleLines = wrapText(tmp, title, 540, cellD < 10 ? 2 : 3);
      const label = this._flatLabel(group, titleLines, 0, height + .05, cellD < 10 ? -.25 : -cellD * .055,
        cellW * .96, cellD * .72,
        { width: 640, height: 300, size: fontSize, color: '#092639' });
      label.userData.selectId = String(b.id);
      this._pickables.push(label);
      if (cellD > 10) {
        const shortName = b.name || b.module || b.id;
        this._flatLabel(group, shortName, 0, height + .065, cellD * .33, cellW * .86, cellD * .14,
          { width: 1024, height: 100, size: 42, color: '#153c52', mono: true });
      }

      // Sparse silicon bus traces below the lifted logic block.
      const trace = new THREE.LineSegments(new THREE.BufferGeometry().setFromPoints([
        new THREE.Vector3(x, 4.65, z), new THREE.Vector3(x, 4.65, 25.6),
        new THREE.Vector3(x, 4.65, 25.6), new THREE.Vector3(0, 4.65, 25.6),
      ]), new THREE.LineBasicMaterial({ color: new THREE.Color(color).multiplyScalar(.73), transparent: true, opacity: .5 }));
      root.add(trace);
    });
  }

  _bindControls() {
    const canvas = this.canvas;
    canvas.style.touchAction = 'none';
    canvas.style.cursor = 'grab';
    this._listeners = [];
    const listen = (target, event, fn, options) => {
      target.addEventListener(event, fn, options);
      this._listeners.push(() => target.removeEventListener(event, fn, options));
    };
    listen(canvas, 'pointerdown', e => {
      if (e.button !== 0 && e.pointerType !== 'touch') return;
      this._pointers.set(e.pointerId, { x: e.clientX, y: e.clientY });
      canvas.setPointerCapture(e.pointerId);
      this._down = { x: e.clientX, y: e.clientY, time: performance.now() };
      this._moving = this._pointers.size > 1;
      this._pinchDistance = this._getPinchDistance();
      this._lastInteraction = performance.now();
      canvas.style.cursor = 'grabbing';
    });
    listen(canvas, 'pointermove', e => {
      const previous = this._pointers.get(e.pointerId);
      if (!previous) {
        this._hover(e);
        return;
      }
      const dx = e.clientX - previous.x, dy = e.clientY - previous.y;
      this._pointers.set(e.pointerId, { x: e.clientX, y: e.clientY });
      if (this._down && Math.hypot(e.clientX - this._down.x, e.clientY - this._down.y) > 5) this._moving = true;
      if (this._pointers.size > 1) {
        const distance = this._getPinchDistance();
        if (this._pinchDistance && distance) this._orbitGoal.radius = clamp(this._orbitGoal.radius * this._pinchDistance / distance, 65, 330);
        this._pinchDistance = distance;
        this._moving = true;
      } else {
        this._orbitGoal.az -= dx * .006;
        this._orbitGoal.el = clamp(this._orbitGoal.el + dy * .005, .22, 1.52);
      }
      this._lastInteraction = performance.now();
    });
    const release = e => {
      const wasTouching = this._pointers.has(e.pointerId);
      this._pointers.delete(e.pointerId);
      if (wasTouching && e.type === 'pointerup' && !this._moving && this._down && performance.now() - this._down.time < 600) this._click(e);
      if (canvas.hasPointerCapture(e.pointerId)) canvas.releasePointerCapture(e.pointerId);
      canvas.style.cursor = 'grab';
      this._pinchDistance = this._getPinchDistance();
      if (!this._pointers.size) this._down = null;
    };
    listen(canvas, 'pointerup', release);
    listen(canvas, 'pointercancel', release);
    listen(canvas, 'wheel', e => {
      e.preventDefault();
      this._orbitGoal.radius = clamp(this._orbitGoal.radius * Math.exp(clamp(e.deltaY, -100, 100) * .0016), 65, 330);
      this._lastInteraction = performance.now();
    }, { passive: false });
    listen(canvas, 'dblclick', () => this.reset());
    listen(canvas, 'contextmenu', e => e.preventDefault());
  }

  _getPinchDistance() {
    if (this._pointers.size < 2) return 0;
    const [a, b] = [...this._pointers.values()];
    return Math.hypot(a.x - b.x, a.y - b.y);
  }

  _hit(event) {
    const r = this.canvas.getBoundingClientRect();
    this.pointer.set((event.clientX - r.left) / r.width * 2 - 1,
      -(event.clientY - r.top) / r.height * 2 + 1);
    this.raycaster.setFromCamera(this.pointer, this.camera);
    const visible = this._pickables.filter(mesh => {
      let obj = mesh;
      while (obj) {
        if (!obj.visible) return false;
        obj = obj.parent;
      }
      return true;
    });
    return this.raycaster.intersectObjects(visible, false)[0]?.object || null;
  }

  _hover(event) {
    if (!this._pointers.size) this.canvas.style.cursor = this._hit(event) ? 'pointer' : 'grab';
  }

  _click(event) {
    const obj = this._hit(event);
    if (!obj) return;
    let id = obj.userData.selectId;
    if (id === '_fpga') {
      id = this._blocks.find(b => b.id === 'garda_uart_top')?.id || this._blocks.find(b => /top|wrapper/.test(b.id))?.id || this._blocks[0]?.id || 'garda_uart_top';
      this.setMode('die');
    }
    this.select(id);
    this.onSelect(id);
  }

  _resize() {
    if (this._disposed) return;
    const r = (this.canvas.parentElement || this.canvas).getBoundingClientRect();
    const width = Math.max(1, Math.round(r.width));
    const height = Math.max(1, Math.round(r.height));
    this.renderer.setSize(width, height, false);
    this.camera.aspect = width / height;
    // Keep the complete board visible on narrow screens without changing zoom intent.
    this._viewScale = Math.max(1, 1.15 / this.camera.aspect);
    this.camera.updateProjectionMatrix();
  }

  _tick(now) {
    if (this._disposed) return;
    this._raf = requestAnimationFrame(this._tick);
    const dt = this._lastFrame ? Math.min((now - this._lastFrame) / 1000, .05) : 1 / 60;
    this._lastFrame = now;
    if (this._autoRotate && !this._pointers.size && now - this._lastInteraction > 1200) this._orbitGoal.az += dt * .12;
    const ease = 1 - Math.exp(-dt * 11);
    ['az', 'el', 'radius'].forEach(k => this._orbit[k] += (this._orbitGoal[k] - this._orbit[k]) * ease);
    const { az, el, radius } = this._orbit;
    const distance = radius * (this._viewScale || 1);
    this.camera.position.set(this._target.x + Math.sin(az) * Math.cos(el) * distance,
      this._target.y + Math.sin(el) * distance, this._target.z + Math.cos(az) * Math.cos(el) * distance);
    this.camera.lookAt(this._target);
    this._blockMeshes.forEach(mesh => {
      const parent = mesh.parent;
      const goal = parent.userData.baseY + (this._exploded ? parent.userData.explode : 0);
      parent.position.y += (goal - parent.position.y) * ease;
    });
    if (!document.hidden) this.renderer.render(this.scene, this.camera);
  }

  _applySelection() {
    this._blockMeshes.forEach(mesh => {
      const yes = mesh.userData.selectId === this._selected;
      mesh.material.color.copy(mesh.userData.baseColor);
      mesh.material.emissive.set(yes ? '#1f4f63' : '#000000');
      mesh.material.emissiveIntensity = yes ? .2 : 0;
      mesh.userData.outline.visible = yes;
    });
    if (this.fpga) {
      const yes = this._mode === 'board' && this._selected && this._selected !== 'hps';
      this.fpga.material.emissive.set(yes ? '#0c3149' : '#000000');
      this.fpga.material.emissiveIntensity = .25;
    }
  }

  _applyExplosion() {
    // Positions interpolate in the main frame loop.
    this._lastInteraction = performance.now();
  }

  setBlocks(blocks) {
    this._blocks = Array.isArray(blocks) ? blocks.filter(b => b && b.id).map(b => ({ ...b, id: String(b.id) })) : [];
    this._rebuildLogic();
    return this;
  }

  setMode(mode) {
    if (!['board', 'die', 'tt'].includes(mode)) return this;
    const changed = this._mode !== mode;
    this._mode = mode;
    this.board.visible = mode === 'board';
    this.die.visible = mode === 'die';
    this.tt.visible = mode === 'tt';
    if (changed) {
      this.reset();
      this.onModeChange(mode);
    }
    this._applySelection();
    return this;
  }

  select(id) {
    this._selected = id == null ? null : String(id);
    this._applySelection();
    return this;
  }

  setExploded(value) {
    this._exploded = Boolean(value);
    this._applyExplosion();
    return this;
  }

  setAutoRotate(value) {
    this._autoRotate = Boolean(value);
    return this;
  }

  reset() {
    Object.assign(this._orbitGoal, { az: this._mode === 'board' ? -.46 : -.25,
      el: this._mode === 'board' ? .83 : 1.04, radius: this._mode === 'board' ? 165 : 150 });
    this._lastInteraction = performance.now();
    return this;
  }

  get state() {
    return { mode: this._mode, selected: this._selected, exploded: this._exploded,
      autoRotate: this._autoRotate, blockCount: this._blocks.length };
  }

  dispose() {
    this._disposed = true;
    cancelAnimationFrame(this._raf);
    this._listeners.forEach(fn => fn());
    this._resizeObserver.disconnect();
    disposeTree(this.scene);
    this.renderer.dispose();
    this._pointers.clear();
  }
}
