// Lazy 3D GDSII view: the Tiny Tapeout viewer loads only on request (WebGL, ~1.6 MB of OASIS).
const button = document.getElementById('silicon-3d-load');
const stage = document.getElementById('silicon-3d-stage');
const msg = document.getElementById('silicon-3d-msg');
const MODEL = 'https://wlmoi.github.io/GARDA/tinytapeout.oas';
const VIEWER = `https://gds-viewer.tinytapeout.com/?pdk=ihp-sg13cmos5l&model=${encodeURIComponent(MODEL)}`;

function hasWebGL() {
  try { const c = document.createElement('canvas'); return !!(c.getContext('webgl2') || c.getContext('webgl')); } catch { return false; }
}

button?.addEventListener('click', () => {
  if (!hasWebGL()) {
    msg.textContent = 'This browser has no WebGL, so the 3D view cannot run here. The image above is the same layout; the GDSII page has a 2D explorer.';
    return;
  }
  const frame = document.createElement('iframe');
  frame.src = VIEWER;
  frame.title = 'Tiny Tapeout 3D GDS viewer showing GARDA-chip';
  frame.allow = 'fullscreen';
  frame.referrerPolicy = 'no-referrer';
  frame.loading = 'eager';
  stage.appendChild(frame);
  stage.classList.add('is-live');
});
