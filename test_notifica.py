#!/usr/bin/env python3
"""Manda una notifica di prova a TUTTI gli iscritti di OneSignal (senza filtri sui tag)
e stampa la risposta di OneSignal, così si vede subito se chiave/ID sono giusti e quanti iscritti ci sono."""
import json, os, urllib.request, urllib.error

if os.environ.get("FCM_SERVICE_ACCOUNT"):  # Firebase: stesso invio usato dagli avvisi veri
    import update_events as ue
    if not ue.subs_on():
        print("ERRORE: mancano SUBS_URL (variabile) o SUBS_TOKEN (secret) su GitHub.")
        raise SystemExit(1)
    topic = os.environ.get("TEST_TOPIC", "").strip() or "TUTTI"
    titolo, testo = "Prova rAKings VGC", "Se leggi questo, le notifiche funzionano (canale: %s)." % topic
    try:
        if topic.upper() == "TUTTI":
            ue.deliver_tutti(titolo, testo, ue.sito_url())
        else:
            ue.deliver(topic, titolo, testo, ue.sito_url())
    except RuntimeError as ex:
        print("ERRORE:", ex)
        raise SystemExit(1)
    raise SystemExit(0)

app = os.environ.get("ONESIGNAL_APP_ID", "")
key = os.environ.get("ONESIGNAL_API_KEY", "")
if not app or not key:
    print("ERRORE: manca ONESIGNAL_APP_ID (variabile) o ONESIGNAL_API_KEY (secret) su GitHub.")
    raise SystemExit(1)

for seg in ("Total Subscriptions", "Subscribed Users"):
    data = {"app_id": app, "target_channel": "push", "included_segments": [seg],
            "headings": {"en": "Prova rAKings VGC"}, "contents": {"en": "Se leggi questo, le notifiche funzionano."}}
    site = os.environ.get("SITE_URL", "").rstrip("/")
    if site.startswith("http"):
        data["url"] = site
        data["chrome_web_icon"] = site + "/icon-192.png"
    req = urllib.request.Request("https://api.onesignal.com/notifications", data=json.dumps(data).encode("utf-8"), method="POST",
                                 headers={"Content-Type": "application/json", "Authorization": "Key " + key})
    try:
        r = json.loads(urllib.request.urlopen(req, timeout=30).read().decode("utf-8") or "{}")
        print("Segmento:", seg, "->", json.dumps(r))
        if r.get("id"):
            print("OK: notifica accettata da OneSignal (id %s)." % r["id"])
            break
        print("Nessun destinatario in questo segmento.")
    except urllib.error.HTTPError as ex:
        print("ERRORE HTTP %s con il segmento %s: %s" % (ex.code, seg, ex.read().decode("utf-8", "ignore")[:400]))
        if ex.code in (401, 403):
            print("-> La REST API Key è sbagliata o non è di questa app (controlla il secret ONESIGNAL_API_KEY).")
            break
