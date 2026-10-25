// Archivio iscritti per le notifiche di rAKings VGC (Cloudflare Worker + KV, piano gratuito).
// Versione con Firebase: accetta sia gli ID OneSignal (UUID) sia i token Firebase.
// Il sito scrive con POST; il bot di GitHub legge con GET /list (serve il token ADMIN_TOKEN).
//   GET /list              -> solo iscrizioni OneSignal (come prima: il bot attuale non cambia)
//   GET /list?kind=fcm     -> solo token Firebase
//   GET /list?kind=all     -> tutte
//   POST /remove           -> {"ids":[...]} toglie dall'archivio (serve ADMIN_TOKEN), per i token morti
// Collegamenti da creare nel pannello Cloudflare: KV namespace con nome variabile SUBS,
// segreto ADMIN_TOKEN, (facoltativa) variabile ALLOW_ORIGIN con l'indirizzo del sito.
const CATS = ["money", "gc", "regionali", "vr", "vrreg", "maddos", "locali", "locali8", "player", "winner", "vrwin"];
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const FCM_TOKEN = /^[A-Za-z0-9_:\-]{100,400}$/;   // i token Firebase distinguono maiuscole e minuscole: non vanno mai modificati
const REFRESH_MS = 5 * 24 * 3600 * 1000;   // si riscrive solo se qualcosa cambia o dopo 5 giorni (limite di scritture KV)
const TTL_S = 150 * 24 * 3600;             // chi non apre il sito per 150 giorni esce dall'archivio

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
      let subs = [];
      if (want === "os" || want === "all") subs = subs.concat(await listKind(env, "s:", "os"));
      if (want === "fcm" || want === "all") subs = subs.concat(await listKind(env, "f:", "fcm"));
      return out({ n: subs.length, subs });
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
