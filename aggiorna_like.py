#!/usr/bin/env python3
"""Copia ogni ora i numeri dei «mi piace» della bacheca dal Worker (database D1) nel file likes.json del sito.
Il sito legge i numeri da qui (GitHub), cosi' chi guarda la bacheca non pesa mai su Cloudflare.
Scrive il file SOLO se i numeri sono cambiati. Se i like non sono attivi (manca il database) non fa niente."""
import json, os, sys, urllib.error, urllib.request
from datetime import datetime, timezone

FILE = "likes.json"


def main(env=None):
    e = env if env is not None else os.environ
    url, tok = (e.get("SUBS_URL") or "").rstrip("/"), e.get("SUBS_TOKEN") or ""
    if not url or not tok:
        print("Mancano SUBS_URL o SUBS_TOKEN: niente da fare.")
        return 0
    try:
        req = urllib.request.Request(url + "/like/conteggi", headers={"Authorization": "Bearer " + tok, "User-Agent": "rakings-bot like"})
        d = json.loads(urllib.request.urlopen(req, timeout=30).read().decode("utf-8"))
    except urllib.error.HTTPError as ex:
        print("Like non letti (HTTP %s): %s" % (ex.code, "database non ancora collegato" if ex.code == 503 else "riprovo al prossimo giro"))
        return 0
    except Exception as ex:
        print("Like non letti (%s): riprovo al prossimo giro." % str(ex)[:100])
        return 0
    try:
        validi = {str(a.get("id")) for a in json.load(open("annunci.json", encoding="utf-8")).get("annunci", [])}
    except Exception:
        validi = None
    c = {k: int(v) for k, v in (d.get("c") or {}).items() if str(k).isdigit() and int(v) > 0 and (validi is None or k in validi)}
    try:
        vecchio = json.load(open(FILE, encoding="utf-8")).get("c")
    except Exception:
        vecchio = None
    if vecchio == c:
        print("Like invariati (%d annunci con like): file non toccato." % len(c))
        return 0
    with open(FILE, "w", encoding="utf-8") as f:
        json.dump({"updated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "c": c}, f, separators=(",", ":"))
        f.write("\n")
    print("likes.json aggiornato: %d annunci con like, %d like in tutto." % (len(c), sum(c.values())))
    return 0


if __name__ == "__main__":
    sys.exit(main())
