// Archivio iscritti per le notifiche di rAKings VGC (Cloudflare Worker + KV, piano gratuito).
// Versione con Firebase: accetta sia gli ID OneSignal (UUID) sia i token Firebase.
// Il sito scrive con POST; il bot di GitHub legge con GET /list (serve il token ADMIN_TOKEN).
//   GET /list              -> solo iscrizioni OneSignal (come prima: il bot attuale non cambia)
//   GET /list?kind=fcm     -> solo token Firebase
//   GET /list?kind=all     -> tutte
//   Lettura A PAGINE (consigliata): aggiungere &limit=1000 (massimo 1000). Ogni risposta ha {n, subs} e, se ce ne sono altre,
//   anche {cursor}: si richiama lo stesso indirizzo aggiungendo &cursor=<valore> finche' non c'e' piu' il cursor.
//   Senza limit e senza cursor la risposta e' una sola, completa, come prima (i bot vecchi continuano a funzionare).
//   POST /remove           -> {"ids":[...]} toglie dall'archivio (serve ADMIN_TOKEN), per i token morti
//   GET /stats?limit=1000[&cursor=..]  -> CONTEGGI di una pagina di iscritti (serve ADMIN_TOKEN), per la pagina admin.html.
//                                         Non manda mai i token al browser: solo numeri. La pagina somma le risposte.
// ARGOMENTI FIREBASE (versione 2026-11-06a): SPENTI finche' non si imposta la variabile ARGOMENTI = on. Spenti, questo Worker si comporta
//   ESATTAMENTE come prima (nessuna chiamata a Google, nessun uso della coda). Accesi, dopo ogni scrittura di un token Firebase il Worker mette
//   un messaggio nella coda CODA; la coda (stesso Worker, funzione queue) allinea gli argomenti del dispositivo a quello che ha scelto
//   (archivio KV = fonte vera), con le credenziali dell'account Google SEPARATO (segreto FCM_TOPICS_KEY, solo permessi sulle iscrizioni).
//   Argomenti per dispositivo: tutti, c_<canale>, h_<categoria> (promemoria), t_<torneo seguito>.
// Collegamenti da creare nel pannello Cloudflare: KV namespace con nome variabile SUBS,
// segreto ADMIN_TOKEN, (facoltativa) variabile ALLOW_ORIGIN con l'indirizzo del sito.
// Solo per gli argomenti: coda CODA (producer + consumer del Worker), segreto FCM_TOPICS_KEY, variabile ARGOMENTI = on.
const CATS = ["money", "gc", "regionali", "vr", "vrreg", "maddos", "locali", "locali8", "player", "winner", "vrwin"];
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const FCM_TOKEN = /^[A-Za-z0-9_:\-]{100,400}$/;   // i token Firebase distinguono maiuscole e minuscole: non vanno mai modificati
const REFRESH_MS = 120 * 24 * 3600 * 1000; // si riscrive solo se qualcosa cambia o dopo 120 giorni (limite di scritture KV; erano 5 giorni)
const TTL_S = 730 * 24 * 3600;             // chi non apre il sito per 2 anni esce dall'archivio (i token morti li toglie comunque il bot)

function keyOf(id) {
  if (typeof id !== "string") return null;
  if (UUID.test(id)) return { key: "s:" + id.toLowerCase(), kind: "os" };
  if (FCM_TOKEN.test(id)) return { key: "f:" + id, kind: "fcm" };
  return null;
}

async function listKind(env, prefix, kind) {
  const subs = [];
  let cursor;
  do {
    const r = await env.SUBS.list({ prefix, cursor });
    for (const k of r.keys) if (k.metadata) subs.push({ id: k.name.slice(2), k: kind, ...k.metadata });
    cursor = r.list_complete ? undefined : r.cursor;
  } while (cursor);
  return subs;
}

