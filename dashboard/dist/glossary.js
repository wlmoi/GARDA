// Glossary: plain-language explanations of the technical words on the page.
// The first occurrence of each term per section gets a dotted underline (CSS
// Custom Highlight API, so the DOM and the page localization are untouched);
// tapping it opens a short explanation.  A glossary list (top-bar button) is
// the accessible way in and works without the Highlight API.
const isId = () => document.documentElement.lang === 'id';
const TERMS = [
  ['lidar', /\bLiDAR\b/, 'LiDAR', 'LiDAR',
    'Light Detection and Ranging: a sensor that fires laser pulses and times their echoes to measure how far away things are, building a 3D picture of the surroundings.',
    'Light Detection and Ranging: sensor yang menembakkan pulsa laser dan mengukur waktu pantulannya untuk mengetahui jarak benda, sehingga terbentuk gambaran 3D di sekitarnya.'],
  ['riscv', /\bRISC-V\b/, 'RISC-V', 'RISC-V',
    'An open, royalty-free instruction set for processors, the "language" a CPU understands. Anyone may build a RISC-V chip without paying licence fees.',
    'Set instruksi prosesor yang terbuka dan bebas royalti, yaitu "bahasa" yang dipahami CPU. Siapa pun boleh membuat chip RISC-V tanpa membayar lisensi.'],
  ['tinyqv', /\bTinyQV\b/, 'TinyQV', 'TinyQV',
    'A small RISC-V processor designed for Tiny Tapeout chips. On GARDA-chip it is the control CPU.',
    'Prosesor RISC-V kecil yang dirancang untuk chip Tiny Tapeout. Di GARDA-chip, ia berperan sebagai CPU pengendali.'],
  ['prism', /\bPRISM\b/, 'PRISM', 'PRISM',
    'A programmable state machine on GARDA-chip that handles communication protocols (UART, SPI, CAN, Ethernet and more) directly in hardware.',
    'Mesin keadaan (state machine) terprogram di GARDA-chip yang menangani protokol komunikasi (UART, SPI, CAN, Ethernet, dan lainnya) langsung di hardware.'],
  ['rtl', /\bRTL\b/, 'RTL', 'RTL',
    'Register-Transfer Level: the circuit written as code (here in Verilog) that describes how data moves between registers on every clock tick. It is simulated first, then turned into a chip.',
    'Register-Transfer Level: rangkaian yang ditulis sebagai kode (di sini dengan Verilog) yang menggambarkan perpindahan data antar-register di setiap detak clock. Kode ini disimulasikan dulu, lalu diubah menjadi chip.'],
  ['verilog', /\bVerilog\b/, 'Verilog', 'Verilog',
    'A hardware description language: code that describes a digital circuit instead of a program.',
    'Bahasa deskripsi hardware: kode yang menggambarkan rangkaian digital, bukan program biasa.'],
  ['testbench', /\btestbench(?:es)?\b/i, 'Testbench', 'Testbench',
    'Simulation code that feeds a design with test inputs and checks that its outputs are correct.',
    'Kode simulasi yang memberi masukan uji ke sebuah desain dan memeriksa apakah keluarannya benar.'],
  ['fpga', /\bFPGA\b/, 'FPGA', 'FPGA',
    'Field-Programmable Gate Array: a reprogrammable chip whose logic is rewired by loading a file. It lets a design run on real hardware before a custom chip is made.',
    'Field-Programmable Gate Array: chip yang logikanya bisa diatur ulang dengan memuat sebuah file. Desain bisa dijalankan di hardware nyata sebelum chip khusus dibuat.'],
  ['bitstream', /\bbitstream\b/i, 'Bitstream', 'Bitstream',
    'The configuration file loaded into an FPGA to turn it into a specific circuit (here, the .sof file).',
    'File konfigurasi yang dimuat ke FPGA agar menjadi rangkaian tertentu (di sini, file .sof).'],
  ['asic', /\bASIC\b/, 'ASIC', 'ASIC',
    'Application-Specific Integrated Circuit: a chip manufactured for one job. Faster and more power-efficient than an FPGA, but its circuit is fixed once made.',
    'Application-Specific Integrated Circuit: chip yang dibuat khusus untuk satu tugas. Lebih cepat dan hemat daya dibanding FPGA, tetapi rangkaiannya tetap setelah dibuat.'],
  ['mac', /\bMAC\b/, 'MAC', 'MAC',
    'Multiply-accumulate: multiply two numbers and add the result to a running total. A neural network is mostly a huge number of these; GARDA computes 16 at once.',
    'Multiply-accumulate: mengalikan dua angka lalu menambahkan hasilnya ke total berjalan. Jaringan saraf sebagian besar terdiri dari operasi ini; GARDA menghitung 16 sekaligus.'],
  ['simd', /\bSIMD\b/, 'SIMD', 'SIMD',
    'Single Instruction, Multiple Data: one command applied to many numbers at the same time, like 16 calculators pressing the same button together.',
    'Single Instruction, Multiple Data: satu perintah dijalankan pada banyak angka sekaligus, seperti 16 kalkulator yang menekan tombol yang sama bersamaan.'],
  ['q88', /\bQ8\.8\b/, 'Q8.8 fixed-point', 'Fixed-point Q8.8',
    'A number format with 8 bits for the whole part and 8 bits for the fraction. Simpler and cheaper in hardware than floating point, at slightly lower precision.',
    'Format angka dengan 8 bit untuk bagian bulat dan 8 bit untuk pecahan. Lebih sederhana dan murah di hardware dibanding floating point, dengan presisi sedikit lebih rendah.'],
  ['relu', /\bReLU\b/, 'ReLU', 'ReLU',
    'A simple step inside neural networks: negative numbers become 0, positive numbers pass through unchanged.',
    'Langkah sederhana di dalam jaringan saraf: angka negatif menjadi 0, angka positif diteruskan apa adanya.'],
  ['inference', /\b[Ii]nferen(?:ce|si)\b/, 'Inference', 'Inferensi',
    'Running a trained AI model on new input to get an answer (here: sensor data in, a proposed motion out). Training happens beforehand; inference is the "using" step.',
    'Menjalankan model AI yang sudah dilatih pada data baru untuk mendapat jawaban (di sini: data sensor masuk, usulan gerak keluar). Pelatihan dilakukan sebelumnya; inferensi adalah tahap "pemakaian".'],
  ['quant', /\b[Qq]uantization\b|\b[Kk]uantisasi\b/, 'Quantization', 'Kuantisasi',
    'Shrinking an AI model\'s numbers to fewer bits (for example 32-bit floating point to 16-bit fixed point) so it runs smaller and faster in hardware.',
    'Memperkecil angka-angka model AI menjadi lebih sedikit bit (misalnya dari floating point 32 bit ke fixed point 16 bit) agar lebih kecil dan cepat di hardware.'],
  ['rl', /\b[Rr]einforcement learning\b/, 'Reinforcement learning', 'Reinforcement learning',
    'Training an AI by trial and error: the model earns rewards for good actions and learns to repeat them.',
    'Melatih AI dengan cara coba-coba: model mendapat "hadiah" untuk tindakan yang baik dan belajar mengulanginya.'],
  ['clock', /\bclock\b/i, 'Clock', 'Clock',
    'A chip\'s heartbeat: a signal that ticks millions of times a second. Each tick (one clock cycle) moves the computation one step forward.',
    'Detak jantung chip: sinyal yang berdetak jutaan kali per detik. Setiap detak (satu siklus clock) memajukan perhitungan satu langkah.'],
  ['mhz', /\bMHz\b/, 'MHz', 'MHz',
    'Megahertz: millions of cycles per second. A 50 MHz clock ticks 50,000,000 times a second.',
    'Megahertz: jutaan siklus per detik. Clock 50 MHz berdetak 50.000.000 kali per detik.'],
  ['us', /µs/, 'µs (microsecond)', 'µs (mikrodetik)',
    'One millionth of a second. 71 µs is roughly 1/14,000 of a second, far quicker than a blink.',
    'Sepersejuta detik. 71 µs kira-kira 1/14.000 detik, jauh lebih cepat dari kedipan mata.'],
  ['latency', /\b[Ll]aten(?:cy|si)\b/, 'Latency', 'Latensi',
    'The delay between an input and the answer. Lower latency means a faster reaction.',
    'Jeda antara masukan dan jawaban. Latensi yang lebih rendah berarti reaksi lebih cepat.'],
  ['uart', /\bUART\b/, 'UART', 'UART',
    'A simple serial link that sends data one bit at a time over two wires, a classic way for a computer and a chip to talk.',
    'Jalur serial sederhana yang mengirim data satu bit demi satu bit lewat dua kabel; cara klasik komputer dan chip berkomunikasi.'],
  ['watchdog', /\b[Ww]atchdog\b/, 'Watchdog', 'Watchdog',
    'A safety timer that must be reset regularly. If the AI stops answering in time, the watchdog runs out and the hardware stops the motors.',
    'Timer keselamatan yang harus di-reset secara rutin. Jika AI berhenti menjawab tepat waktu, watchdog habis dan hardware menghentikan motor.'],
  ['estop', /\bE-stop\b|\b[Ee]mergency stop\b/, 'E-stop', 'E-stop',
    'Emergency stop: a button or signal that immediately cuts the motors, whatever the software is doing.',
    'Emergency stop: tombol atau sinyal yang langsung memutus motor, apa pun yang sedang dilakukan perangkat lunak.'],
  ['motorenable', /\bmotor_enable\b/, 'motor_enable', 'motor_enable',
    'The single signal (1 bit) that allows the motors to move: 1 means they may run, 0 means they are cut off. Only GARDA\'s safety gate controls it.',
    'Satu sinyal (1 bit) yang mengizinkan motor bergerak: 1 berarti boleh jalan, 0 berarti diputus. Hanya gerbang keselamatan GARDA yang mengendalikannya.'],
  ['fault', /\bfault\b/i, 'Fault', 'Fault',
    'Here: an abnormal condition (a timeout, an invalid map, an arithmetic error) that the safety gate treats as a reason to stop the motors.',
    'Di sini: kondisi tidak normal (timeout, peta tidak valid, kesalahan aritmetika) yang membuat gerbang keselamatan menghentikan motor.'],
  ['costmap', /\b[Cc]ostmap\b/, 'Costmap', 'Costmap',
    'A grid map in which every cell stores how risky or blocked that spot is, so the planner can choose a safe path.',
    'Peta berbentuk kisi yang setiap selnya menyimpan seberapa berisiko atau terhalang titik itu, agar perencana jalur bisa memilih jalan yang aman.'],
  ['dwa', /\bDWA\b/, 'DWA', 'DWA',
    'Dynamic Window Approach: a path-planning method that tries many combinations of speed and turning and picks the safest one that still makes progress.',
    'Dynamic Window Approach: metode perencanaan jalur yang mencoba banyak kombinasi kecepatan dan belokan, lalu memilih yang paling aman tetapi tetap maju.'],
  ['ros2', /\bROS 2\b/, 'ROS 2', 'ROS 2',
    'Robot Operating System 2: a widely used open-source software framework for building robot applications.',
    'Robot Operating System 2: kerangka perangkat lunak open-source yang banyak dipakai untuk membangun aplikasi robot.'],
  ['tinytapeout', /\bTiny ?Tapeout\b/, 'Tiny Tapeout', 'Tiny Tapeout',
    'An educational programme that puts many small designs on one shared chip, so students and hobbyists can have real silicon made affordably.',
    'Program edukasi yang menaruh banyak desain kecil dalam satu chip bersama, sehingga pelajar dan penghobi bisa membuat silikon nyata dengan biaya terjangkau.'],
  ['tapeout', /\b[Tt]apeout\b/, 'Tapeout', 'Tapeout',
    'The moment a finished chip layout is sent to the factory for manufacturing. Before tapeout the design can still change; after it, the production masks are made.',
    'Saat layout chip yang sudah jadi dikirim ke pabrik untuk diproduksi. Sebelum tapeout desain masih bisa diubah; setelahnya, masker produksi dibuat.'],
  ['gdsii', /\bGDSII\b/, 'GDSII', 'GDSII',
    'The standard file format for a chip\'s final layout: every shape, on every layer, that the factory will print onto silicon.',
    'Format file standar untuk layout akhir chip: setiap bentuk di setiap lapisan yang akan dicetak pabrik ke atas silikon.'],
  ['netlist', /\bnetlist\b/i, 'Netlist', 'Netlist',
    'The list of all logic cells in a design and the wires connecting them, produced from the RTL code by synthesis.',
    'Daftar semua sel logika dalam desain beserta kabel penghubungnya, dihasilkan dari kode RTL melalui sintesis.'],
  ['drc', /\bDRC\b/, 'DRC', 'DRC',
    'Design Rule Check: an automatic check that every shape in the layout obeys the factory\'s rules (minimum widths, spacing). 0 errors means it can be manufactured.',
    'Design Rule Check: pemeriksaan otomatis bahwa setiap bentuk di layout mematuhi aturan pabrik (lebar minimum, jarak). 0 error berarti bisa diproduksi.'],
  ['lvs', /\bLVS\b/, 'LVS', 'LVS',
    'Layout Versus Schematic: an automatic check that the drawn layout really forms the same circuit as the design. 0 errors means what is drawn is what was designed.',
    'Layout Versus Schematic: pemeriksaan otomatis bahwa layout yang digambar benar-benar membentuk rangkaian yang sama dengan desainnya. 0 error berarti yang digambar sesuai rancangan.'],
  ['signoff', /\b[Ss]ign-?off\b/, 'Sign-off', 'Sign-off',
    'The final set of checks (DRC, LVS, timing) a chip must pass before it is ready to be manufactured.',
    'Rangkaian pemeriksaan akhir (DRC, LVS, timing) yang harus dilalui chip sebelum siap diproduksi.'],
].map(([key, re, en, id, den, did]) => ({ key, re, en, id, den, did }));

