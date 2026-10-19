#!/usr/bin/env python3
"""Promemoria circa un'ora prima dell'inizio dei tornei con orario noto.
Legge solo events.json (nessuna richiesta ad altri siti) e scrive su ntfy.sh nei canali PREFISSO-categoria-1h."""
import json, os, urllib.request, urllib.error
from update_events import sito_url
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

ROME = ZoneInfo("Europe/Rome")
STATE = "reminder_state.json"

def load(p, d):
    try:
        return json.load(open(p, encoding="utf-8"))
    except Exception:
        return d

def cats(e):
    low = ((e.get("name") or "") + " " + (e.get("org") or "")).lower()
    out = []
    if e.get("mode") == "online" and e.get("cash") is True:
        out.append("money")
        if (e.get("players") or 0) > 33:
            out.append("money33")
    if e.get("mode") == "live" or "lega" in (e.get("type") or "").lower() or e.get("local") is True:
        out.append("locali")
    if "victory road" in low:
        out.append("vr")
    if "maddo" in low:
        out.append("maddos")
    if e.get("type") == "Global Challenge":
        out.append("gc")
    return out

def tipo(e):
    low = ((e.get("name") or "") + " " + (e.get("org") or "")).lower()
    if e.get("type") == "Global Challenge":
        return "Global Challenge"
    if "victory road" in low:
        return "Victory Road"
    if "maddo" in low:
        return "Maddos Cup"
    if e.get("mode") == "live" or "lega" in (e.get("type") or "").lower() or e.get("local") is True:
        return "Torneo locale"
    if e.get("cash") is True:
        return "Money tournament"
    return "Torneo online"

def messaggio(e, start, now):
    """Titolo e testo chiari: quale torneo, tra quanto, a che ora (ora italiana), di che tipo."""
    mins = max(5, int(round((start - now).total_seconds() / 60 / 5)) * 5)
    tra = "tra circa 1 ora" if mins >= 55 else "tra %d minuti" % mins
    nome = (e.get("name") or "Torneo").strip()
    if len(nome) > 70:
        nome = nome[:67].rstrip() + "..."
    giorno = start.date() - now.date()
    quando = "oggi" if giorno.days == 0 else "domani" if giorno.days == 1 else start.strftime("%d/%m")
    righe = ["%s - inizia %s, %s alle %s (ora italiana)" % (tipo(e), tra, quando, start.strftime("%H:%M"))]
    if e.get("fee") == 0:
        righe.append("Iscrizione gratuita")
    elif e.get("fee"):
        righe.append("Iscrizione: %s%s" % (e.get("cur") or "", ("%g" % e["fee"])))
    righe.append("Tocca per aprire il torneo")
    return "Inizia %s: %s" % (tra, nome), "\n".join(righe)

def eh(u):
    h = 5381
    for ch in u:
        h = (h * 33 + ord(ch)) & 0xFFFFFFFF
    d, n = "0123456789abcdefghijklmnopqrstuvwxyz", ""
    while h:
        n = d[h % 36] + n; h //= 36
    return n or "0"

# l'invio con OneSignal (e l'archivio iscritti) è lo stesso di update_events.py
from update_events import os_on, os_filters, send_os, subs_on, subs_for

def log_notif(topic, title, body, click, fname, topics=None):
    """Tiene le ultime notifiche inviate: il sito le mostra nella cronologia (campanella)."""
    try:
        try:
            lst = json.load(open(fname, encoding="utf-8"))
        except Exception:
            lst = []
        x = {"t": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "topic": topic, "title": title,
             "body": body, "url": click if (click or "").startswith("http") else ""}
        if topics and len(topics) > 1:
            x["topics"] = topics  # canali che l'hanno richiesta: la cronologia la mostra a chi ne segue anche uno solo
        lst.append(x)
        json.dump(lst[-40:], open(fname, "w", encoding="utf-8"), ensure_ascii=False)
    except Exception as ex:
        print("Cronologia non salvata:", ex)

def deliver_union(topics, title, body, click):
    """Un SOLO promemoria per torneo a chi ha attiva la categoria, a chi ha premuto il + sul torneo, o a entrambi.
    Con l'archivio iscritti si uniscono gli elenchi e nessuno riceve due volte lo stesso avviso."""
    if os_on():
        if subs_on():
            ids = []
            for t in topics:
                for i in subs_for(t):
                    if i not in ids:
                        ids.append(i)
            if ids:
                send_os(None, title, body, click, ids=ids)
            else:
                print("Nessun iscritto per i canali", topics)
        else:  # vecchio sistema a tag: i filtri non si possono unire, un invio per canale
            for t in topics:
                send_os(os_filters(t), title, body, click)
    else:
        for t in topics:
            say(os.environ.get("NTFY_PREFIX", "") + "-" + t, title, body, click)
    log_notif(topics[0], title, body, click, "notifiche_promemoria.json", topics)

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
    log_notif(topic, title, body, click, "notifiche_promemoria.json")

def say(topic, title, body, click):
    head = {"Title": title.encode("ascii", "ignore").decode(), "Tags": "alarm_clock"}
    if click.startswith("http"):
        head["Click"] = click
    if os.environ.get("SITE_URL", "").startswith("http"):
        head["Icon"] = os.environ["SITE_URL"].rstrip("/") + "/icon-192.png"
    req = urllib.request.Request("https://ntfy.sh/" + topic, data=body.encode("utf-8"), headers=head, method="POST")
    urllib.request.urlopen(req, timeout=30).read()

def main():
    if not (os.environ.get("NTFY_PREFIX") or os_on()):
        print("Né OneSignal né NTFY_PREFIX impostati"); return
    now = datetime.now(ROME)
    sent = load(STATE, {})
    ev = load("events.json", {}).get("events", [])
    for e in ev:
        if not (e.get("date") and e.get("time")):
            continue
        try:
            start = datetime.fromisoformat(e["date"] + "T" + e["time"]).replace(tzinfo=ROME)
        except Exception:
            continue
        if not timedelta(0) < start - now <= timedelta(minutes=70):
            continue
        # categorie del torneo + canale del singolo torneo (chi lo segue con il +): UN solo invio all'unione degli iscritti
        topics = [c + "-1h" for c in cats(e)] + ["t-" + eh(e.get("url") or "")]
        key = "%s|1h" % e.get("url")
        if any(k.startswith("%s|" % e.get("url")) for k in sent):  # compresi i vecchi segni "url|categoria"
            continue
        try:
            titolo, testo = messaggio(e, start, now)
            deliver_union(topics, titolo, testo, e.get("signup") or e.get("url") or sito_url(topics[0]))
            sent[key] = start.isoformat()
            print("Promemoria:", e["name"], topics)
        except Exception as ex:
            print("Promemoria non inviato:", ex)
    sent = {k: v for k, v in sent.items() if datetime.fromisoformat(v) > now - timedelta(days=2)}
    json.dump(sent, open(STATE, "w", encoding="utf-8"))

main()