// Una pagina = UNA sola lettura di KV, cosi' il tempo di calcolo per chiamata resta basso anche con tanti iscritti.
// Il cursor e' "<prefisso>:<cursor di KV>" (con kind=all prima si leggono le iscrizioni OneSignal "s", poi quelle Firebase "f").
async function rawPage(env, want, cursorIn, limit) {
  const order = want === "all" ? ["s", "f"] : want === "fcm" ? ["f"] : want === "os" ? ["s"] : [];
  let pi = 0, kvc;
  if (cursorIn) {
    const i = cursorIn.indexOf(":");
    pi = i < 0 ? -1 : order.indexOf(cursorIn.slice(0, i));
    if (pi < 0) throw new Error("cursor");
    kvc = cursorIn.slice(i + 1) || undefined;
  }
  if (pi >= order.length) return { p: null, keys: [], cursor: undefined };
  const p = order[pi];
  const r = await env.SUBS.list({ prefix: p + ":", cursor: kvc, limit });
  let cursor;
  if (!r.list_complete) cursor = p + ":" + r.cursor;
  else if (pi + 1 < order.length) cursor = order[pi + 1] + ":";
  return { p, keys: r.keys, cursor };
}

async function listPage(env, want, cursorIn, limit) {
  const g = await rawPage(env, want, cursorIn, limit);
  const subs = [];
  for (const k of g.keys) if (k.metadata) subs.push({ id: k.name.slice(2), k: g.p === "s" ? "os" : "fcm", ...k.metadata });
  return { subs, cursor: g.cursor };
}

// Conta una pagina di iscritti senza mai mostrare i token: solo numeri.
async function statPage(env, want, cursorIn, limit) {
  const g = await rawPage(env, want, cursorIn, limit);
  const st = { n: 0, fcm: 0, os: 0, c: {}, h: {}, l: {}, seguono: 0, tornei: 0, t1: 0, t7: 0, t30: 0 };
  const now = Date.now(), add = (o, k) => { o[k] = (o[k] || 0) + 1; };
  for (const k of g.keys) {
    const m = k.metadata; if (!m) continue;
    st.n++; if (g.p === "s") st.os++; else st.fcm++;
    for (const x of m.c || []) add(st.c, x);
    for (const x of m.h || []) add(st.h, x);
    add(st.l, m.l || "it");
    const nf = (m.f || []).length; if (nf) { st.seguono++; st.tornei += nf; }
    const eta = now - (m.t || 0); if (eta < 864e5) st.t1++; if (eta < 7 * 864e5) st.t7++; if (eta < 30 * 864e5) st.t30++;
  }
  if (g.cursor) st.cursor = g.cursor;
  return st;
}


// ======================= ARGOMENTI FIREBASE =======================
const VERSIONE = "2026-11-06b";
const MAX_CHIAMATE = 40;     // chiamate a Google per messaggio della coda (il limite del piano gratuito e' 50 per esecuzione, con GET e firma ne servono altre 2)
const PARALLELE = 6;
const MAX_CONTINUAZIONI = 10;
const VERIFICHE = [45, 120, 300];   // dopo aver scritto su Google si ricontrolla dopo 45 s, poi (se serve ancora) dopo 2 min e dopo 5 min: l'elenco di Google puo' essere indietro di qualche secondo
const NS = /^(tutti|c_[a-z0-9_]+|h_[a-z0-9]+|t_[0-9a-z]{1,8})$/;   // gli argomenti che gestiamo noi: tutti gli altri non si toccano mai

// Gli argomenti voluti da un dispositivo, dalle sue scelte. Nomi ammessi da Google: lettere, numeri, - _ . ~ %
function argomentiDi(m) {
  const s = new Set(["tutti"]);
  for (const x of (m && m.c) || []) {
    const n = x === "money=all" ? "money_all" : x === "money=33" ? "money_33" : x;
    if (/^[a-z0-9_]+$/.test(n)) s.add("c_" + n);
  }
  for (const x of (m && m.h) || []) if (/^[a-z0-9]+$/.test(x)) s.add("h_" + x);
  for (const x of (m && m.f) || []) if (/^[0-9a-z]{1,8}$/.test(x)) s.add("t_" + x);
  return s;
}

const ultimi6 = t => "..." + String(t).slice(-6);
const argomentiAcceso = env => env.ARGOMENTI === "on";

