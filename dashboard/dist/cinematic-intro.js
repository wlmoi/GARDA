// Cinematic chip power-up intro. Compositor-only (WAAPI on SVG strokes and
// CSS transforms): no WebGL, no canvas, no per-frame JS.  Once per session,
// skipped entirely for reduced motion; tap, click or Esc skips it.  ?intro
// forces a replay.  Fires 'garda-intro-complete' when done.
const reduced = matchMedia('(prefers-reduced-motion: reduce)').matches;
let seen = false;
try { seen = sessionStorage.getItem('garda-boot-seen') === '1'; } catch {}
if (new URLSearchParams(location.search).has('intro')) seen = false;
if (!reduced && !seen) start();
else document.documentElement.classList.remove('gi-pending');

function start() {
  const css = document.createElement('style');
  css.textContent = `
.gi{position:fixed;inset:0;z-index:100000;display:grid;place-items:center;background:#070B20;color:#F7F9FF;overflow:hidden;cursor:pointer;-webkit-tap-highlight-color:transparent}
.gi::before{content:"";position:absolute;inset:-20%;background:radial-gradient(circle at 50% 46%,rgba(49,92,255,.32),transparent 46%),
 linear-gradient(rgba(49,92,255,.09) 1px,transparent 1px) 0 0/34px 34px,linear-gradient(90deg,rgba(49,92,255,.09) 1px,transparent 1px) 0 0/34px 34px;opacity:0;animation:gi-grid 1.2s ease-out .1s forwards}
.gi-scan{position:absolute;left:0;right:0;height:22vh;top:-25vh;background:linear-gradient(180deg,transparent,rgba(183,255,53,.10),rgba(183,255,53,.32) 50%,transparent 52%);animation:gi-scan 1.5s cubic-bezier(.4,0,.2,1) .15s forwards}
.gi-core{position:relative;display:grid;justify-items:center;gap:clamp(14px,3vh,26px);will-change:transform,opacity}
.gi-chip{width:min(46vw,250px);height:auto;overflow:visible}
.gi-chip .die{fill:none;stroke:#315CFF;stroke-width:2.2}
.gi-chip .die-in{fill:rgba(49,92,255,.12);stroke:rgba(147,172,255,.5);stroke-width:1}
.gi-chip .pin{stroke:#93ACFF;stroke-width:3;stroke-linecap:round}
.gi-chip .tr{fill:none;stroke:#B7FF35;stroke-width:1.6;stroke-linecap:round;stroke-linejoin:round;filter:drop-shadow(0 0 3px rgba(183,255,53,.8))}
.gi-chip .node{fill:#B7FF35}
.gi-chip .glow{fill:#B7FF35;filter:blur(14px);opacity:0}
.gi-chip .mark{fill:#B7FF35;transform-origin:100px 100px;transform-box:view-box}
.gi-word{display:flex;gap:.04em;font:900 clamp(40px,10vw,84px)/1 'Archivo',system-ui,sans-serif;letter-spacing:-.03em}
.gi-word span{display:inline-block;opacity:0}
.gi-word span.dot{color:#B7FF35}
.gi-tag{display:flex;align-items:center;gap:12px;font:600 clamp(11px,2.6vw,14px)/1.3 'IBM Plex Mono',ui-monospace,monospace;letter-spacing:.14em;text-transform:uppercase;color:#A8B6D4;opacity:0;text-align:center}
.gi-tag b{color:#B7FF35;font-weight:600}
.gi-tag i{width:.9em;height:.9em;background:#B7FF35;-webkit-mask:var(--gi-chip) center/contain no-repeat;mask:var(--gi-chip) center/contain no-repeat;flex:none}
.gi-skip{position:absolute;right:max(16px,env(safe-area-inset-right,0px));top:max(16px,env(safe-area-inset-top,0px));min-height:44px;padding:0 16px;border-radius:999px;border:1px solid rgba(247,249,255,.25);background:rgba(7,11,32,.6);color:#F7F9FF;font:600 12px/1 'IBM Plex Mono',monospace;letter-spacing:.08em;text-transform:uppercase;cursor:pointer}
@keyframes gi-grid{to{opacity:1}}
@keyframes gi-scan{to{transform:translateY(150vh)}}`;
  document.head.append(css);

  const chipMask = `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'%3E%3Cpath d='M9 2h2v3H9zM13 2h2v3h-2zM9 19h2v3H9zM13 19h2v3h-2zM2 9h3v2H2zM2 13h3v2H2zM19 9h3v2h-3zM19 13h3v2h-3z'/%3E%3Crect x='6' y='6' width='12' height='12' rx='2.5'/%3E%3C/svg%3E")`;
  // pins: 5 per side; traces: from a few pins into the core
  const pins = [];
  for (let k = 0; k < 5; k++) {
    const p = 62 + k * 19;
    pins.push(`<line class="pin" x1="${p}" y1="44" x2="${p}" y2="30"/>`, `<line class="pin" x1="${p}" y1="156" x2="${p}" y2="170"/>`,
              `<line class="pin" x1="44" y1="${p}" x2="30" y2="${p}"/>`, `<line class="pin" x1="156" y1="${p}" x2="170" y2="${p}"/>`);
  }
  const traces = ['M62 44V62H82V84', 'M138 44V58H120V84', 'M44 81H66V92H84', 'M156 119H134V108H116', 'M81 156V140H92V116', 'M157 62H140V74H116V84', 'M43 138H62V124H84V116', 'M119 156V136H108V116'];
  const nodes = [[82, 84], [120, 84], [84, 92], [116, 108], [92, 116], [116, 84], [84, 116], [108, 116]];
  const overlay = document.createElement('div');
  overlay.className = 'gi';
  overlay.style.setProperty('--gi-chip', chipMask);
  overlay.setAttribute('aria-hidden', 'true');
  overlay.innerHTML = `<div class="gi-scan"></div>
  <div class="gi-core">
    <svg class="gi-chip" viewBox="0 0 200 200">
      <circle class="glow" cx="100" cy="100" r="34"/>
      <rect class="die" x="44" y="44" width="112" height="112" rx="14" pathLength="1"/>
      <rect class="die-in" x="58" y="58" width="84" height="84" rx="8"/>
      ${pins.join('')}
      ${traces.map(d => `<path class="tr" d="${d}" pathLength="1"/>`).join('')}
      ${nodes.map(([x, y]) => `<circle class="node" cx="${x}" cy="${y}" r="2.6"/>`).join('')}
      <g class="mark"><path transform="translate(76 76) scale(.75)" d="M47 21.5a19 19 0 1 0 2.5 18.3v-9H32v7h9.4c-2 3.4-5.5 5.3-9.4 5.3a11.2 11.2 0 1 1 9.1-17.8z"/></g>
    </svg>
    <div class="gi-word">${'GARDA'.split('').map(c => `<span>${c}</span>`).join('')}<span class="dot">.</span></div>
    <p class="gi-tag">AI proposes<i></i><b>Hardware decides</b></p>
  </div>
  <button type="button" class="gi-skip">Skip intro</button>`;
  document.body.append(overlay);
  document.documentElement.classList.remove('gi-pending'); // the overlay now covers the page itself

  const q = s => overlay.querySelector(s), qa = s => [...overlay.querySelectorAll(s)];
  const ease = 'cubic-bezier(.22,1,.36,1)';
  const anims = [];
  // every animation starts paused: the page's 3D scenes block the main thread
  // while this mounts, and a running timeline would jump straight to its end
  const run = (el, frames, opts) => { const a = el.animate(frames, { fill: 'both', easing: ease, ...opts }); a.pause(); anims.push(a); return a; };

  // 1. die outline draws itself, inner die settles
  run(q('.die'), [{ strokeDasharray: 1, strokeDashoffset: 1 }, { strokeDasharray: 1, strokeDashoffset: 0 }], { duration: 750, delay: 100 });
  run(q('.die-in'), [{ opacity: 0, transform: 'scale(.9)', transformOrigin: '100px 100px' }, { opacity: 1, transform: 'scale(1)', transformOrigin: '100px 100px' }], { duration: 500, delay: 450 });
  // 2. pins grow out, side by side
  qa('.pin').forEach((p, i) => run(p, [{ opacity: 0 }, { opacity: 1 }], { duration: 220, delay: 480 + (i % 5) * 45 + Math.floor(i / 20) * 0 }));
  // 3. lime traces run from the pins to the core, nodes light up
  qa('.tr').forEach((t, i) => run(t, [{ strokeDasharray: 1, strokeDashoffset: 1, opacity: 1 }, { strokeDasharray: 1, strokeDashoffset: 0, opacity: 1 }], { duration: 520, delay: 820 + i * 55 }));
  qa('.node').forEach((n, i) => run(n, [{ opacity: 0, transform: 'scale(0)', transformOrigin: 'center', transformBox: 'fill-box' }, { opacity: 1, transform: 'scale(1.6)', offset: .6 }, { opacity: 1, transform: 'scale(1)' }], { duration: 360, delay: 1180 + i * 55 }));
  // 4. the core powers up: glow pulse, GARDA mark pops in
  run(q('.glow'), [{ opacity: 0 }, { opacity: .85, offset: .4 }, { opacity: .35 }], { duration: 900, delay: 1350 });
  run(q('.mark'), [{ opacity: 0, transform: 'scale(.4) rotate(-20deg)' }, { opacity: 1, transform: 'scale(1.12) rotate(0deg)', offset: .7 }, { opacity: 1, transform: 'scale(1)' }], { duration: 620, delay: 1380 });
  // 5. wordmark letters rise, tagline follows
  qa('.gi-word span').forEach((s, i) => run(s, [{ opacity: 0, transform: 'translateY(60%) rotateX(70deg)', filter: 'blur(6px)' }, { opacity: 1, transform: 'none', filter: 'blur(0)' }], { duration: 560, delay: 1500 + i * 60 }));
  run(q('.gi-tag'), [{ opacity: 0, transform: 'translateY(8px)', letterSpacing: '.34em' }, { opacity: 1, transform: 'none', letterSpacing: '.14em' }], { duration: 700, delay: 1850 });
  // 6. dive into the chip: the scene scales through the core and the page appears behind it
  const core = q('.gi-core');
  run(core, [{ transform: 'scale(1)', opacity: 1 }, { transform: 'scale(7)', opacity: 0 }], { duration: 650, delay: 2380, easing: 'cubic-bezier(.7,0,.84,0)' });
  const fade = run(overlay, [{ backgroundColor: 'rgba(7,11,32,1)' }, { backgroundColor: 'rgba(7,11,32,0)' }], { duration: 520, delay: 2520, easing: 'ease-in' });

  let done = false;
  function finish() {
    if (done) return; done = true;
    anims.forEach(a => { try { a.cancel(); } catch {} });
    overlay.remove(); css.remove();
    document.documentElement.classList.remove('gi-pending');
    removeEventListener('keydown', key);
    try { sessionStorage.setItem('garda-boot-seen', '1'); } catch {}
    document.dispatchEvent(new Event('garda-intro-complete'));
  }
  function key(e) { if (e.key === 'Escape' || e.key === 'Enter' || e.key === ' ') finish(); }
  addEventListener('keydown', key);
  overlay.addEventListener('click', finish);
  fade.finished.then(finish).catch(() => {});

  // play once frames arrive smoothly (3 in a row under 40 ms), or after 1.5 s at most
  let calm = 0, last = performance.now(), started = false;
  const t0 = last;
  function play() {
    if (started || done) return; started = true;
    anims.forEach(a => { a.currentTime = 0; a.play(); });
    setTimeout(finish, 3700);              // never block the page
  }
  (function watch(now) {
    if (started || done) return;
    calm = now - last < 40 ? calm + 1 : 0; last = now;
    if (calm >= 3 || now - t0 > 1500) play(); else requestAnimationFrame(watch);
  })(performance.now());
  setTimeout(play, 1700);                  // rAF can stall in background tabs
  setTimeout(finish, 6500);
}