const SKIP = 'script,style,code,pre,button,a,select,option,input,textarea,label,nav,svg,canvas,dialog,.topbar,.judge-hud,.judge-fab,.gloss-pop,[data-gloss-skip],.gi,.robot-path,.swap-tab,.mode-tabs,.clock-stages,.dataflow-node,.mac-lanes,.cat-pill,.status-pill';
const hasHighlights = 'highlights' in CSS && typeof Highlight === 'function';
let marks = [];      // { range, term }

// Only running text: paragraphs, list items and definitions, never headings,
// labels or UI.  Each term is marked once on the whole page, where it first
// appears, so the page is not covered in underlines.
const PROSE = 'p, li, dd';
const NOT_PROSE = 'h1, h2, h3, h4, h5, h6, .mono-eyebrow, .eyebrow, .kicker, .stat-lbl, .def-metric, .def-code, .corner-val, .corner-id, th, .hero-metrics, .robot-readout, #robot-status, .scope-note, .inference-time';
function scan() {
  marks = [];
  const root = document.getElementById('main-content') || document.body;
  const seen = new Set();   // term keys already marked on this page
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  while (walker.nextNode()) {
    const node = walker.currentNode, text = node.textContent;
    if (!text.trim() || !/[A-Za-zµ]/.test(text)) continue;
    const parent = node.parentElement;
    if (!parent || parent.closest(SKIP) || parent.closest('[hidden]')) continue;
    if (!parent.closest(PROSE) || parent.closest(NOT_PROSE)) continue;
    if (!parent.getClientRects().length) continue;   // not rendered (collapsed details, hidden panels)
    const taken = [];
    for (const term of TERMS) {
      if (seen.has(term.key)) continue;
      const m = term.re.exec(text);
      if (!m) continue;
      const a = m.index, b = a + m[0].length;
      if (taken.some(([x, y]) => a < y && b > x)) continue;   // e.g. "Tapeout" inside "Tiny Tapeout"
      taken.push([a, b]); seen.add(term.key);
      const range = document.createRange(); range.setStart(node, a); range.setEnd(node, b);
      marks.push({ range, term });
    }
  }
  if (hasHighlights) CSS.highlights.set('garda-gloss', new Highlight(...marks.map(m => m.range)));
}
let timer = 0;
const rescan = () => { clearTimeout(timer); timer = setTimeout(scan, 250); };
document.addEventListener('garda-localized', rescan);
document.addEventListener('garda-language', () => { closePop(); rescan(); renderList(); });
addEventListener('load', rescan);
rescan();

