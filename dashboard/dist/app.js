import { GardaScene } from './scene.js';
import { evaluateGate, faultDescriptions } from './gate-model.js';

const $ = id => document.getElementById(id);
const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const colors = { host: '#2F5BFF', compute: '#3B64FF', memory: '#7C97FF', control: '#2F5BFF', safety: '#1A8A3E', neural: '#3B64FF', alternate: '#8E9099', asic: '#9B7000' };
let mode = 'board', selected, scene, catalog, report, sourceRequest = 0;
let modules = [], ttModules = [];
const canvas = $('scene');
const available = () => mode === 'tt' ? ttModules : modules;

const translations = {
  id: {
    'hero.stage':'Prototipe riset. Demo browser adalah simulasi; penerapan pada drone inspeksi PLN masih memerlukan pilot.',
    'nav.home':'Beranda','nav.solution':'Solusi','nav.demo':'Demo','nav.technology':'Teknologi','nav.results':'Hasil pengujian',
    'nav.explorer': 'EKSPLORASI',
    'nav.architecture': 'ARSITEKTUR',
    'nav.dataflow': 'DATAFLOW',
    'nav.robot': 'ROBOT & SAFETY',
    'nav.verification': 'VERIFIKASI',
    'hero.title': '<span class="portal-title-left">Drone menginspeksi.</span><br><em class="portal-title-right">GARDA menjaga.</em>',
    'hero.lead': 'Drone inspeksi jaringan listrik perlu menghindari rintangan tanpa bergantung pada koneksi ke server. GARDA mengembangkan chip yang menghitung usulan koreksi gerak dan memeriksanya dengan gerbang keselamatan perangkat keras untuk membantu operator menjaga wahana dan aset.',
    'hero.explore': 'Lihat demo',
    'hero.play': 'Cara kerja dan manfaat',
    'hero.metricCycles': 'clock Parallel16, diuji lewat RTL',
    'hero.metricTime': 'proyeksi core pada 50 MHz'
  },
  en: {
    'hero.stage':'Research prototype. The browser demo is a simulation; deployment on PLN inspection drones still requires a pilot.',
    'nav.home':'Home','nav.solution':'Solution','nav.demo':'Demo','nav.technology':'Technology','nav.results':'Test results',
    'nav.explorer': 'EXPLORATION',
    'nav.architecture': 'ARCHITECTURE',
    'nav.dataflow': 'DATAFLOW',
    'nav.robot': 'ROBOT & SAFETY',
    'nav.verification': 'VERIFICATION',
    'hero.title': '<span class="portal-title-left">Drones inspect.</span><br><em class="portal-title-right">GARDA keeps watch.</em>',
    'hero.lead': 'Power-line inspection drones need to avoid obstacles without depending on a server connection. GARDA is developing a chip that computes proposed motion corrections and checks them with a hardware safety gate to help operators protect vehicles and assets.',
    'hero.explore': 'Watch the demo',
    'hero.play': 'How it works and why it matters',
    'hero.metricCycles': 'Parallel16 clocks, RTL tested',
    'hero.metricTime': 'core projection at 50 MHz'
  }
};

