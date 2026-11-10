// Two-way page localization.  interface-translations.json maps the Indonesian
// source strings to English; interface-translations-id.json maps the strings
// that are written in English in the source to Indonesian.  English mode uses
// the first, Indonesian mode the reverse of the first plus the second, so
// every text node can be shown in either language whatever its source was.
// interface-translations-fix.json ({source: [english, indonesian]}) is the
// reviewed wording and wins over both; PATTERNS cover strings built at runtime.
const V='?v=2';
const dictionary=await fetch('./interface-translations.json'+V).then(r=>r.json());
const extraId=await fetch('./interface-translations-id.json'+V).then(r=>r.ok?r.json():{}).catch(()=>({}));
const fixes=await fetch('./interface-translations-fix.json'+V).then(r=>r.ok?r.json():{}).catch(()=>({}));
const toId=Object.assign(Object.fromEntries(Object.entries(dictionary).map(([id,en])=>[en,id])),extraId);
const toEn=Object.assign({},dictionary,Object.fromEntries(Object.entries(extraId).map(([en,id])=>[id,en])));
for(const [src,[en,id]] of Object.entries(fixes)){toEn[src]=en;toId[src]=id;if(!(id in fixes))toEn[id]=en;if(!(en in fixes))toId[en]=id;}
const enNum=s=>s.replace(/\d{1,3}(?:\.\d{3})+(?!\d)/g,m=>m.replace(/\./g,',')).replace(/(\d),(\d{1,2})(?!\d)/g,'$1.$2');
const PATTERNS=[
 [/^Lane (\d+): menunggu$/,m=>`Lane ${m[1]}: waiting`,m=>m[0]],
 [/^Lane (\d+): tidak digunakan$/,m=>`Lane ${m[1]}: unused`,m=>m[0]],
 [/^(FC\d): neuron (\d+)–(\d+) dari (\d+)$/,m=>`${m[1]}: neurons ${m[2]}–${m[3]} of ${m[4]}`,m=>m[0]],
 [/^([A-Z_]+) , kelompok (\d+)$/,m=>`${m[1]}, group ${m[2]}`,m=>`${m[1]}, kelompok ${m[2]}`],
 [/^([A-Z_]+) , input (\d+) \/ (\d+)$/,m=>`${m[1]}, input ${m[2]} of ${m[3]}`,m=>`${m[1]}, input ${m[2]} dari ${m[3]}`],
 [/^(\d+) port input$/,m=>`${m[1]} input port${m[1]==='1'?'':'s'}`,m=>`${m[1]} port masukan`],
 [/^(\d+) port output$/,m=>`${m[1]} output port${m[1]==='1'?'':'s'}`,m=>`${m[1]} port keluaran`],
 [/^(FC\d): ([\d.]+) siklus \(([\d.]+)%\)$/,m=>`${m[1]}: ${enNum(m[2])} cycles (${m[3]}%)`,m=>`${m[1]}: ${m[2]} siklus (${m[3].replace('.',',')}%)`],
 [/^(.+\.) Fault (\d+)\.$/,(m,t)=>`${t(m[1])} Fault code ${m[2]}.`,(m,t)=>`${t(m[1])} Kode fault ${m[2]}.`],
];
function viaPatterns(key,english){
 const map=english?toEn:toId;
 for(const [re,en,id] of PATTERNS){const m=key.match(re);if(m)return (english?en:id)(m,s=>map[s]||s);}
 return null;
}
const originals=new WeakMap();
const attrOriginals=new WeakMap();
let pending=false;
const changed=new Set();
const SKIP='script,style,pre,code,[data-i18n]:not([data-i18n="judge-mode"]),[data-i18n-skip]';
function translateAttrs(root,english){
 const map=english?toEn:toId;
 (root.querySelectorAll?.('[aria-label],[placeholder],[title]')||[]).forEach(el=>{
  if(el.closest('[data-i18n-skip]'))return;
  let saved=attrOriginals.get(el);if(!saved){saved={};attrOriginals.set(el,saved);}
  for(const attr of ['aria-label','placeholder','title']){
   const value=el.getAttribute(attr);if(!value)continue;
   if(saved[attr]===undefined||value!==saved[attr].output)saved[attr]={source:value,output:value};
   const src=saved[attr].source;
   const out=map[src]??viaPatterns(src,english)??src;   // a string already in the target language maps to itself
   saved[attr].output=out;if(out!==value)el.setAttribute(attr,out);
  }
 });
}
function translate(root=document.body){
 if(!root.isConnected)return;
 const english=document.documentElement.lang!=='id';
 translateAttrs(root,english);
 if(root.nodeType===Node.TEXT_NODE)root=root.parentElement;
 const walker=document.createTreeWalker(root,NodeFilter.SHOW_TEXT);
 while(walker.nextNode()){
  const node=walker.currentNode;
  if(node.parentElement.closest(SKIP))continue;
  const current=node.textContent;
  const previous=originals.get(node);
  const original=previous&&current===previous.output?previous.original:current;
  const key=original.trim();
  if(!key)continue;
  let replacement;
  replacement=(english?toEn:toId)[key]??viaPatterns(key,english)??key;
  const output=original.replace(key,replacement);
  originals.set(node,{original,output});if(output!==current)node.textContent=output;
 }
}
const observer=new MutationObserver(records=>{
 for(const record of records){
  if(record.type==='characterData')changed.add(record.target.parentElement);
  else for(const node of record.addedNodes)changed.add(node.nodeType===Node.TEXT_NODE?node.parentElement:node);
 }
 if(!pending&&changed.size){pending=true;requestAnimationFrame(()=>{
  pending=false;observer.disconnect();
  for(const node of changed)if(node?.isConnected)translate(node);
  changed.clear();observer.observe(document.body,{subtree:true,childList:true,characterData:true});
  document.dispatchEvent(new Event('garda-localized'));
 });}
});
translate();observer.observe(document.body,{subtree:true,childList:true,characterData:true});
document.dispatchEvent(new Event('garda-localized'));
document.addEventListener('garda-language',()=>{observer.disconnect();translate();observer.observe(document.body,{subtree:true,childList:true,characterData:true});document.dispatchEvent(new Event('garda-localized'));});
window.gardaT=(en,id)=>document.documentElement.lang==='id'?(id??toId[en]??en):en;
