/* NEXPLAY 2.0 – offline shell only; not a cloud gaming service. */
const CACHE_NAME='nexplay-cloud-v2.0';
const SHELL=['./','./index.html','./i18n.js','./manifest.webmanifest','./icon.svg','./apple-touch-icon.png'];
self.addEventListener('install',event=>event.waitUntil(caches.open(CACHE_NAME).then(cache=>cache.addAll(SHELL)).then(()=>self.skipWaiting())));
self.addEventListener('activate',event=>event.waitUntil(caches.keys().then(keys=>Promise.all(keys.filter(k=>k.startsWith('nexplay-cloud-')&&k!==CACHE_NAME).map(k=>caches.delete(k)))).then(()=>self.clients.claim())));
self.addEventListener('fetch',event=>{
 const req=event.request,url=new URL(req.url); const safe=SHELL.some(p=>new URL(p,self.location.href).pathname===url.pathname);
 if(req.method!=='GET'||url.origin!==self.location.origin||(!safe&&req.mode!=='navigate'))return;
 event.respondWith(fetch(req).then(resp=>{if(resp.ok&&resp.type==='basic'){const cp=resp.clone();event.waitUntil(caches.open(CACHE_NAME).then(cache=>cache.put(req,cp)).catch(()=>{}))}return resp}).catch(()=>caches.match(req).then(res=>res||caches.match('./index.html'))));
});
