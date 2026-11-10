const dictionary=await fetch('./interface-translations.json').then(r=>r.json());
const originals=new WeakMap();
let pending=false;
const changed=new Set();
function translate(root=document.body){
 if(!root.isConnected)return;
 const english=document.documentElement.lang==='en';
 if(english)(root.querySelectorAll?.('[aria-label],[placeholder],[title]')||[]).forEach(el=>{
  for(const attr of ['aria-label','placeholder','title']){
   const value=el.getAttribute(attr);if(value&&dictionary[value])el.setAttribute(attr,dictionary[value]);
  }
 });
 if(root.nodeType===Node.TEXT_NODE)root=root.parentElement;
 const walker=document.createTreeWalker(root,NodeFilter.SHOW_TEXT);
 while(walker.nextNode()){
  const node=walker.currentNode;
  if(node.parentElement.closest('script,style,pre,code,[data-i18n]'))continue;
  const current=node.textContent;
  const previous=originals.get(node);
  const original=previous&&current===previous.output?previous.original:current;
  const key=original.trim();
  let replacement=english?(dictionary[key]||key):key;
  if(english&&!dictionary[key]){
   const phrases={'siklus':'cycles','cocok':'matched','kelompok':'groups','menunggu':'waiting','Memuat':'Loading','hasil':'results','Putar':'Play','Jeda':'Pause','memindai':'scanning','maju':'moving forward','berhenti':'stopped','Rintangan':'Obstacle','rintangan':'obstacle','aktif':'active'};
   for(const [from,to] of Object.entries(phrases))replacement=replacement.replace(new RegExp('\\b'+from+'\\b','g'),to);
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
 });}
});
translate();observer.observe(document.body,{subtree:true,childList:true,characterData:true});
document.addEventListener('garda-language',()=>{observer.disconnect();translate();observer.observe(document.body,{subtree:true,childList:true,characterData:true});});