async function accoda(env, token, n, v, secondi) {
  if (!argomentiAcceso(env) || !env.CODA) return;
  try { await env.CODA.send({ k: token, n: n || 0, v: v || 0 }, secondi ? { delaySeconds: secondi } : undefined); }
  catch (e) { console.log("argomenti: coda non raggiunta", String((e && e.message) || e).slice(0, 80)); }   // l'archivio e' gia' scritto: si riallinea dopo
}

// --- accesso a Google: firma RS256 con la chiave dell'account separato (WebCrypto), riusata finche' vale ---
let _g = null;
const b64u = buf => btoa(String.fromCharCode(...new Uint8Array(buf))).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
async function accessGoogle(env) {
  const ora = Math.floor(Date.now() / 1000);
  if (_g && _g.exp - 120 > ora) return _g;
  let k;
  try { k = JSON.parse(env.FCM_TOPICS_KEY); } catch (e) { throw new Error("FCM_TOPICS_KEY non valido"); }
  const der = Uint8Array.from(atob(k.private_key.replace(/-----[^-]+-----/g, "").replace(/\s+/g, "")), c => c.charCodeAt(0));
  const chiave = await crypto.subtle.importKey("pkcs8", der.buffer, { name: "RSASSA-PKCS1-v1_5", hash: "SHA-256" }, false, ["sign"]);
  const enc = o => b64u(new TextEncoder().encode(JSON.stringify(o)));
  const corpo = enc({ alg: "RS256", typ: "JWT" }) + "." + enc({ iss: k.client_email, scope: "https://www.googleapis.com/auth/firebase.messaging", aud: "https://oauth2.googleapis.com/token", iat: ora, exp: ora + 3600 });
  const firma = await crypto.subtle.sign("RSASSA-PKCS1-v1_5", chiave, new TextEncoder().encode(corpo));
  const r = await fetch("https://oauth2.googleapis.com/token", { method: "POST", headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: "grant_type=" + encodeURIComponent("urn:ietf:params:oauth:grant-type:jwt-bearer") + "&assertion=" + corpo + "." + b64u(firma) });
  if (!r.ok) throw new Error("accesso a Google rifiutato: HTTP " + r.status);
  const j = await r.json();
  _g = { tok: j.access_token, exp: ora + (j.expires_in || 3600), progetto: k.project_id };
  return _g;
}

async function gcall(g, metodo, coda, token, corpo) {
  const url = "https://fcm.googleapis.com/v1/projects/" + g.progetto + "/registrations/" + token + "/topicSubscriptions" + coda;
  try {
    const r = await fetch(url, { method: metodo, headers: { Authorization: "Bearer " + g.tok, "Content-Type": "application/json; charset=UTF-8" }, body: corpo });
    const t = await r.text();
    return { st: r.status, txt: t };
  } catch (e) { return { st: 0, txt: String((e && e.message) || e) }; }
}
const morto = r => r.st === 404 && /UNREGISTERED|NOT_FOUND|not a valid FCM registration token/i.test(r.txt) || /UNREGISTERED/.test(r.txt);
const ritardo = n => Math.min(30 * Math.pow(2, Math.max(0, (n || 1) - 1)), 600);