// ---------- hit test: which term (if any) is under the pointer ----------
function caretAt(x, y) {
  if (document.caretPositionFromPoint) { const p = document.caretPositionFromPoint(x, y); return p && { node: p.offsetNode, offset: p.offset }; }
  if (document.caretRangeFromPoint) { const r = document.caretRangeFromPoint(x, y); return r && { node: r.startContainer, offset: r.startOffset }; }
  return null;
}
function termAt(x, y) {
  const c = caretAt(x, y);
  if (!c || c.node.nodeType !== Node.TEXT_NODE) return null;
  for (const m of marks) {
    if (m.range.startContainer !== c.node) continue;
    if (c.offset >= m.range.startOffset && c.offset <= m.range.endOffset) {
      // the caret can land just outside a word: confirm the point is inside the word's box
      for (const r of m.range.getClientRects()) if (x >= r.left - 2 && x <= r.right + 2 && y >= r.top - 3 && y <= r.bottom + 3) return m;
    }
  }
  return null;
}

// ---------- popover ----------
const pop = document.createElement('div');
pop.className = 'gloss-pop'; pop.hidden = true; pop.setAttribute('role', 'dialog'); pop.dataset.i18nSkip = '';
pop.innerHTML = '<p class="gloss-kicker"></p><h3 class="gloss-term"></h3><p class="gloss-def"></p><div class="gloss-actions"><button type="button" class="gloss-all"></button><button type="button" class="gloss-close" aria-label="Close">×</button></div>';
document.body.appendChild(pop);
let openTerm = null;
function openPop(m) {
  const t = m.term, I = isId();
  openTerm = m;
  pop.querySelector('.gloss-kicker').textContent = I ? 'Glosarium' : 'Glossary';
  pop.querySelector('.gloss-term').textContent = I ? t.id : t.en;
  pop.querySelector('.gloss-def').textContent = I ? t.did : t.den;
  pop.querySelector('.gloss-all').textContent = I ? 'Semua istilah' : 'All terms';
  pop.querySelector('.gloss-close').setAttribute('aria-label', I ? 'Tutup' : 'Close');
  pop.setAttribute('aria-label', (I ? 'Arti istilah ' : 'Meaning of ') + (I ? t.id : t.en));
  pop.hidden = false;
  const r = m.range.getBoundingClientRect(), w = pop.offsetWidth, h = pop.offsetHeight, pad = 12;
  let left = Math.min(Math.max(pad, r.left + r.width / 2 - w / 2), innerWidth - w - pad);
  let top = r.bottom + 10;
  if (top + h > innerHeight - pad) top = Math.max(pad, r.top - h - 10);
  pop.style.left = left + 'px'; pop.style.top = top + 'px';
  openedAt = scrollY;
  pop.querySelector('.gloss-close').focus({ preventScroll: true });
}
function closePop() { pop.hidden = true; openTerm = null; }
pop.querySelector('.gloss-close').addEventListener('click', closePop);
pop.querySelector('.gloss-all').addEventListener('click', () => { closePop(); openList(); });

