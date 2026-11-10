const section=document.getElementById('verification');
const table=section.querySelector('table');
const rows=[...table.tBodies[0].rows];
const labels=['Evidence','Subsystem','Result','Method','Status'];
rows.forEach(row=>[...row.cells].forEach((cell,i)=>cell.dataset.label=labels[i]));
const categories=['pass','projection','historical','pass','asic','simulation'];
const toolbar=document.createElement('div');toolbar.className='verification-toolbar';
toolbar.innerHTML=`<label>Search results<input type="search" placeholder="Test name or metric" aria-label="Search results pengujian"></label><label>Status<select aria-label="Status filter"><option value="all">All statuses</option><option value="pass">Verified PASS</option><option value="projection">Calculated</option><option value="historical">Historical build</option><option value="asic">ASIC layout</option><option value="simulation">Simulation</option></select></label><p role="status" aria-live="polite"></p>`;
section.querySelector('.verification-table-wrap').before(toolbar);
const input=toolbar.querySelector('input'),filter=toolbar.querySelector('select'),result=toolbar.querySelector('[role=status]');
function update(){let shown=0;rows.forEach((row,i)=>{row.hidden=!(filter.value==='all'||filter.value===categories[i])||!row.textContent.toLocaleLowerCase().includes(input.value.trim().toLocaleLowerCase());if(!row.hidden)shown++;});result.dataset.i18nSkip='';result.textContent=`${shown} / ${rows.length} ${document.documentElement.lang==='id'?'hasil':'results'}`;}
input.addEventListener('input',update);filter.addEventListener('change',update);update();
document.addEventListener('garda-language',()=>setTimeout(update,0));
const signoff=document.createElement('details');signoff.className='signoff-status';signoff.dataset.i18n='judge-mode';signoff.innerHTML='<summary>Physical sign-off status</summary><p>The Tiny Tapeout chip, GARDA-chip (tt_um_garda_chip, IHP SG13CMOS5L), passes KLayout DRC and LVS with zero errors and meets setup timing at the typical corner; the slow corner is not met. It has not been submitted for fabrication yet. Full results: <a href="https://wlmoi.github.io/GARDA/GDSII/#evidence">GDSII explorer</a>. An RTL PASS means the logic matches its reference model; it is not a fabrication approval.</p>';
section.querySelector('.verification-table-wrap').after(signoff);
