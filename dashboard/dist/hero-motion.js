const hero=document.getElementById('hero');
const reduced=matchMedia('(prefers-reduced-motion: reduce)');
function reveal(){hero.classList.add('hero-ready');}
if(document.querySelector('.boot-intro'))document.addEventListener('garda-intro-complete',reveal,{once:true});else reveal();
let scheduled=false;
function update(){scheduled=false;if(reduced.matches)return;const r=hero.getBoundingClientRect();const p=Math.max(0,Math.min(1,-r.top/Math.max(1,r.height)));hero.style.setProperty('--hero-travel',`${p*-28}px`);hero.style.setProperty('--hero-turn',`${p*4}deg`);}
addEventListener('scroll',()=>{if(!scheduled){scheduled=true;requestAnimationFrame(update);}},{passive:true});
update();
