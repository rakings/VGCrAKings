#!/usr/bin/env python3
"""Avviso di un partner (creator) sul suo canale: lo lancia SOLO il Worker vgc-subs, dopo aver controllato il codice del partner,
i testi, il link e i limiti (pagina partner-pardini.html). Qui si ricontrolla tutto: un avviso strano non parte.
L'avviso va solo a chi ha attivo il canale del partner. Non entra nella cronologia del server ne' nelle proposte per X."""
import os, re, sys
from urllib.parse import urlparse

import update_events as ue

PARTNER = {"pardini": "pardini"}          # partner -> canale
HOST_OK = re.compile(r"^((www\.|m\.)?(twitch\.tv|youtube\.com|youtu\.be)|rakings\.github\.io)$", re.I)


def pulisci(s, n):
    return re.sub(r"\s+", " ", re.sub(r"[\x00-\x1f\x7f]+", " ", str(s or ""))).strip()[:n]


def main(env=None):
    e = env if env is not None else os.environ
    p = (e.get("AP_PARTNER") or "").strip()
    canale = PARTNER.get(p)
    titolo, testo, link = pulisci(e.get("AP_TITOLO"), 60), pulisci(e.get("AP_TESTO"), 180), pulisci(e.get("AP_LINK"), 300)
    if not canale or len(titolo) < 3 or len(testo) < 3:
        print("Avviso partner: dati non validi (partner=%r): non mando niente." % p)
        return 1
    if link:
        u = urlparse(link)
        if u.scheme != "https" or not HOST_OK.match(u.hostname or ""):
            print("Avviso partner: link non ammesso: non mando niente.")
            return 1
    else:
        link = ue.sito_url()
    if not ue.push_on() or not ue.subs_on():
        print("Avviso partner: notifiche non configurate.")
        return 1
    print("Avviso partner (%s, canale %s): %s | %s | %s" % (p, canale, titolo, testo, link))
    ue._invia([canale], titolo, testo, link)
    print("Avviso partner inviato.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
