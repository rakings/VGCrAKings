#!/usr/bin/env python3
"""Repository PUBBLICO. Pulizia giornaliera:
  - toglie da locali.json i report più vecchi di 4 mesi e 22 giorni (142 giorni); i report senza data ("iso") non si toccano
  - tiene al massimo 62 annunci in annunci.json: si tolgono i più vecchi NON fissati, con le loro foto
    (i fissati non si cancellano mai; gli annunci non hanno scadenza)"""
import sys
from datetime import datetime, timedelta, timezone

from locali_comune import (ANNUNCI_MAX, RETENTION_GIORNI, carica_annunci, carica_locali, log, salva_annunci, salva_locali,
                           taglia_annunci)


def main():
    oggi = datetime.now(timezone.utc).date()
    d = carica_locali()
    limite = (oggi - timedelta(days=RETENTION_GIORNI)).isoformat()
    tenuti = [v for v in d["locali"] if not v.get("iso") or v["iso"] >= limite]
    tolti = len(d["locali"]) - len(tenuti)
    if tolti:
        d["locali"] = tenuti
        salva_locali(d)
    log("Report tolti perché più vecchi di %d giorni: %d" % (RETENTION_GIORNI, tolti))
    a = carica_annunci()
    fuori = taglia_annunci(a, ".")
    if fuori:
        salva_annunci(a)
    log("Annunci tolti per il limite di %d: %d" % (ANNUNCI_MAX, len(fuori)))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except RuntimeError as ex:
        log("[ERRORE]", ex)
        sys.exit(1)
