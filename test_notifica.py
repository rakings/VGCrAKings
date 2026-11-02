#!/usr/bin/env python3
"""Prova delle notifiche (Firebase). Canale CONTA = solo conteggi per canale, senza inviare nulla; un canale (per esempio regionali)
= avviso di prova a chi lo ha scelto; vuoto o TUTTI = avviso di prova a tutti gli iscritti."""
import os

if os.environ.get("FCM_SERVICE_ACCOUNT"):  # stesso invio usato dagli avvisi veri
    import update_events as ue
    if not ue.subs_on():
        print("ERRORE: mancano SUBS_URL (variabile) o SUBS_TOKEN (secret) su GitHub.")
        raise SystemExit(1)
    topic = os.environ.get("TEST_TOPIC", "").strip() or "TUTTI"
    if topic.upper() == "CONTA":  # solo conteggi per canale: niente invii, nessun codice stampato
        tot = len(ue.subs_list())
        print("Dispositivi Firebase nell'archivio: %d" % tot)
        for c in ["money", "money33", "gc", "regionali", "vr", "vrreg", "maddos", "locali", "locali8", "player", "winner", "vrwin"]:
            print("  canale %-9s %d dispositivi" % (c, len(ue.subs_for(c))))
        for c in ["money-1h", "money33-1h", "gc-1h", "vr-1h", "locali-1h", "maddos-1h"]:
            print("  promemoria %-11s %d dispositivi" % (c, len(ue.subs_for(c))))
        raise SystemExit(0)
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

print("ERRORE: manca FCM_SERVICE_ACCOUNT (secret) su GitHub: le notifiche partono da Firebase.")
raise SystemExit(1)