// Allinea gli argomenti di UN dispositivo a quello che ha scelto. Ritorna "ok" oppure {retry: secondi}.
async function sincronizza(env, body) {
  const kv = keyOf(body && body.k);
  if (!kv || kv.kind !== "fcm") return "ok";
  const rec = await env.SUBS.getWithMetadata(kv.key);
  if (!rec.metadata) { console.log("argomenti: iscrizione non piu' in archivio", ultimi6(body.k)); return "ok"; }
  const t0 = rec.metadata.t, voluti = argomentiDi(rec.metadata);
  const g = await accessGoogle(env);

  // cosa ha oggi Google per questo dispositivo (e' la verita': niente stato salvato che possa sfasarsi)
  const gg = await gcall(g, "GET", "", body.k);
  if (morto(gg)) { console.log("argomenti: dispositivo non piu' valido", ultimi6(body.k)); return "ok"; }
  if (gg.st !== 200) return { retry: ritardo(body.attempts), perche: "elenco HTTP " + gg.st };
  let attuali = new Set();
  try { const j = JSON.parse(gg.txt); for (const x of j.topic_subscriptions || j.topicSubscriptions || []) { const n = x.topic_name || x.topicName; if (n && NS.test(n)) attuali.add(n); } } catch (e) {}

  const lavori = [...voluti].filter(x => !attuali.has(x)).map(x => ["add", x]).concat([...attuali].filter(x => !voluti.has(x)).map(x => ["del", x]));
  const adesso = lavori.slice(0, MAX_CHIAMATE);
  let prossimo = 0, errore = null, mortoQui = false;
  async function lavora() {
    while (prossimo < adesso.length && !errore && !mortoQui) {
      const [cosa, nome] = adesso[prossimo++];
      const r = cosa === "add" ? await gcall(g, "POST", "?topic_name=" + encodeURIComponent(nome), body.k, "{}") : await gcall(g, "DELETE", "/" + encodeURIComponent(nome), body.k);
      if (r.st === 200 || r.st === 409 || (cosa === "del" && r.st === 404 && !morto(r))) continue;
      if (morto(r)) mortoQui = true; else errore = "HTTP " + r.st;
    }
  }
  await Promise.all(Array.from({ length: Math.min(PARALLELE, adesso.length) }, lavora));
  if (mortoQui) { console.log("argomenti: dispositivo non piu' valido", ultimi6(body.k)); return "ok"; }
  if (errore) { console.log("argomenti: errore", errore, ultimi6(body.k)); return { retry: ritardo(body.attempts), perche: errore }; }

  if (lavori.length > adesso.length) {   // altre iscrizioni da fare: un nuovo messaggio (con un budget di chiamate tutto suo)
    if ((body.n || 0) + 1 > MAX_CONTINUAZIONI) { console.log("argomenti: troppe continuazioni", ultimi6(body.k)); return "ok"; }
    await env.CODA.send({ k: body.k, n: (body.n || 0) + 1, v: body.v || 0 });
    return "ok";
  }
  const dopo = await env.SUBS.getWithMetadata(kv.key);   // le scelte sono cambiate mentre lavoravo? allora si rifa' con quelle nuove
  if (dopo.metadata && dopo.metadata.t !== t0) { await env.CODA.send({ k: body.k, n: 0, v: 0 }); return "ok"; }
  // Ho scritto qualcosa su Google: l'ELENCO che ho letto all'inizio puo' essere in ritardo (es. un argomento appena tolto e subito rimesso),
  // quindi tra poco si ricontrolla con un elenco aggiornato. Se alla verifica e' tutto a posto, finisce li'.
  const v = body.v || 0;
  if (adesso.length > 0 && v < VERIFICHE.length) await accoda(env, body.k, 0, v + 1, VERIFICHE[v]);
  return "ok";
}

