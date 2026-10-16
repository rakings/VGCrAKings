// Tocco sulla notifica: se non ha un link suo (o punta alla radice rakings.github.io, che non ha nessun sito)
// si apre il sito. Questo gestore deve stare PRIMA di OneSignal, per poterlo fermare solo in questo caso.
self.addEventListener("notificationclick",e=>{
  const d=e.notification.data||{};
  const u=d.launchURL||(d.custom&&d.custom.u)||d.url||(d.onesignal_data&&d.onesignal_data.launchURL)||"";
  let radice=!u;
  try{if(u){const x=new URL(u,location.origin);radice=x.origin===location.origin&&(x.pathname==="/"||x.pathname==="")}}catch(_){}
  if(!radice)return; // le notifiche con un loro link le gestisce OneSignal come prima
  e.stopImmediatePropagation();
  e.notification.close();
  const dest=self.registration.scope;
  e.waitUntil(self.clients.matchAll({type:"window",includeUncontrolled:true}).then(cs=>{
    for(const c of cs){if(c.url.indexOf(dest)===0&&"focus"in c)return c.focus()}
    return self.clients.openWindow(dest);
  }));
});
try{importScripts("https://cdn.onesignal.com/sdks/web/v16/OneSignalSDK.sw.js")}catch(e){}
const C="vgc-v1",H="vgc-hist";
self.addEventListener("install",e=>{e.waitUntil(caches.open(C).then(c=>c.addAll(["./","index.html","manifest.webmanifest","icon-192.png"])));self.skipWaiting()});
self.addEventListener("activate",e=>{e.waitUntil(caches.keys().then(k=>Promise.all(k.filter(x=>x!==C&&x!==H).map(x=>caches.delete(x)))));self.clients.claim()});
// rete per prima, così i tornei sono sempre aggiornati; senza rete si vede l'ultima copia salvata
self.addEventListener("fetch",e=>{
  if(e.request.method!=="GET")return;
  if(new URL(e.request.url).origin!==location.origin)return;
  e.respondWith(fetch(e.request).then(r=>{const cp=r.clone();caches.open(C).then(c=>c.put(e.request,cp));return r}).catch(()=>caches.match(e.request)));
});
// cronologia: salva le notifiche davvero arrivate su questo dispositivo (la pagina le legge dalla campanella)
async function histSave(items){
  const c=await caches.open(H);const r=await c.match("hist.json");let a=[];
  try{a=r?await r.json():[]}catch(e){}
  const seen=new Set(a.map(x=>x.id));let ch=false;
  items.forEach(x=>{if(!seen.has(x.id)){a.push(x);seen.add(x.id);ch=true}});
  if(ch){a.sort((p,q)=>q.t-p.t);a=a.slice(0,60);await c.put("hist.json",new Response(JSON.stringify(a),{headers:{"Content-Type":"application/json"}}));
    try{const cs=await self.clients.matchAll({type:"window",includeUncontrolled:true});cs.forEach(w=>w.postMessage({vgcHist:1}))}catch(e){}}
}
function histGrab(){
  return self.registration.getNotifications().then(ns=>histSave(ns.map(n=>{
    const d=n.data||{};
    const u=d.launchURL||(d.custom&&d.custom.u)||d.url||(d.onesignal_data&&d.onesignal_data.launchURL)||"";
    return{id:(n.tag||"")+"|"+(n.title||"")+"|"+(n.body||"")+"|"+(n.timestamp||0),t:n.timestamp||Date.now(),title:n.title||"",body:n.body||"",url:/^https?:/.test(u)?u:""};
  })));
}
const wait=ms=>new Promise(r=>setTimeout(r,ms));
self.addEventListener("push",e=>{e.waitUntil(wait(1500).then(histGrab).then(()=>wait(2500)).then(histGrab).then(()=>wait(4000)).then(histGrab).catch(()=>{}))});
