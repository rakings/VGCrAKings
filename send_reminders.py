#!/usr/bin/env python3
"""Promemoria circa un'ora prima dell'inizio dei tornei con orario noto.
Legge solo events.json (nessuna richiesta ad altri siti) e scrive su ntfy.sh nei canali PREFISSO-categoria-1h."""
import json, os, urllib.request
from datetime import datetime, timedelta
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
    if "victory road" in low:
        out.append("vr")
    if "maddo" in low:
        out.append("maddos")
    if e.get("type") == "Global Challenge":
        out.append("gc")
    return out

def eh(u):
    h = 5381
    for ch in u:
        h = (h * 33 + ord(ch)) & 0xFFFFFFFF
    d, n = "0123456789abcdefghijklmnopqrstuvwxyz", ""
    while h:
        n = d[h % 36] + n; h //= 36
    return n or "0"

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
        # canali per categoria e canale del singolo torneo (per chi lo segue con il +)
        for c, topic in [(c, c + "-1h") for c in cats(e)] + [("t", "t-" + eh(e.get("url") or ""))]:
            key = "%s|%s" % (e.get("url"), c)
            if key in sent:
                continue
            try:
                deliver(topic, "Tra circa un'ora", "%s\nInizio alle %s" % (e["name"], e["time"]), e.get("signup") or e.get("url") or "")
                sent[key] = start.isoformat()
                print("Promemoria:", c, e["name"])
            except Exception as ex:
                print("Promemoria non inviato:", ex)
    sent = {k: v for k, v in sent.items() if datetime.fromisoformat(v) > now - timedelta(days=2)}
    json.dump(sent, open(STATE, "w", encoding="utf-8"))

main()
