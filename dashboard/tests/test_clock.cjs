const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const path = require('node:path');
class Element {
  constructor(dataset = {}) { this.dataset = dataset; this.value = '1'; this.textContent = ''; this.handlers = {}; this.attributes = {}; this.active = false; this.classes = {}; this.child = {textContent: ''}; this.classList = {toggle: (name, value) => { this.classes[name] = value; this.active = value; }}; }
  querySelector() { return this.child; }
  addEventListener(event, callback) { this.handlers[event] = callback; }
  setAttribute(name, value) { this.attributes[name] = value; }
  trigger(event) { this.handlers[event](); }
}
const ids = Object.fromEntries(['clock-slider', 'clock-play', 'clock-number', 'clock-range', 'clock-layer', 'clock-group', 'clock-detail', 'clock-back', 'clock-next', 'clock-reset', 'clock-time', 'clock-next-group', 'clock-next-layer', 'clock-mode', 'clock-speed', 'lane-summary', 'group-progress', 'group-label', 'phase-explanation'].map(id => [id, new Element()]));
const stages = ['bias', 'weight', 'mac', 'activate'].map(stage => new Element({clockStage: stage}));
const nodes = ['input', 'weight', 'mac', 'activate', 'output'].map(flowNode => new Element({flowNode}));
const lanes = Array.from({length: 16}, (_, i) => new Element({lane: String(i)}));
const flowVisual = new Element();
const layerButtons = [1, 1809, 3361].map(start => new Element({clockStart: String(start)}));
ids['clock-slider'].value = '0'; ids['clock-mode'].value = 'every'; ids['clock-speed'].value = 'normal';
let intervalCallback;
const sandbox = {document: {getElementById: id => ids[id], querySelectorAll: selector => ({'[data-clock-stage]': stages, '[data-flow-node]': nodes, '[data-lane]': lanes, '[data-clock-start]': layerButtons})[selector], querySelector: () => flowVisual, addEventListener() {}, hidden: false}, window: {matchMedia: () => ({addEventListener() {}}), setInterval: cb => { intervalCallback = cb; return 1; }, clearInterval() {}}, Math};
vm.runInNewContext(fs.readFileSync(path.join(__dirname, '../dist/clock-explorer.js'), 'utf8'), sandbox);
function seek(cycle) { ids['clock-slider'].value = String(cycle); ids['clock-slider'].trigger('input'); }
assert.match(ids['clock-detail'].textContent, /Siap/);
seek(1); assert.match(ids['clock-detail'].textContent, /BIAS_ADDRESS/); assert.equal(nodes[1].classes.active, true); assert.match(ids['lane-summary'].textContent, /neuron 1–16/);
seek(3); assert.match(ids['clock-detail'].textContent, /BIAS_TAKE/);
seek(4); assert.match(ids['clock-detail'].textContent, /WEIGHT_ADDRESS/);
seek(6); assert.match(ids['clock-detail'].textContent, /MAC/); assert.equal(nodes[2].classes.active, true); assert.equal(lanes.filter(lane => lane.classes.working).length, 16);
seek(226); assert.match(ids['clock-detail'].textContent, /ACTIVATE/);
seek(1808); assert.equal(ids['clock-layer'].textContent, 'FC1'); assert.match(ids['clock-detail'].textContent, /ACTIVATE/);
seek(1809); assert.equal(ids['clock-layer'].textContent, 'FC2'); assert.equal(ids['clock-group'].textContent, '1 / 4');
seek(3360); assert.equal(ids['clock-layer'].textContent, 'FC2'); assert.match(ids['clock-detail'].textContent, /ACTIVATE/);
seek(3361); assert.equal(ids['clock-layer'].textContent, 'FC3'); assert.equal(lanes.filter(lane => lane.classes.unused).length, 13); assert.match(ids['lane-summary'].textContent, /neuron 1–3/);
seek(3556); assert.match(ids['clock-detail'].textContent, /ACTIVATE/); assert.equal(nodes[4].classes.active, true); assert.equal(lanes.filter(lane => lane.classes.working).length, 3); assert.match(ids['phase-explanation'].textContent, /residual/);
assert.equal(ids['clock-time'].textContent, '71,12 µs');
ids['clock-play'].trigger('click'); assert.equal(ids['clock-slider'].value, 0); intervalCallback(); assert.equal(ids['clock-slider'].value, 1);
ids['clock-next'].trigger('click'); assert.equal(ids['clock-slider'].value, 2); assert.equal(ids['clock-play'].attributes['aria-pressed'], 'false');
ids['clock-next-group'].trigger('click'); assert.equal(ids['clock-slider'].value, 227);
ids['clock-next-layer'].trigger('click'); assert.equal(ids['clock-slider'].value, 1809);
ids['clock-reset'].trigger('click'); assert.equal(ids['clock-slider'].value, 0);
ids['clock-mode'].value = 'highlights'; ids['clock-play'].trigger('click'); intervalCallback(); intervalCallback(); assert.equal(ids['clock-slider'].value, 4);
layerButtons[2].trigger('click'); assert.equal(ids['clock-slider'].value, 3361);
console.log('PASS: Parallel16 cycle boundaries and controls');
