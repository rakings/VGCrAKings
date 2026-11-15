#!/usr/bin/env python3
"""Bot Regionali, in due modalità (python3 regional_watch.py check | timer):

  check : poche volte al giorno legge l'elenco degli eventi Pokémon su RK9 (rk9.gg/events/pokemon) e, quando RK9 annuncia
          l'orario di apertura delle iscrizioni di un Regionale ("Registration opens ... at ... PDT"), manda UN avviso
          di annuncio. Salva gli orari in regional_watch_state.json (il primo giro memorizza soltanto, senza avvisi).
  timer : non fa richieste a RK9: legge solo regional_watch_state.json e, 8 minuti prima di un'apertura già annunciata,
          manda l'avviso (se parte poco prima, resta in attesa fino al momento giusto). Stato in regional_pre_state.json.

  + Victory Road (dentro «check»): legge anche le pagine Victory Road dei Regionali in arrivo (victoryroad.pro/<anno>-<citta>/),
          dove sono scritte TUTTE le aperture, comprese le wave successive ("A new wave of sign-ups was later announced to open on ...").
          Ogni apertura nuova: avviso subito + avviso 8 minuti prima (come quelle di RK9). Le wave "a sorpresa" ("released ... unannounced")
          danno l'avviso «nuovi posti». Se il modo di scrivere cambia, lo segna (stato «vr_controllo», pagina admin) e il flusso va in rosso
          UNA volta (GitHub manda una mail); intanto RK9 continua a funzionare come prima.

Gli avvisi vanno al canale "regionali" (lo stesso di "Regionali" nelle impostazioni del sito)."""
import html, json, os, random, re, signal, sys, time, unicodedata, urllib.error
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import update_events as ue
from notify_players import fetch_limited

ROME = ZoneInfo("Europe/Rome")
STATE = "regional_watch_state.json"
PRE = "regional_pre_state.json"
LIST_URL = "https://rk9.gg/events/pokemon"
TOPIC = "regionali"
LEAD = timedelta(minutes=8)       # anticipo dell'avviso
MAX_WAIT = timedelta(minutes=24)  # oltre questo tempo il giro successivo se ne occupa

# sigle dei fusi orari che RK9 può usare (ore rispetto a UTC)
TZ = {"PST": -8, "PDT": -7, "MST": -7, "MDT": -6, "CST": -6, "CDT": -5, "EST": -5, "EDT": -4, "AST": -4, "ADT": -3,
      "BRT": -3, "ART": -3, "CLT": -4, "CLST": -3, "COT": -5, "PET": -5, "UTC": 0, "GMT": 0, "WET": 0, "WEST": 1, "BST": 1,
      "CET": 1, "CEST": 2, "EET": 2, "EEST": 3, "JST": 9, "KST": 9, "AEST": 10, "AEDT": 11, "NZST": 12, "NZDT": 13}
MESI = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]
MESI_IT = ["gen", "feb", "mar", "apr", "mag", "giu", "lug", "ago", "set", "ott", "nov", "dic"]

RE_TITLE = re.compile(r"20\d\d\s+[^\d<>|\n,]{2,60}?Pok[eé]mon\s+[A-Za-z ]{0,30}?Championships?")
RE_OPENS = re.compile(r"Registration\s+opens\s+(?:on\s+)?(?:[A-Za-z]+,\s*)?([A-Za-z]+)\.?\s+(\d{1,2})(?:st|nd|rd|th)?(?:,?\s*(\d{4}))?"
                      r"\s*(?:at|@|-)?\s*(\d{1,2})(?::(\d{2}))?\s*([ap])\.?m\.?\s*\(?([A-Za-z]{2,5})\)?", re.I)

def now():
    return datetime.now(timezone.utc)

def log(*a):
    print(*a)
    sys.stdout.flush()

def norm(s):
    return re.sub(r"[^a-z0-9]+", "-", unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()).strip("-")

