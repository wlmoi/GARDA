import { GardaScene } from './scene.js';
import { evaluateGate, faultDescriptions } from './gate-model.js';

const $ = id => document.getElementById(id);
const esc = value => String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const colors = {host:'#54cce5',compute:'#33a5cc',memory:'#589bdb',control:'#9bfd08',safety:'#58fd37',neural:'#36bedb',alternate:'#a3c4d6',asic:'#6dbce5'};
let mode='board', selected, scene, catalog, report, sourceRequest=0;
let modules=[], ttModules=[];
const canvas=$('scene');
const available=()=>mode==='tt'?ttModules:modules;

function setupMotion(){
  const root=document.documentElement;
  root.dataset.motionReady='true';
  document.querySelectorAll('main > section:not(.intro)').forEach(section=>section.classList.add('scroll-reveal'));
  const reduced=window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const intro=$('site-intro');
  let shouldPlay=false;
  try{shouldPlay=!sessionStorage.getItem('garda-intro-seen');if(shouldPlay)sessionStorage.setItem('garda-intro-seen','1');}catch(error){shouldPlay=true;console.warn('Intro session state unavailable',error.message);}
  const finishIntro=()=>{intro?.remove();document.querySelectorAll('.hero-reveal').forEach(el=>el.classList.add('is-visible'));};
  if(!intro||reduced||!shouldPlay){finishIntro();}else{
    intro.classList.add('is-running');
    window.setTimeout(finishIntro,2100);
    intro.addEventListener('animationend',event=>{if(event.animationName==='intro-overlay-exit')finishIntro();},{once:true});
  }
  const revealObserver='IntersectionObserver' in window?new IntersectionObserver(entries=>entries.forEach(entry=>{if(entry.isIntersecting){entry.target.classList.add('is-visible');revealObserver.unobserve(entry.target);}}),{threshold:.12,rootMargin:'0px 0px -40px'}):null;
  document.querySelectorAll('.scroll-reveal').forEach(el=>revealObserver?revealObserver.observe(el):el.classList.add('is-visible'));
  const links=[...document.querySelectorAll('nav a')], sections=links.map(link=>document.querySelector(link.hash)).filter(Boolean);
  const navObserver='IntersectionObserver' in window?new IntersectionObserver(entries=>entries.forEach(entry=>{if(entry.isIntersecting){links.forEach(link=>link.setAttribute('aria-current',link.hash===`#${entry.target.id}`?'true':'false'));}}),{rootMargin:'-25% 0px -60%'}):null;
  sections.forEach(section=>navObserver?.observe(section));
  const progress=$('.scroll-progress span');
  const updateScroll=()=>{const max=document.documentElement.scrollHeight-window.innerHeight;progress.style.transform=`scaleX(${max>0?window.scrollY/max:0})`;};
  window.addEventListener('scroll',updateScroll,{passive:true});updateScroll();
}

