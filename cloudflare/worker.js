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
//   PARTNER (dal 2026-11-13a): GET /partner/stato e POST /partner/invia con il codice del partner (segreto PARDINI_TOKEN):
//     la pagina partner-pardini.html del sito manda avvisi al canale «pardini» (testo libero o «e' in live»), con limiti.
//     Il Worker controlla codice, testi, link e limiti, poi avvia il flusso GitHub «Avviso partner» (segreto GH_AVVISI).
//     Ogni avviso scritto esce anche in BACHECA (annunci.json, etichetta «Francesco Pardini», con articolo e immagine facoltativi):
//     l'immagine passa dal KV (partner:img:<id>, scade in 2 giorni) e il flusso la copia nel sito (GET /partner/img/<id>, codice admin).
//     POST /admin/rimuovi-annuncio {id} (solo ADMIN_TOKEN, dalla pagina admin privata): avvia «Rimuovi annuncio partner».
//   LIKE (2026-11-14d): POST /like {dev, ops:[[idAnnuncio, 1|0], ...]} pubblico, a pacchetti; GET /like/conteggi (ADMIN_TOKEN) per il flusso orario.
//     Serve il collegamento D1 con nome LIKE (le tabelle si creano da sole). Senza, i like restano solo sul telefono.
//   SOCIAL (2026-11-15a): POST /admin/social {id, rete: ig|x, azione: approva|rifiuta|fatto, testo} (solo ADMIN_TOKEN, dalla pagina admin):
//     avvia il flusso «Social - azione dall'admin» del sito (segreto GH_AVVISI). La chiave di Instagram resta SOLO su GitHub.
//   RICHIESTE LOCALI: GET /admin/richieste e POST /admin/richieste/etichetta (ADMIN_TOKEN), con GH_RICHIESTE e RICHIESTE_REPO.
//     GET /partner/statistiche: gli stessi numeri della pagina admin (mai i token), aggiornabili ogni 10 minuti.
//     Per spegnerlo: variabile PARDINI_ATTIVO = off (oppure cancella il segreto PARDINI_TOKEN).
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
const CATS = ["money", "gc", "regionali", "vr", "vrreg", "maddos", "locali", "locali8", "player", "winner", "vrwin", "pardini"];
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
  return contaChiavi(await rawPage(env, want, cursorIn, limit));
}
function contaChiavi(g) {
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
const VERSIONE = "2026-11-15a";
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


// ======================= PARTNER: avvisi mandati da un creator (Francesco Pardini) =======================
const PARTNER = {
  pardini: {
    nome: "Francesco Pardini",
    canale: "pardini",
    live: { titolo: "Francesco Pardini \u00e8 in live", testo: "Tocca per guardare la diretta su Twitch.", link: "https://www.twitch.tv/francescopardinivgc" },
  },
};
const LIMITI = {
  testo: { attesa: 10 * 60, giorno: 8, settimana: 35 },   // avvisi scritti da lui
  live:  { attesa: 30 * 60, giorno: 4, settimana: 20 },   // tasto «sono in live»: contatori separati
};
const HOST_OK = /^(www\.|m\.)?(twitch\.tv|youtube\.com|youtu\.be)$|^rakings\.github\.io$/i;
const PARTNER_FLUSSO = "https://api.github.com/repos/rakings/VGCrAKings/actions/workflows/avviso-partner.yml/dispatches";

async function hashTesto(t) {
  const d = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(String(t || "")));
  return Array.from(new Uint8Array(d), b => b.toString(16).padStart(2, "0")).join("");
}
// il codice si confronta tramite impronta: stesso tempo qualunque sia il codice scritto
async function partnerDi(req, env) {
  const tok = (req.headers.get("Authorization") || "").replace(/^Bearer\s+/i, "");
  const giusto = env.PARDINI_TOKEN;   // segreto con il codice di Francesco (gli spazi in piu' all'inizio o alla fine non contano)
  if (!giusto || tok.length < 20) return null;
  return (await hashTesto(tok)) === (await hashTesto(String(giusto).trim())) ? "pardini" : null;
}
function pulisci(s, max) {
  return String(s || "").replace(/[\u0000-\u001f\u007f]+/g, " ").replace(/\s+/g, " ").trim().slice(0, max);
}
function linkOk(u) {
  if (!u) return "";
  try { const x = new URL(u); return x.protocol === "https:" && HOST_OK.test(x.hostname) ? x.href : null; } catch (e) { return null; }
}
function conti(lista, ora) {
  const g = lista.filter(t => ora - t < 86400).length, s = lista.filter(t => ora - t < 7 * 86400).length;
  const ult = lista.length ? Math.max(...lista) : 0;
  return { g, s, ult };
}
function quote(st, ora) {
  const out = {};
  for (const tipo of ["testo", "live"]) {
    const L = LIMITI[tipo], c = conti(st[tipo] || [], ora);
    out[tipo] = { oggi: Math.max(0, L.giorno - c.g), settimana: Math.max(0, L.settimana - c.s), tra: Math.max(0, c.ult + L.attesa - ora),
                  limiti: { giorno: L.giorno, settimana: L.settimana, attesa_min: L.attesa / 60 } };
  }
  return out;
}
async function statoPartner(env, p) {
  const st = (await env.SUBS.get("partner:" + p, "json")) || {};
  return { testo: st.testo || [], live: st.live || [], log: st.log || [] };
}
// Statistiche per il partner: gli stessi NUMERI della pagina admin (mai i token), a pagine come /stats.
// In piu' conta i tornei seguiti ADESSO: la pagina manda i codici dei tornei non ancora finiti (li calcola da events.json, pubblico).
// Si possono aggiornare al massimo ogni 10 minuti (ogni pagina e' una lettura di KV: il piano gratuito ne ha 1.000 al giorno).
const PARTNER_STAT_OGNI = 10 * 60;
async function statPartner(env, url, ora) {
  const cur = url.searchParams.get("cursor");
  if (!cur) {
    const ultimo = Number(await env.SUBS.get("partner:statT")) || 0;
    if (ora - ultimo < PARTNER_STAT_OGNI) return { attendi: ultimo + PARTNER_STAT_OGNI - ora };
    await env.SUBS.put("partner:statT", String(ora));
  }
  const vivi = new Set((url.searchParams.get("attivi") || "").split(",").filter(x => /^[0-9a-z]{1,8}$/.test(x)).slice(0, 500));
  const g = await rawPage(env, "all", cur, 1000);   // UNA lettura di KV per pagina, come /stats
  const st = contaChiavi(g);
  const att = { persone: 0, scelte: 0, conta: {} };
  for (const k of g.keys) {
    const f = ((k.metadata && k.metadata.f) || []).filter(c => vivi.has(c));
    if (f.length) { att.persone++; att.scelte += f.length; }
    for (const c of f) att.conta[c] = (att.conta[c] || 0) + 1;
  }
  st.attivi = att;
  return st;
}

