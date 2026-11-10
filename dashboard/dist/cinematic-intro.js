import * as THREE from './vendor/three.module.min.js';
const reduced=matchMedia('(prefers-reduced-motion: reduce)').matches;
let seen=false;try{seen=sessionStorage.getItem('garda-boot-seen')==='1';}catch{}
if(!reduced&&!seen)start();
function start(){
 const overlay=document.createElement('div');overlay.className='boot-intro';overlay.setAttribute('aria-label','GARDA cinematic introduction');
 overlay.innerHTML='<img class="boot-logo" src="assets/garda-intro-mark.svg" alt="GARDA">';
 document.body.append(overlay);
 const theme=getComputedStyle(document.documentElement);
 const ground=theme.getPropertyValue('--color-ground-primary').trim()||'#050684';
 const accent=theme.getPropertyValue('--color-signal').trim()||'#9BFD08';
 const surface=theme.getPropertyValue('--color-ground-secondary').trim()||'#034AB6';
 const accentColor=new THREE.Color(accent);
 overlay.style.background=ground;
 const logo=overlay.querySelector('.boot-logo');
 logo.style.transition='none';logo.style.zIndex='2';
 overlay.style.pointerEvents='none';
 let renderer,raf,done=false;const resources=[];
 const finish=()=>{if(done)return;done=true;cancelAnimationFrame(raf);removeEventListener('resize',resize);removeEventListener('keydown',key);resources.forEach(r=>r.dispose());overlay.remove();document.dispatchEvent(new Event('garda-intro-complete'));renderer?.dispose();renderer?.forceContextLoss();try{sessionStorage.setItem('garda-boot-seen','1');}catch{}};
 const key=e=>{if(e.key==='Escape')finish();};addEventListener('keydown',key);
 let scene,camera,frames,signals,streaks;const dummy=new THREE.Object3D();const color=new THREE.Color();
 function resize(){if(!renderer)return;camera.aspect=innerWidth/innerHeight;camera.updateProjectionMatrix();renderer.setSize(innerWidth,innerHeight);}
 try{
 renderer=new THREE.WebGLRenderer({antialias:innerWidth>780,alpha:true});renderer.setPixelRatio(Math.min(devicePixelRatio,innerWidth<780?1.25:2));renderer.outputColorSpace=THREE.SRGBColorSpace;renderer.toneMapping=THREE.ACESFilmicToneMapping;overlay.prepend(renderer.domElement);
 scene=new THREE.Scene();scene.background=new THREE.Color(ground);renderer.setClearColor(ground,1);scene.fog=new THREE.FogExp2(ground,.025);camera=new THREE.PerspectiveCamera(65,innerWidth/innerHeight,.1,160);camera.position.z=4;
 scene.add(new THREE.AmbientLight(accent,.7));const keyLight=new THREE.DirectionalLight(0xffffff,2);keyLight.position.set(2,3,4);scene.add(keyLight);const light=new THREE.PointLight(accent,30,24);scene.add(light);
 const shape=new THREE.Shape();shape.moveTo(-3,-3);shape.lineTo(3,-3);shape.lineTo(3,3);shape.lineTo(-3,3);shape.closePath();const hole=new THREE.Path();hole.moveTo(-2.82,-2.82);hole.lineTo(-2.82,2.82);hole.lineTo(2.82,2.82);hole.lineTo(2.82,-2.82);hole.closePath();shape.holes.push(hole);
 const geometry=new THREE.ExtrudeGeometry(shape,{depth:.12,bevelEnabled:false});const metal=new THREE.MeshStandardMaterial({color:surface,metalness:.65,roughness:.4});const signalMaterial=new THREE.MeshBasicMaterial({color:0xffffff});resources.push(geometry,metal,signalMaterial);
 frames=new THREE.InstancedMesh(geometry,metal,16);signals=new THREE.InstancedMesh(geometry,signalMaterial,16);
 for(let i=0;i<16;i++){dummy.position.set(0,0,-5-i*3.2);dummy.rotation.z=i*.06;dummy.scale.setScalar(1);dummy.updateMatrix();frames.setMatrixAt(i,dummy.matrix);dummy.scale.setScalar(.97);dummy.updateMatrix();signals.setMatrixAt(i,dummy.matrix);signals.setColorAt(i,color.set(accent));}scene.add(frames,signals);
 const count=innerWidth<780?240:600;const positions=new Float32Array(count*6);for(let i=0;i<count;i++){const a=i*2.399,r=3.8+(i%23)/8,z=-i/count*60;positions.set([Math.cos(a)*r,Math.sin(a)*r,z,Math.cos(a)*r,Math.sin(a)*r,z-1.5],i*6);}const lines=new THREE.BufferGeometry();lines.setAttribute('position',new THREE.BufferAttribute(positions,3));const lm=new THREE.LineBasicMaterial({color:accent,transparent:true,opacity:.25});streaks=new THREE.LineSegments(lines,lm);scene.add(streaks);resources.push(lines,lm);
 resize();addEventListener('resize',resize);const began=performance.now();
 const smooth=t=>{const x=Math.max(0,Math.min(1,t));return x*x*(3-2*x);};
 const frame=now=>{if(done)return;const t=(now-began)/1000;
 const p=Math.max(0,Math.min(1,t/2.7));
 const e=p*p*p*(p*(p*6-15)+10);
 const opening=smooth(t/.35),logoExit=smooth((t-.9)/.8),landing=smooth((t-2.9)/.7);
 logo.style.opacity=String(opening*(1-logoExit));
 logo.style.transform=`scale(${.92+.12*logoExit})`;
 renderer.domElement.style.opacity=String(opening*(1-landing));
 // Only the closing transition reveals the page. The tunnel stays opaque.
 overlay.style.background=t>=2.9?'transparent':ground;
 camera.position.set(.2*Math.sin(Math.PI*p)*Math.sin(2*Math.PI*p),0,4-60*e);
 camera.rotation.z=.025*Math.sin(Math.PI*p);
 light.position.copy(camera.position);lm.opacity=.13*Math.sin(Math.PI*p);
 for(let i=0;i<16;i++){
  const distance=(-5-i*3.2)-camera.position.z;
  const pulse=Math.exp(-distance*distance/22);
  signals.setColorAt(i,color.copy(accentColor).multiplyScalar(.3+.7*pulse));
 }
 signals.instanceColor.needsUpdate=true;
 renderer.render(scene,camera);if(t>=3.6)finish();else raf=requestAnimationFrame(frame);};raf=requestAnimationFrame(frame);
 }catch(error){console.warn('Cinematic intro unavailable',error);finish();}
 setTimeout(finish,5000);
}
