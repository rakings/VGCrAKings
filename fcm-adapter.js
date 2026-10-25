/* Adattatore Firebase per il sito: offre gli stessi comandi di OneSignal (OS.User.PushSubscription,
   OS.Notifications, ...) cosi' il resto del sito (spunte, salvataggio automatico, banner) non cambia.
   La configurazione e la chiave pubblica non sono segreti. */
(function () {
  if (window.__fcmAdapter) return;
  window.__fcmAdapter = 1;
  var CFG = {
    apiKey: "AIzaSyAPE0sYnI7oc-qXgsrQPc2qDvzkDx8u-mg",
    authDomain: "rakings-test.firebaseapp.com",
    projectId: "rakings-test",
    storageBucket: "rakings-test.firebasestorage.app",
    messagingSenderId: "719479182646",
    appId: "1:719479182646:web:82082cbd6c5afbbb02cf97"
  };
  var VAPID = "BE00sOYkRBGREzcGLV3zLSpdFdIp-zxmnuME0SnS-h3C6jpJG-lacZ0S6dUDF1IyaLyEz-R8iHkRmLStZnJbtp0";
  var G = "https://www.gstatic.com/firebasejs/13.1.0/";
  var B = location.pathname.replace(/[^\/]*$/, "");
  var OPTK = "fcm-optout";
  var token = "", mods = null, app = null, msg = null, listeners = [];

  function optedOut() { try { return localStorage.getItem(OPTK) === "1"; } catch (e) { return false; } }
  function setOpt(v) { try { if (v) localStorage.setItem(OPTK, "1"); else localStorage.removeItem(OPTK); } catch (e) {} }
  function perm() { return typeof Notification !== "undefined" && Notification.permission === "granted"; }
  function fire() { listeners.slice().forEach(function (f) { try { f(); } catch (e) {} }); }

  function loadMods() {
    if (!mods) {
      mods = Promise.all([import(G + "firebase-app.js"), import(G + "firebase-messaging.js")]).then(function (m) {
        window.OSFAIL = 0;
        return { a: m[0], m: m[1] };
      }, function (e) { mods = null; window.OSFAIL = 1; throw e; });
    }
    return mods;
  }

  function waitActive(r) {
    return new Promise(function (ok, ko) {
      if (r.active) return ok(r);
      var w = r.installing || r.waiting;
      if (!w) return ko(new Error("service worker non trovato"));
      w.addEventListener("statechange", function () {
        if (w.state === "activated") ok(r);
        if (w.state === "redundant") ko(new Error("service worker non installato"));
      });
    });
  }

  function fetchToken() {
    return loadMods().then(function (x) {
      app = app || x.a.initializeApp(CFG);
      msg = msg || x.m.getMessaging(app);
      return navigator.serviceWorker.register(B + "fcm-sw.js", { scope: B + "fcm-scope/" }).then(waitActive).then(function (r) {
        return x.m.getToken(msg, { vapidKey: VAPID, serviceWorkerRegistration: r });
      });
    }).then(function (t) {
      token = t || "";
      fire();
      return token;
    });
  }

  var PS = {
    get id() { return token; },
    get optedIn() { return !!token && perm() && !optedOut(); },
    optIn: function () { setOpt(false); return fetchToken(); },
    optOut: function () {
      setOpt(true);
      return loadMods().then(function (x) { return msg ? x.m.deleteToken(msg) : null; })
        .catch(function () {})
        .then(function () { token = ""; fire(); });
    },
    addEventListener: function (ev, f) { if (ev === "change") listeners.push(f); }
  };

  var OS = {
    init: function () {
      return loadMods().then(function () {
        if (perm() && !optedOut()) return fetchToken().catch(function () {});
      });
    },
    Notifications: {
      get permission() { return perm(); },
      requestPermission: function () {
        if (typeof Notification === "undefined") return Promise.resolve(false);
        return Promise.resolve(Notification.requestPermission()).then(function (p) { return p === "granted"; });
      },
      setDefaultUrl: function () { return Promise.resolve(); },
      addEventListener: function (ev, f) {
        if (ev !== "permissionChange" || !navigator.permissions) return;
        navigator.permissions.query({ name: "notifications" }).then(function (s) { s.addEventListener("change", f); }).catch(function () {});
      }
    },
    User: {
      PushSubscription: PS,
      addTags: function () { return Promise.resolve(); },
      addTag: function () { return Promise.resolve(); },
      removeTag: function () { return Promise.resolve(); },
      getTags: function () { return Promise.resolve({}); }
    }
  };

  var q = Array.isArray(window.OneSignalDeferred) ? window.OneSignalDeferred : [];
  window.OneSignalDeferred = { push: function (fn) { try { return fn(OS); } catch (e) {} } };
  q.forEach(function (fn) { try { fn(OS); } catch (e) {} });
})();
