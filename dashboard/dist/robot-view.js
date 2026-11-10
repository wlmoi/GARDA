import * as T from './vendor/three.module.min.js';
const canvas=document.getElementById('robot-scene');
if(canvas){
try {
const renderer=new T.WebGLRenderer({canvas,antialias:true});renderer.setPixelRatio(Math.min(devicePixelRatio,matchMedia('(pointer: coarse)').matches?1.5:2));
const scene=new T.Scene();scene.background=new T.Color('#0D1535');
const camera=new T.PerspectiveCamera(40,1,.1,100);let yaw=.65,pitch=.7,distance=11;
scene.add(new T.HemisphereLight(0xffffff,0x18385c,2.7));const light=new T.DirectionalLight(0xffffff,3);light.position.set(3,6,4);scene.add(light);
const robot=new T.Group();scene.add(robot);const green=0x315cff,dark=0x15232d;const wheels=[];const body=new T.Group();robot.add(body);
function box(w,h,d,color,x,y,z,parent=body){const m=new T.Mesh(new T.BoxGeometry(w,h,d),new T.MeshStandardMaterial({color,roughness:.55,metalness:.25}));m.position.set(x,y,z);parent.add(m);return m;}
function cylinder(r,h,color,x,y,z,parent=body){const m=new T.Mesh(new T.CylinderGeometry(r,r,h,32),new T.MeshStandardMaterial({color,roughness:.55}));m.position.set(x,y,z);parent.add(m);return m;}
box(1.65,.22,2.25,green,0,.65,0);box(1.35,.12,1.8,dark,0,1,0);box(1.5,.1,1.25,green,0,1.35,.1);
for(const x of [-.67,.67])for(const z of [-.75,.75])box(.07,.6,.07,0x74838b,x,1,z);
for(const x of [-1,1])for(const z of [-.72,.72]){const wheel=new T.Group();wheel.position.set(x,.48,z);robot.add(wheel);const hub=cylinder(.42,.24,0x30383e,0,0,0,wheel);hub.rotation.z=Math.PI/2;
for(let i=0;i<8;i++){const a=i*Math.PI/4;const roller=cylinder(.105,.33,0x11191f,0,Math.sin(a)*.4,Math.cos(a)*.4,wheel);roller.rotation.z=(x*z>0?1:-1)*.8;roller.rotation.x=-a;}wheels.push(wheel);}
cylinder(.38,.22,dark,0,1.52,-.38);cylinder(.29,.04,green,0,1.65,-.38);
box(.14,.8,.14,dark,0,1.65,.6);const screen=box(1.25,.8,.08,dark,0,2,.64);screen.rotation.x=-.15;box(1.1,.65,.02,0x143965,0,2,.58);
box(1.35,.25,.26,dark,0,2.28,-.05);for(const x of [-.45,0,.45]){const lens=cylinder(.075,.04,0x93acff,x,2.28,-.2);lens.rotation.x=Math.PI/2;}
// Conceptual quadrotor inspired by the supplied reference, not a validated aircraft.
const drone=new T.Group();scene.add(drone);const rotors=[];
box(.7,.7,.95,dark,0,.55,0,drone);box(.6,.08,.7,0x34424b,0,.95,0,drone);
for(const x of [-1,1])for(const z of [-1,1]){
 const arm=box(1.65,.09,.1,dark,x*.65,.55,z*.65,drone);arm.rotation.y=-x*z*Math.PI/4;
 cylinder(.16,.22,dark,x*1.2,.6,z*1.2,drone);
 const rotor=new T.Group();rotor.position.set(x*1.2,.75,z*1.2);drone.add(rotor);
 box(1.25,.025,.10,0x46535d,0,0,0,rotor);box(.1,.025,1.25,0x46535d,0,0,0,rotor);rotors.push(rotor);
 const leg=box(.065,.9,.065,0x34424b,x*.55,-.1,z*.46,drone);leg.rotation.z=x*.25;
 box(.12,.08,.9,dark,x*.66,-.55,z*.4,drone);
}
cylinder(.27,.3,0x93acff,0,-.1,-.12,drone);box(.38,.3,.22,dark,0,.35,-.55,drone);const droneLens=cylinder(.11,.04,0x315cff,0,.35,-.68,drone);droneLens.rotation.x=Math.PI/2;
const scanCone=new T.Mesh(new T.ConeGeometry(2.2,2.7,48,1,true),new T.MeshBasicMaterial({color:0x315cff,transparent:true,opacity:.09,side:T.DoubleSide,depthWrite:false}));scanCone.position.y=-1.45;drone.add(scanCone);
const dog=new T.Group();scene.add(dog);const legs=[];
box(.8,.38,1.55,0xfdfdff,0,1.3,0,dog);box(.65,.25,.35,0x25343f,0,1.3,-.85,dog);cylinder(.22,.3,0x202d35,0,1.65,-.35,dog);
for(const x of [-.48,.48])for(const z of [-.55,.55]){const hip=new T.Group();hip.position.set(x,1.3,z);dog.add(hip);cylinder(.15,.18,0x74838b,0,0,0,hip);const thigh=box(.15,.5,.18,0xfdfdff,0,-.24,.1,hip);thigh.rotation.x=-.35;const knee=new T.Group();knee.position.set(0,-.48,.18);hip.add(knee);const shin=box(.09,.55,.1,0x647581,0,-.26,-.1,knee);shin.rotation.x=.35;cylinder(.1,.08,0x202d35,0,-.55,-.19,knee);legs.push({hip,knee,offset:x*z>0?0:Math.PI});}
const surgery=new T.Group();scene.add(surgery);const arms=[];
box(.65,2.2,.65,0xfdfdff,0,1.1,1.8,surgery);box(2.4,.3,.55,0xd6e3e9,0,2.3,1.6,surgery);
for(const x of [-.85,.85]){const shoulder=new T.Group();shoulder.position.set(x,2.2,1.5);surgery.add(shoulder);cylinder(.18,.24,0x93acff,0,0,0,shoulder);box(.23,.25,.95,0xfdfdff,0,-.08,-.45,shoulder);const elbow=new T.Group();elbow.position.set(0,-.08,-.9);shoulder.add(elbow);cylinder(.15,.22,0x93acff,0,0,0,elbow);const tool=box(.07,.07,.9,0xa8bac5,0,-.08,-.42,elbow);const tip=box(.025,.025,.23,0x315cff,0,-.08,-.97,elbow);arms.push({shoulder,elbow,sign:Math.sign(x)});}
box(2,.18,2.2,0x25343f,0,.72,-.4,surgery);const target=cylinder(.2,.03,0xb7ff35,0,.84,-.55,surgery);
const floor=box(12,.03,10,0x101942,0,-.03,0,scene);scene.add(new T.GridHelper(12,24,0x93acff,0x29365b));
const obstacle=box(1.25,1.1,.65,0xfdfdff,0,.55,-1.2,scene);
const route=new T.Line(new T.BufferGeometry().setFromPoints([new T.Vector3(0,.025,3),new T.Vector3(0,.025,-3)]),new T.LineDashedMaterial({color:0xb7ff35,dashSize:.15,gapSize:.1}));route.computeLineDistances();scene.add(route);
const rays=[];for(let i=0;i<41;i++){const line=new T.Line(new T.BufferGeometry().setFromPoints([new T.Vector3(),new T.Vector3()]),new T.LineBasicMaterial({color:0x93acff,transparent:true,opacity:.5}));scene.add(line);rays.push(line);}
function positionAt(p,avoid){const rise=Math.max(0,Math.min(1,(p-.05)/.25));const smooth=rise*rise*(3-2*rise);return {x:avoid?2.7*smooth:0,z:3-p*6};}
function hitBox(ox,oz,dx,dz){let near=0,far=4;for(const [o,d,lo,hi] of [[ox,dx,-.625,.625],[oz,dz,-1.525,-.875]]){if(Math.abs(d)<1e-8){if(o<lo||o>hi)return 4;}else{let a=(lo-o)/d,b=(hi-o)/d;if(a>b)[a,b]=[b,a];near=Math.max(near,a);far=Math.min(far,b);if(near>far)return 4;}}return near;}
const slider=document.getElementById('robot-progress'),play=document.getElementById('robot-play'),mode=document.getElementById('robot-scenario'),status=document.getElementById('robot-status');let running=false,last=0,progress=0,phase='infer',phaseTime=0,stepStart=0,inferenceStep=0;
const inferenceMarks=[0];
for(const [start,inputs,groups] of [[1,74,8],[1809,128,4],[3361,64,1]]){const length=inputs*3+4;for(let group=0;group<groups;group++){const base=start+group*length;for(const offset of [0,1,2,3,4,5,length-2,length-1])inferenceMarks.push(base+offset);}}
function publishClock(clock){document.dispatchEvent(new CustomEvent('garda-demo-frame',{detail:{clock}}));}
function motionOnly(){return document.getElementById('robot-playback').value==='motion';}
function resetSequence(){phase=motionOnly()?'move':'infer';phaseTime=0;inferenceStep=0;stepStart=progress;if(!motionOnly())publishClock(0);}
function draw(){const size=canvas.getBoundingClientRect();if(!size.width||!size.height)return;renderer.setSize(size.width,size.height,false);camera.aspect=size.width/size.height;const fittedDistance=distance*Math.max(1,Math.min(1.6,1.3/camera.aspect));camera.position.set(Math.sin(yaw)*Math.cos(pitch)*fittedDistance,Math.sin(pitch)*fittedDistance,Math.cos(yaw)*Math.cos(pitch)*fittedDistance);camera.lookAt(0,.7,0);camera.updateProjectionMatrix();
const platform=document.getElementById('robot-platform').value;const airborne=platform==='drone',quadruped=platform==='lite3',surgical=platform==='surgery';robot.visible=platform==='hiwonder';drone.visible=airborne;dog.visible=quadruped;surgery.visible=surgical;route.visible=!surgical;
const avoid=mode.value==='avoid',blocked=mode.value==='obstacle',emergency=mode.value==='estop';obstacle.visible=!surgical&&(avoid||blocked);const p=emergency?0:blocked?Math.min(progress,.25):progress;const pathPoints=Array.from({length:61},(_,i)=>{const q=positionAt(i/60,avoid);return new T.Vector3(q.x,.03,q.z);});route.geometry.dispose();route.geometry=new T.BufferGeometry().setFromPoints(pathPoints);route.computeLineDistances();const pos=positionAt(p,avoid),ahead=positionAt(Math.min(1,p+.001),avoid);robot.position.set(pos.x,0,pos.z);
// Mecanum translation: the chassis keeps its heading while strafing around an object.
robot.rotation.y=0;drone.position.set(pos.x,3,pos.z);drone.rotation.set(0,0,0);obstacle.scale.y=airborne?4:1;obstacle.position.y=airborne?2.2:.55;
dog.position.set(pos.x,0,pos.z);
const moving=running&&phase==='move'&&!emergency&&!(blocked&&progress>=.25)&&p<1;
rotors.forEach((rotor,i)=>{rotor.rotation.y=running&&!emergency?p*220*(i%2?1:-1):0;});
legs.forEach(({hip,knee,offset})=>{const stride=Math.sin(p*70+offset);hip.rotation.x=moving?.35*stride:0;knee.rotation.x=moving?.25*Math.max(0,-stride):0;});
arms.forEach(({shoulder,elbow,sign})=>{shoulder.rotation.y=-sign*p*.35;elbow.rotation.x=-p*.2;});
const vibration=moving&&!matchMedia('(prefers-reduced-motion: reduce)').matches;
drone.position.y=3+(vibration?.015*Math.sin(p*160):0);
body.position.y=vibration?.006*Math.sin(p*640):0;
body.rotation.x=vibration?.003*Math.sin(p*410):0;
body.rotation.z=vibration?.004*Math.sin(p*530):0;
// Wheel order: left rear/front, right rear/front. Axles lie on local X.
const forward=3-pos.z,side=pos.x;
const wheelTravel=[forward+side,forward-side,forward-side,forward+side];
wheels.forEach((wheel,i)=>{wheel.rotation.x=-wheelTravel[i]/.42;});
let nearest=4;const origin=new T.Vector3(0,1.6,-.38);robot.localToWorld(origin);if(airborne){origin.x=drone.position.x;origin.y=2.9;origin.z=drone.position.z;}rays.forEach((line,i)=>{const angle=(i/40-.5)*Math.PI*2;const dx=Math.sin(angle),dz=Math.cos(angle);const distance=obstacle.visible?hitBox(origin.x,origin.z,dx,dz):4;nearest=Math.min(nearest,distance);line.visible=!surgical;const points=line.geometry.attributes.position;points.setXYZ(0,origin.x,origin.y,origin.z);points.setXYZ(1,origin.x+dx*distance,.55,origin.z+dz*distance);points.needsUpdate=true;line.geometry.computeBoundingSphere();line.material.color.set(distance<4?0xb7ff35:0x93acff);});
const reading=document.getElementById('lidar-distance');if(reading)reading.textContent=surgical?'Not used':nearest<4?nearest.toFixed(2)+' m':'4.00 m+';
let statusText=emergency?'E-stop active, outputs zero':blocked&&progress>=.25?'Obstacle detected, stopped':avoid&&p>.15&&p<.85?'LiDAR → heading correction → avoidance':p>=1?'Destination reached':'LiDAR scanning, moving forward';
if(running&&phase==='infer'&&!emergency)statusText='Inference running, robot stationary';
if(surgical)statusText=running&&phase==='infer'?'Motion planning, tool stationary':p>=1?'Illustrative target reached':'Illustrative arm motion toward target';
const stage=emergency?'safety':running?(phase==='infer'?'mac':'robot'):'lidar';document.querySelectorAll('[data-robot-stage]').forEach(el=>el.classList.toggle('active',el.dataset.robotStage===stage));
if(status.textContent!==statusText)status.textContent=statusText;renderer.render(scene,camera);}
function pause(){running=false;body.position.y=0;body.rotation.set(0,0,0);play.textContent='▶ Play';play.setAttribute('aria-pressed','false');}
play.addEventListener('click',()=>{if(running)pause();else{if(progress>=1){progress=0;resetSequence();}if(matchMedia('(prefers-reduced-motion: reduce)').matches){if(phase==='infer'){phase='move';publishClock(3556);}else{progress=Math.min(1,progress+.25);resetSequence();}slider.value=Math.round(progress*100);draw();return;}running=true;play.textContent='Ⅱ Pause';play.setAttribute('aria-pressed','true');}});
document.getElementById('robot-reset').addEventListener('click',()=>{pause();progress=0;slider.value=0;resetSequence();draw();});slider.addEventListener('input',()=>{pause();progress=Number(slider.value)/100;resetSequence();draw();});mode.addEventListener('change',()=>{pause();progress=0;slider.value=0;resetSequence();draw();});
document.getElementById('robot-platform').addEventListener('change',()=>{pause();const surgical=document.getElementById('robot-platform').value==='surgery';mode.disabled=surgical;if(surgical)mode.value='clear';document.getElementById('platform-note').textContent=surgical?'Conceptual Physical AI assistance for arm and camera motion.':document.getElementById('robot-platform').value==='lite3'?'Lite3 LiDAR perception and obstacle-avoidance illustration.':'';progress=0;slider.value=0;resetSequence();draw();});
document.getElementById('robot-playback').addEventListener('change',()=>{pause();document.querySelector('.clock-panel').classList.toggle('motion-only',motionOnly());resetSequence();draw();});
let dragging=false,px=0,py=0;canvas.addEventListener('pointerdown',e=>{dragging=true;px=e.clientX;py=e.clientY;canvas.setPointerCapture(e.pointerId);});canvas.addEventListener('pointerup',()=>dragging=false);canvas.addEventListener('pointercancel',()=>dragging=false);canvas.addEventListener('pointermove',e=>{if(!dragging)return;yaw-=(e.clientX-px)*.008;pitch=Math.max(.15,Math.min(1.2,pitch+(e.clientY-py)*.006));px=e.clientX;py=e.clientY;draw();});canvas.addEventListener('wheel',e=>{e.preventDefault();distance=Math.max(5,Math.min(15,distance+e.deltaY*.006));draw();},{passive:false});
const reduced=matchMedia('(prefers-reduced-motion: reduce)');reduced.addEventListener('change',()=>{pause();draw();});document.addEventListener('visibilitychange',()=>{if(document.hidden)pause();});new ResizeObserver(draw).observe(canvas);
function animate(time){const dt=Math.min((time-last)/1000,.06);last=time;
if(running&&!document.hidden){
 if(mode.value==='estop'){pause();draw();}
 else if(phase==='infer'){
  phaseTime+=dt;
  const speed=document.getElementById('clock-speed').value;
  const delay={slow:1.2,normal:.65,fast:.22}[speed]||1.2;
  if(phaseTime>=delay){phaseTime=0;inferenceStep++;if(inferenceStep<inferenceMarks.length)publishClock(inferenceMarks[inferenceStep]);else{publishClock(3556);phase='move';stepStart=progress;}}

  draw();
 }else{
  phaseTime+=dt;const t=Math.min(1,phaseTime/2),smooth=t*t*(3-2*t);
  progress=Math.min(1,stepStart+.25*smooth);slider.value=Math.round(progress*100);draw();
  if(progress>=1||(mode.value==='obstacle'&&progress>=.25)){pause();draw();}
  else if(t>=1)resetSequence();
 }
}requestAnimationFrame(animate);}resetSequence();document.querySelector('.clock-panel').classList.toggle('motion-only',motionOnly());draw();requestAnimationFrame(animate);
} catch(error) { document.getElementById('robot-status').textContent='3D is unavailable. Use a browser with WebGL support.'; console.warn('GARDA robot viewer:',error.message); }
}