export default {
  async fetch(req, env) {
    const cors = {
      "Access-Control-Allow-Origin": env.ALLOW_ORIGIN || "*",
      "Access-Control-Allow-Methods": "POST, GET, OPTIONS",
      "Access-Control-Allow-Headers": "Content-Type, Authorization",
      "Access-Control-Max-Age": "86400",
    };
    const out = (o, s = 200) => new Response(JSON.stringify(o), { status: s, headers: { ...cors, "Content-Type": "application/json" } });
    if (req.method === "OPTIONS") return new Response(null, { headers: cors });
    const url = new URL(req.url);
    const admin = () => env.ADMIN_TOKEN && req.headers.get("Authorization") === "Bearer " + env.ADMIN_TOKEN;

    if (req.method === "GET" && url.pathname === "/list") {
      if (!admin()) return out({ error: "non autorizzato" }, 401);
      const want = url.searchParams.get("kind") || "os";
      const lim = url.searchParams.get("limit"), cur = url.searchParams.get("cursor");
      if (lim !== null || cur) {   // lettura a pagine
        const limit = Math.min(1000, Math.max(1, parseInt(lim, 10) || 1000));
        try {
          const r = await listPage(env, want, cur, limit);
          return out(r.cursor ? { n: r.subs.length, subs: r.subs, cursor: r.cursor } : { n: r.subs.length, subs: r.subs });
        } catch (e) {
          return out({ error: "cursor non valido" }, 400);
        }
      }
      let subs = [];
      if (want === "os" || want === "all") subs = subs.concat(await listKind(env, "s:", "os"));
      if (want === "fcm" || want === "all") subs = subs.concat(await listKind(env, "f:", "fcm"));
      return out({ n: subs.length, subs });
    }

    if (req.method === "GET" && url.pathname === "/stats") {
      if (!admin()) return out({ error: "non autorizzato" }, 401);
      const want = url.searchParams.get("kind") || "all";
      const limit = Math.min(1000, Math.max(1, parseInt(url.searchParams.get("limit"), 10) || 1000));
      try {
        return out(await statPage(env, want, url.searchParams.get("cursor"), limit));
      } catch (e) {
        return out({ error: "cursor non valido" }, 400);
      }
    }

    if (req.method === "POST" && url.pathname === "/remove") {
      if (!admin()) return out({ error: "non autorizzato" }, 401);
      let b;
      try { b = JSON.parse(await req.text()); } catch (e) { return out({ error: "json non valido" }, 400); }
      const ids = (b && Array.isArray(b.ids) ? b.ids : []).slice(0, 200);
      let removed = 0;
      for (const id of ids) {
        const k = keyOf(id);
        if (k) { await env.SUBS.delete(k.key); removed++; }
      }
      return out({ ok: true, removed });
    }

    if (req.method === "POST") {
      const txt = await req.text();
      if (txt.length > 4000) return out({ error: "troppo grande" }, 413);
      let b;
      try { b = JSON.parse(txt); } catch (e) { return out({ error: "json non valido" }, 400); }
      const k = b ? keyOf(b.id) : null;
      if (!k) return out({ error: "id non valido" }, 400);
      const c = (Array.isArray(b.c) ? b.c : []).filter(x => typeof x === "string" && (x === "money=all" || x === "money=33" || CATS.includes(x) && x !== "money")).slice(0, 12);
      const h = (Array.isArray(b.h) ? b.h : []).filter(x => CATS.includes(x)).slice(0, 12);
      const f = (Array.isArray(b.f) ? b.f : []).filter(x => typeof x === "string" && /^[0-9a-z]{1,8}$/.test(x)).slice(0, 50);
      const l = typeof b.l === "string" && /^[a-z]{2}(-[A-Za-z]{2,4})?$/.test(b.l) ? b.l : "it";
      const same = o => o && JSON.stringify([o.c, o.h, o.f, o.l]) === JSON.stringify([c, h, f, l]) && Date.now() - (o.t || 0) < REFRESH_MS;
      const cur = await env.SUBS.getWithMetadata(k.key);
      let scritto = false;
      if (!same(cur.metadata)) { await env.SUBS.put(k.key, "1", { metadata: { c, h, f, l, t: Date.now() }, expirationTtl: TTL_S }); scritto = true; }
      if (scritto && k.kind === "fcm") await accoda(env, b.id, 0);   // con ARGOMENTI spento non fa niente
      return out({ ok: true, tipo: k.kind });
    }

    return out({ ok: true, servizio: "archivio iscritti rAKings VGC ", v: VERSIONE, argomenti: argomentiAcceso(env) ? (env.CODA && env.FCM_TOPICS_KEY ? "on" : "on-ma-incompleto") : "off" });
  },

  // la coda degli argomenti: un messaggio per volta (Maximum batch size = 1), un dispositivo per messaggio
  async queue(batch, env) {
    for (const m of batch.messages) {
      try {
        const body = { ...m.body, attempts: m.attempts };
        const r = await sincronizza(env, body);
        if (r === "ok") m.ack(); else m.retry({ delaySeconds: r.retry });
      } catch (e) {
        console.log("argomenti: eccezione", String((e && e.message) || e).slice(0, 120));
        m.retry({ delaySeconds: ritardo(m.attempts) });
      }
    }
  },
};
