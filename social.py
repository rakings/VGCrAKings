#!/usr/bin/env python3
"""Post per Instagram e X di rAKings VGC. Gira nella repo del sito (VGCrAKings), da solo.

  python3 social.py crea    -> per ogni torneo locale APPENA PUBBLICATO sul sito (locali.json) prepara una richiesta:
                               immagine della Top 8 + testo per Instagram + testo per X, da approvare nella tua pagina admin.
                               Controlla anche, una volta al giorno, che la chiave di Instagram funzioni
                               e legge le statistiche del profilo e degli ultimi post (social/statistiche.json).
  python3 social.py azione  -> esegue quello che hai scelto nella pagina admin (variabili ID, RETE, AZIONE, TESTO):
                               Instagram «approva» = pubblica davvero; X «fatto» = segna come pubblicato da te;
                               YouTube «approva» = crea lo Short dalle stesse immagini e lo carica (youtube.py); «rifiuta».

Regola: prima il sito, poi i social. Una richiesta nasce SOLO da un locale gia' approvato e pubblicato sul sito;
se il locale viene tolto dal sito, le sue richieste non ancora pubblicate si annullano da sole.
Tutto si salva in social/richieste.json (le immagini in social/img/). Solo libreria standard + Pillow per le immagini."""
import hashlib, json, os, re, sys, time, urllib.error, urllib.parse, urllib.request
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

SITO = "https://rakings.github.io/VGCrAKings/"
FILE = "social/richieste.json"
DIR_IMG = "social/img"
LOCALI = "locali.json"
EVENTI = "events.json"
ROMA = ZoneInfo("Europe/Rome")
MONEY_MAX = 19           # copertina + 9 slide da 2 = 10 immagini, il massimo che l'API di Instagram accetta in un carosello
MONEY_GIORNO, MONEY_ORA = 0, 8   # lunedi', dalle 8 (ora italiana)
CAMBIO = {"€": 1.0, "eur": 1.0, "$": 0.9, "usd": 0.9, "£": 1.15, "gbp": 1.15}   # cambio fisso, solo per mettere in ordine i premi
GIORNI = ["lun", "mar", "mer", "gio", "ven", "sab", "dom"]
MESI = ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio", "agosto", "settembre", "ottobre", "novembre", "dicembre"]
GRANDI = ("Regionale", "Special Event", "Internazionale")
TENERE = 30              # richieste gia' chiuse da tenere nell'elenco (le piu' recenti); quelle aperte restano sempre
CONTROLLO_ORE = 20       # ogni quanto si controlla la chiave di Instagram
MAX_IG = 2200            # limite di Instagram per la didascalia
APERTE = ("da approvare", "errore")


def log(*a):
    print(*a, flush=True)


def ora():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load(p, d):
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return d


def save(p, d):
    os.makedirs(os.path.dirname(p) or ".", exist_ok=True)
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=1)
        f.write("\n")
    os.replace(tmp, p)


def eh(u):
    """Stesso codice del sito (eh() in index.html): serve per il link diretto alla scheda del locale."""
    h, b = 5381, u.encode("utf-16-le")
    for i in range(0, len(b), 2):
        h = (h * 33 + (b[i] | (b[i + 1] << 8))) & 0xFFFFFFFF
    s, cifre = "", "0123456789abcdefghijklmnopqrstuvwxyz"
    while True:
        h, r = divmod(h, 36)
        s = cifre[r] + s
        if not h:
            return s


def peso_x(t, link=""):
    """Lunghezza come la conta X: il link vale sempre 23, emoji e caratteri asiatici 2."""
    if link:
        t = t.replace(link, "x" * 23)
    return sum(1 if ord(c) < 0x1100 else 2 for c in t)


# ---------------------------------------------------------------- testi
MEDAGLIE = ["🥇", "🥈", "🥉"]


def tag(s):
    return "".join(c for c in s.title() if c.isalnum())


# Hashtag di Instagram (2026-11-21): MASSIMO 5 (limite di Instagram), #PokemonChampions sempre, niente #VGCItalia.
# Per ogni tipo di post ci sono piu' gruppi che si alternano (sempre lo stesso per lo stesso post), cosi' non incolliamo
# sempre lo stesso blocco. Su X bastano 2 hashtag (#PokemonChampions + uno).
GRUPPI_IG = {
    "locali": (("#PokemonVGC", "#VGC", "#PokemonTournament"), ("#PokemonVGC", "#CompetitivePokemon", "#VGC"), ("#VGC", "#PokemonVGC", "#Pokemon")),
    "money": (("#PokemonVGC", "#MoneyTournament", "#VGC", "#CompetitivePokemon"), ("#PokemonVGC", "#VGC", "#MoneyTournament", "#PokemonTournament"),
              ("#VGC", "#PokemonVGC", "#MoneyTournament", "#Pokemon")),
    "regionale": (("#PokemonVGC", "#VGC", "#Regionals", "#CompetitivePokemon"), ("#PokemonVGC", "#Regionals", "#VGC", "#PokemonTournament"),
                  ("#VGC", "#PokemonVGC", "#Regionals", "#PlayPokemon")),
    "vr": (("#PokemonVGC", "#VictoryRoad", "#VGC", "#CompetitivePokemon"), ("#PokemonVGC", "#VictoryRoad", "#VGC", "#PokemonTournament"),
           ("#VictoryRoad", "#PokemonVGC", "#VGC", "#Pokemon")),
}


def hashtag_ig(tipo, chiave, extra=None):
    g = GRUPPI_IG[tipo][int(hashlib.sha1(str(chiave).encode("utf-8")).hexdigest()[:6], 16) % len(GRUPPI_IG[tipo])]
    l = ["#PokemonChampions"] + ([extra] if extra else []) + [h for h in g if h != extra]
    return " ".join(l[:5])


TIPI_EN = {"sfida di lega": "League Challenge", "coppa di lega": "League Cup"}


def tipo_en(t):
    return TIPI_EN.get(str(t or "").strip().lower(), t or "")


def data_en(t):
    """«8 novembre 2026» -> «Nov 8, 2026» (se non la riconosce la lascia com'e')."""
    m = re.match(r"\s*(\d{1,2})\s+([a-zA-Z]+)\s+(\d{4})\s*$", str(t or ""))
    if m and m.group(2).lower() in MESI:
        return "%s %d, %s" % (MESI_EN[MESI.index(m.group(2).lower())], int(m.group(1)), m.group(3))
    return t or ""


