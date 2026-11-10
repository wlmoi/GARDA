import * as THREE from './vendor/three.module.min.js';
const reduced=matchMedia('(prefers-reduced-motion: reduce)').matches;
let seen=false;try{seen=sessionStorage.getItem('garda-boot-seen')==='1';}catch{}
if(!reduced&&!seen)start();
function start(){
 const overlay=document.createElement('div');overlay.className='boot-intro';overlay.setAttribute('aria-label','GARDA cinematic introduction');
 overlay.innerHTML='<button class="boot-skip" type="button">Lewati intro / Skip intro</button><img class="boot-logo" src="assets/garda-mark.svg" alt="GARDA"><p class="boot-caption">GARDA • Visualisasi konseptual / Conceptual visualization</p>';
 document.body.append(overlay);
 let renderer,raf,done=false;const resources=[];
 const finish=()=>{if(done)return;done=true;cancelAnimationFrame(raf);removeEventListener('resize',resize);removeEventListener('keydown',key);resources.forEach(r=>r.dispose());renderer?.dispose();renderer?.forceContextLoss();overlay.remove();try{sessionStorage.setItem('garda-boot-seen','1');}catch{}};
 const key=e=>{if(e.key==='Escape')finish();};overlay.querySelector('button').onclick=finish;addEventListener('keydown',key);
 let scene,camera,frames,signals,streaks;const dummy=new THREE.Object3D();const color=new THREE.Color();
 function resize(){if(!renderer)return;camera.aspect=innerWidth/innerHeight;camera.updateProjectionMatrix();renderer.setSize(innerWidth,innerHeight);}
 try{
 renderer=new THREE.WebGLRenderer({antialias:innerWidth>780,alpha:false});renderer.setPixelRatio(Math.min(devicePixelRatio,innerWidth<780?1.25:2));renderer.outputColorSpace=THREE.SRGBColorSpace;renderer.toneMapping=THREE.ACESFilmicToneMapping;overlay.prepend(renderer.domElement);
 scene=new THREE.Scene();scene.background=new THREE.Color('#102139');scene.fog=new THREE.FogExp2('#102139',.018);camera=new THREE.PerspectiveCamera(65,innerWidth/innerHeight,.1,160);camera.position.z=4;
 scene.add(new THREE.AmbientLight(0x75bede,.7));const keyLight=new THREE.DirectionalLight(0xffffff,2);keyLight.position.set(2,3,4);scene.add(keyLight);const light=new THREE.PointLight(0x007bc0,30,24);scene.add(light);
 const shape=new THREE.Shape();shape.moveTo(-3,-3);shape.lineTo(3,-3);shape.lineTo(3,3);shape.lineTo(-3,3);shape.closePath();const hole=new THREE.Path();hole.moveTo(-2.82,-2.82);hole.lineTo(-2.82,2.82);hole.lineTo(2.82,2.82);hole.lineTo(2.82,-2.82);hole.closePath();shape.holes.push(hole);
 const geometry=new THREE.ExtrudeGeometry(shape,{depth:.12,bevelEnabled:false});const metal=new THREE.MeshStandardMaterial({color:0x243e80,metalness:.65,roughness:.4});const signalMaterial=new THREE.MeshBasicMaterial({color:0xffffff});resources.push(geometry,metal,signalMaterial);
 frames=new THREE.InstancedMesh(geometry,metal,28);signals=new THREE.InstancedMesh(geometry,signalMaterial,28);
 for(let i=0;i<28;i++){dummy.position.set(0,0,-5-i*3.2);dummy.rotation.z=i*.06;dummy.scale.setScalar(1);dummy.updateMatrix();frames.setMatrixAt(i,dummy.matrix);dummy.scale.setScalar(.97);dummy.updateMatrix();signals.setMatrixAt(i,dummy.matrix);signals.setColorAt(i,color.set('#007BC0'));}scene.add(frames,signals);
 const count=innerWidth<780?240:600;const positions=new Float32Array(count*6);for(let i=0;i<count;i++){const a=i*2.399,r=3.8+(i%23)/8,z=-i/count*100;positions.set([Math.cos(a)*r,Math.sin(a)*r,z,Math.cos(a)*r,Math.sin(a)*r,z-1.5],i*6);}const lines=new THREE.BufferGeometry();lines.setAttribute('position',new THREE.BufferAttribute(positions,3));const lm=new THREE.LineBasicMaterial({color:0x75bede,transparent:true,opacity:.25});streaks=new THREE.LineSegments(lines,lm);scene.add(streaks);resources.push(lines,lm);
 resize();addEventListener('resize',resize);const began=performance.now();
 const frame=now=>{if(done)return;const t=(now-began)/1000,p=Math.min(1,t/5.6),e=p*p*p*(p*(p*6-15)+10);camera.position.set(.45*Math.sin(Math.PI*p)*Math.sin(2*Math.PI*p),0,4-99*e);camera.rotation.z=.055*Math.sin(Math.PI*p);light.position.copy(camera.position);lm.opacity=.25*Math.sin(Math.PI*p);for(let i=0;i<28;i++){const distance=(-5-i*3.2)-camera.position.z;const pulse=Math.exp(-distance*distance/30);signals.setColorAt(i,color.set('#007BC0').lerp(new THREE.Color('#75BEDE'),pulse));}signals.instanceColor.needsUpdate=true;if(t>5.6)overlay.classList.add('landed');if(t>6.7)overlay.style.opacity=String(Math.max(0,(7.2-t)/.5));renderer.render(scene,camera);if(t>=7.2)finish();else raf=requestAnimationFrame(frame);};raf=requestAnimationFrame(frame);
 }catch(error){console.warn('Cinematic intro unavailable',error);finish();}
 setTimeout(finish,8000);
}
