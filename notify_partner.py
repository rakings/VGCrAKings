#!/usr/bin/env python3
"""Avviso di un partner (creator) sul suo canale: lo lancia SOLO il Worker vgc-subs, dopo aver controllato il codice del partner,
i testi, il link e i limiti (pagina partner-pardini.html). Qui si ricontrolla tutto: un avviso strano non parte.

Due fasi (vedi avviso-partner.yml):
  --bacheca : gli avvisi scritti escono anche in bacheca (annunci.json) con l'etichetta del partner, l'articolo e l'immagine
              facoltativa (scaricata dal Worker con il codice admin e salvata in img/annunci/<id>.jpg). Poi il flusso salva su GitHub.
  --invia   : la notifica, SOLO a chi ha attivo il canale del partner (facoltativa, non obbligatoria come gli annunci di Andrea).
Gli annunci del partner NON fanno partire la notifica obbligatoria a tutti (locali_notifica.py li salta) e sono al massimo
PARTNER_MAX in bacheca: i piu' vecchi si tolgono da soli, con le loro immagini."""
import base64, json, os, re, sys, urllib.request
from datetime import datetime, timezone
from urllib.parse import urlparse

PARTNER = {"pardini": "pardini"}          # partner -> canale
HOST_OK = re.compile(r"^((www\.|m\.)?(twitch\.tv|youtube\.com|youtu\.be)|rakings\.github\.io)$", re.I)
PARTNER_MAX = 20                           # annunci del partner tenuti in bacheca
ANNUNCI = "annunci.json"
STATO = "partner_state.json"               # passa dalla fase --bacheca alla fase --invia (non va salvato su GitHub)


def pulisci(s, n):
    return re.sub(r"\s+", " ", re.sub(r"[\x00-\x1f\x7f]+", " ", str(s or ""))).strip()[:n]


def articolo_pulito(s):
    t = re.sub(r"[\x00-\x09\x0b-\x1f\x7f]+", " ", str(s or "").replace("\r", ""))
    return re.sub(r"\n{3,}", "\n\n", t).strip()[:2000]


def dati(e):
    p = (e.get("AP_PARTNER") or "").strip()
    d = {"partner": p, "canale": PARTNER.get(p), "id": (e.get("AP_ID") or "").strip(),
         "titolo": pulisci(e.get("AP_TITOLO"), 60), "testo": pulisci(e.get("AP_TESTO"), 180), "link": pulisci(e.get("AP_LINK"), 300),
         "bacheca": (e.get("AP_BACHECA") or "") == "1", "articolo": articolo_pulito(e.get("AP_ARTICOLO")), "img": (e.get("AP_IMG") or "") == "1"}
    if not d["canale"] or len(d["titolo"]) < 3 or len(d["testo"]) < 3:
        raise ValueError("dati non validi (partner=%r)" % p)
    if d["bacheca"] and not re.fullmatch(r"\d{9,11}", d["id"]):
        raise ValueError("id dell'annuncio non valido")
    if d["link"]:
        u = urlparse(d["link"])
        if u.scheme != "https" or not HOST_OK.match(u.hostname or ""):
            raise ValueError("link non ammesso")
    return d


def scarica_img(e, id_):
    """L'immagine (base64 di un JPEG) dal Worker, con il codice admin. Ritorna i byte o None. Controlla che sia davvero un JPEG."""
    url = (e.get("SUBS_URL") or "").rstrip("/") + "/partner/img/" + id_
    req = urllib.request.Request(url, headers={"Authorization": "Bearer " + (e.get("SUBS_TOKEN") or ""), "User-Agent": "rakings-bot partner"})
    try:
        b = base64.b64decode(urllib.request.urlopen(req, timeout=30).read(), validate=True)
    except Exception as ex:
        print("Immagine non scaricata (%s): l'annuncio esce senza immagine." % str(ex)[:100])
        return None
    if len(b) < 100 or len(b) > 1400000 or b[:3] != b"\xff\xd8\xff":
        print("Immagine non valida: l'annuncio esce senza immagine.")
        return None
    return b


def bacheca(e, radice="."):
    import locali_comune as LC
    d = dati(e)
    if not d["bacheca"]:
        print("Avviso «live»: niente bacheca.")
        return 0
    a = LC.carica_annunci(os.path.join(radice, ANNUNCI))
    num = int(d["id"])
    if any(v.get("id") == num for v in a["annunci"]):
        print("Annuncio %s gia' in bacheca." % num)
    else:
        voce = {"id": num, "t": d["titolo"], "d": d["articolo"] or d["testo"], "pub": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "partner": d["partner"]}
        if d["link"]:
            voce["link"] = d["link"]
        if d["img"]:
            b = scarica_img(e, d["id"])
            if b:
                os.makedirs(os.path.join(radice, "img", "annunci"), exist_ok=True)
                with open(os.path.join(radice, "img", "annunci", "%d.jpg" % num), "wb") as f:
                    f.write(b)
                voce["img"] = "img/annunci/%d.jpg" % num
        a["annunci"].append(voce)
        # al massimo PARTNER_MAX annunci del partner: si tolgono i piu' vecchi (con l'immagine). Quelli di Andrea non si toccano.
        miei = sorted([v for v in a["annunci"] if v.get("partner") == d["partner"]], key=lambda v: v.get("pub", ""))
        via = miei[:max(0, len(miei) - PARTNER_MAX)]
        for v in via:
            if re.fullmatch(r"img/annunci/\d+\.jpg", v.get("img") or ""):
                try:
                    os.remove(os.path.join(radice, v["img"]))
                except OSError:
                    pass
        tolti = {id(v) for v in via}
        a["annunci"] = [v for v in a["annunci"] if id(v) not in tolti]
        LC.salva_annunci(a, os.path.join(radice, ANNUNCI))
        print("Annuncio %s in bacheca%s%s." % (num, " con immagine" if voce.get("img") else "", (", tolti %d vecchi" % len(via)) if via else ""))
    with open(os.path.join(radice, STATO), "w", encoding="utf-8") as f:
        json.dump({"id": num}, f)
    return 0


def invia(e):
    import update_events as ue
    d = dati(e)
    link = d["link"]
    if not link:
        base = ue.sito_url().split("#")[0].rstrip("/")
        link = base + ("/#annuncio-%s" % d["id"] if d["bacheca"] and os.path.exists(STATO) else "/")
    if not ue.push_on() or not ue.subs_on():
        print("Avviso partner: notifiche non configurate.")
        return 1
    print("Avviso partner (%s, canale %s): %s | %s | %s" % (d["partner"], d["canale"], d["titolo"], d["testo"], link))
    ue._invia([d["canale"]], d["titolo"], d["testo"], link)
    print("Avviso partner inviato.")
    return 0


def main(argv=None, env=None):
    e = env if env is not None else os.environ
    fase = (argv or sys.argv[1:] or ["--invia"])[0]
    try:
        return bacheca(e) if fase == "--bacheca" else invia(e)
    except ValueError as ex:
        print("Avviso partner: %s: non mando niente." % ex)
        return 1


if __name__ == "__main__":
    sys.exit(main())
