const section=document.getElementById('verification');
const table=section.querySelector('table');
const rows=[...table.tBodies[0].rows];
const labels=['Evidence','Subsystem','Result','Method','Status'];
rows.forEach(row=>[...row.cells].forEach((cell,i)=>cell.dataset.label=labels[i]));
const categories=['pass','projection','historical','pass','pending','simulation'];
const toolbar=document.createElement('div');toolbar.className='verification-toolbar';
toolbar.innerHTML=`<label>Search results<input type="search" placeholder="Test name or metric" aria-label="Search results pengujian"></label><label>Status<select aria-label="Status filter"><option value="all">All statuses</option><option value="pass">Verified PASS</option><option value="projection">Calculated</option><option value="historical">Historical build</option><option value="pending">ASIC status</option><option value="simulation">Simulation</option></select></label><p role="status" aria-live="polite"></p>`;
section.querySelector('.verification-table-wrap').before(toolbar);
const input=toolbar.querySelector('input'),filter=toolbar.querySelector('select'),result=toolbar.querySelector('[role=status]');
function update(){let shown=0;rows.forEach((row,i)=>{row.hidden=!(filter.value==='all'||filter.value===categories[i])||!row.textContent.toLocaleLowerCase().includes(input.value.trim().toLocaleLowerCase());if(!row.hidden)shown++;});result.textContent=`${shown} / ${rows.length} results`;}
input.addEventListener('input',update);filter.addEventListener('change',update);update();
const signoff=document.createElement('details');signoff.className='signoff-status';signoff.innerHTML='<summary>Status signoff fisik</summary><p>Belum signoff. Laporan yang tersedia belum mencatat kelulusan DRC, LVS, dan timing untuk target SKY130. PASS RTL menyatakan hasil uji logika sesuai model referensi, bukan persetujuan fabrikasi.</p>';
section.querySelector('.verification-table-wrap').after(signoff);