def testi_locale(v, link):
    tipo, neg, citta, data = tipo_en(v.get("t", "")), v.get("s", ""), v.get("c", ""), data_en(v.get("d", ""))
    nomi = [str(x or "").strip() for x in (v.get("top") or [])][:8]
    nomi = [x for x in nomi if x]
    righe = [(MEDAGLIE[i] if i < 3 else "%d." % (i + 1)) + " " + n for i, n in enumerate(nomi)]
    n = v.get("n")
    gioc = ("\n👥 %s players" % n) if isinstance(n, int) or (isinstance(n, str) and n.isdigit()) else ""
    intro = [
        "🏆 Pokémon VGC Top 8 · %s at %s (%s), %s" % (tipo, neg, citta, data),
        "🏆 Pokémon VGC %s at %s in %s: here's the Top 8 of %s." % (tipo, neg, citta, data),
        "🏆 Top 8 · Pokémon VGC %s · %s, %s · %s" % (tipo, neg, citta, data),
    ][int(v.get("id") or 0) % 3]     # il testo cambia un po' da un post all'altro (niente post tutti identici)
    ig = intro + gioc + "\n\n" + "\n".join(righe)
    if nomi:
        ig += "\n\nCongrats to %s! 👏" % nomi[0]
    ig += "\n\nFull teams and results on rAKings VGC: link in bio 📲"
    ig += "\n\n" + hashtag_ig("locali", v.get("id"), ("#VGC" + tag(citta)) if tag(citta) else None)
    ig = ig[:MAX_IG]

    def x_con(k):
        corpo = "\n".join(righe[:k])
        return "🏆 Top 8 %s · %s (%s)\n%s\nTeams on rAKings VGC 👇\n%s\n#PokemonChampions #VGC" % (tipo, neg, citta, corpo, link)
    k = len(righe)
    while k > 1 and peso_x(x_con(k), link) > 275:
        k -= 1
    return ig, x_con(k)


# ---------------------------------------------------------------- crea
def firma(v):
    return hashlib.sha1(json.dumps([v.get(k) for k in ("t", "s", "c", "d", "top", "n")], ensure_ascii=False).encode("utf-8")).hexdigest()[:8]


def prepara_locale(v, vecchia=None):
    import social_img   # Pillow serve solo qui
    f = firma(v)
    rid = "loc-%d" % v["id"]
    img = "%s/%s-%s.jpg" % (DIR_IMG, rid, f)
    os.makedirs(DIR_IMG, exist_ok=True)
    social_img.top8(tipo_en(v.get("t", "")), v.get("s", ""), v.get("c", ""), data_en(v.get("d", "")), list(v.get("top") or []), img)
    link = SITO + "#locali-" + eh("|".join(str(v.get(k, "")) for k in ("t", "s", "c", "d")))
    ig, x = testi_locale(v, link)
    r = vecchia or {"id": rid, "tipo": "locali", "rif": v["id"], "creata": ora()}
    r.update({"v": LINGUA_V, "firma": f, "titolo": "Top 8 · %s · %s" % (v.get("t", ""), v.get("s", "")),
              "sotto": "%s · %s" % (v.get("c", ""), v.get("d", "")), "img": img, "link": link})
    for k, t in (("ig", ig), ("x", x)):
        if not vecchia or r[k]["stato"] in APERTE:
            r[k] = {"stato": "da approvare", "testo": t}
    return r


