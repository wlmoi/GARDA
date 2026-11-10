const section=document.querySelector('.engineering-gallery');
const viewport=section.querySelector('.gallery-viewport');
const cards=[...section.querySelectorAll('.gallery-card')];
const prev=section.querySelector('.gallery-prev'),next=section.querySelector('.gallery-next');
const count=section.querySelector('.gallery-count'),progress=section.querySelector('.gallery-progress span');
const reduced=matchMedia('(prefers-reduced-motion: reduce)');
let tween,frame=0,pinTrigger=null;
function position(card){return card.offsetLeft-cards[0].offsetLeft;}
function current(){let best=0;cards.forEach((card,i)=>{if(Math.abs(position(card)-viewport.scrollLeft)<Math.abs(position(cards[best])-viewport.scrollLeft))best=i;});return best;}
function update(){frame=0;const i=current(),max=viewport.scrollWidth-viewport.clientWidth;count.textContent=`${String(i+1).padStart(2,'0')} / 06`;prev.disabled=viewport.scrollLeft<=2;next.disabled=viewport.scrollLeft>=max-2;progress.style.transform=`scaleX(${max?viewport.scrollLeft/max:1})`;}
function go(delta){const index=Math.max(0,Math.min(cards.length-1,current()+delta));const target=Math.min(position(cards[index]),viewport.scrollWidth-viewport.clientWidth);tween?.kill();if(pinTrigger){const max=viewport.scrollWidth-viewport.clientWidth;const y=pinTrigger.start+(max?target/max:0)*(pinTrigger.end-pinTrigger.start);const state={y:scrollY};tween=window.gsap.to(state,{y,duration:.65,ease:'power2.inOut',onUpdate:()=>window.scrollTo({top:state.y,behavior:'instant'})});return;}if(!window.gsap||reduced.matches){viewport.scrollLeft=target;update();return;}viewport.classList.add('is-tweening');const state={x:viewport.scrollLeft};tween=window.gsap.to(state,{x:target,duration:.65,ease:'power3.inOut',onUpdate:()=>{viewport.scrollLeft=state.x;update();},onComplete:()=>{viewport.classList.remove('is-tweening');update();}});}
prev.addEventListener('click',()=>go(-1));next.addEventListener('click',()=>go(1));
viewport.addEventListener('scroll',()=>{if(!frame)frame=requestAnimationFrame(update);},{passive:true});
function stop(){tween?.kill();viewport.classList.remove('is-tweening');}
viewport.addEventListener('pointerdown',stop,{passive:true});viewport.addEventListener('wheel',stop,{passive:true});
viewport.addEventListener('keydown',e=>{if(e.target!==viewport)return;if(e.key==='ArrowRight'||e.key==='ArrowLeft'){e.preventDefault();go(e.key==='ArrowRight'?1:-1);}});
new ResizeObserver(()=>{stop();update();}).observe(viewport);update();
if(window.gsap&&!reduced.matches){const observer=new IntersectionObserver(entries=>{if(entries.some(e=>e.isIntersecting)){window.gsap.fromTo(section.querySelector('.gallery-heading'),{y:24,opacity:0},{y:0,opacity:1,duration:.7,ease:'power2.out'});observer.disconnect();}},{threshold:.15});observer.observe(section);}
const dialog=document.querySelector('.diagram-dialog');let opener;
section.querySelectorAll('.gallery-open').forEach(button=>button.addEventListener('click',()=>{stop();opener=button;dialog.querySelector('h2').textContent=button.dataset.title;const img=dialog.querySelector('img');img.src=button.dataset.image;img.alt=button.dataset.title;dialog.querySelector('.diagram-caption').textContent=button.dataset.caption;dialog.querySelector('a').href=button.dataset.image;dialog.showModal();}));
dialog.querySelector('button').addEventListener('click',()=>dialog.close());dialog.addEventListener('click',e=>{if(e.target===dialog){const r=dialog.getBoundingClientRect();if(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom)dialog.close();}});dialog.addEventListener('close',()=>opener?.focus({preventScroll:true}));

// Static ES modules: wait for fonts, decoded images and two layout frames before pinning.
async function initializePinnedGallery(){
 if(!window.gsap||!window.ScrollTrigger)return;
 const gsap=window.gsap,ScrollTrigger=window.ScrollTrigger;
 gsap.registerPlugin(ScrollTrigger);
 ScrollTrigger.config({ignoreMobileResize:true});
 await Promise.race([Promise.allSettled([
  document.fonts.ready,
  ...[...section.querySelectorAll('img')].map(img=>{img.loading='eager';return img.decode();})
 ]),new Promise(resolve=>setTimeout(resolve,2500))]);
 await new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)));
 const media=gsap.matchMedia();
 media.add('(prefers-reduced-motion: no-preference) and (min-height: 760px)',()=>{
  if(!section.isConnected||viewport.clientWidth<1)return;
  section.classList.add('gallery-pinned');
  const state={x:0};
  const max=()=>Math.max(0,viewport.scrollWidth-viewport.clientWidth);
  const animation=gsap.fromTo(state,{x:0},{x:max,ease:'none',onUpdate:()=>{viewport.scrollLeft=state.x;update();},scrollTrigger:{
   trigger:section,start:()=>`top ${document.querySelector('.topbar').offsetHeight+12}px`,
   end:()=>`+=${Math.max(innerHeight,Math.min(max(),innerHeight*3))}`,
   pin:true,pinSpacing:true,scrub:.35,anticipatePin:1,invalidateOnRefresh:true,
   onRefresh:self=>{pinTrigger=self;update();}
  }});
  pinTrigger=animation.scrollTrigger;section.dataset.scrollMode='pinned';
  let refreshTimer;
  const resize=new ResizeObserver(()=>{clearTimeout(refreshTimer);refreshTimer=setTimeout(()=>ScrollTrigger.refresh(),150);});
  resize.observe(viewport);
  ScrollTrigger.refresh();
  return()=>{resize.disconnect();clearTimeout(refreshTimer);pinTrigger=null;section.classList.remove('gallery-pinned');section.dataset.scrollMode='swipe';};
 });
}
initializePinnedGallery().catch(error=>console.warn('Gallery remains available with swipe controls:',error.message));

