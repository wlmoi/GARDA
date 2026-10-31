import * as T from './vendor/three.module.min.js';
const canvas=document.getElementById('robot-scene');
if(canvas){
try {
const renderer=new T.WebGLRenderer({canvas,antialias:true});renderer.setPixelRatio(Math.min(devicePixelRatio,2));
const scene=new T.Scene();scene.background=new T.Color('#050684');
const camera=new T.PerspectiveCamera(40,1,.1,100);let yaw=.65,pitch=.7,distance=11;
scene.add(new T.HemisphereLight(0xffffff,0x18385c,2.7));const light=new T.DirectionalLight(0xffffff,3);light.position.set(3,6,4);scene.add(light);
const robot=new T.Group();scene.add(robot);const green=0x58fd37,dark=0x15232d;const wheels=[];const body=new T.Group();robot.add(body);
function box(w,h,d,color,x,y,z,parent=body){const m=new T.Mesh(new T.BoxGeometry(w,h,d),new T.MeshStandardMaterial({color,roughness:.55,metalness:.25}));m.position.set(x,y,z);parent.add(m);return m;}
function cylinder(r,h,color,x,y,z,parent=body){const m=new T.Mesh(new T.CylinderGeometry(r,r,h,32),new T.MeshStandardMaterial({color,roughness:.55}));m.position.set(x,y,z);parent.add(m);return m;}
box(1.65,.22,2.25,green,0,.65,0);box(1.35,.12,1.8,dark,0,1,0);box(1.5,.1,1.25,green,0,1.35,.1);
for(const x of [-.67,.67])for(const z of [-.75,.75])box(.07,.6,.07,0x74838b,x,1,z);
for(const x of [-1,1])for(const z of [-.72,.72]){const wheel=new T.Group();wheel.position.set(x,.48,z);robot.add(wheel);const hub=cylinder(.42,.24,0x30383e,0,0,0,wheel);hub.rotation.z=Math.PI/2;
for(let i=0;i<8;i++){const a=i*Math.PI/4;const roller=cylinder(.105,.33,0x11191f,0,Math.sin(a)*.4,Math.cos(a)*.4,wheel);roller.rotation.z=(x*z>0?1:-1)*.8;roller.rotation.x=-a;}wheels.push(wheel);}
cylinder(.38,.22,dark,0,1.52,-.38);cylinder(.29,.04,green,0,1.65,-.38);
box(.14,.8,.14,dark,0,1.65,.6);const screen=box(1.25,.8,.08,dark,0,2,.64);screen.rotation.x=-.15;box(1.1,.65,.02,0x143965,0,2,.58);
box(1.35,.25,.26,dark,0,2.28,-.05);for(const x of [-.45,0,.45]){const lens=cylinder(.075,.04,0x35b8e4,x,2.28,-.2);lens.rotation.x=Math.PI/2;}
const floor=box(12,.03,10,0x034ab6,0,-.03,0,scene);scene.add(new T.GridHelper(12,24,0x35b8e4,0x225bb5));
const obstacle=box(1.25,1.1,.65,0xfdfdff,0,.55,-1.2,scene);
const route=new T.Line(new T.BufferGeometry().setFromPoints([new T.Vector3(0,.025,3),new T.Vector3(0,.025,-3)]),new T.LineDashedMaterial({color:0x9bfd08,dashSize:.15,gapSize:.1}));route.computeLineDistances();scene.add(route);
const rays=[];for(let i=0;i<41;i++){const line=new T.Line(new T.BufferGeometry().setFromPoints([new T.Vector3(),new T.Vector3()]),new T.LineBasicMaterial({color:0x35b8e4,transparent:true,opacity:.5}));scene.add(line);rays.push(line);}
function positionAt(p,avoid){const rise=Math.max(0,Math.min(1,(p-.05)/.25));const smooth=rise*rise*(3-2*rise);return {x:avoid?2.7*smooth:0,z:3-p*6};}
function hitBox(ox,oz,dx,dz){let near=0,far=4;for(const [o,d,lo,hi] of [[ox,dx,-.625,.625],[oz,dz,-1.525,-.875]]){if(Math.abs(d)<1e-8){if(o<lo||o>hi)return 4;}else{let a=(lo-o)/d,b=(hi-o)/d;if(a>b)[a,b]=[b,a];near=Math.max(near,a);far=Math.min(far,b);if(near>far)return 4;}}return near;}
const slider=document.getElementById('robot-progress'),play=document.getElementById('robot-play'),mode=document.getElementById('robot-scenario'),status=document.getElementById('robot-status');let running=false,last=0,progress=0;
function draw(){const size=canvas.getBoundingClientRect();if(!size.width||!size.height)return;renderer.setSize(size.width,size.height,false);camera.aspect=size.width/size.height;camera.position.set(Math.sin(yaw)*Math.cos(pitch)*distance,Math.sin(pitch)*distance,Math.cos(yaw)*Math.cos(pitch)*distance);camera.lookAt(0,.7,0);camera.updateProjectionMatrix();
const avoid=mode.value==='avoid',blocked=mode.value==='obstacle',emergency=mode.value==='estop';obstacle.visible=avoid||blocked;const p=emergency?0:blocked?Math.min(progress,.25):progress;const pathPoints=Array.from({length:61},(_,i)=>{const q=positionAt(i/60,avoid);return new T.Vector3(q.x,.03,q.z);});route.geometry.dispose();route.geometry=new T.BufferGeometry().setFromPoints(pathPoints);route.computeLineDistances();const pos=positionAt(p,avoid),ahead=positionAt(Math.min(1,p+.001),avoid);robot.position.set(pos.x,0,pos.z);
// Mecanum translation: the chassis keeps its heading while strafing around an object.
robot.rotation.y=0;
const moving=running&&!emergency&&!(blocked&&progress>=.25)&&p<1;
const vibration=moving&&!matchMedia('(prefers-reduced-motion: reduce)').matches;
body.position.y=vibration?.006*Math.sin(p*640):0;
body.rotation.x=vibration?.003*Math.sin(p*410):0;
body.rotation.z=vibration?.004*Math.sin(p*530):0;
// Wheel order: left rear/front, right rear/front. Axles lie on local X.
const forward=3-pos.z,side=pos.x;
const wheelTravel=[forward+side,forward-side,forward-side,forward+side];
wheels.forEach((wheel,i)=>{wheel.rotation.x=-wheelTravel[i]/.42;});
let nearest=4;const origin=new T.Vector3(0,1.6,-.38);robot.localToWorld(origin);rays.forEach((line,i)=>{const angle=(i/40-.5)*Math.PI*2;const dx=Math.sin(angle),dz=Math.cos(angle);const distance=obstacle.visible?hitBox(origin.x,origin.z,dx,dz):4;nearest=Math.min(nearest,distance);const points=line.geometry.attributes.position;points.setXYZ(0,origin.x,1.6,origin.z);points.setXYZ(1,origin.x+dx*distance,.55,origin.z+dz*distance);points.needsUpdate=true;line.geometry.computeBoundingSphere();line.material.color.set(distance<4?0x9bfd08:0x35b8e4);});
const reading=document.getElementById('lidar-distance');if(reading)reading.textContent=nearest<4?nearest.toFixed(2)+' m':'4,00 m+';
status.textContent=emergency?'E-stop , keluaran nol':blocked&&progress>=.25?'LiDAR , berhenti':avoid&&p>.15&&p<.85?'LiDAR → koreksi arah → menghindar':p>=1?'Tujuan tercapai':'LiDAR memindai , maju';
const stage=emergency?'safety':running?['lidar','cpu','mac','safety','robot'][Math.floor(progress*45)%5]:'lidar';document.querySelectorAll('[data-robot-stage]').forEach(el=>el.classList.toggle('active',el.dataset.robotStage===stage));
renderer.render(scene,camera);}
function pause(){running=false;body.position.y=0;body.rotation.set(0,0,0);play.textContent='▶ Jalankan';play.setAttribute('aria-pressed','false');}
play.addEventListener('click',()=>{if(running)pause();else{if(progress>=1)progress=0;if(matchMedia('(prefers-reduced-motion: reduce)').matches){progress=Math.min(1,progress+.1);slider.value=Math.round(progress*100);draw();return;}running=true;play.textContent='Ⅱ Jeda';play.setAttribute('aria-pressed','true');}});
document.getElementById('robot-reset').addEventListener('click',()=>{pause();progress=0;slider.value=0;draw();});slider.addEventListener('input',()=>{pause();progress=Number(slider.value)/100;draw();});mode.addEventListener('change',()=>{pause();progress=0;slider.value=0;draw();});
let dragging=false,px=0,py=0;canvas.addEventListener('pointerdown',e=>{dragging=true;px=e.clientX;py=e.clientY;canvas.setPointerCapture(e.pointerId);});canvas.addEventListener('pointerup',()=>dragging=false);canvas.addEventListener('pointercancel',()=>dragging=false);canvas.addEventListener('pointermove',e=>{if(!dragging)return;yaw-=(e.clientX-px)*.008;pitch=Math.max(.15,Math.min(1.2,pitch+(e.clientY-py)*.006));px=e.clientX;py=e.clientY;draw();});canvas.addEventListener('wheel',e=>{e.preventDefault();distance=Math.max(5,Math.min(15,distance+e.deltaY*.006));draw();},{passive:false});
const reduced=matchMedia('(prefers-reduced-motion: reduce)');reduced.addEventListener('change',()=>{pause();draw();});document.addEventListener('visibilitychange',()=>{if(document.hidden)pause();});new ResizeObserver(draw).observe(canvas);
function animate(time){const dt=Math.min((time-last)/1000,.06);last=time;if(running&&!document.hidden){progress=Math.min(1,progress+dt/8);slider.value=Math.round(progress*100);document.dispatchEvent(new CustomEvent('garda-demo-frame',{detail:{progress,playing:true}}));draw();if(progress>=1||(mode.value==='obstacle'&&progress>=.25)||mode.value==='estop'){pause();draw();}}requestAnimationFrame(animate);}draw();requestAnimationFrame(animate);
} catch(error) { document.getElementById('robot-status').textContent='3D tidak tersedia , coba browser dengan WebGL'; console.warn('GARDA robot viewer:',error.message); }
}
