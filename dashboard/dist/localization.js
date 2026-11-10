const dictionary=await fetch('./interface-translations.json').then(r=>r.json());
const originals=new WeakMap();
let pending=false;
function translate(){
 const english=document.documentElement.lang==='en';
 const walker=document.createTreeWalker(document.body,NodeFilter.SHOW_TEXT);
 while(walker.nextNode()){
  const node=walker.currentNode;
  if(node.parentElement.closest('script,style,pre,code,[data-i18n]'))continue;
  const current=node.textContent;
  const previous=originals.get(node);
  const original=previous&&current===previous.output?previous.original:current;
  const key=original.trim();
  const replacement=english?(dictionary[key]||key):key;
  const output=original.replace(key,replacement);
  originals.set(node,{original,output});if(output!==current)node.textContent=output;
 }
}
new MutationObserver(()=>{if(!pending){pending=true;requestAnimationFrame(()=>{pending=false;translate();});}}).observe(document.body,{subtree:true,childList:true,characterData:true});
document.addEventListener('garda-language',translate);translate();