def controllo_chiave(d):
    """Una volta al giorno: la chiave di Instagram funziona? Il risultato si vede nella scheda Instagram dell'admin.
    Ritorna 1 (flusso in rosso = GitHub ti manda una mail) solo quando una chiave che funzionava smette di funzionare."""
    st = d.setdefault("ig_stato", {})
    if not os.environ.get("IG_TOKEN") or not os.environ.get("IG_USER_ID"):
        if st.get("msg") != "da collegare":
            d["ig_stato"] = {"ok": False, "msg": "da collegare", "quando": ora()}
        return 0
    try:
        ultimo = datetime.strptime(st.get("quando", ""), "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        if st.get("msg") != "da collegare" and (datetime.now(timezone.utc) - ultimo).total_seconds() < CONTROLLO_ORE * 3600:
            return 0
    except ValueError:
        pass
    prima = st.get("ok")
    try:
        u = graph("GET", os.environ["IG_USER_ID"], {"fields": "username"})
        d["ig_stato"] = {"ok": True, "msg": "collegato", "account": u.get("username", ""), "quando": ora()}
        log("Chiave di Instagram: funziona (@%s)." % u.get("username", "?"))
        return 0
    except RuntimeError as ex:
        d["ig_stato"] = {"ok": False, "msg": "la chiave non funziona: %s" % ex, "quando": ora()}
        log("[ATTENZIONE] La chiave di Instagram non funziona:", ex)
        return 1 if prima else 0


STAT_FILE = "social/statistiche.json"
STAT_ORE = 20            # ogni quanto si rileggono le statistiche di Instagram
STAT_GIORNI = 120        # giorni di storico tenuti (follower e numeri del giorno)
STAT_POST = 12           # ultimi post di cui si leggono i numeri
METRICHE_CONTO = ("reach", "views", "accounts_engaged", "total_interactions", "profile_views")
METRICHE_POST = ("reach", "views", "saved", "shares", "total_interactions")
STAT_V = 3               # cambia quando cambia il modo di leggere: le statistiche si rileggono subito
STAT_ERR = {}            # primo errore di Meta per ogni metrica (si salva nel file, per capire cosa non va)


def _totale(metrica, da, a):
    """Un numero dell'account tra due istanti (secondi UTC). None se Meta non lo da' (metrica non disponibile)."""
    try:
        j = graph("GET", "%s/insights" % os.environ["IG_USER_ID"],
                  {"metric": metrica, "period": "day", "metric_type": "total_value", "since": str(da), "until": str(a)})
    except RuntimeError as ex:
        STAT_ERR.setdefault(metrica, str(ex)[:200])
        return None
    if not j.get("data"):
        STAT_ERR.setdefault(metrica, "Meta non ha dato numeri (risposta vuota)")
    for m in j.get("data", []):
        tv = m.get("total_value") or {}
        if "value" in tv:
            return tv["value"]
    return None


def _numeri_post(mid):
    out = {}
    try:                                         # prima tutte insieme (1 chiamata), se Meta ne rifiuta una si va una per una
        j = graph("GET", "%s/insights" % mid, {"metric": ",".join(METRICHE_POST)})
        for m in j.get("data", []):
            out[m["name"]] = (m.get("values") or [{}])[0].get("value", (m.get("total_value") or {}).get("value"))
        return out
    except RuntimeError:
        pass
    for k in METRICHE_POST:
        try:
            j = graph("GET", "%s/insights" % mid, {"metric": k})
            for m in j.get("data", []):
                out[m["name"]] = (m.get("values") or [{}])[0].get("value", (m.get("total_value") or {}).get("value"))
        except RuntimeError:
            continue
    return out


def _openssl(args, dati):
    import subprocess
    r = subprocess.run(["openssl", "enc", "-aes-256-cbc", "-pbkdf2", "-iter", "200000", "-md", "sha256", "-a", "-A",
                        "-pass", "env:BACKUP_CHIAVE"] + args, input=dati, capture_output=True, timeout=60)
    if r.returncode != 0:
        raise RuntimeError("openssl: %s" % r.stderr.decode("utf-8", "replace").strip()[:120])
    return r.stdout


def cifra(d):
    """Le statistiche vanno nel repo pubblico: si salvano CIFRATE con BACKUP_CHIAVE (uguale al codice admin, che le decifra nel browser)."""
    return {"formato": "aes-256-cbc pbkdf2 sha256 200000", "dati": _openssl(["-salt"], json.dumps(d, ensure_ascii=False).encode("utf-8")).decode("ascii")}


def decifra(f):
    if not isinstance(f, dict) or "dati" not in f:
        return f or {}                      # file vecchio non cifrato (o assente)
    try:
        return json.loads(_openssl(["-d"], f["dati"].encode("ascii") + b"\n").decode("utf-8"))
    except (RuntimeError, ValueError) as ex:
        log("[ATTENZIONE] Statistiche vecchie non decifrabili (BACKUP_CHIAVE cambiata?), si riparte da zero:", ex)
        return {}


PUBBLICO_MIN = 100       # sotto i 100 follower Meta non da' i dati sul pubblico


def _pubblico(follower):
    """Citta', paesi, eta', genere e ore online dei follower (dati aggregati di Meta). Sotto i 100 follower Meta li rifiuta."""
    if (follower or 0) < PUBBLICO_MIN:
        return {"msg": "sotto %d follower" % PUBBLICO_MIN}
    uid, out = os.environ["IG_USER_ID"], {}
    for chiave, bd in (("citta", "city"), ("paesi", "country"), ("eta", "age"), ("genere", "gender")):
        try:
            j = graph("GET", "%s/insights" % uid, {"metric": "follower_demographics", "period": "lifetime",
                                                   "metric_type": "total_value", "breakdown": bd})
            res = []
            for m in j.get("data", []):
                for b in (m.get("total_value") or {}).get("breakdowns") or []:
                    for r in b.get("results") or []:
                        res.append([(r.get("dimension_values") or ["?"])[0], r.get("value", 0)])
            out[chiave] = sorted(res, key=lambda x: -x[1])[:10]
        except RuntimeError as ex:
            out.setdefault("msg", str(ex)[:160])
    try:
        j = graph("GET", "%s/insights" % uid, {"metric": "online_followers", "period": "lifetime"})
        for m in j.get("data", []):
            v = (m.get("values") or [{}])[-1].get("value")
            if isinstance(v, dict) and v:
                out["ore"] = {str(k): v[k] for k in v}
    except RuntimeError:
        pass
    return out


def statistiche():
    """Una volta al giorno: numeri del profilo Instagram (follower, copertura, visualizzazioni, interazioni), degli ultimi post
    e, dai 100 follower, del pubblico (citta', eta', ore online). Si salvano CIFRATE in social/statistiche.json e si vedono
    nella scheda Statistiche dell'admin. Un errore qui non ferma mai il resto."""
    if not os.environ.get("IG_TOKEN") or not os.environ.get("IG_USER_ID"):
        return
    if not os.environ.get("BACKUP_CHIAVE"):
        log("[ATTENZIONE] Statistiche di Instagram non salvate: manca BACKUP_CHIAVE (servono cifrate, il repo e' pubblico).")
        return
    s = decifra(load(STAT_FILE, {}))
    try:
        ultimo = datetime.strptime(s.get("quando", ""), "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        attesa = STAT_ORE if not s.get("errori") else 0      # se Meta ha rifiutato qualcosa si riprova a ogni giro
        if s.get("v") == STAT_V and (datetime.now(timezone.utc) - ultimo).total_seconds() < attesa * 3600:
            return
    except ValueError:
        pass
    uid = os.environ["IG_USER_ID"]
    try:
        conto = graph("GET", uid, {"fields": "username,followers_count,follows_count,media_count"})
    except RuntimeError as ex:
        log("[ATTENZIONE] Statistiche di Instagram non lette:", ex)
        return
    adesso = datetime.now(timezone.utc)
    oggi = adesso.replace(hour=0, minute=0, second=0, microsecond=0)
    ieri = oggi - timedelta(days=1)
    t_oggi, t_ieri, t_28 = int(oggi.timestamp()), int(ieri.timestamp()), int((oggi - timedelta(days=28)).timestamp())
    periodo = {k: _totale(k, t_28, t_oggi) for k in METRICHE_CONTO}
    giorno = {"data": ieri.strftime("%Y-%m-%d"), "follower": conto.get("followers_count")}
    for k in METRICHE_CONTO:
        giorno[k] = _totale(k, t_ieri, t_oggi)
    giorni = [g for g in s.get("giorni", []) if g.get("data") != giorno["data"]] + [giorno]
    giorni = sorted(giorni, key=lambda g: g["data"])[-STAT_GIORNI:]
    post = []
    try:
        lst = graph("GET", "%s/media" % uid, {"fields": "id,caption,media_type,media_product_type,timestamp,permalink,like_count,comments_count",
                                              "limit": str(STAT_POST)}).get("data", [])
    except RuntimeError as ex:
        log("[ATTENZIONE] Post di Instagram non letti:", ex)
        lst = []
    for m in lst:
        p = {"id": m.get("id"), "data": m.get("timestamp", ""), "tipo": m.get("media_product_type") or m.get("media_type") or "",
             "testo": (m.get("caption") or "").split("\n")[0][:90], "link": m.get("permalink", ""),
             "like": m.get("like_count"), "commenti": m.get("comments_count")}
        p.update(_numeri_post(m["id"]))
        post.append(p)
    s = {"v": STAT_V, "quando": ora(), "errori": STAT_ERR, "account": conto.get("username", ""), "follower": conto.get("followers_count"),
         "seguiti": conto.get("follows_count"), "post_totali": conto.get("media_count"),
         "periodo28": periodo, "giorni": giorni, "post": post, "pubblico": _pubblico(conto.get("followers_count"))}
    save(STAT_FILE, cifra(s))
    log("Statistiche di Instagram aggiornate: %s follower, %d post letti." % (s["follower"], len(post)))


def pulisci(d):
    aperte = [r for r in d["richieste"] if r["ig"]["stato"] in APERTE or r["x"]["stato"] in APERTE or (r.get("yt") or {}).get("stato") in APERTE]
    chiuse = [r for r in d["richieste"] if r not in aperte]
    chiuse.sort(key=lambda r: r.get("creata", ""), reverse=True)
    d["richieste"] = sorted(aperte + chiuse[:TENERE], key=lambda r: r.get("creata", ""), reverse=True)
    usate = {r.get("img") for r in d["richieste"]} | {x for r in d["richieste"] for x in (r.get("imgs") or [])}
    if os.path.isdir(DIR_IMG):
        for f in os.listdir(DIR_IMG):
            if "%s/%s" % (DIR_IMG, f) not in usate:
                os.remove(os.path.join(DIR_IMG, f))


def scadute(d):
    """I post non ancora pubblicati che non hanno piu' senso si annullano da soli (es. «in 2 days» per un torneo gia' passato)."""
    oggi = datetime.now(ROMA).date()
    for r in d["richieste"]:
        motivo = None
        try:
            if r.get("tipo") in ("regionale", "vr"):
                g = date.fromisoformat(r["data"]) if r.get("data") else \
                    datetime.strptime(r.get("creata", ""), "%Y-%m-%dT%H:%M:%SZ").date() + timedelta(days=3)
                if g < oggi:
                    motivo = "il torneo e' gia' passato"
            elif r.get("tipo") == "money":
                a, s_ = int(r["id"][4:8]), int(r["id"][8:])
                if date.fromisocalendar(a, s_, 7) < oggi:
                    motivo = "la settimana e' finita"
            elif r.get("tipo") == "storia":
                if datetime.strptime(r.get("creata", ""), "%Y-%m-%dT%H:%M:%SZ").date() + timedelta(days=STORIA_GIORNI) < oggi:
                    motivo = "notizia ormai vecchia"
        except (ValueError, KeyError):
            continue
        if motivo:
            for k in ("ig", "x", "yt"):
                if k in r and r[k]["stato"] in APERTE:
                    r[k]["stato"], r[k]["msg"] = "annullato", motivo


def crea():
    d = load(FILE, None)
    loc = load(LOCALI, {"locali": []})
    loc = loc.get("locali", []) if isinstance(loc, dict) else []
    reali = [v for v in loc if isinstance(v, dict) and v.get("real") and isinstance(v.get("id"), int)]
    if d is None:
        # prima volta: i locali gia' sul sito NON diventano post, si parte da adesso
        d = {"dal": ora(), "visti": sorted(v["id"] for v in reali), "richieste": [], "ig_stato": {}}
        log("Prima partenza: %d locali gia' sul sito ignorati, da ora ogni nuovo locale diventa una richiesta." % len(reali))
    presenti = {v["id"]: v for v in reali}
    visti = set(d.get("visti", []))
    per_rif = {r["rif"]: r for r in d["richieste"] if r.get("tipo") == "locali"}
    nuove = agg = 0
    scadute(d)
    # testi o grafica nuovi (LINGUA_V): le richieste ancora da approvare fatte con la versione vecchia si rifanno da sole
    for r in list(d["richieste"]):
        if r.get("v") == LINGUA_V or not (r["ig"]["stato"] in APERTE and r["x"]["stato"] in APERTE):
            continue
        if r.get("tipo") == "locali":
            if r["rif"] in presenti:
                prepara_locale(presenti[r["rif"]], r); agg += 1
        else:
            d["richieste"].remove(r)
            if r.get("yt") and r["yt"].get("stato") not in APERTE:
                d.setdefault("yt_tenuti", {})[r["id"]] = r["yt"]   # Short gia' caricato: non va riproposto
            if r["id"] in d.get("fatti", []):
                d["fatti"].remove(r["id"])
            if r.get("tipo") == "money":
                d["rifai_money"] = True       # il money della settimana si rifa' subito, anche se non e' lunedi'
            log("Da rifare con la versione nuova: %s" % r["id"])
    for v in sorted(reali, key=lambda v: v.get("pub", "")):
        r = per_rif.get(v["id"])
        if r:
            if r.get("firma") != firma(v) and (r["ig"]["stato"] in APERTE or r["x"]["stato"] in APERTE):
                prepara_locale(v, r)          # locale corretto sul sito: immagine e testi rifatti (solo dove non ancora pubblicato)
                agg += 1
            continue
        if v["id"] in visti or v.get("pub", "") < d.get("dal", ""):
            continue
        d["richieste"].append(prepara_locale(v))
        nuove += 1
        log("Nuova richiesta: Top 8 #%d %s · %s" % (v["id"], v.get("t", ""), v.get("s", "")))
    for r in d["richieste"]:                  # locale tolto dal sito: quello che non e' ancora uscito si annulla
        if r.get("tipo") == "locali" and r["rif"] not in presenti:
            for k in ("ig", "x", "yt"):
                if k in r and r[k]["stato"] in APERTE:
                    r[k]["stato"], r[k]["msg"] = "annullato", "il torneo e' stato tolto dal sito"
    d["visti"] = sorted(i for i in visti | {v["id"] for v in reali} if i in presenti)
    try:
        nuove += tornei(d)
    except Exception as ex:   # un problema qui non deve fermare le top 8 dei locali
        log("[ATTENZIONE] money tournament / Regionali / VR non preparati:", ex)
    tenuti = d.pop("yt_tenuti", {})
    for r in d["richieste"]:
        if r["id"] in tenuti:
            r["yt"] = tenuti[r["id"]]
    try:                       # YouTube Shorts: ogni richiesta aperta riceve anche la sua voce per la scheda YouTube
        import youtube
        youtube.aggiungi(d)
    except Exception as ex:
        log("[ATTENZIONE] YouTube:", ex)
    esito = controllo_chiave(d)
    if (d.get("ig_stato") or {}).get("ok"):
        try:
            statistiche()
        except Exception as ex:   # le statistiche non devono mai fermare i post
            log("[ATTENZIONE] Statistiche di Instagram:", ex)
    pulisci(d)
    save(FILE, d)
    log("Fatto: %d richieste nuove, %d aggiornate, %d in elenco." % (nuove, agg, len(d["richieste"])))
    return esito


# ---------------------------------------------------------------- money tournament della settimana, Regionali, VR
def valore_eur(t):
    """«$50 to 1st» -> 45.0, «50€» -> 50.0, «20 USD» -> 18.0; senza cifra -> None (va in fondo)."""
    t = str(t or "")
    m = re.search(r"([€$£])\s?(\d[\d.,]*)\s?(k\b)?", t, re.I) or re.search(r"(\d[\d.,]*)\s?(k\b)?\s?(€|eur\b|usd\b|\$|£|gbp\b)", t, re.I)
    if not m:
        return None
    if m.group(1) in "€$£":
        val, k, cur = m.group(2), m.group(3), m.group(1)
    else:
        val, k, cur = m.group(1), m.group(2), m.group(3)
    val = val.rstrip(".,")
    val = val.replace(".", "").replace(",", ".") if re.search(r"\.\d{3}(?!\d)", val) else val.replace(",", "")
    try:
        n = float(val) * (1000 if k else 1)
    except ValueError:
        return None
    return round(n * CAMBIO.get(cur.lower(), 1.0), 2)


def premio_testo(e):
    t = str(e.get("prize") or "").strip()
    n = e.get("name") or ""   # prima «$50», poi «50€»/«20 USD»: cosi' «Cup #4 $50» da' «$50» e non «4 $»
    m = re.search(r"[€$£]\s?\d[\d.,]*(?:\s?k\b)?", n, re.I) or re.search(r"\d[\d.,]*\s?(?:k\s?)?(?:[€$£]|usd\b|eur\b)", n, re.I)
    if t and re.search(r"\d", t) and not (m and m.group(0).strip().replace(" ", "").startswith(t.replace(" ", "")) and m.group(0).strip() != t):
        return t   # il premio scritto nel torneo, tranne se e' la cifra del nome tagliata (vecchio «$5» al posto di «$50»)
    if m:
        return m.group(0).strip()
    if t and re.search(r"\d", t):
        return t
    return "Montepremi" if t.lower() == "montepremi" else "Cash"


def quando_it(d_iso, hhmm=None):
    try:
        g = date.fromisoformat(d_iso)
    except (TypeError, ValueError):
        return ""
    return "%s %d %s" % (GIORNI[g.weekday()], g.day, MESI[g.month - 1][:3]) + (" · %s" % hhmm if hhmm else "")


MESI_EN = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
GIORNI_EN = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def quando_en(d_iso, hhmm=None):
    """Data per le IMMAGINI (in inglese, pubblico internazionale), con il fuso orario italiano (CET/CEST)."""
    try:
        g = date.fromisoformat(d_iso)
    except (TypeError, ValueError):
        return ""
    fuso = ""
    if hhmm:
        try:
            fuso = " " + datetime(g.year, g.month, g.day, 12, tzinfo=ROMA).tzname()
        except Exception:
            fuso = ""
    return "%s %s %d" % (GIORNI_EN[g.weekday()], MESI_EN[g.month - 1], g.day) + (" · %s%s" % (hhmm, fuso) if hhmm else "")


def premio_en(p):
    return "Prize pool" if p == "Montepremi" else p


LINGUA_V = 3   # versione dei testi: 2 = tutto in inglese; 3 = max 5 hashtag, parola chiave in testa, immagini 4:5 (21/11/2026)


def corto(t, n):
    t = str(t or "")
    return t if len(t) <= n else t[:n].rsplit(" ", 1)[0].rstrip(" -·,") + "…"


def numero(t):
    return int(hashlib.sha1(t.encode("utf-8")).hexdigest()[:7], 16)


def piattaforma(url):
    u = str(url or "")
    return "Limitless" if "limitless" in u else "Battlefy" if "battlefy" in u else "Start.gg" if "start.gg" in u else "Online"


def money_settimana(d, ev, adesso, forza=False):
    lun = adesso.date() - timedelta(days=adesso.weekday())
    sett = lun.isocalendar()
    rid = "mon-%d%02d" % (sett[0], sett[1])
    if (not forza and (adesso.weekday() != MONEY_GIORNO or adesso.hour < MONEY_ORA)) or rid in d.setdefault("fatti", []) or any(r["id"] == rid for r in d["richieste"]):
        return 0
    dom = lun + timedelta(days=6)
    lista = [e for e in ev if e.get("type") == "Torneo" and e.get("cash") and "victoryroad.pro" not in str(e.get("url"))
             and e.get("date") and lun.isoformat() <= e["date"] <= dom.isoformat()]
    d["fatti"].append(rid)
    if not lista:
        log("Money tournament della settimana: nessun torneo con premio, niente post.")
        return 0
    for e in lista:
        e["_eur"] = valore_eur(premio_testo(e)) or valore_eur(e.get("name"))
    lista.sort(key=lambda e: (e["_eur"] is None, -(e["_eur"] or 0), e["date"], e.get("time") or ""))
    lista = lista[:MONEY_MAX]
    # nelle immagini tutto in inglese (pubblico internazionale); nel testo del post resta l'italiano
    t = [{"pos": i + 1, "premio": premio_en(premio_testo(e)), "p_it": premio_testo(e), "nome": e["name"],
          "quando": quando_en(e["date"], e.get("time")), "q_it": quando_it(e["date"], e.get("time")),
          "dove": piattaforma(e.get("url"))} for i, e in enumerate(lista)]
    sett_txt = "%d–%d %s" % (lun.day, dom.day, MESI[dom.month - 1]) if lun.month == dom.month else \
               "%d %s – %d %s" % (lun.day, MESI[lun.month - 1][:3], dom.day, MESI[dom.month - 1][:3])
    sett_en = "%s %d–%d" % (MESI_EN[lun.month - 1], lun.day, dom.day) if lun.month == dom.month else \
              "%s %d – %s %d" % (MESI_EN[lun.month - 1], lun.day, MESI_EN[dom.month - 1], dom.day)
    import social_img
    social_img.assegna_caratteri(t, rid)   # carattere «simpatico» a caso per ogni torneo, mai monotono
    os.makedirs(DIR_IMG, exist_ok=True)
    imgs = ["%s/%s-1.jpg" % (DIR_IMG, rid)]
    social_img.settimana_copertina(sett_en, t[0], len(t), imgs[0])
    for n, i in enumerate(range(1, len(t), 2), start=2):
        imgs.append("%s/%s-%d.jpg" % (DIR_IMG, rid, n))
        social_img.settimana_slide(n, t[i:i + 2], imgs[-1])
    import social_img as _si
    righe = ["%d. %s · %s (%s)" % (x["pos"], x["premio"], corto(_si.pulito(x["nome"]), 60), x["quando"]) for x in t]
    ig = ("💰 Pokémon VGC money tournaments this week · %s\n\n%s\n\n🔖 Save it for the week and share it with your teammates."
          "\nSign-ups and reminders: rAKings VGC app, link in bio 📲\n\n%s") % (sett_en, "\n".join(righe), hashtag_ig("money", rid))
    link = SITO + "#online"
    def x_con(k):
        return "💰 Money tournaments of the week (%s)\n%s\nAll of them in the app 👇\n%s\n#PokemonChampions #VGC" % (
            sett_en, "\n".join("%d) %s %s" % (x["pos"], x["premio"], corto(_si.pulito(x["nome"]), 40)) for x in t[:k]), link)
    k = min(5, len(t))
    while k > 1 and peso_x(x_con(k), link) > 275:
        k -= 1
    d["richieste"].append({"id": rid, "v": LINGUA_V, "tipo": "money", "rif": 0, "creata": ora(), "titolo": "Money tournament · " + sett_txt,
                           "sotto": "%d tornei, dal premio piu' alto" % len(t), "img": imgs[0], "imgs": imgs, "link": link,
                           "ig": {"stato": "da approvare", "testo": ig[:MAX_IG]}, "x": {"stato": "da approvare", "testo": x_con(k)}})
    log("Nuova richiesta: money tournament della settimana (%d tornei, %d immagini)" % (len(t), len(imgs)))
    return 1


def grande_evento(d, e, tipo, riga3, rid):
    import social_img
    os.makedirs(DIR_IMG, exist_ok=True)
    img = "%s/%s.jpg" % (DIR_IMG, rid)
    nome = e["name"]
    if tipo == "vr":
        r1 = "Online · %s" % quando_it(e["date"], e.get("time"))
        r2 = "Montepremi" + (" · iscrizione %s €" % ("%.2f" % e["fee"]).replace(".", ",") if isinstance(e.get("fee"), (int, float)) else "")
        link = e.get("signup") or e.get("url") or SITO
        r2 = "Prize pool" + (" · Entry €%.2f" % e["fee"] if isinstance(e.get("fee"), (int, float)) else "")
        ig = ("🏁 Pokémon VGC Victory Road · registration open: %s\n📅 %s\n💰 %s\n\nSign up from the link in bio or in the rAKings VGC app, with a reminder before it starts 📲"
              "\n\n%s") % (nome, quando_en(e["date"], e.get("time")), r2, hashtag_ig("vr", rid))
        xt = "🏁 Registration open: %s\n📅 %s · %s\nSign up 👇\n%s\n#PokemonChampions #VictoryRoad" % (nome, quando_en(e["date"], e.get("time")), r2, link)
    else:
        dove = e.get("where") or ""
        r1 = (dove + " · " if dove else "") + quando_it(e["date"])
        r2 = "Premi: " + e["prize"] if e.get("prize") else ""
        link = SITO + "#regionali"
        q3 = {"iscrizioni aperte": "registration open", "tra 2 giorni": "in 2 days", "domani": "tomorrow", "oggi": "today"}.get(riga3, riga3)
        ig = ("🏆 Pokémon VGC · %s · %s\n📍 %s\n📅 %s\n\nFollow it live in the rAKings VGC app: standings, teams and Top 8 📲"
              "\n\n%s") % (nome, q3, dove or "TBA", quando_en(e["date"]), hashtag_ig("regionale", rid))
        xt = "🏆 %s · %s\n📍 %s\nFollow it live in the app 👇\n%s\n#PokemonChampions #VGC" % (nome, q3, dove or "", link)
    # righe dell'immagine in inglese
    if tipo == "vr":
        e1 = "Online · %s" % quando_en(e["date"], e.get("time"))
        e2 = "Prize pool" + (" · Entry €%.2f" % e["fee"] if isinstance(e.get("fee"), (int, float)) else "")
    else:
        e1 = ((e.get("where") or "") + " · " if e.get("where") else "") + quando_en(e["date"])
        e2 = "Prizes: " + e["prize"] if e.get("prize") else ""
    e3 = {"iscrizioni aperte": "Registration open", "tra 2 giorni": "In 2 days", "domani": "Tomorrow", "oggi": "Today"}.get(riga3, riga3)
    social_img.evento("vr" if tipo == "vr" else "regionale", nome, e1, e2, e3, img)
    d["richieste"].append({"id": rid, "v": LINGUA_V, "tipo": tipo, "rif": 0, "creata": ora(), "data": e["date"], "titolo": nome, "sotto": r1, "img": img, "link": link,
                           "ig": {"stato": "da approvare", "testo": ig[:MAX_IG]}, "x": {"stato": "da approvare", "testo": xt}})
    log("Nuova richiesta: %s" % nome)


VR_DATI = "https://rakings.github.io/VGCdatiAK/vr/"
STATS = "vgcstats"
STORIA_GIORNI = 3      # la storia del vincitore si prepara solo per tornei finiti da meno di 3 giorni


def leggi_url(url):
    req = urllib.request.Request(url + ("&" if "?" in url else "?") + "t=%d" % time.time(), headers={"User-Agent": "rakings-social"})
    with urllib.request.urlopen(req, timeout=40) as r:
        return json.loads(r.read().decode("utf-8"))


def date_brevi(a, b=None, en=False):
    try:
        x = date.fromisoformat(a)
    except (TypeError, ValueError):
        return ""
    if en:
        try:
            y = date.fromisoformat(b) if b and b != a else None
        except ValueError:
            y = None
        if not y:
            return "%s %d" % (MESI_EN[x.month - 1], x.day)
        return "%s %d–%d" % (MESI_EN[x.month - 1], x.day, y.day) if y.month == x.month else \
               "%s %d – %s %d" % (MESI_EN[x.month - 1], x.day, MESI_EN[y.month - 1], y.day)
    t = "%d %s" % (x.day, MESI[x.month - 1][:3])
    try:
        y = date.fromisoformat(b) if b and b != a else None
    except ValueError:
        y = None
    return "%d %s - %s" % (x.day, MESI[x.month - 1][:3], "%d %s" % (y.day, MESI[y.month - 1][:3])) if y else t


def tipi_di(ref, slug):
    t = ref.get(slug) or ""
    if not t:
        k = next((k for k in ref if k.startswith(slug + "-")), None)
        p = slug
        while not t and "-" in p:
            p = p.rsplit("-", 1)[0]
            t = ref.get(p) or ""
        t = t or (ref.get(k) if k else "")
    return [x for x in (t or "").split("/") if x]


def storia_vincitore(d, tipo, eid, meta, giocatori, squadre, ref):
    rid = "sto-%d" % numero(tipo + str(eid))
    top = sorted([p for p in giocatori if isinstance(p, list) and len(p) > 3 and isinstance(p[3], int) and 1 <= p[3] <= 8], key=lambda p: p[3])
    if not top or top[0][3] != 1:
        return None
    w = top[0]
    sq = [(m[1], tipi_di(ref, m[0])) for m in (squadre.get(str(w[0])) or [])][:6]
    evento = meta.get("name") or eid
    luogo = "Online" if tipo == "vr" else (meta.get("city") or "")
    quando = (luogo + " · " if luogo else "") + date_brevi(meta.get("date"), meta.get("end"), en=True)
    import social_img
    os.makedirs(DIR_IMG, exist_ok=True)
    img = "%s/%s.jpg" % (DIR_IMG, rid)
    social_img.storia("vr" if tipo == "vr" else "regionale", evento, quando, w[1], w[2], sq, [(p[3], p[1], p[2]) for p in top[1:]], img)
    link = SITO + ("#stats-vr-" + eid if tipo == "vr" else "#stats-reg-" + str(eid))
    paese = " (%s)" % w[2] if w[2] else ""
    def x_con(k):
        return "🏆 %s%s wins %s!\nTop 8: %s\nTeams and results in the app 👇\n%s\n#PokemonChampions #VGC" % (
            w[1], paese, corto(evento, 60), ", ".join("%s %s" % (social_img.ordinale(p[3]), corto(p[1], 22)) for p in top[1:1 + k]), link)
    k = len(top) - 1
    while k > 0 and peso_x(x_con(k), link) > 275:
        k -= 1
    d["richieste"].append({"id": rid, "v": LINGUA_V, "tipo": "storia", "storia": True, "rif": 0, "creata": ora(),
                           "titolo": "Storia: %s vince" % w[1], "sotto": corto(evento, 70), "img": img, "link": link,
                           "ig": {"stato": "da approvare", "testo": "(storia: Instagram non permette testo nelle storie)"},
                           "x": {"stato": "da approvare", "testo": x_con(k)}})
    log("Nuova richiesta: storia del vincitore, %s" % evento)
    return rid


def storie(d, adesso):
    """Storia «vincitore + squadra + Top 8» per ogni Regionale (vgcstats/) e VR (VGCdatiAK) appena finito (finale decisa)."""
    fatti = d.setdefault("fatti", [])
    primo = not d.get("storie_dal")
    ora_s = adesso.timestamp()
    nuove = 0
    try:
        ref = load(os.path.join(STATS, "ref.json"), {}).get("t") or {}
    except Exception:
        ref = {}
    cand = []
    if os.path.isdir(STATS):
        for eid in os.listdir(STATS):
            m = load(os.path.join(STATS, eid, "meta.json"), None) if os.path.isdir(os.path.join(STATS, eid)) else None
            if isinstance(m, dict) and m.get("status") == "finished" and m.get("finale_alle") and 0 <= ora_s - m["finale_alle"] < STORIA_GIORNI * 86400:
                cand.append(("regionale", eid, m, None))
    try:
        for e in (leggi_url(VR_DATI + "index.json").get("events") or [])[:6]:
            if e.get("status") == "finished":
                m = leggi_url(VR_DATI + e["id"] + "/meta.json")
                if m.get("finale_alle") and 0 <= ora_s - m["finale_alle"] < STORIA_GIORNI * 86400:
                    cand.append(("vr", e["id"], m, VR_DATI + e["id"] + "/"))
    except Exception as ex:
        log("Storie VR: dati non letti (%s)" % ex)
    for tipo, eid, m, base in cand:
        rid = "sto-%d" % numero(tipo + str(eid))
        if rid in fatti:
            continue
        fatti.append(rid)
        if primo:
            continue
        try:
            if base:
                gi, sq = leggi_url(base + "players.json"), leggi_url(base + "teams.json")
            else:
                gi, sq = load(os.path.join(STATS, eid, "players.json"), []), load(os.path.join(STATS, eid, "teams.json"), {})
            if storia_vincitore(d, tipo, eid, m, gi, sq, ref):
                nuove += 1
        except Exception as ex:
            log("Storia non preparata per %s: %s" % (eid, ex))
    if primo:
        d["storie_dal"] = ora()
        log("Storie: primo giro, ricordati %d tornei gia' finiti (nessuna storia)." % len(cand))
    return nuove


def tornei(d, adesso=None):
    """Dai tornei del sito (events.json): money tournament della settimana (lunedi'), VR quando aprono le iscrizioni,
    grandi tornei (Regionali, Special, Internazionali) 2 giorni prima. Al primo giro si ricorda quelli gia' in corso, senza post."""
    adesso = adesso or datetime.now(ROMA)
    ev = load(EVENTI, {"events": []})
    ev = ev.get("events", []) if isinstance(ev, dict) else []
    fatti = d.setdefault("fatti", [])
    primo = not d.get("tornei_dal")
    oggi = adesso.date()
    nuove = 0
    for e in ev:
        if not e.get("date"):
            continue
        try:
            g = date.fromisoformat(e["date"])
        except ValueError:
            continue
        url = str(e.get("url") or "")
        if "victoryroad.pro/vr-" in url:
            rid = "vr-%d" % numero(url)
            aperte = e.get("signup") and g >= oggi
            if aperte and e.get("opensAt"):
                try:
                    aperte = datetime.fromisoformat(e["opensAt"].replace("Z", "+00:00")) <= adesso
                except ValueError:
                    pass
            if aperte and rid not in fatti:
                fatti.append(rid)
                if not primo:
                    grande_evento(d, e, "vr", "iscrizioni aperte", rid); nuove += 1
        elif e.get("type") in GRANDI:
            mancano = (g - oggi).days
            rid = "reg-%d" % numero(e["name"] + e["date"])
            if 0 <= mancano <= 2 and rid not in fatti:
                fatti.append(rid)
                if not primo:
                    grande_evento(d, e, "regionale", "tra 2 giorni" if mancano == 2 else "domani" if mancano == 1 else "oggi", rid); nuove += 1
    if primo:
        d["tornei_dal"] = ora()
        log("Money tournament / Regionali / VR: primo giro, ricordati %d tornei gia' in corso (nessun post)." % len(fatti))
    nuove += money_settimana(d, ev, adesso, forza=bool(d.pop("rifai_money", False)))
    nuove += storie(d, adesso)
    d["fatti"] = d["fatti"][-300:]
    return nuove


# ---------------------------------------------------------------- Instagram (API ufficiale di Meta)
def graph(metodo, percorso, dati=None):
    """Chiamata all'API di Meta. La chiave non viene MAI scritta nei log (ne' l'indirizzo che la contiene)."""
    host = (os.environ.get("IG_HOST") or "graph.facebook.com").strip().strip("/")
    ver = (os.environ.get("IG_API_VER") or "").strip().strip("/")
    url = "https://%s/%s%s" % (host, ver + "/" if ver else "", percorso.strip("/"))
    q = dict(dati or {})
    q["access_token"] = os.environ["IG_TOKEN"]
    corpo = urllib.parse.urlencode(q).encode("utf-8")
    req = urllib.request.Request(url + ("?" + corpo.decode() if metodo == "GET" else ""),
                                 data=None if metodo == "GET" else corpo, method=metodo)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        try:
            err = json.load(e).get("error", {})
            raise RuntimeError("%s (codice %s)" % (err.get("message", "errore"), err.get("code", e.code)))
        except (ValueError, AttributeError):
            raise RuntimeError("Meta ha risposto %s" % e.code)
    except urllib.error.URLError as e:
        raise RuntimeError("Meta non risponde (%s)" % type(e.reason).__name__)


def immagine_online(url):
    for _ in range(10):      # se la richiesta e' appena nata, il sito puo' metterci un paio di minuti a pubblicare l'immagine
        try:
            with urllib.request.urlopen(urllib.request.Request(url, method="HEAD"), timeout=20) as r:
                if r.status == 200:
                    return True
        except (urllib.error.URLError, OSError):
            pass
        time.sleep(15)
    return False


def pronto(cid):
    for _ in range(12):
        s = graph("GET", cid, {"fields": "status_code"}).get("status_code")
        if s == "FINISHED":
            return
        if s in ("ERROR", "EXPIRED"):
            raise RuntimeError("Meta non ha accettato l'immagine (%s)" % s)
        time.sleep(5)


def pubblica_ig(r, testo):
    user = os.environ["IG_USER_ID"]
    urls = [SITO + x for x in (r.get("imgs") or [r["img"]])][:10]
    for url in urls:
        if not immagine_online(url):
            raise RuntimeError("l'immagine non e' ancora online sul sito, riprova tra qualche minuto")
    if r.get("storia"):   # storia: un'immagine verticale, senza testo (l'API non permette adesivi ne' link)
        c = graph("POST", "%s/media" % user, {"image_url": urls[0], "media_type": "STORIES"})
        cid = c.get("id")
        if not cid:
            raise RuntimeError("Meta non ha preparato la storia (account Creator? passalo ad Azienda)")
        pronto(cid)
        p = graph("POST", "%s/media_publish" % user, {"creation_id": cid})
        if not p.get("id"):
            raise RuntimeError("pubblicazione della storia non confermata da Meta")
        return "https://www.instagram.com/stories/"
    if len(urls) > 1:   # carosello: prima ogni immagine, poi il post che le contiene (massimo 10)
        figli = []
        for url in urls:
            c = graph("POST", "%s/media" % user, {"image_url": url, "is_carousel_item": "true"})
            if not c.get("id"):
                raise RuntimeError("Meta non ha preparato un'immagine del carosello")
            pronto(c["id"]); figli.append(c["id"])
        c = graph("POST", "%s/media" % user, {"media_type": "CAROUSEL", "children": ",".join(figli), "caption": testo})
    else:
        c = graph("POST", "%s/media" % user, {"image_url": urls[0], "caption": testo})
    cid = c.get("id")
    if not cid:
        raise RuntimeError("Meta non ha preparato il post")
    pronto(cid)
    p = graph("POST", "%s/media_publish" % user, {"creation_id": cid})
    mid = p.get("id")
    if not mid:
        raise RuntimeError("pubblicazione non confermata da Meta")
    try:
        return graph("GET", mid, {"fields": "permalink"}).get("permalink") or ""
    except RuntimeError:
        return ""


def azione():
    rid, rete, az = os.environ.get("ID", ""), os.environ.get("RETE", ""), os.environ.get("AZIONE", "")
    testo = (os.environ.get("TESTO") or "").replace("\r", "").strip()
    d = load(FILE, None)
    r = next((x for x in (d or {}).get("richieste", []) if x.get("id") == rid), None)
    if not r or rete not in ("ig", "x", "yt") or rete not in r:
        log("Richiesta %s non trovata: niente da fare." % rid)
        return 0
    s = r[rete]
    if s["stato"] not in APERTE:
        log("Richiesta %s (%s) gia' chiusa (%s): niente da fare." % (rid, rete, s["stato"]))
        return 0
    if testo:
        s["testo"] = testo[:100] if rete == "yt" else testo[:MAX_IG]
    if az == "rifiuta":
        s.update({"stato": "rifiutato", "quando": ora()})
        s.pop("msg", None)
    elif rete == "x" and az == "fatto":
        s.update({"stato": "pubblicato", "quando": ora()})
        s.pop("msg", None)
    elif rete == "ig" and az == "approva":
        if not os.environ.get("IG_TOKEN") or not os.environ.get("IG_USER_ID"):
            s.update({"stato": "errore", "msg": "Instagram non e' ancora collegato (mancano IG_TOKEN / IG_USER_ID su GitHub)"})
        else:
            try:
                link = pubblica_ig(r, s["testo"])
                s.update({"stato": "pubblicato", "quando": ora(), "url": link})
                s.pop("msg", None)
                log("Pubblicato su Instagram: %s" % (link or rid))
            except RuntimeError as ex:
                s.update({"stato": "errore", "msg": str(ex)[:300]})
                log("[ERRORE] Instagram:", ex)
    elif rete == "yt" and az == "approva":
        try:
            import youtube
            link, nota = youtube.pubblica(r, s["testo"])
            s.update({"stato": "pubblicato", "quando": ora(), "url": link})
            s.pop("msg", None)
            if nota:
                s["msg"] = nota
            log("Caricato su YouTube: %s" % link)
        except Exception as ex:
            s.update({"stato": "errore", "msg": str(ex)[:300]})
            log("[ERRORE] YouTube:", ex)
    else:
        log("Azione non valida: %s / %s" % (rete, az))
        return 0
    save(FILE, d)
    return 0


if __name__ == "__main__":
    a = sys.argv[1:]
    sys.exit(crea() if a == ["crea"] else azione() if a == ["azione"] else 2)
