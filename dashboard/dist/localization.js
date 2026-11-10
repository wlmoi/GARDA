// Two-way page localization.  interface-translations.json maps the Indonesian
// source strings to English; interface-translations-id.json maps the strings
// that are written in English in the source to Indonesian.  English mode uses
// the first, Indonesian mode the reverse of the first plus the second, so
// every text node can be shown in either language whatever its source was.
const dictionary=await fetch('./interface-translations.json').then(r=>r.json());
const extraId=await fetch('./interface-translations-id.json').then(r=>r.ok?r.json():{}).catch(()=>({}));
const toId=Object.assign(Object.fromEntries(Object.entries(dictionary).map(([id,en])=>[en,id])),extraId);
const toEn=Object.assign({},dictionary,Object.fromEntries(Object.entries(extraId).map(([en,id])=>[id,en])));
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
   const out=map[src]||src;   // a string already in the target language maps to itself
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
  if(english){
   replacement=toEn[key]||key;
   if(!toEn[key]){
    const phrases={'siklus':'cycles','cocok':'matched','kelompok':'groups','menunggu':'waiting','Memuat':'Loading','hasil':'results','Putar':'Play','Jeda':'Pause','memindai':'scanning','maju':'moving forward','berhenti':'stopped','Rintangan':'Obstacle','rintangan':'obstacle','aktif':'active'};
    for(const [from,to] of Object.entries(phrases))replacement=replacement.replace(new RegExp('\\b'+from+'\\b','g'),to);
   }
  }else{
   replacement=toId[key]||key;
  }
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
