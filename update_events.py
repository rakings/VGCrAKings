#!/usr/bin/env python3
"""Raccoglie i tornei VGC da Limitless e da Victory Road e salva events.json.
Usa solo la libreria standard. Gli eventi di manual.json hanno la precedenza."""
import html, json, os, re, time, unicodedata, urllib.parse, urllib.request, urllib.error
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

API = "https://play.limitlesstcg.com/api/tournaments"
VR = "https://victoryroad.pro/"
OUT = "events.json"
ROME = ZoneInfo("Europe/Rome")
MESI = ["january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december"]
UA = "tornei-vgc-bot (sito della community, con link alle fonti)"

def get(url, tries=3, timeout=30):
    """Legge una pagina. Riprova se c'è un errore temporaneo; 404 e 410 (pagina che non esiste) subito."""
    last = None
    for i in range(tries):
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        key = os.environ.get("LIMITLESS_KEY")
        if key and url.startswith(API):
            req.add_header("X-Access-Key", key)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            if e.code in (400, 401, 403, 404, 410):  # errore definitivo: inutile riprovare
                raise
            last = e
        except Exception as e:
            last = e
        if i < tries - 1:
            time.sleep(3 * (i + 1))
    raise last

PREV = {}        # eventi salvati al giro precedente (url -> evento)
PARTIAL = set()  # fonti lette solo in parte in questo giro
KEEP = set()     # pagine non lette per un errore temporaneo: si tiene la copia precedente
LIVE = set()     # tornei che Limitless dà "in corso" adesso: restano finché non finiscono
GRACE_H = 8      # ore dopo l'inizio in cui un torneo con orario resta in elenco (poi si considera finito)

# ---------- Limitless ----------
def limitless():
    out, seen = [], set()
    for page in range(1, 6):  # fino a 5 pagine da 100: un solo giro non basta se i tornei sono tanti
        q = urllib.parse.urlencode({"game": "VGC", "limit": 100, "page": page})
        try:
            batch = json.loads(get(API + "?" + q))
            if not isinstance(batch, list):
                raise ValueError("risposta inattesa: " + str(batch)[:200])
        except Exception as ex:
            if page == 1:
                raise
            print("Limitless pagina %d non letta: %s" % (page, ex))
            PARTIAL.add("Limitless")
            break
        nuovi = [t for t in batch if t.get("id") not in seen]
        if not nuovi:
            break
        for t in nuovi:
            seen.add(t.get("id"))
        out.extend(limitless_event(t) for t in nuovi)
        if len(batch) < 20:
            break
    return out

SITE = "https://play.limitlesstcg.com"
# pagine pubbliche di Limitless: elenco "in corso" e "prossimi 7 giorni" che si vedono sul sito
PAGINE = (("/tournaments?game=VGC", 1), ("/tournaments/upcoming?game=VGC", 3), ("/tournaments/ongoing?game=VGC", 1))
# l'ID è di 24 caratteri esadecimali, ma gli eventi in evidenza (stellina) hanno un indirizzo personalizzato, es. "pokebros2026"
ID = r"([0-9A-Za-z][0-9A-Za-z_-]{2,60})"
RE_ID = re.compile(r"/tournament/" + ID + r"/(?:details|register|registrations|pairings)")
RE_ISCRITTI = re.compile(r"""href=["'][^"']*?/tournament/""" + ID + r"""/registrations["'][^>]*>\s*(\d+)""")

def _dt_from(txt):
    """Prova a leggere una data/ora (epoch in secondi o millisecondi, oppure ISO 8601) e la dà in UTC."""
    txt = (txt or "").strip()
    try:
        if re.fullmatch(r"\d{10,13}", txt):
            n = int(txt)
            return datetime.fromtimestamp(n / 1000 if n > 10**11 else n, tz=timezone.utc)
        d = datetime.fromisoformat(txt.replace("Z", "+00:00"))
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except Exception:
        return None

RE_DATE = (re.compile(r'data-time=["\'](\d{10,13})["\']'),
           re.compile(r'<time[^>]*datetime=["\']([^"\']+)["\']'),
           re.compile(r'data-date=["\']([^"\']+)["\']'),
           re.compile(r'"startDate"\s*:\s*"([^"]+)"'),
           re.compile(r'"date"\s*:\s*"(\d{4}-\d{2}-\d{2}T[^"]+)"'))