document.addEventListener('click', e => {
  if (e.target.closest('.gloss-pop, .gloss-dialog')) return;
  if (e.target.closest(SKIP)) { if (!pop.hidden) closePop(); return; }
  const m = termAt(e.clientX, e.clientY);
  if (m) { e.preventDefault(); openPop(m); } else if (!pop.hidden) closePop();
});
document.addEventListener('keydown', e => { if (e.key === 'Escape' && !pop.hidden) closePop(); });
// close on a real scroll only: smooth scrolling can still be settling when the popover opens
let openedAt = 0;
addEventListener('scroll', () => { if (!pop.hidden && Math.abs(scrollY - openedAt) > 40) closePop(); }, { passive: true });
addEventListener('resize', () => { if (!pop.hidden) closePop(); });
// desktop: a help cursor over terms
let raf = 0;
document.addEventListener('pointermove', e => {
  if (e.pointerType !== 'mouse' || raf) return;
  raf = requestAnimationFrame(() => { raf = 0; document.documentElement.classList.toggle('gloss-hover', !!termAt(e.clientX, e.clientY)); });
}, { passive: true });

// ---------- full glossary list ----------
const dlg = document.createElement('dialog');
dlg.className = 'gloss-dialog'; dlg.dataset.i18nSkip = '';
dlg.innerHTML = '<div class="gloss-dialog-head"><h2></h2><button type="button" class="gloss-dialog-close">×</button></div><p class="gloss-dialog-intro"></p><dl class="gloss-list"></dl>';
document.body.appendChild(dlg);
function renderList() {
  const I = isId();
  dlg.querySelector('h2').textContent = I ? 'Glosarium' : 'Glossary';
  dlg.querySelector('.gloss-dialog-close').setAttribute('aria-label', I ? 'Tutup glosarium' : 'Close glossary');
  dlg.querySelector('.gloss-dialog-intro').textContent = I
    ? 'Istilah teknis di halaman ini, dijelaskan dengan bahasa sehari-hari. Ketuk kata bergaris bawah titik-titik di halaman untuk melihat artinya langsung.'
    : 'The technical words on this page, explained in everyday language. Tap any word with a dotted underline on the page to see its meaning in place.';
  const items = [...TERMS].sort((a, b) => (I ? a.id : a.en).localeCompare(I ? b.id : b.en, I ? 'id' : 'en', { sensitivity: 'base' }));
  dlg.querySelector('.gloss-list').innerHTML = items.map(t => `<div><dt>${I ? t.id : t.en}</dt><dd>${I ? t.did : t.den}</dd></div>`).join('');
}
function openList() { renderList(); if (dlg.showModal) dlg.showModal(); else dlg.setAttribute('open', ''); dlg.querySelector('.gloss-dialog-close').focus(); }
dlg.querySelector('.gloss-dialog-close').addEventListener('click', () => dlg.close());
dlg.addEventListener('click', e => { if (e.target === dlg) dlg.close(); });
renderList();

