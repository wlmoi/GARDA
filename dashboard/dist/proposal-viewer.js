const dialog=document.getElementById('proposal-viewer');
const opener=document.querySelector('.proposal-cta');
const canvas=dialog.querySelector('canvas'),pages=dialog.querySelector('.proposal-pages'),status=dialog.querySelector('.proposal-status');
const prev=dialog.querySelector('.proposal-prev'),next=dialog.querySelector('.proposal-next'),number=dialog.querySelector('input'),zoom=dialog.querySelector('select');
let documentPromise,pageNumber=1,total=0,sequence=0,renderTask,resizeTimer,lastWidth=0;
function load(){return documentPromise??=(async()=>{const pdf=await import('./vendor/pdf.mjs');pdf.GlobalWorkerOptions.workerSrc=new URL('./vendor/pdf.worker.mjs',import.meta.url).href;return pdf.getDocument(new URL(opener.getAttribute('href'),location.href).href).promise;})();}
async function render(){const ticket=++sequence;renderTask?.cancel();prev.disabled=next.disabled=true;status.textContent='Loading proposal…';try{
 const doc=await load();if(ticket!==sequence||!dialog.open)return;total=doc.numPages;pageNumber=Math.max(1,Math.min(pageNumber,total));number.value=pageNumber;number.max=total;dialog.querySelector('.proposal-page-total').textContent=`/ ${total}`;
 const page=await doc.getPage(pageNumber);if(ticket!==sequence||!dialog.open)return;
 const original=page.getViewport({scale:1});const width=Math.max(200,pages.clientWidth-(innerWidth<=600?16:32));const viewport=page.getViewport({scale:width/original.width*Number(zoom.value)});const ratio=Math.min(devicePixelRatio||1,1.75);
 canvas.width=Math.ceil(viewport.width*ratio);canvas.height=Math.ceil(viewport.height*ratio);canvas.style.width=`${viewport.width}px`;canvas.style.height=`${viewport.height}px`;canvas.setAttribute('aria-label',`GARDA proposal, page ${pageNumber} of ${total}`);
 renderTask=page.render({canvasContext:canvas.getContext('2d'),viewport,transform:ratio===1?undefined:[ratio,0,0,ratio,0,0]});await renderTask.promise;if(ticket!==sequence)return;
 status.textContent=`Page ${pageNumber} of ${total}`;pages.scrollTop=0;prev.disabled=pageNumber===1;next.disabled=pageNumber===total;
 const text=await page.getTextContent();if(ticket===sequence)dialog.querySelector('.proposal-accessible-text').textContent=text.items.map(item=>item.str).join(' ');
 }catch(error){if(error.name==='RenderingCancelledException'||ticket!==sequence)return;status.textContent='The preview could not load. Use “Open full PDF” to read the proposal.';documentPromise=undefined;console.warn('Proposal preview:',error.message);}}
opener.addEventListener('click',event=>{event.preventDefault();dialog.showModal();lastWidth=pages.clientWidth;render();});
dialog.querySelector('.proposal-close').addEventListener('click',()=>dialog.close());dialog.addEventListener('close',()=>{sequence++;renderTask?.cancel();opener.focus({preventScroll:true});});
prev.addEventListener('click',()=>{if(pageNumber>1){pageNumber--;render();}});next.addEventListener('click',()=>{if(pageNumber<total){pageNumber++;render();}});number.addEventListener('change',()=>{pageNumber=Number(number.value)||1;render();});zoom.addEventListener('change',render);
dialog.addEventListener('keydown',event=>{if(event.target.matches('input,select'))return;if(event.key==='ArrowRight'&&!next.disabled){event.preventDefault();next.click();}if(event.key==='ArrowLeft'&&!prev.disabled){event.preventDefault();prev.click();}});
new ResizeObserver(()=>{const width=pages.clientWidth;if(dialog.open&&width!==lastWidth){lastWidth=width;clearTimeout(resizeTimer);resizeTimer=setTimeout(render,150);}}).observe(pages);
