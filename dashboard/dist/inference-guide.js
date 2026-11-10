const playback=document.getElementById('robot-playback');
const guide=document.querySelector('.inference-guide');
playback.addEventListener('change',()=>{if(playback.value!=='inference')return;requestAnimationFrame(()=>{if(!guide.open)guide.showModal();});});
function close(){guide.close();}
guide.querySelector('.guide-close').addEventListener('click',close);guide.querySelector('.guide-stay').addEventListener('click',close);
guide.querySelector('.guide-view').addEventListener('click',()=>{close();const target=document.getElementById('clock-explorer');target.scrollIntoView({behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'instant':'smooth',block:'start'});const title=document.getElementById('clock-title');title.setAttribute('tabindex','-1');title.focus({preventScroll:true});});
