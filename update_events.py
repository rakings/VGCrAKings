#!/usr/bin/env python3
"""Raccoglie i tornei VGC da Limitless e da Victory Road e salva events.json.
Usa solo la libreria standard. Gli eventi di manual.json hanno la precedenza."""
import html, json, os, re, time, urllib.parse, urllib.request
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

API = "https://play.limitlesstcg.com/api/tournaments"
VR = "https://victoryroad.pro/"
OUT = "events.json"
ROME = ZoneInfo("Europe/Rome")
MESI = ["january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december"]
UA = "tornei-vgc-bot (sito della community, con link alle fonti)"

def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    key = os.environ.get("LIMITLESS_KEY")
    if key and url.startswith(API):
        req.add_header("X-Access-Key", key)
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "replace")

# ---------- Limitless ----------
def limitless():
    q = urllib.parse.urlencode({"game": "VGC", "limit": 100})
    out = []
    for t in json.loads(get(API + "?" + q)):
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
        out.append({
            "name": name, "org": org.get("name", "") if isinstance(org, dict) else "",
            "mode": "online", "type": "Torneo", "fee": None,
            "cash": True if money else None,  # mai False: senza indicazione resta "non indicato"
            "prize": money.group(0).strip() if money else "",
            "reg": reg.group(0).upper() if reg else None,
            "bo": "Bo" + bo.group(1) if bo else None,
            "date": date, "time": hhmm, "players": t.get("players"),
            "url": "https://play.limitlesstcg.com/tournament/%s/details" % t["id"],
        })
    return out

# ---------- Victory Road ----------
def vr_slugs():
    now = datetime.now(timezone.utc)
    sigle = [m[:3] for m in MESI]
    out = []
    for k in range(3):  # mese corrente e i due successivi
        i = now.month - 1 + k
        for suf in ["", "-2", "-3", "-4", "-5"]:
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
        try:
            ev = vr_parse(slug, get(VR + slug + "/"))
        except Exception:
            continue  # pagina inesistente
        if ev:
            out.append(ev)
    return out

# ---------- Regionali ----------
MESI_EN = ["january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december"]

def plain(page):
    t = re.sub(r"<(script|style).*?</\1>", " ", page, flags=re.S | re.I)
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", t)).replace("\xa0", " "))

def rk9_info(e):
    """Legge scadenza e costo dell'iscrizione dalla pagina RK9, se il Regionale ha un link."""
    s = e.get("signup") or ""
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

def regionali():
    out = json.load(open("regionali.json", encoding="utf-8"))
    for e in out:
        try:
            rk9_info(e)
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
        if e.get("signup") or e.get("regClose"):
            out.append(("regionali", "open", "Regionali: iscrizioni aperte"))
        dd = days_to(e["regClose"]) if e.get("regClose") else None
        if dd is not None and 0 <= dd <= 3:
            out.append(("regionali", "close", "Regionali: iscrizioni in chiusura"))
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

def send_os(filters, title, body, click):
    data = {"app_id": os.environ["ONESIGNAL_APP_ID"], "target_channel": "push", "filters": filters,
            "headings": {"en": title, "it": title}, "contents": {"en": body, "it": body}}
    if click.startswith("http"):
        data["url"] = click
    site = os.environ.get("SITE_URL", "").rstrip("/")
    if site.startswith("http"):  # logo accanto alla notifica
        data["chrome_web_icon"] = site + "/icon-192.png"
        data["chrome_web_badge"] = site + "/badge-96.png"
    req = urllib.request.Request("https://api.onesignal.com/notifications", data=json.dumps(data).encode("utf-8"), method="POST",
                                 headers={"Content-Type": "application/json", "Authorization": "Key " + os.environ["ONESIGNAL_API_KEY"]})
    urllib.request.urlopen(req, timeout=30).read()

def deliver(topic, title, body, click):
    """Con OneSignal arriva dentro l'app; altrimenti, se c'è NTFY_PREFIX, passa da ntfy."""
    if os_on():
        send_os(os_filters(topic), title, body, click)
    else:
        say(os.environ.get("NTFY_PREFIX", "") + "-" + topic, title, body, click)

def notify_all(events):
    if not (os.environ.get("NTFY_PREFIX") or os_on()) or not events:
        return
    first = not os.path.exists(STATE)
    sent = set(load(STATE, []))
    todo = {}  # (url, topic) -> {kind: titolo}
    for e in events:
        for topic, kind, title in candidates(e):
            key = "%s|%s|%s" % (e.get("url"), topic, kind)
            if key in sent:
                continue
            sent.add(key)
            if not first:
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
                    extra = (" - iscrizioni fino al " + e["regClose"]) if e.get("regClose") else ""
                    deliver(topic, title, "%s\n%s%s" % (e["name"], quando, extra), e.get("signup") or e.get("url") or "")
            print("Avvisi inviati su %s: %d" % (topic, len(items)))
        except Exception as ex:
            print("Avviso non inviato su %s: %s" % (topic, ex))
    urls = {e.get("url") for e in events}
    json.dump(sorted(k for k in sent if k.split("|")[0] in urls), open(STATE, "w", encoding="utf-8"))

# ---------- unione ----------
def main():
    by = {}
    for nome, fonte in (("Limitless", limitless), ("Victory Road", victory_road), ("Regionali", regionali)):
        try:
            for e in fonte():
                by[e["url"]] = e
        except Exception as ex:
            print("Errore con %s: %s" % (nome, ex))
    try:  # eventi a mano: hanno la precedenza
        for e in json.load(open("manual.json", encoding="utf-8")):
            by[e["url"]] = e
    except Exception:
        pass
    limit = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")
    events = [e for e in by.values() if (e.get("end") or e.get("date") or "9999") >= limit]
    events.sort(key=lambda e: e.get("date") or "9999")
    try:
        old = json.load(open(OUT, encoding="utf-8")).get("events")
    except Exception:
        old = None
    notify_all(events)
    if not events or old == events:
        print("Nessuna novità")
        return
    data = {"updated": datetime.now(timezone.utc).isoformat(timespec="seconds"), "events": events}
    json.dump(data, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("Salvati %d tornei" % len(events))

main()
