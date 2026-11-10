import {icon} from './ui-icons.js';
const slider = document.getElementById('clock-slider');
const play = document.getElementById('clock-play');
const stages = [...document.querySelectorAll('[data-clock-stage]')];
const flowNodes = [...document.querySelectorAll('[data-flow-node]')];
const lanes = [...document.querySelectorAll('[data-lane]')];
const flowVisual = document.querySelector('.dataflow-visual');
const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
const layers = [
  {name: 'FC1', start: 1, inputs: 74, outputs: 128, groups: 8},
  {name: 'FC2', start: 1809, inputs: 128, outputs: 64, groups: 4},
  {name: 'FC3', start: 3361, inputs: 64, outputs: 3, groups: 1}
];
let timer = null;
const format = n => n.toLocaleString('en-US');
function describeClock(cycle) {
  if (cycle === 0) return {phase: null, detail: 'Siap memulai inferensi'};
  const layer = [...layers].reverse().find(item => cycle >= item.start);
  const groupLength = 4 + 3 * layer.inputs;
  const offset = cycle - layer.start;
  const group = Math.floor(offset / groupLength) + 1;
  const within = offset % groupLength;
  const groupStart = cycle - within;
  if (within < 3) return {layer, group, groupLength, groupStart, within, phase: 'bias', state: ['BIAS_ADDRESS', 'BIAS_WAIT', 'BIAS_TAKE'][within], detail: ['BIAS_ADDRESS', 'BIAS_WAIT', 'BIAS_TAKE'][within]};
  if (within === groupLength - 1) return {layer, group, groupLength, groupStart, within, phase: 'activate', state: 'ACTIVATE', detail: 'ACTIVATE'};
  const input = Math.floor((within - 3) / 3) + 1;
  const sub = (within - 3) % 3;
  return {layer, group, groupLength, groupStart, within, phase: sub === 2 ? 'mac' : 'weight', state: ['WEIGHT_ADDRESS', 'WEIGHT_WAIT', 'MAC'][sub], input, detail: `${['WEIGHT_ADDRESS', 'WEIGHT_WAIT', 'MAC'][sub]} , input ${input} / ${layer.inputs}`};
}
const explanations = {
  BIAS_ADDRESS: 'Alamat bias kelompok ini disiapkan untuk dibaca.',
  BIAS_WAIT: 'Memori sinkron menyiapkan bias untuk setiap lane kelompok.',
  BIAS_TAKE: 'Bias mengisi akumulator lane yang digunakan.',
  WEIGHT_ADDRESS: 'Input dipilih dan alamat bobot untuk kelompok ini disiapkan.',
  WEIGHT_WAIT: 'Memori sinkron menyiapkan bobot sebelum operasi MAC.',
  MAC: 'Satu input dikalikan dengan bobot lane; hasilnya ditambahkan ke akumulator.',
  ACTIVATE: 'Akumulator diaktifkan atau dibatasi, lalu hasil kelompok disimpan.'
};
function renderFlow(current, cycle) {
  const label = document.getElementById('lane-summary');
  const progress = document.getElementById('group-progress');
  const groupLabel = document.getElementById('group-label');
  const explanation = document.getElementById('phase-explanation');
  const first = current.layer ? (current.group - 1) * 16 + 1 : 0;
  const last = current.layer ? Math.min(first + 15, current.layer.outputs) : 0;
  const activeNode = current.phase === 'bias' ? 'weight' :
    current.state === 'WEIGHT_ADDRESS' ? 'input' :
    current.state === 'WEIGHT_WAIT' ? 'weight' : current.phase;
  flowNodes.forEach(node => node.classList.toggle('active', node.dataset.flowNode === activeNode ||
    (node.dataset.flowNode === 'output' && cycle === 3556)));
  lanes.forEach((lane, index) => {
    const neuron = first + index;
    const used = Boolean(current.layer && neuron <= current.layer.outputs);
    lane.classList.toggle('unused', Boolean(current.layer && !used));
    lane.classList.toggle('working', used && ['BIAS_TAKE', 'MAC', 'ACTIVATE'].includes(current.state));
    lane.querySelector('strong').textContent = used ? '●' : '—';
    lane.setAttribute('aria-label', current.layer ? `Lane ${index + 1}: ${used ? `neuron ${neuron}` : 'tidak digunakan'}` : `Lane ${index + 1}: menunggu`);
  });
  progress.max = current.layer?.groups || 8;
  progress.value = current.group || 0;
  groupLabel.textContent = current.layer ? `${current.group} / ${current.layer.groups}` : 'Menunggu';
  label.textContent = current.layer ? `${current.layer.name}: neuron ${first}–${last} dari ${current.layer.outputs}` : 'Belum ada kelompok yang berjalan.';
  explanation.textContent = current.state ? explanations[current.state] +
    (current.state === 'ACTIVATE' && current.layer.name === 'FC3' ? ' Tiga hasil membentuk residual keluaran.' : '') :
    'Tekan Play atau pilih clock untuk melihat fase perhitungan.';
}
function render() {
  const cycle = Number(slider.value), current = describeClock(cycle);
  document.getElementById('clock-number').textContent = `${format(cycle)} / 3,556`;
  document.getElementById('clock-range').textContent = `${format(cycle)} / 3,556`;
  document.getElementById('clock-time').textContent = `${(cycle / 50).toLocaleString('id-ID', {maximumFractionDigits: 2})} µs`;
  document.getElementById('clock-layer').textContent = current.layer?.name || 'Siap';
  document.getElementById('clock-group').textContent = current.layer ? `${current.group} / ${current.layer.groups}` : '—';
  document.getElementById('clock-detail').textContent = current.layer ? `${current.detail} , kelompok ${current.group}` : current.detail;
  stages.forEach(stage => stage.classList.toggle('active', stage.dataset.clockStage === current.phase));
  renderFlow(current, cycle);
}
function stop() {
  if (timer !== null) window.clearInterval(timer);
  timer = null; flowVisual.classList.toggle('is-playing', false); play.innerHTML = icon('play'); play.setAttribute('aria-label','Play inference'); play.title='Play inference'; play.setAttribute('aria-pressed', 'false');
  document.getElementById('clock-detail').setAttribute('aria-live', 'polite');
}
function setCycle(value) { slider.value = Math.max(0, Math.min(3556, value)); render(); }
function nextHighlight(cycle) {
  if (cycle === 0) return 1;
  const current = describeClock(cycle), end = current.groupLength - 1;
  const marks = [0, 3, 5, end - 3, end - 1, end, current.groupLength];
  const next = marks.find(mark => mark > current.within);
  return Math.min(3556, current.groupStart + next);
}
function startTimer() {
  flowVisual.classList.toggle('is-playing', true);
  const delay = {slow: 1200, normal: 650, fast: 220}[document.getElementById('clock-speed').value];
  timer = window.setInterval(() => {
    const cycle = Number(slider.value);
    setCycle(document.getElementById('clock-mode').value === 'highlights' ? nextHighlight(cycle) : cycle + 1);
    if (Number(slider.value) === 3556) stop();
  }, delay);
}
slider.addEventListener('input', () => { stop(); render(); });
document.getElementById('clock-back').addEventListener('click', () => { stop(); setCycle(Number(slider.value) - 1); });
document.getElementById('clock-next').addEventListener('click', () => { stop(); setCycle(Number(slider.value) + 1); });
document.getElementById('clock-reset').addEventListener('click', () => { stop(); setCycle(0); });
document.getElementById('clock-next-group').addEventListener('click', () => {
  stop(); const cycle = Number(slider.value), current = describeClock(cycle);
  setCycle(cycle === 0 ? 1 : current.groupStart + current.groupLength);
});
document.getElementById('clock-next-layer').addEventListener('click', () => {
  stop(); const cycle = Number(slider.value);
  setCycle(layers.find(item => item.start > cycle)?.start ?? 3556);
});
document.getElementById('clock-speed').addEventListener('change', () => { if (timer !== null) { window.clearInterval(timer); startTimer(); } });
document.querySelectorAll('[data-clock-start]').forEach(button => button.addEventListener('click', () => { stop(); setCycle(Number(button.dataset.clockStart)); }));
play.addEventListener('click', () => {
  if (timer !== null) { stop(); return; }
  if (Number(slider.value) === 3556) setCycle(0);
  play.innerHTML = icon('pause'); play.setAttribute('aria-label','Pause inference'); play.title='Pause inference'; play.setAttribute('aria-pressed', 'true');
  document.getElementById('clock-detail').setAttribute('aria-live', 'off'); startTimer();
});
reducedMotion.addEventListener('change', event => { if (event.matches) stop(); });
document.addEventListener('visibilitychange', () => { if (document.hidden) stop(); });
render();

// Educational synchronization; robot timeline is not measured inference data.
document.addEventListener("garda-demo-frame", event => { if(timer!==null) stop(); setCycle(event.detail.clock); });
