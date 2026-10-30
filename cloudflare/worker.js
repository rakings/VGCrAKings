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
// Collegamenti da creare nel pannello Cloudflare: KV namespace con nome variabile SUBS,
// segreto ADMIN_TOKEN, (facoltativa) variabile ALLOW_ORIGIN con l'indirizzo del sito.
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
      if (!same(cur.metadata)) await env.SUBS.put(k.key, "1", { metadata: { c, h, f, l, t: Date.now() }, expirationTtl: TTL_S });
      return out({ ok: true, tipo: k.kind });
    }

    return out({ ok: true, servizio: "archivio iscritti rAKings VGC " });
  },
};
