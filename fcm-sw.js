/* Service worker di PROVA per Firebase (Fase C). Non e' quello del sito. */
self.addEventListener("install", function () { self.skipWaiting(); });
self.addEventListener("activate", function (e) { e.waitUntil(self.clients.claim()); });


// Cronologia sul dispositivo: la campanella del sito la legge dalla stessa cache che usava sw.js.
function histSave(title, body, link) {
  var t = Date.now();
  var item = { id: "|" + title + "|" + body + "|" + t, t: t, title: title, body: body, url: /^https?:/.test(link || "") ? link : "" };
  return caches.open("vgc-hist").then(function (c) {
    return c.match("hist.json").then(function (r) { return r ? r.json().catch(function () { return []; }) : []; }).then(function (a) {
      if (!Array.isArray(a)) a = [];
      a.push(item);
      a.sort(function (p, q) { return q.t - p.t; });
      return c.put("hist.json", new Response(JSON.stringify(a.slice(0, 60)), { headers: { "Content-Type": "application/json" } }));
    });
  }).then(function () {
    return self.clients.matchAll({ type: "window", includeUncontrolled: true }).then(function (cs) {
      cs.forEach(function (w) { w.postMessage({ vgcHist: 1 }); });
    });
  }).catch(function () {});
}

self.addEventListener("push", function (e) {
  var raw = "", j = {};
  try { raw = e.data ? e.data.text() : ""; } catch (x) {}
  var logP = caches.open("fcm-log").then(function (c) {
    return c.put("/fcm-log/" + Date.now(), new Response(JSON.stringify({ t: new Date().toISOString(), raw: raw.slice(0, 200) })));
  }).catch(function () {});
  try { j = raw ? JSON.parse(raw) : {}; } catch (x) { j = {}; }
  var n = j.notification || {}, d = j.data || {};
  var title = n.title || d.title || "rAKings VGC";
  var body = n.body || d.body || (!n.title && !d.title ? raw.slice(0, 200) : "");
  var link = (j.fcmOptions && j.fcmOptions.link) || n.click_action || d.link || d.url || "./";
  e.waitUntil(Promise.all([logP, histSave(title, body, link), self.registration.showNotification(title, {
    body: body,
    icon: n.icon || d.icon || "icon-192.png",
    badge: "badge-96.png",
    data: { link: link },
    tag: d.tag || undefined
  })]));
});

self.addEventListener("notificationclick", function (e) {
  e.notification.close();
  var link = (e.notification.data && e.notification.data.link) || "./";
  var base = new URL("./", self.location.href);        // radice del sito
  var url = new URL(link, base).href;
  var root = url === base.href;                        // nessuna sezione: basta riportare in primo piano il sito
  e.waitUntil(self.clients.matchAll({ type: "window", includeUncontrolled: true }).then(function (list) {
    for (var i = 0; i < list.length; i++) {
      var c = list[i];
      if (("focus" in c) && (c.url === url || (root && c.url.indexOf(base.href) === 0))) return c.focus();
    }
    return self.clients.openWindow(url);
  }));
});