async function partnerRoute(req, env, url, out) {
  const p = await partnerDi(req, env);
  if (!p) return out({ error: "Codice non valido." }, 401);
  if (req.method === "GET" && url.pathname === "/partner/statistiche") {
    try {
      const r = await statPartner(env, url, Math.floor(Date.now() / 1000));
      return r.attendi ? out({ error: "Statistiche aggiornabili tra " + Math.ceil(r.attendi / 60) + " minuti.", attendi: r.attendi }, 429) : out(r);
    } catch (e) { return out({ error: "cursor non valido" }, 400); }
  }
  const P = PARTNER[p], ora = Math.floor(Date.now() / 1000), attivo = (env.PARDINI_ATTIVO || "on") !== "off";
  const st = await statoPartner(env, p);
  if (req.method === "GET" && url.pathname === "/partner/stato")
    return out({ ok: true, nome: P.nome, attivo, live: P.live, quote: quote(st, ora), log: st.log.slice(-20).reverse() });
  if (req.method !== "POST" || url.pathname !== "/partner/invia") return out({ error: "richiesta non valida" }, 400);
  if (!attivo) return out({ error: "Gli avvisi sono sospesi: contatta Andrea." }, 403);
  if (!env.GH_AVVISI) return out({ error: "Invio non configurato (manca GH_AVVISI): contatta Andrea." }, 503);
  const txt = await req.text();
  if (txt.length > 1100000) return out({ error: "Immagine troppo grande." }, 413);
  let b; try { b = JSON.parse(txt); } catch (e) { return out({ error: "json non valido" }, 400); }
  const tipo = b && b.tipo === "live" ? "live" : "testo";
  let titolo, testo, link, articolo = "", img = null;
  if (tipo === "live") ({ titolo, testo, link } = P.live);
  else {
    titolo = pulisci(b.titolo, 60); testo = pulisci(b.testo, 180); link = linkOk(pulisci(b.link, 300));
    articolo = String(b.articolo || "").replace(/\r/g, "").replace(/[\u0000-\u0009\u000b-\u001f\u007f]+/g, " ").replace(/\n{3,}/g, "\n\n").trim().slice(0, 2000);
    if (titolo.length < 3) return out({ error: "Il titolo deve avere almeno 3 caratteri." }, 400);
    if (testo.length < 3) return out({ error: "Il testo deve avere almeno 3 caratteri." }, 400);
    if (link === null) return out({ error: "Link non ammesso: solo Twitch, YouTube o il sito rAKings (https)." }, 400);
    if (b.img) {   // immagine dell'annuncio in bacheca: solo JPEG (la pagina la converte e la rimpicciolisce). Resta in base64:
      // niente decodifica qui (il piano gratuito concede pochi millisecondi di calcolo); la controlla e decodifica il flusso GitHub
      const s64 = String(b.img).replace(/^data:image\/jpeg;base64,/, "");
      if (s64 === String(b.img) || !/^\/9j\//.test(s64) || s64.length < 200 || s64.length > 1000000 || /[^A-Za-z0-9+/=]/.test(s64.slice(0, 4000)))
        return out({ error: "Immagine non valida: usa una foto JPG o PNG (massimo circa 700 KB dopo la riduzione)." }, 400);
      img = s64;
    }
  }
  const L = LIMITI[tipo], c = conti(st[tipo], ora);
  // l'immagine si salva PRIMA di avviare il flusso (che la scarica con il codice admin); scade da sola dopo 2 giorni
  if (ora - c.ult < L.attesa) return out({ error: "Aspetta ancora " + Math.ceil((c.ult + L.attesa - ora) / 60) + " minuti.", quote: quote(st, ora) }, 429);
  if (c.g >= L.giorno) return out({ error: "Limite di oggi raggiunto (" + L.giorno + " in 24 ore).", quote: quote(st, ora) }, 429);
  if (c.s >= L.settimana) return out({ error: "Limite della settimana raggiunto (" + L.settimana + " in 7 giorni).", quote: quote(st, ora) }, 429);
  if (img) await env.SUBS.put("partner:img:" + ora, img, { expirationTtl: 2 * 86400 });
  const r = await fetch(PARTNER_FLUSSO, {
    method: "POST",
    headers: { "Authorization": "Bearer " + env.GH_AVVISI, "Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28",
               "User-Agent": "vgc-subs-partner", "Content-Type": "application/json" },
    body: JSON.stringify({ ref: "main", inputs: { partner: p, id: String(ora), titolo, testo, link: link || "",
                                                  bacheca: tipo === "testo" ? "1" : "", articolo, img: img ? "1" : "" } }),
  });
  if (r.status !== 204) {
    console.log("partner: avvio flusso non riuscito", r.status);
    return out({ error: "Invio non riuscito (GitHub " + r.status + "). Riprova tra poco; se succede ancora contatta Andrea." }, 502);
  }
  if (tipo === "testo")   // copia dell'annuncio per 2 giorni: l'app la legge da qui se GitHub Pages non l'ha ancora pubblicato (puo' metterci minuti)
    await env.SUBS.put("partner:ann:" + ora, JSON.stringify({ id: ora, t: titolo, d: articolo || testo, pub: new Date(ora * 1000).toISOString().slice(0, 19) + "Z",
                                                             partner: p, link: link || "", img: !!img }), { expirationTtl: 2 * 86400 });
  st[tipo] = st[tipo].filter(t => ora - t < 7 * 86400).concat([ora]);
  st.log = st.log.concat([{ t: ora, tipo, titolo, testo, link: link || "", img: !!img, bacheca: tipo === "testo" }]).slice(-30);
  await env.SUBS.put("partner:" + p, JSON.stringify(st));
  return out({ ok: true, quote: quote(st, ora) });
}


// ======================= LIKE IN BACHECA (database D1, collegamento LIKE) =======================
// Un like per telefono (codice casuale del telefono, non il token delle notifiche). Il telefono manda i like a PACCHETTI.
// I numeri NON si leggono da qui: un flusso GitHub li copia ogni ora in likes.json (il sito li legge da GitHub, zero carico).
// Freno: oltre LIKE_MAX_GIORNO operazioni in un giorno si smette di contare fino al giorno dopo (il resto del Worker non risente).
const LIKE_MAX_GIORNO = 50000, LIKE_MAX_PACCHETTO = 50;
let LIKE_PRONTO = false;
async function likeDb(env) {
  if (!env.LIKE) return null;
  if (!LIKE_PRONTO) {
    await env.LIKE.batch([
      env.LIKE.prepare("CREATE TABLE IF NOT EXISTS l (ann INTEGER NOT NULL, dev TEXT NOT NULL, PRIMARY KEY (ann, dev))"),
      env.LIKE.prepare("CREATE TABLE IF NOT EXISTS g (d TEXT PRIMARY KEY, n INTEGER NOT NULL)"),
    ]);
    LIKE_PRONTO = true;
  }
  return env.LIKE;
}
async function likeRoute(req, env, url, out, admin) {
  const db = await likeDb(env);
  if (!db) return out({ error: "like non attivi (manca il database LIKE)" }, 503);
  if (req.method === "GET" && url.pathname === "/like/conteggi") {
    if (!admin()) return out({ error: "non autorizzato" }, 401);
    const r = await db.prepare("SELECT ann, COUNT(*) AS c FROM l GROUP BY ann").all();
    const c = {}; for (const x of r.results || []) c[String(x.ann)] = x.c;
    return out({ ok: true, c });
  }
  if (req.method !== "POST" || url.pathname !== "/like") return out({ error: "richiesta non valida" }, 400);
  const txt = await req.text();
  if (txt.length > 5000) return out({ error: "troppo grande" }, 413);
  let b; try { b = JSON.parse(txt); } catch (e) { return out({ error: "json non valido" }, 400); }
  const dev = String((b && b.dev) || "");
  if (!/^[a-z0-9]{12,40}$/.test(dev)) return out({ error: "telefono non valido" }, 400);
  const ops = (Array.isArray(b.ops) ? b.ops : []).filter(o => Array.isArray(o) && /^\d{1,11}$/.test(String(o[0]))).slice(0, LIKE_MAX_PACCHETTO);
  if (!ops.length) return out({ ok: true, n: 0 });
  const oggi = new Date().toISOString().slice(0, 10);
  const g = await db.prepare("SELECT n FROM g WHERE d = ?").bind(oggi).first();
  if (g && g.n + ops.length > LIKE_MAX_GIORNO) return out({ ok: true, pausa: true });
  const st = ops.map(o => o[1] ? db.prepare("INSERT OR IGNORE INTO l (ann, dev) VALUES (?, ?)").bind(Number(o[0]), dev)
                               : db.prepare("DELETE FROM l WHERE ann = ? AND dev = ?").bind(Number(o[0]), dev));
  st.push(db.prepare("INSERT INTO g (d, n) VALUES (?, ?) ON CONFLICT(d) DO UPDATE SET n = n + excluded.n").bind(oggi, ops.length));
  await db.batch(st);
  return out({ ok: true, n: ops.length });
}

// ======================= RICHIESTE DEI LOCALI (Issue della repo privata) nella pagina admin =======================
// Segreto GH_RICHIESTE = chiave GitHub di Andrea con «Issues: lettura e scrittura» SOLO sulla repo privata; variabile RICHIESTE_REPO = "proprietario/nome".
// La chiave e' di Andrea, quindi l'etichetta risulta messa da lui: il controllo della repo privata («solo il proprietario») la accetta.
const ETICHETTE_OK = ["approvato", "rifiutato", "rimosso", "fissato"];
async function ghRichieste(env, metodo, percorso, corpo) {
  return fetch("https://api.github.com/repos/" + env.RICHIESTE_REPO + percorso, {
    method: metodo,
    headers: { "Authorization": "Bearer " + env.GH_RICHIESTE, "Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28",
               "User-Agent": "vgc-subs-admin", "Content-Type": "application/json" },
    body: corpo ? JSON.stringify(corpo) : undefined,
  });
}
async function richiesteRoute(req, env, url, out, admin) {
  if (!admin()) return out({ error: "non autorizzato" }, 401);
  if (!env.GH_RICHIESTE || !/^[\w.-]+\/[\w.-]+$/.test(env.RICHIESTE_REPO || "")) return out({ error: "mancano GH_RICHIESTE o RICHIESTE_REPO su Cloudflare" }, 503);
  if (req.method === "GET" && url.pathname === "/admin/richieste") {
    const r = await ghRichieste(env, "GET", "/issues?state=open&per_page=60&sort=created&direction=desc");
    if (!r.ok) return out({ error: "GitHub ha risposto " + r.status }, 502);
    const l = (await r.json()).filter(i => !i.pull_request && i.user && i.user.login === "github-actions[bot]")
      .map(i => ({ n: i.number, t: i.title, body: String(i.body || "").slice(0, 20000), labels: (i.labels || []).map(x => x.name), creata: i.created_at, url: i.html_url }));
    return out({ ok: true, richieste: l });
  }
  if (req.method === "POST" && url.pathname === "/admin/richieste/etichetta") {
    let b; try { b = JSON.parse(await req.text()); } catch (e) { return out({ error: "json non valido" }, 400); }
    const n = Number(b && b.n), lab = String((b && b.label) || ""), togli = !!(b && b.togli);
    if (!Number.isInteger(n) || n < 1 || !ETICHETTE_OK.includes(lab) || (togli && lab !== "fissato")) return out({ error: "richiesta non valida" }, 400);
    const r = togli ? await ghRichieste(env, "DELETE", "/issues/" + n + "/labels/" + lab)
                    : await ghRichieste(env, "POST", "/issues/" + n + "/labels", { labels: [lab] });
    return r.ok ? out({ ok: true }) : out({ error: "GitHub ha risposto " + r.status }, 502);
  }
  return out({ error: "richiesta non valida" }, 400);
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

    if (url.pathname === "/partner/stato" || url.pathname === "/partner/invia" || url.pathname === "/partner/statistiche") return partnerRoute(req, env, url, out);
    if (url.pathname === "/like" || url.pathname === "/like/conteggi") {
      try { return await likeRoute(req, env, url, out, admin); } catch (e) { console.log("like:", String(e && e.message || e).slice(0, 120)); return out({ error: "like non disponibili" }, 503); }
    }
    if (url.pathname === "/admin/richieste" || url.pathname === "/admin/richieste/etichetta") return richiesteRoute(req, env, url, out, admin);
    if (req.method === "POST" && url.pathname === "/admin/social") {   // SOLO Andrea (ADMIN_TOKEN): approva/rifiuta un post per Instagram o X
      if (!admin()) return out({ error: "non autorizzato" }, 401);
      let b; try { b = JSON.parse(await req.text()); } catch (e) { return out({ error: "json non valido" }, 400); }
      const id = String((b && b.id) || ""), rete = String((b && b.rete) || ""), az = String((b && b.azione) || "");
      const testo = typeof (b && b.testo) === "string" ? b.testo.slice(0, 2200) : "";
      if (!/^[a-z]{2,8}-\d{1,10}$/.test(id) || !["ig", "x"].includes(rete) || !["approva", "rifiuta", "fatto"].includes(az)
          || (rete === "ig" && az === "fatto") || (rete === "x" && az === "approva")) return out({ error: "richiesta non valida" }, 400);
      if (!env.GH_AVVISI) return out({ error: "manca il segreto GH_AVVISI" }, 503);
      const r = await fetch("https://api.github.com/repos/rakings/VGCrAKings/actions/workflows/social-azione.yml/dispatches", {
        method: "POST",
        headers: { "Authorization": "Bearer " + env.GH_AVVISI, "Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28",
                   "User-Agent": "vgc-subs-admin", "Content-Type": "application/json" },
        body: JSON.stringify({ ref: "main", inputs: { id, rete, azione: az, testo } }),
      });
      if (r.status !== 204) return out({ error: "GitHub ha risposto " + r.status }, 502);
      return out({ ok: true });
    }
    if (req.method === "POST" && url.pathname === "/admin/rimuovi-annuncio") {   // SOLO Andrea (ADMIN_TOKEN): toglie un annuncio di un partner dalla bacheca
      if (!admin()) return out({ error: "non autorizzato" }, 401);
      let b; try { b = JSON.parse(await req.text()); } catch (e) { return out({ error: "json non valido" }, 400); }
      const id = String((b && b.id) || "");
      if (!/^\d{9,11}$/.test(id)) return out({ error: "id non valido" }, 400);
      if (!env.GH_AVVISI) return out({ error: "manca il segreto GH_AVVISI" }, 503);
      const r = await fetch("https://api.github.com/repos/rakings/VGCrAKings/actions/workflows/rimuovi-annuncio-partner.yml/dispatches", {
        method: "POST",
        headers: { "Authorization": "Bearer " + env.GH_AVVISI, "Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28",
                   "User-Agent": "vgc-subs-admin", "Content-Type": "application/json" },
        body: JSON.stringify({ ref: "main", inputs: { id } }),
      });
      if (r.status !== 204) return out({ error: "GitHub ha risposto " + r.status }, 502);
      await env.SUBS.delete("partner:ann:" + id);   // anche la copia veloce: il tocco su una vecchia notifica non lo mostra piu'
      await env.SUBS.delete("partner:img:" + id);
      return out({ ok: true });
    }
    if (req.method === "GET" && /^\/partner\/annuncio\/\d{9,11}$/.test(url.pathname)) {   // PUBBLICO: un annuncio del partner appena mandato
      const id = url.pathname.split("/").pop();
      const a = await env.SUBS.get("partner:ann:" + id, "json");
      if (!a) return out({ error: "non trovato" }, 404);
      if (a.img) { const im = await env.SUBS.get("partner:img:" + id); if (im) a.img64 = im; }
      delete a.img;
      return out(a);
    }
    if (req.method === "GET" && /^\/partner\/img\/\d{9,11}$/.test(url.pathname)) {   // solo per il flusso GitHub (codice admin): l'immagine dell'annuncio
      if (!admin()) return out({ error: "non autorizzato" }, 401);
      const im = await env.SUBS.get("partner:img:" + url.pathname.split("/").pop());
      return im ? new Response(im, { headers: { ...cors, "Content-Type": "text/plain" } }) : out({ error: "immagine non trovata" }, 404);   // base64 del JPEG
    }

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
      const c = (Array.isArray(b.c) ? b.c : []).filter(x => typeof x === "string" && (x === "money=all" || x === "money=33" || CATS.includes(x) && x !== "money")).slice(0, 16);
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
