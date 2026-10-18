#!/usr/bin/env python3
"""Repository PUBBLICO. Pulizia giornaliera:
  - toglie da locali.json i report più vecchi di 4 mesi e 22 giorni (142 giorni); i report senza data ("iso") non si toccano
  - toglie da annunci.json gli annunci scaduti (data "exp")"""
import os, re, sys
from datetime import datetime, timedelta, timezone

from locali_comune import RETENTION_GIORNI, carica_annunci, carica_locali, log, salva_annunci, salva_locali


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
    validi = [v for v in a["annunci"] if not v.get("exp") or v["exp"] >= oggi.isoformat()]
    scaduti = len(a["annunci"]) - len(validi)
    if scaduti:
        for v in a["annunci"]:
            if v not in validi and re.match(r"^img/annunci/\d+\.jpg$", v.get("img") or ""):
                try:
                    os.remove(v["img"])
                except OSError:
                    pass
        a["annunci"] = validi
        salva_annunci(a)
    log("Annunci scaduti tolti: %d" % scaduti)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except RuntimeError as ex:
        log("[ERRORE]", ex)
        sys.exit(1)
