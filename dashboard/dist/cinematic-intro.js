// Compositor-only intro: no WebGL context, per-frame JS or particle rendering.
const reduced = matchMedia('(prefers-reduced-motion: reduce)').matches;
let seen = false;
try { seen = sessionStorage.getItem('garda-boot-seen') === '1'; } catch {}
if (!reduced && !seen) start();
function start() {
 const overlay = document.createElement('div');
 overlay.className = 'boot-intro boot-lightweight';
 overlay.setAttribute('aria-hidden','true');
 overlay.innerHTML = '<div class="boot-circuit"><i></i><i></i><i></i><i></i></div><img class="boot-logo" src="assets/garda-intro-mark.svg" alt="">';
 document.body.append(overlay);
 const animations = [];
 let done = false;
 function finish() {
  if(done)return; done=true;
  animations.forEach(a=>a.cancel()); overlay.remove();
  removeEventListener('keydown',key);
  document.dispatchEvent(new Event('garda-intro-complete'));
  try { sessionStorage.setItem('garda-boot-seen','1'); } catch {}
 }
 function key(e){if(e.key==='Escape')finish();}
 addEventListener('keydown',key);
 const ease='cubic-bezier(.22,1,.36,1)';
 animations.push(overlay.querySelector('.boot-circuit').animate([
  {transform:'scale(.88) rotate(-8deg)',opacity:0},
  {transform:'scale(1) rotate(0deg)',opacity:.65,offset:.35},
  {transform:'scale(1.12) rotate(3deg)',opacity:0}
 ],{duration:1900,easing:ease,fill:'both'}));
 animations.push(overlay.querySelector('.boot-logo').animate([
  {transform:'scale(.92)',opacity:0},
  {transform:'scale(1)',opacity:1,offset:.25},
  {transform:'scale(1)',opacity:1,offset:.6},
  {transform:'scale(1.04)',opacity:0}
 ],{duration:1600,easing:ease,fill:'both'}));
 const fade=overlay.animate([{opacity:1},{opacity:0}],{delay:1400,duration:450,easing:'ease-out',fill:'forwards'});
 animations.push(fade);fade.finished.then(finish).catch(()=>{});
 setTimeout(finish,2400);
}
