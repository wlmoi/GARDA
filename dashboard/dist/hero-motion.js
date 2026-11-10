const hero = document.getElementById('hero');
const reduced = matchMedia('(prefers-reduced-motion: reduce)');
const gsap = window.gsap;
function reveal() {
 hero.classList.add('hero-ready');
 if (!gsap || reduced.matches) return;
 gsap.fromTo('.nav-event-logo', {opacity:0,y:16}, {opacity:1,y:0,duration:.8,delay:.2});
 // the hero answers the intro: title lines rise in turn, then the lead
 gsap.fromTo('.portal-title > span, .portal-title > em', {opacity:0,yPercent:55,filter:'blur(8px)'}, {opacity:1,yPercent:0,filter:'blur(0px)',duration:.9,stagger:.16,ease:'power3.out',clearProps:'filter'});
 gsap.fromTo('.portal-copy .lead, .portal-copy .eyebrow', {opacity:0,y:18}, {opacity:1,y:0,duration:.8,stagger:.1,delay:.25,ease:'power2.out'});
 // opacity and blur only: the frame's own transform centres it and must not be overwritten
 gsap.fromTo('.hero-drone', {opacity:0,filter:'blur(12px) saturate(.6)'}, {opacity:1,filter:'blur(0px) saturate(1)',duration:1.2,ease:'power3.out',clearProps:'filter'});
 gsap.fromTo('.hero-actions > *', {opacity:0,y:20}, {opacity:1,y:0,stagger:.12,duration:.7,delay:.35});
 gsap.fromTo('.hero-metrics > *', {opacity:0,y:20}, {opacity:1,y:0,stagger:.12,duration:.8,delay:.55});
}
if(document.querySelector('.boot-intro')) document.addEventListener('garda-intro-complete',reveal,{once:true}); else reveal();
if (gsap && !reduced.matches) {
 const observer = new IntersectionObserver(entries => entries.forEach(entry => {
  if (!entry.isIntersecting) return;
  const el = entry.target;
  if (el.matches('.people-section')) {
   gsap.fromTo('.people-heading', {opacity:0,y:30}, {opacity:1,y:0,duration:.8});
   gsap.fromTo('.person-card', {opacity:0,y:36}, {opacity:1,y:0,duration:.75,stagger:.1,ease:'power3.out'});
  } else {
   const tl = gsap.timeline();
   tl.fromTo(el.querySelector('.mono-eyebrow'),{opacity:0,x:-20},{opacity:1,x:0,duration:.6})
    .fromTo(el.querySelectorAll('.closing-title span'),{opacity:0,y:45,clipPath:'inset(100% 0 0 0)'},{opacity:1,y:0,clipPath:'inset(0% 0 0 0)',duration:.9,stagger:.18,ease:'power3.out'},'-.25')
    .fromTo(el.querySelector('.closing-desc'),{opacity:0,y:20},{opacity:1,y:0,duration:.7},'-.4');
   gsap.fromTo(el.querySelector('.closing-wordmark-cropped'),{opacity:.12,x:-30},{opacity:.35,x:0,duration:1.8,ease:'power2.out'});
  }
  observer.unobserve(el);
 }),{threshold:.12});
 document.querySelectorAll('.people-section,.editorial-closing').forEach(el=>observer.observe(el));
 document.querySelectorAll('.proposal-cta,.person-card').forEach(el=>{
  el.addEventListener('pointerenter',()=>gsap.to(el,{y:-4,duration:.25,ease:'power2.out'}));
  el.addEventListener('pointerleave',()=>gsap.to(el,{y:0,duration:.3,ease:'power2.out'}));
 });
}
let scheduled=false;
function update(){scheduled=false;if(reduced.matches)return;const r=hero.getBoundingClientRect();const p=Math.max(0,Math.min(1,-r.top/Math.max(1,r.height)));hero.style.setProperty('--hero-travel',`${p*-28}px`);hero.style.setProperty('--hero-turn',`${p*4}deg`);}
addEventListener('scroll',()=>{if(!scheduled){scheduled=true;requestAnimationFrame(update);}},{passive:true});update();
