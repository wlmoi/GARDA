const dialog=document.getElementById('proposal-viewer');
const opener=document.querySelector('.proposal-cta');
const canvas=dialog.querySelector('canvas'),pages=dialog.querySelector('.proposal-pages'),status=dialog.querySelector('.proposal-status');
const prev=dialog.querySelector('.proposal-prev'),next=dialog.querySelector('.proposal-next'),number=dialog.querySelector('input');
let documentPromise,pageNumber=1,total=0,sequence=0,renderTask,resizeTimer,lastSize='';
function load(){return documentPromise??=(async()=>{const pdf=await import('./vendor/pdf.mjs');pdf.GlobalWorkerOptions.workerSrc=new URL('./vendor/pdf.worker.mjs',import.meta.url).href;return pdf.getDocument({url:new URL(opener.getAttribute('href'),location.href).href}).promise;})();}
async function render(){const ticket=++sequence;renderTask?.cancel();prev.disabled=next.disabled=true;status.textContent='Loading proposal…';pages.classList.add('is-rendering');try{
 const doc=await load();if(ticket!==sequence||!dialog.open)return;total=doc.numPages;pageNumber=Math.max(1,Math.min(pageNumber,total));number.value=pageNumber;number.max=total;dialog.querySelector('.proposal-page-total').textContent=`/ ${total}`;
 const page=await doc.getPage(pageNumber);if(ticket!==sequence||!dialog.open)return;
 const original=page.getViewport({scale:1});const padding=innerWidth<=600?16:32;const width=Math.max(1,pages.clientWidth-padding),height=Math.max(1,pages.clientHeight-padding);const viewport=page.getViewport({scale:Math.min(width/original.width,height/original.height)});const ratio=Math.min(devicePixelRatio||1,2);

 canvas.width=Math.ceil(viewport.width*ratio);canvas.height=Math.ceil(viewport.height*ratio);canvas.style.width=`${viewport.width}px`;canvas.style.height=`${viewport.height}px`;canvas.setAttribute('aria-label',`GARDA proposal, page ${pageNumber} of ${total}`);
 renderTask=page.render({canvasContext:canvas.getContext('2d'),viewport,transform:ratio===1?undefined:[ratio,0,0,ratio,0,0]});await renderTask.promise;if(ticket!==sequence)return;
 status.textContent='';pages.classList.remove('is-rendering');pages.scrollTop=0;prev.disabled=pageNumber===1;next.disabled=pageNumber===total;
 const text=await page.getTextContent();if(ticket===sequence)dialog.querySelector('.proposal-accessible-text').textContent=text.items.map(item=>item.str).join(' ');
 }catch(error){if(error.name==='RenderingCancelledException'||ticket!==sequence)return;status.textContent='The preview could not load. Use “Open full PDF” to read the proposal.';documentPromise=undefined;console.warn('Proposal preview:',error.message);}}
opener.addEventListener('click',event=>{event.preventDefault();dialog.showModal();lastSize=`${pages.clientWidth}x${pages.clientHeight}`;render();});
dialog.querySelector('.proposal-close').addEventListener('click',()=>dialog.close());dialog.addEventListener('close',()=>{sequence++;renderTask?.cancel();opener.focus({preventScroll:true});});
prev.addEventListener('click',()=>{if(pageNumber>1){pageNumber--;render();}});next.addEventListener('click',()=>{if(pageNumber<total){pageNumber++;render();}});number.addEventListener('change',()=>{pageNumber=Number(number.value)||1;render();});
dialog.addEventListener('keydown',event=>{if(event.target.matches('input,select'))return;if(event.key==='ArrowRight'&&!next.disabled){event.preventDefault();next.click();}if(event.key==='ArrowLeft'&&!prev.disabled){event.preventDefault();prev.click();}});
new ResizeObserver(()=>{const size=`${pages.clientWidth}x${pages.clientHeight}`;if(dialog.open&&size!==lastSize){lastSize=size;clearTimeout(resizeTimer);resizeTimer=setTimeout(render,120);}}).observe(pages);
const contents=dialog.querySelector('.proposal-contents'),contentsToggle=dialog.querySelector('.proposal-sections-toggle');
const sections=[['Cover',1],['Contents',2],['Executive summary',3],['Problem',4],['Users and validation',6],['Specifications',9],['Chip architecture and silicon',10],['Working prototype and evidence',15],['Development roadmap',18],['Impact and benefits',21],['Business model',24],['The team',25]];
sections.forEach(([label,page])=>{const button=document.createElement('button');button.type='button';button.textContent=label;const badge=document.createElement('span');badge.textContent=`p. ${page}`;button.append(badge);button.addEventListener('click',()=>{pageNumber=page;contents.hidden=true;contentsToggle.setAttribute('aria-expanded','false');contentsToggle.focus();render();});contents.append(button);});
contentsToggle.addEventListener('click',()=>{contents.hidden=!contents.hidden;contentsToggle.setAttribute('aria-expanded',String(!contents.hidden));if(!contents.hidden){const toolbar=dialog.querySelector('.proposal-toolbar');contents.style.top=`${toolbar.offsetTop+toolbar.offsetHeight}px`;contents.querySelector('button').focus();}});
dialog.addEventListener('close',()=>{contents.hidden=true;contentsToggle.setAttribute('aria-expanded','false');});
let touchStart;
pages.addEventListener('pointerdown',e=>{if(e.pointerType==='mouse')return;touchStart={x:e.clientX,y:e.clientY};});
pages.addEventListener('pointercancel',()=>{touchStart=null;});
pages.addEventListener('pointerup',e=>{if(!touchStart)return;const dx=e.clientX-touchStart.x,dy=e.clientY-touchStart.y;touchStart=null;if(Math.abs(dx)>50&&Math.abs(dx)>Math.abs(dy)*1.3){if(dx<0&&!next.disabled)next.click();else if(dx>0&&!prev.disabled)prev.click();}});
