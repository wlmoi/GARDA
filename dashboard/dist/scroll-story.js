const story=document.querySelector('.signal-story');
const reduced=matchMedia('(prefers-reduced-motion: reduce)');
const mobile=matchMedia('(max-width:780px)');
const steps=[...story.querySelectorAll('.signal-step')];
let scheduled=false;
function draw(){scheduled=false;const rect=story.getBoundingClientRect();const distance=Math.max(1,story.offsetHeight-innerHeight);const p=reduced.matches||mobile.matches?1:Math.max(0,Math.min(1,(innerHeight*.15-rect.top)/distance));story.style.setProperty('--story-progress',p);steps.forEach((step,i)=>{const progress=Math.max(0,Math.min(1,p*3-i));step.style.setProperty('--step',progress);step.classList.toggle('is-current',progress>.5);});}
function schedule(){if(!scheduled){scheduled=true;requestAnimationFrame(draw);}}
addEventListener('scroll',schedule,{passive:true});addEventListener('resize',schedule,{passive:true});reduced.addEventListener('change',schedule);draw();
if(!reduced.matches&&'IntersectionObserver' in window){const observer=new IntersectionObserver(entries=>{entries.forEach(entry=>{if(entry.isIntersecting){entry.target.classList.remove('waiting');observer.unobserve(entry.target);}});},{threshold:.1});document.querySelectorAll('.section-editorial-header').forEach(el=>{el.classList.add('flow-section-title','waiting');observer.observe(el);});}
