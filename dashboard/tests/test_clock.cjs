const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const path = require('node:path');
class Element {
  constructor(dataset = {}) { this.dataset = dataset; this.value = '1'; this.textContent = ''; this.handlers = {}; this.attributes = {}; this.active = false; this.classList = {toggle: (_, value) => { this.active = value; }}; }
  addEventListener(event, callback) { this.handlers[event] = callback; }
  setAttribute(name, value) { this.attributes[name] = value; }
  trigger(event) { this.handlers[event](); }
}
const ids = Object.fromEntries(['clock-slider', 'clock-play', 'clock-number', 'clock-range', 'clock-layer', 'clock-group', 'clock-detail', 'clock-back', 'clock-next', 'clock-reset', 'clock-time', 'clock-next-group', 'clock-next-layer', 'clock-mode', 'clock-speed'].map(id => [id, new Element()]));
const stages = ['bias', 'weight', 'mac', 'activate'].map(stage => new Element({clockStage: stage}));
const layerButtons = [1, 3617, 6721].map(start => new Element({clockStart: String(start)}));
ids['clock-slider'].value = '0'; ids['clock-mode'].value = 'every'; ids['clock-speed'].value = 'normal';
let intervalCallback;
const sandbox = {document: {getElementById: id => ids[id], querySelectorAll: selector => selector === '[data-clock-stage]' ? stages : layerButtons, addEventListener() {}, hidden: false}, window: {matchMedia: () => ({addEventListener() {}}), setInterval: cb => { intervalCallback = cb; return 1; }, clearInterval() {}}, Math};
vm.runInNewContext(fs.readFileSync(path.join(__dirname, '../dist/clock-explorer.js'), 'utf8'), sandbox);
function seek(cycle) { ids['clock-slider'].value = String(cycle); ids['clock-slider'].trigger('input'); }
assert.match(ids['clock-detail'].textContent, /Siap/);
seek(1); assert.match(ids['clock-detail'].textContent, /BIAS_ADDRESS/);
seek(3); assert.match(ids['clock-detail'].textContent, /BIAS_TAKE/);
seek(4); assert.match(ids['clock-detail'].textContent, /WEIGHT_ADDRESS/);
seek(6); assert.match(ids['clock-detail'].textContent, /MAC/);
seek(226); assert.match(ids['clock-detail'].textContent, /ACTIVATE/);
seek(3616); assert.equal(ids['clock-layer'].textContent, 'FC1'); assert.match(ids['clock-detail'].textContent, /ACTIVATE/);
seek(3617); assert.equal(ids['clock-layer'].textContent, 'FC2'); assert.equal(ids['clock-group'].textContent, '1 / 8');
seek(6720); assert.equal(ids['clock-layer'].textContent, 'FC2'); assert.match(ids['clock-detail'].textContent, /ACTIVATE/);
seek(6721); assert.equal(ids['clock-layer'].textContent, 'FC3');
seek(6916); assert.match(ids['clock-detail'].textContent, /ACTIVATE/);
assert.equal(ids['clock-time'].textContent, '138,32 µs');
ids['clock-play'].trigger('click'); assert.equal(ids['clock-slider'].value, 0); intervalCallback(); assert.equal(ids['clock-slider'].value, 1);
ids['clock-next'].trigger('click'); assert.equal(ids['clock-slider'].value, 2); assert.equal(ids['clock-play'].attributes['aria-pressed'], 'false');
ids['clock-next-group'].trigger('click'); assert.equal(ids['clock-slider'].value, 227);
ids['clock-next-layer'].trigger('click'); assert.equal(ids['clock-slider'].value, 3617);
ids['clock-reset'].trigger('click'); assert.equal(ids['clock-slider'].value, 0);
ids['clock-mode'].value = 'highlights'; ids['clock-play'].trigger('click'); intervalCallback(); intervalCallback(); assert.equal(ids['clock-slider'].value, 4);
layerButtons[2].trigger('click'); assert.equal(ids['clock-slider'].value, 6721);
console.log('PASS: Parallel8 cycle boundaries and controls');