function setupPreferences() {
  const root = document.documentElement;
  const themeToggle = $('theme-toggle'), languageToggle = $('language-toggle');
  let theme = 'dark', language = 'id';
  try {
    theme = localStorage.getItem('garda-theme') || (matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
    language = localStorage.getItem('garda-language') || 'id';
  } catch (error) {
    console.warn('Preferences unavailable', error.message);
  }

  const applyTheme = next => {
    theme = next === 'dark' ? 'dark' : 'light';
    root.dataset.theme = theme;
    themeToggle.setAttribute('aria-pressed', String(theme === 'dark'));
    themeToggle.setAttribute('aria-label', theme === 'dark' ? 'Aktifkan mode terang' : 'Aktifkan mode gelap');
    const label = themeToggle.querySelector('[data-theme-label]');
    if (label) label.textContent = theme === 'dark' ? 'Light' : 'Dark';
    try { localStorage.setItem('garda-theme', theme); } catch (error) { console.warn('Theme preference unavailable', error.message); }
  };

  const applyLanguage = next => {
    language = next === 'en' ? 'en' : 'id';
    document.documentElement.lang = language;
    document.dispatchEvent(new CustomEvent('garda-language', {detail:language}));
    document.querySelectorAll('[data-i18n]').forEach(el => {
      const value = translations[language][el.dataset.i18n];
      if (value) el.innerHTML = value;
    });
    languageToggle.setAttribute('aria-label', language === 'id' ? 'Switch to English' : 'Beralih ke Bahasa Indonesia');
    try { localStorage.setItem('garda-language', language); } catch (error) { console.warn('Language preference unavailable', error.message); }
  };

  themeToggle.addEventListener('click', () => applyTheme(theme === 'dark' ? 'light' : 'dark'));
  languageToggle.addEventListener('click', () => applyLanguage(language === 'id' ? 'en' : 'id'));
  applyTheme(theme);
  applyLanguage(language);
}

function setupMotion() {
  const root = document.documentElement;
  root.dataset.motionReady = 'true';
  const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const intro = $('site-intro');
  let shouldPlay = false;
  try {
    shouldPlay = !sessionStorage.getItem('garda-intro-seen');
    if (shouldPlay) sessionStorage.setItem('garda-intro-seen', '1');
  } catch (error) {
    shouldPlay = true;
    console.warn('Intro session state unavailable', error.message);
  }

  const finishIntro = () => {
    intro?.remove();
    document.querySelectorAll('.hero-reveal').forEach(el => el.classList.add('is-visible'));
  };

  if (!intro || reduced || !shouldPlay) {
    finishIntro();
  } else if (window.gsap) {
    const { gsap } = window;
    const holes = intro.querySelector('.site-intro__holes');
    const wordmark = intro.querySelector('.site-intro__wordmark');
    gsap.set(holes, { scale: 0.08, transformOrigin: '50% 50%' });
    gsap.timeline({ defaults: { ease: 'power3.inOut' }, onComplete: finishIntro })
      .to(wordmark, { autoAlpha: 0, y: -12, duration: 0.35, ease: 'power2.out' }, 0.62)
      .to(holes, { scale: 32, duration: 1.15 }, 0.25)
      .to(intro, { autoAlpha: 0, duration: 0.3, ease: 'power2.in' }, 1.42);
    window.setTimeout(finishIntro, 2500);
  } else {
    intro.classList.add('is-running');
    window.setTimeout(finishIntro, 2100);
    intro.addEventListener('animationend', event => {
      if (event.animationName === 'intro-overlay-exit') finishIntro();
    }, { once: true });
  }

  const revealObserver = 'IntersectionObserver' in window ? new IntersectionObserver(entries => entries.forEach(entry => {
    if (entry.isIntersecting) {
      entry.target.classList.add('is-visible');
      revealObserver.unobserve(entry.target);
    }
  }), { threshold: 0.12, rootMargin: '0px 0px -40px' }) : null;

  document.querySelectorAll('.scroll-reveal').forEach(el => revealObserver ? revealObserver.observe(el) : el.classList.add('is-visible'));

  const links = [...document.querySelectorAll('nav a')], sections = links.map(link => document.querySelector(link.hash)).filter(Boolean);
  const navObserver = 'IntersectionObserver' in window ? new IntersectionObserver(entries => entries.forEach(entry => {
    if (entry.isIntersecting) {
      links.forEach(link => link.setAttribute('aria-current', link.hash === `#${entry.target.id}` ? 'true' : 'false'));
    }
  }), { rootMargin: '-25% 0px -60%' }) : null;
  sections.forEach(section => navObserver?.observe(section));

  const progress = document.querySelector('.scroll-progress span');
  const updateScroll = () => {
    const max = document.documentElement.scrollHeight - window.innerHeight;
    if (progress) progress.style.transform = `scaleX(${max > 0 ? window.scrollY / max : 0})`;
  };
  window.addEventListener('scroll', updateScroll, { passive: true });
  updateScroll();

  setupPortalScroll();
  setupFieldSwap();
  setupArchInteractions();
}

function setupPortalScroll() {
  const hero = document.querySelector('.portal-hero');
  const stage = hero?.querySelector('.portal-stage');
  if (!hero || !stage) return;

  const left = stage.querySelector('.portal-panel-left');
  const right = stage.querySelector('.portal-panel-right');
  const image = stage.querySelector('img');
  const wash = stage.querySelector('.portal-wash');
  const veil = stage.querySelector('.portal-veil');
  const dotLeft = stage.querySelector('.portal-dot-left');
  const dotRight = stage.querySelector('.portal-dot-right');
  const titleLeft = hero.querySelector('.portal-title-left');
  const titleRight = hero.querySelector('.portal-title-right');

  let currentEase = 0;
  let targetProgress = 0;
  let isTicking = false;

  const updateTransforms = (p) => {
    const clamped = Math.min(1, Math.max(0, p));
    const ease = clamped * clamped * (3 - 2 * clamped);

    if (left) left.style.transform = `translateX(${-ease * 105}%)`;
    if (right) right.style.transform = `translateX(${ease * 105}%)`;
    if (image) image.style.transform = `scale(${1.15 - ease * 0.15})`;
    if (wash) wash.style.opacity = `${ease * 0.35}`;
    if (veil) veil.style.opacity = `${0.25 - ease * 0.15}`;

    if (dotLeft) {
      dotLeft.style.transform = `translate(${-ease * 45}vw, ${-ease * 25}vh)`;
      dotLeft.style.opacity = `${1 - ease * 0.85}`;
    }
    if (dotRight) {
      dotRight.style.transform = `translate(${ease * 45}vw, ${ease * 25}vh)`;
      dotRight.style.opacity = `${1 - ease * 0.85}`;
    }

    if (titleLeft) titleLeft.style.transform = `translateX(${-ease * 25}px)`;
    if (titleRight) titleRight.style.transform = `translateX(${ease * 25}px)`;
  };

  const calculateProgress = () => {
    const rect = hero.getBoundingClientRect();
    const travel = Math.max(1, hero.offsetHeight - window.innerHeight);
    const raw = -rect.top / travel;
    targetProgress = Math.min(1, Math.max(0, raw));

    if (!isTicking) {
      isTicking = true;
      requestAnimationFrame(function animate() {
        currentEase += (targetProgress - currentEase) * 0.25;
        if (Math.abs(targetProgress - currentEase) < 0.001) {
          currentEase = targetProgress;
          updateTransforms(currentEase);
          isTicking = false;
        } else {
          updateTransforms(currentEase);
          requestAnimationFrame(animate);
        }
      });
    }
  };

  window.addEventListener('scroll', calculateProgress, { passive: true });
  window.addEventListener('resize', calculateProgress, { passive: true });
  calculateProgress();

  // Gentle greeting preview animation on initial load to show that the portal is active
  setTimeout(() => {
    if (window.scrollY < 30) {
      let t = 0;
      const teaserTimer = setInterval(() => {
        t += 0.03;
        if (t <= 0.18) {
          updateTransforms(t);
        } else if (t <= 0.36) {
          updateTransforms(0.36 - t);
        } else {
          clearInterval(teaserTimer);
          calculateProgress();
        }
      }, 25);
    }
  }, 600);
}

function setupFieldSwap() {
  const tabs = document.querySelectorAll('[data-field-perspective]');
  if (!tabs.length) return;
  tabs.forEach(tab => {
    tab.addEventListener('click', () => {
      tabs.forEach(t => t.classList.remove('active'));
      tab.classList.add('active');
      const p = tab.dataset.fieldPerspective;
      const detail = $('clock-detail');
      if (p === 'compute') {
        if (detail) detail.textContent = 'Perspektif Komputasi: 16 Lane SIMD MAC aktif memproses perkalian bobot dan aktivasi Q8.8 (3.556 siklus).';
        if (modules.some(m => m.id === 'garda_neural_logic_top')) selectBlock('garda_neural_logic_top');
      } else if (p === 'control') {
        if (detail) detail.textContent = 'Perspektif Kontrol: HPS ARM Cortex-A9 mengirimkan observasi 74-fitur dan costmap 128×128 via UART 115200 8N1.';
        if (modules.some(m => m.id === 'garda_costmap_manager')) selectBlock('garda_costmap_manager');
      } else if (p === 'safety') {
        if (detail) detail.textContent = 'Perspektif Keselamatan: Logika gerbang memeriksa batasan trajektori (v, ω), watchdog 2 ms, dan validitas TTL 20 ms. Intersepsi <1 µs.';
        if (modules.some(m => m.id === 'garda_safety_security_gate')) selectBlock('garda_safety_security_gate');
      }
    });
  });
}

function setupArchInteractions() {
  const rows = document.querySelectorAll('[data-arch-block]');
  if (!rows.length) return;
  const selectArchBlock = blockId => {
    rows.forEach(r => r.classList.toggle('active', r.dataset.archBlock === blockId));
    document.querySelectorAll('.svg-node').forEach(node => node.classList.toggle('active', node.id === `svg-${blockId}`));
  };
  rows.forEach(row => {
    row.addEventListener('click', () => selectArchBlock(row.dataset.archBlock));
  });
  document.querySelectorAll('.svg-node').forEach(node => {
    node.style.cursor = 'pointer';
    node.addEventListener('click', () => {
      const blockId = node.id.replace('svg-', '');
      selectArchBlock(blockId);
      const matchingRow = document.querySelector(`[data-arch-block="${blockId}"]`);
      if (matchingRow) matchingRow.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    });
  });
}

async function init() {
  try {
    const response = await fetch('data/rtl-catalog.json');
    if (!response.ok) throw new Error('Catalog ' + response.status);
    catalog = await response.json();
    modules = catalog.modules.map(m => ({ ...m, name: m.module, color: colors[m.group] || '#7C97FF' }));
    ttModules = catalog.asic_modules.map(m => ({ ...m, name: m.module, color: colors.asic, group: 'tt' }));
    try {
      scene = new GardaScene(canvas, { onSelect: id => selectBlock(id), onModeChange: m => setMode(m, true) });
      scene.setBlocks(modules);
    } catch (error) {
      $('scene-error').hidden = false;
      console.warn('WebGL unavailable', error.message);
    }
    setMode('board');
    const requested = new URLSearchParams(location.search).get('module');
    if (requested && modules.some(m => m.id === requested)) {
      setMode('die');
      selectBlock(requested);
    } else {
      selectBlock('garda_uart_top');
    }
    renderFlow();
    document.documentElement.dataset.appReady = 'true';
    window.gardaExplorer = { get mode() { return mode; }, get selected() { return selected?.id; }, setMode, selectBlock, evaluateGate, get scene() { return scene?.state; } };
  } catch (error) {
    $('block-description').textContent = 'Katalog belum berhasil dimuat. Jalankan server lokal dengan START_DASHBOARD.bat atau buka website yang sudah diterbitkan.';
    $('scene-error').hidden = false;
    console.error(error);
  }
  loadEvidence();
}

function setMode(next, fromScene = false) {
  if (next === 'tt') next = 'die';
  if (!['board', 'die'].includes(next)) return;
  mode = next;
  $('module-search').value = '';
  const tt = mode === 'tt';
  if (scene) {
    scene.setBlocks(tt ? ttModules : modules);
    if (!fromScene) scene.setMode(mode);
  }
  document.querySelectorAll('[data-mode]').forEach(b => {
    const yes = b.dataset.mode === mode;
    b.setAttribute('aria-selected', String(yes));
    b.tabIndex = yes ? 0 : -1;
  });
  $('mode-chip').textContent = tt ? 'NEURAL CORE / IHP HISTORIS' : mode === 'die' ? '20 MODUL / 19 BERKAS' : 'MAX 10 / 10M50DAF484C7G';
  $('stage-kicker').textContent = tt ? 'TINYTAPEOUT EXPLORER' : mode === 'die' ? 'LOGICAL RTL EXPLORER' : 'BOARD EXPLORER';
  $('stage-title').innerHTML = tt ? '24 → 64 → 64 → 4.<br>Dual MAC. Model tetap.' : mode === 'die' ? 'Dari masukan peta.<br>Ke gerbang keputusan.' : 'Board DE10-Lite.<br>Target FPGA MAX 10.';
  $('block-count').textContent = tt ? '4 modul' : '20 modul / 19 berkas';
  renderLegend();
  if (!selected || !available().some(m => m.id === selected.id)) selectBlock(tt ? 'tt_um_wlmoi_garda_neural_logic' : 'garda_uart_top');
}

function renderLegend() {
  const query = $('module-search').value.toLowerCase().trim();
  const list = available().filter(m => [m.id, m.title, ...m.ports.map(p => p.name)].join(' ').toLowerCase().includes(query));
  $('legend').innerHTML = list.map(m => `<button type="button" data-block="${esc(m.id)}" aria-current="${m.id === selected?.id}"><span class="swatch" style="background:${m.color}"></span><span>${esc(m.title)}</span><small>${esc(m.module.startsWith('garda_') ? m.module.slice(6) : m.module)}</small></button>`).join('') || (query ? '<p class="empty-search">Tidak ada modul atau port yang cocok.</p>' : '');
  $('legend').querySelectorAll('button').forEach(b => b.addEventListener('click', () => {
    if (mode === 'board') setMode('die');
    selectBlock(b.dataset.block);
  }));
}

function selectBlock(id) {
  if (id === 'hps') {
    selected = { id: 'hps', title: 'HPS ARM Cortex-A9', module: 'Cyclone V HPS', explanation: 'Processor ARM untuk Linux dan perangkat lunak host. HPS adalah bagian dari SoC Cyclone V. Tidak ada modul RTL HPS buatan tim dalam katalog ini.', highlights: ['FPGA fabric dan HPS berada pada SoC yang sama', 'Jalur neural dan DWA GARDA berada pada fabric', 'Integrasi HPS menuju sensor dan motor merupakan tahap sistem berikutnya'], ports: [], group: 'board' };
  } else {
    selected = modules.find(m => m.id === id);
    if (!selected) return;
  }
  if (selected.group === 'tt' && mode !== 'tt') setMode('tt');
  if (selected.group !== 'tt' && mode === 'tt') setMode('die');
  scene?.select(id);
  $('block-index').textContent = selected.id === 'hps' ? 'HPS / HOST' : `${String(available().findIndex(m => m.id === id) + 1).padStart(2, '0')} / ${available().length}`;
  $('block-title').textContent = selected.title;
  $('block-name').textContent = selected.module;
  $('block-description').textContent = selected.explanation;
  $('block-highlights').innerHTML = (selected.highlights || []).slice(0, 4).map(x => `<p>${esc(x)}</p>`).join('');
  $('selection-scope').textContent = selected.group === 'tt' ? 'ASIC / NEURAL' : selected.group === 'alternate' ? 'ALTERNATIF' : selected.id === 'hps' ? 'HOST' : 'FPGA';
  const ports = selected.ports || [], ni = ports.filter(p => p.direction === 'input').length, no = ports.filter(p => p.direction === 'output').length;
  $('io-summary').innerHTML = ports.length ? `<span>${ni} port input</span><span>${no} port output</span>` : '';
  $('source-ref').textContent = selected.source ? `${selected.source.path}:${selected.source.line}` : 'Referensi perangkat Terasic';
  $('show-source').disabled = !selected.file;
  $('show-ports').disabled = !selected.file;
  document.querySelectorAll('[data-block]').forEach(b => b.setAttribute('aria-current', String(b.dataset.block === id)));
  if (!$('module-detail').hidden) openDetail(false);
}

async function openDetail(scroll = true) {
  if (!selected?.file) return;
  const current = selected, serial = ++sourceRequest;
  $('module-detail').hidden = false;
  $('detail-title').textContent = current.title;
  $('ports-body').innerHTML = current.ports.map(p => `<tr><td>${esc(p.name)}</td><td>${p.direction === 'input' ? 'IN' : p.direction === 'output' ? 'OUT' : 'INOUT'}</td><td>${esc(p.bits)} bit${p.signed ? ' signed' : ''}</td></tr>`).join('');
  $('code-file').textContent = current.file;
  const file = 'source/' + current.file;
  $('download-source').href = file;
  $('code-content').textContent = 'Memuat source…';
  if (scroll) $('module-detail').scrollIntoView({ behavior: 'smooth', block: 'start' });
  try {
    const r = await fetch(file);
    if (!r.ok) throw Error(r.status);
    const text = await r.text();
    if (serial !== sourceRequest) return;
    const lines = text.split('\n');
    const limited = lines.length > 400 ? lines.slice(0, 400) : lines;
    $('code-content').innerHTML = limited.map((s, i) => `<span class="ln">${i + 1}</span>${esc(s)}`).join('\n') + (lines.length > 400 ? '\n\n// Pratinjau 400 baris. Unduh berkas untuk source lengkap.' : '');
  } catch (error) {
    if (serial === sourceRequest) $('code-content').textContent = 'Source belum tersedia. Gunakan repository atau paket unduhan.';
  }
}

function renderFlow() {
  const nodes = [
    ['01', 'Masukan host', 'garda_uart_protocol', '8 byte / CRC8'],
    ['02', 'Peta & konfigurasi', 'garda_costmap_manager', '128 × 128 / 8 bit'],
    ['03', 'Empat rollout tile', 'garda_rollout_tile', '4 × 128 kandidat'],
    ['04', 'Pilih kandidat', 'garda_best_candidate_selector', 'skor 32 bit / indeks 9 bit'],
    ['05', 'Gerbang izin', 'garda_safety_security_gate', 'permit 1 bit / fault 8 bit']
  ];
  $('flow').innerHTML = nodes.map(([n, t, id, width]) => `<button type="button" data-flow="${id}"><span>${n}</span><h3>${t}</h3><code>${id}</code><small>${width}</small></button>`).join('');
  document.querySelectorAll('[data-flow]').forEach(b => b.addEventListener('click', () => {
    setMode('die');
    selectBlock(b.dataset.flow);
    $('explorer').scrollIntoView({ behavior: 'smooth' });
  }));
}

async function loadEvidence() {
  try {
    const r = await fetch('data/tinytapeout-report.json');
    if (!r.ok) throw Error(r.status);
    report = await r.json();
    const current = report.current_rtl || {};
    $('tt-functional').textContent = current.status === 'pass' ? 'RTL PASS' : 'Uji ulang';
    $('current-rtl-status').textContent = current.result || 'Perlu uji ulang';
    $('current-rtl-status').dataset.status = current.status || 'rerun_required';
    $('current-rtl-summary').textContent = current.summary || 'Bukti RTL aktif belum tersedia.';
    $('current-rtl-activity').textContent = current.activity_summary || '';
    $('tt-summary').textContent = report.summary || 'Hasil RTL dan implementasi fisik memiliki cakupan terpisah.';
    $('evidence-date').textContent = `Diperiksa ${report.checked_date || '15 Oktober 2026'}`;
    $('tt-checks').innerHTML = (report.checks || []).map(c => `<div class="tt-check ${c.status === 'pass' ? '' : 'pending'}"><span>${esc(c.label)}</span><strong>${esc(c.result)}</strong></div>`).join('');
  } catch (error) {
    $('current-rtl-status').textContent = 'Bukti belum dimuat';
    $('current-rtl-summary').textContent = 'Buka laporan repository untuk hasil pengujian.';
    $('current-rtl-activity').textContent = '';
    $('tt-functional').textContent = 'Lihat bukti repository';
    $('tt-summary').textContent = 'Laporan pengujian terbaru belum berhasil dimuat.';
    $('tt-report-link').hidden = true;
  }
}

document.querySelectorAll('[data-mode]').forEach(b => {
  b.addEventListener('click', () => setMode(b.dataset.mode));
  b.addEventListener('keydown', e => {
    if (['ArrowLeft', 'ArrowRight'].includes(e.key)) {
      e.preventDefault();
      const tabs = [...document.querySelectorAll('[data-mode]')];
      const i = tabs.indexOf(b);
      const next = tabs[(i + (e.key === 'ArrowRight' ? 1 : -1) + tabs.length) % tabs.length];
      setMode(next.dataset.mode);
      next.focus();
    }
  });
});

$('show-source').addEventListener('click', () => openDetail());
$('show-ports').addEventListener('click', () => openDetail());
$('close-detail').addEventListener('click', () => { $('module-detail').hidden = true; });
$('module-search').addEventListener('input', renderLegend);
$('reset-camera').addEventListener('click', () => scene?.reset());
$('explode').addEventListener('click', e => {
  const b = e.currentTarget, yes = b.getAttribute('aria-pressed') !== 'true';
  b.setAttribute('aria-pressed', String(yes));
  scene?.setExploded(yes);
});
$('rotate').addEventListener('click', e => {
  const b = e.currentTarget, yes = b.getAttribute('aria-pressed') !== 'true';
  b.setAttribute('aria-pressed', String(yes));
  scene?.setAutoRotate(yes);
});
$('select-gate').addEventListener('click', () => {
  setMode('die');
  selectBlock('garda_safety_security_gate');
});

const faults = [
  ['estop', 'Emergency stop', 0],
  ['protective_stop', 'Protective stop', 0],
  ['map_ok', 'Peta tidak valid', 1],
  ['cfg_ok', 'Konfigurasi tidak valid', 1],
  ['ready', 'Belum ready', 1],
  ['arithmetic_fault', 'Fault aritmetika', 0],
  ['timeout', 'Timeout', 0],
  ['result_valid', 'Hasil tidak valid', 1]
];

$('fault-toggles').innerHTML = faults.map(([id, label]) => `<label><input type="checkbox" data-fault="${id}"><span>${label}</span></label>`).join('');

function updateGate() {
  const state = { candidate_v: Number($('candidate-v').value), candidate_w: Number($('candidate-w').value) };
  faults.forEach(([id, , invert]) => {
    const active = document.querySelector(`[data-fault="${id}"]`).checked;
    state[id] = invert ? Number(!active) : Number(active);
  });
  const r = evaluateGate(state);
  $('candidate-value').textContent = state.candidate_v;
  $('omega-value').textContent = state.candidate_w;
  $('permit-value').textContent = r.motor_enable;
  $('v-value').textContent = r.v_command;
  $('w-value').textContent = r.omega_command;
  $('fault-reason').textContent = `${faultDescriptions[r.fault_code]} Fault ${r.fault_code}.`;
  $('gate-result').className = 'gate-result ' + (r.motor_enable ? 'permitted' : 'blocked');
}

document.querySelectorAll('[data-fault],#candidate-v,#candidate-w').forEach(el => el.addEventListener('input', updateGate));
updateGate();
init();
setupPreferences();
setupMotion();

// Accessible compact navigation; engineering controls keep their own handlers.
const mobileMenu = document.querySelector('.mobile-menu-toggle');
const mainNavigation = document.getElementById('main-navigation');
function closeNavigation(){const wasOpen=mobileMenu?.getAttribute('aria-expanded')==='true';mobileMenu?.setAttribute('aria-expanded','false');mainNavigation?.classList.remove('is-open');if(wasOpen)mobileMenu.focus();}
mobileMenu?.addEventListener('click',()=>{const open=mobileMenu.getAttribute('aria-expanded')!=='true';mobileMenu.setAttribute('aria-expanded',String(open));mainNavigation?.classList.toggle('is-open',open);if(open)mainNavigation?.querySelector('a')?.focus();});
mainNavigation?.querySelectorAll('a').forEach(link=>link.addEventListener('click',closeNavigation));
document.addEventListener('keydown',event=>{if(event.key==='Escape')closeNavigation();});
