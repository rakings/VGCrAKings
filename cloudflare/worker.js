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
//   CONFERMA ARGOMENTI (2026-11-17b): quando Google conferma che un telefono e' iscritto a TUTTI i suoi argomenti, il Worker lo segna nel
//     database D1 «LIKE» (tabella argok: chiave del telefono + firma delle sue scelte). Niente scritture KV in piu'.
//     GET /list?...&conf=1 aggiunge "a":1 ai telefoni confermati: in modo «new» il flusso manda l'argomento a tutti e l'invio diretto
//     SOLO ai non confermati (nessuno resta scoperto). GET /stats?...&conf=1 conta i confermati (pagina admin).
//     Giro orario dal Cron: rimette in coda (al massimo GIRO_MAX all'ora) i telefoni non ancora confermati e pulisce le righe vecchie.
//   ANNUNCIO DI ANDREA (2026-11-17): POST /admin/annuncio {titolo, testo, link, articolo, img} (solo ADMIN_TOKEN, dalla pagina admin):
//     stesso percorso degli annunci di Francesco (flusso «Avviso partner», partner «rakings»), etichetta «rAKings VGC» in bacheca,
//     notifica OBBLIGATORIA a tutti gli iscritti. Nessun limite (solo 1 minuto tra due invii, contro il doppio tocco).
//   LIKE (2026-11-14d): POST /like {dev, ops:[[idAnnuncio, 1|0], ...]} pubblico, a pacchetti; GET /like/conteggi (ADMIN_TOKEN) per il flusso orario.
//     Serve il collegamento D1 con nome LIKE (le tabelle si creano da sole). Senza, i like restano solo sul telefono.
//   PROTEZIONE (2026-11-15d, limiti allargati in 2026-11-15e): limite per indirizzo IP sulle scritture (iscrizioni 150 e like 400 ogni 10 minuti), in memoria (niente KV);
//     un'iscrizione NUOVA viene prima verificata con Google: i telefoni inventati non vengono scritti (con ARGOMENTI acceso);
//     la coda degli argomenti cancella dall'archivio i telefoni che Google dice non esistere piu'.
//   AVVISI AUTOMATICI (2026-11-15b): live Twitch + live e video YouTube di Francesco, con le API ufficiali (vedi sotto, «AVVISI AUTOMATICI»).
//     POST /auto/twitch, GET|POST /auto/youtube (li chiamano Twitch e YouTube, con firma), GET /admin/auto (ADMIN_TOKEN), giro ogni 5 minuti (Cron).
//   SOCIAL (2026-11-17, + YouTube Shorts): POST /admin/social {id, rete: ig|x|yt, azione: approva|rifiuta|fatto, testo} (solo ADMIN_TOKEN, dalla pagina admin):
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

// ---- limite per indirizzo IP, in memoria (gratis, nessuna scrittura su KV). Vale per ogni server Cloudflare separatamente:
// non e' perfetto, ma ferma chi manda raffiche da un solo indirizzo, che e' il caso piu' probabile.
const LIM = new Map();
function troppe(req, tipo, max, finestraS) {
  const ip = req.headers.get("CF-Connecting-IP") || "?", k = tipo + "|" + ip, ora = Date.now();
  let v = LIM.get(k);
  if (!v || ora - v[0] > finestraS * 1000) v = [ora, 0];
  v[1]++; LIM.set(k, v);
  if (LIM.size > 5000) { for (const [kk, vv] of LIM) if (ora - vv[0] > 3600 * 1000) LIM.delete(kk); if (LIM.size > 5000) LIM.clear(); }
  return v[1] > max;
}
// Limiti LARGHI apposta (2026-11-15e): molti telefoni possono uscire dallo stesso indirizzo (wifi di un torneo, operatori mobili
// che condividono gli indirizzi). Gli iscritti inventati li ferma gia' il controllo con Google; qui si fermano solo le raffiche.
const LIM_ISCRIZIONI = 150;  // scritture di iscrizioni per indirizzo IP ogni 10 minuti (oltre: l'app riprova da sola)
const LIM_LIKE = 400;        // pacchetti di like per indirizzo IP ogni 10 minuti (oltre: il like resta sul telefono e parte piu' tardi)

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

async function listPage(env, want, cursorIn, limit, conf) {
  const g = await rawPage(env, want, cursorIn, limit);
  let ok = null;
  if (conf && g.p === "f") { try { ok = await confermati(env, g.keys); } catch (e) { ok = null; } }   // senza database: nessuno confermato (invio diretto a tutti)
  const subs = [];
  for (const k of g.keys) if (k.metadata) subs.push(ok && ok.has(k.name) ? { id: k.name.slice(2), k: "fcm", ...k.metadata, a: 1 } : { id: k.name.slice(2), k: g.p === "s" ? "os" : "fcm", ...k.metadata });
  return { subs, cursor: g.cursor };
}