def when_utc(m, ref):
    """Da 'October 7 at 7:00 pm PDT' a un orario UTC; None se il fuso o il mese non si riconoscono."""
    mon = m.group(1)[:3].lower()
    tz = TZ.get(m.group(7).upper())
    if mon not in MESI or tz is None:
        return None
    hour, minute = int(m.group(4)) % 12 + (12 if m.group(6).lower() == "p" else 0), int(m.group(5) or 0)
    year = int(m.group(3)) if m.group(3) else ref.year
    try:
        local = datetime(year, MESI.index(mon) + 1, int(m.group(2)), hour, minute, tzinfo=timezone(timedelta(hours=tz)))
    except ValueError:
        return None
    if not m.group(3) and local < ref - timedelta(days=60):  # senza anno: la prossima occorrenza
        local = local.replace(year=year + 1)
    return local.astimezone(timezone.utc)

def parse(page):
    """Elenco degli eventi: [{key, name, link, opens (UTC o None), raw}]. Il testo dell'iscrizione sta dopo il titolo di ogni evento."""
    links = sorted(set(re.findall(r"/event/(pokemon-[a-z0-9-]+)", page)))
    t = re.sub(r"<(script|style).*?</\1>", " ", page, flags=re.S | re.I)
    text = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", t)).replace("\xa0", " "))
    hits = list(RE_TITLE.finditer(text))
    out = {}
    for i, h in enumerate(hits):
        chunk = text[h.end(): hits[i + 1].start() if i + 1 < len(hits) else h.end() + 600]
        title = re.sub(r"\s+", " ", h.group(0)).strip()
        key = norm(title)
        e = out.setdefault(key, {"key": key, "name": title, "opens": None, "raw": ""})
        m = RE_OPENS.search(chunk[:600])
        if m and not e["raw"]:
            e["raw"] = m.group(0)
            e["opens"] = when_utc(m, now())
    for e in out.values():
        city = norm(re.sub(r"^20\d\d\s+", "", e["name"]).split(" Pok")[0])
        slug = next((s for s in links if city and city in s), None)
        e["link"] = "https://rk9.gg/event/" + slug if slug else LIST_URL
    return list(out.values())

def clean(name):
    return re.sub(r"\s+", " ", re.sub(r"^20\d\d\s+", "", name).replace("Pokémon ", "").replace("Pokemon ", "")).strip()

def it_time(dt):
    r = dt.astimezone(ROME)
    return "%d %s alle %s" % (r.day, MESI_IT[r.month - 1], r.strftime("%H:%M"))