def limitless_page(i):
    """Dettagli di un torneo letti dalla sua pagina pubblica: nome, organizzatore, data e ora di inizio."""
    page = get(SITE + "/tournament/%s/details" % i)
    m = (re.search(r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)["\']', page)
         or re.search(r'<title[^>]*>([^<]+)</title>', page))
    name = html.unescape(m.group(1)).strip() if m else ""
    name = re.sub(r"\s*[-|\u2013]\s*Limitless\w*\s*$", "", name, flags=re.I).strip()
    m = re.search(r"Organized by\s*(?:<[^>]*>\s*)*([^<\n]+)", page)
    org = html.unescape(m.group(1)).strip() if m else ""
    dt = None
    for rx in RE_DATE:
        for raw in rx.findall(page):
            dt = _dt_from(raw)
            if dt:
                break
        if dt:
            break
    if not name or not dt:
        ctx = re.findall(r".{0,60}(?:data-time|datetime|data-date|startDate).{0,80}", page)[:3]
        print("Limitless %s: pagina letta ma %s non trovato. Titolo=%r; indizi=%r" % (i, "nome" if not name else "data", name[:60], ctx))
        return None
    return {"id": i, "name": name, "organizer": {"name": org}, "game": "VGC",
            "date": dt.strftime("%Y-%m-%dT%H:%M:%S+00:00")}

def limitless_upcoming(have):
    """L'API /tournaments può non elencare i tornei con iscrizioni aperte. Per non perderne nessuno si
    leggono gli ID dalle pagine pubbliche di Limitless e i dettagli di ognuno dall'API ufficiale."""
    ids, iscritti = [], {}
    for path, max_pag in PAGINE:
        for pg in range(1, max_pag + 1):
            url = SITE + path + ("&page=%d" % pg if pg > 1 else "")
            try:
                page = get(url)
            except urllib.error.HTTPError as e:
                if e.code not in (404, 410):
                    print("Limitless %s non letta: HTTP %s" % (path, e.code))
                    PARTIAL.add("Limitless")
                break
            except Exception as ex:
                print("Limitless %s non letta: %s" % (path, ex))
                PARTIAL.add("Limitless")
                break
            trovati = list(dict.fromkeys(RE_ID.findall(page)))
            if "ongoing" in path:
                LIVE.update(SITE + "/tournament/%s/details" % i for i in trovati)
            nuovi = [i for i in trovati if i not in ids]
            if not nuovi:
                break
            ids.extend(nuovi)
            for i, n in RE_ISCRITTI.findall(page):
                iscritti[i] = int(n)
            time.sleep(1)
    print("Limitless: %d tornei trovati nelle pagine pubbliche" % len(ids))
    out = []
    api_ok = True  # se l'API risponde 400 per questi tornei si passa alle pagine pubbliche
    for i in ids[:200]:
        url = SITE + "/tournament/%s/details" % i
        if url in have:
            continue
        old = PREV.get(url)
        if old and old.get("date"):  # già noto dal giro precedente: si aggiorna solo il numero di iscritti
            ev = dict(old)
            ev["players"] = iscritti.get(i, ev.get("players"))
            out.append(ev)
            continue
        t = None
        if api_ok:
            time.sleep(0.5)
            try:
                t = json.loads(get(API + "/%s/details" % i))
            except urllib.error.HTTPError as e:
                if e.code == 400:
                    api_ok = False
                    print("Limitless: l'API non fornisce i dettagli (HTTP 400): leggo le pagine pubbliche dei tornei")
                elif e.code in (401, 403, 404, 410):  # privato o rimosso: si prova la pagina pubblica
                    pass
                else:
                    print("Limitless %s: dettagli non letti (HTTP %s)" % (i, e.code))
                    KEEP.add(url)
                    continue
            except Exception as ex:
                print("Limitless %s: dettagli non letti (%s)" % (i, ex))
                KEEP.add(url)
                continue
        if not isinstance(t, dict):
            time.sleep(0.5)
            try:
                t = limitless_page(i)
            except urllib.error.HTTPError as e:
                if e.code not in (403, 404, 410):
                    print("Limitless %s: pagina non letta (HTTP %s)" % (i, e.code))
                    KEEP.add(url)
                continue
            except Exception as ex:
                print("Limitless %s: pagina non letta (%s)" % (i, ex))
                KEEP.add(url)
                continue
            if not t:
                continue
        if t.get("game") not in (None, "VGC") or t.get("isPublic") is False:
            continue
        t["id"] = i  # l'indirizzo è quello della pagina pubblica (con gli eventi in evidenza l'API può dare un ID diverso)
        ev = limitless_event(t)
        ev["players"] = iscritti.get(i, t.get("players") or None)  # iscritti attuali; per i tornei futuri il numero dell'API non vale
        out.append(ev)
    return out

def limitless_all():
    out = []
    try:
        out = limitless()
    except Exception as ex:
        print("Limitless (elenco API) non letto: %s" % ex)
        PARTIAL.add("Limitless")
    try:
        out.extend(limitless_upcoming({e["url"] for e in out}))
    except Exception as ex:
        print("Limitless (pagine pubbliche) non lette: %s" % ex)
        PARTIAL.add("Limitless")
    return out

def limitless_event(t):
    if True:
        name = t.get("name", "")
        money = re.search(r"[€$£]\s?\d|\d[\d.,]*\s?(?:[€$£]|usd\b|eur\b)|\$\$|\bcash\b|\bpremi[oi] in denaro\b", name, re.I)
        reg = re.search(r"\bM-[A-Z]\b", name, re.I)
        bo = re.search(r"\bBo([13])\b", name, re.I)
        org = t.get("organizer") or {}
        raw = t.get("date") or ""
        try:
            dt = datetime.fromisoformat(raw.replace("Z", "+00:00")).astimezone(ROME)
            date, hhmm = dt.strftime("%Y-%m-%d"), dt.strftime("%H:%M")
        except Exception:
            date, hhmm = raw[:10] or None, None
        return {
            "name": name, "org": org.get("name", "") if isinstance(org, dict) else "",
            "mode": "online", "type": "Torneo", "fee": None,
            "cash": True if money else None,  # mai False: senza indicazione resta "non indicato"
            "prize": money.group(0).strip() if money else "",
            "reg": reg.group(0).upper() if reg else None,
            "bo": "Bo" + bo.group(1) if bo else None,
            "date": date, "time": hhmm, "players": t.get("players"),
            "url": "https://play.limitlesstcg.com/tournament/%s/details" % t["id"],
        }

# ---------- Victory Road ----------
def vr_slugs():
    now = datetime.now(timezone.utc)
    sigle = [m[:3] for m in MESI]
    out = []
    for k in range(4):  # mese corrente e i tre successivi
        i = now.month - 1 + k
        for suf in ["", "-2", "-3", "-4", "-5", "-6"]:
            out.append("vr-%s%02d%s" % (sigle[i % 12], (now.year + i // 12) % 100, suf))
    for n in ("i", "ii", "iii", "iv", "v"):  # Global Challenge: gare online ufficiali nel gioco
        out.append("%d-global-challenge-%s" % (now.year + (1 if now.month >= 6 else 0), n))
    try:  # link trovati nella home
        for s in re.findall(r'href="https://victoryroad\.pro/(vr[a-z0-9-]+)/?"', get(VR)):
            if s not in out:
                out.append(s)
    except Exception as e:
        print("Home di Victory Road non letta:", e)
    return out

def vr_parse(slug, page):
    if "Victory Road" not in page:
        return None
    text = re.sub(r"<(script|style).*?</\1>", " ", page, flags=re.S | re.I)
    text = html.unescape(re.sub(r"<[^>]+>", " ", text)).replace("\xa0", " ")
    text = re.sub(r"\s+", " ", text)
    m = re.search(r"Date\W{0,5}(\d{1,2})(?:\s+([A-Za-z]+))?(?:\s*[–—-]\s*(\d{1,2})\s+([A-Za-z]+))?\s+(\d{4})", text)
    if not m:
        return None
    mon1 = MESI.index((m[2] or m[4] or "").lower()) + 1 if (m[2] or m[4] or "").lower() in MESI else None
    mon2 = MESI.index(m[4].lower()) + 1 if m[4] and m[4].lower() in MESI else mon1
    if not mon1:
        return None
    y = int(m[5])
    date = "%04d-%02d-%02d" % (y, mon1, int(m[1]))
    end = "%04d-%02d-%02d" % (y, mon2, int(m[3])) if m[3] else None
    hhmm = None
    t = re.search(r"at (\d{2}):(\d{2}) UTC", text)
    if t and not end:  # orario solo per eventi di un giorno
        dt = datetime.fromisoformat(date + "T%s:%s:00+00:00" % (t[1], t[2])).astimezone(ROME)
        date, hhmm = dt.strftime("%Y-%m-%d"), dt.strftime("%H:%M")
    sg = re.search(r'href="(https://battlefy\.com/[\w-]+/[\w-]+/[0-9a-f]{24}[^"#]*)"', page)
    signup = sg[1] if sg else None
    title = re.search(r"<title>(.*?)</title>", page, re.S | re.I)
    name = html.unescape(title[1]).strip() if title else slug
    name = re.split(r"\s[–—|-]\s", name)[0].replace("Victory Road ", "VR ", 1)
    name = re.sub(r"\s*\(\d{4}\)", "", name).strip() or slug
    f = re.search(r"Sign-ups are \$(\d+(?:\.\d+)?)", text)
    fee = float(f[1]) if f else (0 if re.search(r"Sign-ups are free|free to enter", text, re.I) else None)
    reg = re.search(r"Regulation Set (M-[A-Z])", text)
    prize = bool(re.search(r"prize ?pool", text, re.I))
    gc = "global-challenge" in slug
    return {
        "name": name, "org": "" if gc else "Victory Road", "mode": "online", "type": "Global Challenge" if gc else "Torneo",
        "fee": fee, "cur": "$" if fee else None, "feeNote": "+ tassa Battlefy" if fee and "Battlefy tax" in text else None,
        "cash": None if gc else (True if prize else None), "prize": "" if gc else ("montepremi" if prize else ""),
        "reg": reg[1] if reg else None, "bo": None,
        "date": date, "end": end, "time": hhmm, "url": VR + slug + "/",
        "signup": signup,
    }

def victory_road():
    out = []
    for slug in vr_slugs():
        time.sleep(1)  # poche richieste, con calma
        url = VR + slug + "/"
        try:
            page = get(url)
        except urllib.error.HTTPError as e:
            if e.code not in (404, 410):  # errore temporaneo, non pagina inesistente
                print("Victory Road %s non letta: HTTP %s" % (slug, e.code))
                KEEP.add(url)
            continue
        except Exception as ex:
            print("Victory Road %s non letta: %s" % (slug, ex))
            KEEP.add(url)
            continue
        try:
            ev = vr_parse(slug, page)
        except Exception as ex:
            print("Victory Road %s non riconosciuta: %s" % (slug, ex))
            KEEP.add(url)
            continue
        if ev:
            out.append(ev)
        elif "Victory Road" in page:
            print("Victory Road %s: pagina senza data riconoscibile" % slug)
            KEEP.add(url)
    return out

# ---------- Regionali ----------
MESI_EN = ["january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december"]

def plain(page):
    t = re.sub(r"<(script|style).*?</\1>", " ", page, flags=re.S | re.I)
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", t)).replace("\xa0", " "))

# Orari scritti da RK9 come "Tournament start  October 17, 2026  08:30 CEST (Europe/Paris)": si converte tutto in UTC
# usando il fuso IANA tra parentesi, così il sito può mostrarli in ora italiana senza errori di fuso.
RK9_WHEN = r"%s\W{0,6}([A-Za-z]+)\.? (\d{1,2}),? (\d{4})\W{0,8}(\d{1,2}):(\d{2})\s*([ap]m)?\W{0,6}(?:[A-Z]{2,5}\W{0,6})?\(([A-Za-z_]+/[A-Za-z_]+(?:/[A-Za-z_]+)?)\)"
RK9_CAMPI = (("regCloseAt", "Registration closes"), ("listAt", "List submission closes"), ("startAt", "Tournament start"),
             ("juniorAt", "Junior division:"), ("seniorAt", "Senior division:"), ("opensAt", "Registration opens"))
RK9_TENUTI = ("signup", "signupLabel", "signupAuto", "regClose", "price", "regCloseAt", "listAt", "startAt", "juniorAt", "seniorAt", "opensAt", "tz")

def rk9_when(text, label):
    """Dà ('2026-10-17T06:30:00Z', 'Europe/Paris') oppure None."""
    m = re.search(RK9_WHEN % label, text, re.I)
    if not m:
        return None
    mon = [k for k, x in enumerate(MESI_EN) if x[:3] == m[1][:3].lower()]
    if not mon:
        return None
    h, mi = int(m[4]), int(m[5])
    if m[6]:
        h = h % 12 + (12 if m[6].lower() == "pm" else 0)
    try:
        loc = datetime(int(m[3]), mon[0] + 1, int(m[2]), h, mi, tzinfo=ZoneInfo(m[7]))
    except Exception:
        return None
    return loc.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), m[7]

def slug_nome(s):
    return re.sub(r"[^a-z0-9]+", "-", unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()).strip("-")

def rk9_watch(e):
    """Dal file del bot Regionali (nessuna richiesta): link della pagina evento RK9 e, se annunciata, l'apertura delle iscrizioni."""
    link, opens = "", None
    try:
        st = load("regional_watch_state.json", {}).get("ev", {})
    except Exception:
        return ""
    k = slug_nome(e.get("name"))
    for v in st.values():
        if slug_nome(v.get("name")) != k:
            continue
        if "/event/" in (v.get("link") or ""):
            link = v["link"]
        if v.get("opens"):
            opens = v["opens"]
    if opens and not e.get("opensAt"):
        try:
            e["opensAt"] = datetime.fromisoformat(opens).astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        except ValueError:
            pass
    return link

def rk9_vgc_link(event_url):
    """Nella pagina evento RK9 c'è un blocco per ogni gioco (TCG, VGC, Pokémon GO): si prende il link del VGC."""
    page = get(event_url)
    m = re.search(r"""(?is)VGC[^<]{0,80}</h\d>.{0,600}?href=["'](?:https?://(?:www\.)?rk9\.gg)?(/tournament/[A-Za-z0-9_-]+)""", page)
    return "https://rk9.gg" + m.group(1) if m else ""

def rk9_info(e, event_link=""):
    """Legge dalla pagina di iscrizione RK9 scadenze, orari di inizio e costo."""
    s = e.get("signup") or ""
    if "rk9.gg/tournament/" not in s and event_link:
        s = rk9_vgc_link(event_link)
        if s:
            e["signup"], e["signupLabel"], e["signupAuto"] = s, "Iscriviti su RK9", True
    if "rk9.gg/tournament/" not in s:
        return
    text = plain(get(s))
    m = re.search(r"Registration closes\W{0,5}([A-Za-z]+) (\d{1,2}), (\d{4})", text)
    if m and m[1].lower() in MESI_EN:
        e["regClose"] = "%s-%02d-%02d" % (m[3], MESI_EN.index(m[1].lower()) + 1, int(m[2]))
    prezzi = re.findall(r"(Junior|Senior|Masters) division:\s*([A-Z]{0,3}[$€£]\s?[\d.,]+)", text)
    if prezzi:
        nomi = {"Junior": "Junior", "Senior": "Senior", "Masters": "Master"}
        e["price"] = ", ".join("%s %s" % (nomi[k], v.replace(".00", "")) for k, v in prezzi)
    for campo, label in RK9_CAMPI:
        w = rk9_when(text, label)
        if w:
            e[campo] = w[0]
            e["tz"] = w[1]

def regionali():
    out = json.load(open("regionali.json", encoding="utf-8"))
    oggi = datetime.now(ROME).date()
    orizzonte = (oggi + timedelta(days=90)).isoformat()
    for e in out:
        try:
            link = rk9_watch(e)
            # solo gli eventi in corso o dei prossimi 90 giorni: gli altri non hanno ancora una pagina utile
            if (e.get("end") or e.get("date") or "") >= oggi.isoformat() and (e.get("date") or "") <= orizzonte:
                rk9_info(e, link)
        except Exception as ex:
            print("Iscrizione non letta per %s: %s" % (e["name"], ex))
    return out

# ---------- Avvisi per categoria (ntfy.sh) ----------
# Ogni categoria ha un canale: NTFY_PREFIX-money, -money33, -gc, -regionali, -vr, -maddos.
# Gli utenti scelgono nel sito (ingranaggio) a quali iscriversi. Stato in notify_state.json.
STATE = "notify_state.json"

def load(p, default):
    try:
        return json.load(open(p, encoding="utf-8"))
    except Exception:
        return default

def days_to(d):
    try:
        return (datetime.strptime(d, "%Y-%m-%d").date() - datetime.now(ROME).date()).days
    except Exception:
        return None

def candidates(e):
    out = []
    low = ((e.get("name") or "") + " " + (e.get("org") or "")).lower()
    opened = bool(e.get("signup")) or "limitlesstcg.com" in (e.get("url") or "")
    if e.get("mode") == "online" and e.get("cash") is True:
        out.append(("money", "new", "Money tournament"))
        if (e.get("players") or 0) > 33:
            out.append(("money33", "big", "Money tournament (oltre 33 iscritti)"))
    if e.get("type") == "Global Challenge":
        out.append(("gc", "new", "Global Challenge"))
    if e.get("mode") == "regional":
        out.append(("regionali", "new", "Regionali: nuovo evento"))
        # il link trovato in automatico non fa partire l'avviso "iscrizioni aperte" (lo danno già il bot Regionali e l'annuncio):
        # altrimenti al primo giro arriverebbero avvisi vecchi su tutti i Regionali già aperti
        if (e.get("signup") or e.get("regClose")) and not e.get("signupAuto"):
            out.append(("regionali", "open", "Regionali: iscrizioni aperte"))
        dd = days_to(e["regClose"]) if e.get("regClose") else None
        if dd is not None and 0 <= dd <= 3:
            out.append(("regionali", "close", "Regionali: iscrizioni in chiusura"))
    # torneo locale segnalato da un organizzatore (inserito a mano in manual.json): dal vivo, oppure Lega / Sfida di Lega / Coppa di Lega
    if e.get("mode") == "live" or "lega" in (e.get("type") or "").lower() or e.get("local") is True:
        out.append(("locali", "new", "Torneo locale segnalato"))
    for cat, key, label in (("vr", "victory road", "Victory Road"), ("maddos", "maddo", "Maddos Cup")):
        if key in low:
            out.append((cat, "new", label + ": torneo annunciato"))
            if opened:
                out.append((cat, "open", label + ": iscrizioni aperte"))
    return out

def say(topic, title, body, click):
    head = {"Title": title.encode("ascii", "ignore").decode(), "Tags": "trophy"}
    if click.startswith("http"):
        head["Click"] = click
    if os.environ.get("SITE_URL", "").startswith("http"):
        head["Icon"] = os.environ["SITE_URL"].rstrip("/") + "/icon-192.png"
    req = urllib.request.Request("https://ntfy.sh/" + topic, data=body.encode("utf-8"), headers=head, method="POST")
    urllib.request.urlopen(req, timeout=30).read()

def os_on():
    return bool(os.environ.get("ONESIGNAL_APP_ID") and os.environ.get("ONESIGNAL_API_KEY"))

def os_filters(topic):
    """Filtri OneSignal: le scelte dell'utente (tag) impostate dall'ingranaggio del sito."""
    if topic.startswith("t-"):
        return [{"field": "tag", "key": "t_" + topic[2:], "relation": "=", "value": "1"}]
    cat, one = (topic[:-3], True) if topic.endswith("-1h") else (topic, False)
    val = "all" if cat == "money" else "33" if cat == "money33" else "1"
    key = "c_money" if cat in ("money", "money33") else "c_" + cat
    f = [{"field": "tag", "key": key, "relation": "=", "value": val}]
    if one:
        f.append({"field": "tag", "key": "h_" + ("money" if cat in ("money", "money33") else cat), "relation": "=", "value": "1"})
    return f

def send_os(filters, title, body, click, ids=None):
    """Invia con OneSignal: ai filtri sui tag (vecchio sistema) oppure a un elenco di iscrizioni (archivio iscritti)."""
    base = {"app_id": os.environ["ONESIGNAL_APP_ID"], "target_channel": "push",
            "headings": {"en": title, "it": title}, "contents": {"en": body, "it": body}}
    if click.startswith("http"):
        base["url"] = click
    site = os.environ.get("SITE_URL", "").rstrip("/")
    if site.startswith("http"):  # logo accanto alla notifica
        base["chrome_web_icon"] = site + "/icon-192.png"
        base["chrome_web_badge"] = site + "/badge-96.png"
    batches = [dict(base, included_segments=["Subscribed Users"]) if filters == "TUTTI" else dict(base, filters=filters)] if ids is None else [dict(base, include_subscription_ids=ids[k:k + 2000]) for k in range(0, len(ids), 2000)]
    r = {}
    for data in batches:
        req = urllib.request.Request("https://api.onesignal.com/notifications", data=json.dumps(data).encode("utf-8"), method="POST",
                                     headers={"Content-Type": "application/json", "Authorization": "Key " + os.environ["ONESIGNAL_API_KEY"]})
        try:
            r = json.loads(urllib.request.urlopen(req, timeout=30).read().decode("utf-8") or "{}")
        except urllib.error.HTTPError as ex:
            raise RuntimeError("OneSignal HTTP %s: %s" % (ex.code, ex.read().decode("utf-8", "ignore")[:300]))
        print("OneSignal:", json.dumps(r)[:300])
        if r.get("errors") and not r.get("id"):
            print("ATTENZIONE: nessun destinatario:", r.get("errors"))
    return r

# ---------- archivio iscritti (Cloudflare Worker): sostituisce i tag di OneSignal, limitati a 6 sul piano gratuito ----------
_SUBS = None

def subs_on():
    return bool(os.environ.get("SUBS_URL") and os.environ.get("SUBS_TOKEN"))

def subs_list():
    global _SUBS
    if _SUBS is None:
        req = urllib.request.Request(os.environ["SUBS_URL"].rstrip("/") + "/list", headers={"Authorization": "Bearer " + os.environ["SUBS_TOKEN"], "User-Agent": UA})
        try:
            _SUBS = json.loads(urllib.request.urlopen(req, timeout=30).read().decode("utf-8")).get("subs") or []
        except urllib.error.HTTPError as ex:
            raise RuntimeError("Archivio iscritti: HTTP %s" % ex.code)
        print("Archivio iscritti: %d iscrizioni" % len(_SUBS))
    return _SUBS

def subs_for(topic):
    """ID delle iscrizioni che hanno scelto questo canale (stessa logica dei vecchi filtri sui tag)."""
    subs = subs_list()
    if topic.startswith("t-"):
        return [s["id"] for s in subs if topic[2:] in (s.get("f") or [])]
    cat, one = (topic[:-3], True) if topic.endswith("-1h") else (topic, False)
    base = "money" if cat in ("money", "money33") else cat
    want = "money=all" if cat == "money" else "money=33" if cat == "money33" else cat
    return [s["id"] for s in subs if want in (s.get("c") or []) and (not one or base in (s.get("h") or []))]

def log_notif(topic, title, body, click, fname):
    """Tiene le ultime notifiche inviate: il sito le mostra nella cronologia (campanella)."""
    try:
        try:
            lst = json.load(open(fname, encoding="utf-8"))
        except Exception:
            lst = []
        lst.append({"t": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "topic": topic, "title": title,
                    "body": body, "url": click if (click or "").startswith("http") else ""})
        json.dump(lst[-40:], open(fname, "w", encoding="utf-8"), ensure_ascii=False)
    except Exception as ex:
        print("Cronologia non salvata:", ex)

def deliver(topic, title, body, click):
    """Con OneSignal arriva dentro l'app; altrimenti, se c'è NTFY_PREFIX, passa da ntfy."""
    if os_on():
        if subs_on():
            ids = subs_for(topic)
            if ids:
                send_os(None, title, body, click, ids=ids)
            else:
                print("Nessun iscritto per il canale", topic)
        else:
            send_os(os_filters(topic), title, body, click)
    else:
        say(os.environ.get("NTFY_PREFIX", "") + "-" + topic, title, body, click)
    log_notif(topic, title, body, click, "notifiche_avvisi.json")

def deliver_tutti(title, body, click):
    """Avviso OBBLIGATORIO (annunci del sito): arriva a tutti gli iscritti, qualunque spunta abbiano scelto."""
    if os_on():
        if subs_on():
            ids = [s["id"] for s in subs_list() if s.get("id")]
            if ids:
                send_os(None, title, body, click, ids=ids)
            else:
                print("Nessun iscritto a cui mandare l'annuncio")
        else:
            send_os("TUTTI", title, body, click)
    else:
        say(os.environ.get("NTFY_PREFIX", "") + "-annunci", title, body, click)
    log_notif("annunci", title, body, click, "notifiche_avvisi.json")

def notify_all(events):
    if not (os.environ.get("NTFY_PREFIX") or os_on()) or not events:
        return
    first = not os.path.exists(STATE)
    sent = set(load(STATE, []))
    todo = {}  # (url, topic) -> {kind: titolo}
    added = {}  # topic -> chiavi nuove: se l'invio fallisce si tolgono, così si riprova al giro dopo
    for e in events:
        for topic, kind, title in candidates(e):
            key = "%s|%s|%s" % (e.get("url"), topic, kind)
            if key in sent:
                continue
            sent.add(key)
            if not first:
                added.setdefault(topic, []).append(key)
                todo.setdefault((e["url"], topic), {})[kind] = (title, e)
    by_topic = {}
    for (url, topic), kinds in todo.items():
        kind = "open" if "open" in kinds else next(iter(kinds))  # annuncio + iscrizioni aperte insieme: un solo avviso
        by_topic.setdefault(topic, []).append(kinds[kind])
    for topic, items in by_topic.items():
        try:
            if len(items) > 5:
                deliver(topic, "Nuovi avvisi VGC", "\n".join(e["name"] for _, e in items[:5]) + "\ne altri %d" % (len(items) - 5), os.environ.get("SITE_URL", ""))
            else:
                for title, e in items:
                    quando = e.get("date") or "data sul link"
                    if e.get("where") and topic == "locali":
                        quando += " - " + e["where"]
                    extra = (" - iscrizioni fino al " + e["regClose"]) if e.get("regClose") else ""
                    deliver(topic, title, "%s\n%s%s" % (e["name"], quando, extra), e.get("signup") or e.get("url") or "")
            print("Avvisi inviati su %s: %d" % (topic, len(items)))
        except Exception as ex:
            print("Avviso non inviato su %s: %s" % (topic, ex))
            sent.difference_update(added.get(topic, []))
    urls = {e.get("url") for e in events}
    json.dump(sorted(k for k in sent if k.split("|")[0] in urls), open(STATE, "w", encoding="utf-8"))

# ---------- unione ----------
def source_of(e):
    u = e.get("url") or ""
    if e.get("mode") == "regional":
        return "Regionali"
    if "limitlesstcg.com" in u:
        return "Limitless"
    if "victoryroad.pro" in u:
        return "Victory Road"
    return None

def ancora_valido(e, now):
    """Un torneo sparisce dall'elenco quando è finito: con orario, GRACE_H ore dopo l'inizio;
    senza orario o su più giorni, alla fine dell'ultimo giorno (ora di Roma). Senza data resta."""
    if e.get("url") in LIVE:
        return True
    d = e.get("end") or e.get("date")
    if not d:
        return True
    try:
        if e.get("time") and not e.get("end"):
            inizio = datetime.strptime(e["date"] + " " + e["time"], "%Y-%m-%d %H:%M").replace(tzinfo=ROME)
            return now < inizio + timedelta(hours=GRACE_H)
        fine = datetime.strptime(d, "%Y-%m-%d").replace(tzinfo=ROME) + timedelta(days=1)
        return now < fine
    except Exception:
        return True  # in caso di dubbio il torneo resta

def main():
    try:
        prev = json.load(open(OUT, encoding="utf-8")).get("events") or []
    except Exception:
        prev = []
    PREV.update({e["url"]: e for e in prev if e.get("url")})
    by, failed = {}, set()
    for nome, fonte in (("Limitless", limitless_all), ("Victory Road", victory_road), ("Regionali", regionali)):
        try:
            got = fonte()
            print("%s: %d eventi letti" % (nome, len(got)))
            for e in got:
                by[e["url"]] = e
        except Exception as ex:
            failed.add(nome)
            print("Errore con %s: %s" % (nome, ex))
    failed |= PARTIAL
    # se una fonte ha avuto un errore, i suoi tornei non spariscono: restano quelli del giro precedente
    for e in prev:
        u = e.get("url")
        if u and u not in by and (source_of(e) in failed or u in KEEP):
            by[u] = e
            print("Tenuto dalla copia precedente: %s" % e.get("name"))
    # se la pagina di iscrizione RK9 non si è letta, restano scadenza e costo già noti
    pmap = {e.get("url"): e for e in prev}
    for e in by.values():
        o = pmap.get(e.get("url"))
        if o and e.get("mode") == "regional":
            for k in RK9_TENUTI:
                if k not in e and k in o:
                    e[k] = o[k]
    try:  # eventi a mano: hanno la precedenza
        for e in json.load(open("manual.json", encoding="utf-8")):
            by[e["url"]] = e
    except Exception:
        pass
    ora = datetime.now(ROME)
    events = [e for e in by.values() if ancora_valido(e, ora)]
    events.sort(key=lambda e: e.get("date") or "9999")
    try:
        old = json.load(open(OUT, encoding="utf-8")).get("events")
    except Exception:
        old = None
    notify_all(events)
    if subs_on():  # controllo: quante iscrizioni ci sono nell'archivio (compare nel log, anche senza avvisi)
        try:
            subs_list()
        except Exception as ex:
            print("Archivio iscritti non letto:", ex)
    if not events or old == events:
        print("Nessuna novità")
        return
    data = {"updated": datetime.now(timezone.utc).isoformat(timespec="seconds"), "events": events}
    json.dump(data, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("Salvati %d tornei" % len(events))

if __name__ == "__main__":
    main()