// Conta una pagina di iscritti senza mai mostrare i token: solo numeri.
async function statPage(env, want, cursorIn, limit, conf) {
  const g = await rawPage(env, want, cursorIn, limit), st = contaChiavi(g);
  if (conf && g.p === "f") { try { const ok = await confermati(env, g.keys); if (ok) { st.conf = ok.size; st.cdb = 1; } } catch (e) {} }
  return st;
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
const VERSIONE = "2026-11-18v";
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

// ---- conferma degli argomenti (database D1 «LIKE», lo stesso dei like: piano gratuito 100.000 scritture al giorno, KV solo 1.000) ----
const GIRO_MAX = 40;   // telefoni non confermati rimessi in coda dal giro orario (la coda gratuita regge circa 10.000 operazioni al giorno)
function firmaArg(m) {   // firma corta delle scelte: cambia se cambiano gli argomenti voluti
  const t = [...argomentiDi(m)].sort().join(",");
  let h = 5381; for (let i = 0; i < t.length; i++) h = ((h * 33) ^ t.charCodeAt(i)) >>> 0;
  return h.toString(36) + "." + t.length;
}
let ARGOK_PRONTO = false;
async function argokDb(env) {
  if (!env.LIKE) return null;
  if (!ARGOK_PRONTO) {
    await env.LIKE.batch([
      env.LIKE.prepare("CREATE TABLE IF NOT EXISTS argok (id TEXT PRIMARY KEY, s TEXT NOT NULL)"),
      env.LIKE.prepare("CREATE TABLE IF NOT EXISTS argstato (k TEXT PRIMARY KEY, v TEXT)"),
    ]);
    ARGOK_PRONTO = true;
  }
  return env.LIKE;
}
async function segnaConfermato(env, chiave, meta) {
  try {
    const db = await argokDb(env); if (!db) return;
    await db.prepare("INSERT INTO argok (id, s) VALUES (?, ?) ON CONFLICT(id) DO UPDATE SET s = excluded.s WHERE argok.s <> excluded.s")
      .bind(chiave, firmaArg(meta)).run();
  } catch (e) { console.log("argomenti: conferma non scritta", String((e && e.message) || e).slice(0, 80)); }
}
async function togliConferma(env, chiave) {
  try { const db = await argokDb(env); if (db) await db.prepare("DELETE FROM argok WHERE id = ?").bind(chiave).run(); } catch (e) {}
}
// I telefoni confermati di una pagina di chiavi KV (ordinate per nome): UNA sola lettura del database. null = database assente.
async function confermati(env, keys) {
  const db = await argokDb(env); if (!db) return null;
  const ok = new Set(); if (!keys.length) return ok;
  const r = await db.prepare("SELECT id, s FROM argok WHERE id >= ? AND id <= ?").bind(keys[0].name, keys[keys.length - 1].name).all();
  const m = new Map((r.results || []).map(x => [x.id, x.s]));
  for (const k of keys) if (k.metadata && m.get(k.name) === firmaArg(k.metadata)) ok.add(k.name);
  return ok;
}
// Giro orario (dal Cron): i telefoni non ancora confermati tornano in coda, a piccoli lotti; si tolgono le righe di telefoni usciti.
async function giroConferme(env) {
  if (!argomentiAcceso(env) || !env.CODA || !env.FCM_TOPICS_KEY || new Date().getUTCMinutes() >= 5) return;
  const db = await argokDb(env); if (!db) return;
  const ora = Date.now();
  let s = {}; try { const x = await db.prepare("SELECT v FROM argstato WHERE k = 'giro'").first(); s = JSON.parse((x && x.v) || "{}"); } catch (e) {}
  if (ora - (s.ult || 0) < 50 * 60 * 1000) return;
  const r = await env.SUBS.list({ prefix: "f:", cursor: s.cur || undefined, limit: 1000 });
  const keys = r.keys;
  let avanti = true, accodati = 0;
  if (keys.length) {
    const ok = (await confermati(env, keys)) || new Set();
    const scoperti = keys.filter(k => k.metadata && !ok.has(k.name));
    const lotto = scoperti.slice(0, GIRO_MAX);
    if (lotto.length) { await env.CODA.sendBatch(lotto.map(k => ({ body: { k: k.name.slice(2), n: 0, v: 0 } }))); accodati = lotto.length; }
    avanti = scoperti.length <= GIRO_MAX;
    const lo = s.cur ? (s.ultimo || keys[0].name) : "f:", hi = r.list_complete ? "f;" : keys[keys.length - 1].name, ci = new Set(keys.map(k => k.name));
    const righe = await db.prepare("SELECT id FROM argok WHERE id > ? AND id <= ?").bind(lo, hi).all();
    const via = (righe.results || []).map(x => x.id).filter(id => !ci.has(id)).slice(0, 100);
    if (via.length) await db.batch(via.map(id => db.prepare("DELETE FROM argok WHERE id = ?").bind(id)));
  }
  const fine = avanti && r.list_complete;
  const n = { ult: ora, cur: avanti ? (fine ? "" : r.cursor) : (s.cur || ""), ultimo: avanti ? (fine ? "" : (keys.length ? keys[keys.length - 1].name : "")) : (s.ultimo || ""),
              accodati, giri: (s.giri || 0) + (fine ? 1 : 0) };
  await db.prepare("INSERT INTO argstato (k, v) VALUES ('giro', ?) ON CONFLICT(k) DO UPDATE SET v = excluded.v").bind(JSON.stringify(n)).run();
  if (accodati) console.log("argomenti: giro conferme, rimessi in coda", accodati);
}

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
  if (morto(gg)) { console.log("argomenti: dispositivo non piu' valido, tolto dall'archivio", ultimi6(body.k)); await env.SUBS.delete(kv.key); await togliConferma(env, kv.key); return "ok"; }
  if (gg.st !== 200) return { retry: ritardo(body.attempts), perche: "elenco HTTP " + gg.st };
  let attuali = new Set();
  try { const j = JSON.parse(gg.txt); for (const x of j.topic_subscriptions || j.topicSubscriptions || []) { const n = x.topic_name || x.topicName; if (n && NS.test(n)) attuali.add(n); } } catch (e) {}

  const lavori = [...voluti].filter(x => !attuali.has(x)).map(x => ["add", x]).concat([...attuali].filter(x => !voluti.has(x)).map(x => ["del", x]));
  if (!lavori.length) { await segnaConfermato(env, kv.key, rec.metadata); return "ok"; }   // Google dice che e' tutto a posto: confermato
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
  if (mortoQui) { console.log("argomenti: dispositivo non piu' valido, tolto dall'archivio", ultimi6(body.k)); await env.SUBS.delete(kv.key); await togliConferma(env, kv.key); return "ok"; }
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
  if (troppe(req, "like", LIM_LIKE, 600)) return out({ error: "troppe richieste, riprova piu' tardi" }, 429);   // il sito tiene il like e lo rimanda piu' tardi
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

// ======================= VISITATORI (database D1, collegamento LIKE, tabella v) =======================
// Il sito manda UN segnale per telefono al massimo ogni 12 ore, con lo stesso codice casuale dei like (nessun dato personale).
// Una riga per telefono: ora dell'ultima visita e tipo (a = app, i = sito installato, b = browser). Si legge solo dalla pagina admin.
// Freno: oltre VIS_MAX_GIORNO segnali in un giorno si smette di contare fino al giorno dopo, cosi' like e conferme non restano mai senza scritture.
// Niente indice sulla colonna t: ogni indice raddoppierebbe le scritture. Le righe piu' vecchie di 8 giorni si tolgono quando apri le statistiche.
const VIS_MAX_GIORNO = 15000, LIM_VIS = 60;
let VIS_PRONTO = false;
async function visDb(env) {
  if (!env.LIKE) return null;
  if (!VIS_PRONTO) {
    await env.LIKE.batch([
      env.LIKE.prepare("CREATE TABLE IF NOT EXISTS v (dev TEXT PRIMARY KEY, t INTEGER NOT NULL, k TEXT NOT NULL)"),
      env.LIKE.prepare("CREATE TABLE IF NOT EXISTS g (d TEXT PRIMARY KEY, n INTEGER NOT NULL)"),
    ]);
    VIS_PRONTO = true;
  }
  return env.LIKE;
}
async function visiteRoute(req, env, url, out, admin) {
  const db = await visDb(env);
  if (!db) return out({ error: "visite non attive (manca il database LIKE)" }, 503);
  const ora = Math.floor(Date.now() / 1000), gk = "v:" + new Date().toISOString().slice(0, 10);
  if (req.method === "GET" && url.pathname === "/admin/visite") {   // SOLO Andrea (ADMIN_TOKEN)
    if (!admin()) return out({ error: "non autorizzato" }, 401);
    await db.prepare("DELETE FROM v WHERE t < ?").bind(ora - 8 * 86400).run();
    const r = await db.prepare("SELECT k, COUNT(*) AS c FROM v WHERE t >= ? GROUP BY k").bind(ora - 86400).all();
    const s7 = await db.prepare("SELECT COUNT(*) AS c FROM v WHERE t >= ?").bind(ora - 7 * 86400).first();
    const g = await db.prepare("SELECT n FROM g WHERE d = ?").bind(gk).first();
    const k = { a: 0, i: 0, b: 0 }; let n = 0;
    for (const x of r.results || []) { if (x.k in k) k[x.k] = x.c; n += x.c; }
    return out({ ok: true, n24: n, k, n7: (s7 && s7.c) || 0, segnaliOggi: (g && g.n) || 0, max: VIS_MAX_GIORNO });
  }
  if (req.method !== "POST" || url.pathname !== "/visita") return out({ error: "richiesta non valida" }, 400);
  if (troppe(req, "visita", LIM_VIS, 600)) return out({ ok: true, pausa: true });
  const txt = await req.text();
  if (txt.length > 300) return out({ error: "troppo grande" }, 413);
  let b; try { b = JSON.parse(txt); } catch (e) { return out({ error: "json non valido" }, 400); }
  const dev = String((b && b.dev) || ""), k = String((b && b.k) || "b");
  if (!/^[a-z0-9]{12,40}$/.test(dev) || !["a", "i", "b"].includes(k)) return out({ error: "richiesta non valida" }, 400);
  const g = await db.prepare("SELECT n FROM g WHERE d = ?").bind(gk).first();
  if (g && g.n >= VIS_MAX_GIORNO) return out({ ok: true, pausa: true });
  await db.batch([
    db.prepare("INSERT INTO v (dev, t, k) VALUES (?, ?, ?) ON CONFLICT(dev) DO UPDATE SET t = excluded.t, k = excluded.k").bind(dev, ora, k),
    db.prepare("INSERT INTO g (d, n) VALUES (?, 1) ON CONFLICT(d) DO UPDATE SET n = n + 1").bind(gk),
  ]);
  return out({ ok: true });
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

// ======================= AVVISI AUTOMATICI DI FRANCESCO (2026-11-15b) =======================
// Twitch: avviso ufficiale «stream.online» (EventSub), Twitch chiama il Worker nell'istante in cui va in live.
// YouTube: avviso ufficiale dei video nuovi (WebSub), poi UNA domanda all'API per capire se e' una live, una live programmata o un video.
//   Live programmate: ricontrollate ogni 5 minuti SOLO finche' non partono. Shorts esclusi.
// Si accende da solo quando ci sono le chiavi su Cloudflare (senza, non fa niente):
//   TWITCH_CLIENT_ID (testo) + TWITCH_CLIENT_SECRET (segreto)      -> live Twitch
//   YT_API_KEY (segreto) + YT_CANALE (testo, ID del canale UC...)   -> live e video YouTube
//   + un «Cron Trigger» del Worker ogni 5 minuti (*/5 * * * *): rinnova da solo le iscrizioni a Twitch e YouTube.
// Niente doppioni: se nelle ultime 2 ore e' gia' partito un avviso di live (anche dal pulsante di Francesco) non ne parte un altro.
// Si spegne con PARDINI_ATTIVO = off, come il resto. Stato visibile nella pagina admin (scheda Statistiche).
const AUTO = { twitch: "francescopardinivgc", nome: "Francesco Pardini", finestraLive: 2 * 3600, maxVisti: 60 };
const AUTO_KEY = "auto:stato";
const AUTO_URL = "https://vgc-subs.andrykvideo.workers.dev";

function autoBase(env) { return String(env.WORKER_URL || AUTO_URL).replace(/\/+$/, ""); }
function twOn(env) { return !!(env.TWITCH_CLIENT_ID && env.TWITCH_CLIENT_SECRET); }
function ytOn(env) { return !!(env.YT_API_KEY && /^UC[\w-]{22}$/.test(String(env.YT_CANALE || "").trim())); }
async function segreto(env, base) { return (await hashTesto("rakings-auto:" + base)).slice(0, 48); }   // ricavato dalle chiavi: nessun segreto in piu' da creare
async function hmacHex(algo, chiave, testo) {
  const k = await crypto.subtle.importKey("raw", new TextEncoder().encode(chiave), { name: "HMAC", hash: algo }, false, ["sign"]);
  const s = await crypto.subtle.sign("HMAC", k, new TextEncoder().encode(testo));
  return Array.from(new Uint8Array(s), b => b.toString(16).padStart(2, "0")).join("");
}
function uguali(a, b) { a = String(a || ""); b = String(b || ""); if (a.length !== b.length) return false; let x = 0; for (let i = 0; i < a.length; i++) x |= a.charCodeAt(i) ^ b.charCodeAt(i); return x === 0; }
async function autoStato(env) { return (await env.SUBS.get(AUTO_KEY, "json")) || { visti: [], attesa: [], log: [] }; }
async function autoSalva(env, s) { s.log = (s.log || []).slice(-20); s.visti = (s.visti || []).slice(-AUTO.maxVisti); await env.SUBS.put(AUTO_KEY, JSON.stringify(s)); }
function autoLog(s, t) { (s.log = s.log || []).push({ t: Math.floor(Date.now() / 1000), m: String(t).slice(0, 160) }); }

// manda l'avviso con lo STESSO flusso del pulsante di Francesco (avviso-partner.yml, invio diretto)
async function autoAvviso(env, s, tipo, titolo, testo, link) {
  if ((env.PARDINI_ATTIVO || "on") === "off" || !env.GH_AVVISI) { autoLog(s, "avviso non mandato (sospeso o manca GH_AVVISI): " + titolo); return false; }
  const ora = Math.floor(Date.now() / 1000);
  const st = await statoPartner(env, "pardini");
  if (tipo === "live" && st.live.some(t => ora - t < AUTO.finestraLive)) { autoLog(s, "live gia' avvisata nelle ultime 2 ore: niente doppione"); return false; }
  titolo = pulisci(titolo, 60); testo = pulisci(testo, 180); link = linkOk(link) || "";
  const r = await fetch(PARTNER_FLUSSO, {
    method: "POST",
    headers: { "Authorization": "Bearer " + env.GH_AVVISI, "Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28",
               "User-Agent": "vgc-subs-auto", "Content-Type": "application/json" },
    body: JSON.stringify({ ref: "main", inputs: { partner: "pardini", id: String(ora), titolo, testo, link, bacheca: "", articolo: "", img: "" } }),
  });
  if (r.status !== 204) { autoLog(s, "GitHub ha risposto " + r.status + ": avviso non partito (" + titolo + ")"); return false; }
  if (tipo === "live") st.live = st.live.filter(t => ora - t < 7 * 86400).concat([ora]);   // conta anche per il pulsante: niente doppioni
  st.log = st.log.concat([{ t: ora, tipo: tipo === "live" ? "live" : "testo", auto: true, titolo, testo, link, img: false, bacheca: false }]).slice(-30);
  await env.SUBS.put("partner:pardini", JSON.stringify(st));
  autoLog(s, "inviato: " + titolo + " · " + testo);
  return true;
}

// ---------------- Twitch ----------------
async function twToken(env, s) {
  const ora = Math.floor(Date.now() / 1000);
  if (s.twTok && s.twTokFino > ora + 3600) return s.twTok;
  const r = await fetch("https://id.twitch.tv/oauth2/token", { method: "POST", headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({ client_id: env.TWITCH_CLIENT_ID, client_secret: env.TWITCH_CLIENT_SECRET, grant_type: "client_credentials" }) });
  if (!r.ok) throw new Error("Twitch: chiavi non valide (" + r.status + ")");
  const j = await r.json();
  s.twTok = j.access_token; s.twTokFino = ora + Number(j.expires_in || 0);
  return s.twTok;
}
async function twApi(env, s, metodo, percorso, corpo) {
  const r = await fetch("https://api.twitch.tv/helix" + percorso, { method: metodo, body: corpo ? JSON.stringify(corpo) : undefined,
    headers: { "Client-Id": env.TWITCH_CLIENT_ID, "Authorization": "Bearer " + await twToken(env, s), "Content-Type": "application/json" } });
  if (r.status === 401) { s.twTok = ""; }
  return r;
}
async function twAssicura(env, s) {   // l'iscrizione «stream.online» c'e' ed e' attiva? Se no la crea
  if (!s.twId) {
    const r = await twApi(env, s, "GET", "/users?login=" + AUTO.twitch);
    const u = r.ok ? ((await r.json()).data || [])[0] : null;
    if (!u) throw new Error("Twitch: canale " + AUTO.twitch + " non trovato (" + r.status + ")");
    s.twId = u.id;
  }
  const cb = autoBase(env) + "/auto/twitch";
  const r = await twApi(env, s, "GET", "/eventsub/subscriptions?type=stream.online");
  if (!r.ok) throw new Error("Twitch: elenco iscrizioni non letto (" + r.status + ")");
  const l = ((await r.json()).data || []).filter(x => x.condition && x.condition.broadcaster_user_id === s.twId && x.transport && x.transport.callback === cb);
  if (l.some(x => x.status === "enabled" || x.status === "webhook_callback_verification_pending")) { s.twOk = true; return; }
  for (const x of l) await twApi(env, s, "DELETE", "/eventsub/subscriptions?id=" + x.id);   // iscrizioni guaste: si rifanno
  const c = await twApi(env, s, "POST", "/eventsub/subscriptions", { type: "stream.online", version: "1", condition: { broadcaster_user_id: s.twId },
    transport: { method: "webhook", callback: cb, secret: await segreto(env, env.TWITCH_CLIENT_SECRET) } });
  if (c.status !== 202 && c.status !== 409) throw new Error("Twitch: iscrizione non creata (" + c.status + ")");
  s.twOk = true; autoLog(s, "Twitch: iscrizione alle live creata");
}
async function twEvento(req, env, out) {
  if (!twOn(env)) return out({ error: "spento" }, 404);
  const corpo = await req.text();
  const id = req.headers.get("Twitch-Eventsub-Message-Id") || "", ts = req.headers.get("Twitch-Eventsub-Message-Timestamp") || "";
  const firma = "sha256=" + await hmacHex("SHA-256", await segreto(env, env.TWITCH_CLIENT_SECRET), id + ts + corpo);
  if (!uguali(firma, req.headers.get("Twitch-Eventsub-Message-Signature"))) return new Response("firma non valida", { status: 403 });
  if (Math.abs(Date.now() - Date.parse(ts)) > 10 * 60 * 1000) return new Response("troppo vecchio", { status: 403 });
  let b; try { b = JSON.parse(corpo); } catch (e) { return new Response("json", { status: 400 }); }
  const tipo = req.headers.get("Twitch-Eventsub-Message-Type");
  if (tipo === "webhook_callback_verification") return new Response(String(b.challenge || ""), { headers: { "Content-Type": "text/plain" } });
  const s = await autoStato(env);
  if (tipo === "revocation") { s.twOk = false; autoLog(s, "Twitch ha revocato l'iscrizione (" + ((b.subscription || {}).status || "?") + "): si rifa' al prossimo giro"); await autoSalva(env, s); return new Response(null, { status: 204 }); }
  if (tipo !== "notification" || !b.event || (b.subscription || {}).type !== "stream.online") return new Response(null, { status: 204 });
  if ((s.visti || []).includes("tw:" + id)) return new Response(null, { status: 204 });   // Twitch puo' rimandare lo stesso avviso
  s.visti = (s.visti || []).concat(["tw:" + id]);
  let titolo = "";
  try { const r = await twApi(env, s, "GET", "/streams?user_id=" + b.event.broadcaster_user_id); if (r.ok) titolo = (((await r.json()).data || [])[0] || {}).title || ""; } catch (e) {}
  await autoAvviso(env, s, "live", AUTO.nome + " è in live su Twitch", titolo || "Tocca per guardare la diretta.", "https://www.twitch.tv/" + AUTO.twitch);
  await autoSalva(env, s);
  return new Response(null, { status: 204 });
}

// ---------------- YouTube ----------------
function ytTopic(env) { return "https://www.youtube.com/xml/feeds/videos.xml?channel_id=" + String(env.YT_CANALE).trim(); }
async function ytRinnova(env, s) {
  const r = await fetch("https://pubsubhubbub.appspot.com/subscribe", { method: "POST", headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({ "hub.callback": autoBase(env) + "/auto/youtube", "hub.topic": ytTopic(env), "hub.mode": "subscribe", "hub.verify": "async",
                                "hub.lease_seconds": "864000", "hub.secret": await segreto(env, env.YT_API_KEY) }) });
  if (r.status !== 202 && r.status !== 204) throw new Error("YouTube: rinnovo non accettato (" + r.status + ")");
  s.ytRinnovo = Math.floor(Date.now() / 1000);
}
async function ytProva(env, s) {   // controllo giornaliero: chiave e ID del canale funzionano? (1 unita' su 10.000)
  const r = await fetch("https://www.googleapis.com/youtube/v3/channels?part=snippet&id=" + encodeURIComponent(String(env.YT_CANALE).trim()) + "&key=" + encodeURIComponent(env.YT_API_KEY));
  if (r.status === 400 || r.status === 403) throw new Error("YouTube: chiave non valida o API non abilitata (" + r.status + ")");
  if (!r.ok) throw new Error("YouTube: controllo non riuscito (" + r.status + ")");
  const c = ((await r.json()).items || [])[0];
  if (!c) throw new Error("YouTube: canale non trovato, controlla YT_CANALE");
  s.ytNome = String((c.snippet || {}).title || "").slice(0, 80); s.ytChiave = Math.floor(Date.now() / 1000);
}
async function ytVideo(env, id) {   // UNA domanda all'API (1 unita' su 10.000 gratuite al giorno)
  const r = await fetch("https://www.googleapis.com/youtube/v3/videos?part=snippet,liveStreamingDetails,contentDetails&id=" + encodeURIComponent(id) + "&key=" + encodeURIComponent(env.YT_API_KEY));
  if (!r.ok) throw new Error("YouTube: video non letto (" + r.status + ")");
  return ((await r.json()).items || [])[0] || null;
}
function secondi(d) { const m = /^PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?$/.exec(d || ""); return m ? (+m[1] || 0) * 3600 + (+m[2] || 0) * 60 + (+m[3] || 0) : 0; }
async function eShort(id, durata) {
  if (durata > 180) return false;   // gli Shorts durano al massimo 3 minuti
  try { const r = await fetch("https://www.youtube.com/shorts/" + id, { method: "HEAD", redirect: "manual" }); return r.status === 200; }
  catch (e) { return true; }        // nel dubbio un video brevissimo non si avvisa
}
async function ytGestisci(env, s, v) {   // ritorna true se il video e' "chiuso" (avvisato o da ignorare)
  const sn = v.snippet || {}, lb = sn.liveBroadcastContent, link = "https://www.youtube.com/watch?v=" + v.id;
  if (lb === "live") { await autoAvviso(env, s, "live", AUTO.nome + " è in live su YouTube", sn.title || "Tocca per guardare la diretta.", link); return true; }
  if (lb === "upcoming") return false;
  if ((v.liveStreamingDetails || {}).actualEndTime) return true;   // replica di una live gia' finita: niente avviso
  if (Date.now() - Date.parse(sn.publishedAt || 0) > 2 * 86400 * 1000) return true;   // video vecchio modificato: niente avviso
  if (await eShort(v.id, secondi((v.contentDetails || {}).duration))) { autoLog(s, "Short ignorato: " + (sn.title || v.id)); return true; }
  await autoAvviso(env, s, "video", "Nuovo video di " + AUTO.nome, sn.title || "Tocca per guardarlo.", link);
  return true;
}
async function ytEvento(req, env, out, url) {
  if (!ytOn(env)) return out({ error: "spento" }, 404);
  if (req.method === "GET") {   // verifica dell'iscrizione da parte di YouTube
    const ok = url.searchParams.get("hub.topic") === ytTopic(env);
    return ok ? new Response(url.searchParams.get("hub.challenge") || "", { headers: { "Content-Type": "text/plain" } }) : new Response("no", { status: 404 });
  }
  const corpo = await req.text();
  const firma = "sha1=" + await hmacHex("SHA-1", await segreto(env, env.YT_API_KEY), corpo);
  if (!uguali(firma, req.headers.get("X-Hub-Signature"))) return new Response(null, { status: 204 });   // non e' YouTube: ignorato in silenzio
  const ids = [...corpo.matchAll(/<yt:videoId>([\w-]{11})<\/yt:videoId>/g)].map(m => m[1]).slice(0, 3);
  if (!ids.length) return new Response(null, { status: 204 });
  const s = await autoStato(env);
  for (const id of ids) {
    if ((s.visti || []).includes("yt:" + id) || (s.attesa || []).some(a => a.id === id)) continue;
    try {
      const v = await ytVideo(env, id);
      if (!v) continue;
      if (await ytGestisci(env, s, v)) s.visti = (s.visti || []).concat(["yt:" + id]);
      else { s.attesa = (s.attesa || []).concat([{ id, da: Math.floor(Date.now() / 1000), inizio: Date.parse((v.liveStreamingDetails || {}).scheduledStartTime || 0) / 1000 || 0 }]); autoLog(s, "live programmata in attesa: " + ((v.snippet || {}).title || id)); }
    } catch (e) { autoLog(s, String(e.message || e)); }
  }
  await autoSalva(env, s);
  return new Response(null, { status: 204 });
}

// ---------------- giro ogni 5 minuti (Cron Trigger) ----------------
async function autoGiro(env) {
  if (!twOn(env) && !ytOn(env)) return;
  const s = await autoStato(env), prima = JSON.stringify(s), ora = Math.floor(Date.now() / 1000);
  if (ytOn(env) && (s.attesa || []).length) {   // live programmate: si controllano solo da 15 minuti prima dell'orario in poi
    const resta = [];
    for (const a of s.attesa) {
      if (ora - a.da > 3 * 86400 || (a.inizio && ora - a.inizio > 12 * 3600)) { autoLog(s, "live programmata scaduta: " + a.id); continue; }
      if (a.inizio && a.inizio - ora > 15 * 60) { resta.push(a); continue; }
      try { const v = await ytVideo(env, a.id); if (!v || await ytGestisci(env, s, v)) { s.visti = (s.visti || []).concat(["yt:" + a.id]); continue; } } catch (e) { autoLog(s, String(e.message || e)); }
      resta.push(a);
    }
    s.attesa = resta;
  }
  if (ora - (s.giorno || 0) > 20 * 3600 || (twOn(env) && !s.twOk)) {   // una volta al giorno: le iscrizioni ci sono ancora?
    s.giorno = ora; s.errore = "";
    if (twOn(env)) { try { await twAssicura(env, s); } catch (e) { s.twOk = false; s.errore = String(e.message || e); autoLog(s, s.errore); } }
    if (ytOn(env)) { try { await ytProva(env, s); } catch (e) { s.ytChiave = 0; s.errore = String(e.message || e); autoLog(s, s.errore); } }
    if (ytOn(env) && ora - (s.ytRinnovo || 0) > 3 * 86400) { try { await ytRinnova(env, s); autoLog(s, "YouTube: iscrizione rinnovata"); } catch (e) { s.errore = String(e.message || e); autoLog(s, s.errore); } }
  }
  if (JSON.stringify(s) !== prima) await autoSalva(env, s);   // si scrive solo se e' cambiato qualcosa
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
    if (url.pathname === "/visita" || url.pathname === "/admin/visite") {
      try { return await visiteRoute(req, env, url, out, admin); } catch (e) { console.log("visite:", String(e && e.message || e).slice(0, 120)); return out({ error: "visite non disponibili" }, 503); }
    }
    if (url.pathname === "/auto/twitch" && req.method === "POST") return twEvento(req, env, out);
    if (url.pathname === "/auto/youtube" && (req.method === "GET" || req.method === "POST")) return ytEvento(req, env, out, url);
    if (url.pathname === "/admin/auto" && req.method === "GET") {   // SOLO Andrea: stato degli avvisi automatici (scheda Statistiche)
      if (!admin()) return out({ error: "non autorizzato" }, 401);
      const s = await autoStato(env);
      return out({ ok: true, twitch: twOn(env), youtube: ytOn(env), twOk: !!s.twOk, ytRinnovo: s.ytRinnovo || 0, ytChiave: s.ytChiave || 0, ytNome: s.ytNome || "", giro: s.giorno || 0, attesa: (s.attesa || []).length, errore: s.errore || "", log: (s.log || []).slice(-8).reverse() });
    }
    if (url.pathname === "/admin/richieste" || url.pathname === "/admin/richieste/etichetta") return richiesteRoute(req, env, url, out, admin);
    if (req.method === "POST" && url.pathname === "/admin/social") {   // SOLO Andrea (ADMIN_TOKEN): approva/rifiuta un post per Instagram o X
      if (!admin()) return out({ error: "non autorizzato" }, 401);
      let b; try { b = JSON.parse(await req.text()); } catch (e) { return out({ error: "json non valido" }, 400); }
      const id = String((b && b.id) || ""), rete = String((b && b.rete) || ""), az = String((b && b.azione) || "");
      const testo = typeof (b && b.testo) === "string" ? b.testo.slice(0, 2200) : "";
      if (!/^[a-z]{2,8}-\d{1,10}$/.test(id) || !["ig", "x", "yt"].includes(rete) || !["approva", "rifiuta", "fatto"].includes(az)
          || (rete !== "x" && az === "fatto") || (rete === "x" && az === "approva")) return out({ error: "richiesta non valida" }, 400);
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
    if (req.method === "POST" && url.pathname === "/admin/annuncio") {   // SOLO Andrea (ADMIN_TOKEN): annuncio in bacheca + notifica a tutti
      if (!admin()) return out({ error: "non autorizzato" }, 401);
      if (!env.GH_AVVISI) return out({ error: "manca il segreto GH_AVVISI" }, 503);
      const txt = await req.text();
      if (txt.length > 1100000) return out({ error: "Immagine troppo grande." }, 413);
      let b; try { b = JSON.parse(txt); } catch (e) { return out({ error: "json non valido" }, 400); }
      const titolo = pulisci(b.titolo, 60), testo = pulisci(b.testo, 180), link = linkOk(pulisci(b.link, 300));
      const articolo = String(b.articolo || "").replace(/\r/g, "").replace(/[\u0000-\u0009\u000b-\u001f\u007f]+/g, " ").replace(/\n{3,}/g, "\n\n").trim().slice(0, 2000);
      if (titolo.length < 3) return out({ error: "Il titolo deve avere almeno 3 caratteri." }, 400);
      if (testo.length < 3) return out({ error: "Il testo deve avere almeno 3 caratteri." }, 400);
      if (link === null) return out({ error: "Link non ammesso: solo Twitch, YouTube o il sito rAKings (https)." }, 400);
      let img = null;
      if (b.img) {
        const s64 = String(b.img).replace(/^data:image\/jpeg;base64,/, "");
        if (s64 === String(b.img) || !/^\/9j\//.test(s64) || s64.length < 200 || s64.length > 1000000 || /[^A-Za-z0-9+/=]/.test(s64.slice(0, 4000)))
          return out({ error: "Immagine non valida: usa una foto JPG o PNG." }, 400);
        img = s64;
      }
      const ora = Math.floor(Date.now() / 1000), ult = Number(await env.SUBS.get("admin:annT")) || 0;
      if (ora - ult < 60) return out({ error: "Hai appena mandato un annuncio: aspetta un minuto." }, 429);
      await env.SUBS.put("admin:annT", String(ora), { expirationTtl: 3600 });
      if (img) await env.SUBS.put("partner:img:" + ora, img, { expirationTtl: 2 * 86400 });
      const r = await fetch(PARTNER_FLUSSO, {
        method: "POST",
        headers: { "Authorization": "Bearer " + env.GH_AVVISI, "Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28",
                   "User-Agent": "vgc-subs-admin", "Content-Type": "application/json" },
        body: JSON.stringify({ ref: "main", inputs: { partner: "rakings", id: String(ora), titolo, testo, link: link || "",
                                                      bacheca: "1", articolo, img: img ? "1" : "" } }),
      });
      if (r.status !== 204) { await env.SUBS.delete("admin:annT"); return out({ error: "GitHub ha risposto " + r.status + ": annuncio non partito, riprova." }, 502); }
      await env.SUBS.put("partner:ann:" + ora, JSON.stringify({ id: ora, t: titolo, d: articolo || testo, pub: new Date(ora * 1000).toISOString().slice(0, 19) + "Z",
                                                               partner: "rakings", link: link || "", img: !!img }), { expirationTtl: 2 * 86400 });
      return out({ ok: true, id: ora });
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
          const r = await listPage(env, want, cur, limit, url.searchParams.get("conf") === "1");
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
        return out(await statPage(env, want, url.searchParams.get("cursor"), limit, url.searchParams.get("conf") === "1"));
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
      if (!same(cur.metadata)) {
        if (troppe(req, "iscr", LIM_ISCRIZIONI, 600)) return out({ error: "troppe richieste, riprova tra qualche minuto" }, 429);
        if (!cur.metadata && k.kind === "fcm" && argomentiAcceso(env) && env.FCM_TOPICS_KEY) {
          // iscrizione NUOVA: Google conosce davvero questo telefono? Se dice di no, non si scrive niente (niente iscritti inventati).
          // Se Google non risponde, si scrive lo stesso: un utente vero non deve mai restare fuori per colpa del controllo.
          try { const g = await accessGoogle(env); const r = await gcall(g, "GET", "", b.id); if (r.st === 400 || morto(r)) return out({ error: "dispositivo non valido" }, 400); } catch (e) {}
        }
        await env.SUBS.put(k.key, "1", { metadata: { c, h, f, l, t: Date.now() }, expirationTtl: TTL_S }); scritto = true;
      }
      if (scritto && k.kind === "fcm") await accoda(env, b.id, 0);   // con ARGOMENTI spento non fa niente
      return out({ ok: true, tipo: k.kind });
    }

    return out({ ok: true, servizio: "archivio iscritti rAKings VGC ", v: VERSIONE, argomenti: argomentiAcceso(env) ? (env.CODA && env.FCM_TOPICS_KEY ? "on" : "on-ma-incompleto") : "off" });
  },

  // ogni 5 minuti (Cron Trigger «*/5 * * * *» nelle impostazioni del Worker): avvisi automatici di Francesco
  async scheduled(event, env, ctx) {
    ctx.waitUntil(autoGiro(env).catch(e => console.log("auto:", String((e && e.message) || e).slice(0, 160))));
    ctx.waitUntil(giroConferme(env).catch(e => console.log("argomenti: giro conferme", String((e && e.message) || e).slice(0, 160))));
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