def save(st, path=STATE):
    json.dump(st, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

def ready():
    if hasattr(signal, "SIGALRM"):
        signal.alarm(28 * 60)  # rete di sicurezza: il lavoro dura al massimo 30 minuti
    if not (os.environ.get("NTFY_PREFIX") or ue.push_on()):
        log("regional_watch: né Firebase né NTFY_PREFIX impostati")
        return False
    return True

def check():
    if not ready():
        return
    if os.environ.get("GITHUB_EVENT_NAME") == "schedule":
        time.sleep(random.uniform(0, 60))  # un po' di variazione negli orari di lettura
    log("regional_watch: leggo l'elenco RK9")
    try:
        t0 = time.monotonic()
        page = fetch_limited(LIST_URL, total=40)
        log("regional_watch: pagina letta in %.1f secondi" % (time.monotonic() - t0))
    except Exception as ex:
        log("regional_watch: pagina RK9 non letta:", ex)
        return
    evs = parse(page)
    if not evs:
        log("regional_watch: nessun evento riconosciuto (formato della pagina cambiato?)")
        return
    for e in evs:
        log("  %s -> %s" % (clean(e["name"]), ("iscrizioni dal %s UTC (%s)" % (e["opens"].strftime("%d/%m %H:%M"), e["raw"])) if e["opens"] else (e["raw"] or "nessun orario di apertura")))
    cur = {e["key"]: e for e in evs}
    st = ue.load(STATE, None)

    def entry(e):
        return {"name": clean(e["name"]), "link": e["link"], "opens": e["opens"].isoformat() if e["opens"] else None}

    if not isinstance(st, dict):  # primo giro: si ricorda tutto, senza avvisi di annuncio
        st = {"ev": {k: entry(e) for k, e in cur.items()}}
        rc = vr_check(st, cur)
        save(st)
        log("regional_watch: stato iniziale salvato, nessun avviso di annuncio")
        return rc
    known = st.setdefault("ev", {})
    for k, e in cur.items():
        s = known.get(k)
        iso = e["opens"].isoformat() if e["opens"] else None
        if iso and (s is None or s.get("opens") != iso):
            changed = bool(s and s.get("opens"))
            title = "Regionali: orario iscrizioni aggiornato" if changed else "Regionali: iscrizioni annunciate"
            body = "%s\nApertura iscrizioni: %s (ora italiana)" % (clean(e["name"]), it_time(e["opens"]))
            try:
                ue.deliver(TOPIC, title, body, e["link"])
                log("regional_watch: annuncio inviato:", clean(e["name"]))
            except Exception as ex:
                log("regional_watch: annuncio non inviato:", ex)
                continue  # si riprova al giro dopo
        known[k] = entry(e) if (iso or s is None or not s.get("opens")) else s
        save(st)
    for k in [k for k in known if k not in cur]:  # via gli eventi spariti dall'elenco
        del known[k]
    save(st)
    rc = vr_check(st, cur)
    save(st)
    return rc


# ---------------------------------------------------------------- Victory Road: tutte le wave di iscrizione
VR_SITO = "https://victoryroad.pro/"
VR_MAX_PAGINE = 25
MESI_EN = {m: i + 1 for i, m in enumerate(["january", "february", "march", "april", "may", "june", "july", "august", "september",
                                           "october", "november", "december"])}
RE_APRE = re.compile(r"\bopens?\b[^()]{0,40}?\bon\s+(?:(\d{1,2})\s+([A-Za-z]{3,9})|([A-Za-z]{3,9})\s+(\d{1,2}))[^()]{0,60}?\(([^()]{0,40}?UTC)\)", re.I)
RE_UTC = re.compile(r"(?:(?:(\d{1,2})\s+([A-Za-z]{3,9})|([A-Za-z]{3,9})\s+(\d{1,2}))\s*(?:at|,)?\s*)?(\d{1,2}):(\d{2})\s*UTC", re.I)
RE_SORPRESA = re.compile(r"\bwave\b.{0,80}\breleased\b.{0,80}\bunannounced\b|\breleased\b.{0,60}\bunannounced\b", re.I)
RE_STATO = re.compile(r"\bsign-?ups are (open|closed)\b", re.I)
RE_DOPO = re.compile(r"\b(will be announced|to be announced|tba|tbd|to be confirmed|not yet)\b", re.I)


def vr_slug(key):
    """«2027-stuttgart-pokemon-regional-championships» -> «2027-stuttgart» (gli altri tipi di evento non hanno questo indirizzo)."""
    m = re.match(r"^(20\d\d)-(.+?)-pokemon-regional-championships$", key)
    return "%s-%s" % (m.group(1), m.group(2)) if m else None


def vr_mese(nome):
    nome = (nome or "").lower()
    return next((v for k, v in MESI_EN.items() if k.startswith(nome[:3])), None) if len(nome) >= 3 else None


def vr_data(giorno, mese, ora, minuti, rif):
    """Data senza anno: si sceglie l'anno che la mette piu' vicina a oggi (le pagine parlano di date entro pochi mesi)."""
    meglio = None
    for a in (rif.year - 1, rif.year, rif.year + 1):
        try:
            d = datetime(a, mese, giorno, ora, minuti, tzinfo=timezone.utc)
        except ValueError:
            continue
        if meglio is None or abs(d - rif) < abs(meglio - rif):
            meglio = d
    return meglio


def vr_frasi(page):
    t = re.sub(r"<(script|style).*?</\1>", " ", page, flags=re.S | re.I)
    testo = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", t)).replace("\xa0", " "))
    i = testo.lower().find("sign-up instructions")
    parte = testo[i:i + 6000] if i >= 0 else testo
    return i >= 0, [f.strip() for f in re.split(r"(?<=[.!?])\s+", parte) if re.search(r"sign-?ups?|registration|\bwave\b", f, re.I)]


def vr_leggi(page, rif):
    """Dalla pagina di un Regionale: aperture (UTC), wave a sorpresa, stato, frasi non capite."""
    ha_sezione, frasi = vr_frasi(page)
    out = {"aperture": [], "sorpresa": 0, "stato": "", "dubbi": [], "sezione": ha_sezione}
    for f in frasi:
        st = RE_STATO.search(f)
        if st and not out["stato"]:
            out["stato"] = st.group(1).lower() + (" (esaurito Masters)" if re.search(r"sold out for masters", f, re.I) else "")
        if RE_SORPRESA.search(f):
            out["sorpresa"] += 1
            continue
        trovate = 0
        for m in RE_APRE.finditer(f):
            u = RE_UTC.search(m.group(5))
            if not u:
                continue
            g, me = (u.group(1), u.group(2)) if u.group(1) else (u.group(4), u.group(3)) if u.group(3) else \
                    ((m.group(1), m.group(2)) if m.group(1) else (m.group(4), m.group(3)))
            mese = vr_mese(me)
            d = vr_data(int(g), mese, int(u.group(5)), int(u.group(6)), rif) if mese and g else None
            if d:
                out["aperture"].append(d)
                trovate += 1
        # una frase che parla di aperture o di wave ma da cui non si ricava nessun orario: il formato potrebbe essere cambiato
        if not trovate and re.search(r"\bopens?\b[^.]{0,40}\bon\b|\bwave\b", f, re.I) and not RE_DOPO.search(f):
            out["dubbi"].append(f[:220])
    out["aperture"] = sorted(set(out["aperture"]))
    return out


def vr_check(st, cur):
    """Ritorna 1 solo quando il controllo passa da «ok» a «problema» (flusso in rosso = una mail da GitHub), altrimenti 0."""
    known, vr = st.setdefault("ev", {}), st.setdefault("vr", {})
    primo = "vr_controllo" not in st
    chiavi = [k for k in cur if vr_slug(k)][:VR_MAX_PAGINE]
    lette = mancanti = errori = 0
    problemi = []
    for k in chiavi:
        url = VR_SITO + vr_slug(k) + "/"
        try:
            page = fetch_limited(url, total=30)
        except urllib.error.HTTPError as ex:
            if ex.code == 404:
                mancanti += 1          # pagina non ancora creata: normale per i Regionali lontani
            else:
                errori += 1
            continue
        except Exception:
            errori += 1
            continue
        lette += 1
        e, nome = cur[k], clean(cur[k]["name"])
        r = vr_leggi(page, now())
        if not r["sezione"]:
            problemi.append({"nome": nome, "frase": "manca la sezione «Sign-up instructions» (pagina cambiata?)"})
        problemi += [{"nome": nome, "frase": f} for f in r["dubbi"][:2]]
        s = vr.get(k)
        nuove = [d for d in r["aperture"] if d.isoformat() not in ((s or {}).get("waves") or [])]
        rk9 = (known.get(k) or {}).get("opens")
        if s is not None and not primo:
            for d in nuove:
                if d <= now() + timedelta(minutes=10) or d.isoformat() == rk9:
                    continue           # gia' passata, o gia' annunciata da RK9: niente doppione
                prima = bool((s.get("waves") or []) or rk9)
                titolo = "Regionali: nuova wave di iscrizioni" if prima else "Regionali: iscrizioni annunciate"
                try:
                    ue.deliver(TOPIC, titolo, "%s\nApertura iscrizioni: %s (ora italiana)" % (nome, it_time(d)), e.get("link") or LIST_URL)
                    log("regional_watch: VR, %s -> %s %s" % (titolo, nome, d.isoformat()))
                except Exception as ex:
                    log("regional_watch: avviso VR non inviato:", ex)
                    r["aperture"] = [x for x in r["aperture"] if x != d]   # si riprova al giro dopo
            if r["sorpresa"] > (s.get("sorpresa") or 0) and r["stato"] == "open":
                try:
                    ue.deliver(TOPIC, "Regionali: nuovi posti disponibili", "%s\nSi sono liberati posti: iscrizioni di nuovo aperte" % nome, e.get("link") or LIST_URL)
                    log("regional_watch: VR, nuovi posti ->", nome)
                except Exception as ex:
                    log("regional_watch: avviso VR non inviato:", ex)
                    r["sorpresa"] = s.get("sorpresa") or 0
        vr[k] = {"name": nome, "link": e.get("link") or LIST_URL, "waves": [d.isoformat() for d in r["aperture"]],
                 "sorpresa": r["sorpresa"], "stato": r["stato"]}
        log("  VR %s: %d aperture, %d a sorpresa, iscrizioni %s%s" % (nome, len(r["aperture"]), r["sorpresa"], r["stato"] or "?",
                                                                      (", %d frasi non capite" % len(r["dubbi"])) if r["dubbi"] else ""))
    for k in [k for k in vr if k not in cur]:
        del vr[k]
    if chiavi and not lette and (mancanti == len(chiavi) and len(chiavi) >= 3):
        problemi.append({"nome": "Victory Road", "frase": "nessuna pagina dei Regionali trovata: forse gli indirizzi sono cambiati"})
    ok = not problemi
    prima_ok = (st.get("vr_controllo") or {}).get("ok", True)
    st["vr_controllo"] = {"ok": ok, "quando": now().isoformat(timespec="minutes"), "pagine": lette, "senza_pagina": mancanti,
                          "errori": errori, "problemi": problemi[:6]}
    if errori and not lette:
        st["vr_controllo"]["nota"] = "Victory Road non ha risposto a questo giro"
    if not ok:
        log("regional_watch: [ATTENZIONE] Victory Road, formato forse cambiato:", json.dumps(problemi[:3], ensure_ascii=False))
    return 1 if (prima_ok and not ok) else 0

def timer():
    """Solo file locali: nessuna richiesta a RK9."""
    st = ue.load(STATE, None)
    if not isinstance(st, dict):
        return
    pre = ue.load(PRE, {})
    due = []
    voci = [(k, s) for k, s in (st.get("ev") or {}).items()]
    for k, v in (st.get("vr") or {}).items():   # le wave lette da Victory Road (la stessa apertura di RK9 ha la stessa chiave: un solo avviso)
        voci += [(k, {"name": v.get("name"), "link": v.get("link"), "opens": w}) for w in (v.get("waves") or [])]
    for k, s in voci:
        if not s.get("opens") or "%s|%s" % (k, s["opens"]) in pre or any(x[1] == k and x[2]["opens"] == s["opens"] for x in due):
            continue
        opens = datetime.fromisoformat(s["opens"])
        if timedelta(minutes=-30) <= opens - now() <= MAX_WAIT + LEAD:
            due.append((opens, k, s))
    if not due or not ready():
        log("regional_watch: nessuna apertura imminente")
        return
    for opens, k, s in sorted(due, key=lambda x: x[0]):
        wait = (opens - LEAD - now()).total_seconds()
        if wait > 0:
            log("regional_watch: attendo %d secondi per %s" % (wait, s.get("name")))
            time.sleep(wait)
        left = opens - now()
        hhmm = opens.astimezone(ROME).strftime("%H:%M")
        if left > timedelta(0):
            mins = max(1, int((left.total_seconds() + 59) // 60))
            title, body = "Iscrizioni tra %d minuti" % mins, "%s\nSi aprono alle %s (ora italiana)" % (s.get("name"), hhmm)
        else:
            title, body = "Iscrizioni aperte ora", "%s\nApertura prevista alle %s (ora italiana)" % (s.get("name"), hhmm)
        try:
            ue.deliver(TOPIC, title, body, s.get("link") or LIST_URL)
            log("regional_watch: %s -> %s" % (title, s.get("name")))
        except Exception as ex:
            log("regional_watch: avviso non inviato:", ex)
            continue
        pre["%s|%s" % (k, s["opens"])] = now().isoformat()
        save(pre, PRE)
    pre = {k: v for k, v in pre.items() if datetime.fromisoformat(v) > now() - timedelta(days=5)}
    save(pre, PRE)

if __name__ == "__main__":
    sys.exit((timer if (sys.argv[1:] or ["check"])[0] == "timer" else check)() or 0)
