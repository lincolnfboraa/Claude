self.addEventListener('install',e=>self.skipWaiting());
self.addEventListener('activate',e=>e.waitUntil(self.clients.claim()));
self.addEventListener('push',e=>{let d={};try{d=e.data.json()}catch(_){d={titulo:'Bora Studio',texto:e.data?e.data.text():''}}
 e.waitUntil(self.registration.showNotification(d.titulo||'Bora Studio',{body:d.texto||'',icon:'icone.png',badge:'icone.png',data:{url:d.url||'/'}}))});
self.addEventListener('notificationclick',e=>{e.notification.close();const u=e.notification.data.url||'/';
 e.waitUntil(clients.matchAll({type:'window',includeUncontrolled:true}).then(l=>{for(const c of l){c.navigate(u);return c.focus()}return clients.openWindow(u)}))});
