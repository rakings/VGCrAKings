#!/usr/bin/env python3
"""Repository PUBBLICO. Parte quando locali.json o annunci.json cambiano (dopo 3 minuti di attesa, nel workflow).
  - report dei locali approvati nelle ultime 24 ore: notifica al canale "locali8" (solo a chi ha la spunta)
  - annunci approvati nelle ultime 24 ore: notifica OBBLIGATORIA a tutti gli iscritti
Se nel frattempo hai tolto il report/annuncio con "rimosso", non c'è più nei file e non parte nulla."""
import os, sys
from datetime import datetime, timedelta, timezone

from locali_comune import carica_annunci, carica_locali, carica_stato, log, salva_stato


def main():
    limite = (datetime.now(timezone.utc) - timedelta(hours=24)).strftime("%Y-%m-%dT%H:%M:%SZ")
    stato = carica_stato()
    nuovi = [v for v in carica_locali()["locali"]
             if v.get("real") and v.get("pub", "") >= limite and v.get("id") not in stato["notificati"]]
    ann = [v for v in carica_annunci()["annunci"]
           if v.get("t") and v.get("pub", "") >= limite and v.get("id") not in stato["notificati"]]
    if not nuovi and not ann:
        log("Nessuna novità da notificare.")
        return 0
    import update_events as ue  # stesso invio delle altre notifiche (OneSignal o ntfy)
    sito = ue.sito_url().rstrip("/")
    for v in sorted(nuovi, key=lambda x: x["pub"]):
        ue.deliver("locali8", "Nuova top 8: %s" % v["s"], "%s · %s · %s" % (v["t"], v["c"], v["d"]), sito + "/#locali")
        stato["notificati"].append(v["id"])
        salva_stato(stato)
        log("Notifica inviata per il report %s." % v["id"])
    for v in sorted(ann, key=lambda x: x["pub"]):
        testo = (v.get("d") or "").replace("\n", " ").strip()
        ue.deliver_tutti("Annuncio: %s" % v["t"], (testo[:140] + "…") if len(testo) > 140 else testo or "Apri il sito per i dettagli.",
                       "%s/#annuncio-%s" % (sito, v["id"]))
        stato["notificati"].append(v["id"])
        salva_stato(stato)
        log("Notifica a tutti inviata per l'annuncio %s." % v["id"])
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except RuntimeError as ex:
        log("[ERRORE]", ex)
        sys.exit(1)
