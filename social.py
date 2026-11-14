#!/usr/bin/env python3
"""Post per Instagram e X di rAKings VGC. Gira nella repo del sito (VGCrAKings), da solo.

  python3 social.py crea    -> per ogni torneo locale APPENA PUBBLICATO sul sito (locali.json) prepara una richiesta:
                               immagine della Top 8 + testo per Instagram + testo per X, da approvare nella tua pagina admin.
                               Controlla anche, una volta al giorno, che la chiave di Instagram funzioni.
  python3 social.py azione  -> esegue quello che hai scelto nella pagina admin (variabili ID, RETE, AZIONE, TESTO):
                               Instagram «approva» = pubblica davvero; X «fatto» = segna come pubblicato da te; «rifiuta».

Regola: prima il sito, poi i social. Una richiesta nasce SOLO da un locale gia' approvato e pubblicato sul sito;
se il locale viene tolto dal sito, le sue richieste non ancora pubblicate si annullano da sole.
Tutto si salva in social/richieste.json (le immagini in social/img/). Solo libreria standard + Pillow per le immagini."""
import hashlib, json, os, sys, time, urllib.error, urllib.parse, urllib.request
from datetime import datetime, timezone

SITO = "https://rakings.github.io/VGCrAKings/"
FILE = "social/richieste.json"
DIR_IMG = "social/img"
LOCALI = "locali.json"
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


def testi_locale(v, link):
    tipo, neg, citta, data = v.get("t", ""), v.get("s", ""), v.get("c", ""), v.get("d", "")
    nomi = [str(x or "").strip() for x in (v.get("top") or [])][:8]
    nomi = [x for x in nomi if x]
    righe = [(MEDAGLIE[i] if i < 3 else "%d." % (i + 1)) + " " + n for i, n in enumerate(nomi)]
    n = v.get("n")
    gioc = ("\n👥 %s giocatori" % n) if isinstance(n, int) or (isinstance(n, str) and n.isdigit()) else ""
    intro = [
        "🏆 Ecco la Top 8 della %s di %s (%s), %s!" % (tipo, neg, citta, data),
        "🏆 %s da %s a %s: ecco la Top 8 del %s." % (tipo, neg, citta, data),
        "🏆 Top 8 · %s · %s, %s · %s" % (tipo, neg, citta, data),
    ][int(v.get("id") or 0) % 3]     # il testo cambia un po' da un post all'altro (niente post tutti identici)
    ig = intro + gioc + "\n\n" + "\n".join(righe)
    if nomi:
        ig += "\n\nComplimenti a %s! 👏" % nomi[0]
    ig += "\n\nSquadre e risultati completi su rAKings VGC: link in bio 📲"
    ig += "\n\n#PokemonVGC #VGC #VGCItalia #Pokemon #VGC%s" % tag(citta)
    ig = ig[:MAX_IG]

    def x_con(k):
        corpo = "\n".join(righe[:k])
        return "🏆 Top 8 %s · %s (%s)\n%s\nSquadre su rAKings VGC 👇\n%s\n#PokemonVGC #VGCItalia" % (tipo, neg, citta, corpo, link)
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
    social_img.top8(v.get("t", ""), v.get("s", ""), v.get("c", ""), v.get("d", ""), list(v.get("top") or []), img)
    link = SITO + "#locali-" + eh("|".join(str(v.get(k, "")) for k in ("t", "s", "c", "d")))
    ig, x = testi_locale(v, link)
    r = vecchia or {"id": rid, "tipo": "locali", "rif": v["id"], "creata": ora()}
    r.update({"firma": f, "titolo": "Top 8 · %s · %s" % (v.get("t", ""), v.get("s", "")),
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


def pulisci(d):
    aperte = [r for r in d["richieste"] if r["ig"]["stato"] in APERTE or r["x"]["stato"] in APERTE]
    chiuse = [r for r in d["richieste"] if r not in aperte]
    chiuse.sort(key=lambda r: r.get("creata", ""), reverse=True)
    d["richieste"] = sorted(aperte + chiuse[:TENERE], key=lambda r: r.get("creata", ""), reverse=True)
    usate = {r.get("img") for r in d["richieste"]}
    if os.path.isdir(DIR_IMG):
        for f in os.listdir(DIR_IMG):
            if "%s/%s" % (DIR_IMG, f) not in usate:
                os.remove(os.path.join(DIR_IMG, f))


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
            for k in ("ig", "x"):
                if r[k]["stato"] in APERTE:
                    r[k]["stato"], r[k]["msg"] = "annullato", "il torneo e' stato tolto dal sito"
    d["visti"] = sorted(i for i in visti | {v["id"] for v in reali} if i in presenti)
    esito = controllo_chiave(d)
    pulisci(d)
    save(FILE, d)
    log("Fatto: %d richieste nuove, %d aggiornate, %d in elenco." % (nuove, agg, len(d["richieste"])))
    return esito


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


def pubblica_ig(r, testo):
    user = os.environ["IG_USER_ID"]
    url = SITO + r["img"]
    if not immagine_online(url):
        raise RuntimeError("l'immagine non e' ancora online sul sito, riprova tra qualche minuto")
    c = graph("POST", "%s/media" % user, {"image_url": url, "caption": testo})
    cid = c.get("id")
    if not cid:
        raise RuntimeError("Meta non ha preparato il post")
    for _ in range(12):
        s = graph("GET", cid, {"fields": "status_code"}).get("status_code")
        if s == "FINISHED":
            break
        if s in ("ERROR", "EXPIRED"):
            raise RuntimeError("Meta non ha accettato l'immagine (%s)" % s)
        time.sleep(5)
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
    if not r or rete not in ("ig", "x"):
        log("Richiesta %s non trovata: niente da fare." % rid)
        return 0
    s = r[rete]
    if s["stato"] not in APERTE:
        log("Richiesta %s (%s) gia' chiusa (%s): niente da fare." % (rid, rete, s["stato"]))
        return 0
    if testo:
        s["testo"] = testo[:MAX_IG]
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
    else:
        log("Azione non valida: %s / %s" % (rete, az))
        return 0
    save(FILE, d)
    return 0


if __name__ == "__main__":
    a = sys.argv[1:]
    sys.exit(crea() if a == ["crea"] else azione() if a == ["azione"] else 2)
