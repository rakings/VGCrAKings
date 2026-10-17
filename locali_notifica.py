#!/usr/bin/env python3
"""Repository PUBBLICO. Parte quando locali.json cambia (dopo 3 minuti di attesa, nel workflow).
Manda la notifica al canale "locali8" per i report approvati nelle ultime 24 ore e non ancora notificati.
Se nel frattempo il report è stato tolto con "rimosso", non c'è più in locali.json e non parte nulla."""
import os, sys
from datetime import datetime, timedelta, timezone

from locali_comune import carica_locali, carica_stato, log, salva_stato


def main():
    limite = (datetime.now(timezone.utc) - timedelta(hours=24)).strftime("%Y-%m-%dT%H:%M:%SZ")
    stato = carica_stato()
    nuovi = [v for v in carica_locali()["locali"]
             if v.get("real") and v.get("pub", "") >= limite and v.get("id") not in stato["notificati"]]
    if not nuovi:
        log("Nessun report nuovo da notificare.")
        return 0
    import update_events as ue  # stesso invio delle altre notifiche (OneSignal o ntfy)
    for v in sorted(nuovi, key=lambda x: x["pub"]):
        ue.deliver("locali8", "Nuova top 8: %s" % v["s"], "%s · %s · %s" % (v["t"], v["c"], v["d"]),
                   os.environ.get("SITE_URL", ""))
        stato["notificati"].append(v["id"])
        salva_stato(stato)
        log("Notifica inviata per il report %s." % v["id"])
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except RuntimeError as ex:
        log("[ERRORE]", ex)
        sys.exit(1)
