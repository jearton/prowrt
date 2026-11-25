/* Read authenticated inventory summary, without querying QuickStart traffic data. */
;(function () {
 'use strict';
 let summary=null,error=false,busy=false,last=0;
 const home=()=>/^\/cgi-bin\/luci\/admin\/quickstart\/?$/.test(location.pathname);
 function render(){
  if(!home())return;
  const cards=document.querySelectorAll('#app .feature-card');
  for(const card of cards){
   if(!card.querySelector('.extra_num'))continue;
   const native=card.querySelector('.extra.badge:not(.lingjing-count)');
   if(!native)continue;
   let label=card.querySelector('.lingjing-count');
   if(!label){label=native.cloneNode(false);label.classList.add('lingjing-count');label.removeAttribute('hidden');native.parentNode.appendChild(label);}
   if(!native.hidden)native.hidden=true;
   label.style.whiteSpace='normal';label.style.fontSize='13px';
   const detail=summary?.snmpEnabled ? `本地 ${summary.localCount}，SNMP ${summary.snmpCount}${summary.ready?'':'，采集未就绪'}` : `本地 ${summary?.localCount ?? 0}`;
   const text=summary ? `已发现 ${summary.total} 台设备（${detail}）` : error?'设备数量读取失败':'正在读取已发现设备数量…';
   if(label.textContent!==text)label.textContent=text;
  }
 }
 async function update(){
  if(!home()||busy||Date.now()-last<60000)return;
  busy=true;last=Date.now();const controller=new AbortController();const timer=setTimeout(()=>controller.abort(),5000);
  try{
   const r=await fetch('/cgi-bin/luci/istore/lingjing/snmpSummary/',{credentials:'same-origin',cache:'no-store',signal:controller.signal});
   if(!r.ok)throw new Error('HTTP '+r.status);
   const d=await r.json();if(d.success!==0||!d.result||!Number.isInteger(d.result.total))throw new Error('Invalid inventory summary');
   summary=d.result;error=false;
  }catch(e){summary=null;error=true;}
  finally{clearTimeout(timer);busy=false;render();}
 }
 const root=document.getElementById('app');
 if(root)new MutationObserver(()=>{render();update();}).observe(root,{childList:true,subtree:true});
 render();update();setInterval(()=>{render();update();},10000);
})();
