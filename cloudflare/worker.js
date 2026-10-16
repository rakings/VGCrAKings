// Archivio iscritti per le notifiche di rAKings VGC (Cloudflare Worker + KV, piano gratuito).
// Salva, per ogni iscrizione OneSignal, le categorie scelte, i promemoria e i tornei seguiti.
// Il sito scrive con POST; il bot di GitHub legge con GET /list (serve il token ADMIN_TOKEN).
// Collegamenti da creare nel pannello Cloudflare: KV namespace con nome variabile SUBS,
// segreto ADMIN_TOKEN, (facoltativa) variabile ALLOW_ORIGIN con l'indirizzo del sito.
const CATS = ["money", "gc", "regionali", "vr", "maddos", "locali", "player", "winner", "vrwin"];
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const REFRESH_MS = 5 * 24 * 3600 * 1000;   // si riscrive solo se qualcosa cambia o dopo 5 giorni (limite di scritture KV)
const TTL_S = 150 * 24 * 3600;             // chi non apre il sito per 150 giorni esce dall'archivio

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

    if (req.method === "GET" && url.pathname === "/list") {
      if (!env.ADMIN_TOKEN || req.headers.get("Authorization") !== "Bearer " + env.ADMIN_TOKEN) return out({ error: "non autorizzato" }, 401);
      const subs = [];
      let cursor;
      do {
        const r = await env.SUBS.list({ prefix: "s:", cursor });
        for (const k of r.keys) if (k.metadata) subs.push({ id: k.name.slice(2), ...k.metadata });
        cursor = r.list_complete ? undefined : r.cursor;
      } while (cursor);
      return out({ n: subs.length, subs });
    }

    if (req.method === "POST") {
      const txt = await req.text();
      if (txt.length > 4000) return out({ error: "troppo grande" }, 413);
      let b;
      try { b = JSON.parse(txt); } catch (e) { return out({ error: "json non valido" }, 400); }
      if (!b || typeof b.id !== "string" || !UUID.test(b.id)) return out({ error: "id non valido" }, 400);
      const c = (Array.isArray(b.c) ? b.c : []).filter(x => typeof x === "string" && (x === "money=all" || x === "money=33" || CATS.includes(x) && x !== "money")).slice(0, 12);
      const h = (Array.isArray(b.h) ? b.h : []).filter(x => CATS.includes(x)).slice(0, 12);
      const f = (Array.isArray(b.f) ? b.f : []).filter(x => typeof x === "string" && /^[0-9a-z]{1,8}$/.test(x)).slice(0, 50);
      const l = typeof b.l === "string" && /^[a-z]{2}(-[A-Za-z]{2,4})?$/.test(b.l) ? b.l : "it";
      const key = "s:" + b.id.toLowerCase();
      const same = o => o && JSON.stringify([o.c, o.h, o.f, o.l]) === JSON.stringify([c, h, f, l]) && Date.now() - (o.t || 0) < REFRESH_MS;
      const cur = await env.SUBS.getWithMetadata(key);
      if (!same(cur.metadata)) await env.SUBS.put(key, "1", { metadata: { c, h, f, l, t: Date.now() }, expirationTtl: TTL_S });
      return out({ ok: true });
    }

    return out({ ok: true, servizio: "archivio iscritti rAKings VGC" });
  },
};
