const slider = document.getElementById('clock-slider');
const play = document.getElementById('clock-play');
const stages = [...document.querySelectorAll('[data-clock-stage]')];
const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
const layers = [
  {name: 'FC1', start: 1, inputs: 74, groups: 16},
  {name: 'FC2', start: 3617, inputs: 128, groups: 8},
  {name: 'FC3', start: 6721, inputs: 64, groups: 1}
];
let timer = null;
const format = n => n.toLocaleString('id-ID');
function describeClock(cycle) {
  if (cycle === 0) return {phase: null, detail: 'Siap memulai inferensi'};
  const layer = [...layers].reverse().find(item => cycle >= item.start);
  const groupLength = 4 + 3 * layer.inputs;
  const offset = cycle - layer.start;
  const group = Math.floor(offset / groupLength) + 1;
  const within = offset % groupLength;
  const groupStart = cycle - within;
  if (within < 3) return {layer, group, groupLength, groupStart, within, phase: 'bias', detail: ['BIAS_ADDRESS', 'BIAS_WAIT', 'BIAS_TAKE'][within]};
  if (within === groupLength - 1) return {layer, group, groupLength, groupStart, within, phase: 'activate', detail: 'ACTIVATE'};
  const input = Math.floor((within - 3) / 3) + 1;
  const sub = (within - 3) % 3;
  return {layer, group, groupLength, groupStart, within, phase: sub === 2 ? 'mac' : 'weight', detail: `${['WEIGHT_ADDRESS', 'WEIGHT_WAIT', 'MAC'][sub]} · input ${input} / ${layer.inputs}`};
}
function render() {
  const cycle = Number(slider.value), current = describeClock(cycle);
  document.getElementById('clock-number').textContent = `${format(cycle)} / 6.916`;
  document.getElementById('clock-range').textContent = `${format(cycle)} / 6.916`;
  document.getElementById('clock-time').textContent = `${(cycle / 50).toLocaleString('id-ID', {maximumFractionDigits: 2})} µs`;
  document.getElementById('clock-layer').textContent = current.layer?.name || 'Siap';
  document.getElementById('clock-group').textContent = current.layer ? `${current.group} / ${current.layer.groups}` : '—';
  document.getElementById('clock-detail').textContent = current.layer ? `${current.detail} · kelompok ${current.group}` : current.detail;
  stages.forEach(stage => stage.classList.toggle('active', stage.dataset.clockStage === current.phase));
}
function stop() {
  if (timer !== null) window.clearInterval(timer);
  timer = null; play.textContent = '▶ Putar'; play.setAttribute('aria-pressed', 'false');
  document.getElementById('clock-detail').setAttribute('aria-live', 'polite');
}
function setCycle(value) { slider.value = Math.max(0, Math.min(6916, value)); render(); }
function nextHighlight(cycle) {
  if (cycle === 0) return 1;
  const current = describeClock(cycle), end = current.groupLength - 1;
  const marks = [0, 3, 5, end - 3, end - 1, end, current.groupLength];
  const next = marks.find(mark => mark > current.within);
  return Math.min(6916, current.groupStart + next);
}
function startTimer() {
  const delay = {slow: 700, normal: 250, fast: 80}[document.getElementById('clock-speed').value];
  timer = window.setInterval(() => {
    const cycle = Number(slider.value);
    setCycle(document.getElementById('clock-mode').value === 'highlights' ? nextHighlight(cycle) : cycle + 1);
    if (Number(slider.value) === 6916) stop();
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
  setCycle(layers.find(item => item.start > cycle)?.start ?? 6916);
});
document.getElementById('clock-speed').addEventListener('change', () => { if (timer !== null) { window.clearInterval(timer); startTimer(); } });
document.querySelectorAll('[data-clock-start]').forEach(button => button.addEventListener('click', () => { stop(); setCycle(Number(button.dataset.clockStart)); }));
play.addEventListener('click', () => {
  if (timer !== null) { stop(); return; }
  if (Number(slider.value) === 6916) setCycle(0);
  play.textContent = 'Ⅱ Jeda'; play.setAttribute('aria-pressed', 'true');
  document.getElementById('clock-detail').setAttribute('aria-live', 'off'); startTimer();
});
reducedMotion.addEventListener('change', event => { if (event.matches) stop(); });
document.addEventListener('visibilitychange', () => { if (document.hidden) stop(); });
render();