async function init(){
  try {
    const response=await fetch('data/rtl-catalog.json');
    if(!response.ok)throw new Error('Catalog '+response.status);
    catalog=await response.json();
    modules=catalog.modules.map(m=>({...m,name:m.module,color:colors[m.group]||'#7d9fbd'}));
    ttModules=catalog.asic_modules.map(m=>({...m,name:m.module,color:colors.asic,group:'tt'}));
    try{scene=new GardaScene(canvas,{onSelect:id=>selectBlock(id),onModeChange:m=>setMode(m,true)});scene.setBlocks(modules);}catch(error){$('scene-error').hidden=false;console.warn('WebGL unavailable',error.message);}
    setMode('board');
    const requested=new URLSearchParams(location.search).get('module');
    if(requested&&modules.some(m=>m.id===requested)){setMode('die');selectBlock(requested);}
    else selectBlock('garda_uart_top');
    renderFlow();
    document.documentElement.dataset.appReady='true';
    window.gardaExplorer={get mode(){return mode;},get selected(){return selected?.id;},setMode,selectBlock,evaluateGate,get scene(){return scene?.state;}};
  }catch(error){$('block-description').textContent='Katalog belum berhasil dimuat. Jalankan server lokal dengan START_DASHBOARD.bat atau buka website yang sudah diterbitkan.';$('scene-error').hidden=false;console.error(error);}
  loadEvidence();
}
function setMode(next,fromScene=false){
  if(next==='tt')next='die';
  if(!['board','die'].includes(next))return;
  mode=next;
  $('module-search').value='';
  const tt=mode==='tt';
  if(scene){scene.setBlocks(tt?ttModules:modules);if(!fromScene)scene.setMode(mode);}
  document.querySelectorAll('[data-mode]').forEach(b=>{const yes=b.dataset.mode===mode;b.setAttribute('aria-selected',String(yes));b.tabIndex=yes?0:-1;});
  $('mode-chip').textContent=tt?'NEURAL CORE / IHP HISTORIS':mode==='die'?'20 MODUL / 19 BERKAS':'CYCLONE V SoC';
  $('stage-kicker').textContent=tt?'TINYTAPEOUT EXPLORER':mode==='die'?'LOGICAL RTL EXPLORER':'BOARD EXPLORER';
  $('stage-title').innerHTML=tt?'24 → 64 → 64 → 4.<br>Dual MAC. Model tetap.':mode==='die'?'Dari masukan peta.<br>Ke gerbang keputusan.':'Satu board.<br>Dua dunia komputasi.';
  $('block-count').textContent=tt?'4 modul': '20 modul / 19 berkas';
  renderLegend();
  if(!selected||!available().some(m=>m.id===selected.id))selectBlock(tt?'tt_um_wlmoi_garda_neural_logic':'garda_uart_top');
}
function renderLegend(){
  const query=$('module-search').value.toLowerCase().trim();
  const list=available().filter(m=>[m.id,m.title,...m.ports.map(p=>p.name)].join(' ').toLowerCase().includes(query));
  $('legend').innerHTML=list.map(m=>`<button type="button" data-block="${esc(m.id)}" aria-current="${m.id===selected?.id}"><span class="swatch" style="background:${m.color}"></span><span>${esc(m.title)}</span><small>${esc(m.module.startsWith('garda_') ? m.module.slice(6) : m.module)}</small></button>`).join('')||(query?'<p class="empty-search">Tidak ada modul atau port yang cocok.</p>':'');
  $('legend').querySelectorAll('button').forEach(b=>b.addEventListener('click',()=>{if(mode==='board')setMode('die');selectBlock(b.dataset.block);}));
}
function selectBlock(id){
  if(id==='hps'){
    selected={id:'hps',title:'HPS ARM Cortex-A9',module:'Cyclone V HPS',explanation:'Processor ARM untuk Linux dan perangkat lunak host. HPS adalah bagian dari SoC Cyclone V. Tidak ada modul RTL HPS buatan tim dalam katalog ini.',highlights:['FPGA fabric dan HPS berada pada SoC yang sama','Jalur neural dan DWA GARDA berada pada fabric','Integrasi HPS menuju sensor dan motor merupakan tahap sistem berikutnya'],ports:[],group:'board'};
  }else{selected=modules.find(m=>m.id===id);if(!selected)return;}
  if(selected.group==='tt'&&mode!=='tt')setMode('tt');
  if(selected.group!=='tt'&&mode==='tt')setMode('die');
  scene?.select(id);
  $('block-index').textContent=selected.id==='hps'?'HPS / HOST':`${String(available().findIndex(m=>m.id===id)+1).padStart(2,'0')} / ${available().length}`;
  $('block-title').textContent=selected.title;
  $('block-name').textContent=selected.module;
  $('block-description').textContent=selected.explanation;
  $('block-highlights').innerHTML=(selected.highlights||[]).slice(0,4).map(x=>`<p>${esc(x)}</p>`).join('');
  $('selection-scope').textContent=selected.group==='tt'?'ASIC / NEURAL':selected.group==='alternate'?'ALTERNATIF':selected.id==='hps'?'HOST':'FPGA';
  const ports=selected.ports||[],ni=ports.filter(p=>p.direction==='input').length,no=ports.filter(p=>p.direction==='output').length;
  $('io-summary').innerHTML=ports.length?`<span>${ni} port input</span><span>${no} port output</span>`:'';
  $('source-ref').textContent=selected.source?`${selected.source.path}:${selected.source.line}`:'Referensi perangkat Terasic';
  $('show-source').disabled=!selected.file;$('show-ports').disabled=!selected.file;
  document.querySelectorAll('[data-block]').forEach(b=>b.setAttribute('aria-current',String(b.dataset.block===id)));
  if(!$('module-detail').hidden)openDetail(false);
}
async function openDetail(scroll=true){
  if(!selected?.file)return;
  const current=selected,serial=++sourceRequest;
  $('module-detail').hidden=false;
  $('detail-title').textContent=current.title;
  $('ports-body').innerHTML=current.ports.map(p=>`<tr><td>${esc(p.name)}</td><td>${p.direction==='input'?'IN':p.direction==='output'?'OUT':'INOUT'}</td><td>${esc(p.bits)} bit${p.signed?' signed':''}</td></tr>`).join('');
  $('code-file').textContent=current.file;
  const file='source/'+current.file;
  $('download-source').href=file;
  $('code-content').textContent='Memuat source…';
  if(scroll)$('module-detail').scrollIntoView({behavior:'smooth',block:'start'});
  try{const r=await fetch(file);if(!r.ok)throw Error(r.status);const text=await r.text();if(serial!==sourceRequest)return;
    const lines=text.split('\n');const limited=lines.length>400?lines.slice(0,400):lines;
    $('code-content').innerHTML=limited.map((s,i)=>`<span class="ln">${i+1}</span>${esc(s)}`).join('\n')+(lines.length>400?'\n\n// Pratinjau 400 baris. Unduh berkas untuk source lengkap.':'');
  }catch(error){if(serial===sourceRequest)$('code-content').textContent='Source belum tersedia. Gunakan repository atau paket unduhan.';}
}
function renderFlow(){
  const nodes=[['01','Masukan host','garda_uart_protocol','8 byte / CRC8'],['02','Peta & konfigurasi','garda_costmap_manager','128 × 128 / 8 bit'],['03','Empat rollout tile','garda_rollout_tile','4 × 128 kandidat'],['04','Pilih kandidat','garda_best_candidate_selector','skor 32 bit / indeks 9 bit'],['05','Gerbang izin','garda_safety_security_gate','permit 1 bit / fault 8 bit']];
  $('flow').innerHTML=nodes.map(([n,t,id,width])=>`<button type="button" data-flow="${id}"><span>${n}</span><h3>${t}</h3><code>${id}</code><small>${width}</small></button>`).join('');
  document.querySelectorAll('[data-flow]').forEach(b=>b.addEventListener('click',()=>{setMode('die');selectBlock(b.dataset.flow);$('explorer').scrollIntoView({behavior:'smooth'});}));
}
async function loadEvidence(){
  try{const r=await fetch('data/tinytapeout-report.json');if(!r.ok)throw Error(r.status);report=await r.json();
    const current=report.current_rtl||{};
    $('tt-functional').textContent=current.status==='pass'?'RTL GARDA / PASS':'RTL aktif perlu uji ulang';
    $('current-rtl-status').textContent=current.result||'Perlu uji ulang';
    $('current-rtl-status').dataset.status=current.status||'rerun_required';
    $('current-rtl-summary').textContent=current.summary||'Bukti RTL aktif belum tersedia.';
    $('current-rtl-activity').textContent=current.activity_summary||'';
    $('tt-summary').textContent=report.summary||'Hasil RTL dan implementasi fisik memiliki cakupan terpisah.';
    $('evidence-date').textContent=`Diperiksa ${report.checked_date||'15 Oktober 2026'}`;
    $('tt-checks').innerHTML=(report.checks||[]).map(c=>`<div class="tt-check ${c.status==='pass'?'':'pending'}"><span>${esc(c.label)}</span><strong>${esc(c.result)}</strong></div>`).join('');
  }catch(error){$('current-rtl-status').textContent='Bukti belum dimuat';$('current-rtl-summary').textContent='Buka laporan repository untuk hasil pengujian.';$('current-rtl-activity').textContent='';$('tt-functional').textContent='Lihat bukti pengujian repository';$('tt-summary').textContent='Laporan pengujian terbaru belum berhasil dimuat. Status implementasi fisik tidak disimpulkan dari hasil simulasi.';$('tt-report-link').hidden=true;}
}
document.querySelectorAll('[data-mode]').forEach(b=>{b.addEventListener('click',()=>setMode(b.dataset.mode));b.addEventListener('keydown',e=>{if(['ArrowLeft','ArrowRight'].includes(e.key)){e.preventDefault();const tabs=[...document.querySelectorAll('[data-mode]')];const i=tabs.indexOf(b);const next=tabs[(i+(e.key==='ArrowRight'?1:-1)+tabs.length)%tabs.length];setMode(next.dataset.mode);next.focus();}});});
$('show-source').addEventListener('click',()=>openDetail());$('show-ports').addEventListener('click',()=>openDetail());$('close-detail').addEventListener('click',()=>{$('module-detail').hidden=true;});
$('module-search').addEventListener('input',renderLegend);
$('reset-camera').addEventListener('click',()=>scene?.reset());
$('explode').addEventListener('click',e=>{const b=e.currentTarget,yes=b.getAttribute('aria-pressed')!=='true';b.setAttribute('aria-pressed',String(yes));scene?.setExploded(yes);});
$('rotate').addEventListener('click',e=>{const b=e.currentTarget,yes=b.getAttribute('aria-pressed')!=='true';b.setAttribute('aria-pressed',String(yes));scene?.setAutoRotate(yes);});
$('select-gate').addEventListener('click',()=>{setMode('die');selectBlock('garda_safety_security_gate');});
const faults=[['estop','Emergency stop',0],['protective_stop','Protective stop',0],['map_ok','Peta tidak valid',1],['cfg_ok','Konfigurasi tidak valid',1],['ready','Belum ready',1],['arithmetic_fault','Fault aritmetika',0],['timeout','Timeout',0],['result_valid','Hasil tidak valid',1]];
$('fault-toggles').innerHTML=faults.map(([id,label])=>`<label><input type="checkbox" data-fault="${id}"><span>${label}</span></label>`).join('');
function updateGate(){
  const state={candidate_v:Number($('candidate-v').value),candidate_w:Number($('candidate-w').value)};
  faults.forEach(([id,,invert])=>{const active=document.querySelector(`[data-fault="${id}"]`).checked;state[id]=invert?Number(!active):Number(active);});
  const r=evaluateGate(state);
  $('candidate-value').textContent=state.candidate_v;$('omega-value').textContent=state.candidate_w;
  $('permit-value').textContent=r.motor_enable;$('v-value').textContent=r.v_command;$('w-value').textContent=r.omega_command;
  $('fault-reason').textContent=`${faultDescriptions[r.fault_code]} Fault ${r.fault_code}.`;
  $('gate-result').className='gate-result '+(r.motor_enable?'permitted':'blocked');
}
document.querySelectorAll('[data-fault],#candidate-v,#candidate-w').forEach(el=>el.addEventListener('input',updateGate));
updateGate();init();
setupMotion();
