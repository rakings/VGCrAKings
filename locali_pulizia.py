#!/usr/bin/env python3
"""Repository PUBBLICO. Toglie da locali.json i report più vecchi di 4 mesi e 22 giorni (142 giorni).
I report senza data ("iso"), per esempio scritti a mano, non vengono toccati."""
import sys
from datetime import datetime, timedelta, timezone

from locali_comune import RETENTION_GIORNI, carica_locali, log, salva_locali


def main():
    d = carica_locali()
    limite = (datetime.now(timezone.utc).date() - timedelta(days=RETENTION_GIORNI)).isoformat()
    tenuti = [v for v in d["locali"] if not v.get("iso") or v["iso"] >= limite]
    tolti = len(d["locali"]) - len(tenuti)
    if tolti:
        d["locali"] = tenuti
        salva_locali(d)
    log("Report tolti perché più vecchi di %d giorni: %d" % (RETENTION_GIORNI, tolti))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except RuntimeError as ex:
        log("[ERRORE]", ex)
        sys.exit(1)
