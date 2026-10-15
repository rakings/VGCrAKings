#!/usr/bin/env python3
"""Avviso "Player in evidenza": quando in news.json compare un nuovo italiano in evidenza
(top 16 di un grande torneo) manda una notifica sul canale "player".
Manda anche l'avviso "Vincitore di un Regionale" (canale "winner"): primo posto, di qualsiasi nazionalità.
Si lancia DOPO update_news.py. Riusa l'invio di update_events.py (OneSignal o ntfy).
Il primo giro non manda nulla: memorizza solo lo stato. Poi avvisa soltanto per i tornei
più recenti di quelli già noti, così il caricamento a ritroso dello storico non genera avvisi."""
import json, os
import update_events as ue

STATE = "notify_players_state.json"
TOPIC = "player"

def place(p):
    return "Vincitore" if p == 1 else "%d° posto" % p

def main():
    if not (os.environ.get("NTFY_PREFIX") or ue.os_on()):
        return
    try:
        news = json.load(open("news.json", encoding="utf-8"))
    except Exception as ex:
        print("news.json non letto:", ex)
        return
    ita = [x for x in news.get("ita") or [] if x.get("pl") and x.get("id") is not None]
    all_ids = [int(x["id"]) for x in ita] + [int(r[3]) for r in news.get("bp") or [] if len(r) > 3]
    st = ue.load(STATE, None)
    if not isinstance(st, dict):  # primo giro: si ricorda tutto, senza avvisi
        json.dump({"min_id": max(all_ids or [0]), "sent": sorted("%s|%s" % (x["pl"], x["id"]) for x in ita)},
                  open(STATE, "w", encoding="utf-8"), ensure_ascii=False)
        print("Player in evidenza: stato iniziale salvato, nessun avviso")
        return
    sent, min_id = set(st.get("sent") or []), int(st.get("min_id") or 0)
    wins = []  # vincitori dei Regionali (bp: [giocatore, paese, torneo, id, posizione])
    for r in news.get("bp") or []:
        if len(r) > 4 and r[4] == 1 and ("W|%s" % r[3]) not in sent:
            sent.add("W|%s" % r[3])
            if int(r[3]) > min_id:
                wins.append(r)
    new = []
    for x in ita:
        key = "%s|%s" % (x["pl"], x["id"])
        if key in sent:
            continue
        sent.add(key)
        if int(x["id"]) > min_id:
            new.append(x)
    site = os.environ.get("SITE_URL", "")
    try:
        if len(new) > 5:
            ue.deliver(TOPIC, "Player in evidenza", "\n".join("%s - %s" % (x["pl"], x["t"]) for x in new[:5]) + "\ne altri %d" % (len(new) - 5), site)
        else:
            for x in new:
                ue.deliver(TOPIC, "Player in evidenza: %s" % x["pl"], "%s a %s%s" % (place(x["p"]), x["t"], (" (%s)" % x["d"]) if x.get("d") else ""),
                           "https://limitlessvgc.com/tournaments/%s" % x["id"])
        for r in wins:
            ue.deliver("winner", "Vincitore Regionale: %s" % r[0], "Regional %s%s" % (r[2], (" (%s)" % r[1]) if r[1] else ""),
                       "https://limitlessvgc.com/tournaments/%s" % r[3])
        print("Avvisi inviati: %d player, %d vincitori" % (len(new), len(wins)))
    except Exception as ex:
        print("Avviso player non inviato:", ex)
        return  # lo stato non si aggiorna: si riprova al giro dopo
    json.dump({"min_id": min_id, "sent": sorted(sent)}, open(STATE, "w", encoding="utf-8"), ensure_ascii=False)

if __name__ == "__main__":
    main()