// top-bar button
const btn = document.createElement('button');
btn.type = 'button'; btn.className = 'gloss-btn'; btn.dataset.i18nSkip = '';
btn.innerHTML = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 4.5A2.5 2.5 0 0 1 7.5 2H19v17H7.5A2.5 2.5 0 0 0 5 21.5zM5 21.5A2.5 2.5 0 0 1 7.5 19H19v3H7.5A2.5 2.5 0 0 1 5 21.5z" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"/><path d="M9 7h6M9 10.5h4" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg>';
const label = () => { btn.setAttribute('aria-label', isId() ? 'Buka glosarium istilah teknis' : 'Open the glossary of technical terms'); btn.title = isId() ? 'Glosarium' : 'Glossary'; };
label(); document.addEventListener('garda-language', label);
btn.addEventListener('click', openList);
document.querySelector('.site-settings')?.prepend(btn);
// also a menu entry (the navigation drawer), which is the way in on phones where the top bar has no room
const nav = document.getElementById('main-navigation');
if (nav && !nav.querySelector('a[href="#glossary"]')) {
  const a = document.createElement('a'); a.href = '#glossary'; a.className = 'nav-gloss'; a.textContent = 'Glossary';
  nav.appendChild(a);
}
document.addEventListener('click', e => { if (e.target.closest('a[href="#glossary"]')) { e.preventDefault(); document.querySelector('.mobile-menu-toggle[aria-expanded="true"]')?.click(); openList(); } }, true);
window.gardaGlossary = { count: () => marks.length, terms: () => marks.map(m => m.term.key), open: openList, termAt };
