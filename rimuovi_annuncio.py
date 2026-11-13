#!/usr/bin/env python3
"""Toglie dalla bacheca (annunci.json) un annuncio di un PARTNER (Francesco Pardini), con la sua immagine.
Lo lancia SOLO il Worker, quando Andrea preme «Cancella» nella sua pagina admin privata. Gli annunci di Andrea
(senza «partner») NON si toccano mai da qui: quelli si tolgono come sempre con l'etichetta «rimosso» nella repo privata."""
import os, re, sys

import locali_comune as LC


def main(env=None, radice="."):
    e = env if env is not None else os.environ
    id_ = (e.get("AR_ID") or "").strip()
    if not re.fullmatch(r"\d{9,11}", id_):
        print("Id non valido: non tolgo niente.")
        return 1
    path = os.path.join(radice, LC.ANNUNCI)
    a = LC.carica_annunci(path)
    trovati = [v for v in a["annunci"] if str(v.get("id")) == id_ and v.get("partner")]
    if not trovati:
        print("Nessun annuncio di un partner con id %s (gia' tolto, oppure e' un tuo annuncio): niente da fare." % id_)
        return 0
    for v in trovati:
        if re.fullmatch(r"img/annunci/\d+\.jpg", v.get("img") or ""):
            try:
                os.remove(os.path.join(radice, v["img"]))
                print("Immagine tolta: %s" % v["img"])
            except OSError:
                pass
    a["annunci"] = [v for v in a["annunci"] if not (str(v.get("id")) == id_ and v.get("partner"))]
    LC.salva_annunci(a, path)
    print("Annuncio %s tolto dalla bacheca: «%s»." % (id_, trovati[0].get("t", "")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
